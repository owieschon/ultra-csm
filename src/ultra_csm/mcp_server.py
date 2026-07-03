"""MCP server exposing the Ultra CSM system.

Boots an ephemeral Postgres, seeds governance, builds the fixture data plane,
and exposes tools for scoring, sweeping, and governing customer-success work.

The default MCP stdio transport is local-operator trust: it is intended for a
trusted local process on the same workstation. Any HTTP transport for this
server must require the same bearer token mapping used by the REST API. Verdict
tools still take an API token so approvals are signed by a token-mapped human
principal rather than a server-held authority.
"""

from __future__ import annotations

import atexit
import logging
import os
from pathlib import Path

import psycopg
from mcp.server.fastmcp import FastMCP

from ultra_csm.logging_config import setup_logging
from ultra_csm.platform import EphemeralCluster
from ultra_csm.platform.db import session
from ultra_csm.platform.seed import det_uuid, SEED_CLOCK

from ultra_csm.data_plane import (
    CustomerDataPlane,
    DEFAULT_TENANT,
    build_sweep_fixture_data_plane,
)
from ultra_csm.data_plane.synthetic_book import SEED_DATE
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
from ultra_csm.agent1 import run_time_to_value_sweep, SweepResult
from ultra_csm._api_helpers import (
    AccountDataError,
    AuthError,
    _build_account_brief,
    _score_one_account,
    auth_marker,
    demo_noauth_enabled,
    parse_api_tokens,
    resolve_write_principal,
    score_account_priority,
)
from ultra_csm.snapshot_store import SnapshotStore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
_CLOCK = SEED_CLOCK
_AS_OF = "2026-06-27"

_TENANT_NAME = "acme-csm"
_TENANT_ID = det_uuid("tenant", _TENANT_NAME)
_SEED_AGENT = det_uuid("principal", _TENANT_NAME, "system-seed")
_READONLY_ENV = "ULTRA_CSM_MCP_READONLY"
_READONLY_CODE = "MCP_READONLY"
_TIMELINE_DAYS = (0, 30, 60)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons populated by _boot()
# ---------------------------------------------------------------------------

_cluster: EphemeralCluster | None = None
_conn: psycopg.Connection | None = None
_data_plane: CustomerDataPlane | None = None
_orch_principal: str | None = None

# Map proposal_id -> ActionProposal kept in memory so submit_verdict can
# reconstruct the full proposal from just an id.
_proposals: dict[str, ActionProposal] = {}

# Cache the most recent sweep result so list_proposals can pull from it.
_last_sweep: SweepResult | None = None


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def mcp_readonly_enabled() -> bool:
    """Return whether MCP is running as a read-only conversational surface."""

    return _truthy(os.getenv(_READONLY_ENV))


def _readonly_refusal(tool_name: str) -> dict[str, str]:
    return {
        "error": (
            f"{tool_name} is disabled while {_READONLY_ENV}=1. "
            "Use the REST/API approval path or restart MCP without read-only mode."
        ),
        "code": _READONLY_CODE,
        "tool": tool_name,
        "access_mode": "read_only",
    }


def _boot() -> None:
    """Boot the fixture data plane and, unless read-only, the ephemeral
    Postgres governance store. Called once at import time.

    Read-only mode never runs a sweep or accepts a verdict, so it never
    writes to the governance database — the only read-only tool that would
    otherwise query it (list_proposals) always sees zero rows, since nothing
    but run_sweep populates action_proposal. Booting Postgres for that path
    bought nothing but startup latency and an external-tool dependency, so
    read-only mode skips it entirely: no initdb/pg_ctl subprocess, no
    Postgres 16 install required at all to talk to the account book.
    """

    global _cluster, _conn, _data_plane, _orch_principal

    setup_logging("INFO")

    if mcp_readonly_enabled():
        _data_plane = build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT)
        log.info(
            "Ultra CSM MCP server ready (read-only, no database)",
            extra={"tenant_id": _TENANT_ID, "auth": "read-only-no-db"},
        )
        return

    log.info("Booting ephemeral Postgres cluster")
    if demo_noauth_enabled():
        log.warning(
            "ULTRA_CSM_DEMO_NOAUTH=1 enabled; MCP verdict tools allow "
            "tokenless local demo approvals",
            extra={"auth": "demo-noauth"},
        )

    _cluster = EphemeralCluster().start()
    atexit.register(_cluster.stop)

    # Apply migrations and seed base tenant rows via a bootstrap connection.
    with psycopg.connect(**_cluster.dsn(user=_cluster.BOOTSTRAP_USER)) as boot:
        from ultra_csm.platform.db import apply_migrations
        from ultra_csm.platform.seed import seed

        apply_migrations(boot, _MIGRATIONS)
        seed(boot)

    # Open the runtime connection used for the lifetime of the server.
    dsn = _cluster.dsn(user="app_runtime")
    _conn = psycopg.connect(**dsn)

    # Seed the governance roster for the acme-csm tenant.
    seed_roster(_conn, tenant_id=_TENANT_ID, actor_id=_SEED_AGENT, now=_CLOCK)

    _orch_principal = make_principal(
        _conn,
        tenant_id=_TENANT_ID,
        actor_id=_SEED_AGENT,
        display_name="cs-orchestrator",
        role=ROLE_CS_ORCHESTRATOR,
        now=_CLOCK,
    )

    # Build the fixture data plane (in-memory, no DB needed).
    _data_plane = build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT)

    log.info(
        "Ultra CSM MCP server ready",
        extra={
            "tenant_id": _TENANT_ID,
            "orch_principal": _orch_principal,
            "auth": auth_marker(),
            "configured_api_tokens": len(parse_api_tokens()),
        },
    )


def _gate() -> ActionGate:
    """Build a fresh ActionGate bound to the runtime connection."""
    assert _conn is not None and _orch_principal is not None
    return ActionGate(
        _conn,
        tenant_id=_TENANT_ID,
        actor_principal_id=_orch_principal,
        verdict_source=FixtureVerdictSource(),
        now=_CLOCK,
    )


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Ultra CSM",
    instructions=(
        "Ultra CSM is a customer-success management system. Use these tools "
        "to score accounts, inspect account context, review pending action "
        "proposals, and submit human verdicts only when write access is enabled."
    ),
)


MCP_TOOL_AUDIT: tuple[dict[str, object], ...] = (
    {
        "name": "score_account",
        "classification": "read",
        "readonly_available": True,
    },
    {
        "name": "list_accounts",
        "classification": "read",
        "readonly_available": True,
    },
    {
        "name": "get_account_brief",
        "classification": "read",
        "readonly_available": True,
    },
    {
        "name": "get_hold_status",
        "classification": "read",
        "readonly_available": True,
    },
    {
        "name": "get_trajectory",
        "classification": "read",
        "readonly_available": True,
    },
    {
        "name": "list_proposals",
        "classification": "read",
        "readonly_available": True,
    },
    {
        "name": "run_sweep",
        "classification": "state_changing",
        "readonly_available": False,
    },
    {
        "name": "submit_verdict",
        "classification": "state_changing",
        "readonly_available": False,
    },
)


@mcp.tool()
def get_tool_manifest() -> dict:
    """List MCP tools and their read/write classification."""

    return {
        "access_mode": "read_only" if mcp_readonly_enabled() else "operator",
        "read_only_env": _READONLY_ENV,
        "tools": [dict(tool) for tool in MCP_TOOL_AUDIT],
    }


@mcp.tool()
def score_account(account_id: str) -> dict:
    """Score a single customer account.

    Returns the full value-model output including lifecycle stage, usage,
    penetration, feature depth, outcome rails, divergence signals, and the
    projected priority score with contributing factors.

    Args:
        account_id: The UUID of the account to score.
    """
    assert _data_plane is not None
    try:
        return _score_one_account(account_id, data_plane=_data_plane, as_of=_AS_OF)
    except AccountDataError as exc:
        return {"error": str(exc), "code": exc.code, "account_id": exc.account_id}


@mcp.tool()
def list_accounts() -> dict:
    """List all accounts in the fixture tenant with their priority scores.

    Returns a list of accounts, each with account_id, name, health band,
    lifecycle stage, ARR, and projected priority score.
    """
    assert _data_plane is not None

    accounts = _data_plane.crm.list_accounts(tenant_id=DEFAULT_TENANT)
    results = []

    for account in accounts:
        company = _data_plane.cs.get_company(account.account_id)
        health = _data_plane.cs.get_health_score(account.account_id)
        adoption = _data_plane.cs.get_adoption_summary(account.account_id)

        entry: dict = {
            "account_id": account.account_id,
            "account_name": account.name,
            "industry": account.industry,
            "owner_id": account.owner_id,
        }

        if company:
            entry["arr_cents"] = company.arr_cents
            entry["lifecycle_stage"] = company.lifecycle_stage
            entry["status"] = company.status
            entry["renewal_date"] = company.renewal_date

        if health:
            entry["health_band"] = health.band
            entry["health_score"] = health.score

        if adoption:
            entry["adoption_rate"] = adoption.adoption_rate
            entry["active_users"] = adoption.active_users
            entry["licensed_users"] = adoption.licensed_users

        # Compute priority if we have enough data.
        if company and health and adoption:
            try:
                priority_score, _divergences = score_account_priority(
                    account.account_id,
                    data_plane=_data_plane,
                    as_of=_AS_OF,
                )
                entry["priority_score"] = priority_score
            except Exception as exc:
                log.warning(
                    "priority_score_failed",
                    extra={
                        "surface": "mcp.list_accounts",
                        "account_id": account.account_id,
                        "error_type": exc.__class__.__name__,
                    },
                )
                entry["priority_score"] = None
                entry["priority_score_error"] = exc.__class__.__name__

        results.append(entry)

    # Sort by priority score descending (accounts without a score go to the end).
    results.sort(
        key=lambda r: r["priority_score"] if r.get("priority_score") is not None else -1,
        reverse=True,
    )

    return {
        "tenant_id": DEFAULT_TENANT,
        "account_count": len(results),
        "accounts": results,
    }


@mcp.tool()
def get_account_brief(account_id: str) -> dict:
    """Get a comprehensive account brief for a single customer.

    Returns a health snapshot, recent changes, risk signals, expansion
    opportunities, open CTAs, success plans, open cases, contacts,
    milestones, and suggested talking points derived from the value model.

    Args:
        account_id: The UUID of the account.
    """
    assert _data_plane is not None
    try:
        return _build_account_brief(account_id, data_plane=_data_plane, as_of=_AS_OF)
    except AccountDataError as exc:
        return {"error": str(exc), "code": exc.code, "account_id": exc.account_id}


@mcp.tool()
def get_hold_status(account_id: str) -> dict:
    """Read whether a customer-facing expansion action is currently held.

    The current MCP fixture surface has no DB-backed hold queue. This tool
    therefore derives the same default policy from current records and the
    precedence matrix without creating proposals or changing state.

    Args:
        account_id: Account id to inspect.
    """

    assert _data_plane is not None
    account = _find_account(account_id)
    if account is None:
        return {
            "error": f"Account {account_id} not found",
            "code": "ACCOUNT_NOT_FOUND",
            "account_id": account_id,
        }

    expansion_opps = tuple(
        opp for opp in _data_plane.crm.list_opportunities(account.account_id)
        if opp.opportunity_type.lower() == "expansion"
    )
    blockers = _expansion_blockers(account.account_id)
    status = (
        "held"
        if expansion_opps and blockers
        else "blocked_no_action"
        if blockers
        else "not_held"
    )
    return {
        "account_id": account.account_id,
        "account_name": account.name,
        "action_scope": "customer_facing",
        "lens": "expansion",
        "status": status,
        "blocking_refs": [blocker["blocking_ref"] for blocker in blockers],
        "blockers": blockers,
        "held_since": _AS_OF if status == "held" else None,
        "release_conditions": (
            ["all_blocking_refs_clear_or_dismissed", "authorized_override"]
            if status == "held"
            else []
        ),
        "expansion_opportunities": [
            {
                "opportunity_id": opp.opportunity_id,
                "stage_name": opp.stage_name,
                "amount_cents": opp.amount_cents,
                "close_date": opp.close_date,
            }
            for opp in expansion_opps
        ],
        "source": "read_only_precedence_projection",
        "claim_boundary": {"sim": True, "live": False},
    }


@mcp.tool()
def get_trajectory(account_id: str, window_days: int = 60) -> dict:
    """Read the recent simulated health trajectory for an account.

    Args:
        account_id: Account id to inspect.
        window_days: Lookback window in days. Defaults to 60.
    """

    assert _data_plane is not None
    account = _find_account(account_id)
    if account is None:
        return {
            "error": f"Account {account_id} not found",
            "code": "ACCOUNT_NOT_FOUND",
            "account_id": account_id,
        }

    store = _fixture_trajectory_store(account.account_id)
    trajectory = store.build_trajectory(account.account_id, window_days=window_days)
    return {
        "account_id": account.account_id,
        "account_name": account.name,
        "window_days": trajectory.window_days,
        "trend": trajectory.trend,
        "trend_velocity": trajectory.trend_velocity,
        "consecutive_band": trajectory.consecutive_band,
        "consecutive_count": trajectory.consecutive_count,
        "points": [
            {
                "day": point.day,
                "health_band": point.health_band,
                "health_score": point.health_score,
                "priority_score": point.priority_score,
                "priority_factors": list(point.priority_factors),
            }
            for point in trajectory.points
        ],
        "claim_boundary": {"sim": True, "live": False},
    }


@mcp.tool()
def run_sweep() -> dict:
    """Run the Agent 1 time-to-value sweep across the entire tenant book.

    Evaluates every account, builds value models, computes priorities,
    proposes outreach where consent allows, and returns the prioritised
    work queue plus any identity-ambiguity escalations.
    """
    global _last_sweep

    if mcp_readonly_enabled():
        return _readonly_refusal("run_sweep")

    assert _data_plane is not None and _orch_principal is not None

    gate = _gate()
    sweep = run_time_to_value_sweep(
        _data_plane,
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=_orch_principal,
        as_of=_AS_OF,
    )

    # Cache proposals from work items for later verdict submission.
    for item in sweep.work_items:
        if item.proposal is not None:
            _proposals[item.proposal.proposal_id] = ActionProposal(
                proposal_id=item.proposal.proposal_id,
                intent="agent1_time_to_value_sweep",
                action=item.proposal.action_type,
                payload={},  # payload not carried on ProposalRef
                payload_sha256="",
                autonomy_tier=0,
                required_permission="",
                status=item.proposal.status,
            )

    _last_sweep = sweep

    return sweep.to_dict()


@mcp.tool()
def list_proposals() -> dict:
    """List all pending action proposals from the most recent sweep.

    Returns proposals that are awaiting a human verdict (approve or deny).
    Run the sweep first if no proposals exist.
    """
    if mcp_readonly_enabled():
        return {
            "tenant_id": _TENANT_ID,
            "pending_count": 0,
            "proposals": [],
            "note": (
                "read-only mode never runs a sweep, so no proposals ever exist "
                "here — this is not an error. Restart without "
                f"{_READONLY_ENV}=1 and call run_sweep to generate real ones."
            ),
        }

    assert _conn is not None

    # Query the DB for pending proposals in this tenant.
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
        proposal_id = str(row[0])
        proposal = ActionProposal(
            proposal_id=proposal_id,
            intent=row[1],
            action=row[2],
            payload=row[3] if isinstance(row[3], dict) else {},
            payload_sha256=row[4],
            autonomy_tier=row[5],
            required_permission=row[6],
            status=row[7],
        )
        # Update the in-memory cache.
        _proposals[proposal_id] = proposal

        proposals.append({
            "proposal_id": proposal_id,
            "intent": proposal.intent,
            "action": proposal.action,
            "payload": proposal.payload,
            "autonomy_tier": proposal.autonomy_tier,
            "required_permission": proposal.required_permission,
            "status": proposal.status,
        })

    return {
        "tenant_id": _TENANT_ID,
        "pending_count": len(proposals),
        "proposals": proposals,
    }


@mcp.tool()
def submit_verdict(
    proposal_id: str,
    verdict: str,
    reason: str,
    token: str | None = None,
) -> dict:
    """Submit a human verdict on a pending action proposal.

    Approves or denies a proposal that was created during a sweep.
    The verdict transitions the proposal to its terminal state.

    Args:
        proposal_id: The UUID of the proposal to judge.
        verdict: One of "approve" or "deny".
        reason: Human-readable rationale for the decision.
        token: API token mapped by ULTRA_CSM_API_TOKENS to the approving human.
    """
    if mcp_readonly_enabled():
        return _readonly_refusal("submit_verdict")

    assert _conn is not None and _orch_principal is not None

    try:
        auth_principal = resolve_write_principal(
            _conn,
            tenant_id=_TENANT_ID,
            actor_id=_orch_principal,
            now=_CLOCK,
            token=token,
        )
    except AuthError as exc:
        return {"error": str(exc), "code": exc.code}

    if verdict not in ("approve", "deny"):
        return {"error": f"Invalid verdict '{verdict}'. Must be 'approve' or 'deny'."}

    # Look up the proposal -- first from cache, then from the DB.
    proposal = _proposals.get(proposal_id)
    if proposal is None:
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
            return {"error": f"Proposal {proposal_id} not found"}

        import json as _json

        payload_raw = row[3]
        payload = (
            _json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
        )
        proposal = ActionProposal(
            proposal_id=str(row[0]),
            intent=row[1],
            action=row[2],
            payload=payload if isinstance(payload, dict) else {},
            payload_sha256=row[4],
            autonomy_tier=row[5],
            required_permission=row[6],
            status=row[7],
        )

    if proposal.status != "pending":
        return {
            "error": f"Proposal {proposal_id} is already '{proposal.status}', "
            f"cannot apply verdict."
        }

    gate = _gate()
    human_verdict = Verdict(
        verdict=verdict,
        human_principal_id=auth_principal.principal_id,
        rationale=reason,
    )

    try:
        outcome = gate.record_verdict(proposal, human_verdict)
    except GateError as exc:
        return {"error": str(exc)}

    # Update cache.
    _proposals.pop(proposal_id, None)

    return {
        "proposal_id": outcome.proposal_id,
        "status": outcome.status,
        "authorized": outcome.authorized,
        "verdict": outcome.verdict,
        "payload_sha256": outcome.payload_sha256,
        "auth": auth_principal.auth,
    }


def _find_account(account_id: str):
    assert _data_plane is not None
    for account in _data_plane.crm.list_accounts(tenant_id=DEFAULT_TENANT):
        if account.account_id == account_id or account.name.lower() == account_id.lower():
            return account
    return None


def _expansion_blockers(account_id: str) -> tuple[dict[str, object], ...]:
    assert _data_plane is not None
    blockers: list[dict[str, object]] = []
    company = _data_plane.cs.get_company(account_id)
    health = _data_plane.cs.get_health_score(account_id)
    ctas = tuple(_data_plane.cs.list_ctas(account_id, status="open"))
    milestones = tuple(_data_plane.telemetry.list_ttv_milestones(account_id))
    open_milestones = tuple(
        milestone for milestone in milestones
        if milestone.achieved_at is None and milestone.expected_by < _AS_OF
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
        blockers.append({
            "lens": "ttv_gap",
            "blocking_ref": f"ttv_gap:{account_id}",
            "evidence_refs": [
                *(f"milestone:{account_id}:{item.milestone}" for item in open_milestones),
                *(f"cta:{item.cta_id}" for item in ctas),
            ],
            "reason": "active onboarding or adoption gap blocks customer-facing expansion",
        })
    if health is not None and health.band == "red":
        blockers.append({
            "lens": "risk",
            "blocking_ref": f"risk:{account_id}",
            "evidence_refs": [f"health:{account_id}"],
            "reason": "red health blocks customer-facing expansion",
        })
    return tuple(blockers)


def _fixture_trajectory_store(account_id: str) -> SnapshotStore:
    assert _data_plane is not None
    store = SnapshotStore()
    for day in _TIMELINE_DAYS:
        payload = _trajectory_payload_for_day(account_id, day)
        if payload is not None:
            store.store_snapshot(day, account_id, payload)
    return store


def _trajectory_payload_for_day(account_id: str, day: int) -> dict[str, object] | None:
    assert _data_plane is not None
    # The MCP fixture data is point-in-time. Keep the tool read-only by deriving
    # a conservative three-point simulated history from the current records.
    account = _find_account(account_id)
    company = _data_plane.cs.get_company(account_id)
    health = _data_plane.cs.get_health_score(account_id)
    if account is None or company is None or health is None:
        return None
    priority_score, _divergences = score_account_priority(
        account_id,
        data_plane=_data_plane,
        as_of=_AS_OF,
    )
    day_index = _TIMELINE_DAYS.index(day)
    score_adjustment = (-4.0, -2.0, 0.0)[day_index]
    health_score = max(0.0, min(100.0, health.score + score_adjustment))
    return {
        "health_band": health.band,
        "health_score": health_score,
        "priority_score": priority_score,
        "priority_factors": tuple(health.drivers),
        "lifecycle_stage": company.lifecycle_stage,
        "arr_cents": company.arr_cents,
        "as_of": SEED_DATE if day == 0 else _AS_OF,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_boot()

if __name__ == "__main__":
    mcp.run()
