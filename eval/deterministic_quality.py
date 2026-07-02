"""Deterministic scorers for quality dimensions that do not need model judgment."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

PRIORITY_DIMENSION = "priority_fidelity"
DETERMINISTIC_DIMENSIONS = (PRIORITY_DIMENSION,)

_SCORE_RE = re.compile(r"\bscore(?:\s+of)?\s+(\d{1,3})\b", re.IGNORECASE)
_CONTRADICTORY_PRIORITY_PHRASES = (
    "low concern",
    "tracking well",
    "good shape",
    "path to green is clear",
    "close to fully activated",
)
_PRIORITY_THEME_TERMS = (
    "attention",
    "follow-up",
    "follow up",
    "onboarding",
    "risk",
    "gap",
    "blocker",
    "review",
)


@dataclass(frozen=True)
class DeterministicScore:
    score: int
    reason: str


def deterministic_scores(request: Mapping, output: Mapping) -> dict[str, DeterministicScore]:
    return {
        PRIORITY_DIMENSION: score_priority_fidelity(request, output),
    }


def score_priority_fidelity(request: Mapping, output: Mapping) -> DeterministicScore:
    """Score priority faithfulness from typed request data and rendered reason text.

    The LLM should not decide whether a reason names the real deterministic score
    and factors. This scorer intentionally ignores the customer draft so urgency or
    tone there cannot contaminate priority faithfulness.
    """

    priority = request.get("priority") or {}
    expected_score = priority.get("score")
    factors = tuple(priority.get("factors") or ())
    reason = str(output.get("reason") or "")
    normalized_reason = _normalize(reason)

    score_mentions = [int(match.group(1)) for match in _SCORE_RE.finditer(reason)]
    if score_mentions and expected_score is not None and expected_score not in score_mentions:
        return DeterministicScore(1, "reason states a priority score that does not match request")

    if any(phrase in normalized_reason for phrase in _CONTRADICTORY_PRIORITY_PHRASES):
        return DeterministicScore(1, "reason uses a priority characterization that contradicts an at-risk item")

    factor_hits = [
        factor
        for factor in factors
        if _factor_present(str(factor.get("name") or ""), normalized_reason)
    ]
    has_score = expected_score is not None and expected_score in score_mentions
    if factors and has_score and len(factor_hits) == len(factors):
        return DeterministicScore(3, "reason states the deterministic score and all real priority factors")

    if has_score or factor_hits or _has_priority_theme(normalized_reason):
        return DeterministicScore(2, "reason is directionally priority-related but omits score or factor detail")

    return DeterministicScore(1, "reason does not convey the deterministic priority drivers")


def _factor_present(name: str, normalized_reason: str) -> bool:
    if not name:
        return False
    normalized_name = _normalize(name)
    spaced_name = normalized_name.replace("_", " ")
    return normalized_name in normalized_reason or spaced_name in normalized_reason


def _has_priority_theme(normalized_reason: str) -> bool:
    return any(term in normalized_reason for term in _PRIORITY_THEME_TERMS)


def _normalize(text: str) -> str:
    return text.lower().replace("-", " ")
