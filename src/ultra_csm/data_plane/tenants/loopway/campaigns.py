"""Loopway campaign objects + deterministic engagement exhaust (Universe
v2, WS-Tenant-Loopway, Wave 3). Mirrors
``ultra_csm.data_plane.campaigns``'s pattern (one campaign object +
engagement exhaust derived from the fixture book, not invented) at this
tenant's own scale: TWO seeded cohort campaigns, matching Arc L1 (the
activation-nurture cohort_action) and Arc L3 (the win-back cohort_action)
from ``docs/TENANT_LOOPWAY_BIBLE.md``. Cohorts are read directly off
``synthetic_book.py``'s frozen ``L1_STALLED``/``L3_COHORT`` tuples, never
re-derived from a heuristic.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from ultra_csm.data_plane.fixtures import account_id_for, det_id
from ultra_csm.data_plane.tenants.loopway.synthetic_book import L1_STALLED, L3_COHORT

ACTIVATION_CAMPAIGN_ID = det_id("campaign", "loopway", "driver-app-activation-nurture-d75")
WINBACK_CAMPAIGN_ID = det_id("campaign", "loopway", "usage-decay-winback-d200")

_ACTIVATION_SEND_DAYS: tuple[int, ...] = (75, 85, 95)
_WINBACK_SEND_DAYS: tuple[int, ...] = (200, 210)


@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    tenant: str
    content_refs: tuple[str, ...]
    target_cohort_rule: str
    schedule: tuple[int, ...]


@dataclass(frozen=True)
class CampaignEngagementEvent:
    event_id: str
    campaign_id: str
    account_id: str
    day_offset: int
    sent: bool
    opened: bool
    clicked: bool


ACTIVATION_NURTURE_CAMPAIGN = Campaign(
    campaign_id=ACTIVATION_CAMPAIGN_ID,
    tenant="loopway",
    content_refs=("content-driver-app-quickstart", "content-driver-app-activation-video"),
    target_cohort_rule="Arc L1: signup wave day 30-45, driver_app_activated milestone not achieved by day 75",
    schedule=_ACTIVATION_SEND_DAYS,
)

USAGE_DECAY_WINBACK_CAMPAIGN = Campaign(
    campaign_id=WINBACK_CAMPAIGN_ID,
    tenant="loopway",
    content_refs=("content-winback-reactivation-guide",),
    target_cohort_rule="Arc L3: active_users/route_plans_per_week decayed to zero, days 150-210, zero support contact",
    schedule=_WINBACK_SEND_DAYS,
)

# Low but non-zero engagement -- these are the two "unhealthy" cohorts by
# construction (stalled activation / silent decay); their engagement is
# deliberately weak, unlike fleetops' healthy-persona-driven variation --
# this tenant's campaigns are corrective, not lifecycle-nurture-for-healthy-accounts.
_ACTIVATION_OPEN_RATE = 0.25
_ACTIVATION_CLICK_RATE = 0.08
_WINBACK_OPEN_RATE = 0.10
_WINBACK_CLICK_RATE = 0.02


def _det_unit_interval(*parts: object) -> float:
    return (UUID(det_id(*parts)).int % 10_000) / 10_000


def _engagement_events_for(cohort: tuple[str, ...], campaign: Campaign, open_rate: float, click_rate: float) -> tuple[CampaignEngagementEvent, ...]:
    events: list[CampaignEngagementEvent] = []
    for slug in cohort:
        account_id = account_id_for(slug)
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


def activation_engagement_events() -> tuple[CampaignEngagementEvent, ...]:
    return _engagement_events_for(L1_STALLED, ACTIVATION_NURTURE_CAMPAIGN, _ACTIVATION_OPEN_RATE, _ACTIVATION_CLICK_RATE)


def winback_engagement_events() -> tuple[CampaignEngagementEvent, ...]:
    return _engagement_events_for(L3_COHORT, USAGE_DECAY_WINBACK_CAMPAIGN, _WINBACK_OPEN_RATE, _WINBACK_CLICK_RATE)


def engagement_summary_by_account(events: tuple[CampaignEngagementEvent, ...]) -> dict[str, dict[str, int]]:
    by_account_id: dict[str, dict[str, int]] = {}
    for e in events:
        bucket = by_account_id.setdefault(e.account_id, {"sends": 0, "opens": 0, "clicks": 0})
        bucket["sends"] += 1
        bucket["opens"] += 1 if e.opened else 0
        bucket["clicks"] += 1 if e.clicked else 0
    return by_account_id
