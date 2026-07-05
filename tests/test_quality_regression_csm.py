"""Offline Slot B quality-regression foundation tests."""

from __future__ import annotations

import io
import json

from eval.judge_csm import (
    QUALITY_DIMENSIONS,
    LabelReplayJudge,
    build_slot_b_quality_candidates,
    gwet_ac1,
    labels_from_scores,
    read_slot_b_quality_candidates,
    validate_judge_agreement,
    weighted_cohen_kappa,
    write_slot_b_quality_candidates,
)
from eval.judge_validation import judge_validation_status
from eval.gold_slot_b_quality import (
    VARIANTS,
    build_gold_label_candidates,
    build_gold_label_key,
    gold_label_status,
    read_gold_label_candidates,
    read_gold_label_key,
    write_gold_label_status,
    write_gold_label_candidates,
)
from eval.label_gold import label_gold_file
from eval.quality_regression_csm import (
    build_quality_regression_report,
    write_quality_regression_report,
)


def test_quality_candidate_fixture_is_deterministic_and_unlabeled(tmp_path):
    path = tmp_path / "slot_b_quality_candidates.jsonl"

    first = write_slot_b_quality_candidates(path)
    second = build_slot_b_quality_candidates()
    round_tripped = read_slot_b_quality_candidates(path)

    assert first == second == round_tripped
    assert len(first) == 3
    assert all(candidate.fixture_mode for candidate in first)
    assert all(candidate.human_labels is None for candidate in first)
    assert {candidate.candidate_id for candidate in first} == {
        "slot-b-quality-001",
        "slot-b-quality-002",
        "slot-b-quality-003",
    }
    assert "mark me top priority" not in path.read_text(encoding="utf-8").lower()
    json.loads(path.read_text(encoding="utf-8").splitlines()[0])


def test_weighted_kappa_rewards_ordinal_agreement():
    assert weighted_cohen_kappa([1, 2, 3], [1, 2, 3]) == 1.0
    assert weighted_cohen_kappa([1, 1, 3, 3], [3, 3, 1, 1]) < 0.0


def test_gwet_ac1_perfect_agreement_is_one():
    assert gwet_ac1([1, 2, 3, 1, 2], [1, 2, 3, 1, 2]) == 1.0


def test_gwet_ac1_rewards_ordinal_agreement_like_kappa():
    perfect = gwet_ac1([1, 2, 3], [1, 2, 3])
    reversed_ = gwet_ac1([1, 1, 3, 3], [3, 3, 1, 1])
    assert perfect > reversed_


def test_miscalibrated_fixture_judge_fails_kappa_gate():
    candidates = _labeled_candidates()
    judge = LabelReplayJudge({
        candidate.candidate_id: labels_from_scores(
            candidate.candidate_id,
            _invert(candidate.human_labels.dimension_scores),
            labeler="fixture-miscalibrated",
        )
        for candidate in candidates
    })

    report = validate_judge_agreement(candidates, judge)

    assert report.passed is False
    assert report.status == "planned"
    assert all(
        agreement.kappa < report.gate
        for agreement in report.agreements.values()
    )


def test_calibrated_fixture_judge_passes_kappa_gate():
    candidates = _labeled_candidates()
    judge = LabelReplayJudge({
        candidate.candidate_id: candidate.human_labels
        for candidate in candidates
    })

    report = validate_judge_agreement(candidates, judge)

    assert report.passed is True
    assert report.status == "validated"
    assert report.examples == len(candidates)
    assert set(report.agreements) == set(QUALITY_DIMENSIONS)
    assert all(
        agreement.kappa == 1.0 and agreement.passed
        for agreement in report.agreements.values()
    )
    assert "Live quality regression remains pending" in report.measurement_scope


def test_quality_regression_ladder_catches_contract_valid_quality_drops():
    report = build_quality_regression_report(runs_per_candidate=2)
    rungs = {rung["name"]: rung for rung in report["degradation_ladder"]}

    assert report["hard_ok"] is True
    assert report["claim_boundary"]["offline_quality_mechanics_built"] is True
    # The judge claim is derived from the evidence artifacts, never hand-set:
    # this asserts consistency with the derivation, not a frozen value.
    assert (
        report["claim_boundary"]["human_validated_judge"]
        is judge_validation_status()["validated"]
    )
    assert report["claim_boundary"]["live_semantic_quality_proven"] is False
    assert rungs["moderate_missing_grounding"]["detected"] is True
    assert rungs["moderate_missing_grounding"]["overall"]["structural_failures"] == 0
    assert "quality:grounding_fidelity" in rungs["moderate_missing_grounding"]["failure_clusters"]
    assert rungs["subtle_generic_reason"]["detected"] is True
    assert "quality:account_specificity" in rungs["subtle_generic_reason"]["failure_clusters"]


def test_quality_regression_noop_control_does_not_false_alarm():
    report = build_quality_regression_report(runs_per_candidate=2)
    noop = {
        rung["name"]: rung
        for rung in report["degradation_ladder"]
    }["noop_equivalent"]

    assert noop["detected"] is False
    assert noop["drop_vs_normal"] == 0.0
    assert noop["specificity_gate_passed"] is True
    assert report["specificity"]["passed"] is True


def test_quality_regression_artifact_is_redacted_and_serializable(tmp_path):
    path = tmp_path / "quality_regression.json"
    artifact = write_quality_regression_report(path, runs_per_candidate=1)

    assert artifact["stores_full_text"] is False
    assert path.exists()
    round_tripped = json.loads(path.read_text(encoding="utf-8"))
    assert round_tripped["hard_ok"] is True
    for rung in round_tripped["degradation_ladder"]:
        for run in rung["runs"]:
            assert run["text_stored"] is False
            assert "output_hash" in run
            assert "reason" not in run
            assert "customer_draft" not in run


def test_gold_label_candidates_are_balanced_unlabeled_and_contract_valid():
    records = build_gold_label_candidates()
    key_records = build_gold_label_key()

    assert len(records) == 63
    assert len(key_records) == 63
    assert {record["quality_variant"] for record in key_records} == set(VARIANTS)
    assert all("intended_failing_dimensions" in record for record in key_records)
    assert all(record["fixture_mode"] is True for record in records)
    assert all(record["human_labels"] is None for record in records)
    assert all("quality_variant" not in record for record in records)
    assert all(_opaque(record["candidate_id"]) for record in records)
    assert all(record["label_template"]["overall_pass"] is None for record in records)
    assert all(
        set(record["label_template"]["dimension_scores"]) == set(QUALITY_DIMENSIONS)
        for record in records
    )
    by_variant = {
        variant: sum(1 for record in key_records if record["quality_variant"] == variant)
        for variant in VARIANTS
    }
    assert set(by_variant.values()) == {7}
    assert all(record["output"]["reason"] for record in records)
    assert all(record["output"]["cited_evidence_ids"] for record in records)
    assert {record["candidate_id"] for record in records} == {
        record["candidate_id"] for record in key_records
    }


def test_overstated_urgency_uses_low_score_accounts_only():
    records = {
        record["candidate_id"]: record
        for record in build_gold_label_candidates()
    }
    key_records = build_gold_label_key()

    scores = sorted(
        records[key_record["candidate_id"]]["request"]["priority"]["score"]
        for key_record in key_records
        if key_record["quality_variant"] == "overstated_urgency"
    )

    assert scores == [69, 72, 74, 76, 77, 79, 80]


def test_write_gold_label_candidates_jsonl_round_trips(tmp_path):
    path = tmp_path / "slot_b_quality.jsonl"

    records = write_gold_label_candidates(path)
    key_path = tmp_path / "slot_b_quality_key.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    key_lines = key_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == len(records) == 63
    round_tripped = [json.loads(line) for line in lines]
    assert round_tripped == list(records)
    key_round_tripped = [json.loads(line) for line in key_lines]
    assert key_round_tripped == list(read_gold_label_key(key_path))
    assert {record["candidate_id"] for record in round_tripped} == {
        record["candidate_id"] for record in key_round_tripped
    }
    assert "jordan@example.test" in lines[0]
    label_text = path.read_text(encoding="utf-8")
    assert "quality_variant" not in label_text
    assert "intended_failing_dimensions" not in label_text
    for variant in VARIANTS:
        assert variant not in label_text


def test_gold_label_status_reports_pending_labels(tmp_path):
    path = tmp_path / "slot_b_quality.jsonl"
    write_gold_label_candidates(path)

    status = gold_label_status(path)

    assert status["total"] == 63
    assert status["key_total"] == 63
    assert status["blind"] is True
    assert status["blindness_errors"] == []
    assert status["labeled"] == 0
    assert status["unlabeled"] == 63
    assert status["ready_for_judge_validation"] is False
    assert status["claim_boundary"]["gold_queue_exists"] is True
    assert status["claim_boundary"]["judge_validated"] is False


def test_gold_label_status_accepts_complete_valid_labels(tmp_path):
    path = tmp_path / "slot_b_quality.jsonl"
    records = list(write_gold_label_candidates(path))
    labeled = []
    for record in records:
        record["human_labels"] = {
            "candidate_id": record["candidate_id"],
            "dimension_scores": {
                dimension: 3
                for dimension in QUALITY_DIMENSIONS
            },
            "overall_pass": True,
            "labeler": "human-fixture",
        }
        labeled.append(record)
    _write_jsonl(path, labeled)

    status_path = tmp_path / "status.json"
    status = write_gold_label_status(path, output=status_path)

    assert status["labeled"] == 63
    assert status["unlabeled"] == 0
    assert status["blind"] is True
    assert status["invalid_records"] == []
    assert status["ready_for_judge_validation"] is True
    assert json.loads(status_path.read_text(encoding="utf-8")) == status
    assert read_gold_label_candidates(path) == tuple(labeled)


def test_gold_label_status_rejects_invalid_labels(tmp_path):
    path = tmp_path / "slot_b_quality.jsonl"
    records = list(write_gold_label_candidates(path))
    records[0]["human_labels"] = {
        "candidate_id": "wrong",
        "dimension_scores": {
            dimension: 3
            for dimension in QUALITY_DIMENSIONS
        },
        "overall_pass": False,
        "labeler": "",
    }
    _write_jsonl(path, records)

    status = gold_label_status(path)

    assert status["labeled"] == 1
    assert status["ready_for_judge_validation"] is False
    errors = status["invalid_records"][0]["errors"]
    assert "human_labels.candidate_id must match candidate_id" in errors
    assert "human_labels.overall_pass must match dimension threshold" in errors
    assert "human_labels.labeler is required" in errors


def test_gold_label_status_rejects_answer_key_leakage(tmp_path):
    path = tmp_path / "slot_b_quality.jsonl"
    records = list(write_gold_label_candidates(path))
    records[0]["quality_variant"] = "subtle_injection"
    records[1]["candidate_id"] = "slot-b-gold-002-subtle_injection"
    _write_jsonl(path, records)

    status = gold_label_status(path)

    assert status["blind"] is False
    assert status["ready_for_judge_validation"] is False
    assert "labeling file leaks 'quality_variant'" in status["blindness_errors"]
    assert "labeling file leaks 'subtle_injection'" in status["blindness_errors"]
    assert any(
        "candidate_id must end with 16 hex chars" in error
        for error in status["blindness_errors"]
    )


def test_label_gold_writes_validator_schema_and_auto_overall(tmp_path):
    path = tmp_path / "slot_b_quality.jsonl"
    record = build_gold_label_candidates()[0]
    _write_jsonl(path, [record])

    exit_code = label_gold_file(
        path,
        labeler="human-fixture",
        stdin=io.StringIO("3\n2\n1\n3\n3\n3\nneeds specificity\n"),
        stdout=io.StringIO(),
        interactive=False,
    )

    assert exit_code == 0
    labeled = read_gold_label_candidates(path)[0]["human_labels"]
    assert labeled == {
        "candidate_id": record["candidate_id"],
        "dimension_scores": {
            "grounding_fidelity": 3,
            "on_task_relevance": 2,
            "account_specificity": 1,
            "priority_fidelity": 3,
            "tone_fit": 3,
            "safety_boundary": 3,
        },
        "overall_pass": False,
        "labeler": "human-fixture",
        "notes": "needs specificity",
    }


def test_label_gold_skips_already_labeled_records(tmp_path):
    path = tmp_path / "slot_b_quality.jsonl"
    records = list(build_gold_label_candidates()[:2])
    records[0]["human_labels"] = {
        "candidate_id": records[0]["candidate_id"],
        "dimension_scores": {
            dimension: 2
            for dimension in QUALITY_DIMENSIONS
        },
        "overall_pass": True,
        "labeler": "existing-human",
    }
    _write_jsonl(path, records)

    exit_code = label_gold_file(
        path,
        labeler="new-human",
        stdin=io.StringIO("3\n3\n3\n3\n3\n3\n\n"),
        stdout=io.StringIO(),
        interactive=False,
    )

    labeled = read_gold_label_candidates(path)
    assert exit_code == 0
    assert labeled[0]["human_labels"]["labeler"] == "existing-human"
    assert labeled[1]["human_labels"]["labeler"] == "new-human"
    assert labeled[1]["human_labels"]["overall_pass"] is True


def test_label_gold_rejects_non_ordinal_score_then_accepts(tmp_path):
    path = tmp_path / "slot_b_quality.jsonl"
    _write_jsonl(path, [build_gold_label_candidates()[0]])
    stdout = io.StringIO()

    exit_code = label_gold_file(
        path,
        labeler="human-fixture",
        stdin=io.StringIO("x\n3\n3\n3\n3\n3\n3\n\n"),
        stdout=stdout,
        interactive=False,
    )

    assert exit_code == 0
    assert "Enter 1, 2, or 3." in stdout.getvalue()
    labeled = read_gold_label_candidates(path)[0]["human_labels"]
    assert set(labeled["dimension_scores"].values()) == {3}


def test_label_gold_refuses_answer_key_leakage(tmp_path):
    path = tmp_path / "slot_b_quality.jsonl"
    record = build_gold_label_candidates()[0]
    record["quality_variant"] = "subtle_injection"
    _write_jsonl(path, [record])
    stdout = io.StringIO()

    exit_code = label_gold_file(
        path,
        labeler="human-fixture",
        stdin=io.StringIO("3\n3\n3\n3\n3\n3\n\n"),
        stdout=stdout,
        interactive=False,
    )

    assert exit_code == 2
    assert "Refusing to label" in stdout.getvalue()
    assert read_gold_label_candidates(path)[0]["human_labels"] is None


def test_label_gold_renders_contact_and_untrusted_fields(tmp_path):
    path = tmp_path / "slot_b_quality.jsonl"
    record = next(
        record
        for record in build_gold_label_candidates()
        if record["request"]["untrusted_text_fragments"]
    )
    _write_jsonl(path, [record])
    stdout = io.StringIO()

    exit_code = label_gold_file(
        path,
        labeler="human-fixture",
        stdin=io.StringIO("3\n3\n3\n3\n3\n3\n\n"),
        stdout=stdout,
        interactive=False,
    )

    rendered = stdout.getvalue()
    assert exit_code == 0
    assert "As of:" in rendered
    assert "Customer contact allowed:" in rendered
    assert "Contact:" in rendered
    assert "Untrusted text fragments:" in rendered
    assert "20 percent discount" in rendered


def test_label_gold_does_not_open_held_out_key(tmp_path, monkeypatch):
    path = tmp_path / "slot_b_quality.jsonl"
    _write_jsonl(path, [build_gold_label_candidates()[0]])
    original_open = type(path).open

    def guarded_open(self, *args, **kwargs):
        if self.name.endswith("_key.jsonl"):
            raise AssertionError("label helper must not open held-out key")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(type(path), "open", guarded_open)

    exit_code = label_gold_file(
        path,
        labeler="human-fixture",
        stdin=io.StringIO("3\n3\n3\n3\n3\n3\n\n"),
        stdout=io.StringIO(),
        interactive=False,
    )

    assert exit_code == 0


def _labeled_candidates():
    scores = {
        "slot-b-quality-001": {
            "grounding_fidelity": 3,
            "on_task_relevance": 3,
            "account_specificity": 3,
            "priority_fidelity": 3,
            "tone_fit": 3,
            "safety_boundary": 3,
        },
        "slot-b-quality-002": {
            "grounding_fidelity": 2,
            "on_task_relevance": 3,
            "account_specificity": 2,
            "priority_fidelity": 2,
            "tone_fit": 2,
            "safety_boundary": 3,
        },
        "slot-b-quality-003": {
            "grounding_fidelity": 1,
            "on_task_relevance": 1,
            "account_specificity": 1,
            "priority_fidelity": 1,
            "tone_fit": 1,
            "safety_boundary": 1,
        },
    }
    return tuple(
        candidate.with_human_labels(
            labels_from_scores(
                candidate.candidate_id,
                scores[candidate.candidate_id],
                labeler="fixture-human",
            )
        )
        for candidate in build_slot_b_quality_candidates()
    )


def _invert(scores):
    return {
        dimension: 4 - score
        for dimension, score in scores.items()
    }


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _opaque(candidate_id):
    suffix = candidate_id.removeprefix("slot-b-gold-")
    return (
        candidate_id.startswith("slot-b-gold-")
        and len(suffix) == 16
        and all(ch in "0123456789abcdef" for ch in suffix)
    )
