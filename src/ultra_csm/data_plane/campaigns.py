"""Campaign objects + deterministic engagement exhaust (Universe v2,
WS-Data-Classes Phase 3).

One seeded campaign: a Route Optimizer adoption campaign (days 60-120)
targeting fleetops accounts entitled to ``route_optimization`` with the
capability listed in ``AdoptionSummary.underused_capabilities`` (shallow
depth) -- the cohort is derived directly from
``synthetic_book.py``'s existing entitlement/adoption tables, never a new
cohort invented. Engagement (sends/opens/clicks per account per send)
varies by account persona (``data_simulator._ACCOUNT_PERSONA``): healthy
personas engage, at-risk personas don't -- derived from the existing
persona map, no randomness.

``content_catalog.json`` (``knowledge/tenants/fleetops/content_catalog.json``)
supplies this campaign's ``content_refs``; wave 2's ``playbooks.json``
wiring is out of scope here (see docs/PROGRAM_REPORT_12.md's Owner Ask for
the exact ids to use).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from ultra_csm.data_plane.data_simulator import _ACCOUNT_PERSONA
from ultra_csm.data_plane.fixtures import account_id_for, det_id
from ultra_csm.data_plane.synthetic_book import _ADOPTION, _ENTITLEMENTS

CAMPAIGN_ID = det_id("campaign", "fleetops", "route-optimizer-adoption-w60-120")

# Cohort: entitled to route_optimization AND it appears in the account's
# own underused_capabilities (shallow depth) -- read directly off
# synthetic_book.py's tables, not invented.
TARGET_COHORT: tuple[str, ...] = tuple(
    sorted(
        slug
        for slug, caps in _ENTITLEMENTS.items()
        if any(cap == "route_optimization" for cap, _qty, _unit in caps)
        and "route_optimization" in _ADOPTION[slug][5]
    )
)

_CAMPAIGN_START_DAY = 60
_CAMPAIGN_END_DAY = 120
_SEND_INTERVAL_DAYS = 15  # sends at day 60, 75, 90, 105, 120
_SEND_DAYS: tuple[int, ...] = tuple(
    range(_CAMPAIGN_START_DAY, _CAMPAIGN_END_DAY + 1, _SEND_INTERVAL_DAYS)
)

# Engagement rates (open_rate, click_rate) by persona, derived from the
# existing persona map -- healthy personas (steady/renewal-stable) engage
# well; at-risk/declining personas barely open; onboarding/moderate sit in
# between. No randomness: the rate itself is the deterministic model, and
# per-account/per-send opens/clicks are a deterministic hash-based
# threshold against that rate (see ``_det_unit_interval``), not a random
# draw.
_PERSONA_ENGAGEMENT: dict[str, tuple[float, float]] = {
    "renewal_stable": (0.65, 0.30),
    "stable": (0.60, 0.25),
    "exemplary": (0.70, 0.35),
    "expanding": (0.65, 0.30),
    "moderate": (0.45, 0.15),
    "stalled_onboarding": (0.35, 0.10),
    "normal_onboarding": (0.50, 0.20),
    "fast_onboarding": (0.55, 0.22),
    "at_risk_champion": (0.15, 0.03),
    "at_risk_declining": (0.10, 0.02),
    "at_risk_support": (0.20, 0.05),
    "renewal_risk": (0.25, 0.08),
    "churned": (0.0, 0.0),
}


@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    tenant: str
    content_refs: tuple[str, ...]
    target_cohort_rule: str
    schedule: tuple[int, ...]  # day offsets of each send


@dataclass(frozen=True)
class CampaignEngagementEvent:
    """One account's engagement outcome for one campaign send."""

    event_id: str
    campaign_id: str
    account_id: str
    day_offset: int
    sent: bool
    opened: bool
    clicked: bool


ROUTE_OPTIMIZER_ADOPTION_CAMPAIGN = Campaign(
    campaign_id=CAMPAIGN_ID,
    tenant="fleetops",
    content_refs=("content-route-optimizer-adoption", "content-route-optimizer-setup-video"),
    target_cohort_rule="entitlement:route_optimization AND underused_capabilities contains route_optimization",
    schedule=_SEND_DAYS,
)


def _det_unit_interval(*parts: object) -> float:
    """Deterministic value in [0, 1) derived from ``det_id``'s UUID5 --
    used as a stable per-account/per-send engagement threshold, never
    randomness."""

    return (UUID(det_id(*parts)).int % 10_000) / 10_000


def _persona_for(slug: str) -> str:
    return _ACCOUNT_PERSONA.get(slug, "stable")


def engagement_events_for_campaign(campaign: Campaign = ROUTE_OPTIMIZER_ADOPTION_CAMPAIGN) -> tuple[CampaignEngagementEvent, ...]:
    """Deterministic sends/opens/clicks for every account in
    ``TARGET_COHORT``, at every scheduled send day. Every send is
    delivered (``sent=True``); whether it's opened, and if opened whether
    it's clicked, is a deterministic threshold check against that
    account's persona-derived engagement rate."""

    events: list[CampaignEngagementEvent] = []
    for slug in TARGET_COHORT:
        account_id = account_id_for(slug)
        open_rate, click_rate = _PERSONA_ENGAGEMENT.get(_persona_for(slug), (0.30, 0.10))
        for day in campaign.schedule:
            opened = _det_unit_interval("campaign-open", campaign.campaign_id, account_id, day) < open_rate
            clicked = opened and _det_unit_interval("campaign-click", campaign.campaign_id, account_id, day) < click_rate
            events.append(
                CampaignEngagementEvent(
                    event_id=det_id("campaign-engagement", campaign.campaign_id, account_id, day),
                    campaign_id=campaign.campaign_id,
                    account_id=account_id,
                    day_offset=day,
                    sent=True,
                    opened=opened,
                    clicked=clicked,
                )
            )
    return tuple(events)


def engagement_summary_by_account(
    campaign: Campaign = ROUTE_OPTIMIZER_ADOPTION_CAMPAIGN,
) -> dict[str, dict[str, int]]:
    """Sends/opens/clicks rolled up per account across the campaign's full
    schedule -- the shape a briefing/lens would actually consume."""

    events = engagement_events_for_campaign(campaign)
    by_account_id: dict[str, dict[str, int]] = {}
    for e in events:
        bucket = by_account_id.setdefault(e.account_id, {"sends": 0, "opens": 0, "clicks": 0})
        bucket["sends"] += 1
        bucket["opens"] += 1 if e.opened else 0
        bucket["clicks"] += 1 if e.clicked else 0
    return by_account_id
