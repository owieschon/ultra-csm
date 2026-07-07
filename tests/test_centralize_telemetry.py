from __future__ import annotations

import pytest

from ultra_csm.data_plane.centralize_telemetry import (
    CENTRALIZE_ARC_PROFILES,
    centralize_telemetry_timeline,
    centralize_telemetry_bundle,
    centralize_usage_signals_for_day,
)


def _signal_value(slug: str, day: int, metric: str) -> float:
    signals = centralize_usage_signals_for_day(slug, day)
    match = next(signal for signal in signals if signal.metric_name == metric)
    return match.value


def test_centralize_dataset_covers_all_six_bible_arcs_at_checkpoints():
    assert set(CENTRALIZE_ARC_PROFILES) == {
        "pinehill-transport",
        "pinnacle-supply",
        "quarrystone-logistics",
        "aspenridge-supply",
        "meridian-fleet",
        "trailhead-logistics",
    }

    for slug, profile in CENTRALIZE_ARC_PROFILES.items():
        for day in profile.checkpoint_days:
            bundle = centralize_telemetry_bundle(slug, day)
            assert bundle.app_events, f"{slug} day{day} missing Centralize app exhaust"
            assert bundle.posthog_events, f"{slug} day{day} missing PostHog exhaust"
            assert {signal.account_id for signal in bundle.usage_signals} == {
                bundle.app_events[0].account_id
            }
            assert {signal.source_ref for signal in bundle.usage_signals} == {
                "centralize_posthog:derived_fixture"
            }


def test_centralize_posthog_events_stay_raw_and_do_not_pretend_to_be_live_custom_events():
    bundle = centralize_telemetry_bundle("aspenridge-supply", 200)

    assert any(event.event == "$pageview" for event in bundle.posthog_events)
    assert any(event.event == "$autocapture" for event in bundle.posthog_events)
    assert all(event.event != "activation_completed" for event in bundle.posthog_events)
    assert {event.confidence for event in bundle.posthog_events} <= {
        "observed_config",
        "inferred_route",
    }


def test_onboarding_stall_has_failure_exhaust_then_recovers():
    day_50 = centralize_telemetry_bundle("pinehill-transport", 50)
    day_310 = centralize_telemetry_bundle("pinehill-transport", 310)

    assert any(event.contains_exception for event in day_50.posthog_events)
    assert not any(event.contains_exception for event in day_310.posthog_events)
    assert _signal_value("pinehill-transport", 50, "centralize_integration_sync_failures") == 1.0
    assert _signal_value("pinehill-transport", 310, "centralize_integration_sync_failures") == 0.0


def test_expansion_ready_has_action_and_relationship_exhaust_without_control_false_positive():
    meridian = centralize_telemetry_bundle("meridian-fleet", 170)
    trailhead = centralize_telemetry_bundle("trailhead-logistics", 180)

    assert any(
        event.event_type == "recommended_action_completed" for event in meridian.app_events
    )
    assert _signal_value("meridian-fleet", 170, "centralize_action_completions") == 1.0
    assert _signal_value("trailhead-logistics", 180, "centralize_action_completions") == 0.0
    assert not any(event.contains_exception for event in trailhead.posthog_events)


def test_churn_brewing_and_silent_decline_are_absence_or_decay_signals_not_error_spikes():
    quarrystone = centralize_telemetry_bundle("quarrystone-logistics", 225)
    aspenridge = centralize_telemetry_bundle("aspenridge-supply", 340)

    assert not any(event.contains_exception for event in quarrystone.posthog_events)
    assert not any(event.contains_exception for event in aspenridge.posthog_events)
    assert _signal_value("quarrystone-logistics", 225, "centralize_relationship_events") == 0.0
    assert _signal_value("aspenridge-supply", 340, "posthog_autocapture_events") >= 1.0


def test_centralize_telemetry_is_deterministic():
    first = centralize_telemetry_bundle("pinnacle-supply", 120)
    second = centralize_telemetry_bundle("pinnacle-supply", 120)

    assert first == second


def test_timeline_shapes_match_real_world_arc_differences():
    pinehill = centralize_telemetry_timeline("pinehill-transport", 310)
    quarrystone = centralize_telemetry_timeline("quarrystone-logistics", 225)
    meridian = centralize_telemetry_timeline("meridian-fleet", 280)
    trailhead = centralize_telemetry_timeline("trailhead-logistics", 300)

    pinehill_pre_recovery_exceptions = sum(
        event.contains_exception
        for bundle in pinehill
        if bundle.day_offset < 100
        for event in bundle.posthog_events
    )
    pinehill_after_recovery_exceptions = sum(
        event.contains_exception
        for bundle in pinehill
        if bundle.day_offset >= 300
        for event in bundle.posthog_events
    )
    quarrystone_posthog = sum(len(bundle.posthog_events) for bundle in quarrystone)
    meridian_action_events = sum(
        event.event_type == "recommended_action_completed"
        for bundle in meridian
        for event in bundle.app_events
    )
    trailhead_action_events = sum(
        event.event_type == "recommended_action_completed"
        for bundle in trailhead
        for event in bundle.app_events
    )

    assert pinehill_pre_recovery_exceptions > 0
    assert pinehill_after_recovery_exceptions == 0
    assert quarrystone_posthog < sum(len(bundle.posthog_events) for bundle in trailhead)
    assert meridian_action_events > trailhead_action_events


def test_timeline_includes_identity_gaps_and_console_log_noise_without_breaking_rollups():
    timeline = centralize_telemetry_timeline("meridian-fleet", 280)
    missing_account_events = [
        event
        for bundle in timeline
        for event in bundle.posthog_events
        if event.account_id is None
    ]
    console_events = [
        event
        for bundle in timeline
        for event in bundle.posthog_events
        if event.contains_console_logs
    ]
    signal_names = {
        signal.metric_name
        for bundle in timeline
        for signal in bundle.usage_signals
    }

    assert missing_account_events
    assert console_events
    assert {
        "centralize_account_views",
        "centralize_relationship_events",
        "posthog_session_recordings",
        "posthog_autocapture_events",
    } <= signal_names


def test_unscripted_account_fails_closed():
    with pytest.raises(ValueError):
        centralize_telemetry_bundle("ironhorse-freight", 30)
