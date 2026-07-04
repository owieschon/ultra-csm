"""Fieldstone Service Cloud's 12-account book (Universe v2, WS-Tenant-
Fieldstone, Wave 3). See ``docs/TENANT_FIELDSTONE_BIBLE.md`` for the
authored ground truth this module is causal exhaust of.

Fieldstone is the NORMS tenant: field-service management SaaS for HVAC/
plumbing contractors, HubSpot-shaped CRM, **no CS platform at all** (see
the bible's "No-CS-platform discipline"). ``FieldstoneCSPlatformConnector``
below implements the full ``CSPlatformConnector`` protocol but every
method returns the honest absence value the protocol already supports --
no new sentinel type invented, see the bible section by that name.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from ultra_csm.data_plane.contracts import (
    AccountResolution,
    AdoptionSummary,
    CRMAccount,
    CRMActivity,
    CRMCase,
    CRMContact,
    CRMOpportunity,
    CSCompany,
    CTA,
    CTAStatus,
    CustomerDataPlane,
    Entitlement,
    HealthScore,
    SuccessPlan,
    UsageSignal,
    TimeToValueMilestone,
    resolve_candidates,
)

TENANT = "fieldstone"


def det_id(*parts: object) -> str:
    """Namespaced ``det_id`` for the fieldstone tenant (D5): every id is
    computed under ``"ultra-csm:fieldstone:" + ":".join(parts)`` so no
    fieldstone-authored id can ever collide with a fleetops one even if
    the same slug string were reused across tenants."""

    return str(uuid5(NAMESPACE_URL, f"ultra-csm:{TENANT}:" + ":".join(map(str, parts))))


def account_id_for(slug: str) -> str:
    return det_id("account", slug)


# ---------------------------------------------------------------------------
# Account master list (slug, name, arr_cents, tier, role)
# ---------------------------------------------------------------------------
_ACCT_DATA: tuple[tuple[str, str, int, str, str], ...] = (
    ("masonry-home-services", "Masonry Home Services", 14_500_000, "high_touch", "arc_f1"),
    ("culvert-mechanical", "Culvert Mechanical", 11_200_000, "high_touch", "arc_f2"),
    ("wrenhouse-hvac", "Wrenhouse HVAC", 6_800_000, "mid_touch", "herring_fh1"),
    ("shale-plumbing-group", "Shale Plumbing Group", 4_900_000, "mid_touch", "boring"),
    ("tanbark-mechanical", "Tanbark Mechanical", 3_600_000, "mid_touch", "boring"),
    ("cobblestone-hvac-co", "Cobblestone HVAC Co", 2_700_000, "mid_touch", "boring"),
    ("driftstone-plumbing", "Driftstone Plumbing", 1_900_000, "tech_touch", "boring"),
    ("quarrybed-mechanical", "Quarrybed Mechanical", 1_400_000, "tech_touch", "boring"),
    ("slaterock-home-services", "Slaterock Home Services", 980_000, "tech_touch", "boring"),
    ("graybrick-hvac", "Graybrick HVAC", 720_000, "tech_touch", "boring"),
    ("fieldstone-mortar-co", "Fieldstone Mortar Co", 510_000, "tech_touch", "boring"),
    ("hearthstone-plumbing", "Hearthstone Plumbing", 340_000, "tech_touch", "boring"),
)

ACCOUNT_SLUGS: tuple[str, ...] = tuple(slug for slug, *_ in _ACCT_DATA)
ARC_F1_SLUG = "masonry-home-services"
ARC_F2_SLUG = "culvert-mechanical"
HERRING_SLUG = "wrenhouse-hvac"
BORING_CONTROL_SLUGS: tuple[str, ...] = tuple(
    slug for slug, _name, _arr, _tier, role in _ACCT_DATA if role == "boring"
)

_CSM_BY_TIER = {"high_touch": "fs-csm-201", "mid_touch": "fs-csm-201", "tech_touch": "fs-csm-202"}
_OWNER_OVERRIDE = {
    # Mid-touch accounts split across both CSMs per the bible's cast.
    "shale-plumbing-group": "fs-csm-202",
    "cobblestone-hvac-co": "fs-csm-202",
}


def _owner_for(slug: str, tier: str) -> str:
    return _OWNER_OVERRIDE.get(slug, _CSM_BY_TIER[tier])


def tier_for(slug: str) -> str:
    for account_slug, _name, _arr, tier, _role in _ACCT_DATA:
        if account_slug == slug:
            return tier
    raise KeyError(f"unknown fieldstone account slug: {slug}")


def arr_cents_for(slug: str) -> int:
    for account_slug, _name, arr_cents, _tier, _role in _ACCT_DATA:
        if account_slug == slug:
            return arr_cents
    raise KeyError(f"unknown fieldstone account slug: {slug}")


@dataclass(frozen=True)
class FieldstoneCustomerData:
    accounts: tuple[CRMAccount, ...]
    contacts: tuple[CRMContact, ...]
    cases: tuple[CRMCase, ...]
    opportunities: tuple[CRMOpportunity, ...]
    entitlements: tuple[Entitlement, ...]
    usage_signals: tuple[UsageSignal, ...]
    milestones: tuple[TimeToValueMilestone, ...]


def build_fieldstone_book() -> FieldstoneCustomerData:
    accounts = tuple(
        CRMAccount(
            account_id=account_id_for(slug),
            name=name,
            owner_id=_owner_for(slug, tier),
            industry="field_service_management",
        )
        for slug, name, _arr, tier, _role in _ACCT_DATA
    )
    contacts = tuple(
        CRMContact(
            contact_id=det_id("contact", slug, "champion"),
            account_id=account_id_for(slug),
            email=f"owner@{slug}.example",
            name=_champion_name(slug),
            role="owner_operator",
            title="Owner",
            consent_to_contact=True,
        )
        for slug, _name, _arr, _tier, _role in _ACCT_DATA
    )
    cases = _cases()
    opportunities = tuple(
        CRMOpportunity(
            opportunity_id=det_id("opp", slug, "renewal"),
            account_id=account_id_for(slug),
            stage_name="closedwon",
            amount_cents=arr,
            close_date="2026-05-01",
            opportunity_type="Renewal",
        )
        for slug, _name, arr, _tier, _role in _ACCT_DATA
    )
    entitlements = tuple(
        Entitlement(account_id_for(slug), "job_scheduling", 1, "seats", "2026-05-01")
        for slug, _name, _arr, _tier, _role in _ACCT_DATA
    )
    return FieldstoneCustomerData(
        accounts=accounts,
        contacts=contacts,
        cases=cases,
        opportunities=opportunities,
        entitlements=entitlements,
        usage_signals=(),
        milestones=(),
    )


_CHAMPION_NAMES = {
    "masonry-home-services": "Renata Vaughn",
    "culvert-mechanical": "Marcus Oduya",
    "wrenhouse-hvac": "Diane Kessler",
}


def _champion_name(slug: str) -> str:
    return _CHAMPION_NAMES.get(slug, f"{slug.replace('-', ' ').title()} Owner")


def _cases() -> tuple[CRMCase, ...]:
    """Per the bible: Arc F2 gets one open billing-dispute case (day 100,
    unresolved through day 150+); the herring gets one loud-looking case
    that resolves same-day; every other account has zero cases (boring is
    boring, and a tech-touch account with zero comms/case fixture is
    correct thinness per the segmented-book bible's own discipline, not
    an artifact)."""

    culvert = account_id_for(ARC_F2_SLUG)
    wrenhouse = account_id_for(HERRING_SLUG)
    return (
        CRMCase(
            case_id=det_id("case", ARC_F2_SLUG, "billing-dispute"),
            account_id=culvert,
            status="Open",
            priority="Medium",
            origin="Portal",
            subject="Quote-to-Invoice: disputed line item on May invoice",
            created_at="2026-09-29T14:00:00Z",  # day 100
        ),
        CRMCase(
            case_id=det_id("case", HERRING_SLUG, "portal-down"),
            account_id=wrenhouse,
            status="Closed",
            priority="P1",
            origin="Portal",
            subject="Customer portal down for all users",
            created_at="2026-08-05T09:00:00Z",  # day 45
            closed_at="2026-08-05T13:00:00Z",  # resolved same day, 4h
        ),
    )


class FieldstoneCRMDataConnector:
    """HubSpot-shaped-CRM-backed connector -- read side only exposes the
    normalized ``CRMDataConnector`` protocol shape; ``tenants/fieldstone/
    hubspot_transport.py`` is the actual wire-shape layer this data is
    also exposed through for the onboarding-run phase."""

    def __init__(self, *, data: FieldstoneCustomerData | None = None) -> None:
        self._data = data or build_fieldstone_book()
        self._logged: list[CRMActivity] = []

    def list_accounts(self, *, tenant_id: str | None = None) -> list[CRMAccount]:
        return list(self._data.accounts)

    def resolve_account_by_email(self, email: str) -> AccountResolution:
        if not email:
            return resolve_candidates([])
        account_ids = [c.account_id for c in self._data.contacts if c.email.lower() == email.lower()]
        return resolve_candidates(account_ids)

    def get_account(self, account_id: str) -> CRMAccount | None:
        return next((a for a in self._data.accounts if a.account_id == account_id), None)

    def list_contacts(self, account_id: str) -> list[CRMContact]:
        return [c for c in self._data.contacts if c.account_id == account_id]

    def list_cases(self, account_id: str) -> list[CRMCase]:
        return [c for c in self._data.cases if c.account_id == account_id]

    def list_opportunities(self, account_id: str) -> list[CRMOpportunity]:
        return [o for o in self._data.opportunities if o.account_id == account_id]

    def log_activity(
        self,
        account_id: str,
        *,
        channel: str,
        direction: str,
        summary: str,
        idempotency_key: str,
    ) -> str:
        for activity in self._logged:
            if activity.idempotency_key == idempotency_key:
                return activity.activity_id
        ref = det_id("activity", account_id, idempotency_key)
        self._logged.append(CRMActivity(
            activity_id=ref,
            account_id=account_id,
            channel=channel,
            direction=direction,
            summary=summary,
            occurred_at="2026-06-21T12:00:00Z",
            idempotency_key=idempotency_key,
        ))
        return ref


class FieldstoneCSPlatformConnector:
    """No CS platform exists for this tenant (bible: "No-CS-platform
    discipline"). Every method returns the honest absence value the
    ``CSPlatformConnector`` protocol already supports -- ``None`` for a
    single-record lookup, ``[]`` for a list -- never a fabricated
    health band/CTA/adoption summary."""

    def get_company(self, account_id: str) -> CSCompany | None:
        return None

    def get_health_score(self, account_id: str) -> HealthScore | None:
        return None

    def list_ctas(self, account_id: str, *, status: CTAStatus | None = None) -> list[CTA]:
        return []

    def list_success_plans(self, account_id: str) -> list[SuccessPlan]:
        return []

    def get_adoption_summary(self, account_id: str) -> AdoptionSummary | None:
        return None


class FieldstoneProductTelemetryConnector:
    def __init__(self, *, data: FieldstoneCustomerData | None = None) -> None:
        self._data = data or build_fieldstone_book()

    def list_entitlements(self, account_id: str) -> list[Entitlement]:
        return [e for e in self._data.entitlements if e.account_id == account_id]

    def list_usage_signals(
        self,
        account_id: str,
        *,
        metric_name: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> list[UsageSignal]:
        return [s for s in self._data.usage_signals if s.account_id == account_id]

    def list_ttv_milestones(self, account_id: str) -> list[TimeToValueMilestone]:
        return [m for m in self._data.milestones if m.account_id == account_id]


def build_fieldstone_data_plane() -> CustomerDataPlane:
    data = build_fieldstone_book()
    return CustomerDataPlane(
        crm=FieldstoneCRMDataConnector(data=data),
        cs=FieldstoneCSPlatformConnector(),
        telemetry=FieldstoneProductTelemetryConnector(data=data),
    )
