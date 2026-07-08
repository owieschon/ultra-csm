"""Deterministic CSM work-packet contract.

This module is a read-side planner over existing organs: Agent 1 sweep output,
the value-model priority factors, Slot B artifacts, internal-bridge routing,
and governance action specs. It does not introduce a second scorer, motion
resolver, or approval source.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ultra_csm.data_plane.contracts import CRMAccount, CRMContact, EvidenceRef
from ultra_csm.governance.csm_actions import (
    CSMActionSpec,
    CSMActionType,
    UnknownCSMActionError,
    csm_action_spec,
)


PacketJobType = Literal[
    "customer_outreach",
    "education_recommendation",
    "internal_escalation",
    "product_feedback_synthesis",
    "identity_resolution",
    "no_action_monitor",
]
PacketLane = Literal["prepared", "needs_judgment", "blocked", "covered"]
ProvenanceTier = Literal["raw_fact", "interpreted_signal", "hypothesis"]


@dataclass(frozen=True)
class DiagnosticHypothesis:
    label: Literal["unverified_hypothesis"]
    summary: str
    confidence: float
    confidence_label: Literal["low", "medium"]
    basis: tuple[str, ...]
    unknowns: tuple[str, ...]
    validation_status: Literal["out_of_validated_domain"]


@dataclass(frozen=True)
class RecommendedAction:
    action_type: CSMActionType | None
    motion: str | None
    target_actor: str
    rationale: str
    source_organ: str
    validation_status: Literal["oracle_graded", "out_of_validated_domain"]


@dataclass(frozen=True)
class GovernanceBoundary:
    source_organ: Literal["governance.csm_actions"]
    action_type: CSMActionType | None
    release_condition: str | None
    required_permission: str | None
    autonomy_tier: int | None
    customer_affecting: bool
    requires_action_gate: bool
    can_execute_from_ui: bool


@dataclass(frozen=True)
class AllowedCTA:
    cta_id: str
    label: str
    enabled: bool
    reason: str
    governance_requirement: str | None
    source_organ: Literal["governance.csm_actions"]


@dataclass(frozen=True)
class PreparedArtifact:
    artifact_type: Literal[
        "customer_draft",
        "content_route",
        "internal_note",
        "handoff_outline",
        "none",
    ]
    title: str
    body: str | None
    source_organ: str
    requires_approval: bool
    validation_status: Literal[
        "oracle_graded", "judge_graded_in_domain", "out_of_validated_domain"
    ]


@dataclass(frozen=True)
class EvidenceChainStep:
    step_id: str
    provenance_tier: ProvenanceTier
    source: str
    source_id: str
    field: str
    observed_at: str
    claim: str
    validation_status: Literal["oracle_graded", "out_of_validated_domain"]


@dataclass(frozen=True)
class BucketTrace:
    bucket: str
    state: Literal["covered", "missing", "not_applicable"]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class CoverageTrace:
    accounts_scanned: int
    accounts_in_book: int
    account_resolution: str
    coverage_label: Literal["sweep_item", "identity_exception", "cohort_item"]


@dataclass(frozen=True)
class FeedbackHook:
    hook_id: str
    label: str
    target: Literal["rejection_ledger"]
    enabled: bool


@dataclass(frozen=True)
class CSMWorkPacket:
    packet_version: Literal["csm-work-packet-v1"]
    tenant_id: str
    account_id: str | None
    account_name: str | None
    as_of: str
    job_type: PacketJobType
    lane: PacketLane
    cadence: str
    diagnostic_hypothesis: DiagnosticHypothesis
    recommended_action: RecommendedAction
    primary_next_step: str
    governance_boundary: GovernanceBoundary
    prepared_artifact: PreparedArtifact
    evidence_chain: tuple[EvidenceChainStep, ...]
    bucket_trace: tuple[BucketTrace, ...]
    coverage_trace: CoverageTrace
    allowed_ctas: tuple[AllowedCTA, ...]
    feedback_hooks: tuple[FeedbackHook, ...]
    field_validation: dict[str, str]


@dataclass(frozen=True)
class PacketInputs:
    tenant_id: str
    account: CRMAccount | None
    as_of: str
    account_resolution: str
    candidate_account_ids: tuple[str, ...]
    disposition: str
    recommended_action: CSMActionType | None
    motion: str | None
    reason: str
    priority_score: int | None
    priority_factors: tuple[Any, ...]
    evidence: tuple[EvidenceRef, ...]
    contacts: tuple[CRMContact, ...] = ()
    selected_contact: CRMContact | None = None
    recipient_resolution: str | None = None
    customer_contact_allowed: bool = False
    proposal_id: str | None = None
    proposal_status: str | None = None
    draft_body: str | None = None
    draft_mode: str | None = None
    internal_bridge_decision: Any | None = None
    content_route_title: str | None = None
    accounts_scanned: int = 0
    accounts_in_book: int = 0


def build_work_packet(inputs: PacketInputs) -> CSMWorkPacket:
    """Build a packet from already-computed sweep facts."""

    action_spec = _action_spec(inputs.recommended_action)
    job_type = _job_type(inputs, action_spec)
    lane = _lane(inputs, action_spec)
    evidence_chain = _evidence_chain(inputs.evidence)
    priority_evidence_ids = _factor_evidence_ids(inputs.priority_factors)
    primary_next_step = _primary_next_step(inputs, action_spec)

    return CSMWorkPacket(
        packet_version="csm-work-packet-v1",
        tenant_id=inputs.tenant_id,
        account_id=inputs.account.account_id if inputs.account is not None else None,
        account_name=inputs.account.name if inputs.account is not None else None,
        as_of=inputs.as_of,
        job_type=job_type,
        lane=lane,
        cadence=_cadence(inputs),
        diagnostic_hypothesis=_diagnostic_hypothesis(
            inputs, evidence_chain=evidence_chain
        ),
        recommended_action=_recommended_action(inputs, action_spec),
        primary_next_step=primary_next_step,
        governance_boundary=_governance_boundary(inputs, action_spec),
        prepared_artifact=_prepared_artifact(inputs, action_spec),
        evidence_chain=evidence_chain,
        bucket_trace=_bucket_trace(inputs, priority_evidence_ids),
        coverage_trace=CoverageTrace(
            accounts_scanned=inputs.accounts_scanned,
            accounts_in_book=inputs.accounts_in_book,
            account_resolution=inputs.account_resolution,
            coverage_label=(
                "cohort_item"
                if inputs.account is None and inputs.candidate_account_ids
                else "identity_exception"
                if inputs.account_resolution != "exactly_one"
                else "sweep_item"
            ),
        ),
        allowed_ctas=allowed_ctas_for(
            inputs.recommended_action,
            proposal_status=inputs.proposal_status,
            artifact_present=bool(inputs.draft_body or inputs.content_route_title),
        ),
        feedback_hooks=_feedback_hooks(),
        field_validation=_field_validation(),
    )


def allowed_ctas_for(
    action: CSMActionType | None,
    *,
    proposal_status: str | None,
    artifact_present: bool,
) -> tuple[AllowedCTA, ...]:
    """Derive operator CTAs from governance release conditions."""

    spec = _action_spec(action)
    release_condition = spec.release_condition if spec else None
    can_request_approval = (
        spec is not None
        and proposal_status == "pending"
        and release_condition != "auto_internal_only"
    )
    can_mark_internal = (
        spec is not None
        and proposal_status in (None, "pending")
        and release_condition == "auto_internal_only"
    )

    return (
        AllowedCTA(
            cta_id="inspect_sources",
            label="Inspect sources",
            enabled=True,
            reason="Source inspection is read-only.",
            governance_requirement=None,
            source_organ="governance.csm_actions",
        ),
        AllowedCTA(
            cta_id="preview_artifact",
            label="Preview artifact",
            enabled=artifact_present,
            reason=(
                "Prepared artifact is available."
                if artifact_present
                else "No prepared artifact was produced."
            ),
            governance_requirement=release_condition,
            source_organ="governance.csm_actions",
        ),
        AllowedCTA(
            cta_id="request_gate_approval",
            label="Request approval",
            enabled=can_request_approval,
            reason=(
                f"Proposal is pending and requires {release_condition}."
                if can_request_approval
                else "No pending customer-affecting proposal requires approval."
            ),
            governance_requirement=release_condition,
            source_organ="governance.csm_actions",
        ),
        AllowedCTA(
            cta_id="mark_internal_reviewed",
            label="Mark reviewed",
            enabled=can_mark_internal,
            reason=(
                "Internal-only recommendation may be marked reviewed."
                if can_mark_internal
                else "Only internal-only recommendations can be marked reviewed."
            ),
            governance_requirement=release_condition,
            source_organ="governance.csm_actions",
        ),
        AllowedCTA(
            cta_id="record_feedback",
            label="Record feedback",
            enabled=True,
            reason="Operator feedback is ledgered for model/process review.",
            governance_requirement=None,
            source_organ="governance.csm_actions",
        ),
    )


def _action_spec(action: CSMActionType | None) -> CSMActionSpec | None:
    if action is None:
        return None
    try:
        return csm_action_spec(action)
    except UnknownCSMActionError:
        return None


def _job_type(
    inputs: PacketInputs, action_spec: CSMActionSpec | None
) -> PacketJobType:
    decision = inputs.internal_bridge_decision
    if inputs.account is None and inputs.candidate_account_ids:
        return "customer_outreach" if action_spec and action_spec.customer_affecting else "no_action_monitor"
    if inputs.account_resolution != "exactly_one":
        return "identity_resolution"
    if decision is not None and not getattr(decision, "abstained", True):
        if getattr(decision, "target", None) == "product":
            return "product_feedback_synthesis"
        return "internal_escalation"
    if inputs.recommended_action == "content_route":
        return "education_recommendation"
    if action_spec is not None and action_spec.customer_affecting:
        return "customer_outreach"
    if inputs.disposition == "escalate":
        return "identity_resolution"
    if inputs.disposition == "internal_review":
        return "internal_escalation"
    return "no_action_monitor"


def _lane(inputs: PacketInputs, action_spec: CSMActionSpec | None) -> PacketLane:
    if inputs.account_resolution != "exactly_one":
        if inputs.account is None and inputs.candidate_account_ids and action_spec is not None:
            return "needs_judgment"
        return "blocked"
    if inputs.proposal_status in ("approved", "denied"):
        return "covered"
    if action_spec is not None and action_spec.release_condition != "auto_internal_only":
        return "needs_judgment"
    if not inputs.evidence:
        return "blocked"
    return "prepared"


def _cadence(inputs: PacketInputs) -> str:
    if inputs.disposition == "escalate":
        return "immediate_identity_review"
    if inputs.priority_score is not None and inputs.priority_score >= 85:
        return "same_day"
    if inputs.priority_score is not None and inputs.priority_score >= 65:
        return "next_business_day"
    return "next_sweep"


def _diagnostic_hypothesis(
    inputs: PacketInputs, *, evidence_chain: tuple[EvidenceChainStep, ...]
) -> DiagnosticHypothesis:
    basis = tuple(step.step_id for step in evidence_chain[:5])
    unknowns: list[str] = []
    if inputs.account_resolution != "exactly_one":
        unknowns.append("resolved_account_identity")
    if inputs.recipient_resolution not in (None, "resolved"):
        unknowns.append("best_customer_recipient")
    if not inputs.evidence:
        unknowns.append("source_evidence")
    if inputs.proposal_status is None and inputs.customer_contact_allowed:
        unknowns.append("gate_proposal_status")
    confidence = _confidence(inputs, evidence_chain=evidence_chain)
    return DiagnosticHypothesis(
        label="unverified_hypothesis",
        summary=_hypothesis_summary(inputs),
        confidence=confidence,
        confidence_label="medium" if confidence >= 0.55 else "low",
        basis=basis,
        unknowns=tuple(unknowns),
        validation_status="out_of_validated_domain",
    )


def _hypothesis_summary(inputs: PacketInputs) -> str:
    account_name = inputs.account.name if inputs.account is not None else "This item"
    if inputs.reason:
        return f"{account_name}: {inputs.reason}"
    if inputs.account_resolution != "exactly_one":
        return "Account identity is ambiguous and needs operator resolution."
    return "No independently validated diagnosis has been produced for this item."


def _confidence(
    inputs: PacketInputs, *, evidence_chain: tuple[EvidenceChainStep, ...]
) -> float:
    raw_count = sum(1 for step in evidence_chain if step.provenance_tier == "raw_fact")
    score = 0.25 + min(raw_count, 4) * 0.1
    if inputs.priority_score is not None:
        score += 0.08
    if inputs.proposal_status:
        score += 0.06
    if inputs.internal_bridge_decision is not None and not getattr(
        inputs.internal_bridge_decision, "abstained", True
    ):
        score += 0.06
    return min(score, 0.72)


def _recommended_action(
    inputs: PacketInputs, action_spec: CSMActionSpec | None
) -> RecommendedAction:
    target_actor = "operator"
    if action_spec is not None and action_spec.customer_affecting:
        target_actor = "customer_success_manager"
    decision = inputs.internal_bridge_decision
    if decision is not None and not getattr(decision, "abstained", True):
        target = getattr(decision, "target", None)
        if target:
            target_actor = str(target)
    return RecommendedAction(
        action_type=inputs.recommended_action,
        motion=inputs.motion,
        target_actor=target_actor,
        rationale=(
            action_spec.description
            if action_spec is not None
            else "No governed action is attached."
        ),
        source_organ="motion/playbook + governance.csm_actions",
        validation_status=(
            "oracle_graded" if action_spec is not None else "out_of_validated_domain"
        ),
    )


def _primary_next_step(
    inputs: PacketInputs, action_spec: CSMActionSpec | None
) -> str:
    if inputs.account_resolution != "exactly_one":
        return "Resolve account identity before any customer action."
    if inputs.proposal_status == "pending" and action_spec is not None:
        return f"Review the pending {action_spec.action} proposal in ActionGate."
    if action_spec is not None and action_spec.release_condition == "auto_internal_only":
        return "Review the internal recommendation and record operator feedback."
    if inputs.internal_bridge_decision is not None and not getattr(
        inputs.internal_bridge_decision, "abstained", True
    ):
        return "Inspect the internal bridge handoff and route to the owning team."
    return "Inspect sources and decide whether follow-up is warranted."


def _governance_boundary(
    inputs: PacketInputs, action_spec: CSMActionSpec | None
) -> GovernanceBoundary:
    requires_gate = bool(
        action_spec is not None
        and (
            action_spec.customer_affecting
            or action_spec.release_condition != "auto_internal_only"
        )
    )
    return GovernanceBoundary(
        source_organ="governance.csm_actions",
        action_type=inputs.recommended_action,
        release_condition=action_spec.release_condition if action_spec else None,
        required_permission=action_spec.required_permission if action_spec else None,
        autonomy_tier=action_spec.autonomy_tier if action_spec else None,
        customer_affecting=bool(action_spec.customer_affecting) if action_spec else False,
        requires_action_gate=requires_gate,
        can_execute_from_ui=False,
    )


def _prepared_artifact(
    inputs: PacketInputs, action_spec: CSMActionSpec | None
) -> PreparedArtifact:
    if inputs.draft_body:
        return PreparedArtifact(
            artifact_type="customer_draft",
            title="Customer outreach draft",
            body=inputs.draft_body,
            source_organ="agent1.slot_b",
            requires_approval=True,
            validation_status="judge_graded_in_domain",
        )
    if inputs.content_route_title:
        return PreparedArtifact(
            artifact_type="content_route",
            title=inputs.content_route_title,
            body=None,
            source_organ="agent1.content_route_matcher",
            requires_approval=True,
            validation_status="oracle_graded",
        )
    decision = inputs.internal_bridge_decision
    if decision is not None and not getattr(decision, "abstained", True):
        return PreparedArtifact(
            artifact_type="handoff_outline",
            title=f"{getattr(decision, 'target', 'internal')} handoff",
            body=getattr(decision, "reason", None),
            source_organ="internal_bridge",
            requires_approval=False,
            validation_status="out_of_validated_domain",
        )
    return PreparedArtifact(
        artifact_type="internal_note",
        title=(
            action_spec.description
            if action_spec is not None
            else "Operator review"
        ),
        body=inputs.reason,
        source_organ="agent1.sweep",
        requires_approval=False,
        validation_status="out_of_validated_domain",
    )


def _evidence_chain(evidence: tuple[EvidenceRef, ...]) -> tuple[EvidenceChainStep, ...]:
    return tuple(
        EvidenceChainStep(
            step_id=f"evidence:{ref.source}:{ref.source_id}:{ref.field}",
            provenance_tier="raw_fact",
            source=ref.source,
            source_id=ref.source_id,
            field=ref.field,
            observed_at=ref.observed_at,
            claim=f"{ref.source}.{ref.field} observed for {ref.source_id}",
            validation_status="oracle_graded",
        )
        for ref in evidence
    )


def _factor_evidence_ids(priority_factors: tuple[Any, ...]) -> frozenset[str]:
    ids: set[str] = set()
    for factor in priority_factors:
        for ref in getattr(factor, "evidence", ()):
            ids.add(ref.source_id)
    return frozenset(ids)


def _bucket_trace(
    inputs: PacketInputs, priority_evidence_ids: frozenset[str]
) -> tuple[BucketTrace, ...]:
    evidence_ids = tuple(ref.source_id for ref in inputs.evidence)
    priority_ids = tuple(
        ref.source_id
        for ref in inputs.evidence
        if ref.source_id in priority_evidence_ids
    )
    bridge_ids: tuple[str, ...] = ()
    decision = inputs.internal_bridge_decision
    if decision is not None:
        bridge_ids = tuple(ref.source_id for ref in getattr(decision, "evidence", ()))
    return (
        BucketTrace(
            bucket="identity",
            state="covered" if inputs.account_resolution == "exactly_one" else "missing",
            evidence_ids=tuple(contact.contact_id for contact in inputs.contacts),
        ),
        BucketTrace(
            bucket="priority",
            state="covered" if priority_ids else "missing",
            evidence_ids=priority_ids,
        ),
        BucketTrace(
            bucket="source_evidence",
            state="covered" if evidence_ids else "missing",
            evidence_ids=evidence_ids,
        ),
        BucketTrace(
            bucket="internal_bridge",
            state="covered" if bridge_ids else "not_applicable",
            evidence_ids=bridge_ids,
        ),
    )


def _feedback_hooks() -> tuple[FeedbackHook, ...]:
    return (
        FeedbackHook(
            hook_id="verdict_reason",
            label="Capture approval or rejection reason",
            target="rejection_ledger",
            enabled=True,
        ),
        FeedbackHook(
            hook_id="missing_factor",
            label="Flag missing success factor",
            target="rejection_ledger",
            enabled=True,
        ),
    )


def _field_validation() -> dict[str, str]:
    return {
        "job_type": "deterministic_oracle",
        "cadence": "deterministic_oracle",
        "lane": "deterministic_oracle",
        "allowed_ctas": "deterministic_oracle",
        "governance_boundary": "deterministic_oracle",
        "primary_next_step": "deterministic_oracle",
        "customer_artifact": "judge_graded_in_domain_or_out_of_validated_domain",
        "diagnostic_hypothesis": "out_of_validated_domain",
        "recommended_action_rationale": "out_of_validated_domain",
        "confidence": "out_of_validated_domain",
        "open_questions": "out_of_validated_domain",
        "evidence_chain": "deterministic_oracle",
        "feedback_hooks": "deterministic_oracle",
    }
