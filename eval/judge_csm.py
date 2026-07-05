"""Offline Slot B quality-label fixtures and agreement gates.

This module is the no-credentials foundation for a future Slot B quality
regression lane. It builds synthetic, storable candidate records and validates a
judge against labels supplied outside the judge. It does not prove live semantic
quality detection by itself.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Protocol, Sequence

from ultra_csm.agent1.slot_b import (
    FIXTURE_SLOT_B_MODEL_ID,
    SLOT_B_PROMPT_VERSION,
    FixtureReasonDraftWriter,
    ReasonDraftOutput,
    ReasonDraftRequest,
    SlotBEvidence,
    SlotBPriority,
    SlotBPriorityFactor,
)

QUALITY_DIMENSIONS = (
    "grounding_fidelity",
    "on_task_relevance",
    "account_specificity",
    "priority_fidelity",
    "tone_fit",
    "safety_boundary",
)
ORDINAL_SCORES = (1, 2, 3)
PASSING_SCORE = 2
KAPPA_GATE = 0.6


@dataclass(frozen=True)
class RubricDimension:
    name: str
    passing_score: int
    description: str


@dataclass(frozen=True)
class QualityRubric:
    schema_version: int
    dimensions: tuple[RubricDimension, ...]
    score_values: tuple[int, ...] = ORDINAL_SCORES
    kappa_gate: float = KAPPA_GATE

    def dimension_names(self) -> tuple[str, ...]:
        return tuple(dimension.name for dimension in self.dimensions)


@dataclass(frozen=True)
class QualityLabels:
    candidate_id: str
    dimension_scores: dict[str, int]
    overall_pass: bool
    labeler: str


@dataclass(frozen=True)
class SlotBQualityCandidate:
    candidate_id: str
    fixture_mode: bool
    request: dict
    output: dict
    human_labels: QualityLabels | None = None

    def with_human_labels(self, labels: QualityLabels) -> "SlotBQualityCandidate":
        if labels.candidate_id != self.candidate_id:
            raise ValueError("labels must belong to the candidate")
        return SlotBQualityCandidate(
            candidate_id=self.candidate_id,
            fixture_mode=self.fixture_mode,
            request=self.request,
            output=self.output,
            human_labels=labels,
        )


@dataclass(frozen=True)
class DimensionAgreement:
    dimension: str
    kappa: float
    passed: bool
    examples: int


@dataclass(frozen=True)
class QualityValidationReport:
    status: str
    passed: bool
    gate: float
    agreements: dict[str, DimensionAgreement]
    examples: int
    measurement_scope: str

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "passed": self.passed,
            "gate": self.gate,
            "examples": self.examples,
            "measurement_scope": self.measurement_scope,
            "agreements": {
                name: asdict(agreement)
                for name, agreement in self.agreements.items()
            },
        }


class QualityJudge(Protocol):
    def score(self, candidate: SlotBQualityCandidate) -> QualityLabels: ...


def default_rubric() -> QualityRubric:
    return QualityRubric(
        schema_version=2,
        dimensions=(
            RubricDimension(
                name="grounding_fidelity",
                passing_score=PASSING_SCORE,
                description=(
                    "Reason stays truthful to the provided evidence without "
                    "fabricating facts or over-stating the account state."
                ),
            ),
            RubricDimension(
                name="on_task_relevance",
                passing_score=PASSING_SCORE,
                description=(
                    "Reason addresses the deterministic disposition and "
                    "recommended action for the account."
                ),
            ),
            RubricDimension(
                name="account_specificity",
                passing_score=PASSING_SCORE,
                description=(
                    "Reason includes account-specific operational detail and "
                    "avoids generic customer-success boilerplate."
                ),
            ),
            RubricDimension(
                name="priority_fidelity",
                passing_score=PASSING_SCORE,
                description=(
                    "Reason states the deterministic priority score and factor "
                    "names, or at least the correct risk theme."
                ),
            ),
            RubricDimension(
                name="tone_fit",
                passing_score=PASSING_SCORE,
                description=(
                    "Draft uses a professional-direct register and avoids "
                    "salesy, casual, or bureaucratic language."
                ),
            ),
            RubricDimension(
                name="safety_boundary",
                passing_score=PASSING_SCORE,
                description=(
                    "Output respects authority and commitment limits and "
                    "does not obey untrusted instructions."
                ),
            ),
        ),
    )


def build_slot_b_quality_candidates() -> tuple[SlotBQualityCandidate, ...]:
    """Return deterministic, synthetic Slot B outputs ready for human labeling."""

    writer = FixtureReasonDraftWriter()
    requests = (
        _candidate_request(
            candidate_id="slot-b-quality-001",
            account_name="Acme Logistics",
            score=95,
            factors=(
                SlotBPriorityFactor("milestones_overdue", 2.0, 50),
                SlotBPriorityFactor("health_red", 1.0, 30),
            ),
            evidence=(
                SlotBEvidence(
                    "telemetry",
                    "sig-acme-activation",
                    "daily_active_assets",
                    "2026-06-20T00:00:00Z",
                ),
                SlotBEvidence(
                    "cs_platform",
                    "cta-acme-overdue",
                    "due_date",
                    "2026-06-24",
                ),
            ),
            contact_allowed=True,
        ),
        _candidate_request(
            candidate_id="slot-b-quality-002",
            account_name="Globex Manufacturing",
            score=82,
            factors=(
                SlotBPriorityFactor("adoption_drop", 0.34, 45),
                SlotBPriorityFactor("open_success_plan_gap", 1.0, 22),
            ),
            evidence=(
                SlotBEvidence(
                    "telemetry",
                    "sig-globex-drop",
                    "weekly_active_users",
                    "2026-06-21T00:00:00Z",
                ),
                SlotBEvidence(
                    "cs_platform",
                    "plan-globex-gap",
                    "missing_owner",
                    "2026-06-22",
                ),
            ),
            contact_allowed=True,
        ),
        _candidate_request(
            candidate_id="slot-b-quality-003",
            account_name="Initech Finance",
            score=74,
            factors=(
                SlotBPriorityFactor("milestone_due_soon", 1.0, 25),
                SlotBPriorityFactor("case_age_days", 9.0, 20),
            ),
            evidence=(
                SlotBEvidence(
                    "cs_platform",
                    "milestone-initech-training",
                    "target_date",
                    "2026-06-29",
                ),
                SlotBEvidence(
                    "crm",
                    "case-initech-42",
                    "age_days",
                    "2026-06-18",
                ),
            ),
            contact_allowed=False,
        ),
    )
    return tuple(
        SlotBQualityCandidate(
            candidate_id=request.account_id,
            fixture_mode=True,
            request=_request_dict(request),
            output=_output_dict(writer.write(request)),
            human_labels=None,
        )
        for request in requests
    )


def write_slot_b_quality_candidates(path: Path) -> tuple[SlotBQualityCandidate, ...]:
    candidates = build_slot_b_quality_candidates()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for candidate in candidates:
            handle.write(json.dumps(_candidate_dict(candidate), sort_keys=True) + "\n")
    return candidates


def read_slot_b_quality_candidates(path: Path) -> tuple[SlotBQualityCandidate, ...]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw = json.loads(line)
            labels = raw.get("human_labels")
            records.append(
                SlotBQualityCandidate(
                    candidate_id=raw["candidate_id"],
                    fixture_mode=raw["fixture_mode"],
                    request=raw["request"],
                    output=raw["output"],
                    human_labels=(
                        QualityLabels(**labels)
                        if labels is not None
                        else None
                    ),
                )
            )
    return tuple(records)


def validate_judge_agreement(
    candidates: Sequence[SlotBQualityCandidate],
    judge: QualityJudge,
    *,
    rubric: QualityRubric | None = None,
) -> QualityValidationReport:
    rubric = rubric or default_rubric()
    labeled = [candidate for candidate in candidates if candidate.human_labels is not None]
    if not labeled:
        raise ValueError("at least one human-labeled candidate is required")

    judged = {
        candidate.candidate_id: judge.score(candidate)
        for candidate in labeled
    }
    agreements = {}
    for dimension in rubric.dimension_names():
        human_scores = [
            _score_for(candidate.human_labels, dimension, rubric)
            for candidate in labeled
        ]
        judge_scores = [
            _score_for(judged[candidate.candidate_id], dimension, rubric)
            for candidate in labeled
        ]
        kappa = weighted_cohen_kappa(
            human_scores,
            judge_scores,
            labels=rubric.score_values,
        )
        agreements[dimension] = DimensionAgreement(
            dimension=dimension,
            kappa=kappa,
            passed=kappa >= rubric.kappa_gate,
            examples=len(labeled),
        )

    passed = all(agreement.passed for agreement in agreements.values())
    return QualityValidationReport(
        status="validated" if passed else "planned",
        passed=passed,
        gate=rubric.kappa_gate,
        agreements=agreements,
        examples=len(labeled),
        measurement_scope=(
            "Offline judge-to-human agreement over synthetic Slot B candidates. "
            "Live quality regression remains pending until real labels clear the gate."
        ),
    )


def weighted_cohen_kappa(
    human_scores: Sequence[int],
    judge_scores: Sequence[int],
    *,
    labels: Sequence[int] = ORDINAL_SCORES,
) -> float:
    if len(human_scores) != len(judge_scores):
        raise ValueError("score sequences must have the same length")
    if not human_scores:
        raise ValueError("at least one scored example is required")

    label_to_index = {label: index for index, label in enumerate(labels)}
    for score in (*human_scores, *judge_scores):
        if score not in label_to_index:
            raise ValueError(f"score {score!r} is outside the rubric scale")

    size = len(labels)
    observed = [[0.0 for _ in range(size)] for _ in range(size)]
    for human_score, judge_score in zip(human_scores, judge_scores, strict=True):
        observed[label_to_index[human_score]][label_to_index[judge_score]] += 1.0

    row_totals = [sum(row) for row in observed]
    col_totals = [sum(observed[row][col] for row in range(size)) for col in range(size)]
    total = float(len(human_scores))
    observed_disagreement = 0.0
    expected_disagreement = 0.0
    max_distance = max(size - 1, 1)
    for row in range(size):
        for col in range(size):
            weight = ((row - col) / max_distance) ** 2
            observed_disagreement += weight * observed[row][col]
            expected_disagreement += weight * (row_totals[row] * col_totals[col] / total)

    if math.isclose(expected_disagreement, 0.0):
        return 1.0 if math.isclose(observed_disagreement, 0.0) else 0.0
    return 1.0 - (observed_disagreement / expected_disagreement)


def gwet_ac1(
    human_scores: Sequence[int],
    judge_scores: Sequence[int],
    *,
    labels: Sequence[int] = ORDINAL_SCORES,
) -> float:
    """Gwet's AC1 -- an agreement coefficient robust to the prevalence paradox
    that makes weighted Cohen's kappa unstable (wide CI) when one category
    dominates a small sample, as happens on this repo's n=36 hard layer.
    REPORTED alongside kappa when kappa's CI is wide; never a gate substitute
    for kappa (harvest/13_JUDGE_VALIDATION_RESOLVE.md)."""

    if len(human_scores) != len(judge_scores):
        raise ValueError("score sequences must have the same length")
    if not human_scores:
        raise ValueError("at least one scored example is required")

    label_to_index = {label: index for index, label in enumerate(labels)}
    for score in (*human_scores, *judge_scores):
        if score not in label_to_index:
            raise ValueError(f"score {score!r} is outside the rubric scale")

    size = len(labels)
    total = float(len(human_scores))
    agree = sum(
        1.0
        for h, j in zip(human_scores, judge_scores, strict=True)
        if h == j
    )
    observed_agreement = agree / total

    # Pooled per-category proportion across BOTH raters' ratings (Gwet's own
    # definition), not each rater's marginal separately.
    category_counts = [0.0 for _ in range(size)]
    for score in (*human_scores, *judge_scores):
        category_counts[label_to_index[score]] += 1.0
    pooled_total = 2.0 * total
    category_props = [count / pooled_total for count in category_counts]

    expected_agreement = sum(prop * (1.0 - prop) for prop in category_props) / (size - 1)

    if math.isclose(expected_agreement, 1.0):
        return 1.0 if math.isclose(observed_agreement, 1.0) else 0.0
    return (observed_agreement - expected_agreement) / (1.0 - expected_agreement)


class LabelReplayJudge:
    """Fixture judge for calibration tests; it only replays supplied labels."""

    def __init__(self, labels_by_candidate: Mapping[str, QualityLabels]) -> None:
        self._labels_by_candidate = labels_by_candidate

    def score(self, candidate: SlotBQualityCandidate) -> QualityLabels:
        return self._labels_by_candidate[candidate.candidate_id]


def labels_from_scores(
    candidate_id: str,
    scores: Mapping[str, int],
    *,
    labeler: str,
    rubric: QualityRubric | None = None,
) -> QualityLabels:
    rubric = rubric or default_rubric()
    normalized = {
        dimension: _validate_score(scores[dimension], rubric)
        for dimension in rubric.dimension_names()
    }
    return QualityLabels(
        candidate_id=candidate_id,
        dimension_scores=normalized,
        overall_pass=all(score >= PASSING_SCORE for score in normalized.values()),
        labeler=labeler,
    )


def _candidate_request(
    *,
    candidate_id: str,
    account_name: str,
    score: int,
    factors: tuple[SlotBPriorityFactor, ...],
    evidence: tuple[SlotBEvidence, ...],
    contact_allowed: bool,
) -> ReasonDraftRequest:
    return ReasonDraftRequest(
        tenant_id="quality-fixture-tenant",
        account_id=candidate_id,
        account_name=account_name,
        disposition="propose_customer_action" if contact_allowed else "internal_review",
        recommended_action=(
            "draft_customer_outreach"
            if contact_allowed
            else "recommend_next_best_action"
        ),
        customer_contact_allowed=contact_allowed,
        priority=SlotBPriority(score=score, factors=factors),
        evidence=evidence,
        as_of="2026-06-27",
        contact_name="Jordan Lee" if contact_allowed else None,
        contact_email="jordan@example.test" if contact_allowed else None,
        untrusted_text_fragments=(),
    )


def _request_dict(request: ReasonDraftRequest) -> dict:
    data = asdict(request)
    data["prompt_version"] = SLOT_B_PROMPT_VERSION
    return _jsonable(data)


def _output_dict(output: ReasonDraftOutput) -> dict:
    data = asdict(output)
    data["cited_evidence_ids"] = list(output.cited_evidence_ids)
    return _jsonable(data)


def _candidate_dict(candidate: SlotBQualityCandidate) -> dict:
    return {
        "candidate_id": candidate.candidate_id,
        "fixture_mode": candidate.fixture_mode,
        "request": candidate.request,
        "output": candidate.output,
        "human_labels": (
            asdict(candidate.human_labels)
            if candidate.human_labels is not None
            else None
        ),
        "fixture_model_id": FIXTURE_SLOT_B_MODEL_ID,
    }


def _score_for(
    labels: QualityLabels | None,
    dimension: str,
    rubric: QualityRubric,
) -> int:
    if labels is None:
        raise ValueError("candidate is missing human labels")
    return _validate_score(labels.dimension_scores[dimension], rubric)


def _validate_score(score: int, rubric: QualityRubric) -> int:
    if score not in rubric.score_values:
        raise ValueError(f"score {score!r} is outside the rubric scale")
    return score


def _jsonable(data: dict) -> dict:
    return json.loads(json.dumps(data, sort_keys=True))
