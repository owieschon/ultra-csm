from __future__ import annotations

from eval.judge_csm import QUALITY_DIMENSIONS
from eval.judge_model_migration import build_migration_report
from eval.judge_nrun import aggregate


def _vector(value: int) -> dict[str, int]:
    return {dim: value for dim in QUALITY_DIMENSIONS}


def _case(candidate_id: str, reference: dict[str, int], vector: dict[str, int]) -> dict:
    return {
        "candidate_id": candidate_id,
        "family": "fixture",
        "reference": reference,
        "agg": aggregate([vector, vector, vector]),
    }


def _compare(cases: list[dict]) -> dict:
    return {
        "model_id": "baseline",
        "judge_prompt_version": "quality-judge-v9",
        "runs_per_case": 3,
        "arms": {
            "cot@N": {
                "n": len(cases),
                "false_neg": 0,
                "false_pos": 0,
                "gate_repeatability": 1.0,
                "indeterminate_ids": [],
                "exact_vector_match": len(cases),
                "cases": cases,
            }
        },
    }


def test_judge_model_migration_blocks_fail_open_increase():
    good = _vector(3)
    bad = _vector(1)
    baseline_cases = [
        _case("good", good, good),
        _case("bad", bad, bad),
    ]
    candidate_cases = [
        _case("good", good, good),
        _case("bad", bad, good),
    ]

    report = build_migration_report(
        baseline_compare=_compare(baseline_cases),
        candidate_arm={"cases": candidate_cases, "n": 2},
        candidate_model_id="candidate",
    )

    assert report["adoption_decision"]["adopt"] is False
    assert any("fail-open false passes increased" in b for b in report["adoption_decision"]["blockers"])
    assert report["comparison"]["overall_pass"]["fail_open_delta"] == 1


def test_judge_model_migration_adopts_when_candidate_matches_baseline():
    cases = [
        _case("good", _vector(3), _vector(3)),
        _case("bad", _vector(1), _vector(1)),
    ]

    report = build_migration_report(
        baseline_compare=_compare(cases),
        candidate_arm={"cases": cases, "n": 2},
        candidate_model_id="candidate",
    )

    assert report["adoption_decision"]["adopt"] is True
    assert report["candidate_hard_gate"]["validated"] is True
    assert report["comparison"]["overall_pass"]["verdict"] == "no-evidence-of-regression"
