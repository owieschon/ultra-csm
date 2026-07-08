"""Backend-owned CSM work packet contract and deterministic planner."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from ultra_csm.blocked_value_path import (
    BlockedValuePathAssessment,
    assess_blocked_value_path,
)
from ultra_csm.data_plane import CustomerDataPlane
from ultra_csm.data_plane.contracts import (
    AdoptionSummary,
    CommunicationSignal,
    CRMAccount,
    CRMCase,
    CRMContact,
    CRMOpportunity,
    CSCompany,
    CTA,
    Entitlement,
    EvidenceRef,
    HealthScore,
    InternalCommsNote,
    OnboardingPhase,
    OnboardingProject,
    OnboardingTask,
    StakeholderRelationship,
    SuccessPlan,
    TimeToValueMilestone,
    UsageSignal,
)

Cadence = Literal["daily", "weekly", "monthly", "quarterly", "annual", "event_driven"]
JobType = Literal[
    "customer_outreach",
    "internal_escalation",
    "sales_handoff",
    "csm_onboarding_brief",
    "qbr_packet",
    "ebr_packet",
    "product_feedback_synthesis",
    "education_recommendation",
    "renewal_risk_review",
    "success_plan_update",
    "no_action_monitor",
    "needs_data",
]
Lane = Literal["needs_judgment", "prepared", "monitoring", "blocked", "covered", "suppressed"]
ArtifactType = Literal[
    "email_draft",
    "internal_brief",
    "sales_handoff",
    "csm_brief",
    "qbr_packet",
    "ebr_packet",
    "product_feedback",
    "education_recommendation",
    "success_plan_update",
    "renewal_risk_note",
]
CTAKind = Literal[
    "inspect",
    "preview",
    "copy",
    "edit",
    "approve",
    "reject",
    "assign",
    "simulate",
    "deep_link",
    "mark_reviewed",
    "leave_feedback",
]
GovernanceMode = Literal[
    "readonly_demo",
    "local_simulation",
    "approval_required",
    "human_approved",
    "sent",
    "blocked",
]

FEEDBACK_CATEGORIES: tuple[str, ...] = (
    "wrong_diagnosis",
    "wrong_contact",
    "wrong_action",
    "missing_evidence",
    "wrong_bucket",
    "stale_data",
    "product_feedback_candidate",
    "education_resource_candidate",
    "dismiss_monitor",
)

_UNTRUSTED_DIRECTIVE_MARKERS = (
    "ignore previous instructions",
    "ignore policy",
    "mark me top priority",
    "mark this account top priority",
    "email all customer data",
)


@dataclass(frozen=True)
class DiagnosticHypothesis:
    summary: str
    signals: tuple[str, ...]
    counter_signals: tuple[str, ...]
    unknowns: tuple[str, ...]
    confidence: float
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class RecommendedAction:
    action_id: str
    action_type: str
    label: str
    objective: str
    recipient_role: str | None
    recipient_contact_id: str | None
    message_strategy: str
    success_criteria: tuple[str, ...]
    blocked_by: tuple[str, ...]
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class ContactPlan:
    primary_contact: dict[str, Any] | None
    backup_contact: dict[str, Any] | None
    internal_owner: str | None
    tone: str
    channel: str
    reason_for_contact_choice: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class PreparedArtifact:
    artifact_id: str
    artifact_type: ArtifactType
    title: str
    body_or_outline: str
    intended_audience: str
    requires_approval: bool
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class AllowedCTA:
    cta_id: str
    label: str
    kind: CTAKind
    enabled: bool
    disabled_reason: str | None
    governance_requirement: str | None
    readonly_behavior: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class GovernanceBoundary:
    mode: GovernanceMode
    requires_human_principal: bool
    requires_action_gate: bool
    can_execute_from_ui: bool
    audit_requirements: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceChainStep:
    step_id: str
    claim: str
    source_type: str
    source_id: str
    field: str
    observed_value: str
    interpretation: str
    supports: str
    strength: Literal["weak", "medium", "strong"]


@dataclass(frozen=True)
class BucketTrace:
    lane: Lane
    rule_id: str
    rule_label: str
    inputs: dict[str, Any]
    thresholds: dict[str, Any]
    matched: tuple[str, ...]
    near_misses: tuple[str, ...]
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class CoverageTrace:
    book_size: int
    accounts_scanned: int
    included_reason: str
    excluded_or_suppressed_reason: str | None
    last_reviewed_at: str | None
    freshness: str


@dataclass(frozen=True)
class FeedbackHook:
    category: str
    label: str
    local_only: bool
    readonly_behavior: str


@dataclass(frozen=True)
class CSMWorkPacket:
    packet_id: str
    account_id: str | None
    account_name: str
    generated_at: str
    as_of_day: str
    cadence: Cadence
    job_type: JobType
    lane: Lane
    primary_next_step: str
    why_now: str
    diagnostic_hypothesis: DiagnosticHypothesis
    implied_customer_state: str
    recommended_action: RecommendedAction
    contact_plan: ContactPlan
    prepared_artifacts: tuple[PreparedArtifact, ...]
    allowed_ctas: tuple[AllowedCTA, ...]
    governance: GovernanceBoundary
    evidence_chain: tuple[EvidenceChainStep, ...]
    bucket_trace: BucketTrace
    coverage_trace: CoverageTrace
    open_questions: tuple[str, ...]
    confidence: float
    feedback_hooks: tuple[FeedbackHook, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PacketInputs:
    tenant_id: str
    account: CRMAccount
    as_of: str
    disposition: str
    action: str | None
    motion: str | None
    priority_score: int | None
    priority_factors: tuple[Any, ...]
    evidence: tuple[EvidenceRef, ...]
    contacts: tuple[CRMContact, ...]
    selected_contact: CRMContact | None
    recipient_role: str | None
    recipient_resolution: str | None
    customer_contact_allowed: bool
    proposal_id: str | None
    proposal_status: str | None
    draft_body: str | None
    cases: tuple[CRMCase, ...]
    success_plans: tuple[SuccessPlan, ...]
    usage_signals: tuple[UsageSignal, ...]
    milestones: tuple[TimeToValueMilestone, ...]
    opportunities: tuple[CRMOpportunity, ...]
    internal_bridge_decision: Any | None
    content_route_title: str | None
    book_size: int
    accounts_scanned: int
    company: CSCompany | None = None
    health: HealthScore | None = None
    adoption: AdoptionSummary | None = None
    entitlements: tuple[Entitlement, ...] = ()
    stakeholders: tuple[StakeholderRelationship, ...] = ()
    ctas: tuple[CTA, ...] = ()
    communication_signals: tuple[CommunicationSignal, ...] = ()
    internal_notes: tuple[InternalCommsNote, ...] = ()
    onboarding_projects: tuple[OnboardingProject, ...] = ()
    onboarding_phases: tuple[OnboardingPhase, ...] = ()
    onboarding_tasks: tuple[OnboardingTask, ...] = ()


def build_work_packet(inputs: PacketInputs) -> CSMWorkPacket:
    evidence_chain = _evidence_chain(inputs)
    source_ids = _source_ids(inputs.evidence, evidence_chain)
    job_type = _job_type(inputs)
    lane = _lane(inputs, job_type)
    primary_next_step = _primary_next_step(inputs, job_type)
    diagnostic = _diagnostic_hypothesis(inputs, evidence_chain)
    action = _recommended_action(inputs, job_type, primary_next_step, source_ids)
    contact_plan = _contact_plan(inputs, source_ids)
    artifact = _artifact(inputs, job_type, primary_next_step, source_ids)
    governance = _governance(inputs)
    allowed_ctas = _allowed_ctas(inputs, governance, source_ids)
    bucket_trace = _bucket_trace(inputs, lane, source_ids)
    coverage_trace = CoverageTrace(
        book_size=inputs.book_size,
        accounts_scanned=inputs.accounts_scanned,
        included_reason=_included_reason(inputs, job_type),
        excluded_or_suppressed_reason=None,
        last_reviewed_at=None,
        freshness=_freshness(inputs),
    )
    unknowns = _unknowns(inputs)
    confidence = _confidence(inputs, evidence_chain)
    return CSMWorkPacket(
        packet_id=f"packet:{inputs.account.account_id}:{inputs.as_of}",
        account_id=inputs.account.account_id,
        account_name=inputs.account.name,
        generated_at=inputs.as_of,
        as_of_day=inputs.as_of,
        cadence=_cadence(inputs, job_type),
        job_type=job_type,
        lane=lane,
        primary_next_step=primary_next_step,
        why_now=_why_now(inputs),
        diagnostic_hypothesis=diagnostic,
        implied_customer_state=_implied_customer_state(inputs, job_type),
        recommended_action=action,
        contact_plan=contact_plan,
        prepared_artifacts=(artifact,),
        allowed_ctas=allowed_ctas,
        governance=governance,
        evidence_chain=evidence_chain,
        bucket_trace=bucket_trace,
        coverage_trace=coverage_trace,
        open_questions=unknowns,
        confidence=confidence,
        feedback_hooks=_feedback_hooks(),
    )


def build_coverage_packet(
    *,
    account: CRMAccount,
    as_of: str,
    book_size: int,
    accounts_scanned: int,
    included_work_account_ids: frozenset[str],
    data_plane: CustomerDataPlane,
) -> CSMWorkPacket:
    company = data_plane.cs.get_company(account.account_id)
    health = data_plane.cs.get_health_score(account.account_id)
    adoption = data_plane.cs.get_adoption_summary(account.account_id)
    missing = tuple(
        name
        for name, value in (
            ("company", company),
            ("health_score", health),
            ("adoption", adoption),
        )
        if value is None
    )
    lane: Lane = "blocked" if missing else "covered"
    job_type: JobType = "needs_data" if missing else "no_action_monitor"
    source_id = account.account_id
    evidence_chain: tuple[EvidenceChainStep, ...] = ()
    if not missing:
        evidence_chain = (
            EvidenceChainStep(
                step_id=f"evidence:{source_id}:coverage",
                claim="Account was scanned and did not meet an action threshold.",
                source_type="cs_platform",
                source_id=source_id,
                field="coverage",
                observed_value=f"health={getattr(health, 'band', 'unknown')}; adoption={getattr(adoption, 'adoption_rate', 'unknown')}",
                interpretation="No packet-level action was selected for this sweep.",
                supports="no_action_monitor",
                strength="medium",
            ),
        )
    reason = (
        f"Missing required data buckets: {', '.join(missing)}."
        if missing
        else "Scanned in the whole book and no governed next step was selected."
    )
    governance = GovernanceBoundary(
        mode="readonly_demo",
        requires_human_principal=False,
        requires_action_gate=False,
        can_execute_from_ui=False,
        audit_requirements=("coverage.review.local_only",),
    )
    return CSMWorkPacket(
        packet_id=f"packet:{account.account_id}:{as_of}:coverage",
        account_id=account.account_id,
        account_name=account.name,
        generated_at=as_of,
        as_of_day=as_of,
        cadence="weekly",
        job_type=job_type,
        lane=lane,
        primary_next_step=(
            "Fill missing CS data before recommending work"
            if missing
            else "Mark reviewed or leave feedback if this account should not be covered"
        ),
        why_now=reason,
        diagnostic_hypothesis=DiagnosticHypothesis(
            summary=reason,
            signals=() if missing else ("whole_book_scanned",),
            counter_signals=(),
            unknowns=missing,
            confidence=0.2 if missing else 0.72,
            source_ids=(source_id,) if not missing else (),
        ),
        implied_customer_state=(
            "The system cannot infer customer state without the missing data."
            if missing
            else "No immediate customer-facing or internal action is justified by this sweep."
        ),
        recommended_action=RecommendedAction(
            action_id=f"action:{account.account_id}:{job_type}",
            action_type=job_type,
            label="Monitor" if not missing else "Needs data",
            objective=reason,
            recipient_role=None,
            recipient_contact_id=None,
            message_strategy="Do not contact the customer from this packet.",
            success_criteria=("Human can inspect coverage rationale.",),
            blocked_by=missing,
            source_ids=(source_id,) if not missing else (),
        ),
        contact_plan=ContactPlan(
            primary_contact=None,
            backup_contact=None,
            internal_owner=account.owner_id,
            tone="none",
            channel="none",
            reason_for_contact_choice="No customer contact is recommended for coverage packets.",
            source_ids=(source_id,) if not missing else (),
        ),
        prepared_artifacts=(),
        allowed_ctas=(
            AllowedCTA(
                cta_id=f"cta:{account.account_id}:inspect",
                label="Inspect coverage",
                kind="inspect",
                enabled=True,
                disabled_reason=None,
                governance_requirement=None,
                readonly_behavior="Open local coverage details only.",
                source_ids=(source_id,),
            ),
            AllowedCTA(
                cta_id=f"cta:{account.account_id}:feedback",
                label="Leave feedback",
                kind="leave_feedback",
                enabled=True,
                disabled_reason=None,
                governance_requirement=None,
                readonly_behavior="Store feedback locally for this demo session.",
                source_ids=(source_id,),
            ),
        ),
        governance=governance,
        evidence_chain=evidence_chain,
        bucket_trace=BucketTrace(
            lane=lane,
            rule_id=f"coverage:{job_type}",
            rule_label="Whole-book coverage review",
            inputs={
                "selected_for_work": account.account_id in included_work_account_ids,
                "missing_data": list(missing),
            },
            thresholds={"visible_in_whole_book": True},
            matched=(job_type,),
            near_misses=(),
            source_ids=(source_id,) if not missing else (),
        ),
        coverage_trace=CoverageTrace(
            book_size=book_size,
            accounts_scanned=accounts_scanned,
            included_reason="whole_book_coverage",
            excluded_or_suppressed_reason=(
                "missing_data" if missing else "not_selected_for_priority_queue"
            ),
            last_reviewed_at=None,
            freshness="current_sweep",
        ),
        open_questions=missing,
        confidence=0.2 if missing else 0.72,
        feedback_hooks=_feedback_hooks(),
    )


def build_cohort_packet(
    *,
    tenant_id: str,
    candidate_account_ids: tuple[str, ...],
    reason: str,
    as_of: str,
    book_size: int,
    accounts_scanned: int,
) -> CSMWorkPacket:
    source_ids = candidate_account_ids[:8]
    governance = GovernanceBoundary(
        mode="readonly_demo",
        requires_human_principal=True,
        requires_action_gate=True,
        can_execute_from_ui=False,
        audit_requirements=("ActionGate cohort proposal required", "human approval before external write"),
    )
    return CSMWorkPacket(
        packet_id=f"packet:cohort:{as_of}:{len(candidate_account_ids)}",
        account_id=None,
        account_name=f"{len(candidate_account_ids)} account cohort",
        generated_at=as_of,
        as_of_day=as_of,
        cadence="weekly",
        job_type="education_recommendation",
        lane="needs_judgment",
        primary_next_step="Inspect the cohort membership and approve only through ActionGate",
        why_now=reason,
        diagnostic_hypothesis=DiagnosticHypothesis(
            summary=reason,
            signals=("Multiple accounts share the same trigger and tier.",),
            counter_signals=(),
            unknowns=("per-account owner readiness",),
            confidence=0.68,
            source_ids=source_ids,
        ),
        implied_customer_state="A segment may need the same educational or adoption motion, but blast radius requires human review.",
        recommended_action=RecommendedAction(
            action_id=f"action:cohort:{as_of}",
            action_type="cohort_action",
            label="Review cohort action",
            objective="Avoid one-off outreach when a repeated adoption pattern is present.",
            recipient_role=None,
            recipient_contact_id=None,
            message_strategy="Inspect membership and approve only if the cohort is coherent.",
            success_criteria=("Cohort membership is verified.", "ActionGate approval is recorded before execution."),
            blocked_by=("readonly_demo",),
            source_ids=source_ids,
        ),
        contact_plan=ContactPlan(
            primary_contact=None,
            backup_contact=None,
            internal_owner=tenant_id,
            tone="cohort review",
            channel="governed console",
            reason_for_contact_choice="No single recipient exists for a cohort packet.",
            source_ids=source_ids,
        ),
        prepared_artifacts=(
            PreparedArtifact(
                artifact_id=f"artifact:cohort:{as_of}",
                artifact_type="education_recommendation",
                title="Cohort adoption motion review",
                body_or_outline=reason,
                intended_audience="CS operator",
                requires_approval=True,
                source_ids=source_ids,
            ),
        ),
        allowed_ctas=(
            AllowedCTA(
                cta_id=f"cta:cohort:{as_of}:inspect",
                label="Inspect cohort",
                kind="inspect",
                enabled=True,
                disabled_reason=None,
                governance_requirement=None,
                readonly_behavior="Open local cohort membership only.",
                source_ids=source_ids,
            ),
            AllowedCTA(
                cta_id=f"cta:cohort:{as_of}:approve",
                label="Approve through ActionGate",
                kind="approve",
                enabled=False,
                disabled_reason="Readonly demo cannot execute cohort actions.",
                governance_requirement="ActionGate cohort_action proposal with dual-control approval",
                readonly_behavior="Explain disabled governed approval.",
                source_ids=source_ids,
            ),
            AllowedCTA(
                cta_id=f"cta:cohort:{as_of}:feedback",
                label="Leave feedback",
                kind="leave_feedback",
                enabled=True,
                disabled_reason=None,
                governance_requirement=None,
                readonly_behavior="Record local packet feedback only.",
                source_ids=source_ids,
            ),
        ),
        governance=governance,
        evidence_chain=(
            EvidenceChainStep(
                step_id=f"evidence:cohort:{as_of}",
                claim=reason,
                source_type="cohort_resolver",
                source_id="|".join(source_ids),
                field="candidate_account_ids",
                observed_value=str(len(candidate_account_ids)),
                interpretation="Repeated pattern supports a cohort review instead of isolated drafts.",
                supports="cohort_action",
                strength="medium",
            ),
        ),
        bucket_trace=BucketTrace(
            lane="needs_judgment",
            rule_id="lane:cohort:blast-radius",
            rule_label="Cohort actions require human judgment because they affect multiple accounts",
            inputs={"candidate_account_count": len(candidate_account_ids)},
            thresholds={"dual_control_required": True},
            matched=("cohort_action", "human_judgment_required"),
            near_misses=(),
            source_ids=source_ids,
        ),
        coverage_trace=CoverageTrace(
            book_size=book_size,
            accounts_scanned=accounts_scanned,
            included_reason="cohort_collapse",
            excluded_or_suppressed_reason=None,
            last_reviewed_at=None,
            freshness="current_sweep",
        ),
        open_questions=("whether every account belongs in this cohort",),
        confidence=0.68,
        feedback_hooks=_feedback_hooks(),
    )


def build_identity_escalation_packet(
    *,
    candidate_account_ids: tuple[str, ...],
    contact_source_ids: tuple[str, ...],
    as_of: str,
) -> CSMWorkPacket:
    source_ids = contact_source_ids or candidate_account_ids
    reason = "Ambiguous contact identity; no account was auto-selected."
    return CSMWorkPacket(
        packet_id=f"packet:identity-escalation:{as_of}:{len(candidate_account_ids)}",
        account_id=None,
        account_name="Ambiguous account identity",
        generated_at=as_of,
        as_of_day=as_of,
        cadence="event_driven",
        job_type="internal_escalation",
        lane="blocked",
        primary_next_step="Resolve the account identity before any customer action",
        why_now=reason,
        diagnostic_hypothesis=DiagnosticHypothesis(
            summary=reason,
            signals=("contact resolution returned multiple candidate accounts",),
            counter_signals=(),
            unknowns=("correct account identity",),
            confidence=0.35,
            source_ids=source_ids,
        ),
        implied_customer_state="Customer state is unknown until identity is resolved.",
        recommended_action=RecommendedAction(
            action_id=f"action:identity-escalation:{as_of}",
            action_type="internal_escalation",
            label="Resolve identity",
            objective="Prevent an agent from writing to the wrong account.",
            recipient_role=None,
            recipient_contact_id=None,
            message_strategy="Keep the work internal until account identity is exact.",
            success_criteria=("One account is selected by a human or source mapping.",),
            blocked_by=("ambiguous_account_identity",),
            source_ids=source_ids,
        ),
        contact_plan=ContactPlan(
            primary_contact=None,
            backup_contact=None,
            internal_owner=None,
            tone="internal only",
            channel="operator review",
            reason_for_contact_choice="No customer contact is safe until identity is resolved.",
            source_ids=source_ids,
        ),
        prepared_artifacts=(
            PreparedArtifact(
                artifact_id=f"artifact:identity-escalation:{as_of}",
                artifact_type="internal_brief",
                title="Resolve ambiguous account identity",
                body_or_outline=f"Candidate accounts: {', '.join(candidate_account_ids)}",
                intended_audience="CS operator",
                requires_approval=False,
                source_ids=source_ids,
            ),
        ),
        allowed_ctas=(
            AllowedCTA(
                cta_id=f"cta:identity-escalation:{as_of}:inspect",
                label="Inspect candidates",
                kind="inspect",
                enabled=True,
                disabled_reason=None,
                governance_requirement=None,
                readonly_behavior="Open local candidate details only.",
                source_ids=source_ids,
            ),
            AllowedCTA(
                cta_id=f"cta:identity-escalation:{as_of}:feedback",
                label="Leave feedback",
                kind="leave_feedback",
                enabled=True,
                disabled_reason=None,
                governance_requirement=None,
                readonly_behavior="Record local packet feedback only.",
                source_ids=source_ids,
            ),
        ),
        governance=GovernanceBoundary(
            mode="blocked",
            requires_human_principal=True,
            requires_action_gate=False,
            can_execute_from_ui=False,
            audit_requirements=("identity_resolution_required",),
        ),
        evidence_chain=tuple(
            EvidenceChainStep(
                step_id=f"evidence:identity:{idx}",
                claim=f"Contact evidence {source_id} maps ambiguously.",
                source_type="crm",
                source_id=source_id,
                field="email",
                observed_value=source_id,
                interpretation="Identity is not safe enough for an external action.",
                supports="internal_escalation",
                strength="strong",
            )
            for idx, source_id in enumerate(source_ids, start=1)
        ),
        bucket_trace=BucketTrace(
            lane="blocked",
            rule_id="lane:identity:ambiguous-account",
            rule_label="Ambiguous account identity blocks external action",
            inputs={"candidate_account_count": len(candidate_account_ids)},
            thresholds={"exactly_one_account_required": True},
            matched=("ambiguous_identity", "blocked"),
            near_misses=(),
            source_ids=source_ids,
        ),
        coverage_trace=CoverageTrace(
            book_size=len(candidate_account_ids),
            accounts_scanned=len(candidate_account_ids),
            included_reason="identity_escalation",
            excluded_or_suppressed_reason=None,
            last_reviewed_at=None,
            freshness="current_sweep",
        ),
        open_questions=("which account owns this contact",),
        confidence=0.35,
        feedback_hooks=_feedback_hooks(),
    )


def planned_customer_draft(inputs: PacketInputs) -> str | None:
    if not inputs.customer_contact_allowed or inputs.selected_contact is None:
        return None
    blocked_value_path = _blocked_value_path(inputs)
    if blocked_value_path.missing_required_sources:
        return None
    if blocked_value_path.triggered:
        return (
            f"Hi {inputs.selected_contact.name}, {inputs.account.name} is blocked on "
            f"{blocked_value_path.blocking_dependency}. I want to reset the "
            f"{blocked_value_path.blocked_workflow} recovery plan. The data points to "
            f"that dependency holding back {blocked_value_path.purchased_value_path}; "
            "can we use a working session to "
            "confirm the technical owner, the next corrective step, reset the activation date, "
            "and record the recovery checkpoint?"
        )
    blocker = _blocker_phrase(inputs)
    return (
        f"Hi {inputs.selected_contact.name}, {inputs.account.name} is blocked on {blocker}. "
        "Can we confirm the owner, decide the next technical step, and reset the activation date?"
    )


def _source_ids(
    evidence: tuple[EvidenceRef, ...],
    evidence_chain: tuple[EvidenceChainStep, ...] = (),
) -> tuple[str, ...]:
    seen: list[str] = []
    for ref in evidence:
        if ref.source_id not in seen:
            seen.append(ref.source_id)
    for step in evidence_chain:
        if step.source_id not in seen:
            seen.append(step.source_id)
    return tuple(seen)


def _job_type(inputs: PacketInputs) -> JobType:
    blocked_value_path = _blocked_value_path(inputs)
    if not inputs.evidence and not blocked_value_path.triggered:
        return "needs_data"
    if blocked_value_path.missing_required_sources and blocked_value_path.blocking_dependency != "unconfirmed dependency":
        return "needs_data"
    if blocked_value_path.triggered:
        return "customer_outreach" if inputs.customer_contact_allowed else "csm_onboarding_brief"
    if inputs.disposition == "escalate":
        return "internal_escalation"
    if inputs.internal_bridge_decision is not None and not getattr(inputs.internal_bridge_decision, "abstained", True):
        target = getattr(inputs.internal_bridge_decision, "target", None)
        if target == "product":
            return "product_feedback_synthesis"
        return "internal_escalation"
    if any(_case_product_feedback(case) for case in inputs.cases):
        return "product_feedback_synthesis"
    if inputs.content_route_title or inputs.action == "content_route":
        return "education_recommendation"
    if any(opp.opportunity_type.lower() == "renewal" for opp in inputs.opportunities):
        return "renewal_risk_review"
    if any(opp.opportunity_type.lower() == "expansion" for opp in inputs.opportunities):
        return "sales_handoff"
    if any(_factor_name(factor) in {"milestones_overdue", "days_overdue"} for factor in inputs.priority_factors):
        return "customer_outreach" if inputs.customer_contact_allowed else "csm_onboarding_brief"
    if any(_factor_name(factor) == "success_plan_overdue" for factor in inputs.priority_factors):
        return "success_plan_update"
    if inputs.customer_contact_allowed:
        return "customer_outreach"
    return "internal_escalation"


def _lane(inputs: PacketInputs, job_type: JobType) -> Lane:
    if job_type == "needs_data":
        return "blocked"
    if inputs.proposal_status == "pending" or job_type in {"internal_escalation", "product_feedback_synthesis"}:
        return "needs_judgment"
    if inputs.proposal_status in {"approved", "denied"}:
        return "covered"
    return "prepared"


def _primary_next_step(inputs: PacketInputs, job_type: JobType) -> str:
    blocked_value_path = _blocked_value_path(inputs)
    if blocked_value_path.missing_required_sources and blocked_value_path.blocking_dependency != "unconfirmed dependency":
        return (
            "Complete success-plan baseline and current-state evidence coverage before recommending "
            "customer-facing recovery"
        )
    if blocked_value_path.triggered:
        contact_name = inputs.selected_contact.name if inputs.selected_contact else "the accountable customer owner"
        return (
            f"Run blocked value path recovery with {contact_name}: confirm owner, corrective step, "
            f"and date for {blocked_value_path.blocking_dependency}"
        )
    blocker = _blocker_phrase(inputs)
    contact_name = inputs.selected_contact.name if inputs.selected_contact else "the right owner"
    if job_type == "product_feedback_synthesis":
        return f"Triage {blocker} with product/technical owner before generic outreach"
    if job_type == "education_recommendation":
        title = inputs.content_route_title or "the matched help resource"
        return f"Preview {title} and confirm it addresses {blocker}"
    if job_type == "sales_handoff":
        return f"Send sales a brief on the expansion context and {blocker}"
    if job_type == "renewal_risk_review":
        return f"Review renewal risk tied to {blocker}"
    if job_type == "success_plan_update":
        return f"Update the success plan owner/date for {blocker}"
    if job_type == "csm_onboarding_brief":
        return f"Prepare an internal onboarding brief for {blocker}"
    if job_type == "needs_data":
        return "Collect missing source data before recommending a customer action"
    return f"Ask {contact_name} to resolve {blocker} and reset the activation plan"


def _why_now(inputs: PacketInputs) -> str:
    blocked_value_path = _blocked_value_path(inputs)
    if blocked_value_path.missing_required_sources and blocked_value_path.blocking_dependency != "unconfirmed dependency":
        return (
            "Potential blocked value path is present, but analysis coverage is insufficient: missing "
            f"{', '.join(blocked_value_path.missing_required_sources)}."
        )
    if blocked_value_path.triggered:
        return (
            f"{blocked_value_path.blocking_dependency} is now tied to value realization: "
            f"{'; '.join(blocked_value_path.evidence_claims[:3])}"
        )
    score = inputs.priority_score
    factor_text = ", ".join(_factor_name(factor) for factor in inputs.priority_factors[:3])
    if score is not None and factor_text:
        return f"Priority score {score} is driven by {factor_text}; evidence is present in the source chain."
    if inputs.evidence:
        return "This account has fresh source evidence requiring operator review."
    return "The account was scanned, but required source evidence is missing."


def _diagnostic_hypothesis(
    inputs: PacketInputs,
    evidence_chain: tuple[EvidenceChainStep, ...],
) -> DiagnosticHypothesis:
    blocked_value_path = _blocked_value_path(inputs)
    if blocked_value_path.missing_required_sources and blocked_value_path.blocking_dependency != "unconfirmed dependency":
        return DiagnosticHypothesis(
            summary="The agent has not completed the required baseline-plan and current-state evidence review.",
            signals=blocked_value_path.evidence_claims,
            counter_signals=(),
            unknowns=blocked_value_path.missing_required_sources,
            confidence=0.25,
            source_ids=blocked_value_path.source_ids or tuple(step.source_id for step in evidence_chain),
        )
    if blocked_value_path.triggered:
        return DiagnosticHypothesis(
            summary=(
                f"The account is in blocked value path recovery: "
                f"{blocked_value_path.blocking_dependency} is preventing "
                f"{blocked_value_path.purchased_value_path} from turning into realized value."
            ),
            signals=blocked_value_path.evidence_claims,
            counter_signals=blocked_value_path.counter_signals,
            unknowns=blocked_value_path.unknowns,
            confidence=_confidence(inputs, evidence_chain),
            source_ids=blocked_value_path.source_ids or tuple(step.source_id for step in evidence_chain),
        )
    signals = tuple(step.interpretation for step in evidence_chain[:5])
    counter_signals = ()
    if inputs.priority_score is not None and inputs.priority_score < 30:
        counter_signals = ("Priority score is below the needs-judgment threshold.",)
    unknowns = _unknowns(inputs)
    return DiagnosticHypothesis(
        summary=_blocker_sentence(inputs),
        signals=signals,
        counter_signals=counter_signals,
        unknowns=unknowns,
        confidence=_confidence(inputs, evidence_chain),
        source_ids=tuple(step.source_id for step in evidence_chain),
    )


def _recommended_action(
    inputs: PacketInputs,
    job_type: JobType,
    label: str,
    source_ids: tuple[str, ...],
) -> RecommendedAction:
    blocked_value_path = _blocked_value_path(inputs)
    action_type = (
        "initiate_customer_call"
        if blocked_value_path.triggered and inputs.customer_contact_allowed
        else "recommend_next_best_action"
        if blocked_value_path.missing_required_sources and blocked_value_path.blocking_dependency != "unconfirmed dependency"
        else inputs.action or job_type
    )
    blocked_by: tuple[str, ...] = ()
    if inputs.customer_contact_allowed and inputs.selected_contact is None:
        blocked_by = ("no_consented_contact",)
    if inputs.proposal_status is None and action_type in {
        "draft_customer_outreach",
        "content_route",
        "cohort_action",
        "initiate_customer_call",
    }:
        blocked_by = (*blocked_by, "no_action_gate_proposal")
    return RecommendedAction(
        action_id=f"action:{inputs.account.account_id}:{job_type}",
        action_type=action_type,
        label=label,
        objective=_objective(inputs, job_type),
        recipient_role=inputs.recipient_role,
        recipient_contact_id=inputs.selected_contact.contact_id if inputs.selected_contact else None,
        message_strategy=_message_strategy(inputs, job_type),
        success_criteria=_success_criteria(inputs, job_type),
        blocked_by=blocked_by,
        source_ids=source_ids,
    )


def _contact_plan(inputs: PacketInputs, source_ids: tuple[str, ...]) -> ContactPlan:
    backups = [
        contact for contact in inputs.contacts
        if contact.consent_to_contact
        and (inputs.selected_contact is None or contact.contact_id != inputs.selected_contact.contact_id)
    ]
    return ContactPlan(
        primary_contact=_contact_row(inputs.selected_contact),
        backup_contact=_contact_row(backups[0]) if backups else None,
        internal_owner=inputs.account.owner_id,
        tone="specific, operational, and approval-safe" if inputs.selected_contact else "internal only",
        channel=(
            "working_session_request"
            if _blocked_value_path(inputs).triggered and inputs.selected_contact and inputs.customer_contact_allowed
            else "email" if inputs.selected_contact and inputs.customer_contact_allowed else "internal_note"
        ),
        reason_for_contact_choice=_contact_reason(inputs),
        source_ids=source_ids,
    )


def _artifact(
    inputs: PacketInputs,
    job_type: JobType,
    primary_next_step: str,
    source_ids: tuple[str, ...],
) -> PreparedArtifact:
    artifact_type: ArtifactType = {
        "sales_handoff": "sales_handoff",
        "csm_onboarding_brief": "csm_brief",
        "qbr_packet": "qbr_packet",
        "ebr_packet": "ebr_packet",
        "product_feedback_synthesis": "product_feedback",
        "education_recommendation": "education_recommendation",
        "renewal_risk_review": "renewal_risk_note",
        "success_plan_update": "success_plan_update",
        "internal_escalation": "internal_brief",
    }.get(job_type, "email_draft")  # type: ignore[assignment]
    body = planned_customer_draft(inputs) if artifact_type == "email_draft" else None
    if body is None:
        body = (
            f"{primary_next_step}\n\nEvidence to inspect: "
            f"{'; '.join(step.claim for step in _evidence_chain(inputs)[:4])}"
        )
    return PreparedArtifact(
        artifact_id=f"artifact:{inputs.account.account_id}:{artifact_type}",
        artifact_type=artifact_type,
        title=f"{inputs.account.name}: {primary_next_step}",
        body_or_outline=body,
        intended_audience=_artifact_audience(inputs, job_type),
        requires_approval=artifact_type == "email_draft" or job_type in {"sales_handoff", "renewal_risk_review"},
        source_ids=source_ids,
    )


def _governance(inputs: PacketInputs) -> GovernanceBoundary:
    executing_action = inputs.action in {
        "draft_customer_outreach",
        "content_route",
        "cohort_action",
        "initiate_customer_call",
    }
    return GovernanceBoundary(
        mode="readonly_demo",
        requires_human_principal=executing_action,
        requires_action_gate=executing_action,
        can_execute_from_ui=False,
        audit_requirements=(
            "action_gate.proposal_id" if executing_action else "operator.review",
            "human_approval_before_external_write" if executing_action else "local_feedback_only",
        ),
    )


def _allowed_ctas(
    inputs: PacketInputs,
    governance: GovernanceBoundary,
    source_ids: tuple[str, ...],
) -> tuple[AllowedCTA, ...]:
    proposal_present = bool(inputs.proposal_id)
    governed = governance.requires_action_gate
    disabled_reason = (
        "Readonly demo cannot execute external actions; use ActionGate metadata for review."
        if proposal_present and governed
        else "Readonly demo cannot execute this action."
    )
    return (
        AllowedCTA(
            cta_id=f"cta:{inputs.account.account_id}:inspect",
            label="Inspect evidence",
            kind="inspect",
            enabled=True,
            disabled_reason=None,
            governance_requirement=None,
            readonly_behavior="Open packet evidence and source drawers locally.",
            source_ids=source_ids,
        ),
        AllowedCTA(
            cta_id=f"cta:{inputs.account.account_id}:preview",
            label="Preview artifact",
            kind="preview",
            enabled=True,
            disabled_reason=None,
            governance_requirement=None,
            readonly_behavior="Render the prepared artifact without sending it.",
            source_ids=source_ids,
        ),
        AllowedCTA(
            cta_id=f"cta:{inputs.account.account_id}:copy",
            label="Copy artifact",
            kind="copy",
            enabled=True,
            disabled_reason=None,
            governance_requirement="human reviews copied text before external use",
            readonly_behavior="Copy local text only; no connector write.",
            source_ids=source_ids,
        ),
        AllowedCTA(
            cta_id=f"cta:{inputs.account.account_id}:approve",
            label="Approve through ActionGate",
            kind="approve",
            enabled=False,
            disabled_reason=disabled_reason,
            governance_requirement=(
                f"ActionGate proposal {inputs.proposal_id}" if proposal_present else "ActionGate proposal required"
            ),
            readonly_behavior="Explain approval requirement; no send in hosted demo.",
            source_ids=source_ids,
        ),
        AllowedCTA(
            cta_id=f"cta:{inputs.account.account_id}:feedback",
            label="Leave feedback",
            kind="leave_feedback",
            enabled=True,
            disabled_reason=None,
            governance_requirement=None,
            readonly_behavior="Record local packet feedback only.",
            source_ids=source_ids,
        ),
    )


def _evidence_chain(inputs: PacketInputs) -> tuple[EvidenceChainStep, ...]:
    observations = _observed_values(inputs)
    steps: list[EvidenceChainStep] = []
    for idx, ref in enumerate(inputs.evidence, start=1):
        observed = observations.get(ref.source_id, ref.observed_at)
        steps.append(EvidenceChainStep(
            step_id=f"evidence:{inputs.account.account_id}:{idx}",
            claim=_claim_for_ref(ref, observed),
            source_type=ref.source,
            source_id=ref.source_id,
            field=ref.field,
            observed_value=observed,
            interpretation=_interpretation_for_ref(ref, inputs),
            supports=_blocker_phrase(inputs),
            strength=_strength_for_ref(ref),
        ))
    blocked_value_path = _blocked_value_path(inputs)
    if blocked_value_path.triggered:
        for claim_idx, claim in enumerate(blocked_value_path.evidence_claims, start=1):
            source_id = (
                blocked_value_path.source_ids[claim_idx - 1]
                if claim_idx - 1 < len(blocked_value_path.source_ids)
                else inputs.account.account_id
            )
            steps.append(EvidenceChainStep(
                step_id=f"evidence:{inputs.account.account_id}:blocked-value-path:{claim_idx}",
                claim=claim,
                source_type=_source_type_for_blocked_value_claim(claim),
                source_id=source_id,
                field="blocked_value_path_assessment",
                observed_value=claim,
                interpretation="Purchased value is blocked by a dependency, not by generic awareness or motivation.",
                supports="blocked_value_path_recovery",
                strength="strong" if claim_idx <= 3 else "medium",
            ))
    return tuple(steps)


def _observed_values(inputs: PacketInputs) -> dict[str, str]:
    values: dict[str, str] = {}
    for signal in inputs.usage_signals:
        values[signal.signal_id] = f"{signal.metric_name}={signal.value:g} {signal.unit} at {signal.observed_at}"
    for plan in inputs.success_plans:
        values[plan.plan_id] = f"status={plan.status}; target={plan.target_date}; objectives={', '.join(plan.objectives)}"
    for case in inputs.cases:
        values[case.case_id] = (
            f"{_safe_case_subject(case)}; status={case.status}; priority={case.priority}"
        )
    for milestone in inputs.milestones:
        for source_id in milestone.evidence_signal_ids:
            values.setdefault(
                source_id,
                f"{milestone.milestone} expected by {milestone.expected_by}; achieved={milestone.achieved_at or 'not yet'}",
            )
    values.setdefault(inputs.account.account_id, f"account={inputs.account.name}")
    return values


def _bucket_trace(inputs: PacketInputs, lane: Lane, source_ids: tuple[str, ...]) -> BucketTrace:
    score = inputs.priority_score or 0
    matched = []
    if _blocked_value_path(inputs).triggered:
        matched.append("blocked_value_path_recovery")
    if score >= 70:
        matched.append("daily_high_priority")
    if inputs.proposal_status == "pending":
        matched.append("pending_action_gate")
    if lane == "needs_judgment":
        matched.append("human_judgment_required")
    if not matched:
        matched.append(lane)
    return BucketTrace(
        lane=lane,
        rule_id=f"lane:{lane}:score-action-evidence",
        rule_label="Lane chosen from priority, proposal state, job type, and evidence",
        inputs={
            "priority_score": score,
            "proposal_status": inputs.proposal_status,
            "action": inputs.action,
            "motion": inputs.motion,
            "evidence_count": len(inputs.evidence),
            "blocked_value_path": _blocked_value_path(inputs).triggered,
        },
        thresholds={
            "daily_high_priority": 70,
            "weekly_priority": 30,
            "evidence_required_for_confident_action": True,
        },
        matched=tuple(matched),
        near_misses=tuple(
            name for name, met in (
                ("weekly_priority", score >= 30),
                ("customer_contact_allowed", inputs.customer_contact_allowed),
            )
            if not met
        ),
        source_ids=source_ids,
    )


def _feedback_hooks() -> tuple[FeedbackHook, ...]:
    labels = {
        "wrong_diagnosis": "Wrong diagnosis",
        "wrong_contact": "Wrong contact",
        "wrong_action": "Wrong action",
        "missing_evidence": "Missing evidence",
        "wrong_bucket": "Wrong bucket",
        "stale_data": "Stale data",
        "product_feedback_candidate": "Product feedback candidate",
        "education_resource_candidate": "Education resource candidate",
        "dismiss_monitor": "Dismiss or monitor",
    }
    return tuple(
        FeedbackHook(
            category=category,
            label=labels[category],
            local_only=True,
            readonly_behavior="Store as local demo feedback; does not approve or execute work.",
        )
        for category in FEEDBACK_CATEGORIES
    )


def _cadence(inputs: PacketInputs, job_type: JobType) -> Cadence:
    if job_type in {"customer_outreach", "internal_escalation", "product_feedback_synthesis"}:
        return "daily"
    if job_type in {"qbr_packet", "ebr_packet"}:
        return "quarterly"
    if job_type == "renewal_risk_review":
        return "monthly"
    if inputs.cases:
        return "event_driven"
    return "weekly"


def _implied_customer_state(inputs: PacketInputs, job_type: JobType) -> str:
    blocked_value_path = _blocked_value_path(inputs)
    if blocked_value_path.missing_required_sources and blocked_value_path.blocking_dependency != "unconfirmed dependency":
        return (
            "Customer state cannot be safely assessed until the original success-plan baseline and "
            "current evidence review are complete."
        )
    if blocked_value_path.triggered:
        return (
            f"Customer appears engaged enough for recovery, but {blocked_value_path.blocking_dependency} "
            f"is blocking realized value from {blocked_value_path.purchased_value_path}."
        )
    if job_type == "product_feedback_synthesis":
        return "Customer may be blocked by a product or integration issue that needs internal triage."
    if any(_factor_name(factor) in {"milestones_overdue", "days_overdue"} for factor in inputs.priority_factors):
        return "Activation is stalled against dated milestones despite usage evidence."
    if inputs.priority_score and inputs.priority_score >= 70:
        return "Account needs near-term CSM judgment before the next cadence review."
    return "Customer state is monitorable, but the current evidence does not justify escalation beyond this packet."


def _objective(inputs: PacketInputs, job_type: JobType) -> str:
    blocked_value_path = _blocked_value_path(inputs)
    if blocked_value_path.missing_required_sources and blocked_value_path.blocking_dependency != "unconfirmed dependency":
        return "Complete multi-source evidence coverage before any customer-facing recovery recommendation."
    if blocked_value_path.triggered:
        return (
            f"Restore the blocked value path by assigning an owner, corrective step, and date for "
            f"{blocked_value_path.blocking_dependency}."
        )
    if job_type == "product_feedback_synthesis":
        return "Convert customer blocker evidence into an internal product/technical triage brief."
    if job_type == "education_recommendation":
        return "Route a relevant self-help resource only if it addresses the evidenced adoption gap."
    if job_type == "sales_handoff":
        return "Keep sales context aligned with customer-success evidence before expansion pursuit."
    return f"Resolve {_blocker_phrase(inputs)} with an accountable owner and date."


def _message_strategy(inputs: PacketInputs, job_type: JobType) -> str:
    blocked_value_path = _blocked_value_path(inputs)
    if blocked_value_path.missing_required_sources and blocked_value_path.blocking_dependency != "unconfirmed dependency":
        return "Do not draft customer-facing language until missing source groups are reviewed."
    if blocked_value_path.triggered:
        return (
            "Frame this as a recovery working session. Anchor every claim in the case, adoption, "
            "entitlement, and milestone facts; avoid generic adoption nudges or unsupported blame."
        )
    if job_type == "product_feedback_synthesis":
        return "Lead with the customer-reported blocker, then attach source evidence for product/engineering review."
    if job_type == "education_recommendation":
        return "Preview the resource and route it as supporting help, not as a substitute for CSM judgment."
    if inputs.selected_contact:
        backup = " Include the technical backup if the blocker needs implementation detail." if _backup_contact(inputs) else ""
        return f"Be concrete about {_blocker_phrase(inputs)}, ask for owner/date, and avoid generic check-in language.{backup}"
    return "Keep the work internal until a consented contact or owner is identified."


def _success_criteria(inputs: PacketInputs, job_type: JobType) -> tuple[str, ...]:
    blocked_value_path = _blocked_value_path(inputs)
    if blocked_value_path.missing_required_sources and blocked_value_path.blocking_dependency != "unconfirmed dependency":
        return (
            "Original success-plan baseline is reconstructed from all required source groups.",
            "Current state is assessed from all required current evidence groups.",
            "Any missing source is named before customer-facing activity.",
        )
    if _blocked_value_path(inputs).triggered:
        return (
            "Customer-side owner is named.",
            "Technical blocker has a corrective next step.",
            "Recovery date and follow-up checkpoint are recorded.",
            "Customer-facing action remains approval-gated.",
        )
    if job_type == "product_feedback_synthesis":
        return ("Internal owner accepts or rejects the blocker hypothesis.", "Customer-facing follow-up is not sent until approved.")
    if job_type == "education_recommendation":
        return ("Resource is verified against evidence.", "Human confirms whether to route or monitor.")
    return ("Owner is identified.", "Next date or decision is recorded.", "External action remains approval-gated.")


def _artifact_audience(inputs: PacketInputs, job_type: JobType) -> str:
    if job_type in {"product_feedback_synthesis", "internal_escalation", "sales_handoff", "csm_onboarding_brief"}:
        return "internal CS/product/sales operator"
    if inputs.selected_contact:
        return f"{inputs.selected_contact.name} ({inputs.selected_contact.email})"
    return "CS operator"


def _included_reason(inputs: PacketInputs, job_type: JobType) -> str:
    if _blocked_value_path(inputs).triggered:
        return "selected_for_blocked_value_path_recovery"
    if inputs.priority_score is not None:
        return f"selected_for_{job_type}_score_{inputs.priority_score}"
    return f"selected_for_{job_type}"


def _freshness(inputs: PacketInputs) -> str:
    if not inputs.evidence:
        return "missing"
    latest = max(ref.observed_at for ref in inputs.evidence)
    return f"latest_evidence_at:{latest}"


def _confidence(inputs: PacketInputs, evidence_chain: tuple[EvidenceChainStep, ...]) -> float:
    if not evidence_chain:
        return 0.0
    score = 0.55 + min(0.3, len(evidence_chain) * 0.04)
    if inputs.selected_contact:
        score += 0.08
    if inputs.cases and inputs.milestones:
        score += 0.05
    return round(min(score, 0.94), 2)


def _unknowns(inputs: PacketInputs) -> tuple[str, ...]:
    blocked_value_path = _blocked_value_path(inputs)
    if blocked_value_path.missing_required_sources and blocked_value_path.blocking_dependency != "unconfirmed dependency":
        return blocked_value_path.missing_required_sources
    if blocked_value_path.triggered:
        return blocked_value_path.unknowns
    unknowns: list[str] = []
    if not inputs.selected_contact and inputs.customer_contact_allowed:
        unknowns.append("which consented customer contact owns the next step")
    if not inputs.cases:
        unknowns.append("whether there is an open support blocker")
    if not inputs.success_plans:
        unknowns.append("current success-plan owner/date")
    if inputs.internal_bridge_decision is not None and getattr(inputs.internal_bridge_decision, "abstained", False):
        unknowns.append(getattr(inputs.internal_bridge_decision, "reason", "internal bridge abstained"))
    return tuple(unknowns)


def _blocker_sentence(inputs: PacketInputs) -> str:
    blocked_value_path = _blocked_value_path(inputs)
    if blocked_value_path.triggered:
        return (
            f"The likely blocker is {blocked_value_path.blocking_dependency}, which is holding back "
            f"{blocked_value_path.purchased_value_path}."
        )
    return f"The likely blocker is {_blocker_phrase(inputs)}."


def _blocker_phrase(inputs: PacketInputs) -> str:
    blocked_value_path = _blocked_value_path(inputs)
    if blocked_value_path.triggered:
        return (
            f"{blocked_value_path.blocking_dependency} blocking "
            f"{blocked_value_path.blocked_workflow}"
        )
    overdue = [m for m in inputs.milestones if m.achieved_at is None and m.expected_by <= inputs.as_of]
    if overdue and inputs.cases:
        return f"{_humanize(overdue[0].milestone)} plus {_safe_case_subject(inputs.cases[0]).lower()}"
    if overdue:
        return ", ".join(_humanize(m.milestone) for m in overdue[:2])
    if inputs.cases:
        return _safe_case_subject(inputs.cases[0]).lower()
    if inputs.success_plans:
        return f"success plan target {inputs.success_plans[0].target_date}"
    if inputs.priority_factors:
        return ", ".join(_humanize(_factor_name(factor)) for factor in inputs.priority_factors[:2])
    return "insufficient source evidence"


def _case_product_feedback(case: CRMCase) -> bool:
    if _contains_untrusted_directive(case.subject):
        return False
    text = case.subject.lower()
    return any(token in text for token in ("integration", "not working", "failing", "bug", "missing"))


def _safe_case_subject(case: CRMCase) -> str:
    if _contains_untrusted_directive(case.subject):
        return "customer-reported case content withheld pending review"
    return case.subject.strip()


def _contains_untrusted_directive(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _UNTRUSTED_DIRECTIVE_MARKERS)


def _contact_reason(inputs: PacketInputs) -> str:
    if inputs.selected_contact is None:
        return "No consented contact was selected; keep work internal."
    blocked_value_path = _blocked_value_path(inputs)
    if blocked_value_path.triggered:
        role = inputs.recipient_role or inputs.selected_contact.role or "customer stakeholder"
        return (
            f"{inputs.selected_contact.name} is the consented {role} for recovery coordination; "
            f"{blocked_value_path.technical_owner_status}."
        )
    role = inputs.recipient_role or inputs.selected_contact.role or "known stakeholder"
    resolution = inputs.recipient_resolution or "backend recipient resolver"
    return f"{inputs.selected_contact.name} is the consented {role} selected by {resolution} for this blocker."


def _contact_row(contact: CRMContact | None) -> dict[str, Any] | None:
    if contact is None:
        return None
    return {
        "contact_id": contact.contact_id,
        "name": contact.name,
        "email": contact.email,
        "role": contact.role,
        "title": contact.title,
        "consent_to_contact": contact.consent_to_contact,
    }


def _backup_contact(inputs: PacketInputs) -> CRMContact | None:
    for contact in inputs.contacts:
        if contact.consent_to_contact and (inputs.selected_contact is None or contact.contact_id != inputs.selected_contact.contact_id):
            return contact
    return None


def _claim_for_ref(ref: EvidenceRef, observed: str) -> str:
    return f"{ref.source}.{ref.field} reports {observed}"


def _interpretation_for_ref(ref: EvidenceRef, inputs: PacketInputs) -> str:
    if ref.source == "crm" and ref.field == "status":
        return "Open customer case may explain adoption friction."
    if ref.source == "telemetry":
        return "Product telemetry anchors the activation/adoption gap."
    if ref.field == "target_date":
        return "Success plan timing is stale or due."
    if ref.field == "health_score":
        return "Health score gives counter/context for the recommendation."
    return f"{ref.source} evidence supports the packet diagnosis."


def _strength_for_ref(ref: EvidenceRef) -> Literal["weak", "medium", "strong"]:
    if ref.source in {"telemetry", "crm"}:
        return "strong"
    if ref.source == "cs_platform":
        return "medium"
    return "weak"


def _factor_name(factor: Any) -> str:
    return str(getattr(factor, "name", "unknown"))


def _blocked_value_path(inputs: PacketInputs) -> BlockedValuePathAssessment:
    return assess_blocked_value_path(
        account=inputs.account,
        as_of=inputs.as_of,
        cases=inputs.cases,
        success_plans=inputs.success_plans,
        usage_signals=inputs.usage_signals,
        milestones=inputs.milestones,
        contacts=inputs.contacts,
        selected_contact=inputs.selected_contact,
        priority_factors=inputs.priority_factors,
        adoption=inputs.adoption,
        entitlements=inputs.entitlements,
        stakeholders=inputs.stakeholders,
        company=inputs.company,
        health=inputs.health,
        ctas=inputs.ctas,
        communication_signals=inputs.communication_signals,
        internal_notes=inputs.internal_notes,
        onboarding_projects=inputs.onboarding_projects,
        onboarding_phases=inputs.onboarding_phases,
        onboarding_tasks=inputs.onboarding_tasks,
    )


def _source_type_for_blocked_value_claim(claim: str) -> str:
    lowered = claim.lower()
    if "case" in lowered:
        return "crm"
    if "entitlement" in lowered or "adoption" in lowered or "health" in lowered:
        return "cs_platform"
    if "milestone" in lowered:
        return "telemetry"
    return "cs_platform"


def _humanize(value: str) -> str:
    known = {
        "activate_50pct_assets": "50% asset activation",
        "first_route_optimization": "first route optimization",
        "milestones_overdue": "overdue milestones",
        "days_overdue": "days overdue",
        "success_plan_overdue": "overdue success plan",
        "feature_depth_gap": "feature depth gap",
        "usage_outcome_unverified": "unverified usage outcome",
        "health_red": "red health",
        "health_yellow": "yellow health",
    }
    return known.get(value, value.replace("_", " "))
