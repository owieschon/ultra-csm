"""Shared API/MCP helpers for scoring, briefs, and operator auth."""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import os
from dataclasses import asdict, dataclass
from typing import Any

from ultra_csm._util import iso_date
from ultra_csm.agent1.sweep import _person_layer_inputs
from ultra_csm.data_plane import CustomerDataPlane
from ultra_csm.governance import ActionProposal
from ultra_csm.governance import ROLE_CS_ORCHESTRATOR as CSM_APPROVAL_ROLE
from ultra_csm.governance import role_id
from ultra_csm.person_factors import new_stakeholder_unengaged
from ultra_csm.platform.db import session
from ultra_csm.platform.seed import det_uuid
from ultra_csm.value_model import (
    account_attributes,
    build_customer_value_model,
    load_value_model_config,
    project_ttv_lens,
    resolve_thresholds,
)

log = logging.getLogger(__name__)


class AccountDataError(Exception):
    """Base exception for account helper lookups."""

    def __init__(self, message: str, *, code: str, account_id: str) -> None:
        super().__init__(message)
        self.code = code
        self.account_id = account_id


class AccountNotFoundError(AccountDataError):
    def __init__(self, account_id: str) -> None:
        super().__init__(
            f"Account {account_id} not found in CRM",
            code="ACCOUNT_NOT_FOUND",
            account_id=account_id,
        )


class MissingCSDataError(AccountDataError):
    def __init__(self, account_id: str) -> None:
        super().__init__(
            f"Missing CS platform data for account {account_id}",
            code="MISSING_CS_DATA",
            account_id=account_id,
        )


@dataclass(frozen=True)
class AuthPrincipal:
    """Authenticated human principal used to sign state-changing work."""

    principal_id: str
    display_name: str
    auth: str
    demo_noauth: bool = False


class AuthError(Exception):
    """Bearer-token auth failed before a mutating operation."""

    def __init__(self, *, code: str, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def parse_api_tokens(raw: str | None = None) -> dict[str, str]:
    """Parse ULTRA_CSM_API_TOKENS into token -> display_name."""

    token_map: dict[str, str] = {}
    source = os.environ.get("ULTRA_CSM_API_TOKENS", "") if raw is None else raw
    for chunk in source.split(","):
        item = chunk.strip()
        if not item:
            continue
        if ":" not in item:
            log.warning(
                "api_token_config_invalid",
                extra={"reason": "missing_colon", "entry_length": len(item)},
            )
            continue
        token, display_name = item.split(":", 1)
        token = token.strip()
        display_name = display_name.strip()
        if not token or not display_name:
            log.warning(
                "api_token_config_invalid",
                extra={"reason": "empty_token_or_display_name"},
            )
            continue
        token_map[token] = display_name
    return token_map


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def demo_noauth_enabled() -> bool:
    return (
        _truthy(os.environ.get("ULTRA_CSM_DEMO_NOAUTH"))
        or _truthy(os.environ.get("ULTRA_CSM_DEMO_OPERATOR"))
    )


def assert_demo_noauth_loopback(bind_host: str | None = None) -> None:
    """Fail closed if demo no-auth is enabled on a non-loopback bind host."""
    if not demo_noauth_enabled():
        return
    host = (bind_host if bind_host is not None else os.environ.get("ULTRA_CSM_BIND_HOST"))
    host = (host or "").strip()
    if not host:
        raise RuntimeError(
            "ULTRA_CSM_DEMO_NOAUTH may only boot on a loopback bind host; "
            "got unset/empty bind host. Use HOST=127.0.0.1 or disable demo no-auth."
        )
    normalized = host[1:-1] if host.startswith("[") and host.endswith("]") else host
    if normalized == "localhost":
        return
    try:
        if ipaddress.ip_address(normalized).is_loopback:
            return
    except ValueError:
        pass
    raise RuntimeError(
        "ULTRA_CSM_DEMO_NOAUTH may only boot on a loopback bind host; "
        f"got {host!r}. Use HOST=127.0.0.1 or disable demo no-auth."
    )


def auth_marker() -> str:
    return "demo-noauth" if demo_noauth_enabled() else "bearer-token"


def bearer_token_from_authorization(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def resolve_write_principal(
    conn,
    *,
    tenant_id: str,
    actor_id: str,
    now,
    authorization: str | None = None,
    token: str | None = None,
) -> AuthPrincipal:
    """Resolve a mutating request to a human principal or fail closed."""

    presented = token or bearer_token_from_authorization(authorization)
    if presented is None:
        if demo_noauth_enabled():
            principal_id = _ensure_human_principal(
                conn,
                tenant_id=tenant_id,
                actor_id=actor_id,
                display_name="csm-demo-approval-operator",
                stable_key="demo-noauth",
                now=now,
            )
            return AuthPrincipal(
                principal_id=principal_id,
                display_name="csm-demo-approval-operator",
                auth="demo-noauth",
                demo_noauth=True,
            )
        raise AuthError(code="AUTH_REQUIRED", message="Bearer token required")

    display_name = parse_api_tokens().get(presented)
    if display_name is None:
        raise AuthError(code="AUTH_INVALID", message="Unknown bearer token")

    token_hash = hashlib.sha256(presented.encode("utf-8")).hexdigest()
    principal_id = _ensure_human_principal(
        conn,
        tenant_id=tenant_id,
        actor_id=actor_id,
        display_name=display_name,
        stable_key=f"api-token:{token_hash}",
        now=now,
    )
    return AuthPrincipal(
        principal_id=principal_id,
        display_name=display_name,
        auth="bearer-token",
    )


def _ensure_human_principal(
    conn,
    *,
    tenant_id: str,
    actor_id: str,
    display_name: str,
    stable_key: str,
    now,
) -> str:
    principal_id = det_uuid("principal", tenant_id, stable_key)
    with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=now) as cur:
        cur.execute(
            "INSERT INTO principal (principal_id, tenant_id, kind, display_name) "
            "VALUES (%s, %s, 'human', %s) "
            "ON CONFLICT (principal_id) DO UPDATE "
            "SET display_name = EXCLUDED.display_name",
            (principal_id, tenant_id, display_name),
        )
        cur.execute(
            "INSERT INTO grant_ (principal_id, role_id, tenant_id) "
            "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (principal_id, role_id(CSM_APPROVAL_ROLE), tenant_id),
        )
    return principal_id


def sync_demo_accounts_to_postgres(conn, *, tenant_id: str, actor_id: str, now) -> int:
    """Mirror every fictional CRM account the demo can show into
    Postgres's ``account`` table, keyed by the SAME deterministic
    account_id the fixture books already generate (``account_id_for``/
    ``det_id`` -- stable across every ephemeral cluster boot, since
    neither book has randomness).

    Without this, the comms confirm/ingest pipeline (comms_mapping.py)
    can only be exercised against manually-seeded test accounts, never
    the actual accounts /accounts and the account-detail UI show --
    every write into comms_source_mapping/internal_note/
    communication_signal has an account_id FK into this table.

    TWO disjoint books need syncing (verified: zero account_id overlap),
    because ``GET /accounts`` serves a DIFFERENT book depending on the
    ``day`` query param (``_data_plane_for_day`` in api.py): no ``day`` ->
    the persistent 9-account ``build_sweep_fixture_data_plane`` book;
    ``day=N`` -> the 181-account ``build_synthetic_book`` book (the
    account SET is identical across every simulated day -- simulate_book
    mutates account VALUES, never the account list -- so one sync per
    book at boot covers every day the UI can request).

    Returns the number of accounts synced."""

    from ultra_csm.data_plane import build_sweep_fixture_data_plane, DEFAULT_TENANT
    from ultra_csm.data_plane.synthetic_book import build_synthetic_book

    accounts = list(build_synthetic_book().accounts)
    accounts += build_sweep_fixture_data_plane().crm.list_accounts(tenant_id=DEFAULT_TENANT)

    with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=now) as cur:
        for account in accounts:
            cur.execute(
                "INSERT INTO account (account_id, tenant_id, name) VALUES (%s, %s, %s) "
                "ON CONFLICT (account_id) DO UPDATE SET name = EXCLUDED.name",
                (account.account_id, tenant_id, account.name),
            )
    return len(accounts)


def _score_one_account(
    account_id: str,
    *,
    data_plane: CustomerDataPlane,
    as_of: str,
) -> dict[str, Any]:
    """Build the value model + projected priority for a single account."""

    account = _require_account(account_id, data_plane)
    company = data_plane.cs.get_company(account_id)
    health = data_plane.cs.get_health_score(account_id)
    adoption = data_plane.cs.get_adoption_summary(account_id)

    if company is None or health is None:
        raise MissingCSDataError(account_id)

    entitlements = tuple(data_plane.telemetry.list_entitlements(account_id))
    signals = tuple(data_plane.telemetry.list_usage_signals(account_id))
    plans = tuple(data_plane.cs.list_success_plans(account_id))
    milestones = tuple(data_plane.telemetry.list_ttv_milestones(account_id))

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
        p for p in plans if p.target_date and p.target_date <= as_of
    )

    projected = project_ttv_lens(
        model,
        company=company,
        health=health,
        open_milestone_gaps=open_gaps,
        overdue_success_plans=overdue_plans,
        as_of=as_of,
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


def score_account_priority(
    account_id: str,
    *,
    data_plane: CustomerDataPlane,
    as_of: str,
) -> tuple[int, list[dict[str, Any]]]:
    """Return priority score plus divergence packets for list/digest views."""

    scored = _score_one_account(account_id, data_plane=data_plane, as_of=as_of)
    return int(scored["priority"]["score"]), list(scored["divergences"])


def _stakeholder_rows(
    account,
    company,
    contacts,
    stakeholders,
    job_changes,
    *,
    as_of: str,
) -> list[dict[str, Any]]:
    """Person UI depth (Harvest 17): per-person role-graph rows for the
    Stakeholders drawer. Server-side only -- the UI renders what's served,
    it does not compute (K13) -- ``days_since_interaction`` is precomputed
    here, and ``new_unengaged`` reuses report 32's own pure detection
    function (config-window resolved) rather than re-deriving that window
    logic in the API layer. ``departed`` is a plain presence check (any
    departure signal, no window) since a person who left is honestly
    "departed" regardless of whether that departure currently fires the
    champion_departed priority factor.
    """

    cfg = load_value_model_config()
    resolved = resolve_thresholds(account_attributes(account, company), cfg)
    thresholds = resolved.thresholds

    departed_contact_ids = {
        jc.contact_id for jc in job_changes if jc.change_type == "departure"
    }
    new_unengaged = new_stakeholder_unengaged(
        stakeholders, (), as_of=as_of,
        window_days=thresholds.new_stakeholder_window_days,
    )
    new_unengaged_contact_id = new_unengaged.contact_id if new_unengaged else None

    stakeholders_by_contact = {s.contact_id: s for s in stakeholders}
    as_of_date = iso_date(as_of)

    rows: list[dict[str, Any]] = []
    for c in contacts:
        stake = stakeholders_by_contact.get(c.contact_id)
        rows.append({
            "contact_id": c.contact_id,
            "name": c.name,
            "relationship_type": stake.relationship_type if stake else None,
            "title": c.title,
            "consent_to_contact": c.consent_to_contact,
            "days_since_interaction": (
                (as_of_date - iso_date(stake.last_interaction)).days if stake else None
            ),
            "champion": bool(stake and stake.relationship_type == "champion"),
            "departed": c.contact_id in departed_contact_ids,
            "new_unengaged": c.contact_id == new_unengaged_contact_id,
        })
    return rows


def _enrich_person_evidence(
    work_items: list[dict[str, Any]], *, data_plane: CustomerDataPlane,
) -> None:
    """Person UI depth (Harvest 17): attach a plain ``person_name`` to any
    factor-evidence entry sourced from a person record (report 32's person
    factors file evidence under source ``"crm"`` with a contact or
    job-change-signal id) so the UI can cite the person without joining
    evidence ids client-side (K13: the UI renders, it does not compute).
    Mutates ``work_items`` in place; read-only lookups, no sweep/value-model
    logic touched.
    """

    cache: dict[str, dict[str, str]] = {}
    for item in work_items:
        account_id = item.get("account_id")
        if not account_id:
            continue
        factors = (item.get("priority") or {}).get("factors") or []
        if not any(f.get("evidence") for f in factors):
            continue
        name_by_id = cache.get(account_id)
        if name_by_id is None:
            contacts = data_plane.crm.list_contacts(account_id)
            _, job_changes = _person_layer_inputs(data_plane, account_id)
            name_by_id = {c.contact_id: c.name for c in contacts}
            name_by_id.update({jc.signal_id: jc.contact_name for jc in job_changes})
            cache[account_id] = name_by_id
        for factor in factors:
            for ev in factor.get("evidence") or ():
                if ev.get("source") == "crm":
                    name = name_by_id.get(ev.get("source_id"))
                    if name:
                        ev["person_name"] = name


def _build_account_brief(
    account_id: str,
    *,
    data_plane: CustomerDataPlane,
    as_of: str,
) -> dict[str, Any]:
    """Compose a rich account brief from all data-plane sources."""

    account = _require_account(account_id, data_plane)
    company = data_plane.cs.get_company(account_id)
    health = data_plane.cs.get_health_score(account_id)
    adoption = data_plane.cs.get_adoption_summary(account_id)

    if company is None or health is None:
        raise MissingCSDataError(account_id)

    entitlements = tuple(data_plane.telemetry.list_entitlements(account_id))
    signals = tuple(data_plane.telemetry.list_usage_signals(account_id))
    plans = tuple(data_plane.cs.list_success_plans(account_id))
    milestones = tuple(data_plane.telemetry.list_ttv_milestones(account_id))
    ctas = data_plane.cs.list_ctas(account_id)
    cases = data_plane.crm.list_cases(account_id)
    contacts = data_plane.crm.list_contacts(account_id)
    opportunities = data_plane.crm.list_opportunities(account_id)
    stakeholders, job_changes = _person_layer_inputs(data_plane, account_id)

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
        p for p in plans if p.target_date and p.target_date <= as_of
    )

    projected = project_ttv_lens(
        model,
        company=company,
        health=health,
        open_milestone_gaps=open_gaps,
        overdue_success_plans=overdue_plans,
        as_of=as_of,
    )

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

    if data_plane.comms is not None:
        comms_gmail = data_plane.comms.list_gmail_signals(account_id)
        comms_call_transcripts = data_plane.comms.list_call_transcript_signals(account_id)
        comms_internal = data_plane.comms.list_internal_notes(account_id)
    else:
        # No comms source configured for this account -- degrade honestly to
        # empty, same discipline as onboarding/adoption when their source is
        # absent (never fabricate rows).
        comms_gmail, comms_call_transcripts, comms_internal = [], [], []

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
        "stakeholders": _stakeholder_rows(
            account, company, contacts, stakeholders, job_changes, as_of=as_of,
        ),
        "opportunities": [asdict(o) for o in opportunities],
        "entitlements": [asdict(e) for e in entitlements],
        "recent_usage_signals": [asdict(s) for s in signals[:20]],
        "milestones": [asdict(m) for m in milestones],
        "suggested_talking_points": talking_points,
        "comms_gmail": [asdict(c) for c in comms_gmail],
        "comms_call_transcripts": [asdict(c) for c in comms_call_transcripts],
        "comms_internal": [asdict(n) for n in comms_internal],
    }


def _require_account(account_id: str, data_plane: CustomerDataPlane):
    account = data_plane.crm.get_account(account_id)
    if account is None:
        raise AccountNotFoundError(account_id)
    return account


def _proposal_has_contact_consent(
    proposal: ActionProposal, *, data_plane: CustomerDataPlane,
) -> bool:
    """True unless *proposal* is a ``draft_customer_outreach`` targeting a
    contact without ``consent_to_contact``. Shared by the REST (api.py) and
    MCP (mcp_server.py) approve paths so both surfaces enforce identical
    consent semantics on the same proposal shape."""

    if proposal.action != "draft_customer_outreach":
        return True
    account_id = proposal.payload.get("account_id")
    contact_id = proposal.payload.get("contact_id")
    if not isinstance(account_id, str):
        return False
    contacts = data_plane.crm.list_contacts(account_id)
    if isinstance(contact_id, str):
        contacts = [contact for contact in contacts if contact.contact_id == contact_id]
    return any(contact.consent_to_contact for contact in contacts)
