"""MCP server exposing the Ultra CSM system.

Boots an ephemeral Postgres, seeds governance, builds the fixture data plane,
and exposes tools for scoring, sweeping, and governing customer-success work.
"""

from __future__ import annotations

import atexit
import logging
from dataclasses import asdict
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
from ultra_csm.agent1 import run_time_to_value_sweep, SweepResult

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
# Module-level singletons populated by _boot()
# ---------------------------------------------------------------------------

_cluster: EphemeralCluster | None = None
_conn: psycopg.Connection | None = None
_data_plane: CustomerDataPlane | None = None
_orch_principal: str | None = None
_authority_principal: str | None = None

# Map proposal_id -> ActionProposal kept in memory so submit_verdict can
# reconstruct the full proposal from just an id.
_proposals: dict[str, ActionProposal] = {}

# Cache the most recent sweep result so list_proposals can pull from it.
_last_sweep: SweepResult | None = None


def _boot() -> None:
    """Boot the ephemeral Postgres, run migrations, seed governance, and build
    the fixture data plane.  Called once at import time."""

    global _cluster, _conn, _data_plane, _orch_principal, _authority_principal

    setup_logging("INFO")
    log.info("Booting ephemeral Postgres cluster")

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
    _authority_principal = make_principal(
        _conn,
        tenant_id=_TENANT_ID,
        actor_id=_SEED_AGENT,
        display_name="order-confirm-authority",
        role=ROLE_ORDER_CONFIRM_AUTHORITY,
        now=_CLOCK,
    )

    # Build the fixture data plane (in-memory, no DB needed).
    _data_plane = build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT)

    log.info(
        "Ultra CSM MCP server ready",
        extra={"tenant_id": _TENANT_ID, "orch_principal": _orch_principal},
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
# Helpers
# ---------------------------------------------------------------------------


def _score_one_account(account_id: str) -> dict:
    """Build the value model + projected priority for a single account and
    return a serialisable dict."""

    assert _data_plane is not None

    account = _data_plane.crm.get_account(account_id)
    if account is None:
        return {"error": f"Account {account_id} not found in CRM"}

    company = _data_plane.cs.get_company(account_id)
    health = _data_plane.cs.get_health_score(account_id)
    adoption = _data_plane.cs.get_adoption_summary(account_id)

    if company is None or health is None:
        return {"error": f"Missing CS platform data for account {account_id}"}

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

    open_gaps = tuple(
        m for m in milestones if m.achieved_at is None
    )
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


def _build_account_brief(account_id: str) -> dict:
    """Compose a rich account brief from all data-plane sources."""

    assert _data_plane is not None

    account = _data_plane.crm.get_account(account_id)
    if account is None:
        return {"error": f"Account {account_id} not found in CRM"}

    company = _data_plane.cs.get_company(account_id)
    health = _data_plane.cs.get_health_score(account_id)
    adoption = _data_plane.cs.get_adoption_summary(account_id)

    if company is None or health is None:
        return {"error": f"Missing CS platform data for account {account_id}"}

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


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Ultra CSM",
    instructions=(
        "Ultra CSM is a customer-success management system. Use these tools "
        "to score accounts, run a time-to-value sweep across the book, review "
        "pending action proposals, and submit human verdicts (approve/deny)."
    ),
)


@mcp.tool()
def score_account(account_id: str) -> dict:
    """Score a single customer account.

    Returns the full value-model output including lifecycle stage, usage,
    penetration, feature depth, outcome rails, divergence signals, and the
    projected priority score with contributing factors.

    Args:
        account_id: The UUID of the account to score.
    """
    return _score_one_account(account_id)


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
            except Exception as exc:
                entry["priority_error"] = str(exc)

        results.append(entry)

    # Sort by priority score descending (accounts without a score go to the end).
    results.sort(
        key=lambda r: r.get("priority_score", -1),
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
    return _build_account_brief(account_id)


@mcp.tool()
def run_sweep() -> dict:
    """Run the Agent 1 time-to-value sweep across the entire tenant book.

    Evaluates every account, builds value models, computes priorities,
    proposes outreach where consent allows, and returns the prioritised
    work queue plus any identity-ambiguity escalations.
    """
    global _last_sweep

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
def submit_verdict(proposal_id: str, verdict: str, reason: str) -> dict:
    """Submit a human verdict on a pending action proposal.

    Approves or denies a proposal that was created during a sweep.
    The verdict transitions the proposal to its terminal state.

    Args:
        proposal_id: The UUID of the proposal to judge.
        verdict: One of "approve" or "deny".
        reason: Human-readable rationale for the decision.
    """
    assert _conn is not None and _authority_principal is not None

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
        human_principal_id=_authority_principal,
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
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_boot()

if __name__ == "__main__":
    mcp.run()
