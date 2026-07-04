"""Event-level telemetry exhaust must aggregate back to the simulator's own
``AdoptionSummary`` at every bible checkpoint for Pinehill and Meridian --
the aggregation-derivation test the universe never had (Universe v2,
WS-Data-Classes Phase 1)."""

from __future__ import annotations

from ultra_csm.data_plane.book_simulator import simulate_book
from ultra_csm.data_plane.fixtures import account_id_for
from ultra_csm.data_plane.narrative_shared import base_synthetic_book
from ultra_csm.data_plane.telemetry_events import (
    TELEMETRY_ACCOUNTS,
    adoption_rate_from_events,
    daily_active_assets_from_events,
    telemetry_events_for_day,
)

# Bible checkpoints (docs/SYNTHETIC_UNIVERSE_BIBLE.md): Pinehill
# before/during/after, Meridian day20/day170/day280.
_CHECKPOINTS: dict[str, tuple[int, ...]] = {
    "pinehill-transport": (20, 50, 310),
    "meridian-fleet": (20, 170, 280),
}

_TOLERANCE_PCT = 2.0


def test_telemetry_accounts_cover_pinehill_and_meridian_only():
    assert set(TELEMETRY_ACCOUNTS) == {"pinehill-transport", "meridian-fleet"}


def test_event_aggregation_matches_simulator_within_tolerance_at_every_checkpoint():
    base = base_synthetic_book()
    for slug, days in _CHECKPOINTS.items():
        account_id = account_id_for(slug)
        for day in days:
            events = telemetry_events_for_day(slug, day)
            book = simulate_book(base, day)
            adoption = next(a for a in book.adoption_summaries if a.account_id == account_id)

            derived_active = daily_active_assets_from_events(events, day)
            denom = max(1, adoption.active_assets)
            pct_error = abs(derived_active - adoption.active_assets) / denom * 100
            assert pct_error <= _TOLERANCE_PCT, (
                f"{slug} day{day}: simulator active_assets={adoption.active_assets}, "
                f"derived={derived_active}, error={pct_error:.2f}% exceeds {_TOLERANCE_PCT}%"
            )

            derived_rate = adoption_rate_from_events(events, day, adoption.entitled_assets)
            rate_denom = max(0.01, adoption.adoption_rate)
            rate_pct_error = abs(derived_rate - adoption.adoption_rate) / rate_denom * 100
            assert rate_pct_error <= _TOLERANCE_PCT, (
                f"{slug} day{day}: simulator adoption_rate={adoption.adoption_rate}, "
                f"derived={derived_rate}, error={rate_pct_error:.2f}% exceeds {_TOLERANCE_PCT}%"
            )


def test_every_active_asset_emits_login_feature_action_and_api_call():
    events = telemetry_events_for_day("pinehill-transport", 50)
    by_asset: dict[str, set[str]] = {}
    for e in events:
        by_asset.setdefault(e.asset_id, set()).add(e.event_type)
    assert by_asset, "expected at least one active asset at day 50"
    for asset_id, types in by_asset.items():
        assert types == {"login", "feature_action", "api_call"}, (asset_id, types)


def test_feature_action_module_is_within_account_entitlements():
    events = telemetry_events_for_day("meridian-fleet", 170)
    modules = {e.module for e in events if e.event_type == "feature_action"}
    assert modules <= {"core_telematics", "route_optimization", "driver_coaching", "maintenance_alerts"}


def test_rejects_untelemetered_account():
    import pytest

    with pytest.raises(ValueError):
        telemetry_events_for_day("trailhead-logistics", 60)


def test_derivation_is_deterministic_across_two_calls():
    first = telemetry_events_for_day("pinehill-transport", 50)
    second = telemetry_events_for_day("pinehill-transport", 50)
    assert first == second
