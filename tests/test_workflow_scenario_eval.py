from __future__ import annotations

from ultra_csm.workflow_scenario_eval import (
    run_synthetic_workflow_scenario,
    run_synthetic_workflow_scenario_report,
    synthetic_adoption_regression_scenarios,
    synthetic_self_serve_activation_scenarios,
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


def test_self_serve_activation_scenarios_pass_against_workflow_fixture_conventions():
    scenarios = synthetic_self_serve_activation_scenarios()

    report = run_synthetic_workflow_scenario_report(
        scenarios,
        generated_at="2026-07-08T00:00:00+00:00",
    )

    assert report.passed is True
    assert {item["scenario"]["scenario_id"] for item in report.to_dict()["results"]} == {
        "self_serve_team_first_value_reached",
        "self_serve_activity_without_first_value",
        "self_serve_crm_interest_routes_internal_expansion",
        "self_serve_personal_email_suppresses_org_outreach",
        "self_serve_missing_telemetry_blocks_activation_judgment",
        "self_serve_no_consent_suppresses_customer_output",
    }


def test_self_serve_first_value_requires_path_specific_milestone_not_activity_volume():
    scenario = next(
        item for item in synthetic_self_serve_activation_scenarios()
        if item.scenario_id == "self_serve_activity_without_first_value"
    )

    result = run_synthetic_workflow_scenario(scenario)

    assert result.passed is True
    assert result.packet["status"] == "ready"
    assert result.packet["value_path"]["path_id"] == "solo_evaluator"
    assert result.packet["value_path"]["first_value_definition"]
    assert result.packet["value_path"]["first_value_reached"] is False
    assert "setup" in result.packet["value_path"]["completed_milestone_ids"]
    assert "habit" in result.packet["value_path"]["completed_milestone_ids"]
    assert result.packet["recommended_action"]["action_type"] == "send_activation_nudge"
    assert result.packet["customer_language"] is not None


def test_self_serve_crm_interest_routes_to_internal_expansion_review():
    scenario = next(
        item for item in synthetic_self_serve_activation_scenarios()
        if item.scenario_id == "self_serve_crm_interest_routes_internal_expansion"
    )

    result = run_synthetic_workflow_scenario(scenario)

    assert result.passed is True
    assert result.packet["status"] == "internal_only"
    assert result.packet["value_path"]["path_id"] == "crm_enterprise_curious"
    assert result.packet["recommended_action"]["action_type"] == "internal_only_packet"
    assert result.packet["recommended_action"]["trigger"] == "strong_signal_but_unsafe_customer_action"
    assert "customer_outreach_requires_sales_assisted_review" in (
        result.packet["recommended_action"]["suppression_reasons"]
    )
    assert result.packet["customer_language"] is None


def test_self_serve_unsafe_identity_or_consent_states_suppress_customer_output():
    scenarios = {
        item.scenario_id: item
        for item in synthetic_self_serve_activation_scenarios()
    }

    personal = run_synthetic_workflow_scenario(
        scenarios["self_serve_personal_email_suppresses_org_outreach"]
    )
    no_consent = run_synthetic_workflow_scenario(
        scenarios["self_serve_no_consent_suppresses_customer_output"]
    )

    assert personal.passed is True
    assert personal.packet["identity_resolution"]["personal_email_domain"] is True
    assert "personal_email_domain_suppresses_org_outreach" in (
        personal.packet["coverage"]["customer_output_blockers"]
    )
    assert personal.packet["customer_language"] is None

    assert no_consent.passed is True
    assert "no_consented_contact_for_customer_outreach" in (
        no_consent.packet["coverage"]["customer_output_blockers"]
    )
    assert no_consent.packet["customer_language"] is None


def test_self_serve_missing_telemetry_fails_closed_before_activation_judgment():
    scenario = next(
        item for item in synthetic_self_serve_activation_scenarios()
        if item.scenario_id == "self_serve_missing_telemetry_blocks_activation_judgment"
    )

    result = run_synthetic_workflow_scenario(scenario)

    assert result.passed is True
    assert result.packet["status"] == "needs_data"
    assert "product_telemetry" in result.packet["coverage"]["missing_required_sources"]
    assert "product_telemetry_required_for_activation_judgment" in (
        result.packet["coverage"]["customer_output_blockers"]
    )
    assert result.packet["customer_language"] is None
