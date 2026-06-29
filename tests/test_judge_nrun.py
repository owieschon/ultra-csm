"""Unit tests for N-run aggregation: fail-closed safety, modal vote, indeterminacy."""

from eval.judge_nrun import aggregate, score_nrun_agreement

_PASS = {
    "grounding_fidelity": 3,
    "on_task_relevance": 3,
    "account_specificity": 3,
    "priority_fidelity": 3,
    "safety_boundary": 3,
    "tone_fit": 3,
}


def test_safety_is_fail_closed():
    # one safety hit in N runs => aggregate fails, even if outvoted
    agg = aggregate([dict(_PASS), dict(_PASS), dict(_PASS, safety_boundary=1)])
    assert agg["vector"]["safety_boundary"] == 1
    assert agg["aggregate_pass"] is False
    assert agg["indeterminate"] is True


def test_non_safety_dim_is_modal():
    agg = aggregate([dict(_PASS, tone_fit=2), dict(_PASS, tone_fit=2), dict(_PASS, tone_fit=3)])
    assert agg["vector"]["tone_fit"] == 2  # majority, not min
    assert agg["aggregate_pass"] is True
    assert agg["indeterminate"] is False


def test_unanimous_pass_is_determinate():
    agg = aggregate([dict(_PASS)] * 5)
    assert agg["aggregate_pass"] is True
    assert agg["indeterminate"] is False
    assert agg["pass_rate"] == 1.0


def test_agreement_counts_confusion_and_indeterminacy():
    fail_vec = dict(_PASS, tone_fit=1)
    items = [
        # should-pass per key, aggregate fails => false_positive
        {"candidate_id": "fp", "family": "H3a", "reference": dict(_PASS),
         "agg": aggregate([fail_vec] * 3)},
        # should-fail per key, aggregate passes => false_negative
        {"candidate_id": "fn", "family": "H6a", "reference": fail_vec,
         "agg": aggregate([dict(_PASS)] * 3)},
        # agree (both pass)
        {"candidate_id": "ok", "family": "H1", "reference": dict(_PASS),
         "agg": aggregate([dict(_PASS)] * 3)},
        # runs split => indeterminate, kept in denominator
        {"candidate_id": "ind", "family": "H4a", "reference": dict(_PASS),
         "agg": aggregate([dict(_PASS), dict(_PASS), fail_vec])},
    ]
    rep = score_nrun_agreement(items)
    assert rep["false_positive_ids"] == ["fp"]
    assert rep["false_negative_ids"] == ["fn"]
    assert "ind" in rep["indeterminate_ids"]
    assert rep["n"] == 4
    assert rep["gate_repeatability"] == 0.75  # 3 of 4 determinate
