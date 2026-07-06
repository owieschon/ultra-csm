"""Deterministic internal handoff routing for the MP-B spike.

The bridge is intentionally narrow: it reads grounded CRM cases and maps
positive support/feedback signals to either Engineering, Product, or an
abstention. It does not call a model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ultra_csm.data_plane.contracts import CRMCase, EvidenceRef

InternalBridgeTarget = Literal["engineering", "product"]
InternalBridgeMotion = Literal["escalation", "content_route"]


@dataclass(frozen=True)
class InternalBridgeConfig:
    active_statuses: tuple[str, ...] = ("open", "in progress", "escalated")
    resolved_statuses: tuple[str, ...] = ("resolved", "closed")


@dataclass(frozen=True)
class InternalBridgeDecision:
    target: InternalBridgeTarget | None
    motion: InternalBridgeMotion | None
    signal: str | None
    evidence: tuple[EvidenceRef, ...]
    abstained: bool
    reason: str


_FEATURE_KEYWORDS = (
    "feature request",
    "api webhook",
    "format change request",
    "report template",
)

_TECHNICAL_KEYWORDS = (
    "integration",
    "timeout",
    "dropping",
    "failing",
    "failure",
    "500",
    "performance",
    "load times",
    "discrepancy",
    "stale data",
    "export failing",
    "gps accuracy",
    "real-time positions",
    "real-time",
    "not showing",
    "inefficient paths",
    "dashboard",
    "blocker",
)


def route_internal_bridge(
    cases: tuple[CRMCase, ...] | list[CRMCase],
    *,
    as_of: str,
    config: InternalBridgeConfig | None = None,
) -> InternalBridgeDecision:
    """Route grounded CRM cases to the internal bridge target.

    Product capability requests are durable feedback evidence even after a
    support case resolves. Engineering requires an active technical failure or
    a recurring defect pattern; resolved one-off technical cases abstain.
    """

    cfg = config or InternalBridgeConfig()
    ordered_cases = tuple(cases)
    product_cases = tuple(case for case in ordered_cases if _is_product_feedback(case))
    active_technical = tuple(
        case for case in ordered_cases
        if _is_technical_case(case) and _is_active(case, cfg)
    )
    technical_cases = tuple(case for case in ordered_cases if _is_technical_case(case))

    if active_technical:
        return _engineering_decision(active_technical, technical_cases, as_of=as_of)
    if product_cases:
        return _product_decision(product_cases, as_of=as_of)
    return InternalBridgeDecision(
        target=None,
        motion=None,
        signal=None,
        evidence=(),
        abstained=True,
        reason="No live engineering defect or product-feedback capability gap found.",
    )


def _engineering_decision(
    active_cases: tuple[CRMCase, ...],
    technical_cases: tuple[CRMCase, ...],
    *,
    as_of: str,
) -> InternalBridgeDecision:
    signal = "active_technical_failure"
    subjects = " ".join(case.subject.lower() for case in active_cases)
    if len(technical_cases) >= 2:
        signal = "recurring_technical_case_pattern"
    elif "gps accuracy" in subjects:
        signal = "single_contestable_accuracy_case"
    elif "inefficient paths" in subjects or "route optimization" in subjects:
        signal = "single_contestable_quality_case"
    elif "real-time" in subjects or "not showing" in subjects:
        signal = "active_realtime_position_defect"

    evidence_cases = technical_cases if len(technical_cases) >= 2 else active_cases
    return InternalBridgeDecision(
        target="engineering",
        motion="escalation",
        signal=signal,
        evidence=_case_evidence(evidence_cases, as_of=as_of),
        abstained=False,
        reason="Active or recurring technical failure requires engineering handoff.",
    )


def _product_decision(
    cases: tuple[CRMCase, ...],
    *,
    as_of: str,
) -> InternalBridgeDecision:
    subjects = " ".join(case.subject.lower() for case in cases)
    signal = (
        "feature_request_cluster"
        if len(cases) >= 2 or "feature request" in subjects or "api webhook" in subjects
        else "single_product_capability_request"
    )
    return InternalBridgeDecision(
        target="product",
        motion="content_route",
        signal=signal,
        evidence=_case_evidence(cases, as_of=as_of),
        abstained=False,
        reason="Feature or format request is durable product-feedback evidence.",
    )


def _case_evidence(cases: tuple[CRMCase, ...], *, as_of: str) -> tuple[EvidenceRef, ...]:
    return tuple(EvidenceRef("crm", case.case_id, "subject", as_of) for case in cases)


def _is_active(case: CRMCase, config: InternalBridgeConfig) -> bool:
    status = case.status.strip().lower()
    if status in config.resolved_statuses:
        return False
    return case.closed_at is None or status in config.active_statuses


def _is_product_feedback(case: CRMCase) -> bool:
    subject = case.subject.lower()
    return any(keyword in subject for keyword in _FEATURE_KEYWORDS)


def _is_technical_case(case: CRMCase) -> bool:
    subject = case.subject.lower()
    return any(keyword in subject for keyword in _TECHNICAL_KEYWORDS)
