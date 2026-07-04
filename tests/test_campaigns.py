"""Campaign target-cohort derivation and engagement exhaust (Universe v2,
WS-Data-Classes Phase 3)."""

from __future__ import annotations

from ultra_csm.data_plane.campaigns import (
    ROUTE_OPTIMIZER_ADOPTION_CAMPAIGN,
    TARGET_COHORT,
    engagement_events_for_campaign,
    engagement_summary_by_account,
)
from ultra_csm.data_plane.fixtures import account_id_for


def test_target_cohort_is_route_optimizer_entitled_and_shallow_depth():
    assert set(TARGET_COHORT) == {
        "pinehill-transport", "stonebridge-fleet", "sagebrush-transport", "cedar-valley",
    }


def test_campaign_schedule_spans_days_60_to_120():
    assert ROUTE_OPTIMIZER_ADOPTION_CAMPAIGN.schedule[0] == 60
    assert ROUTE_OPTIMIZER_ADOPTION_CAMPAIGN.schedule[-1] == 120
    assert all(60 <= d <= 120 for d in ROUTE_OPTIMIZER_ADOPTION_CAMPAIGN.schedule)


def test_content_refs_reference_route_optimizer_catalog_entries():
    assert ROUTE_OPTIMIZER_ADOPTION_CAMPAIGN.content_refs == (
        "content-route-optimizer-adoption", "content-route-optimizer-setup-video",
    )


def test_healthy_persona_engages_more_than_at_risk_persona():
    summary = engagement_summary_by_account()
    cedar_valley = summary[account_id_for("cedar-valley")]  # renewal_stable
    sagebrush = summary[account_id_for("sagebrush-transport")]  # at_risk_declining
    assert cedar_valley["opens"] > sagebrush["opens"]


def test_every_cohort_account_gets_one_event_per_scheduled_send():
    events = engagement_events_for_campaign()
    assert len(events) == len(TARGET_COHORT) * len(ROUTE_OPTIMIZER_ADOPTION_CAMPAIGN.schedule)
    assert all(e.sent for e in events)


def test_engagement_is_deterministic_across_two_calls():
    first = engagement_events_for_campaign()
    second = engagement_events_for_campaign()
    assert first == second


def test_click_implies_open():
    events = engagement_events_for_campaign()
    assert all((not e.clicked) or e.opened for e in events)
