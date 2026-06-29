"""Synthetic Agent 1 outcome-simulation artifact tests."""

from __future__ import annotations

import json

from eval.outcome_simulation_csm import ARTIFACT_LABEL, build_outcome_simulation
from ultra_csm.data_plane import ACME_LOGISTICS, build_fixture_data_plane


def test_outcome_simulation_is_labeled_synthetic_not_customer_evidence():
    artifact = build_outcome_simulation()

    assert artifact["label"] == ARTIFACT_LABEL
    assert "synthetic" in artifact["label"]
    assert "not real customer outcome evidence" in artifact["label"]
    assert artifact["aggregate"]["claim"] == "not_real_customer_outcome_evidence"
    assert artifact["fixture_source"] == "src/ultra_csm/data_plane/fixtures.py"


def test_outcome_simulation_uses_current_data_plane_fixture_evidence():
    plane = build_fixture_data_plane()
    artifact = build_outcome_simulation(data_plane=plane)
    scenarios = {scenario["milestone"]: scenario for scenario in artifact["scenarios"]}

    activation = scenarios["activate_50_percent_of_assets"]
    fixture_signal_ids = {
        signal.signal_id
        for signal in plane.telemetry.list_usage_signals(ACME_LOGISTICS)
    }
    evidence_ids = set(activation["evidence"]["usage_signal_ids"])

    assert activation["account_id"] == ACME_LOGISTICS
    assert activation["evidence"]["health_score"] == 62.0
    assert activation["evidence"]["adoption_rate"] == 0.40
    assert activation["evidence"]["open_case_ids"]
    assert evidence_ids
    assert evidence_ids <= fixture_signal_ids
    assert activation["baseline_agent_1_behavior"]["estimated_days_to_value"] == 66
    assert activation["evidence"]["usage_metrics"][0]["source_ref"].startswith(
        "product-telemetry:"
    )


def test_outcome_simulation_compares_baseline_and_improved_agent1_ttv():
    artifact = build_outcome_simulation()

    assert artifact["aggregate"]["scenario_count"] == 2
    assert artifact["aggregate"]["synthetic_baseline_mean_days_to_value"] == 69.5
    assert artifact["aggregate"]["synthetic_improved_mean_days_to_value"] == 56.5
    assert artifact["aggregate"]["synthetic_delta_days"] == 13.0

    for scenario in artifact["scenarios"]:
        baseline = scenario["baseline_agent_1_behavior"]
        improved = scenario["improved_agent_1_behavior"]
        assert baseline["policy"] == "weekly_manual_review_after_gap"
        assert improved["policy"] == "evidence_triggered_ttv_accelerator"
        assert baseline["estimated_days_to_value"] > improved["estimated_days_to_value"]
        assert scenario["synthetic_delta_days"] > 0
        assert scenario["outcome_claim"] == "synthetic_counterfactual_not_real_customer_lift"


def test_outcome_simulation_can_use_book_sweep_work_queue(tmp_path):
    queue = {
        "work_items": [
            {
                "disposition": "propose_customer_action",
                "priority": {"score": 135},
            },
            {
                "disposition": "internal_review",
                "priority": {"score": 82},
            },
        ],
        "escalations": [{"disposition": "escalate"}],
    }
    path = tmp_path / "csm_work_queue.json"
    path.write_text(json.dumps(queue))

    artifact = build_outcome_simulation(work_queue_path=path)
    projection = artifact["book_level_projection"]

    assert projection["source"] == str(path)
    assert projection["work_item_count"] == 2
    assert projection["proposed_action_count"] == 1
    assert projection["internal_review_count"] == 1
    assert projection["escalation_count"] == 1
    assert projection["synthetic_projected_ttv_days_saved"] == 21
    assert projection["claim"] == "synthetic_book_level_projection_not_real_customer_lift"
