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
from dataclasses import dataclass, field, replace
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Mapping

import psycopg
from mcp.server.fastmcp import FastMCP

from ultra_csm.logging_config import setup_logging
from ultra_csm.platform import EphemeralCluster
from ultra_csm.platform.db import session
from ultra_csm.platform.seed import det_uuid, SEED_CLOCK

from ultra_csm.data_plane import (
    ACME_LOGISTICS,
    CYBERDYNE_NO_CONSENT,
    CustomerDataPlane,
    DEFAULT_DEMO_STATE_DIR,
    DEFAULT_TENANT,
    SimTenantStore,
    build_sweep_fixture_data_plane,
    FixtureCRMDataConnector,
    FixtureCSPlatformConnector,
    FixtureCustomerData,
    FixtureProductTelemetryConnector,
)
from ultra_csm.data_plane.external_book import (
    CONNECTOR_ID as _EXTERNAL_CONNECTOR_ID,
    DEFAULT_MAX_RECORDS,
    ExternalSourceDescriptor,
    RelationalTable,
    ingest_external_book,
    ingest_relational_book,
    propose_external_source_mapping,
)
from ultra_csm.data_plane.connector_catalog import CONNECTOR_SPECS
from ultra_csm.data_plane.synthetic_book import SEED_DATE
from ultra_csm.data_plane.source_mapping import (
    MappingConfirmation,
    ProposedFieldMapping,
    SourceMapProposal,
    freeze_confirmed_source_map,
)
from ultra_csm.governance import (
    ActionGate,
    ActionProposal,
    FixtureVerdictSource,
    GateError,
    Verdict,
    canonical_payload_sha256,
    proposal_fields_for,
    seed_roster,
    make_principal,
    ROLE_CS_ORCHESTRATOR,
)
from ultra_csm.email_drafts import (
    EmailDraftError,
    render_email_draft_from_payload,
    render_email_draft_from_proposal,
)
from ultra_csm.agent1 import run_time_to_value_sweep, SweepResult
from ultra_csm.committers import SimCrmActivityCommitter, SimOutboundCommitter
from ultra_csm.proposal_revise import ReviseServiceError, apply_bounded_revise
from ultra_csm._api_helpers import (
    AccountDataError,
    AuthError,
    _build_account_brief,
    _proposal_has_contact_consent,
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
_DEMO_OPERATOR_ENV = "ULTRA_CSM_DEMO_OPERATOR"
_READONLY_CODE = "MCP_READONLY"
_DEMO_STATE_DIR = DEFAULT_DEMO_STATE_DIR / "mcp_operator"
_TIMELINE_DAYS = (0, 30, 60)
_RELAY_MAX_RECORDS = DEFAULT_MAX_RECORDS

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons populated by _boot()
# ---------------------------------------------------------------------------

_cluster: EphemeralCluster | None = None
_conn: psycopg.Connection | None = None
_data_plane: CustomerDataPlane | None = None
_sim_store: SimTenantStore | None = None
_orch_principal: str | None = None

# Map proposal_id -> ActionProposal kept in memory so submit_verdict can
# reconstruct the full proposal from just an id.
_proposals: dict[str, ActionProposal] = {}

# Cache the most recent sweep result so list_proposals can pull from it.
_last_sweep: SweepResult | None = None
_session_events: list[dict[str, object]] = []


@dataclass
class _RelaySession:
    session_id: str
    descriptor: ExternalSourceDescriptor
    expected_count: int
    raw_records: list[dict[str, Any]] = field(default_factory=list)
    received_count: int = 0
    dropped_record_count: int = 0
    proposal: SourceMapProposal | None = None
    frozen_config_hash: str | None = None
    replay_sha256: str | None = None
    # Relational ingest_table path only; the flat ingest_book path never sets
    # these. field_metadata is source-declared per-column metadata (e.g. a
    # Salesforce describe); contract is the host-declared contract this
    # table's records ARE.
    field_metadata: dict[str, dict[str, Any]] | None = None
    contract: str | None = None


_relay_sessions: dict[str, _RelaySession] = {}
_last_relay_session_id: str | None = None

# Relational books: book_id -> {table_name -> per-table relay session}. Kept
# separate from _relay_sessions so the flat single-table tools can never grab
# a table of a relational book (and vice versa).
_relational_books: dict[str, dict[str, _RelaySession]] = {}


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def mcp_readonly_enabled() -> bool:
    """Return whether MCP is running as a read-only conversational surface."""

    return _truthy(os.getenv(_READONLY_ENV))


def mcp_demo_operator_enabled() -> bool:
    """Return whether MCP should run the local sim operator loop."""

    return _truthy(os.getenv(_DEMO_OPERATOR_ENV))


def _validate_access_mode_env() -> None:
    if mcp_readonly_enabled() and mcp_demo_operator_enabled():
        raise RuntimeError(
            f"{_READONLY_ENV}=1 and {_DEMO_OPERATOR_ENV}=1 are mutually exclusive"
        )


def _access_mode() -> str:
    if mcp_readonly_enabled():
        return "read_only"
    if mcp_demo_operator_enabled():
        return "demo_operator"
    return "operator"


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


def _relay_claim_boundary(*, unverified_mapping: bool = True) -> dict[str, object]:
    return {
        "provenance": "mcp_relay",
        "unverified_mapping": unverified_mapping,
        "sim": False,
        "live": False,
    }


def _relay_refusal(code: str, message: str, tool_name: str, **extra: object) -> dict:
    payload: dict[str, object] = {
        "error": message,
        "code": code,
        "tool": tool_name,
        "claim_boundary": _relay_claim_boundary(),
    }
    payload.update(extra)
    return payload


def _relay_tool_available(tool_name: str) -> dict | None:
    if mcp_readonly_enabled():
        return _readonly_refusal(tool_name)
    if mcp_demo_operator_enabled():
        return _relay_refusal(
            "RELAY_DEMO_OPERATOR_CONFLICT",
            (
                f"{tool_name} mutates relay session state and is disabled while "
                f"{_DEMO_OPERATOR_ENV}=1. Restart MCP without demo-operator mode "
                "to ingest host-relayed books."
            ),
            tool_name,
            access_mode="demo_operator",
        )
    return None


def _with_demo_context(payload: dict, *, suggested_next: list[str] | None = None) -> dict:
    if not mcp_demo_operator_enabled():
        return payload
    result = dict(payload)
    result.setdefault("claim_boundary", {"sim": True, "live": False})
    result.setdefault("suggested_next", suggested_next or _default_suggested_next())
    return result


def _default_suggested_next() -> list[str]:
    return [
        "get_morning_briefing",
        "list_proposals",
        "get_session_ledger",
    ]


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

    global _cluster, _conn, _data_plane, _sim_store, _orch_principal

    setup_logging("INFO")
    _validate_access_mode_env()

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
            "Demo no-auth enabled; MCP verdict tools allow "
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

    if mcp_demo_operator_enabled():
        _reset_demo_operator_state()
        _sim_store = SimTenantStore.seed(
            _DEMO_STATE_DIR,
            tenant_id=DEFAULT_TENANT,
            reset=True,
        )
        _data_plane = _sim_store.data_plane()
        _run_sweep_and_cache(cause_ref="mcp-demo:boot")
        _seed_demo_refusal_proposals()
    else:
        # Build the fixture data plane (in-memory, no DB needed).
        _data_plane = build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT)

    log.info(
        "Ultra CSM MCP server ready",
        extra={
            "tenant_id": _TENANT_ID,
            "orch_principal": _orch_principal,
            "auth": auth_marker(),
            "access_mode": _access_mode(),
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


def _run_sweep_and_cache(*, cause_ref: str) -> SweepResult:
    """Run the TTV sweep and refresh proposal cache from the DB."""

    global _last_sweep
    _ = cause_ref
    assert _data_plane is not None and _orch_principal is not None
    sweep = run_time_to_value_sweep(
        _data_plane,
        DEFAULT_TENANT,
        _gate(),
        sweep_principal_id=_orch_principal,
        as_of=_AS_OF,
    )
    _last_sweep = sweep
    _refresh_pending_proposal_cache()
    return sweep


def _refresh_pending_proposal_cache() -> tuple[ActionProposal, ...]:
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
            "ORDER BY created_ts DESC, proposal_id ASC"
        )
        rows = cur.fetchall()
    proposals = tuple(_proposal_from_row(row) for row in rows)
    for proposal in proposals:
        _proposals[proposal.proposal_id] = proposal
    return proposals


def _lookup_proposal(proposal_id: str) -> ActionProposal | None:
    proposal = _proposals.get(proposal_id)
    if proposal is not None:
        return proposal
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
        return None
    proposal = _proposal_from_row(row)
    _proposals[proposal.proposal_id] = proposal
    return proposal


def _proposal_from_row(row) -> ActionProposal:
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


def _seed_demo_refusal_proposals() -> None:
    """Create the two proposals used by the refusal beat in demo mode."""

    if not mcp_demo_operator_enabled():
        return
    assert _data_plane is not None
    gate = _gate()

    cyberdyne = _data_plane.crm.get_account(CYBERDYNE_NO_CONSENT)
    cyberdyne_contact = next(iter(_data_plane.crm.list_contacts(CYBERDYNE_NO_CONSENT)), None)
    if cyberdyne is not None and cyberdyne_contact is not None:
        gate.propose(
            intent="mcp_demo_no_consent_refusal",
            payload={
                "account_id": cyberdyne.account_id,
                "account_name": cyberdyne.name,
                "contact_id": cyberdyne_contact.contact_id,
                "contact_email": cyberdyne_contact.email,
                "subject": "Onboarding activation follow-up",
                "body": "Simulation-only draft that must not be approved without consent.",
                "evidence_ids": [f"health:{cyberdyne.account_id}"],
                "as_of": _AS_OF,
                "source": "sim",
            },
            grounding_ref="mcp-demo:no-consent-refusal",
            **proposal_fields_for("draft_customer_outreach"),
        )

    acme = _data_plane.crm.get_account(ACME_LOGISTICS)
    opportunity = next(iter(_data_plane.crm.list_opportunities(ACME_LOGISTICS)), None)
    if acme is not None and opportunity is not None:
        gate.propose(
            intent="mcp_demo_held_expansion_refusal",
            payload={
                "account_id": acme.account_id,
                "account_name": acme.name,
                "opportunity_id": opportunity.opportunity_id,
                "opportunity_stage": opportunity.stage_name,
                "as_of": _AS_OF,
                "source": "sim",
            },
            grounding_ref="mcp-demo:held-expansion-refusal",
            **proposal_fields_for("initiate_customer_call"),
        )
    _refresh_pending_proposal_cache()


def _reset_demo_operator_state() -> None:
    for path in (
        _DEMO_STATE_DIR / "outbox.jsonl",
        _DEMO_STATE_DIR / "commit_audit.jsonl",
        _DEMO_STATE_DIR / "tenant_state.json",
    ):
        path.unlink(missing_ok=True)


def _record_session_event(event_type: str, payload: dict[str, object]) -> None:
    if not mcp_demo_operator_enabled():
        return
    _session_events.append({
        "event_type": event_type,
        "payload": payload,
        "claim_boundary": {"sim": True, "live": False},
    })


def _typed_refusal(
    *,
    code: str,
    message: str,
    proposal: ActionProposal | None = None,
    extra: dict[str, object] | None = None,
) -> dict:
    payload: dict[str, object] = {
        "error": message,
        "code": code,
        "refused": True,
    }
    if proposal is not None:
        payload["proposal_id"] = proposal.proposal_id
        payload["action"] = proposal.action
    if extra:
        payload.update(extra)
    _record_session_event("refusal", payload)
    return _with_demo_context(payload, suggested_next=["get_session_ledger", "list_proposals"])


def _expansion_approval_blockers(proposal: ActionProposal) -> tuple[dict[str, object], ...]:
    if proposal.action != "initiate_customer_call":
        return ()
    account_id = proposal.payload.get("account_id")
    if not isinstance(account_id, str):
        return ({"blocking_ref": "proposal:missing_account_id", "reason": "missing account_id"},)
    return _expansion_blockers(account_id)


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Ultra CSM",
    instructions=(
        "Ultra CSM is a customer-success management system. In demo-operator "
        "mode, start with get_morning_briefing, inspect evidence before "
        "submitting any verdict, use revise only with a plain-English edit "
        "instruction, and treat all outbound receipts as simulation artifacts. "
        "In read-only mode, use tools only to inspect accounts and holds."
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
        "name": "get_morning_briefing",
        "classification": "read",
        "readonly_available": False,
    },
    {
        "name": "get_next_steps",
        "classification": "read",
        "readonly_available": True,
    },
    {
        "name": "get_session_ledger",
        "classification": "read",
        "readonly_available": False,
    },
    {
        "name": "report_readiness",
        "classification": "state_changing",
        "readonly_available": False,
    },
    {
        "name": "ingest_book",
        "classification": "state_changing",
        "readonly_available": False,
    },
    {
        "name": "confirm_book_mappings",
        "classification": "state_changing",
        "readonly_available": False,
    },
    {
        "name": "ingest_table",
        "classification": "state_changing",
        "readonly_available": False,
    },
    {
        "name": "confirm_book",
        "classification": "state_changing",
        "readonly_available": False,
    },
    {
        "name": "render_email_draft",
        "classification": "state_changing",
        "readonly_available": False,
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

    return _with_demo_context({
        "access_mode": _access_mode(),
        "read_only_env": _READONLY_ENV,
        "demo_operator_env": _DEMO_OPERATOR_ENV,
        "tools": [dict(tool) for tool in MCP_TOOL_AUDIT],
    }, suggested_next=["get_morning_briefing", "get_next_steps"])


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
        return _with_demo_context(
            _score_one_account(account_id, data_plane=_data_plane, as_of=_AS_OF),
            suggested_next=["get_account_brief", "list_proposals"],
        )
    except AccountDataError as exc:
        return _with_demo_context(
            {"error": str(exc), "code": exc.code, "account_id": exc.account_id}
        )


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

    return _with_demo_context({
        "tenant_id": DEFAULT_TENANT,
        "account_count": len(results),
        "accounts": results,
    }, suggested_next=["score_account", "get_account_brief", "list_proposals"])


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
        return _with_demo_context(
            _build_account_brief(account_id, data_plane=_data_plane, as_of=_AS_OF),
            suggested_next=["list_proposals", "submit_verdict"],
        )
    except AccountDataError as exc:
        return _with_demo_context(
            {"error": str(exc), "code": exc.code, "account_id": exc.account_id}
        )


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
        return _with_demo_context({
            "error": f"Account {account_id} not found",
            "code": "ACCOUNT_NOT_FOUND",
            "account_id": account_id,
        })

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
    return _with_demo_context({
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
    }, suggested_next=["list_proposals", "get_session_ledger"])


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
        return _with_demo_context({
            "error": f"Account {account_id} not found",
            "code": "ACCOUNT_NOT_FOUND",
            "account_id": account_id,
        })

    store = _fixture_trajectory_store(account.account_id)
    trajectory = store.build_trajectory(account.account_id, window_days=window_days)
    return _with_demo_context({
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
    }, suggested_next=["get_account_brief", "get_hold_status"])


@mcp.tool()
def get_morning_briefing() -> dict:
    """Return the demo operator's first screen for the simulated morning."""

    if mcp_readonly_enabled():
        return _readonly_refusal("get_morning_briefing")
    if _last_sweep is None:
        _run_sweep_and_cache(cause_ref="mcp:morning_briefing")

    assert _last_sweep is not None and _data_plane is not None
    pending = _refresh_pending_proposal_cache()
    pending_sorted = sorted(
        pending,
        key=lambda proposal: (
            proposal.intent,
            proposal.action,
            str(proposal.payload.get("account_name", "")),
            str(proposal.payload.get("account_id", "")),
        ),
    )
    sweep = _last_sweep.to_dict()
    work_items = list(sweep.get("work_items", []))
    stalled_arr_cents = 0
    for item in work_items:
        account_id = item.get("account_id")
        if isinstance(account_id, str):
            company = _data_plane.cs.get_company(account_id)
            if company is not None:
                stalled_arr_cents += int(company.arr_cents)

    held_accounts = [
        account.account_id
        for account in _data_plane.crm.list_accounts(tenant_id=DEFAULT_TENANT)
        if _expansion_blockers(account.account_id)
        and _data_plane.crm.list_opportunities(account.account_id)
    ]
    briefing = {
        "tenant_id": DEFAULT_TENANT,
        "as_of": _AS_OF,
        "headline": {
            "accounts_need_you_today": len(work_items),
            "identity_escalations": len(sweep.get("escalations", [])),
            "drafts_awaiting_verdict": sum(
                1 for proposal in pending if proposal.action == "draft_customer_outreach"
            ),
            "held_customer_facing_expansions": len(held_accounts),
            "stalled_arr_cents": stalled_arr_cents,
        },
        "top_work_items": work_items[:5],
        "pending_proposals": [
            {
                "proposal_id": proposal.proposal_id,
                "intent": proposal.intent,
                "action": proposal.action,
                "account_id": proposal.payload.get("account_id"),
                "account_name": proposal.payload.get("account_name"),
                "autonomy_tier": proposal.autonomy_tier,
            }
            for proposal in pending_sorted[:5]
        ],
        "operator_script": [
            "Inspect a proposed draft with list_proposals and get_account_brief.",
            "Use submit_verdict with verdict='revise' for one bounded edit.",
            "Approve the revised draft to write a simulation receipt.",
            "Try approving a held or no-consent action to see the refusal.",
            "End with get_session_ledger.",
        ],
    }
    return _with_demo_context(
        briefing,
        suggested_next=["list_proposals", "get_account_brief", "submit_verdict"],
    )


@mcp.tool()
def get_next_steps() -> dict:
    """Return the operator-demo script and credential boundary."""

    return _with_demo_context({
        "mode": _access_mode(),
        "steps": [
            "Run get_morning_briefing for the current simulated book.",
            "Use list_proposals to choose a pending draft.",
            "Use get_account_brief before approving or revising.",
            "Use submit_verdict with revise plus edit_instruction once.",
            "Approve the superseding draft and inspect get_session_ledger.",
            "Render the approved email draft artifact; it is placement-ready but never sent.",
            "For a host-relayed book, restart without demo/read-only mode and use "
            "report_readiness, ingest_book, then confirm_book_mappings.",
            "For a normalized multi-table CRM, use ingest_table per table, "
            "then confirm_book.",
        ],
        "credential_boundary": (
            "This demo uses simulated data and local no-auth approval only when "
            f"{_DEMO_OPERATOR_ENV}=1. Live tenants must use mapped API tokens."
        ),
        "outbox": str(_DEMO_STATE_DIR / "outbox.jsonl"),
        "bring_your_own_book": {
            "docs": "QUICKSTART.md#bring-your-own-book",
            "tools": [
                "report_readiness",
                "ingest_book",
                "confirm_book_mappings",
                "ingest_table",
                "confirm_book",
            ],
            "claim_boundary": _relay_claim_boundary(),
        },
    }, suggested_next=["get_morning_briefing", "list_proposals"])


@mcp.tool()
def get_session_ledger() -> dict:
    """Read the current demo-operator session ledger."""

    if mcp_readonly_enabled():
        return _readonly_refusal("get_session_ledger")

    receipts = []
    if (_DEMO_STATE_DIR / "commit_audit.jsonl").exists():
        for line in (_DEMO_STATE_DIR / "commit_audit.jsonl").read_text(
            encoding="utf-8"
        ).splitlines():
            if line.strip():
                receipts.append(json.loads(line))
    return _with_demo_context({
        "tenant_id": DEFAULT_TENANT,
        "events": list(_session_events),
        "event_count": len(_session_events),
        "receipt_count": len(receipts),
        "receipts": receipts,
        "not_a_compliance_assessment": True,
    }, suggested_next=["get_next_steps"])


@mcp.tool()
def report_readiness(sources: list[str] | None = None) -> dict:
    """Report what a host-declared relay source set can support."""

    refusal = _relay_tool_available("report_readiness")
    if refusal is not None:
        return refusal

    source_set = _normalize_sources(sources or [])
    checklist = {
        "crm": {
            "declared": "crm" in source_set,
            "enables": [
                "account identity",
                "contacts",
                "opportunities",
                "minimum viable relay book",
            ],
            "missing_if_absent": "cannot build the minimum account book",
        },
        "email": {
            "declared": "email" in source_set,
            "enables": ["host-placed drafts"],
            "missing_if_absent": "ultra-csm can return draft content but cannot place it",
        },
        "telemetry": {
            "declared": "telemetry" in source_set,
            "enables": ["usage and adoption rails"],
            "missing_if_absent": "value-model usage rails remain unknown",
        },
    }
    missing = [name for name, item in checklist.items() if not item["declared"]]
    minimum_ok = bool(checklist["crm"]["declared"])
    return {
        "claim_boundary": _relay_claim_boundary(),
        "declared_sources": sorted(source_set),
        "minimum_viable_book": {
            "requires": ["crm"],
            "ready": minimum_ok,
        },
        "checklist": checklist,
        "missing_sources": missing,
        "degradation": (
            "CRM-only relay can establish account context, but health, adoption, "
            "outcome, and telemetry rails remain unknown until those sources are relayed."
        ),
        "routes": {
            "nothing_connected": (
                "Use ULTRA_CSM_DEMO_OPERATOR=1 and get_morning_briefing for the "
                "sim morning when no host sources are connected."
            ),
            "next_tool": "ingest_book" if minimum_ok else None,
            "multi_table_next_tool": "ingest_table" if minimum_ok else None,
            "multi_table": (
                "A normalized CRM (separate Account/Contact/Opportunity tables) "
                "relays each table with ingest_table, then confirm_book joins "
                "them by confirmed foreign keys."
            ),
        },
    }


@mcp.tool()
def ingest_book(
    records: list[dict[str, Any]],
    source_descriptor: dict[str, Any] | None,
    expected_count: int | None,
    session_id: str | None = None,
    final_chunk: bool = True,
) -> dict:
    """Ingest host-relayed raw records and return a confirmation proposal."""

    refusal = _relay_tool_available("ingest_book")
    if refusal is not None:
        return refusal
    if expected_count is None:
        return _relay_refusal(
            "EXPECTED_COUNT_REQUIRED",
            "ingest_book requires expected_count so truncation and count mismatch are visible.",
            "ingest_book",
        )
    if expected_count < 0:
        return _relay_refusal(
            "EXPECTED_COUNT_INVALID",
            "expected_count must be zero or greater.",
            "ingest_book",
            expected_count=expected_count,
        )
    if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
        return _relay_refusal(
            "RELAY_RECORDS_INVALID",
            "records must be a list of JSON objects.",
            "ingest_book",
        )

    descriptor = _relay_descriptor(source_descriptor or {}, expected_count=expected_count)
    session = _relay_session(session_id, descriptor=descriptor, expected_count=expected_count)
    if session.expected_count != expected_count:
        return _relay_refusal(
            "EXPECTED_COUNT_CHANGED",
            "expected_count must remain stable across chunks for a relay session.",
            "ingest_book",
            session_id=session.session_id,
            existing_expected_count=session.expected_count,
            supplied_expected_count=expected_count,
        )

    _append_relay_records(session, records)
    if not final_chunk:
        return {
            "claim_boundary": _relay_claim_boundary(),
            "session_id": session.session_id,
            "accepted_chunk": True,
            "received_count": session.received_count,
            "stored_count": len(session.raw_records),
            "expected_count": session.expected_count,
            "truncated": session.dropped_record_count > 0,
            "dropped_record_count": session.dropped_record_count,
            "next": "send the next chunk with the same session_id",
        }

    if session.received_count != session.expected_count:
        return _relay_refusal(
            "RELAY_COUNT_MISMATCH",
            "received record count does not match expected_count; refusing to freeze a partial book.",
            "ingest_book",
            session_id=session.session_id,
            received_count=session.received_count,
            expected_count=session.expected_count,
            stored_count=len(session.raw_records),
            truncated=session.dropped_record_count > 0,
            dropped_record_count=session.dropped_record_count,
        )

    _snapshot, proposal, unrepresentable = propose_external_source_mapping(
        session.raw_records,
        session.descriptor,
    )
    session.proposal = proposal
    return {
        "claim_boundary": _relay_claim_boundary(),
        "session_id": session.session_id,
        "received_count": session.received_count,
        "stored_count": len(session.raw_records),
        "expected_count": session.expected_count,
        "truncated": session.dropped_record_count > 0,
        "dropped_record_count": session.dropped_record_count,
        "raw_input_sha256": _raw_records_hash(session.raw_records),
        "unrepresentable_paths": list(unrepresentable),
        "mapping_proposal": proposal.to_dict(),
        "confirmation_questions": _confirmation_questions(proposal),
        "next_tool": "confirm_book_mappings",
    }


@mcp.tool()
def confirm_book_mappings(
    confirmations: dict[str, Any],
    session_id: str | None = None,
) -> dict:
    """Freeze relay mappings, transform the relayed book, and return a briefing."""

    refusal = _relay_tool_available("confirm_book_mappings")
    if refusal is not None:
        return refusal
    session = _selected_relay_session(session_id)
    if session is None:
        return _relay_refusal(
            "RELAY_SESSION_NOT_FOUND",
            "No relay session with a mapping proposal is available.",
            "confirm_book_mappings",
            session_id=session_id,
        )
    if session.proposal is None:
        return _relay_refusal(
            "RELAY_PROPOSAL_REQUIRED",
            "Run ingest_book through the final chunk before confirming mappings.",
            "confirm_book_mappings",
            session_id=session.session_id,
        )

    try:
        parsed = _mapping_confirmations_from_tool(confirmations)
        frozen = freeze_confirmed_source_map(session.proposal, confirmations=parsed)
    except ValueError as exc:
        return _relay_refusal(
            "RELAY_CONFIRMATION_INVALID",
            str(exc),
            "confirm_book_mappings",
            session_id=session.session_id,
        )

    first = _relay_replay_payload(session, frozen)
    second = _relay_replay_payload(session, frozen)
    if first != second:
        return _relay_refusal(
            "RELAY_REPLAY_NONDETERMINISTIC",
            "Recorded raw inputs plus frozen map did not replay deterministically.",
            "confirm_book_mappings",
            session_id=session.session_id,
        )
    replay_sha = _json_sha256(first)
    session.frozen_config_hash = frozen.config_hash
    session.replay_sha256 = replay_sha
    first.update({
        "claim_boundary": _relay_claim_boundary(),
        "session_id": session.session_id,
        "replay_sha256": replay_sha,
    })
    return first


@mcp.tool()
def ingest_table(
    book_id: str,
    table_name: str,
    contract: str,
    records: list[dict[str, Any]],
    expected_count: int | None,
    field_metadata: dict[str, Any] | None = None,
    final_chunk: bool = True,
) -> dict:
    """Ingest one named table of a relational book and return its open questions.

    A relational book is N tables joined by foreign keys (a normalized CRM);
    call ingest_table once per table (chunk within a table via final_chunk),
    then confirm_book to freeze the mappings and assemble the joined book.
    contract declares what this table's records ARE (CRMAccount, CRMContact,
    or CRMOpportunity); only that contract's open questions come back — other
    contracts' fields are never mapped against this table, because that would
    mint records that do not exist in the source. field_metadata carries
    source-declared schema facts per column, e.g. from a Salesforce describe:
    {"AccountId": {"field_type": "reference", "references": ["Account"],
    "relationship_name": "Account"}}. Declared references drive foreign-key
    mapping directly; identity and value-direction decisions always remain
    human.
    """

    refusal = _relay_tool_available("ingest_table")
    if refusal is not None:
        return refusal
    if not isinstance(book_id, str) or not book_id.strip():
        return _relay_refusal(
            "RELAY_BOOK_ID_REQUIRED",
            "ingest_table requires a non-empty book_id naming the relational book.",
            "ingest_table",
        )
    if not isinstance(table_name, str) or not table_name.strip():
        return _relay_refusal(
            "RELAY_TABLE_NAME_REQUIRED",
            "ingest_table requires a non-empty table_name.",
            "ingest_table",
            book_id=book_id,
        )
    known_contracts = CONNECTOR_SPECS[_EXTERNAL_CONNECTOR_ID].source_contracts
    if contract not in known_contracts:
        return _relay_refusal(
            "RELAY_CONTRACT_INTENT_INVALID",
            "contract must declare what this table's records are.",
            "ingest_table",
            book_id=book_id,
            table_name=table_name,
            supplied_contract=contract,
            known_contracts=list(known_contracts),
        )
    if expected_count is None:
        return _relay_refusal(
            "EXPECTED_COUNT_REQUIRED",
            "ingest_table requires expected_count so truncation and count mismatch are visible.",
            "ingest_table",
        )
    if expected_count < 0:
        return _relay_refusal(
            "EXPECTED_COUNT_INVALID",
            "expected_count must be zero or greater.",
            "ingest_table",
            expected_count=expected_count,
        )
    if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
        return _relay_refusal(
            "RELAY_RECORDS_INVALID",
            "records must be a list of JSON objects.",
            "ingest_table",
        )
    if field_metadata is not None and (
        not isinstance(field_metadata, dict)
        or any(not isinstance(value, dict) for value in field_metadata.values())
    ):
        return _relay_refusal(
            "RELAY_FIELD_METADATA_INVALID",
            "field_metadata must map column names to metadata objects.",
            "ingest_table",
        )

    book = _relational_books.setdefault(book_id, {})
    session = book.get(table_name)
    if session is None:
        claimed_by = next(
            (
                name for name, table in book.items()
                if table.contract == contract
            ),
            None,
        )
        if claimed_by is not None:
            return _relay_refusal(
                "RELAY_CONTRACT_INTENT_INVALID",
                f"contract {contract} is already declared by table {claimed_by}; "
                "each contract may be declared by at most one table per book.",
                "ingest_table",
                book_id=book_id,
                table_name=table_name,
            )
        session = _RelaySession(
            session_id=f"{book_id}:{table_name}",
            descriptor=ExternalSourceDescriptor(
                source_name="mcp_relay",
                expected_count=expected_count,
                object_name=table_name,
            ),
            expected_count=expected_count,
            field_metadata=field_metadata,
            contract=contract,
        )
        book[table_name] = session
    if session.contract != contract:
        return _relay_refusal(
            "RELAY_CONTRACT_CHANGED",
            "contract must remain stable across chunks for a table.",
            "ingest_table",
            book_id=book_id,
            table_name=table_name,
            existing_contract=session.contract,
            supplied_contract=contract,
        )
    if session.expected_count != expected_count:
        return _relay_refusal(
            "EXPECTED_COUNT_CHANGED",
            "expected_count must remain stable across chunks for a table.",
            "ingest_table",
            book_id=book_id,
            table_name=table_name,
            existing_expected_count=session.expected_count,
            supplied_expected_count=expected_count,
        )
    if field_metadata is not None:
        if session.field_metadata is not None and session.field_metadata != field_metadata:
            return _relay_refusal(
                "RELAY_FIELD_METADATA_CHANGED",
                "field_metadata must remain stable across chunks for a table.",
                "ingest_table",
                book_id=book_id,
                table_name=table_name,
            )
        session.field_metadata = field_metadata

    _append_relay_records(session, records)
    if not final_chunk:
        return {
            "claim_boundary": _relay_claim_boundary(),
            "book_id": book_id,
            "table_name": table_name,
            "accepted_chunk": True,
            "received_count": session.received_count,
            "stored_count": len(session.raw_records),
            "expected_count": session.expected_count,
            "truncated": session.dropped_record_count > 0,
            "dropped_record_count": session.dropped_record_count,
            "next": "send the next chunk with the same book_id and table_name",
        }

    if session.received_count != session.expected_count:
        return _relay_refusal(
            "RELAY_COUNT_MISMATCH",
            "received record count does not match expected_count; refusing to freeze a partial table.",
            "ingest_table",
            book_id=book_id,
            table_name=table_name,
            received_count=session.received_count,
            expected_count=session.expected_count,
            stored_count=len(session.raw_records),
            truncated=session.dropped_record_count > 0,
            dropped_record_count=session.dropped_record_count,
        )

    _snapshot, proposal, unrepresentable = propose_external_source_mapping(
        session.raw_records,
        session.descriptor,
        session.field_metadata,
    )
    session.proposal = proposal
    prefix = f"{contract}."
    _intent_proposal, demoted, _synthesized = _apply_contract_intent(proposal, contract)
    return {
        "claim_boundary": _relay_claim_boundary(),
        "book_id": book_id,
        "table_name": table_name,
        "contract": contract,
        "received_count": session.received_count,
        "stored_count": len(session.raw_records),
        "expected_count": session.expected_count,
        "truncated": session.dropped_record_count > 0,
        "dropped_record_count": session.dropped_record_count,
        "raw_input_sha256": _raw_records_hash(session.raw_records),
        "unrepresentable_paths": list(unrepresentable),
        "auto_mapped": [
            entry for entry in _auto_map_summary(proposal)
            if entry["key"].startswith(prefix)
        ],
        "confirmation_questions": [
            question for question in _confirmation_questions(proposal)
            if question["key"].startswith(prefix)
        ],
        "declared_not_mappable": demoted,
        "book_tables": sorted(book),
        "next_tool": "confirm_book",
    }


@mcp.tool()
def confirm_book(
    book_id: str,
    confirmations: dict[str, Any] | None = None,
) -> dict:
    """Freeze a relational book's mappings, join its tables, and return a briefing.

    Each table holds one contract's records (declared at ingest_table time):
    any other contract's proposals on a table are recorded as not_mappable and
    declared in the response. confirmations is keyed by table name, then by
    question key, in the same shape confirm_book_mappings accepts.
    """

    refusal = _relay_tool_available("confirm_book")
    if refusal is not None:
        return refusal
    book = _relational_books.get(book_id or "")
    if book is None:
        return _relay_refusal(
            "RELAY_BOOK_NOT_FOUND",
            "No relational book with this book_id; run ingest_table first.",
            "confirm_book",
            book_id=book_id,
        )
    pending = sorted(name for name, table in book.items() if table.proposal is None)
    if pending:
        return _relay_refusal(
            "RELAY_PROPOSAL_REQUIRED",
            "Run ingest_table through the final chunk for every table before confirming.",
            "confirm_book",
            book_id=book_id,
            pending_tables=pending,
        )
    confirmations = confirmations or {}
    if not isinstance(confirmations, dict):
        return _relay_refusal(
            "RELAY_CONFIRMATION_INVALID",
            "confirmations must be keyed by table name.",
            "confirm_book",
            book_id=book_id,
        )
    unknown_tables = sorted(set(confirmations) - set(book))
    if unknown_tables:
        return _relay_refusal(
            "RELAY_CONFIRMATION_INVALID",
            "confirmations name tables that are not part of this book.",
            "confirm_book",
            book_id=book_id,
            unknown_tables=unknown_tables,
        )

    frozen_by_table: dict[str, Any] = {}
    declared_not_mappable: dict[str, list[str]] = {}
    for name in sorted(book):
        contract = book[name].contract
        assert contract is not None
        try:
            parsed = _mapping_confirmations_from_tool(
                confirmations.get(name, {}) or {}
            )
        except ValueError as exc:
            return _relay_refusal(
                "RELAY_CONFIRMATION_INVALID",
                str(exc),
                "confirm_book",
                book_id=book_id,
                table_name=name,
            )
        conflicts = sorted(
            key for key, confirmation in parsed.items()
            if confirmation.contract != contract
        )
        if conflicts:
            return _relay_refusal(
                "RELAY_CONTRACT_INTENT_CONFLICT",
                (
                    f"table {name} is declared {contract}; confirming another "
                    "contract's fields against it would mint records that do "
                    "not exist in the source."
                ),
                "confirm_book",
                book_id=book_id,
                table_name=name,
                conflicting_keys=conflicts,
            )
        session = book[name]
        assert session.proposal is not None
        intent_proposal, not_mappable, synthesized = _apply_contract_intent(
            session.proposal, contract
        )
        declared_not_mappable[name] = not_mappable
        try:
            frozen = freeze_confirmed_source_map(
                intent_proposal,
                confirmations={**synthesized, **parsed},
            )
        except ValueError as exc:
            return _relay_refusal(
                "RELAY_CONFIRMATION_INVALID",
                str(exc),
                "confirm_book",
                book_id=book_id,
                table_name=name,
            )
        frozen_by_table[name] = frozen

    first = _relational_replay_payload(book, frozen_by_table)
    second = _relational_replay_payload(book, frozen_by_table)
    if first != second:
        return _relay_refusal(
            "RELAY_REPLAY_NONDETERMINISTIC",
            "Recorded raw inputs plus frozen maps did not replay deterministically.",
            "confirm_book",
            book_id=book_id,
        )
    replay_sha = _json_sha256(first)
    for name, session in book.items():
        session.frozen_config_hash = frozen_by_table[name].config_hash
        session.replay_sha256 = replay_sha
    first.update({
        "claim_boundary": _relay_claim_boundary(),
        "book_id": book_id,
        "table_contracts": {name: book[name].contract for name in sorted(book)},
        "declared_not_mappable": declared_not_mappable,
        "book_has_parent": any(
            mapping.contract == "CRMAccount" and mapping.internal_field == "account_id"
            for frozen in frozen_by_table.values()
            for mapping in frozen.mappings
        ),
        "replay_sha256": replay_sha,
    })
    return first


@mcp.tool()
def render_email_draft(
    proposal_id: str | None = None,
    proposal: dict[str, Any] | None = None,
    approved_payload_sha256: str | None = None,
) -> dict:
    """Render a placement-ready draft artifact from an approved proposal."""

    if mcp_readonly_enabled():
        return _readonly_refusal("render_email_draft")
    try:
        if proposal_id:
            stored = _lookup_proposal(proposal_id)
            if stored is None:
                return _with_demo_context({
                    "error": f"Proposal {proposal_id} not found",
                    "code": "PROPOSAL_NOT_FOUND",
                    "proposal_id": proposal_id,
                })
            artifact = render_email_draft_from_proposal(
                stored,
                approved_payload_sha256=approved_payload_sha256,
            )
        elif proposal is not None:
            payload = proposal.get("payload")
            if not isinstance(payload, dict):
                raise EmailDraftError("proposal payload must be an object")
            artifact = render_email_draft_from_payload(
                proposal_id=str(proposal.get("proposal_id") or "host-approved-draft"),
                action=str(proposal.get("action") or ""),
                status=str(proposal.get("status") or ""),
                payload=payload,
                payload_sha256=str(proposal.get("payload_sha256") or ""),
                approved_payload_sha256=approved_payload_sha256,
            )
        else:
            raise EmailDraftError("proposal_id or proposal is required")
    except EmailDraftError as exc:
        return _with_demo_context({
            "error": str(exc),
            "code": "EMAIL_DRAFT_REFUSED",
            "claim_boundary": {"draft_never_send": True},
        })

    payload = artifact.to_dict()
    payload["tool"] = "render_email_draft"
    _record_session_event("email_draft_rendered", {
        "proposal_id": artifact.proposal_id,
        "payload_sha256": artifact.payload_sha256,
        "draft_never_send": True,
    })
    return _with_demo_context(
        payload,
        suggested_next=["get_session_ledger", "list_proposals"],
    )


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

    sweep = _run_sweep_and_cache(cause_ref="mcp:run_sweep")
    return _with_demo_context(
        sweep.to_dict(),
        suggested_next=["list_proposals", "get_morning_briefing"],
    )


@mcp.tool()
def list_proposals() -> dict:
    """List all pending action proposals from the most recent sweep.

    Returns proposals that are awaiting a human verdict (approve or deny).
    Run the sweep first if no proposals exist.
    """
    if mcp_readonly_enabled():
        return _with_demo_context({
            "tenant_id": _TENANT_ID,
            "pending_count": 0,
            "proposals": [],
            "note": (
                "read-only mode never runs a sweep, so no proposals ever exist "
                "here — this is not an error. Restart without "
                f"{_READONLY_ENV}=1 and call run_sweep to generate real ones."
            ),
        })

    proposals = []
    for proposal in _refresh_pending_proposal_cache():
        proposals.append({
            "proposal_id": proposal.proposal_id,
            "intent": proposal.intent,
            "action": proposal.action,
            "payload": proposal.payload,
            "autonomy_tier": proposal.autonomy_tier,
            "required_permission": proposal.required_permission,
            "status": proposal.status,
        })

    return _with_demo_context({
        "tenant_id": _TENANT_ID,
        "pending_count": len(proposals),
        "proposals": proposals,
    }, suggested_next=["get_account_brief", "submit_verdict"])


@mcp.tool()
def submit_verdict(
    proposal_id: str,
    verdict: str,
    reason: str,
    token: str | None = None,
    edit_instruction: str | None = None,
) -> dict:
    """Submit a human verdict on a pending action proposal.

    Approves or denies a proposal that was created during a sweep.
    The verdict transitions the proposal to its terminal state.

    Args:
        proposal_id: The UUID of the proposal to judge.
        verdict: One of "approve", "deny", or "revise".
        reason: Human-readable rationale for the decision.
        token: API token mapped by ULTRA_CSM_API_TOKENS to the approving human.
        edit_instruction: Required for verdict="revise"; ignored otherwise.
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
        return _with_demo_context({"error": str(exc), "code": exc.code})

    if verdict not in ("approve", "deny", "revise"):
        return _with_demo_context({
            "error": f"Invalid verdict '{verdict}'. Must be approve, deny, or revise.",
            "code": "INVALID_VERDICT",
        })

    proposal = _lookup_proposal(proposal_id)
    if proposal is None:
        return _with_demo_context({
            "error": f"Proposal {proposal_id} not found",
            "code": "PROPOSAL_NOT_FOUND",
            "proposal_id": proposal_id,
        })

    if proposal.status != "pending":
        return _with_demo_context({
            "error": f"Proposal {proposal_id} is already '{proposal.status}', "
            f"cannot apply verdict.",
            "code": "ALREADY_VERDICTED",
            "proposal_id": proposal_id,
        })

    if verdict == "revise":
        assert _data_plane is not None
        try:
            result = apply_bounded_revise(
                _gate(),
                proposal,
                data_plane=_data_plane,
                tenant_id=DEFAULT_TENANT,
                human_principal_id=auth_principal.principal_id,
                reason=reason,
                edit_instruction=edit_instruction,
                cause_ref=f"mcp:revise:{proposal.proposal_id}",
            )
        except ReviseServiceError as exc:
            return _typed_refusal(
                code=exc.code,
                message=exc.message,
                proposal=proposal,
                extra=exc.to_dict(),
            )
        _proposals.pop(proposal_id, None)
        _refresh_pending_proposal_cache()
        response = result.to_dict()
        response["auth"] = auth_principal.auth
        _record_session_event("verdict_recorded", {
            "proposal_id": proposal_id,
            "verdict": "revise",
            "superseding_proposal_id": result.superseding_proposal_id,
        })
        return _with_demo_context(
            response,
            suggested_next=["list_proposals", "submit_verdict", "get_session_ledger"],
        )

    assert _data_plane is not None
    if verdict == "approve" and not _proposal_has_contact_consent(
        proposal, data_plane=_data_plane,
    ):
        return _typed_refusal(
            code="CONSENT_MISSING",
            message="Customer-facing outreach is blocked because contact consent is missing",
            proposal=proposal,
        )

    blockers = _expansion_approval_blockers(proposal)
    if verdict == "approve" and blockers:
        return _typed_refusal(
            code="PRECEDENCE_HELD",
            message="Proposal is held by current precedence blockers",
            proposal=proposal,
            extra={"blocking_refs": [str(item["blocking_ref"]) for item in blockers]},
        )

    gate = _gate()
    human_verdict = Verdict(
        verdict=verdict,
        human_principal_id=auth_principal.principal_id,
        rationale=reason,
    )

    try:
        outcome = gate.record_verdict(proposal, human_verdict)
    except GateError as exc:
        return _typed_refusal(
            code="GATE_ERROR",
            message=str(exc),
            proposal=proposal,
        )

    # Update cache.
    _proposals.pop(proposal_id, None)
    receipt = None
    crm_receipt = None
    if mcp_demo_operator_enabled() and outcome.authorized and proposal.action == "draft_customer_outreach":
        assert _sim_store is not None
        receipt = SimOutboundCommitter(gate, state_dir=_DEMO_STATE_DIR).commit(
            proposal,
            outcome,
        )
        crm_receipt = SimCrmActivityCommitter(gate, _sim_store).commit(
            proposal,
            outcome,
        )

    _record_session_event("verdict_recorded", {
        "proposal_id": outcome.proposal_id,
        "verdict": outcome.verdict,
        "status": outcome.status,
        "authorized": outcome.authorized,
    })
    if receipt is not None:
        _record_session_event("sim_commit_receipt", {
            "proposal_id": receipt.proposal_id,
            "receipt_id": receipt.receipt_id,
            "target": receipt.target,
            "committed": receipt.committed,
        })

    result = {
        "proposal_id": outcome.proposal_id,
        "status": outcome.status,
        "authorized": outcome.authorized,
        "verdict": outcome.verdict,
        "payload_sha256": outcome.payload_sha256,
        "auth": auth_principal.auth,
    }
    if receipt is not None:
        result["receipt"] = {
            "receipt_id": receipt.receipt_id,
            "target": receipt.target,
            "committed": receipt.committed,
            "dry_run": receipt.dry_run,
        }
    if crm_receipt is not None:
        result["crm_receipt"] = {
            "receipt_id": crm_receipt.receipt_id,
            "target": crm_receipt.target,
            "committed": crm_receipt.committed,
            "dry_run": crm_receipt.dry_run,
        }
    return _with_demo_context(
        result,
        suggested_next=["render_email_draft", "get_session_ledger", "list_proposals"],
    )


def _normalize_sources(sources: list[str]) -> set[str]:
    allowed = {"email", "crm", "telemetry", "none"}
    normalized = {
        str(source).strip().lower()
        for source in sources
        if str(source).strip()
    }
    if not normalized:
        normalized = {"none"}
    if "none" in normalized:
        return {"none"}
    return {source for source in normalized if source in allowed}


def _relay_descriptor(
    payload: Mapping[str, Any],
    *,
    expected_count: int,
) -> ExternalSourceDescriptor:
    source_name = str(payload.get("source_name") or payload.get("name") or "mcp_relay")
    object_name = str(payload.get("object_name") or "records")
    max_records = _bounded_int(payload.get("max_records"), default=_RELAY_MAX_RECORDS)
    max_schema_depth = _bounded_int(payload.get("max_schema_depth"), default=3)
    return ExternalSourceDescriptor(
        source_name=source_name,
        expected_count=expected_count,
        object_name=object_name,
        max_records=max_records,
        max_schema_depth=max_schema_depth,
    )


def _bounded_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0, parsed)


def _relay_session(
    session_id: str | None,
    *,
    descriptor: ExternalSourceDescriptor,
    expected_count: int,
) -> _RelaySession:
    global _last_relay_session_id
    if session_id and session_id in _relay_sessions:
        session = _relay_sessions[session_id]
    else:
        session_id = session_id or f"relay-{len(_relay_sessions) + 1:04d}"
        session = _RelaySession(
            session_id=session_id,
            descriptor=descriptor,
            expected_count=expected_count,
        )
        _relay_sessions[session_id] = session
    _last_relay_session_id = session.session_id
    return session


def _selected_relay_session(session_id: str | None) -> _RelaySession | None:
    if session_id:
        return _relay_sessions.get(session_id)
    if _last_relay_session_id is None:
        return None
    return _relay_sessions.get(_last_relay_session_id)


def _append_relay_records(session: _RelaySession, records: list[dict[str, Any]]) -> None:
    session.received_count += len(records)
    remaining = max(0, session.descriptor.max_records - len(session.raw_records))
    session.raw_records.extend(records[:remaining])
    session.dropped_record_count += max(0, len(records) - remaining)
    session.proposal = None
    session.frozen_config_hash = None
    session.replay_sha256 = None


def _raw_records_hash(records: list[dict[str, Any]]) -> str:
    return _json_sha256({"records": records})


def _json_sha256(payload: object) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _confirmation_questions(proposal: SourceMapProposal) -> list[dict[str, Any]]:
    questions = []
    for entry in proposal.entries:
        if entry.state != "ambiguous_confirm":
            continue
        questions.append({
            "key": entry.key,
            "question": (
                f"Map {entry.key} to one candidate source path, or mark it not_mappable?"
            ),
            "value_direction": entry.value_direction,
            "candidate_keys": [
                {
                    "source_object": candidate.source_object,
                    "source_field": candidate.source_field,
                    "source_path": candidate.source_path,
                    "rows_present": candidate.rows_present,
                    "rows_nonempty": candidate.rows_nonempty,
                    "rows_sampled": candidate.rows_sampled,
                }
                for candidate in entry.candidate_evidence
            ],
        })
    return questions


def _auto_map_summary(proposal: SourceMapProposal) -> list[dict[str, Any]]:
    """Auto-mapped entries, so the host can show provenance without re-asking."""

    return [
        {
            "key": entry.key,
            "source_path": entry.source_path,
            "reason": entry.reason,
            "transform": entry.transform,
        }
        for entry in proposal.entries
        if entry.state == "mapped" and entry.reason.startswith("auto-mapped:")
    ]


def _apply_contract_intent(
    proposal: SourceMapProposal,
    contract: str,
) -> tuple[SourceMapProposal, list[str], dict[str, MappingConfirmation]]:
    """Make the declared contract authoritative for one table.

    Every other contract's entry on this table — auto-mapped or ambiguous — is
    demoted to an explicit not_mappable, because mapping contract X's fields
    onto a table that holds contract Y's records mints records that do not
    exist in the source. Returns the adjusted proposal, the demoted keys (so
    the response can declare them), and the synthesized confirmations.
    """

    entries: list[ProposedFieldMapping] = []
    demoted: list[str] = []
    synthesized: dict[str, MappingConfirmation] = {}
    for entry in proposal.entries:
        if entry.contract != contract and entry.state != "missing_to_unknown":
            if entry.state == "mapped":
                entry = replace(
                    entry,
                    state="ambiguous_confirm",
                    requires_human_confirmation=True,
                )
            demoted.append(entry.key)
            synthesized[entry.key] = MappingConfirmation(
                contract=entry.contract,
                internal_field=entry.internal_field,
                verdict="not_mappable",
            )
        entries.append(entry)
    return replace(proposal, entries=tuple(entries)), sorted(demoted), synthesized


def _relational_replay_payload(
    book: dict[str, _RelaySession],
    frozen_by_table: dict[str, Any],
) -> dict[str, Any]:
    tables = tuple(
        RelationalTable(
            table_name=name,
            records=tuple(book[name].raw_records),
            frozen_map=frozen_by_table[name],
            expected_count=book[name].expected_count,
            field_metadata=book[name].field_metadata,
        )
        for name in sorted(book)
    )
    result = ingest_relational_book(tables)
    scores, score_errors = _score_relay_accounts(result.data)
    return {
        "provenance": "mcp_relay",
        "unverified_mapping": True,
        "sim": False,
        "live": False,
        "typed_counts": {
            "CRMAccount": len(result.data.accounts),
            "CRMContact": len(result.data.contacts),
            "CRMOpportunity": len(result.data.opportunities),
        },
        "tables": {
            name: {
                "received_count": book[name].received_count,
                "stored_count": len(book[name].raw_records),
                "expected_count": book[name].expected_count,
                "truncated": book[name].dropped_record_count > 0,
                "dropped_record_count": book[name].dropped_record_count,
                "raw_input_sha256": _raw_records_hash(book[name].raw_records),
                "frozen_config_hash": frozen_by_table[name].config_hash,
            }
            for name in sorted(book)
        },
        "coverage": result.coverage.to_dict(),
        "briefing": list(result.briefing),
        "score_summary": {
            "scoreable_accounts": len(scores),
            "score_error_count": len(score_errors),
        },
        "scores": scores,
        "score_errors": score_errors,
        "propose_only_actions": _relay_propose_only_actions(result.data),
    }


def _mapping_confirmations_from_tool(
    payload: dict[str, Any],
) -> dict[str, MappingConfirmation]:
    if not isinstance(payload, dict):
        raise ValueError("confirmations must be keyed by field")
    raw_confirmations = payload.get("confirmations", payload)
    if not isinstance(raw_confirmations, dict):
        raise ValueError("confirmations must be keyed by field")
    return {
        str(key): _mapping_confirmation_from_tool(str(key), value)
        for key, value in raw_confirmations.items()
    }


def _mapping_confirmation_from_tool(key: str, payload: Any) -> MappingConfirmation:
    if not isinstance(payload, dict):
        raise ValueError(f"{key} confirmation must be an object")
    contract, internal_field = _split_mapping_key(key, payload)
    verdict = str(payload.get("verdict", "mapped"))
    if verdict == "not_mappable":
        return MappingConfirmation(
            contract=contract,
            internal_field=internal_field,
            verdict="not_mappable",
        )
    if verdict != "mapped":
        raise ValueError(f"{key} verdict must be mapped or not_mappable")
    for required in ("source_object", "source_field", "source_path", "semantic_role"):
        if not isinstance(payload.get(required), str) or not payload[required]:
            raise ValueError(f"{key} mapped confirmation requires {required}")
    return MappingConfirmation(
        contract=contract,
        internal_field=internal_field,
        source_object=str(payload["source_object"]),
        source_field=str(payload["source_field"]),
        source_path=str(payload["source_path"]),
        semantic_role=str(payload["semantic_role"]),
        value_direction=str(payload.get("value_direction") or "not_applicable"),  # type: ignore[arg-type]
        verdict="mapped",
    )


def _split_mapping_key(key: str, payload: Mapping[str, Any]) -> tuple[str, str]:
    if "." in key:
        contract, internal_field = key.split(".", 1)
        return contract, internal_field
    contract = payload.get("contract")
    internal_field = payload.get("internal_field")
    if not isinstance(contract, str) or not isinstance(internal_field, str):
        raise ValueError(f"{key} must include contract and internal_field")
    return contract, internal_field


def _relay_replay_payload(session: _RelaySession, frozen) -> dict[str, Any]:  # noqa: ANN001
    result = ingest_external_book(
        session.raw_records,
        session.descriptor,
        frozen_map=frozen,
    )
    scores, score_errors = _score_relay_accounts(result.data)
    return {
        "provenance": "mcp_relay",
        "unverified_mapping": True,
        "sim": False,
        "live": False,
        "raw_input_sha256": _raw_records_hash(session.raw_records),
        "frozen_config_hash": frozen.config_hash,
        "records": {
            "received_count": session.received_count,
            "stored_count": len(session.raw_records),
            "expected_count": session.expected_count,
            "truncated": session.dropped_record_count > 0,
            "dropped_record_count": session.dropped_record_count,
        },
        "coverage": result.coverage.to_dict(),
        "briefing": list(result.briefing),
        "score_summary": {
            "scoreable_accounts": len(scores),
            "score_error_count": len(score_errors),
        },
        "scores": scores,
        "score_errors": score_errors,
        "propose_only_actions": _relay_propose_only_actions(result.data),
    }


def _score_relay_accounts(data: FixtureCustomerData) -> tuple[list[dict], list[dict]]:
    data_plane = CustomerDataPlane(
        crm=FixtureCRMDataConnector(data=data),
        cs=FixtureCSPlatformConnector(data=data),
        telemetry=FixtureProductTelemetryConnector(data=data),
    )
    scores = []
    errors = []
    for account in data.accounts:
        try:
            score = _score_one_account(
                account.account_id,
                data_plane=data_plane,
                as_of=_AS_OF,
            )
        except AccountDataError as exc:
            errors.append({
                "account_id": account.account_id,
                "code": exc.code,
                "message": str(exc),
            })
            continue
        scores.append(score)
    return scores, errors


def _relay_propose_only_actions(data: FixtureCustomerData) -> list[dict[str, Any]]:
    actions = []
    contacts_by_account: dict[str, list] = {}
    for contact in data.contacts:
        if contact.consent_to_contact:
            contacts_by_account.setdefault(contact.account_id, []).append(contact)
    for account in data.accounts[:3]:
        contacts = contacts_by_account.get(account.account_id, [])
        if not contacts:
            continue
        payload = {
            "account_id": account.account_id,
            "account_name": account.name,
            "contact_id": contacts[0].contact_id,
            "contact_email": contacts[0].email,
            "subject": "Customer-success follow-up",
            "body": (
                "Draft only. Review this in the host email client before placement; "
                "ultra-csm has not delivered anything."
            ),
        }
        payload_sha256 = canonical_payload_sha256(payload)
        actions.append({
            "type": "email_draft",
            "propose_only": True,
            "proposal_id": f"relay-draft:{account.account_id}",
            "action": "draft_customer_outreach",
            "status": "needs_host_approval",
            "payload": payload,
            "payload_sha256": payload_sha256,
            "account_id": account.account_id,
            "contact_id": contacts[0].contact_id,
            "contact_email": contacts[0].email,
            "subject": payload["subject"],
            "body": payload["body"],
            "placement": "host_may_create_draft_in_user_mail_client",
            "claim_boundary": {"draft_never_send": True},
            "live_send_performed": False,
        })
    return actions


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
