"""Shared API/MCP helpers for scoring, briefs, and operator auth."""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import asdict, dataclass
from typing import Any

from ultra_csm.data_plane import CustomerDataPlane
from ultra_csm.governance import ROLE_ORDER_CONFIRM_AUTHORITY as CSM_APPROVAL_ROLE
from ultra_csm.governance import role_id
from ultra_csm.platform.db import session
from ultra_csm.platform.seed import det_uuid
from ultra_csm.value_model import build_customer_value_model, project_ttv_lens

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


def demo_noauth_enabled() -> bool:
    return (
        os.environ.get("ULTRA_CSM_DEMO_NOAUTH") == "1"
        or os.environ.get("ULTRA_CSM_DEMO_OPERATOR") == "1"
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


def _require_account(account_id: str, data_plane: CustomerDataPlane):
    account = data_plane.crm.get_account(account_id)
    if account is None:
        raise AccountNotFoundError(account_id)
    return account
