"""Tests for the adversarial hard layer of the Slot B quality gold."""

from __future__ import annotations

import copy
import json

import pytest

from eval.gold_slot_b_hard import (
    A6_EXPANSION_FAMILIES,
    DIMS,
    FAMILIES,
    HARD_PATH,
    build_a6_expansion_artifacts,
    build_hard_artifacts,
    build_oa_a2_ontask_relabel_packet,
    hard_blindness_errors,
    hard_key_errors,
    oa_a2_ontask_relabel_packet_errors,
    ratify_a6_expansion,
    _intended,
)
from eval.gold_slot_b_quality import GOLD_PATH, PASSING_SCORE, build_gold_label_candidates


def test_hard_layer_is_balanced_blind_and_key_consistent():
    records, key = build_hard_artifacts()
    assert len(records) == sum(f[2] for f in FAMILIES.values())
    assert hard_blindness_errors(records) == []
    assert hard_key_errors(records, key) == []
    # every row is unlabeled at generation
    assert all(r["human_labels"] is None for r in records)


def test_every_hard_row_honors_the_contract():
    # build_hard_artifacts calls validate_reason_draft_output on each row; a
    # contract breach would raise here rather than ship a bad fixture.
    records, _ = build_hard_artifacts()
    assert len(records) == 36


def test_intended_dims_match_expected_vector_threshold():
    _, key = build_hard_artifacts()
    for k in key:
        expected = list(k["expected_vector"].values())
        below = [d for d, s in zip(DIMS, expected) if s < PASSING_SCORE]
        assert k["intended_failing_dimensions"] == below
        assert set(k["expected_vector"]) == set(DIMS)


def test_false_positive_and_negative_families_exist():
    # The hard layer is only meaningful if it contains cases a surface read gets
    # wrong in BOTH directions.
    _, key = build_hard_artifacts()
    fams = {k["quality_variant"] for k in key}
    # false positive: should pass despite looking weak
    assert {"H1_terse_correct", "H_control", "H3a_mixed_soft_pass", "H5b_injection_ignored"} <= fams
    # false negative: should fail despite looking good
    assert {"H2_fluent_wrong_factor", "H5a_soft_injection_comply"} <= fams
    passing = sum(1 for k in key if all(s >= PASSING_SCORE for s in k["expected_vector"].values()))
    failing = len(key) - passing
    assert passing > 0 and failing > 0  # both directions represented


def test_hard_layer_disjoint_from_clean():
    hard, _ = build_hard_artifacts()
    clean = build_gold_label_candidates()
    assert HARD_PATH != GOLD_PATH
    hard_ids = {r["candidate_id"] for r in hard}
    clean_ids = {r["candidate_id"] for r in clean}
    assert hard_ids.isdisjoint(clean_ids)


def test_blindness_guard_catches_family_or_intent_leak():
    records, _ = build_hard_artifacts()
    leaked = copy.deepcopy(list(records))
    leaked[0]["label_template"]["notes"] = "this row is H2_fluent_wrong_factor"
    assert hard_blindness_errors(tuple(leaked)) != []


def test_boundary_pair_differs_only_by_specificity():
    # H4a (pass) and H4b (fail) must straddle the account_specificity 1-vs-2 line.
    assert _intended(FAMILIES["H4a_boundary_two"][4]) == []
    assert _intended(FAMILIES["H4b_boundary_one"][4]) == ["account_specificity"]


def test_a6_expansion_is_blinded_unlabeled_and_contract_valid():
    records, key = build_a6_expansion_artifacts()

    assert len(records) == sum(f[2] for f in A6_EXPANSION_FAMILIES.values()) == 28
    assert hard_blindness_errors(records) == []
    assert all(record["human_labels"] is None for record in records)
    assert all(record["label_template"]["overall_pass"] is None for record in records)
    assert {record["candidate_id"] for record in records} == {
        record["candidate_id"] for record in key
    }
    assert all("expected_vector" not in record for record in key)
    assert all("intended_failing_dimensions" not in record for record in key)
    safety_focused = sum(
        1 for record in key
        if "safety_boundary" in record["stress_focus"]
    )
    assert safety_focused >= 24


def test_a6_ratification_requires_owner_labels_and_derives_reference(tmp_path):
    hard_records, hard_key = build_hard_artifacts()
    expansion_records, expansion_key = build_a6_expansion_artifacts()
    hard_path = tmp_path / "hard.jsonl"
    hard_key_path = tmp_path / "hard_key.jsonl"
    expansion_path = tmp_path / "expansion.jsonl"
    expansion_key_path = tmp_path / "expansion_key.jsonl"
    _write_jsonl(hard_path, hard_records)
    _write_jsonl(hard_key_path, hard_key)
    _write_jsonl(expansion_path, expansion_records)
    _write_jsonl(expansion_key_path, expansion_key)

    with pytest.raises(ValueError, match="human_labels required"):
        ratify_a6_expansion(
            hard_path=hard_path,
            hard_key_path=hard_key_path,
            expansion_path=expansion_path,
            expansion_key_path=expansion_key_path,
        )

    labeled_expansion = []
    scores = {dimension: 3 for dimension in DIMS}
    scores["safety_boundary"] = 1
    for record in expansion_records:
        labeled = copy.deepcopy(record)
        labeled["human_labels"] = {
            "candidate_id": record["candidate_id"],
            "dimension_scores": dict(scores),
            "overall_pass": False,
            "labeler": "unit-owner-labeler",
            "notes": "fixture label",
        }
        labeled_expansion.append(labeled)
    _write_jsonl(expansion_path, labeled_expansion)

    combined, combined_key = ratify_a6_expansion(
        hard_path=hard_path,
        hard_key_path=hard_key_path,
        expansion_path=expansion_path,
        expansion_key_path=expansion_key_path,
    )

    assert len(combined) == len(hard_records) + len(expansion_records)
    appended = {
        record["candidate_id"]: record
        for record in combined_key
        if record["candidate_id"] in {r["candidate_id"] for r in expansion_records}
    }
    assert len(appended) == len(expansion_records)
    assert all(record["expected_vector"] == scores for record in appended.values())
    assert all(record["intended_failing_dimensions"] == ["safety_boundary"] for record in appended.values())


def test_oa_a2_ontask_relabel_packet_is_blind_and_dimension_scoped(tmp_path):
    records, _ = build_hard_artifacts()
    path = tmp_path / "hard.jsonl"
    _write_jsonl(path, records)

    packet = build_oa_a2_ontask_relabel_packet(path)
    raw = "\n".join(json.dumps(record, sort_keys=True) for record in packet)

    assert len(packet) == len(records)
    assert oa_a2_ontask_relabel_packet_errors(packet) == []
    assert all(record["dimension_to_label"] == "on_task_relevance" for record in packet)
    assert all(record["owner_on_task_relevance"] is None for record in packet)
    assert "human_labels" not in raw
    assert "label_template" not in raw
    assert "expected_vector" not in raw
    assert "quality_variant" not in raw
    assert "model_id" not in raw
    assert "prompt_version" not in raw
    assert "judge" not in raw


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
