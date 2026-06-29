"""Tests for the adversarial hard layer of the Slot B quality gold."""

from __future__ import annotations

import copy

from eval.gold_slot_b_hard import (
    DIMS,
    FAMILIES,
    HARD_PATH,
    build_hard_artifacts,
    hard_blindness_errors,
    hard_key_errors,
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
