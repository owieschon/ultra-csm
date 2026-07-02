"""STATUS.md renderer behavior."""

from __future__ import annotations

import json

from scripts.render_status import render_status, write_status


def test_render_status_uses_artifacts_and_reports_claim_boundary_gap(tmp_path):
    _write_json(
        tmp_path / "eval" / "scorecard_csm.json",
        {
            "hard_ok": True,
            "score": {"passed": 2, "total": 2},
            "hard_failures": [],
            "measurement_scope": "fixture scope",
            "unsafe_placeholder": {"passed": True, "failed_hard_gates": ["H1"]},
        },
    )
    _write_json(
        tmp_path / "eval" / "regression_csm.json",
        {
            "hard_ok": True,
            "mode": "offline",
            "scorecard_score": {"passed": 2, "total": 2},
            "deterministic_spine": {
                "passed": True,
                "comparison": "exact_zero_tolerance",
                "changes": [],
            },
            "live_lane": {
                "status": "not_run",
                "target": "make regression-csm-live",
                "non_determinism_claimed": False,
            },
        },
    )
    _write_json(
        tmp_path / "eval" / "quality_regression_csm.json",
        {
            "hard_ok": True,
            "mode": "offline",
            "normal": {"overall": {"pass_rate_band": {"passed": 3, "total": 3}}},
            "sensitivity": {"passed": True},
            "specificity": {"passed": True},
            "claim_boundary": {"live_semantic_quality_proven": False},
        },
    )
    _write_json(
        tmp_path / "eval" / "gold" / "judge_agreement.json",
        {
            "clean_layer": {
                "n": 4,
                "min_dimension_kappa": 0.7,
                "min_judge_scored_dimension_kappa": 0.7,
            },
            "hard_layer": {
                "n": 4,
                "min_dimension_kappa": 0.8,
                "min_judge_scored_dimension_kappa": 0.8,
            },
            "claim_boundary": {"single_labeler_caveat": True},
        },
    )
    _write_json(
        tmp_path / "eval" / "demo_loop_csm.json",
        {
            "first_sweep": {"swept_accounts": ["a1"], "degraded_items": 1},
            "second_sweep": {"degraded_items": 0},
            "quality_breaker": {"red": {"triggered": True, "state": "open"}},
            "outcomes": [{"source": "sim"}],
            "claim_boundary": {"loop_closed_sim": True, "loop_closed_live": False},
        },
    )
    _write_json(
        tmp_path / "eval" / "deep_vs_shallow_detection.json",
        {"summary": {"deep_only": 1}},
    )
    proof = tmp_path / "docs" / "OPERATING_PROOF.md"
    proof.parent.mkdir(parents=True)
    proof.write_text(
        "Date: 2026-07-02.\n"
        "`eval/deep_vs_shallow_detection.json` currently lacks a `claim_boundary`.\n",
        encoding="utf-8",
    )

    rendered = render_status(tmp_path)

    assert "score=passed=2 total=2" in rendered
    assert "min_dimension_kappa=0.7" in rendered
    assert "Live tenant readiness is not claimed" in rendered
    assert "lacks `claim_boundary`" in rendered
    assert "Proof note date: 2026-07-02" in rendered


def test_write_status_writes_rendered_file(tmp_path):
    target = write_status(tmp_path)

    assert target == tmp_path / "STATUS.md"
    assert target.read_text(encoding="utf-8").startswith("# Ultra CSM Status")


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
