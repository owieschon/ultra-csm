from __future__ import annotations

import json

from eval.workflow_scenario_battery import build_workflow_scenario_battery_artifact


def test_workflow_scenario_battery_hard_ok(tmp_path):
    artifact = build_workflow_scenario_battery_artifact(
        output_path=tmp_path / "workflow_scenario_battery.json"
    )

    assert artifact["artifact"] == "workflow_scenario_battery"
    assert artifact["hard_ok"] is True
    assert artifact["score"] == {"passed": 9, "total": 9}
    assert artifact["hard_failures"] == []
    assert {case["scenario_id"] for case in artifact["cases"]} == {
        "fleetops_aspenridge_silent_decline_day340",
        "fleetops_aspenridge_no_shift_control_day90",
        "fleetops_aspenridge_missing_current_window",
        "self_serve_team_first_value_reached",
        "self_serve_activity_without_first_value",
        "self_serve_crm_interest_routes_internal_expansion",
        "self_serve_personal_email_suppresses_org_outreach",
        "self_serve_missing_telemetry_blocks_activation_judgment",
        "self_serve_no_consent_suppresses_customer_output",
    }


def test_workflow_scenario_battery_records_claim_boundary_and_provenance(tmp_path):
    artifact = build_workflow_scenario_battery_artifact(
        output_path=tmp_path / "workflow_scenario_battery.json"
    )

    assert artifact["claim_boundary"] == {
        "fixture": True,
        "synthetic_universe": True,
        "workflow_fixture_conventions": True,
        "live": False,
        "llm_judge": False,
        "network": False,
    }
    assert artifact["ground_truth_sources"] == (
        "docs/SYNTHETIC_UNIVERSE_BIBLE.md",
        "docs/UNIVERSE_V2_CONVENTIONS.md",
        "eval/gold/fleetops_expected_actions.json",
        "src/ultra_csm/workflow_playbooks.py",
        "tests/test_self_serve_activation_workflow.py",
    )
    assert "Bible/conventions own world truth" in artifact["anti_goodhart_rule"]
    assert "No live connectors, LLM calls, or customer writes" in artifact["measurement_scope"]


def test_workflow_scenario_battery_summarizes_path_and_identity_behavior(tmp_path):
    artifact = build_workflow_scenario_battery_artifact(
        output_path=tmp_path / "workflow_scenario_battery.json"
    )
    cases = {case["scenario_id"]: case for case in artifact["cases"]}

    activity = cases["self_serve_activity_without_first_value"]["observed"]
    assert activity["value_path"] == "solo_evaluator"
    assert activity["first_value_reached"] is False
    assert activity["recommended_action"] == "send_activation_nudge"
    assert activity["customer_language_present"] is True

    crm = cases["self_serve_crm_interest_routes_internal_expansion"]["observed"]
    assert crm["value_path"] == "crm_enterprise_curious"
    assert crm["recommended_action"] == "internal_only_packet"
    assert crm["trigger"] == "strong_signal_but_unsafe_customer_action"
    assert "customer_outreach_requires_sales_assisted_review" in crm["suppression_reasons"]

    personal = cases["self_serve_personal_email_suppresses_org_outreach"]["observed"]
    assert personal["identity_state"] == "exactly_one"
    assert personal["personal_email_domain"] is True
    assert "personal_email_domain_suppresses_org_outreach" in personal["customer_output_blockers"]


def test_workflow_scenario_battery_two_runs_byte_identical(tmp_path):
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"

    first = build_workflow_scenario_battery_artifact(output_path=first_path)
    second = build_workflow_scenario_battery_artifact(output_path=second_path)

    assert first == second
    assert first_path.read_text(encoding="utf-8") == second_path.read_text(encoding="utf-8")
    json.loads(first_path.read_text(encoding="utf-8"))
