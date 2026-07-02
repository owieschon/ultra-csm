"""Tests for the Anthropic quality judge and the agreement aggregation (no creds)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from eval.judge_csm import QUALITY_DIMENSIONS
from eval.gold_slot_b_quality import _request_specs
from eval.judge_anthropic import AnthropicQualityJudge, _parse_scores, _system_prompt
from eval.run_quality_judge import score_agreement, by_family
from ultra_csm.agent1.slot_b import JUDGE_MODEL_ID


def _vec(g, t, a, p, to, s):
    return dict(zip(QUALITY_DIMENSIONS, [g, t, a, p, to, s]))


class _FakeClient:
    """Returns a fixed JSON body for every messages.create call."""

    def __init__(self, scores: dict):
        self._text = json.dumps(scores)
        self.messages = self

    def create(self, **kwargs):
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self._text)])


def test_parse_scores_accepts_valid_and_rejects_bad():
    good = _vec(3, 3, 3, 3, 3, 3)
    assert _parse_scores("noise " + json.dumps(good) + " trailer") == good
    with pytest.raises(ValueError):
        _parse_scores(json.dumps({**good, "tone_fit": 4}))
    with pytest.raises(ValueError):
        _parse_scores("not json")


def test_parse_scores_accepts_cot_reasoning_shape():
    # CoT mode emits {dim: {"reason": ..., "score": N}}; the parser must read `.score`.
    want = _vec(3, 2, 3, 1, 3, 3)
    cot = {dim: {"reason": "deciding evidence", "score": v} for dim, v in want.items()}
    assert _parse_scores("reasoning... " + json.dumps(cot)) == want
    # an out-of-range nested score is still rejected
    bad = {dim: {"reason": "x", "score": 3} for dim in QUALITY_DIMENSIONS}
    bad["tone_fit"]["score"] = 5
    with pytest.raises(ValueError):
        _parse_scores(json.dumps(bad))


def test_judge_score_output_via_fake_client():
    scores = _vec(1, 2, 3, 1, 3, 3)
    judge = AnthropicQualityJudge(client=_FakeClient(scores), model_id="fake")
    assert judge.score_output({"a": 1}, {"b": 2}) == scores


def test_judge_defaults_to_dedicated_model_id():
    judge = AnthropicQualityJudge(client=_FakeClient(_vec(3, 3, 3, 3, 3, 3)))
    assert judge.model_id == JUDGE_MODEL_ID


def test_judge_prompt_has_no_gold_item_specific_account_names():
    system_prompt = _system_prompt(reasoning=True).lower()

    for spec in _request_specs():
        assert spec["account_name"].lower() not in system_prompt


def test_agreement_perfect_and_inverted():
    items = [
        {"candidate_id": "c1", "reference": _vec(3, 3, 3, 3, 3, 3), "family": "ok"},
        {"candidate_id": "c2", "reference": _vec(1, 2, 3, 1, 3, 3), "family": "bad"},
    ]
    # perfect judge
    for it in items:
        it["judge"] = dict(it["reference"])
    perfect = score_agreement(items)
    assert perfect["exact_vector_match"] == 2
    assert perfect["overall_pass_false_positive"] == 0
    assert perfect["overall_pass_false_negative"] == 0
    assert perfect["min_dimension_kappa"] == 1.0

    # judge that passes the failing case -> false negative; fails the good case -> false positive
    items[0]["judge"] = _vec(1, 3, 3, 3, 3, 3)  # good case judged failing
    items[1]["judge"] = _vec(3, 3, 3, 3, 3, 3)  # bad case judged passing
    flipped = score_agreement(items)
    assert flipped["overall_pass_false_positive"] == 1
    assert flipped["overall_pass_false_negative"] == 1


def test_by_family_counts_pass_match():
    items = [
        {"candidate_id": "c1", "reference": _vec(3, 3, 3, 3, 3, 3), "judge": _vec(3, 3, 3, 3, 3, 3), "family": "H_control"},
        {"candidate_id": "c2", "reference": _vec(1, 2, 3, 1, 3, 3), "judge": _vec(3, 3, 3, 3, 3, 3), "family": "H2_fluent_wrong_factor"},
    ]
    fam = by_family(items)
    assert fam["H_control"]["pass_match"] == 1
    assert fam["H2_fluent_wrong_factor"]["pass_match"] == 0  # judge missed the false-negative
