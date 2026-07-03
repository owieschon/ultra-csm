"""Customer value model config and factor tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from ultra_csm.data_plane import ACME_LOGISTICS, sweep_fixture_data
from ultra_csm.data_plane.contracts import AdoptionSummary, UsageSignal
from ultra_csm.value_model import (
    ConfigRule,
    ConfigValidationError,
    MatchPredicate,
    Thresholds,
    ValueModelConfig,
    build_customer_value_model,
    load_value_model_config,
    resolve_thresholds,
)

_DEFAULT = object()


def _thresholds(
    *,
    adoption_floor: float = 0.40,
    depth_floor: float = 0.60,
    seat_penetration_floor: float = 0.50,
    outcome_activity_floor: float = 0.75,
    concentration_ceiling: float = 0.80,
    min_seats_for_risk: int = 5,
) -> Thresholds:
    return Thresholds(
        adoption_floor=adoption_floor,
        depth_floor=depth_floor,
        seat_penetration_floor=seat_penetration_floor,
        outcome_activity_floor=outcome_activity_floor,
        decline_slope=-0.15,
        concentration_ceiling=concentration_ceiling,
        min_threaded_persons=1,
        min_seats_for_risk=min_seats_for_risk,
        activation_window_days=45,
        trend_window_days=30,
        milestone_overdue_points=25,
        days_overdue_points=2,
        days_overdue_cap=40,
        onboarding_activation_gap_points=15,
        success_plan_overdue_points=20,
        health_red_points=30,
        health_yellow_points=15,
        arr_review_floor_cents=15_000_000,
        arr_review_points=5,
    )


def _config(*rules: ConfigRule) -> ValueModelConfig:
    return ValueModelConfig(
        config_version="test-value-config",
        rules=(
            ConfigRule("base_default", (), _thresholds()),
            *rules,
        ),
    )


def _facts(account_id: str = ACME_LOGISTICS):
    data = sweep_fixture_data()
    account = next(item for item in data.accounts if item.account_id == account_id)
    company = next(item for item in data.companies if item.company_id == account_id)
    health = next(item for item in data.health_scores if item.account_id == account_id)
    adoption = next(item for item in data.adoption_summaries if item.account_id == account_id)
    entitlements = tuple(item for item in data.entitlements if item.account_id == account_id)
    signals = tuple(item for item in data.usage_signals if item.account_id == account_id)
    plans = tuple(item for item in data.success_plans if item.account_id == account_id)
    return account, company, health, adoption, entitlements, signals, plans


def _model(
    *,
    adoption: AdoptionSummary | None | object = _DEFAULT,
    config: ValueModelConfig | None = None,
    signals: tuple[UsageSignal, ...] | None = None,
):
    account, company, health, base_adoption, entitlements, base_signals, plans = _facts()
    selected_adoption = base_adoption if adoption is _DEFAULT else adoption
    return build_customer_value_model(
        account=account,
        company=company,
        health=replace(health, band="green"),
        adoption=selected_adoption,
        entitlements=entitlements,
        usage_signals=signals if signals is not None else base_signals,
        success_plans=plans,
        config=config or _config(),
    )


def test_default_config_loads_from_versioned_artifact():
    cfg = load_value_model_config()

    assert cfg.config_version == "value-model-config-v1"
    assert any(not rule.match for rule in cfg.rules)


def test_factor_boundary_below_at_above_for_adoption_floor():
    _, _, _, adoption, *_ = _facts()
    cfg = _config(ConfigRule(
        "strict_adoption",
        (MatchPredicate("account_id", "==", ACME_LOGISTICS),),
        _thresholds(adoption_floor=0.40),
    ))

    below = _model(adoption=replace(adoption, active_users=39, licensed_users=100), config=cfg)
    at = _model(adoption=replace(adoption, active_users=40, licensed_users=100), config=cfg)
    above = _model(adoption=replace(adoption, active_users=41, licensed_users=100), config=cfg)

    assert _factor_names(below) >= {"health_usage_divergence"}
    assert "health_usage_divergence" not in _factor_names(at)
    assert "health_usage_divergence" not in _factor_names(above)


def test_thresholds_resolve_by_criteria():
    account, company, *_ = _facts()
    cfg = _config(
        ConfigRule(
            "high_arr",
            (MatchPredicate("arr_cents", ">=", 15_000_000),),
            _thresholds(adoption_floor=0.60),
        ),
        ConfigRule(
            "low_arr",
            (MatchPredicate("arr_cents", "<", 15_000_000),),
            _thresholds(adoption_floor=0.40),
        ),
    )

    high = resolve_thresholds({
        "account_id": account.account_id,
        "account_name": account.name,
        "owner_id": account.owner_id,
        "industry": account.industry,
        "arr_cents": company.arr_cents,
        "lifecycle_stage": company.lifecycle_stage,
        "status": company.status,
        "current_score": company.current_score,
    }, cfg)
    low = resolve_thresholds({
        "account_id": "low-arr",
        "account_name": "Low ARR",
        "owner_id": "csm",
        "industry": "transportation",
        "arr_cents": 5_000_000,
        "lifecycle_stage": "onboarding",
        "status": "Active",
        "current_score": 70.0,
    }, cfg)

    assert high.rule_name == "high_arr"
    assert low.rule_name == "low_arr"
    assert high.thresholds.adoption_floor == 0.60
    assert low.thresholds.adoption_floor == 0.40


def test_most_specific_rule_wins():
    account, company, *_ = _facts()
    cfg = _config(
        ConfigRule(
            "broad_high_arr",
            (MatchPredicate("arr_cents", ">=", 15_000_000),),
            _thresholds(adoption_floor=0.60),
        ),
        ConfigRule(
            "account_override",
            (
                MatchPredicate("arr_cents", ">=", 15_000_000),
                MatchPredicate("account_id", "==", ACME_LOGISTICS),
            ),
            _thresholds(adoption_floor=0.75),
        ),
    )

    resolved = resolve_thresholds({
        "account_id": account.account_id,
        "account_name": account.name,
        "owner_id": account.owner_id,
        "industry": account.industry,
        "arr_cents": company.arr_cents,
        "lifecycle_stage": company.lifecycle_stage,
        "status": company.status,
        "current_score": company.current_score,
    }, cfg)

    assert resolved.rule_name == "account_override"
    assert resolved.thresholds.adoption_floor == 0.75


def test_no_match_uses_base_default():
    account, company, *_ = _facts()
    cfg = _config(ConfigRule(
        "unmatched",
        (MatchPredicate("arr_cents", ">", 999_000_000),),
        _thresholds(adoption_floor=0.99),
    ))

    resolved = resolve_thresholds({
        "account_id": account.account_id,
        "account_name": account.name,
        "owner_id": account.owner_id,
        "industry": account.industry,
        "arr_cents": company.arr_cents,
        "lifecycle_stage": company.lifecycle_stage,
        "status": company.status,
        "current_score": company.current_score,
    }, cfg)

    assert resolved.rule_name == "base_default"


def test_unknown_field_fails_config_load():
    cfg = _config(ConfigRule(
        "unknown",
        (MatchPredicate("employee_count", ">=", 1000),),
        _thresholds(),
    ))

    with pytest.raises(ConfigValidationError, match="unknown match field"):
        resolve_thresholds({"account_id": ACME_LOGISTICS}, cfg)


def test_value_model_positive_evidence_only_for_missing_adoption():
    model = _model(adoption=None)

    assert model.penetration.state == "unknown"
    assert model.penetration.factors == ()
    assert model.feature_depth.factors == ()
    assert model.divergences == ()


def test_penetration_and_feature_depth_factors_record_resolution():
    model = _model()

    factors = {factor.name: factor for factor in model.ttv_factors}
    assert factors["low_seat_penetration"].config_version == "test-value-config"
    assert factors["low_seat_penetration"].rule_name == "base_default"
    assert factors["low_seat_penetration"].threshold_name == "seat_penetration_floor"
    assert factors["low_seat_penetration"].threshold_value == 0.50
    assert factors["low_seat_penetration"].evidence
    assert factors["feature_depth_gap"].threshold_value == 0.60
    assert factors["feature_depth_gap"].evidence


def test_outcome_not_instrumented_does_not_fabricate_risk_by_itself():
    _, _, _, adoption, *_ = _facts()
    model = _model()
    low_usage = _model(adoption=replace(adoption, active_users=40, licensed_users=100))

    assert model.outcome.realized_state == "not_instrumented"
    assert model.outcome.factors[0].name == "outcome_stated"
    assert model.outcome.factors[0].contribution == 0
    assert model.outcome.factors[0].evidence
    assert "outcome_unknown" not in _factor_names(model)
    assert "usage_outcome_unverified" not in _factor_names(low_usage)


def test_usage_outcome_divergence_requires_high_usage_and_stated_outcome():
    _, _, _, adoption, *_ = _facts()
    model = _model(
        adoption=replace(adoption, active_users=80, licensed_users=100),
        config=_config(ConfigRule(
            "strict_outcome",
            (MatchPredicate("account_id", "==", ACME_LOGISTICS),),
            _thresholds(outcome_activity_floor=0.75),
        )),
    )

    factor = {item.name: item for item in model.divergences}["usage_outcome_unverified"]
    assert factor.value == 0.8
    assert factor.contribution == 18
    assert factor.threshold_name == "outcome_activity_floor"
    assert factor.threshold_value == 0.75
    assert {ref.field for ref in factor.evidence} >= {"active_users", "objectives"}


def test_min_seats_guard_blocks_single_threaded_risk():
    _, _, _, adoption, *_ = _facts()
    low_seat_adoption = replace(adoption, active_users=1, licensed_users=2)
    signal = UsageSignal(
        "person-signal-1",
        ACME_LOGISTICS,
        "person",
        "person-1",
        "sessions",
        10.0,
        "count",
        "2026-06-21T00:00:00Z",
        "product-telemetry:sessions",
    )

    model = _model(adoption=low_seat_adoption, signals=(signal,))

    assert "single_threaded_risk" not in _factor_names(model)


def test_single_threaded_risk_requires_person_grain_usage():
    signal = UsageSignal(
        "person-signal-1",
        ACME_LOGISTICS,
        "person",
        "person-1",
        "sessions",
        10.0,
        "count",
        "2026-06-21T00:00:00Z",
        "product-telemetry:sessions",
    )

    model = _model(signals=(signal,))

    factor = {item.name: item for item in model.divergences}["single_threaded_risk"]
    assert factor.value == 1.0
    assert factor.threshold_name == "concentration_ceiling"
    assert factor.evidence[0].source_id == "person-signal-1"


def test_config_change_changes_factor_firing():
    _, _, _, adoption, *_ = _facts()
    relaxed = _model(
        adoption=replace(adoption, active_users=50, licensed_users=100),
        config=_config(ConfigRule(
            "relaxed",
            (MatchPredicate("account_id", "==", ACME_LOGISTICS),),
            _thresholds(adoption_floor=0.40),
        )),
    )
    strict = _model(
        adoption=replace(adoption, active_users=50, licensed_users=100),
        config=_config(ConfigRule(
            "strict",
            (MatchPredicate("account_id", "==", ACME_LOGISTICS),),
            _thresholds(adoption_floor=0.60),
        )),
    )

    assert "health_usage_divergence" not in _factor_names(relaxed)
    assert "health_usage_divergence" in _factor_names(strict)


def _factor_names(model) -> set[str]:
    return {factor.name for factor in model.ttv_factors}
