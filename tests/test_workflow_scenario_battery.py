from __future__ import annotations

import json

from eval.workflow_scenario_battery import build_workflow_scenario_battery_artifact


def test_workflow_scenario_battery_hard_ok(tmp_path):
    artifact = build_workflow_scenario_battery_artifact(
        output_path=tmp_path / "workflow_scenario_battery.json"
    )

    assert artifact["artifact"] == "workflow_scenario_battery"
    assert artifact["hard_ok"] is True
    assert artifact["score"] == {"passed": 3, "total": 3}
    assert artifact["hard_failures"] == []
    assert {case["scenario_id"] for case in artifact["cases"]} == {
        "fleetops_aspenridge_silent_decline_day340",
        "fleetops_aspenridge_no_shift_control_day90",
        "fleetops_aspenridge_missing_current_window",
    }


def test_workflow_scenario_battery_records_claim_boundary_and_provenance(tmp_path):
    artifact = build_workflow_scenario_battery_artifact(
        output_path=tmp_path / "workflow_scenario_battery.json"
    )

    assert artifact["claim_boundary"] == {
        "fixture": True,
        "synthetic_universe": True,
        "live": False,
        "llm_judge": False,
        "network": False,
    }
    assert artifact["ground_truth_sources"] == (
        "docs/SYNTHETIC_UNIVERSE_BIBLE.md",
        "docs/UNIVERSE_V2_CONVENTIONS.md",
        "eval/gold/fleetops_expected_actions.json",
    )
    assert "Bible/conventions own world truth" in artifact["anti_goodhart_rule"]
    assert "No live connectors, LLM calls, or customer writes" in artifact["measurement_scope"]


def test_workflow_scenario_battery_two_runs_byte_identical(tmp_path):
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"

    first = build_workflow_scenario_battery_artifact(output_path=first_path)
    second = build_workflow_scenario_battery_artifact(output_path=second_path)

    assert first == second
    assert first_path.read_text(encoding="utf-8") == second_path.read_text(encoding="utf-8")
    json.loads(first_path.read_text(encoding="utf-8"))
