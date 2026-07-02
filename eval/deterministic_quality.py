"""Deterministic scorers for quality dimensions that do not need model judgment."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

PRIORITY_DIMENSION = "priority_fidelity"
ACCOUNT_SPECIFICITY_DIMENSION = "account_specificity"
ON_TASK_DIMENSION = "on_task_relevance"
TONE_DIMENSION = "tone_fit"

# `priority_fidelity` and `account_specificity` are the dimensions the judge NEVER
# scores — both are fully code-owned (score_priority_fidelity, score_account_specificity),
# decided from the request's own typed factors/names vs the output text, so there is no
# lexicon to game. on_task_relevance and tone_fit stay judge-scored; code only touches
# specific structurally-detectable cells of them via deterministic_assignments (full
# decisions) and quality_floors (down-only traps). They remain in the judge-scored kappa.
DETERMINISTIC_DIMENSIONS = (PRIORITY_DIMENSION, ACCOUNT_SPECIFICITY_DIMENSION)

# --- category lexicons (config-shaped signatures, NOT the two gold phrases) -----
# These are CATEGORY signatures for known failure classes. They must describe the
# register/deferral CATEGORY, never memorize the specific gold strings, or the
# floors would launder the benchmark instead of hardening measurement.
_OFFICIALESE_TERMS = (
    "necessitate",
    "kindly advise",
    "per our records",
    "remediation",
    "corrective action",
    "deficiencies",
    "herewith",
    "aforementioned",
    "pursuant to",
)
_URGENCY_CAPS_RE = re.compile(r"\b(URGENT|ASAP|IMMEDIATE|CRITICAL|EMERGENCY)\b")
_DEFERRAL_TERMS = (
    "keep an eye",
    "touch base",
    "circle back",
    "when things settle",
    "at some point",
    "check back",
    "reach out later",
    "down the road",
    "later if anything changes",
    "no rush",
    "when it's a good time",
)
# A concrete customer ask disqualifies the passive-deferral floor: a real motion
# is present, so the draft is scored by the judge, not floored.
_CONCRETE_ASK_TERMS = (
    "can we review",
    "can we meet",
    "let's meet",
    "meet this week",
    "this week to",
    "schedule",
    "walk through",
    "hop on",
    "review the",
    "next steps this week",
    "find time",
    "grab 20",
    "20 min",
    "confirm timelines",
    "address the",
    "fix it",
)

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
        ACCOUNT_SPECIFICITY_DIMENSION: score_account_specificity(request, output),
    }


def score_account_specificity(request: Mapping, output: Mapping) -> DeterministicScore:
    """Score account specificity from typed request data vs the output text.

    3 = the output names one of THIS request's real priority factors/blockers.
    2 = it is personalized by the account or contact name but names no factor.
    1 = interchangeable boilerplate: neither a factor nor a name of this account.

    Assess the customer draft; for a null draft (internal_review) assess the reason.
    Uses only the request's own factor names and account/contact names — no lexicon —
    so it cannot be gamed and generalizes by construction, like priority.
    """

    draft = output.get("customer_draft")
    text = draft if draft is not None else (output.get("reason") or "")
    normalized = _normalize(str(text))

    factors = tuple((request.get("priority") or {}).get("factors") or ())
    if any(_factor_present(str(factor.get("name") or ""), normalized) for factor in factors):
        return DeterministicScore(3, "output names an account-specific factor/blocker")
    if _name_present(request, normalized):
        return DeterministicScore(2, "personalized by account/contact name but names no factor")
    return DeterministicScore(1, "interchangeable boilerplate: no account-specific detail")


def _name_present(request: Mapping, normalized_text: str) -> bool:
    for key in ("account_name", "contact_name"):
        value = str(request.get(key) or "").lower()
        for token in re.split(r"[^a-z0-9]+", value):
            if len(token) > 2 and re.search(rf"\b{re.escape(token)}\b", normalized_text):
                return True
    return False


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


def _has_any(text: str, terms) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _is_grounded(request: Mapping, output: Mapping) -> bool:
    """Citation check: the output cites evidence ids that are present and real.

    'Real' means every cited id resolves to a source_id actually supplied in the
    request evidence. This is the mechanical precondition for the internal_review
    on_task assignment; a reason with no citation, or one that cites an id absent
    from the request, is not grounded and does not earn the assignment.
    """

    cited = tuple(output.get("cited_evidence_ids") or ())
    if not cited:
        return False
    source_ids = {
        str(item.get("source_id"))
        for item in (request.get("evidence") or ())
        if item.get("source_id")
    }
    return bool(source_ids) and all(str(cid) in source_ids for cid in cited)


def deterministic_assignments(request: Mapping, output: Mapping) -> dict[str, DeterministicScore]:
    """Dimensions fully decided by structure, not judgment — like priority.

    internal_review + a grounded reason + no customer draft IS the output the
    disposition calls for, so on_task_relevance is 3 by definition. This is an
    ASSIGNMENT (it can set any score), distinct from a floor (which only lowers).
    """

    assignments: dict[str, DeterministicScore] = {}
    disposition = request.get("disposition")
    draft = output.get("customer_draft")
    if disposition == "internal_review" and not draft and _is_grounded(request, output):
        assignments[ON_TASK_DIMENSION] = DeterministicScore(
            3, "internal_review with grounded reason and no draft is the correct output"
        )
    return assignments


def quality_floors(request: Mapping, output: Mapping) -> dict[str, DeterministicScore]:
    """Downward-only failure traps. A floor may ONLY force a score to 1 on a
    signature-detected failure; it must never raise a score. The caller applies
    each as min(current, 1). Never add an upward rule here — that would turn the
    safety net into a score inflator.
    """

    floors: dict[str, DeterministicScore] = {}
    draft = str(output.get("customer_draft") or "")
    reason = str(output.get("reason") or "")

    # tone_fit register-failure floor: bureaucratic officialese or all-caps alarm.
    if _has_any(draft, _OFFICIALESE_TERMS):
        floors[TONE_DIMENSION] = DeterministicScore(1, "bureaucratic/officialese register")
    elif _URGENCY_CAPS_RE.search(draft) or _URGENCY_CAPS_RE.search(reason):
        floors[TONE_DIMENSION] = DeterministicScore(1, "all-caps alarm register")

    # on_task_relevance passive-deferral floor: for a customer-action disposition,
    # a draft that defers with no concrete ask proposes no action -> fails the job.
    if request.get("disposition") == "propose_customer_action" and draft:
        if _has_any(draft, _DEFERRAL_TERMS) and not _has_any(draft, _CONCRETE_ASK_TERMS):
            floors[ON_TASK_DIMENSION] = DeterministicScore(
                1, "passive deferral proposes no concrete customer action"
            )

    return floors


def apply_deterministic(
    request: Mapping,
    output: Mapping,
    scores: dict[str, int],
    reasons: dict[str, str] | None = None,
) -> None:
    """Merge code decisions over judge scores, in precedence order, in place.

    1. deterministic_scores  — full override for code-owned dimensions (priority).
    2. deterministic_assignments — structural full decisions (internal_review on_task).
    3. quality_floors — down-only; applied last, and only when they LOWER the score.
    """

    def _set(dim: str, det: DeterministicScore) -> None:
        scores[dim] = det.score
        if reasons is not None:
            reasons[dim] = det.reason

    for dimension, det in deterministic_scores(request, output).items():
        _set(dimension, det)
    for dimension, det in deterministic_assignments(request, output).items():
        _set(dimension, det)
    for dimension, det in quality_floors(request, output).items():
        if scores.get(dimension, det.score + 1) > det.score:
            _set(dimension, det)
