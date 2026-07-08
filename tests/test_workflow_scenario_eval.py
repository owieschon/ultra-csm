from __future__ import annotations

from ultra_csm.workflow_scenario_eval import (
    run_synthetic_workflow_scenario,
    run_synthetic_workflow_scenario_report,
    synthetic_adoption_regression_scenarios,
)


def test_synthetic_workflow_scenarios_pass_against_existing_universe():
    scenarios = synthetic_adoption_regression_scenarios()

    report = run_synthetic_workflow_scenario_report(
        scenarios,
        generated_at="2026-07-08T00:00:00+00:00",
    )

    assert report.passed is True
    body = report.to_dict()
    assert body["passed"] is True
    assert {item["scenario"]["scenario_id"] for item in body["results"]} == {
        "fleetops_aspenridge_silent_decline_day340",
        "fleetops_aspenridge_no_shift_control_day90",
        "fleetops_aspenridge_missing_current_window",
    }


def test_silent_decline_scenario_detects_watch_level_shift_without_customer_motion():
    scenario = next(
        item for item in synthetic_adoption_regression_scenarios()
        if item.scenario_id == "fleetops_aspenridge_silent_decline_day340"
    )

    result = run_synthetic_workflow_scenario(scenario)

    assert result.passed is True
    assert result.packet["status"] == "internal_only"
    assert result.packet["interpretation"]["severity"] == "watch"
    assert result.packet["recommended_action"]["action_type"] == "recommend_internal_review"
    assert result.packet["customer_language"] is None
    primary = result.packet["metric_comparisons"][0]
    assert primary["metric_name"] == "daily_active_assets"
    assert primary["drop_ratio"] >= 0.10
    assert primary["drop_ratio"] < 0.20


def test_no_shift_control_is_ignored_not_routed_to_internal_review():
    scenario = next(
        item for item in synthetic_adoption_regression_scenarios()
        if item.scenario_id == "fleetops_aspenridge_no_shift_control_day90"
    )

    result = run_synthetic_workflow_scenario(scenario)

    assert result.passed is True
    assert result.packet["status"] == "ignored"
    assert result.packet["interpretation"]["severity"] == "none"
    assert result.packet["recommended_action"]["action_type"] == "suppress_regression_motion"
    assert result.packet["metric_comparisons"][0]["drop_ratio"] == 0.0


def test_missing_current_window_counterfactual_fails_closed():
    scenario = next(
        item for item in synthetic_adoption_regression_scenarios()
        if item.scenario_id == "fleetops_aspenridge_missing_current_window"
    )

    result = run_synthetic_workflow_scenario(scenario)

    assert result.passed is True
    assert result.packet["status"] == "needs_data"
    assert "current_usage_window" in result.packet["coverage"]["missing_required_sources"]
    assert result.packet["customer_language"] is None
