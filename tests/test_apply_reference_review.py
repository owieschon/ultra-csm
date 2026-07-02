"""Mechanical reference-review application."""

from __future__ import annotations

import json

from eval.apply_reference_review import APPROVED_LABELER, apply_reference_review


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_apply_reference_review_updates_clean_and_hard_references(tmp_path):
    review_path = tmp_path / "review.json"
    clean_path = tmp_path / "clean.jsonl"
    hard_key_path = tmp_path / "hard_key.jsonl"
    report_path = tmp_path / "apply_report.json"
    review_path.write_text(
        json.dumps(
            {
                "cards": [
                    {
                        "candidate_id": "clean-1",
                        "dimension": "grounding_fidelity",
                        "layer": "clean",
                        "owner_review": {
                            "bucket": "reference_stale",
                            "final_reference_score": 1,
                        },
                    },
                    {
                        "candidate_id": "hard-1",
                        "dimension": "tone_fit",
                        "layer": "hard",
                        "owner_review": {
                            "bucket": "judge_error",
                            "final_reference_score": 1,
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    _write_jsonl(
        clean_path,
        [
            {
                "candidate_id": "clean-1",
                "human_labels": {
                    "candidate_id": "clean-1",
                    "dimension_scores": {
                        "account_specificity": 3,
                        "grounding_fidelity": 3,
                        "on_task_relevance": 3,
                        "priority_fidelity": 3,
                        "safety_boundary": 3,
                        "tone_fit": 3,
                    },
                    "labeler": "provisional-pending-review",
                    "overall_pass": True,
                },
            }
        ],
    )
    _write_jsonl(
        hard_key_path,
        [
            {
                "candidate_id": "hard-1",
                "expected_vector": {
                    "account_specificity": 3,
                    "grounding_fidelity": 3,
                    "on_task_relevance": 3,
                    "priority_fidelity": 3,
                    "safety_boundary": 3,
                    "tone_fit": 3,
                },
                "intended_failing_dimensions": [],
            }
        ],
    )

    report = apply_reference_review(
        review_path=review_path,
        clean_path=clean_path,
        hard_key_path=hard_key_path,
        report_path=report_path,
    )

    clean = _read_jsonl(clean_path)[0]
    hard = _read_jsonl(hard_key_path)[0]
    assert clean["human_labels"]["dimension_scores"]["grounding_fidelity"] == 1
    assert clean["human_labels"]["labeler"] == APPROVED_LABELER
    assert clean["human_labels"]["overall_pass"] is False
    assert hard["expected_vector"]["tone_fit"] == 1
    assert hard["intended_failing_dimensions"] == ["tone_fit"]
    assert report["changed_cells"] == 2
    assert json.loads(report_path.read_text(encoding="utf-8"))["total_cells"] == 2
