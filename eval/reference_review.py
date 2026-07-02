"""Build the iteration-3 reference review queue from the judge diagnosis report.

This artifact is intentionally non-mutating. It narrows the final review to cells
where the reference may still reflect old anchors while the judge prompt is frozen.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from eval.diagnose_judge import OUT_PATH
from eval.judge_anthropic import JUDGE_PROMPT_VERSION

REFERENCE_REVIEW_PATH = (
    Path(__file__).resolve().parent / "gold" / "reference_review_iteration3.json"
)
DEFAULT_REVIEW_DIMENSIONS = ("grounding_fidelity", "account_specificity", "tone_fit")


def _load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _review_card(row: dict, dimension: str) -> dict:
    disagreement = row["disagree_dims"][dimension]
    return {
        "candidate_id": row["candidate_id"],
        "layer": row["layer"],
        "family": row.get("family"),
        "dimension": dimension,
        "current_reference": disagreement["reference"],
        "judge_score": disagreement["judge"],
        "judge_reason": disagreement.get("judge_reason", ""),
        "request": row["request"],
        "output": row["output"],
        "owner_review": {
            "final_reference_score": None,
            "bucket": None,
            "notes": "",
        },
    }


def build_reference_review(
    report: dict,
    *,
    dimensions: tuple[str, ...] = DEFAULT_REVIEW_DIMENSIONS,
) -> dict:
    cards = []
    counts: Counter[str] = Counter()
    for row in report.get("review_rows", ()):
        for dimension in dimensions:
            if dimension not in row.get("disagree_dims", {}):
                continue
            cards.append(_review_card(row, dimension))
            counts[dimension] += 1

    return {
        "artifact": "slot_b_iteration3_reference_review",
        "source_report": str(OUT_PATH),
        "judge_prompt_version": report.get("judge_prompt_version", JUDGE_PROMPT_VERSION),
        "review_dimensions": list(dimensions),
        "total_cells": len(cards),
        "cells_by_dimension": dict(sorted(counts.items())),
        "claim_boundary": {
            "judge_prompt_frozen": True,
            "reference_review_only": True,
            "label_values_mutated": False,
            "judge_validated": False,
        },
        "instructions": [
            "Score each cell under the ratified D1/D3 anchors.",
            "Do not change judge prompts during this pass.",
            "Use owner_review.final_reference_score for the approved reference value.",
        ],
        "cards": cards,
    }


def _parse_dimensions(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(OUT_PATH))
    parser.add_argument("--output", default=str(REFERENCE_REVIEW_PATH))
    parser.add_argument(
        "--dimensions",
        default=",".join(DEFAULT_REVIEW_DIMENSIONS),
        help="Comma-separated dimensions to include in the reference review queue.",
    )
    args = parser.parse_args(argv)

    report = _load_report(Path(args.input))
    artifact = build_reference_review(
        report,
        dimensions=_parse_dimensions(args.dimensions),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "reference review: "
        f"{artifact['total_cells']} cells "
        f"dimensions={','.join(artifact['review_dimensions'])} -> {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
