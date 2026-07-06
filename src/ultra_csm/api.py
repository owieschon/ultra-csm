"""REST API for the Ultra CSM system.

Boots an ephemeral Postgres, seeds governance and fixture data, then serves
a FastAPI application with endpoints for account scoring, sweeps, governance
proposals, and daily digest.
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import psycopg
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ultra_csm.logging_config import setup_logging
from ultra_csm.platform import EphemeralCluster
from ultra_csm.platform.db import apply_migrations, session
from ultra_csm.platform.seed import det_uuid, seed, SEED_CLOCK

from ultra_csm.data_plane import (
    CustomerDataPlane,
    DEFAULT_TENANT,
    build_sweep_fixture_data_plane,
)
from ultra_csm.governance import (
    ActionGate,
    ActionProposal,
    FixtureVerdictSource,
    GateError,
    Verdict,
    seed_roster,
    make_principal,
    ROLE_CS_ORCHESTRATOR,
)
from ultra_csm.value_model import (
    account_attributes,
    build_customer_value_model,
    load_value_model_config,
    project_ttv_lens,
    resolve_tenant_tier,
)
from ultra_csm.agent1 import collapse_cohorts, run_time_to_value_sweep
from ultra_csm.knowledge import load_playbooks
from ultra_csm.agent1.precedence import (
    ActionPacket,
    FindingPacket,
    approval_decision,
    evaluate_precedence,
    load_precedence_config,
)
from ultra_csm.api_metrics import APIMetrics, SweepTiming
from ultra_csm.cohort_packets import build_cohort_rollup_packets
from ultra_csm.cost_tracker import CostBudget, CostTracker
from ultra_csm.proposal_revise import ReviseServiceError, apply_bounded_revise
from ultra_csm._api_helpers import (
    AccountDataError,
    AuthError,
    _build_account_brief,
    _enrich_person_evidence,
    _proposal_has_contact_consent,
    _score_one_account,
    auth_marker,
    demo_noauth_enabled,
    parse_api_tokens,
    resolve_write_principal,
    score_account_priority,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
_CLOCK = SEED_CLOCK
_AS_OF = "2026-06-27"

_TENANT_NAME = "acme-csm"
_TENANT_ID = det_uuid("tenant", _TENANT_NAME)
_SEED_AGENT = det_uuid("principal", _TENANT_NAME, "system-seed")

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state populated by lifespan
# ---------------------------------------------------------------------------

_cluster: EphemeralCluster | None = None
_conn: psycopg.Connection | None = None
_data_plane: CustomerDataPlane | None = None
_orch_principal: str | None = None

# Cost tracking and API metrics — initialised at import time so the
# middleware and /metrics endpoint can reference them immediately.
_cost_tracker = CostTracker()
_api_metrics = APIMetrics()
_cost_budget = CostBudget(max_cost_per_sweep_usd=1.00, max_cost_per_day_usd=10.00)
_value_model_config = load_value_model_config()
_FLEETOPS_PLAYBOOK_SLUG = "fleetops"
_fleetops_playbooks = load_playbooks(_FLEETOPS_PLAYBOOK_SLUG)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    error: str
    code: str
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    db_connected: bool
    config_loaded: bool
    tenant_id: str
    accounts_loaded: int
    auth: str


class ValueFactorSchema(BaseModel):
    name: str
    value: float
    contribution: int
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    config_version: str
    rule_name: str
    threshold_name: str | None = None
    threshold_value: float | int | None = None


class PrioritySchema(BaseModel):
    score: int
    factors: list[ValueFactorSchema] = Field(default_factory=list)


class AccountSummarySchema(BaseModel):
    account_id: str
    account_name: str
    industry: str | None = None
    health_band: str | None = None
    health_score: float | None = None
    lifecycle_stage: str | None = None
    arr_cents: int | None = None
    priority_score: int | None = None
    priority_score_error: str | None = None
    tier: str | None = None


class AccountListResponse(BaseModel):
    tenant_id: str
    account_count: int
    accounts: list[AccountSummarySchema]


class AccountDetailResponse(BaseModel):
    account_id: str
    account_name: str
    lifecycle_stage: str
    resolved_thresholds: dict[str, Any]
    usage: dict[str, Any]
    penetration: dict[str, Any]
    feature_depth: dict[str, Any]
    outcome: dict[str, Any]
    divergences: list[dict[str, Any]]
    priority: dict[str, Any]


class AccountBriefResponse(BaseModel):
    account_id: str
    account_name: str
    industry: str | None = None
    company: dict[str, Any]
    health_snapshot: dict[str, Any]
    adoption: dict[str, Any] | None = None
    priority: dict[str, Any]
    lifecycle_stage: str
    trajectory: dict[str, Any] | None = None
    divergences: list[dict[str, Any]]
    open_ctas: list[dict[str, Any]]
    success_plans: list[dict[str, Any]]
    open_cases: list[dict[str, Any]]
    contacts: list[dict[str, Any]]
    stakeholders: list[dict[str, Any]]
    opportunities: list[dict[str, Any]]
    entitlements: list[dict[str, Any]]
    recent_usage_signals: list[dict[str, Any]]
    milestones: list[dict[str, Any]]
    suggested_talking_points: list[str]


class SweepResponse(BaseModel):
    tenant_id: str
    work_items: list[dict[str, Any]]
    escalations: list[dict[str, Any]]
    swept_accounts: list[str]
    degraded_items: int = 0
    auth: str | None = None


class ProposalSchema(BaseModel):
    proposal_id: str
    intent: str
    action: str
    payload: dict[str, Any]
    autonomy_tier: int
    required_permission: str
    status: str


class ProposalListResponse(BaseModel):
    tenant_id: str
    pending_count: int
    proposals: list[ProposalSchema]


class VerdictRequest(BaseModel):
    verdict: Literal["approve", "deny", "revise"]
    reason: str
    edit_instruction: str | None = Field(default=None, max_length=280)


class VerdictResponse(BaseModel):
    proposal_id: str
    status: str
    authorized: bool
    verdict: str
    payload_sha256: str
    superseding_proposal_id: str | None = None
    auth: str | None = None


class DigestAccountSchema(BaseModel):
    account_id: str
    account_name: str
    health_band: str | None = None
    priority_score: int | None = None
    priority_score_error: str | None = None
    disposition: str | None = None
    reason: str | None = None


class DigestResponse(BaseModel):
    tenant_id: str
    as_of: str
    prioritized_accounts: list[DigestAccountSchema]
    pending_proposals: int
    commitments: list[dict[str, Any]]
    manager_rollup: dict[str, Any]


class LedgerEventSchema(BaseModel):
    ts: str
    event: str
    label: str
    proposal_id: str
    detail: str


class LedgerResponse(BaseModel):
    tenant_id: str
    events: list[LedgerEventSchema]
    ledger_gap: list[str]


class DelegationResponse(BaseModel):
    tenant_id: str
    pending_count: int
    groups: dict[str, Any]
    held_actions: list[dict[str, Any]] = Field(default_factory=list)


class TrajectoryPointSchema(BaseModel):
    day: int
    health_band: str
    health_score: float
    priority_score: int
    priority_factors: list[str] = Field(default_factory=list)


class TrajectoryResponse(BaseModel):
    account_id: str
    window_days: int
    points: list[TrajectoryPointSchema]
    trend: str
    trend_velocity: float
    consecutive_band: str | None = None
    consecutive_count: int = 0


# ---------------------------------------------------------------------------
# Lifespan (boot/teardown)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Boot ephemeral Postgres, seed, and configure on startup; tear down on
    shutdown."""
    global _cluster, _conn, _data_plane, _orch_principal

    setup_logging("INFO")
    log.info("Booting ephemeral Postgres cluster for API")
    if demo_noauth_enabled():
        log.warning(
            "ULTRA_CSM_DEMO_NOAUTH=1 enabled; mutating API routes allow "
            "tokenless local demo access",
            extra={"auth": "demo-noauth"},
        )

    _cluster = EphemeralCluster().start()

    # Migrate and seed via bootstrap connection.
    with psycopg.connect(**_cluster.dsn(user=_cluster.BOOTSTRAP_USER)) as boot:
        apply_migrations(boot, _MIGRATIONS)
        seed(boot)

    # Runtime connection for the lifetime of the server.
    _conn = psycopg.connect(**_cluster.dsn(user="app_runtime"))

    # Seed governance roster.
    seed_roster(_conn, tenant_id=_TENANT_ID, actor_id=_SEED_AGENT, now=_CLOCK)

    _orch_principal = make_principal(
        _conn,
        tenant_id=_TENANT_ID,
        actor_id=_SEED_AGENT,
        display_name="cs-orchestrator",
        role=ROLE_CS_ORCHESTRATOR,
        now=_CLOCK,
    )

    # Build the fixture data plane.
    _data_plane = build_sweep_fixture_data_plane()

    log.info(
        "Ultra CSM API ready",
        extra={
            "tenant_id": _TENANT_ID,
            "orch_principal": _orch_principal,
            "auth": auth_marker(),
            "configured_api_tokens": len(parse_api_tokens()),
        },
    )

    yield  # ← server runs here

    # Teardown
    if _conn is not None:
        _conn.close()
    if _cluster is not None:
        _cluster.stop()
    log.info("Ultra CSM API shutdown complete")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Ultra CSM API",
    description=(
        "Customer Success Management API — account scoring, book sweeps, "
        "governance proposals, and daily digest."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# Ops surface (ui/) runs `next dev` on :3000 against this API on :8000 in
# dev mode; the built static export is served same-origin via StaticFiles
# in demo/prod, where this middleware is a no-op.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# Demo/prod: `make ui-build` writes ui/out (Next static export); mount it at
# /ui same-origin, one process for the demo (Decisions). Absent until built
# — mounting is skipped, not an error, so `make serve` alone still works.
_UI_OUT_DIR = Path(__file__).resolve().parents[2] / "ui" / "out"
if _UI_OUT_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=_UI_OUT_DIR, html=True), name="ui")


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def request_logging(request: Request, call_next):
    start = time.monotonic()
    response: Response = await call_next(request)
    elapsed_ms = (time.monotonic() - start) * 1000

    # Record in API metrics tracker.
    _api_metrics.record_request(request.url.path, elapsed_ms)

    # Extract account_id from path if present.
    account_id = request.path_params.get("account_id")
    extra: dict[str, Any] = {
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "response_time_ms": round(elapsed_ms, 2),
    }
    if account_id:
        extra["account_id"] = account_id

    log.info(
        "request",
        extra=extra,
    )
    return response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _gate() -> ActionGate:
    assert _conn is not None and _orch_principal is not None
    return ActionGate(
        _conn,
        tenant_id=_TENANT_ID,
        actor_principal_id=_orch_principal,
        verdict_source=FixtureVerdictSource(),
        now=_CLOCK,
    )


def _account_data_http_error(exc: AccountDataError) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "error": str(exc),
            "code": exc.code,
            "account_id": exc.account_id,
        },
    )


def _require_write_auth(request: Request):
    assert _conn is not None and _orch_principal is not None
    try:
        return resolve_write_principal(
            _conn,
            tenant_id=_TENANT_ID,
            actor_id=_orch_principal,
            now=_CLOCK,
            authorization=request.headers.get("Authorization"),
        )
    except AuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": str(exc), "code": exc.code},
        )


def _require_account(account_id: str, dp: CustomerDataPlane | None = None):
    """Look up an account; raise 404 if not found."""
    plane = dp or _data_plane
    assert plane is not None
    account = plane.crm.get_account(account_id)
    if account is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Account not found", "code": "ACCOUNT_NOT_FOUND",
                    "account_id": account_id},
        )
    return account


def _data_plane_for_day(
    day: int | None,
    *,
    deep: bool = False,
) -> tuple[CustomerDataPlane, str]:
    """Return a data plane and as_of date for a given simulation day.

    When *day* is ``None``, the default (static) data plane is returned.
    When *day* >= 0, the 35-account synthetic book is used, optionally
    evolved to the requested day.

    When *deep* is ``True`` and *day* > 0, the deep data simulation layer
    overlays per-user activity, feature adoption, and case lifecycle data
    onto the book-simulator snapshot.  The value model then scores from
    granular data rather than pre-computed health scores.
    """
    if day is None:
        assert _data_plane is not None
        return _data_plane, _AS_OF

    from ultra_csm.data_plane.book_simulator import simulate_book
    from ultra_csm.data_plane.fixtures import (
        FixtureCRMDataConnector,
        FixtureCSPlatformConnector,
        FixtureProductTelemetryConnector,
    )
    from ultra_csm.data_plane.synthetic_book import (
        SEED_DATE,
        build_synthetic_book,
    )

    base = build_synthetic_book()
    data = simulate_book(base, day_offset=day) if day > 0 else base

    # Overlay deep data simulation when requested
    if deep and day > 0:
        from ultra_csm.cli import _apply_deep_data_overlay
        data = _apply_deep_data_overlay(data, day)

    base_date = datetime.strptime(SEED_DATE, "%Y-%m-%d")
    as_of = (base_date + timedelta(days=day)).strftime("%Y-%m-%d")
    dp = CustomerDataPlane(
        crm=FixtureCRMDataConnector(data=data),
        cs=FixtureCSPlatformConnector(data=data),
        telemetry=FixtureProductTelemetryConnector(data=data),
    )
    return dp, as_of


def _precedence_data_plane_for_proposal(
    proposal: ActionProposal,
) -> tuple[CustomerDataPlane, str]:
    """Return the data plane + as_of a precedence re-check should use for
    *proposal*, scoped to the day it actually originated from rather than
    the static default.

    Real proposals from a day-scoped sweep (``POST /sweep?day=N``) already
    carry ``payload["as_of"]`` (set by agent1/lens_expansion.py's
    _propose_expansion_call at emit time) -- this derives the simulation day
    back out of that recorded date and re-fetches that day's synthetic-book
    data plane via the same ``_data_plane_for_day`` used at sweep time, so
    the re-check sees the same book the proposal was raised against. Falls
    back to the static default plane (today's behaviour) when the proposal
    carries no parseable ``as_of`` -- not every proposal type carries one.
    """

    as_of = proposal.payload.get("as_of")
    if not isinstance(as_of, str):
        return _data_plane_for_day(None)

    from ultra_csm.data_plane.synthetic_book import SEED_DATE

    try:
        seed_date = datetime.strptime(SEED_DATE, "%Y-%m-%d")
        proposal_date = datetime.strptime(as_of, "%Y-%m-%d")
    except ValueError:
        return _data_plane_for_day(None)

    day = (proposal_date - seed_date).days
    if day < 0:
        return _data_plane_for_day(None)
    return _data_plane_for_day(day)


def _fixture_data_for_day(day: int | None, *, deep: bool = False):
    """Return fixture data aligned with ``_data_plane_for_day`` for reporting."""

    if day is None:
        from ultra_csm.data_plane.fixtures import default_fixture_data

        return default_fixture_data()

    from ultra_csm.data_plane.book_simulator import simulate_book
    from ultra_csm.data_plane.synthetic_book import build_synthetic_book

    base = build_synthetic_book()
    data = simulate_book(base, day_offset=day) if day > 0 else base
    if deep and day > 0:
        from ultra_csm.cli import _apply_deep_data_overlay

        data = _apply_deep_data_overlay(data, day)
    return data


def _current_precedence_state(as_of: str = _AS_OF):
    assert _data_plane is not None
    config = load_precedence_config()
    findings = _current_precedence_findings(_data_plane, as_of=as_of)
    actions = _current_expansion_actions(_data_plane, as_of=as_of)
    return evaluate_precedence(findings, actions, config, as_of=as_of)


def _current_precedence_findings(
    data_plane: CustomerDataPlane,
    *,
    as_of: str,
) -> tuple[FindingPacket, ...]:
    findings: list[FindingPacket] = []
    for account in data_plane.crm.list_accounts(tenant_id=DEFAULT_TENANT):
        company = data_plane.cs.get_company(account.account_id)
        health = data_plane.cs.get_health_score(account.account_id)
        ctas = tuple(data_plane.cs.list_ctas(account.account_id, status="open"))
        milestones = tuple(data_plane.telemetry.list_ttv_milestones(account.account_id))
        open_milestones = tuple(
            milestone for milestone in milestones
            if milestone.achieved_at is None and milestone.expected_by < as_of
        )
        if (
            company is not None
            and company.lifecycle_stage in {"onboarding", "adopting"}
            and (
                open_milestones
                or ctas
                or (health is not None and health.band in {"yellow", "red"})
            )
        ):
            findings.append(FindingPacket(
                finding_id=f"ttv_gap:{account.account_id}",
                account_id=account.account_id,
                lens="ttv_gap",
                condition_instance=f"ttv_gap:{account.account_id}:{as_of}",
                evidence_refs=tuple(
                    [
                        *(
                            f"milestone:{account.account_id}:{milestone.milestone}"
                            for milestone in open_milestones
                        ),
                        *(f"cta:{cta.cta_id}" for cta in ctas),
                    ]
                ),
                payload={
                    "account_name": account.name,
                    "reason": "active onboarding or adoption gap",
                },
            ))
        if health is not None and health.band == "red":
            findings.append(FindingPacket(
                finding_id=f"risk:{account.account_id}",
                account_id=account.account_id,
                lens="risk",
                condition_instance=f"risk:{account.account_id}:{health.measured_at}",
                evidence_refs=(f"health:{account.account_id}",),
                payload={
                    "account_name": account.name,
                    "reason": "red health",
                },
            ))
    return tuple(findings)


def _current_expansion_actions(
    data_plane: CustomerDataPlane,
    *,
    as_of: str,
) -> tuple[ActionPacket, ...]:
    actions: list[ActionPacket] = []
    for account in data_plane.crm.list_accounts(tenant_id=DEFAULT_TENANT):
        opportunities = tuple(
            opp for opp in data_plane.crm.list_opportunities(account.account_id)
            if opp.opportunity_type.lower() == "expansion"
        )
        for opportunity in opportunities:
            payload = {
                "account_id": account.account_id,
                "account_name": account.name,
                "opportunity_id": opportunity.opportunity_id,
                "opportunity_stage": opportunity.stage_name,
                "action": "initiate_customer_call",
                "as_of": as_of,
            }
            actions.append(ActionPacket(
                action_id=f"expansion:{account.account_id}:{opportunity.opportunity_id}",
                account_id=account.account_id,
                lens="expansion",
                scope="customer_facing",
                action_type="initiate_customer_call",
                autonomy_tier=3,
                payload=payload,
            ))
    return tuple(actions)


def _action_packet_for_proposal(proposal: ActionProposal) -> ActionPacket | None:
    if proposal.action != "initiate_customer_call":
        return None
    account_id = str(proposal.payload.get("account_id") or "")
    if not account_id:
        return None
    return ActionPacket(
        action_id=f"proposal:{proposal.proposal_id}",
        account_id=account_id,
        lens="expansion",
        scope="customer_facing",
        action_type=proposal.action,
        autonomy_tier=proposal.autonomy_tier,
        payload=proposal.payload,
        payload_sha256=proposal.payload_sha256,
    )


def _lookup_proposal(proposal_id: str) -> ActionProposal:
    """Fetch a proposal from the DB by ID. Raises 404 if not found."""
    assert _conn is not None

    with session(
        _conn,
        tenant_id=_TENANT_ID,
        actor_id=_orch_principal or _SEED_AGENT,
        now=_CLOCK,
    ) as cur:
        cur.execute(
            "SELECT proposal_id, intent, action, payload, payload_sha256, "
            "       autonomy_tier, required_permission, status "
            "FROM action_proposal WHERE proposal_id = %s",
            (proposal_id,),
        )
        row = cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Proposal not found", "code": "PROPOSAL_NOT_FOUND",
                    "proposal_id": proposal_id},
        )

    payload_raw = row[3]
    payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw

    return ActionProposal(
        proposal_id=str(row[0]),
        intent=row[1],
        action=row[2],
        payload=payload if isinstance(payload, dict) else {},
        payload_sha256=row[4],
        autonomy_tier=row[5],
        required_permission=row[6],
        status=row[7],
    )


def _bounded_revise_response(
    proposal: ActionProposal,
    body: VerdictRequest,
    *,
    auth_principal,
) -> VerdictResponse:
    assert _data_plane is not None
    try:
        result = apply_bounded_revise(
            _gate(),
            proposal,
            data_plane=_data_plane,
            tenant_id=DEFAULT_TENANT,
            human_principal_id=auth_principal.principal_id,
            reason=body.reason,
            edit_instruction=body.edit_instruction,
            cause_ref=f"api:revise:{proposal.proposal_id}",
        )
    except ReviseServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_dict()) from exc
    log.info(
        "Draft revise recorded",
        extra={
            "proposal_id": proposal.proposal_id,
            "superseding_proposal_id": result.superseding_proposal_id,
            "actor": auth_principal.principal_id,
            "auth": auth_principal.auth,
        },
    )
    return VerdictResponse(
        **result.to_dict(),
        auth=auth_principal.auth,
    )


def _decode_payload(payload_raw: Any) -> dict[str, Any]:
    payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
    return payload if isinstance(payload, dict) else {}


def _pending_proposal_packets() -> list[dict[str, Any]]:
    assert _conn is not None
    with session(
        _conn,
        tenant_id=_TENANT_ID,
        actor_id=_orch_principal or _SEED_AGENT,
        now=_CLOCK,
    ) as cur:
        cur.execute(
            "SELECT proposal_id, intent, action, payload, payload_sha256, "
            "       autonomy_tier, required_permission, status, created_ts "
            "FROM action_proposal "
            "WHERE status = 'pending' "
            "ORDER BY autonomy_tier ASC, created_ts ASC, proposal_id ASC"
        )
        rows = cur.fetchall()

    packets = []
    for row in rows:
        packets.append({
            "proposal_id": str(row[0]),
            "intent": row[1],
            "action": row[2],
            "payload": _decode_payload(row[3]),
            "payload_sha256": row[4],
            "autonomy_tier": row[5],
            "required_permission": row[6],
            "status": row[7],
            "created_at": row[8].isoformat() if row[8] else None,
        })
    return packets


def _delegation_groups() -> dict[str, Any]:
    groups: dict[str, Any] = {
        "tier_1_auto_executed_audit_trail": {
            "tier": 1,
            "label": "auto-executed tier-1 audit trail",
            "batch_approvable": False,
            "proposals": [],
        },
        "tier_2_batch_approvable": {
            "tier": 2,
            "label": "batch-approvable tier-2",
            "batch_approvable": True,
            "proposals": [],
        },
        "tier_3_escalation": {
            "tier": 3,
            "label": "escalation tier-3",
            "batch_approvable": False,
            "proposals": [],
        },
    }
    tier_keys = {
        1: "tier_1_auto_executed_audit_trail",
        2: "tier_2_batch_approvable",
        3: "tier_3_escalation",
    }
    for proposal in _pending_proposal_packets():
        key = tier_keys.get(proposal["autonomy_tier"], "tier_3_escalation")
        groups[key]["proposals"].append(proposal)
    for group in groups.values():
        group["pending_count"] = len(group["proposals"])
        group["mutation_path"] = "individual_verdict_required"
    return groups


def _action_throughput() -> dict[str, Any]:
    assert _conn is not None
    with session(
        _conn,
        tenant_id=_TENANT_ID,
        actor_id=_orch_principal or _SEED_AGENT,
        now=_CLOCK,
    ) as cur:
        cur.execute(
            "SELECT status, count(*) FROM action_proposal GROUP BY status "
            "ORDER BY status ASC"
        )
        proposal_counts = {row[0]: row[1] for row in cur.fetchall()}
        cur.execute(
            "SELECT verdict, count(*) FROM action_verdict GROUP BY verdict "
            "ORDER BY verdict ASC"
        )
        verdict_counts = {row[0]: row[1] for row in cur.fetchall()}
    return {
        "proposals_by_status": proposal_counts,
        "verdicts_by_type": verdict_counts,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """System health check — DB up, config loaded."""
    db_ok = False
    account_count = 0
    if _conn is not None and _data_plane is not None:
        try:
            with session(
                _conn,
                tenant_id=_TENANT_ID,
                actor_id=_orch_principal or _SEED_AGENT,
                now=_CLOCK,
            ) as cur:
                cur.execute("SELECT 1")
            db_ok = True
            account_count = len(
                _data_plane.crm.list_accounts(tenant_id=DEFAULT_TENANT)
            )
        except Exception:
            db_ok = False

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        db_connected=db_ok,
        config_loaded=_data_plane is not None,
        tenant_id=_TENANT_ID,
        accounts_loaded=account_count,
        auth=auth_marker(),
    )


@app.get("/accounts", response_model=AccountListResponse)
async def list_accounts(
    day: int | None = Query(None, ge=0, le=365),
    deep: bool = Query(False, description="Use deep data simulation layer"),
):
    """List all accounts with current value model scores.

    Pass ``?day=N`` to view the synthetic book at simulation day *N*.
    Add ``&deep=true`` to use the deep data simulation overlay.
    """
    dp, as_of = _data_plane_for_day(day, deep=deep)
    accounts = dp.crm.list_accounts(tenant_id=DEFAULT_TENANT)
    results: list[dict[str, Any]] = []

    for account in accounts:
        company = dp.cs.get_company(account.account_id)
        health = dp.cs.get_health_score(account.account_id)
        adoption = dp.cs.get_adoption_summary(account.account_id)

        entry: dict[str, Any] = {
            "account_id": account.account_id,
            "account_name": account.name,
            "industry": account.industry,
        }

        if company:
            entry["arr_cents"] = company.arr_cents
            entry["lifecycle_stage"] = company.lifecycle_stage
            try:
                resolved = resolve_tenant_tier(
                    account_attributes(account, company), _value_model_config
                )
                entry["tier"] = resolved.tier
            except Exception as exc:
                log.warning(
                    "tier_resolution_failed",
                    extra={
                        "surface": "api.list_accounts",
                        "account_id": account.account_id,
                        "error_type": exc.__class__.__name__,
                    },
                )

        if health:
            entry["health_band"] = health.band
            entry["health_score"] = health.score

        # Compute priority if we have enough data.
        if company and health and adoption:
            try:
                priority_score, _divergences = score_account_priority(
                    account.account_id,
                    data_plane=dp,
                    as_of=as_of,
                )
                entry["priority_score"] = priority_score
            except Exception as exc:
                log.warning(
                    "priority_score_failed",
                    extra={
                        "surface": "api.list_accounts",
                        "account_id": account.account_id,
                        "error_type": exc.__class__.__name__,
                    },
                )
                entry["priority_score"] = None
                entry["priority_score_error"] = exc.__class__.__name__

        results.append(entry)

    # Sort by priority score descending.
    results.sort(
        key=lambda r: r["priority_score"] if r.get("priority_score") is not None else -1,
        reverse=True,
    )

    return AccountListResponse(
        tenant_id=DEFAULT_TENANT,
        account_count=len(results),
        accounts=[AccountSummarySchema(**r) for r in results],
    )


@app.get("/accounts/{account_id}")
async def get_account_detail(
    account_id: str,
    day: int | None = Query(None, ge=0, le=365),
    deep: bool = Query(False, description="Use deep data simulation layer"),
):
    """Single account detail: value model output, active factors, divergence
    signals, lens projections."""
    dp, as_of = _data_plane_for_day(day, deep=deep)
    try:
        return _score_one_account(account_id, data_plane=dp, as_of=as_of)
    except AccountDataError as exc:
        raise _account_data_http_error(exc)


@app.get("/accounts/{account_id}/brief")
async def get_account_brief(
    account_id: str,
    day: int | None = Query(None, ge=0, le=365),
    deep: bool = Query(False, description="Use deep data simulation layer"),
):
    """Account brief — the key demo endpoint.

    Health snapshot, recent changes, risks, expansion signals, and suggested
    talking points.  Includes trajectory when simulation day is provided.
    """
    dp, as_of = _data_plane_for_day(day, deep=deep)
    try:
        brief = _build_account_brief(account_id, data_plane=dp, as_of=as_of)
    except AccountDataError as exc:
        raise _account_data_http_error(exc)

    # Inject trajectory data when a simulation day is specified.
    if day is not None:
        from ultra_csm.data_plane.book_simulator import simulate_book
        from ultra_csm.data_plane.synthetic_book import SEED_DATE, build_synthetic_book
        from ultra_csm.snapshot_store import SnapshotStore

        base_date = datetime.strptime(SEED_DATE, "%Y-%m-%d")
        timeline_days = [d for d in [0, 30, 60, 90, 120, 180, 270, 365] if d <= day]
        base_book = build_synthetic_book()
        snap_store = SnapshotStore()

        for td in timeline_days:
            td_as_of = (base_date + timedelta(days=td)).strftime("%Y-%m-%d")
            if deep:
                from ultra_csm.data_plane.data_simulator import simulate_data
                from ultra_csm.value_model_bridge import build_deep_value_model

                bundle = simulate_data(base_book, day=td)
                if account_id not in bundle.accounts:
                    continue
                companies_by_id = {c.company_id: c for c in base_book.companies}
                adoption_by_id = {a.account_id: a for a in base_book.adoption_summaries}
                ents = [e for e in base_book.entitlements if e.account_id == account_id]
                plans = [p for p in base_book.success_plans if p.account_id == account_id]
                company = companies_by_id.get(account_id)
                if company is None:
                    continue
                adoption = adoption_by_id.get(account_id)
                lu = adoption.licensed_users if adoption else 0
                model, health = build_deep_value_model(
                    bundle=bundle, account_id=account_id,
                    account=next(a for a in base_book.accounts if a.account_id == account_id),
                    company=company, entitlements=tuple(ents),
                    success_plans=tuple(plans), licensed_users=lu,
                )
                priority = project_ttv_lens(
                    model, company=company, health=health,
                    open_milestone_gaps=(), overdue_success_plans=(), as_of=td_as_of,
                )
            else:
                td_data = base_book if td == 0 else simulate_book(base_book, day_offset=td)
                from ultra_csm.data_plane.fixtures import (
                    FixtureCRMDataConnector, FixtureCSPlatformConnector,
                    FixtureProductTelemetryConnector,
                )
                crm = FixtureCRMDataConnector(data=td_data)
                cs = FixtureCSPlatformConnector(data=td_data)
                acct = crm.get_account(account_id)
                if acct is None:
                    continue
                company = cs.get_company(account_id)
                health = cs.get_health_score(account_id)
                if company is None or health is None:
                    continue
                adoption = cs.get_adoption_summary(account_id)
                telemetry = FixtureProductTelemetryConnector(data=td_data)
                model = build_customer_value_model(
                    account=acct, company=company, health=health,
                    adoption=adoption, entitlements=tuple(telemetry.list_entitlements(account_id)),
                    usage_signals=tuple(telemetry.list_usage_signals(account_id)),
                    success_plans=tuple(cs.list_success_plans(account_id)),
                )
                priority = project_ttv_lens(
                    model, company=company, health=health,
                    open_milestone_gaps=(), overdue_success_plans=(), as_of=td_as_of,
                )

            snap_store.store_snapshot(td, account_id, {
                "health_band": health.band,
                "health_score": health.score,
                "priority_score": priority.score,
                "priority_factors": [f.name for f in priority.factors],
                "lifecycle_stage": company.lifecycle_stage,
                "arr_cents": company.arr_cents,
            })

        traj = snap_store.build_trajectory(account_id, window_days=365)
        brief["trajectory"] = {
            "trend": traj.trend,
            "trend_velocity": traj.trend_velocity,
            "consecutive_band": traj.consecutive_band,
            "consecutive_count": traj.consecutive_count,
            "points": [
                {
                    "day": p.day,
                    "health_band": p.health_band,
                    "health_score": p.health_score,
                    "priority_score": p.priority_score,
                }
                for p in traj.points
            ],
        }

    return brief


@app.get("/accounts/{account_id}/trajectory", response_model=TrajectoryResponse)
async def get_account_trajectory(
    account_id: str,
    window: int = Query(30, ge=1, le=365, description="Trajectory window in days"),
    deep: bool = Query(False, description="Use deep data simulation layer"),
):
    """Account health trajectory over a time window (VM-7).

    Scores the account at each timeline checkpoint (0, 30, 60, …, 365),
    stores snapshots, and returns the trajectory: trend direction, velocity,
    and the full series of data points within the requested window.
    """
    from ultra_csm.data_plane.book_simulator import simulate_book
    from ultra_csm.data_plane.synthetic_book import SEED_DATE, build_synthetic_book
    from ultra_csm.snapshot_store import SnapshotStore

    _require_account(account_id)

    base_date = datetime.strptime(SEED_DATE, "%Y-%m-%d")
    timeline_days = [0, 30, 60, 90, 120, 180, 270, 365]
    base_book = build_synthetic_book()
    snap_store = SnapshotStore()

    for day in timeline_days:
        as_of = (base_date + timedelta(days=day)).strftime("%Y-%m-%d")
        if deep:
            from ultra_csm.data_plane.data_simulator import simulate_data
            from ultra_csm.value_model_bridge import build_deep_value_model

            bundle = simulate_data(base_book, day=day)
            if account_id not in bundle.accounts:
                continue

            companies_by_id = {c.company_id: c for c in base_book.companies}
            adoption_by_id = {a.account_id: a for a in base_book.adoption_summaries}
            entitlements_by_acct: dict[str, list] = {}
            for e in base_book.entitlements:
                entitlements_by_acct.setdefault(e.account_id, []).append(e)
            plans_by_acct: dict[str, list] = {}
            for p in base_book.success_plans:
                plans_by_acct.setdefault(p.account_id, []).append(p)

            company = companies_by_id.get(account_id)
            if company is None:
                continue
            adoption = adoption_by_id.get(account_id)
            licensed_users = adoption.licensed_users if adoption else 0

            model, health = build_deep_value_model(
                bundle=bundle,
                account_id=account_id,
                account=next(a for a in base_book.accounts if a.account_id == account_id),
                company=company,
                entitlements=tuple(entitlements_by_acct.get(account_id, [])),
                success_plans=tuple(plans_by_acct.get(account_id, [])),
                licensed_users=licensed_users,
            )
            milestones = [m for m in base_book.milestones if m.account_id == account_id]
            open_milestones = tuple(m for m in milestones if m.achieved_at is None and m.expected_by < as_of)
            overdue_plans = tuple(
                p for p in plans_by_acct.get(account_id, [])
                if p.status in ("active",) and p.target_date < as_of
            )
            priority = project_ttv_lens(
                model, company=company, health=health,
                open_milestone_gaps=open_milestones,
                overdue_success_plans=overdue_plans, as_of=as_of,
            )
            snap_store.store_snapshot(day, account_id, {
                "health_band": health.band,
                "health_score": health.score,
                "priority_score": priority.score,
                "priority_factors": [f.name for f in priority.factors],
                "lifecycle_stage": company.lifecycle_stage,
                "arr_cents": company.arr_cents,
            })
        else:
            if day == 0:
                data = base_book
            else:
                data = simulate_book(base_book, day_offset=day)

            from ultra_csm.data_plane.fixtures import (
                FixtureCRMDataConnector,
                FixtureCSPlatformConnector,
                FixtureProductTelemetryConnector,
            )
            crm = FixtureCRMDataConnector(data=data)
            cs = FixtureCSPlatformConnector(data=data)
            telemetry = FixtureProductTelemetryConnector(data=data)

            account = crm.get_account(account_id)
            if account is None:
                continue
            company = cs.get_company(account_id)
            health = cs.get_health_score(account_id)
            if company is None or health is None:
                continue
            adoption = cs.get_adoption_summary(account_id)
            entitlements = tuple(telemetry.list_entitlements(account_id))
            signals = tuple(telemetry.list_usage_signals(account_id))
            plans = tuple(cs.list_success_plans(account_id))
            milestones = tuple(telemetry.list_ttv_milestones(account_id))

            model = build_customer_value_model(
                account=account, company=company, health=health,
                adoption=adoption, entitlements=entitlements,
                usage_signals=signals, success_plans=plans,
            )
            open_milestones = tuple(m for m in milestones if m.achieved_at is None and m.expected_by < as_of)
            overdue_plans = tuple(p for p in plans if p.status in ("active",) and p.target_date < as_of)
            priority = project_ttv_lens(
                model, company=company, health=health,
                open_milestone_gaps=open_milestones,
                overdue_success_plans=overdue_plans, as_of=as_of,
            )
            snap_store.store_snapshot(day, account_id, {
                "health_band": health.band,
                "health_score": health.score,
                "priority_score": priority.score,
                "priority_factors": [f.name for f in priority.factors],
                "lifecycle_stage": company.lifecycle_stage,
                "arr_cents": company.arr_cents,
            })

    traj = snap_store.build_trajectory(account_id, window_days=window)
    return TrajectoryResponse(
        account_id=traj.account_id,
        window_days=traj.window_days,
        points=[
            TrajectoryPointSchema(
                day=p.day,
                health_band=p.health_band,
                health_score=p.health_score,
                priority_score=p.priority_score,
                priority_factors=list(p.priority_factors),
            )
            for p in traj.points
        ],
        trend=traj.trend,
        trend_velocity=traj.trend_velocity,
        consecutive_band=traj.consecutive_band,
        consecutive_count=traj.consecutive_count,
    )


@app.post("/sweep", response_model=SweepResponse)
async def trigger_sweep(
    request: Request,
    day: int | None = Query(None, ge=0, le=365),
    deep: bool = Query(False, description="Use deep data simulation layer"),
):
    """Trigger a sweep of the book, return the SweepResult.

    Pass ``?day=N`` to sweep the synthetic book at simulation day *N*.
    Add ``&deep=true`` to use the deep data simulation overlay.
    """
    dp, as_of = _data_plane_for_day(day, deep=deep)
    assert _orch_principal is not None
    auth_principal = _require_write_auth(request)

    log.info(
        "Sweep triggered",
        extra={
            "tenant_id": _TENANT_ID,
            "day": day,
            "auth": auth_principal.auth,
            "operator_principal": auth_principal.principal_id,
        },
    )

    sweep_start = time.monotonic()
    gate = _gate()
    sweep = run_time_to_value_sweep(
        dp,
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=_orch_principal,
        as_of=as_of,
        cost_tracker=_cost_tracker,
        cost_budget=_cost_budget,
        # DEFAULT_TENANT ("ultra-demo") is fleetops-only by construction
        # (verified report 23/24) — this opts the API's sweep into the same
        # live motion resolution tick.py already uses; work_items carry a
        # real `motion` value instead of staying None.
        playbook_tenant_slug=_FLEETOPS_PLAYBOOK_SLUG,
    )
    # Cohort collapse needs the whole book, not the per-trigger restricted
    # sweep data plane — same pattern as tick.py's own collapse_cohorts call.
    sweep = collapse_cohorts(
        sweep,
        dp,
        tenant_id=DEFAULT_TENANT,
        playbooks=_fleetops_playbooks,
        value_model_config=_value_model_config,
        as_of=as_of,
    )
    sweep_elapsed_ms = (time.monotonic() - sweep_start) * 1000.0

    # Record sweep timing in API metrics.
    _api_metrics.record_sweep(SweepTiming(
        total_ms=sweep_elapsed_ms,
        accounts_swept=len(sweep.swept_accounts),
        budget_skipped=sweep.budget_skipped,
    ))

    log.info(
        "Sweep complete",
        extra={
            "tenant_id": _TENANT_ID,
            "accounts_evaluated": len(sweep.swept_accounts),
            "work_items": len(sweep.work_items),
            "escalations": len(sweep.escalations),
            "proposals_generated": sum(
                1 for item in sweep.work_items if item.proposal is not None
            ),
            "budget_skipped": sweep.budget_skipped,
        },
    )

    result = sweep.to_dict()
    _enrich_person_evidence(list(result.get("work_items", ())), data_plane=dp)
    # Ensure the top-level keys match the SweepResponse model.
    return SweepResponse(
        tenant_id=result["tenant_id"],
        work_items=list(result.get("work_items", ())),
        escalations=list(result.get("escalations", ())),
        swept_accounts=list(result.get("swept_accounts", ())),
        degraded_items=result.get("degraded_items", 0),
        auth=auth_principal.auth,
    )


@app.get("/proposals", response_model=ProposalListResponse)
async def list_proposals():
    """List pending governance proposals."""
    assert _conn is not None

    with session(
        _conn,
        tenant_id=_TENANT_ID,
        actor_id=_orch_principal or _SEED_AGENT,
        now=_CLOCK,
    ) as cur:
        cur.execute(
            "SELECT proposal_id, intent, action, payload, payload_sha256, "
            "       autonomy_tier, required_permission, status "
            "FROM action_proposal "
            "WHERE status = 'pending' "
            "ORDER BY created_ts DESC"
        )
        rows = cur.fetchall()

    proposals = []
    for row in rows:
        payload_raw = row[3]
        payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw

        proposals.append(ProposalSchema(
            proposal_id=str(row[0]),
            intent=row[1],
            action=row[2],
            payload=payload if isinstance(payload, dict) else {},
            autonomy_tier=row[5],
            required_permission=row[6],
            status=row[7],
        ))

    return ProposalListResponse(
        tenant_id=_TENANT_ID,
        pending_count=len(proposals),
        proposals=proposals,
    )


# Two-register rule (UI_DESIGN_BRIEF.md): plain-English label for the primary
# UI text; the raw event name rides along in `event` for a mono/tooltip
# receipt. Mirrors ui-mockup.html's LEDGER_HUMAN table exactly.
_LEDGER_HUMAN = {
    "gate.propose": "Proposed",
    "gate.approve": "Approved",
    "gate.deny": "Denied",
    "gate.revise": "Edit saved",
}
# Event types the mockup's ledger shows (sweep.fired, value_model,
# slot_b.draft, judge.score, gmail.commit, reobserve.queue) are NOT
# persisted anywhere this endpoint can read from — action_proposal/
# action_verdict only carry the propose/approve/deny/revise lifecycle.
# Honest ledger gap (UI_DESIGN_BRIEF.md: "anything the surface cannot show
# live exposes a LEDGER GAP"), not something this endpoint papers over.
_LEDGER_GAP = [
    "sweep.fired", "value_model", "slot_b.draft", "judge.score",
    "gmail.commit", "reobserve.queue",
]


@app.get("/ledger", response_model=LedgerResponse)
async def get_ledger(limit: int = Query(50, ge=1, le=500)):
    """Append-only ledger tail: proposal + verdict lifecycle events, most
    recent first. Read-only view over `action_proposal`/`action_verdict` —
    computes nothing, mirrors DB state exactly."""
    assert _conn is not None

    with session(
        _conn,
        tenant_id=_TENANT_ID,
        actor_id=_orch_principal or _SEED_AGENT,
        now=_CLOCK,
    ) as cur:
        cur.execute(
            "SELECT proposal_id, 'gate.propose' AS event, created_ts AS ts, "
            "       intent, action, NULL::text AS verdict "
            "FROM action_proposal "
            "UNION ALL "
            "SELECT p.proposal_id, "
            "       CASE v.verdict WHEN 'approve' THEN 'gate.approve' "
            "                      WHEN 'deny' THEN 'gate.deny' "
            "                      ELSE 'gate.revise' END AS event, "
            "       v.decided_ts AS ts, p.intent, p.action, v.verdict "
            "FROM action_verdict v JOIN action_proposal p "
            "  ON p.proposal_id = v.proposal_id "
            "ORDER BY ts DESC LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()

    events = [
        LedgerEventSchema(
            ts=row[2].isoformat() if row[2] else "",
            event=row[1],
            label=_LEDGER_HUMAN.get(row[1], row[1]),
            proposal_id=str(row[0]),
            detail=f"{row[3]} · {row[4]}",
        )
        for row in rows
    ]
    return LedgerResponse(
        tenant_id=_TENANT_ID,
        events=events,
        ledger_gap=_LEDGER_GAP,
    )


@app.get("/queue/delegation", response_model=DelegationResponse)
async def get_delegation_queue():
    """Read-only tier grouping for pending delegated work."""
    groups = _delegation_groups()
    precedence = _current_precedence_state()
    return DelegationResponse(
        tenant_id=_TENANT_ID,
        pending_count=sum(group["pending_count"] for group in groups.values()),
        groups=groups,
        held_actions=[item.to_dict() for item in precedence.held_actions],
    )


@app.post("/proposals/{proposal_id}/verdict", response_model=VerdictResponse)
async def submit_verdict(proposal_id: str, body: VerdictRequest, request: Request):
    """Submit approve, deny, or bounded draft-revise verdict."""
    assert _conn is not None
    auth_principal = _require_write_auth(request)

    proposal = _lookup_proposal(proposal_id)

    if proposal.status != "pending":
        raise HTTPException(
            status_code=409,
            detail={
                "error": f"Proposal already '{proposal.status}'",
                "code": "ALREADY_VERDICTED",
                "proposal_id": proposal_id,
            },
        )

    if body.verdict == "revise":
        return _bounded_revise_response(
            proposal,
            body,
            auth_principal=auth_principal,
        )

    if body.verdict == "approve" and not _proposal_has_contact_consent(
        proposal, data_plane=_data_plane,
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Customer-facing outreach is blocked because contact consent is missing",
                "code": "CONSENT_MISSING",
                "proposal_id": proposal_id,
            },
        )

    action_packet = _action_packet_for_proposal(proposal)
    if body.verdict == "approve" and action_packet is not None:
        precedence_dp, precedence_as_of = _precedence_data_plane_for_proposal(proposal)
        blockers = _current_precedence_findings(precedence_dp, as_of=precedence_as_of)
        decision = approval_decision(
            action_packet,
            blockers,
            load_precedence_config(),
            as_of=precedence_as_of,
        )
        if not decision.allowed:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "Proposal is held by current precedence blockers",
                    "code": "PRECEDENCE_HELD",
                    "proposal_id": proposal_id,
                    "blocking_refs": list(decision.blocking_refs),
                },
            )

    gate = _gate()
    human_verdict = Verdict(
        verdict=body.verdict,
        human_principal_id=auth_principal.principal_id,
        rationale=body.reason,
    )

    try:
        outcome = gate.record_verdict(proposal, human_verdict)
    except GateError as exc:
        log.warning(
            "Verdict failed",
            extra={"proposal_id": proposal_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=409,
            detail={"error": str(exc), "code": "GATE_ERROR",
                    "proposal_id": proposal_id},
        )

    log.info(
        "Verdict recorded",
        extra={
            "proposal_id": outcome.proposal_id,
            "verdict": outcome.verdict,
            "status": outcome.status,
            "authorized": outcome.authorized,
            "actor": auth_principal.principal_id,
            "auth": auth_principal.auth,
        },
    )

    return VerdictResponse(
        proposal_id=outcome.proposal_id,
        status=outcome.status,
        authorized=outcome.authorized,
        verdict=outcome.verdict,
        payload_sha256=outcome.payload_sha256,
        auth=auth_principal.auth,
    )


@app.get("/digest", response_model=DigestResponse)
async def get_digest(
    day: int | None = Query(None, ge=0, le=365),
    deep: bool = Query(False, description="Use deep data simulation layer"),
):
    """Daily digest — prioritized accounts, proposals, commitments.

    Pass ``?day=N`` for the synthetic book at simulation day *N*.
    Add ``&deep=true`` to use the deep data simulation overlay.
    """
    dp, as_of = _data_plane_for_day(day, deep=deep)
    assert _conn is not None

    # 1. Prioritized accounts with a quick sweep.
    accounts = dp.crm.list_accounts(tenant_id=DEFAULT_TENANT)
    prioritized: list[DigestAccountSchema] = []
    health_counts = {"green": 0, "yellow": 0, "red": 0, "unknown": 0}
    divergence_counts: dict[str, int] = {}

    for account in accounts:
        company = dp.cs.get_company(account.account_id)
        health = dp.cs.get_health_score(account.account_id)
        adoption = dp.cs.get_adoption_summary(account.account_id)
        band = health.band if health else None
        if band in health_counts:
            health_counts[band] += 1
        else:
            health_counts["unknown"] += 1

        entry = DigestAccountSchema(
            account_id=account.account_id,
            account_name=account.name,
            health_band=band,
        )

        if company and health and adoption:
            try:
                priority_score, divergences = score_account_priority(
                    account.account_id,
                    data_plane=dp,
                    as_of=as_of,
                )
                entry = DigestAccountSchema(
                    account_id=account.account_id,
                    account_name=account.name,
                    health_band=health.band,
                    priority_score=priority_score,
                )
                for divergence in divergences:
                    name = str(divergence.get("name") or "unknown")
                    divergence_counts[name] = divergence_counts.get(name, 0) + 1
            except Exception as exc:
                log.warning(
                    "priority_score_failed",
                    extra={
                        "surface": "api.digest",
                        "account_id": account.account_id,
                        "error_type": exc.__class__.__name__,
                    },
                )
                entry = DigestAccountSchema(
                    account_id=account.account_id,
                    account_name=account.name,
                    health_band=health.band,
                    priority_score=None,
                    priority_score_error=exc.__class__.__name__,
                )

        prioritized.append(entry)

    # Sort by priority.
    prioritized.sort(
        key=lambda a: a.priority_score if a.priority_score is not None else -1,
        reverse=True,
    )

    # 2. Pending proposals count.
    pending_count = 0
    with session(
        _conn,
        tenant_id=_TENANT_ID,
        actor_id=_orch_principal or _SEED_AGENT,
        now=_CLOCK,
    ) as cur:
        cur.execute(
            "SELECT count(*) FROM action_proposal WHERE status = 'pending'"
        )
        row = cur.fetchone()
        pending_count = row[0] if row else 0

    # 3. Recent commitments (approved verdicts).
    commitments: list[dict[str, Any]] = []
    with session(
        _conn,
        tenant_id=_TENANT_ID,
        actor_id=_orch_principal or _SEED_AGENT,
        now=_CLOCK,
    ) as cur:
        cur.execute(
            "SELECT v.proposal_id, v.verdict, v.rationale, v.decided_ts, "
            "       p.intent, p.action "
            "FROM action_verdict v "
            "JOIN action_proposal p ON p.proposal_id = v.proposal_id "
            "WHERE v.verdict IN ('approve', 'revise') "
            "ORDER BY v.decided_ts DESC LIMIT 10"
        )
        for row in cur.fetchall():
            commitments.append({
                "proposal_id": str(row[0]),
                "verdict": row[1],
                "rationale": row[2],
                "decided_at": row[3].isoformat() if row[3] else None,
                "intent": row[4],
                "action": row[5],
            })

    return DigestResponse(
        tenant_id=_TENANT_ID,
        as_of=as_of,
        prioritized_accounts=prioritized,
        pending_proposals=pending_count,
        commitments=commitments,
        manager_rollup={
            "book_health_counts": health_counts,
            "divergence_patterns": [
                {"name": name, "account_count": count}
                for name, count in sorted(
                    divergence_counts.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ],
            "action_throughput": _action_throughput(),
            "cohort_packets": [
                packet.to_dict()
                for packet in build_cohort_rollup_packets(
                    _fixture_data_for_day(day, deep=deep),
                )
            ],
        },
    )


@app.get("/metrics")
async def get_metrics():
    """Operational metrics — API latency, Slot B cost, sweep timing, budget."""
    return {
        "api": _api_metrics.snapshot(),
        "sweeps": _api_metrics.sweep_snapshot(),
        "llm_cost": _cost_tracker.stats(),
        "cost_per_account": _cost_tracker.cost_per_account(),
        "budget": {
            **_cost_budget.to_dict(),
            "current_daily_cost_usd": round(_cost_tracker.today_cost_usd(), 6),
            "budget_remaining_today_usd": round(
                _cost_budget.max_cost_per_day_usd
                - _cost_tracker.today_cost_usd(),
                6,
            ),
        },
    }


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(detail), "code": "HTTP_ERROR"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.exception("Unhandled exception", extra={"path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "code": "INTERNAL_ERROR"},
    )
