"""Lane B core-loop coverage: trajectories, bridge rails, simulator determinism."""

from __future__ import annotations

import pytest

from tests._govhelpers import CLOCK, T1, setup_roster
from ultra_csm.agent1.sweep import (
    _trajectory_decline_evaluation,
    run_time_to_value_sweep,
)
from ultra_csm.data_plane import (
    DEFAULT_TENANT,
    GLOBEX_TELEMETRY_GAP,
    build_sweep_fixture_data_plane,
    sweep_fixture_data,
)
from ultra_csm.data_plane.book_simulator import simulate_book
from ultra_csm.data_plane.contracts import (
    CRMAccount,
    CSCompany,
    Entitlement,
    SuccessPlan,
)
from ultra_csm.data_plane.data_simulator import (
    AccountDataBundle,
    FeatureAdoptionState,
    SimulatedDataBundle,
    UserLoginHistory,
    simulate_data,
)
from ultra_csm.data_plane.fixtures import account_id_for
from ultra_csm.data_plane.synthetic_book import build_synthetic_book
from ultra_csm.governance import ActionGate, FixtureVerdictSource
from ultra_csm.snapshot_store import SnapshotStore
from ultra_csm.value_model import build_customer_value_model
from ultra_csm.value_model_bridge import build_deep_value_model

AS_OF = "2026-06-27"


@pytest.fixture
def sweep_conn(runtime_conn):
    runtime_conn.execute("BEGIN")
    try:
        yield runtime_conn
    finally:
        runtime_conn.rollback()


def test_sweep_adds_trajectory_decline_factor_from_snapshot_store(sweep_conn):
    orch, _authority = setup_roster(sweep_conn)
    gate = ActionGate(
        sweep_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )
    store = SnapshotStore()
    store.store_snapshot(
        0,
        GLOBEX_TELEMETRY_GAP,
        _snapshot_payload(health_band="green", health_score=75.0),
    )
    store.store_snapshot(
        30,
        GLOBEX_TELEMETRY_GAP,
        _snapshot_payload(health_band="yellow", health_score=61.0),
    )

    sweep = run_time_to_value_sweep(
        build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=orch,
        as_of=AS_OF,
        snapshot_store=store,
    )

    globex = next(item for item in sweep.work_items if item.account_id == GLOBEX_TELEMETRY_GAP)
    assert globex.priority is not None
    factor = next(
        factor for factor in globex.priority.factors
        if factor.name == "trajectory_decline"
    )
    assert factor.value == -0.4667
    assert factor.contribution == 12
    assert factor.config_version == "value-model-config-v1"
    assert factor.rule_name == "base_default"
    assert factor.threshold_name == "decline_slope"
    assert factor.threshold_value == -0.15
    assert [(ref.source_id, ref.field) for ref in factor.evidence] == [
        (GLOBEX_TELEMETRY_GAP, "snapshot_day_0_health_score"),
        (GLOBEX_TELEMETRY_GAP, "snapshot_day_30_health_score"),
    ]
    assert globex.priority.score == sum(f.contribution for f in globex.priority.factors)


def test_trajectory_decline_unknown_for_missing_or_single_snapshot():
    model = _fixture_model(GLOBEX_TELEMETRY_GAP)

    missing = _trajectory_decline_evaluation(
        None,
        account_id=GLOBEX_TELEMETRY_GAP,
        model=model,
    )
    assert missing.state == "unknown"
    assert missing.factor is None

    store = SnapshotStore()
    store.store_snapshot(
        0,
        GLOBEX_TELEMETRY_GAP,
        _snapshot_payload(health_band="green", health_score=75.0),
    )
    single = _trajectory_decline_evaluation(
        store,
        account_id=GLOBEX_TELEMETRY_GAP,
        model=model,
    )
    assert single.state == "unknown"
    assert single.factor is None


def test_snapshot_store_trend_window_velocity_and_band_change_math():
    store = SnapshotStore()
    account_id = "acct-trend"
    store.store_snapshot(
        0,
        account_id,
        _snapshot_payload(health_band="green", health_score=80.0),
    )
    store.store_snapshot(
        10,
        account_id,
        _snapshot_payload(health_band="yellow", health_score=72.0),
    )
    store.store_snapshot(
        40,
        account_id,
        _snapshot_payload(health_band="red", health_score=60.0),
    )

    assert [snap.day for snap in store.get_trajectory(account_id, window_days=30)] == [10, 40]
    assert store.compute_trend(account_id, window_days=30) == "declining"
    assert store.compute_trend_velocity(account_id, window_days=30) == -0.4

    band_change = store.detect_band_change(account_id, from_day=0, to_day=10)
    assert band_change is not None
    assert band_change.old_band == "green"
    assert band_change.new_band == "yellow"
    assert band_change.direction == "declining"
    assert store.detect_band_change(account_id, from_day=40, to_day=40) is None

    store.store_snapshot(
        50,
        account_id,
        _snapshot_payload(health_band="red", health_score=59.0),
    )
    trajectory = store.build_trajectory(account_id, window_days=365)
    assert trajectory.trend == "declining"
    assert trajectory.trend_velocity == -0.42
    assert trajectory.consecutive_band == "red"
    assert trajectory.consecutive_count == 2
    assert [point.day for point in trajectory.points] == [0, 10, 40, 50]


def test_snapshot_store_undersampled_trajectory_is_unknown():
    store = SnapshotStore()

    empty = store.build_trajectory("missing", window_days=30)
    assert empty.trend == "unknown"
    assert empty.trend_velocity == 0.0
    assert empty.points == ()

    store.store_snapshot(
        0,
        "single",
        _snapshot_payload(health_band="yellow", health_score=55.0),
    )
    single = store.build_trajectory("single", window_days=30)
    assert single.trend == "unknown"
    assert single.trend_velocity == 0.0
    assert single.consecutive_band == "yellow"
    assert single.consecutive_count == 1


def test_value_model_bridge_known_bundle_maps_expected_rails():
    account_id = "acct-known-bridge"
    account = CRMAccount(
        account_id=account_id,
        name="Known Bridge Account",
        owner_id="csm-known",
        industry="logistics",
    )
    company = CSCompany(
        company_id=account_id,
        name="Known Bridge Account",
        industry="logistics",
        arr_cents=10_000_000,
        lifecycle_stage="onboarding",
        status="Active",
        original_contract_date="2026-06-01",
        renewal_date="2027-06-01",
        csm_owner_id="csm-known",
        current_score=50.0,
    )
    entitlements = (
        Entitlement(account_id, "alpha", 10, "users", "2026-06-01"),
        Entitlement(account_id, "beta", 10, "users", "2026-06-01"),
    )
    plan = SuccessPlan(
        plan_id="plan-known",
        account_id=account_id,
        status="active",
        objectives=("reduce cycle time",),
        target_date="2026-08-01",
    )
    bundle = SimulatedDataBundle(
        day=60,
        as_of_date="2026-08-20",
        accounts={
            account_id: AccountDataBundle(
                account_id=account_id,
                account_slug="known-bridge",
                login_histories=(
                    UserLoginHistory(
                        contact_id="contact-a",
                        account_id=account_id,
                        login_days=(5, 45),
                        role_type="admin",
                        is_champion=False,
                    ),
                    UserLoginHistory(
                        contact_id="contact-b",
                        account_id=account_id,
                        login_days=(10, 50),
                        role_type="end_user",
                        is_champion=False,
                    ),
                ),
                feature_adoptions=(
                    FeatureAdoptionState(account_id, "alpha", "exploring", 10, 1, 10),
                    FeatureAdoptionState(account_id, "beta", "not_started", None, 0, 10),
                ),
                cases=(),
                opportunities=(),
                contacts=(),
                activities=(),
                dau=1,
                wau=2,
                mau=2,
                overall_csat=2.0,
                feature_depth_score=0.25,
                active_user_count=2,
                champion_active=True,
            )
        },
    )

    model, health = build_deep_value_model(
        bundle=bundle,
        account_id=account_id,
        account=account,
        company=company,
        entitlements=entitlements,
        success_plans=(plan,),
        licensed_users=10,
    )

    assert health.score == 46.0
    assert health.band == "yellow"
    assert set(health.drivers) == {
        "low_active_users",
        "low_feature_adoption",
        "low_csat",
    }
    assert model.usage.adoption_rate == 0.2
    assert model.usage.underused_capabilities == ("alpha", "beta")
    assert model.penetration.seat_penetration == 0.2
    assert model.penetration.state == "known"
    assert model.feature_depth.entitled_capabilities == ("alpha", "beta")
    assert model.feature_depth.underused_capabilities == ("alpha", "beta")
    assert model.outcome.stated_objectives == ("reduce cycle time",)
    assert model.outcome.realized_state == "not_instrumented"
    assert [factor.name for factor in model.ttv_factors] == [
        "low_seat_penetration",
        "feature_depth_gap",
    ]


def test_deep_data_simulator_is_deterministic_for_same_inputs():
    base = build_synthetic_book()
    first = simulate_data(base, day=90)
    second = simulate_data(base, day=90)
    pinehill = account_id_for("pinehill-transport")

    assert first == second
    assert first.accounts[pinehill] == second.accounts[pinehill]


def test_book_simulator_is_deterministic_and_does_not_mutate_base_book():
    base = build_synthetic_book()
    fresh_base = build_synthetic_book()

    first = simulate_book(base, day_offset=180)
    second = simulate_book(base, day_offset=180)

    assert first == second
    assert base == fresh_base


def _fixture_model(account_id: str):
    data = sweep_fixture_data(tenant_id=DEFAULT_TENANT)
    account = next(item for item in data.accounts if item.account_id == account_id)
    company = next(item for item in data.companies if item.company_id == account_id)
    health = next(item for item in data.health_scores if item.account_id == account_id)
    adoption = next(item for item in data.adoption_summaries if item.account_id == account_id)
    entitlements = tuple(item for item in data.entitlements if item.account_id == account_id)
    signals = tuple(item for item in data.usage_signals if item.account_id == account_id)
    plans = tuple(item for item in data.success_plans if item.account_id == account_id)
    return build_customer_value_model(
        account=account,
        company=company,
        health=health,
        adoption=adoption,
        entitlements=entitlements,
        usage_signals=signals,
        success_plans=plans,
    )


def _snapshot_payload(*, health_band: str, health_score: float) -> dict:
    return {
        "health_band": health_band,
        "health_score": health_score,
        "priority_score": 0,
        "priority_factors": (),
        "lifecycle_stage": "onboarding",
        "arr_cents": 0,
    }
