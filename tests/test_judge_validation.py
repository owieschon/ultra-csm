"""Judge-validation claim is derived from evidence artifacts, never hand-flipped."""

from __future__ import annotations

import json
from pathlib import Path

from eval.judge_validation import (
    AGREEMENT_PATH,
    COMPARE_PATH,
    GATE_KAPPA,
    judge_validation_status,
)
from eval.judge_csm import PASSING_SCORE, QUALITY_DIMENSIONS


def _copy(tmp_path: Path) -> tuple[Path, Path]:
    agreement = tmp_path / "judge_agreement.json"
    compare = tmp_path / "judge_compare.json"
    agreement.write_text(AGREEMENT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    compare.write_text(COMPARE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return agreement, compare


def test_validates_from_committed_evidence_artifacts():
    status = judge_validation_status()

    assert status["validated"] is True
    assert status["failures"] == []
    assert status["method"]["judge_prompt_version"] == "quality-judge-v7"
    assert status["method"]["runs_per_case"] >= 3
    for dim in QUALITY_DIMENSIONS:
        assert status["hard"]["per_dimension_kappa_aggregated"][dim] >= GATE_KAPPA
        assert status["clean"]["per_dimension_kappa"][dim] >= GATE_KAPPA
    assert status["clean"]["false_neg"] == 0


def test_missing_evidence_fails_closed(tmp_path):
    status = judge_validation_status(
        agreement_path=tmp_path / "absent_agreement.json",
        compare_path=tmp_path / "absent_compare.json",
    )

    assert status["validated"] is False
    assert any("missing evidence artifact" in f for f in status["failures"])


def test_subgate_clean_kappa_fails_closed(tmp_path):
    agreement, compare = _copy(tmp_path)
    payload = json.loads(agreement.read_text(encoding="utf-8"))
    payload["clean_layer"]["per_dimension_kappa"]["grounding_fidelity"] = 0.4
    agreement.write_text(json.dumps(payload), encoding="utf-8")

    status = judge_validation_status(agreement_path=agreement, compare_path=compare)

    assert status["validated"] is False
    assert any("clean grounding_fidelity" in f for f in status["failures"])


def test_hard_kappa_is_recomputed_not_read_from_summary(tmp_path):
    # Corrupt the per-case aggregated vectors: the module must recompute kappa from
    # them and fail, even though no stored summary number was touched.
    agreement, compare = _copy(tmp_path)
    payload = json.loads(compare.read_text(encoding="utf-8"))
    for case in payload["arms"]["cot@N"]["cases"]:
        case["agg"]["vector"]["on_task_relevance"] = 3
    compare.write_text(json.dumps(payload), encoding="utf-8")

    status = judge_validation_status(agreement_path=agreement, compare_path=compare)

    assert status["validated"] is False
    assert any("hard on_task_relevance" in f or "false negatives" in f for f in status["failures"])


def test_aggregated_false_negative_fails_closed(tmp_path):
    # Force one hard case to an all-pass aggregate while its key says fail.
    agreement, compare = _copy(tmp_path)
    payload = json.loads(compare.read_text(encoding="utf-8"))
    cases = payload["arms"]["cot@N"]["cases"]
    failing = next(
        c for c in cases
        if not all(c["reference"][d] >= PASSING_SCORE for d in QUALITY_DIMENSIONS)
    )
    failing["agg"]["vector"] = {d: 3 for d in QUALITY_DIMENSIONS}
    compare.write_text(json.dumps(payload), encoding="utf-8")

    status = judge_validation_status(agreement_path=agreement, compare_path=compare)

    assert status["validated"] is False
    assert any("false negatives" in f for f in status["failures"])
