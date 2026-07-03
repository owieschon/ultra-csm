"""Deterministic quality scorers."""

from __future__ import annotations

import json
from pathlib import Path

from eval.deterministic_quality import score_priority_fidelity


def _gold_by_variant() -> dict[str, dict]:
    key = {
        record["candidate_id"]: record
        for record in (
            json.loads(line)
            for line in Path("eval/gold/slot_b_quality_key.jsonl").read_text().splitlines()
        )
    }
    by_variant = {}
    for record in (
        json.loads(line)
        for line in Path("eval/gold/slot_b_quality.jsonl").read_text().splitlines()
    ):
        variant = key[record["candidate_id"]]["quality_variant"]
        by_variant.setdefault(variant, record)
    return by_variant


def test_priority_fidelity_scores_exact_factor_reason_as_three():
    record = _gold_by_variant()["control_good"]

    scored = score_priority_fidelity(record["request"], record["output"])

    assert scored.score == 3
    assert "score and all real priority factors" in scored.reason


def test_priority_fidelity_scores_contradiction_as_one():
    record = _gold_by_variant()["priority_misrepresented"]

    scored = score_priority_fidelity(record["request"], record["output"])

    assert scored.score == 1
    assert "contradicts" in scored.reason


def test_priority_fidelity_scores_theme_without_factors_as_two():
    record = _gold_by_variant()["overstated_urgency"]

    scored = score_priority_fidelity(record["request"], record["output"])

    assert scored.score == 2
    assert "omits score or factor detail" in scored.reason


def test_priority_fidelity_ignores_customer_draft_urgency():
    record = _gold_by_variant()["control_good"]
    output = dict(record["output"])
    output["customer_draft"] = "URGENT: drop everything and meet right now."

    scored = score_priority_fidelity(record["request"], output)

    assert scored.score == 3
