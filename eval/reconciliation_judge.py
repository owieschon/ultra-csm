"""Standalone judge for the reconciliation agent's LLM output (Harvest 31 /
report 52).

Deliberately NOT wired into ``judge_anthropic.py``'s shared
``QUALITY_DIMENSIONS``/``SlotBQualityCandidate`` infrastructure -- that
enum is tightly coupled to Slot B's ``reason``/``customer_draft`` gold-
label pipeline (report 31's v8 stabilization); extending it for a
different candidate type would risk disturbing gold-label counts for
unrelated artifacts (see ``PROGRESS.md``'s LEDGER #3). This module reuses
``judge_anthropic.py``'s ARCHITECTURAL PATTERN only (a ``_SYSTEM`` prompt,
``_text_from_message``, ``JUDGE_MODEL_ID``) with its own, independent
dimensions and prompt.

One combined judge call per account scores the explanation AND every
candidate divergence together, for live-spend economy under the
dispatch's $25 verification ceiling.
"""

from __future__ import annotations

import json

from ultra_csm.agent1.slot_b import (
    JUDGE_MODEL_ID,
    LIVE_MAX_RETRIES,
    LIVE_TIMEOUT_S,
    _text_from_message,
)

RECONCILIATION_JUDGE_PROMPT_VERSION = "reconciliation-judge-v1"
EXPLANATION_DIMENSIONS = ("explanation_grounding", "explanation_specificity")
HYPOTHESIS_DIMENSIONS = ("hypothesis_grounding", "hypothesis_specificity")
PASSING_SCORE = 2

_SYSTEM = """You are a strict quality grader for a reconciliation agent's output about one customer account. You receive the DETERMINISTIC_SIGNALS the agent was given (ground truth, already verified deterministically), the RAW_EVIDENCE pool it could draw from, and the agent's OUTPUT (an explanation paragraph and zero or more candidate divergences). Score EACH listed item 1, 2, or 3.

- explanation_grounding: score truthfulness of the explanation paragraph only. Score 1 when it states a fact, number, or evidence not present in DETERMINISTIC_SIGNALS. Score 2 when it is technically accurate but overreaches (invented urgency, a conclusion stronger than the evidence supports). Score 3 when faithful.
- explanation_specificity: score whether the explanation names at least one specific signal/evidence detail (a factor name, a metric, an account-specific fact) rather than generic filler. Score 3 for specific, 1 for boilerplate that could describe any account.
- hypothesis_grounding (scored per candidate divergence): score 1 if the claim states something not supported by its OWN cited evidence, or cites an evidence reference not actually present in RAW_EVIDENCE. Score 2 if the evidence is real but the claim's characterization overreaches. Score 3 if the claim is a faithful, narrow reading of its cited evidence.
- hypothesis_specificity (scored per candidate divergence): score 3 if the claim names a specific record/metric/person from its evidence; score 1 if it is a vague, generic-sounding claim.

Return ONLY a JSON object of this exact shape, one entry in "candidates" per candidate divergence in the SAME ORDER as the input (empty list if there are none):

{"explanation": {"explanation_grounding": 1, "explanation_specificity": 1}, "candidates": [{"hypothesis_grounding": 1, "hypothesis_specificity": 1}]}

No prose outside the JSON object."""


def _user_payload(
    deterministic_signals: list[dict],
    raw_evidence: list[dict],
    explanation: str,
    candidates: list[dict],
) -> str:
    return json.dumps(
        {
            "deterministic_signals": deterministic_signals,
            "raw_evidence": raw_evidence,
            "output": {"explanation": explanation, "candidate_divergences": candidates},
        },
        sort_keys=True,
    )


def _parse_scores(
    text: str, *, candidate_count: int,
) -> tuple[dict[str, int], list[dict[str, int]]]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"judge returned no JSON object: {text[:200]!r}")
    data = json.loads(text[start : end + 1])

    explanation_scores: dict[str, int] = {}
    explanation_raw = data.get("explanation", {})
    for dim in EXPLANATION_DIMENSIONS:
        value = explanation_raw.get(dim)
        if value not in (1, 2, 3):
            raise ValueError(f"judge score for {dim} must be 1/2/3, got {value!r}")
        explanation_scores[dim] = int(value)

    candidates_raw = data.get("candidates", [])
    if len(candidates_raw) != candidate_count:
        raise ValueError(
            f"judge returned {len(candidates_raw)} candidate scores, expected {candidate_count}"
        )
    candidate_scores: list[dict[str, int]] = []
    for item in candidates_raw:
        scores: dict[str, int] = {}
        for dim in HYPOTHESIS_DIMENSIONS:
            value = item.get(dim)
            if value not in (1, 2, 3):
                raise ValueError(f"judge score for {dim} must be 1/2/3, got {value!r}")
            scores[dim] = int(value)
        candidate_scores.append(scores)
    return explanation_scores, candidate_scores


def passes(scores: dict[str, int]) -> bool:
    return all(value >= PASSING_SCORE for value in scores.values())


class AnthropicReconciliationJudge:
    """Live judge. Not constructed by the offline battery."""

    def __init__(self, client=None, *, model_id: str | None = None) -> None:
        if client is None:  # pragma: no cover - live lane
            from anthropic import Anthropic

            client = Anthropic(timeout=LIVE_TIMEOUT_S, max_retries=LIVE_MAX_RETRIES)
        self._client = client
        self.model_id = model_id or JUDGE_MODEL_ID

    def score(
        self,
        *,
        deterministic_signals: list[dict],
        raw_evidence: list[dict],
        explanation: str,
        candidates: list[dict],
    ) -> tuple[dict[str, int], list[dict[str, int]]]:
        payload = _user_payload(deterministic_signals, raw_evidence, explanation, candidates)
        msg = self._client.messages.create(
            model=self.model_id,
            max_tokens=500,
            system=_SYSTEM,
            messages=[{"role": "user", "content": payload}],
        )
        return _parse_scores(_text_from_message(msg), candidate_count=len(candidates))
