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
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

import psycopg
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
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
    ROLE_ORDER_CONFIRM_AUTHORITY,
)
from ultra_csm.value_model import (
    build_customer_value_model,
    project_ttv_lens,
)
from ultra_csm.agent1 import run_time_to_value_sweep

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
_authority_principal: str | None = None


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
    divergences: list[dict[str, Any]]
    open_ctas: list[dict[str, Any]]
    success_plans: list[dict[str, Any]]
    open_cases: list[dict[str, Any]]
    contacts: list[dict[str, Any]]
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
    verdict: Literal["approve", "deny"]
    reason: str


class VerdictResponse(BaseModel):
    proposal_id: str
    status: str
    authorized: bool
    verdict: str
    payload_sha256: str


class DigestAccountSchema(BaseModel):
    account_id: str
    account_name: str
    health_band: str | None = None
    priority_score: int | None = None
    disposition: str | None = None
    reason: str | None = None


class DigestResponse(BaseModel):
    tenant_id: str
    as_of: str
    prioritized_accounts: list[DigestAccountSchema]
    pending_proposals: int
    commitments: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Lifespan (boot/teardown)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Boot ephemeral Postgres, seed, and configure on startup; tear down on
    shutdown."""
    global _cluster, _conn, _data_plane, _orch_principal, _authority_principal

    setup_logging("INFO")
    log.info("Booting ephemeral Postgres cluster for API")

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
    _authority_principal = make_principal(
        _conn,
        tenant_id=_TENANT_ID,
        actor_id=_SEED_AGENT,
        display_name="order-confirm-authority",
        role=ROLE_ORDER_CONFIRM_AUTHORITY,
        now=_CLOCK,
    )

    # Build the fixture data plane.
    _data_plane = build_sweep_fixture_data_plane()

    log.info(
        "Ultra CSM API ready",
        extra={"tenant_id": _TENANT_ID, "orch_principal": _orch_principal},
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


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def request_logging(request: Request, call_next):
    start = time.monotonic()
    response: Response = await call_next(request)
    elapsed_ms = (time.monotonic() - start) * 1000

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


def _require_account(account_id: str):
    """Look up an account; raise 404 if not found."""
    assert _data_plane is not None
    account = _data_plane.crm.get_account(account_id)
    if account is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Account not found", "code": "ACCOUNT_NOT_FOUND",
                    "account_id": account_id},
        )
    return account


def _score_one_account(account_id: str) -> dict[str, Any]:
    """Build the value model + projected priority for a single account."""
    assert _data_plane is not None

    account = _require_account(account_id)
    company = _data_plane.cs.get_company(account_id)
    health = _data_plane.cs.get_health_score(account_id)
    adoption = _data_plane.cs.get_adoption_summary(account_id)

    if company is None or health is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Missing CS platform data", "code": "MISSING_CS_DATA",
                    "account_id": account_id},
        )

    entitlements = tuple(_data_plane.telemetry.list_entitlements(account_id))
    signals = tuple(_data_plane.telemetry.list_usage_signals(account_id))
    plans = tuple(_data_plane.cs.list_success_plans(account_id))
    milestones = tuple(_data_plane.telemetry.list_ttv_milestones(account_id))

    model = build_customer_value_model(
        account=account,
        company=company,
        health=health,
        adoption=adoption,
        entitlements=entitlements,
        usage_signals=signals,
        success_plans=plans,
    )

    open_gaps = tuple(m for m in milestones if m.achieved_at is None)
    overdue_plans = tuple(
        p for p in plans if p.target_date and p.target_date <= _AS_OF
    )

    projected = project_ttv_lens(
        model,
        company=company,
        health=health,
        open_milestone_gaps=open_gaps,
        overdue_success_plans=overdue_plans,
        as_of=_AS_OF,
    )

    return {
        "account_id": account_id,
        "account_name": account.name,
        "lifecycle_stage": model.lifecycle_stage,
        "resolved_thresholds": asdict(model.resolved_thresholds),
        "usage": asdict(model.usage),
        "penetration": asdict(model.penetration),
        "feature_depth": asdict(model.feature_depth),
        "outcome": asdict(model.outcome),
        "divergences": [asdict(d) for d in model.divergences],
        "priority": {
            "score": projected.score,
            "factors": [asdict(f) for f in projected.factors],
        },
    }


def _build_account_brief(account_id: str) -> dict[str, Any]:
    """Compose a rich account brief from all data-plane sources."""
    assert _data_plane is not None

    account = _require_account(account_id)
    company = _data_plane.cs.get_company(account_id)
    health = _data_plane.cs.get_health_score(account_id)
    adoption = _data_plane.cs.get_adoption_summary(account_id)

    if company is None or health is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Missing CS platform data", "code": "MISSING_CS_DATA",
                    "account_id": account_id},
        )

    entitlements = tuple(_data_plane.telemetry.list_entitlements(account_id))
    signals = tuple(_data_plane.telemetry.list_usage_signals(account_id))
    plans = tuple(_data_plane.cs.list_success_plans(account_id))
    milestones = tuple(_data_plane.telemetry.list_ttv_milestones(account_id))
    ctas = _data_plane.cs.list_ctas(account_id)
    cases = _data_plane.crm.list_cases(account_id)
    contacts = _data_plane.crm.list_contacts(account_id)
    opportunities = _data_plane.crm.list_opportunities(account_id)

    model = build_customer_value_model(
        account=account,
        company=company,
        health=health,
        adoption=adoption,
        entitlements=entitlements,
        usage_signals=signals,
        success_plans=plans,
    )

    open_gaps = tuple(m for m in milestones if m.achieved_at is None)
    overdue_plans = tuple(
        p for p in plans if p.target_date and p.target_date <= _AS_OF
    )

    projected = project_ttv_lens(
        model,
        company=company,
        health=health,
        open_milestone_gaps=open_gaps,
        overdue_success_plans=overdue_plans,
        as_of=_AS_OF,
    )

    # Derive talking points from evidence and model factors.
    talking_points: list[str] = []
    for factor in projected.factors:
        if factor.contribution > 0:
            talking_points.append(
                f"{factor.name}: value={factor.value:.2f}, "
                f"contribution=+{factor.contribution} "
                f"(rule: {factor.rule_name})"
            )
    for div in model.divergences:
        talking_points.append(
            f"Divergence signal: {div.name} "
            f"(value={div.value:.2f}, contribution={div.contribution:+d})"
        )
    if health.band in ("red", "yellow"):
        talking_points.append(
            f"Health is {health.band} (score {health.score}) -- "
            f"drivers: {', '.join(health.drivers) if health.drivers else 'unknown'}"
        )
    if adoption and adoption.underused_capabilities:
        talking_points.append(
            f"Underused capabilities: {', '.join(adoption.underused_capabilities)}"
        )
    for gap in open_gaps:
        talking_points.append(
            f"Overdue milestone: {gap.milestone} (expected by {gap.expected_by})"
        )

    open_ctas = [c for c in ctas if c.status in ("open", "in_progress")]
    open_cases = [c for c in cases if c.closed_at is None]

    return {
        "account_id": account_id,
        "account_name": account.name,
        "industry": account.industry,
        "company": {
            "arr_cents": company.arr_cents,
            "lifecycle_stage": company.lifecycle_stage,
            "status": company.status,
            "renewal_date": company.renewal_date,
            "csm_owner_id": company.csm_owner_id,
        },
        "health_snapshot": {
            "score": health.score,
            "band": health.band,
            "drivers": list(health.drivers) if health.drivers else [],
            "measured_at": health.measured_at,
        },
        "adoption": asdict(adoption) if adoption else None,
        "priority": {
            "score": projected.score,
            "factors": [asdict(f) for f in projected.factors],
        },
        "lifecycle_stage": model.lifecycle_stage,
        "divergences": [asdict(d) for d in model.divergences],
        "open_ctas": [asdict(c) for c in open_ctas],
        "success_plans": [asdict(p) for p in plans],
        "open_cases": [asdict(c) for c in open_cases],
        "contacts": [
            {
                "name": c.name,
                "email": c.email,
                "role": c.role,
                "title": c.title,
                "consent_to_contact": c.consent_to_contact,
            }
            for c in contacts
        ],
        "opportunities": [asdict(o) for o in opportunities],
        "entitlements": [asdict(e) for e in entitlements],
        "recent_usage_signals": [asdict(s) for s in signals[:20]],
        "milestones": [asdict(m) for m in milestones],
        "suggested_talking_points": talking_points,
    }


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
    )


@app.get("/accounts", response_model=AccountListResponse)
async def list_accounts():
    """List all accounts with current value model scores."""
    assert _data_plane is not None

    accounts = _data_plane.crm.list_accounts(tenant_id=DEFAULT_TENANT)
    results: list[dict[str, Any]] = []

    for account in accounts:
        company = _data_plane.cs.get_company(account.account_id)
        health = _data_plane.cs.get_health_score(account.account_id)
        adoption = _data_plane.cs.get_adoption_summary(account.account_id)

        entry: dict[str, Any] = {
            "account_id": account.account_id,
            "account_name": account.name,
            "industry": account.industry,
        }

        if company:
            entry["arr_cents"] = company.arr_cents
            entry["lifecycle_stage"] = company.lifecycle_stage

        if health:
            entry["health_band"] = health.band
            entry["health_score"] = health.score

        # Compute priority if we have enough data.
        if company and health and adoption:
            try:
                entitlements = tuple(
                    _data_plane.telemetry.list_entitlements(account.account_id)
                )
                signals = tuple(
                    _data_plane.telemetry.list_usage_signals(account.account_id)
                )
                plans = tuple(
                    _data_plane.cs.list_success_plans(account.account_id)
                )
                milestones = tuple(
                    _data_plane.telemetry.list_ttv_milestones(account.account_id)
                )

                model = build_customer_value_model(
                    account=account,
                    company=company,
                    health=health,
                    adoption=adoption,
                    entitlements=entitlements,
                    usage_signals=signals,
                    success_plans=plans,
                )
                open_gaps = tuple(m for m in milestones if m.achieved_at is None)
                overdue_plans = tuple(
                    p for p in plans
                    if p.target_date and p.target_date <= _AS_OF
                )
                projected = project_ttv_lens(
                    model,
                    company=company,
                    health=health,
                    open_milestone_gaps=open_gaps,
                    overdue_success_plans=overdue_plans,
                    as_of=_AS_OF,
                )
                entry["priority_score"] = projected.score
            except Exception:
                pass

        results.append(entry)

    # Sort by priority score descending.
    results.sort(key=lambda r: r.get("priority_score", -1), reverse=True)

    return AccountListResponse(
        tenant_id=DEFAULT_TENANT,
        account_count=len(results),
        accounts=[AccountSummarySchema(**r) for r in results],
    )


@app.get("/accounts/{account_id}")
async def get_account_detail(account_id: str):
    """Single account detail: value model output, active factors, divergence
    signals, lens projections."""
    return _score_one_account(account_id)


@app.get("/accounts/{account_id}/brief")
async def get_account_brief(account_id: str):
    """Account brief — the key demo endpoint.

    Health snapshot, recent changes, risks, expansion signals, and suggested
    talking points.
    """
    return _build_account_brief(account_id)


@app.post("/sweep", response_model=SweepResponse)
async def trigger_sweep():
    """Trigger a sweep of the book, return the SweepResult."""
    assert _data_plane is not None and _orch_principal is not None

    log.info("Sweep triggered", extra={"tenant_id": _TENANT_ID})

    gate = _gate()
    sweep = run_time_to_value_sweep(
        _data_plane,
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=_orch_principal,
        as_of=_AS_OF,
    )

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
        },
    )

    result = sweep.to_dict()
    # Ensure the top-level keys match the SweepResponse model.
    return SweepResponse(
        tenant_id=result["tenant_id"],
        work_items=list(result.get("work_items", ())),
        escalations=list(result.get("escalations", ())),
        swept_accounts=list(result.get("swept_accounts", ())),
        degraded_items=result.get("degraded_items", 0),
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


@app.post("/proposals/{proposal_id}/verdict", response_model=VerdictResponse)
async def submit_verdict(proposal_id: str, body: VerdictRequest):
    """Submit approve/deny verdict — the live verdict source (G-6)."""
    assert _conn is not None and _authority_principal is not None

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

    gate = _gate()
    human_verdict = Verdict(
        verdict=body.verdict,
        human_principal_id=_authority_principal,
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
            "actor": _authority_principal,
        },
    )

    return VerdictResponse(
        proposal_id=outcome.proposal_id,
        status=outcome.status,
        authorized=outcome.authorized,
        verdict=outcome.verdict,
        payload_sha256=outcome.payload_sha256,
    )


@app.get("/digest", response_model=DigestResponse)
async def get_digest():
    """Daily digest — prioritized accounts, proposals, commitments."""
    assert _data_plane is not None and _conn is not None

    # 1. Prioritized accounts with a quick sweep.
    accounts = _data_plane.crm.list_accounts(tenant_id=DEFAULT_TENANT)
    prioritized: list[DigestAccountSchema] = []

    for account in accounts:
        company = _data_plane.cs.get_company(account.account_id)
        health = _data_plane.cs.get_health_score(account.account_id)
        adoption = _data_plane.cs.get_adoption_summary(account.account_id)

        entry = DigestAccountSchema(
            account_id=account.account_id,
            account_name=account.name,
            health_band=health.band if health else None,
        )

        if company and health and adoption:
            try:
                entitlements = tuple(
                    _data_plane.telemetry.list_entitlements(account.account_id)
                )
                signals = tuple(
                    _data_plane.telemetry.list_usage_signals(account.account_id)
                )
                plans = tuple(
                    _data_plane.cs.list_success_plans(account.account_id)
                )
                milestones = tuple(
                    _data_plane.telemetry.list_ttv_milestones(account.account_id)
                )
                model = build_customer_value_model(
                    account=account,
                    company=company,
                    health=health,
                    adoption=adoption,
                    entitlements=entitlements,
                    usage_signals=signals,
                    success_plans=plans,
                )
                open_gaps = tuple(m for m in milestones if m.achieved_at is None)
                overdue_plans = tuple(
                    p for p in plans
                    if p.target_date and p.target_date <= _AS_OF
                )
                projected = project_ttv_lens(
                    model,
                    company=company,
                    health=health,
                    open_milestone_gaps=open_gaps,
                    overdue_success_plans=overdue_plans,
                    as_of=_AS_OF,
                )
                entry = DigestAccountSchema(
                    account_id=account.account_id,
                    account_name=account.name,
                    health_band=health.band,
                    priority_score=projected.score,
                )
            except Exception:
                pass

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
        as_of=_AS_OF,
        prioritized_accounts=prioritized,
        pending_proposals=pending_count,
        commitments=commitments,
    )


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
