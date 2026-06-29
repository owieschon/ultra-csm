"""Agent 1 stochastic skeleton artifact tests."""

from __future__ import annotations

import pytest

from eval.stochastic_csm import (
    ARTIFACT_LABEL,
    SELECTED_AGENT1_CASE_IDS,
    build_stochastic_report,
    wilson_pass_rate_band,
)


def test_wilson_pass_rate_band_math_is_pinned():
    band = wilson_pass_rate_band(8, 10)

    assert band == {
        "method": "wilson_score_interval_95",
        "passed": 8,
        "total": 10,
        "point": 0.8,
        "lower": 0.4902,
        "upper": 0.9433,
    }


def test_stochastic_skeleton_has_selected_cases_n_runs_and_artifact_shape():
    artifact = build_stochastic_report(n_runs=3)

    assert artifact["label"] == ARTIFACT_LABEL
    assert artifact["mode"] == "offline"
    assert artifact["selected_case_ids"] == list(SELECTED_AGENT1_CASE_IDS)
    assert artifact["runs_per_case"] == 3
    assert artifact["book_sweep_surface"]["hard_gate"] == "H_reproducible"
    assert artifact["book_sweep_surface"]["priority_scope"].startswith("deterministic")
    assert artifact["live_extension"]["enabled"] is False
    assert artifact["live_extension"]["requires_credentials"] is True
    assert "not claimed" in artifact["measurement_scope"]

    assert len(artifact["cases"]) == len(SELECTED_AGENT1_CASE_IDS)
    for case in artifact["cases"]:
        assert case["case_id"] in SELECTED_AGENT1_CASE_IDS
        assert len(case["runs"]) == 3
        assert case["summary"]["pass_rate_band"]["point"] == 1.0
        assert all(run["passed"] is True for run in case["runs"])
        assert all(run["latency_ms"] == 0 for run in case["runs"])
        assert all(run["cost_usd"] == 0.0 for run in case["runs"])


def test_stochastic_skeleton_aggregate_pass_rate_band_counts_all_runs():
    artifact = build_stochastic_report(n_runs=4)

    assert artifact["pass_rate_band"]["passed"] == len(SELECTED_AGENT1_CASE_IDS) * 4
    assert artifact["pass_rate_band"]["total"] == len(SELECTED_AGENT1_CASE_IDS) * 4
    assert artifact["pass_rate_band"]["point"] == 1.0
    assert artifact["shipping_band"]["minimum_lower_bound"] == 0.7


def test_stochastic_skeleton_rejects_invalid_or_live_parameters():
    with pytest.raises(ValueError):
        build_stochastic_report(n_runs=0)

    with pytest.raises(NotImplementedError):
        build_stochastic_report(mode="live")
