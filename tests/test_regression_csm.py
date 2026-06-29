"""Agent 1 two-lane regression artifact tests."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from eval.regression_csm import (
    DEGRADED_PROMPT_MARKER,
    LiveRegressionRequiresCredentials,
    build_baseline,
    build_live_regression_report,
    build_live_model_migration_report,
    build_regression_report,
    paired_mcnemar_report,
    write_regression_report,
)


def test_regression_baseline_contains_exact_spine_and_seeded_distribution():
    baseline = build_baseline()

    assert baseline["artifact"] == "csm_regression_baseline"
    assert baseline["scorecard_score"] == {"passed": 23, "total": 23}
    assert len(baseline["deterministic_spine"]["work_items"]) == 5
    assert len(baseline["deterministic_spine"]["escalations"]) == 1
    assert baseline["distributional_fixture"]["minimum_point_estimate"] == 0.78
    assert "not live model drift evidence" in baseline["measurement_scope"]


def test_regression_report_passes_offline_against_committed_baseline():
    artifact = build_regression_report()

    assert artifact["mode"] == "offline"
    assert artifact["hard_ok"] is True
    assert artifact["deterministic_spine"]["passed"] is True
    assert artifact["distributional_fixture"]["passed"] is True
    assert artifact["distributional_fixture"]["pass_rate_band"]["point"] == 0.8
    assert artifact["live_lane"]["non_determinism_claimed"] is False


def test_regression_report_goes_red_on_planted_distribution_shift():
    artifact = build_regression_report(degraded_distribution=True)

    assert artifact["hard_ok"] is False
    assert artifact["deterministic_spine"]["passed"] is True
    assert artifact["distributional_fixture"]["passed"] is False
    assert "distributional_fixture_regressed" in artifact["hard_failures"]
    assert "missing_evidence_citation" in artifact["distributional_fixture"]["failure_clusters"]


def test_regression_report_is_writable(tmp_path):
    output = tmp_path / "regression_csm.json"

    artifact = write_regression_report(output)

    assert output.exists()
    assert artifact["hard_ok"] is True


def test_live_regression_requires_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(LiveRegressionRequiresCredentials):
        build_live_regression_report(output_path=tmp_path / "live.json")


class _FakeLiveMessages:
    def create(self, **kwargs):
        if DEGRADED_PROMPT_MARKER in kwargs["system"] or "candidate-bad" in kwargs["model"]:
            text = json.dumps({
                "reason": "Degraded output cites [evidence:invented].",
                "cited_evidence_ids": ["invented"],
                "customer_draft": "This should fail validation.",
            })
        else:
            payload = json.loads(kwargs["messages"][0]["content"])
            request = payload["request"]
            evidence_id = request["evidence"][0]["source_id"]
            draft = None
            if request["customer_contact_allowed"]:
                draft = "Hi, can we review activation blockers?"
            text = json.dumps({
                "reason": f"Score {request['priority']['score']} from [evidence:{evidence_id}].",
                "cited_evidence_ids": [evidence_id],
                "customer_draft": draft,
            })
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(input_tokens=50, output_tokens=15),
        )


class _FakeLiveClient:
    def __init__(self):
        self.messages = _FakeLiveMessages()


def test_live_regression_fake_client_captures_normal_green_degraded_red(tmp_path):
    artifact = build_live_regression_report(
        runs_per_case=2,
        output_path=tmp_path / "live.json",
        client_factory=_FakeLiveClient,
    )

    assert artifact["mode"] == "live"
    assert artifact["hard_ok"] is True
    assert artifact["deterministic_spine"]["passed"] is True
    assert artifact["normal_prompt"]["pass_rate_band"]["point"] == 1.0
    assert artifact["degraded_prompt"]["pass_rate_band"]["point"] == 0.0
    assert artifact["degraded_prompt"]["failure_clusters"] == {"unknown_evidence_id": 6}
    assert artifact["band_separation"]["bands_disjoint"] is True
    assert artifact["non_determinism_claimed"] is True
    assert artifact["normal_prompt"]["stores_full_text"] is False


def test_paired_mcnemar_report_detects_candidate_regression():
    pairs = [
        {
            "baseline_passed": True,
            "candidate_passed": False,
        }
        for _ in range(8)
    ]

    report = paired_mcnemar_report(pairs)

    assert report["baseline_pass_candidate_fail"] == 8
    assert report["baseline_fail_candidate_pass"] == 0
    assert report["p_value"] < 0.05
    assert report["verdict"] == "regressed"


def test_live_model_migration_fake_client_uses_paired_comparison(tmp_path):
    artifact = build_live_model_migration_report(
        baseline_model_id="baseline-good",
        candidate_model_id="candidate-bad",
        runs_per_case=3,
        output_path=tmp_path / "migration.json",
        baseline_client_factory=_FakeLiveClient,
        candidate_client_factory=_FakeLiveClient,
    )

    assert artifact["mode"] == "live_model_migration"
    assert artifact["comparison"]["method"] == "McNemar exact paired test"
    assert artifact["comparison"]["verdict"] == "regressed"
    assert artifact["comparison"]["baseline_pass_candidate_fail"] == 9
    assert artifact["comparison"]["baseline_fail_candidate_pass"] == 0
    assert artifact["stores_full_text"] is False
    assert artifact["failure_clusters"]["candidate"] == {"unknown_evidence_id": 9}
