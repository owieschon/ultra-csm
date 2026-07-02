"""Apply owner-approved iteration-3 reference scores.

This is a mechanical transfer from `reference_review_iteration3.json` into the
clean gold labels and hard-layer expected vectors. It has no scoring judgment.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from eval.gold_slot_b_hard import HARD_KEY_PATH
from eval.gold_slot_b_quality import GOLD_PATH
from eval.judge_csm import PASSING_SCORE, QUALITY_DIMENSIONS
from eval.reference_review import REFERENCE_REVIEW_PATH

APPLY_REPORT_PATH = (
    Path(__file__).resolve().parent / "gold" / "reference_review_apply_report.json"
)
APPROVED_LABELER = "owner-approved-single-labeler-2026-07-02"


def _read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def _approved_cards(review: dict) -> list[dict]:
    cards = []
    for card in review.get("cards", ()):
        score = card.get("owner_review", {}).get("final_reference_score")
        if score not in (1, 2, 3):
            raise ValueError(
                f"{card.get('candidate_id')}:{card.get('dimension')} is missing final_reference_score"
            )
        cards.append(card)
    return cards


def _overall_pass(scores: dict[str, int]) -> bool:
    return all(scores[dimension] >= PASSING_SCORE for dimension in QUALITY_DIMENSIONS)


def _intended_failing_dimensions(expected_vector: dict[str, int]) -> list[str]:
    return [
        dimension
        for dimension in QUALITY_DIMENSIONS
        if expected_vector[dimension] < PASSING_SCORE
    ]


def apply_reference_review(
    *,
    review_path: Path = REFERENCE_REVIEW_PATH,
    clean_path: Path = GOLD_PATH,
    hard_key_path: Path = HARD_KEY_PATH,
    report_path: Path = APPLY_REPORT_PATH,
) -> dict:
    review = json.loads(review_path.read_text(encoding="utf-8"))
    cards = _approved_cards(review)
    clean_records = _read_jsonl(clean_path)
    hard_key_records = _read_jsonl(hard_key_path)

    clean_by_id = {record["candidate_id"]: record for record in clean_records}
    hard_by_id = {record["candidate_id"]: record for record in hard_key_records}

    applied_counts: Counter[str] = Counter()
    bucket_counts: Counter[str] = Counter()
    changed_cells = 0
    unchanged_cells = 0

    for card in cards:
        candidate_id = card["candidate_id"]
        dimension = card["dimension"]
        final_score = int(card["owner_review"]["final_reference_score"])
        bucket_counts[str(card["owner_review"].get("bucket"))] += 1

        if card["layer"] == "clean":
            record = clean_by_id[candidate_id]
            labels = record["human_labels"]
            scores = labels["dimension_scores"]
            previous = int(scores[dimension])
            scores[dimension] = final_score
            labels["overall_pass"] = _overall_pass(scores)
            labels["labeler"] = APPROVED_LABELER
        elif card["layer"] == "hard":
            record = hard_by_id[candidate_id]
            scores = record["expected_vector"]
            previous = int(scores[dimension])
            scores[dimension] = final_score
            record["intended_failing_dimensions"] = _intended_failing_dimensions(scores)
        else:
            raise ValueError(f"unknown review layer: {card['layer']!r}")

        applied_counts[f"{card['layer']}:{dimension}"] += 1
        if previous == final_score:
            unchanged_cells += 1
        else:
            changed_cells += 1

    for record in clean_records:
        labels = record.get("human_labels")
        if not labels:
            raise ValueError(f"{record['candidate_id']} is missing human_labels")
        labels["labeler"] = APPROVED_LABELER
        labels["overall_pass"] = _overall_pass(labels["dimension_scores"])

    _write_jsonl(clean_path, clean_records)
    _write_jsonl(hard_key_path, hard_key_records)

    report = {
        "artifact": "slot_b_iteration3_reference_apply_report",
        "review_path": str(review_path),
        "clean_path": str(clean_path),
        "hard_key_path": str(hard_key_path),
        "approved_labeler": APPROVED_LABELER,
        "total_cells": len(cards),
        "changed_cells": changed_cells,
        "unchanged_cells": unchanged_cells,
        "applied_counts": dict(sorted(applied_counts.items())),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "claim_boundary": {
            "mechanical_transfer": True,
            "judge_prompt_changed": False,
            "single_labeler": True,
        },
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", default=str(REFERENCE_REVIEW_PATH))
    parser.add_argument("--clean", default=str(GOLD_PATH))
    parser.add_argument("--hard-key", default=str(HARD_KEY_PATH))
    parser.add_argument("--report", default=str(APPLY_REPORT_PATH))
    args = parser.parse_args(argv)

    report = apply_reference_review(
        review_path=Path(args.review),
        clean_path=Path(args.clean),
        hard_key_path=Path(args.hard_key),
        report_path=Path(args.report),
    )
    print(
        "applied reference review: "
        f"{report['total_cells']} cells "
        f"changed={report['changed_cells']} unchanged={report['unchanged_cells']}"
    )
    print(f"report -> {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
