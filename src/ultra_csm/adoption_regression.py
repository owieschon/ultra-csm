"""Ongoing account adoption regression workflow.

This workflow is deliberately not another onboarding/activation plan. It is an
observability-triggered CSM motion: product telemetry detects a meaningful usage
drop, then the agent re-reads all connected account evidence before deciding
whether the shift looks like support friction, entitlement/feature-depth decay,
relationship risk, delivery drag, or telemetry noise.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Literal

from ultra_csm.data_plane.contracts import (
    AdoptionSummary,
    CRMAccount,
    CRMContact,
    CSCompany,
    CustomerDataPlane,
    Entitlement,
    HealthScore,
    SuccessPlan,
    UsageSignal,
)
from ultra_csm.governance import ActionGate, ActionProposal, proposal_fields_for
from ultra_csm.value_model import (
    CustomerValueModel,
    account_attributes,
    build_customer_value_model,
    load_value_model_config,
    project_ttv_lens,
    resolve_tenant_tier,
)
from ultra_csm.workflow_core import (
    WorkflowDecisionTrace,
    WorkflowExecutionEnvelope,
    WorkflowOutputContract,
    WorkflowValidationResult,
    build_evidence_bundle,
    build_execution_envelope,
)
from ultra_csm.workflow_playbooks import (
    ACCOUNT_ADOPTION_REGRESSION,
    evaluate_source_coverage,
    workflow_packet_metadata,
)


PacketStatus = Literal["ready", "needs_data", "internal_only", "ignored"]
RegressionSeverity = Literal["none", "watch", "material", "severe"]


@dataclass(frozen=True)
class ProductUsageRegressionEvent:
    tenant_id: str
    account_id: str
    metric_name: str
    baseline_start: str
    baseline_end: str
    current_start: str
    current_end: str
    observed_at: str
    source: str = "product_usage_monitor"


@dataclass(frozen=True)
class AdoptionRegressionSourceReceipt:
    source_id: str
    source_type: str
    field: str
    observed_at: str
    claim: str
    customer_safe: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AdoptionRegressionCoverage:
    reviewed_sources: tuple[str, ...]
    missing_required_sources: tuple[str, ...]
    customer_output_blockers: tuple[str, ...]
    source_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MetricWindowComparison:
    metric_name: str
    baseline_value: float | None
    current_value: float | None
    absolute_change: float | None
    percent_change: float | None
    drop_ratio: float
    severity: RegressionSeverity
    baseline_source_ids: tuple[str, ...]
    current_source_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValueModelRegressionContext:
    config_version: str
    rule_name: str
    service_tier: str | None
    lifecycle_stage: str
    adoption_rate: float | None
    seat_penetration: float | None
    active_users: int | None
    licensed_users: int | None
    active_assets: int | None
    entitled_assets: int | None
    underused_capabilities: tuple[str, ...]
    priority_score: int | None
    value_factors: tuple[str, ...]
    source_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RegressionContributingContext:
    support_pressure: str
    open_high_priority_cases: int
    open_ctas: int
    success_plan_risk: str
    relationship_depth: int
    customer_comms_recent: int
    internal_notes_recent: int
    delivery_risk: str
    source_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AdoptionRegressionInterpretation:
    selected_hypothesis: str
    confidence: float
    severity: RegressionSeverity
    rationale: tuple[str, ...]
    alternatives: tuple[str, ...]
    source_ids: tuple[str, ...]
    open_questions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AdoptionRegressionRecommendedAction:
    action_type: str
    trigger: str
    label: str
    customer_safe_message: str | None
    source_ids: tuple[str, ...]
    suppressed: bool
    suppression_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AdoptionRegressionProposalRef:
    proposal_id: str
    action_type: str
    status: str
    autonomy_tier: int
    required_permission: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AdoptionRegressionPacket:
    workflow_id: str
    workflow_config_version: str
    execution_envelope: WorkflowExecutionEnvelope
    packet_id: str
    tenant_id: str
    status: PacketStatus
    account_id: str
    account_name: str
    generated_at: str
    trigger_receipt: AdoptionRegressionSourceReceipt
    coverage: AdoptionRegressionCoverage
    metric_comparisons: tuple[MetricWindowComparison, ...]
    value_context: ValueModelRegressionContext | None
    contributing_context: RegressionContributingContext
    interpretation: AdoptionRegressionInterpretation
    recommended_action: AdoptionRegressionRecommendedAction
    customer_language: str | None
    risks: tuple[str, ...]
    source_receipts: tuple[AdoptionRegressionSourceReceipt, ...]
    proposals: tuple[AdoptionRegressionProposalRef, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "workflow": workflow_packet_metadata(ACCOUNT_ADOPTION_REGRESSION),
            "workflow_id": self.workflow_id,
            "workflow_config_version": self.workflow_config_version,
            "execution_envelope": self.execution_envelope.to_dict(),
            "tenant_id": self.tenant_id,
            "status": self.status,
            "account_id": self.account_id,
            "account_name": self.account_name,
            "generated_at": self.generated_at,
            "trigger_receipt": self.trigger_receipt.to_dict(),
            "coverage": self.coverage.to_dict(),
            "metric_comparisons": [item.to_dict() for item in self.metric_comparisons],
            "value_context": self.value_context.to_dict() if self.value_context else None,
            "contributing_context": self.contributing_context.to_dict(),
            "interpretation": self.interpretation.to_dict(),
            "recommended_action": self.recommended_action.to_dict(),
            "customer_language": self.customer_language,
            "risks": list(self.risks),
            "source_receipts": [receipt.to_dict() for receipt in self.source_receipts],
            "proposals": [proposal.to_dict() for proposal in self.proposals],
        }


@dataclass(frozen=True)
class _AccountEvidence:
    account: CRMAccount | None
    contacts: tuple[CRMContact, ...]
    cases: tuple[Any, ...]
    company: CSCompany | None
    health_score: HealthScore | None
    ctas: tuple[Any, ...]
    success_plans: tuple[SuccessPlan, ...]
    adoption_summary: AdoptionSummary | None
    entitlements: tuple[Entitlement, ...]
    usage_signals: tuple[UsageSignal, ...]
    ttv_milestones: tuple[Any, ...]
    stakeholders: tuple[Any, ...]
    job_changes: tuple[Any, ...]
    gmail_signals: tuple[Any, ...]
    call_signals: tuple[Any, ...]
    internal_notes: tuple[Any, ...]
    onboarding_projects: tuple[Any, ...]
    onboarding_tasks: tuple[Any, ...]


def run_account_adoption_regression(
    *,
    data_plane: CustomerDataPlane,
    gate: ActionGate | None,
    event: ProductUsageRegressionEvent,
    as_of: str,
) -> AdoptionRegressionPacket:
    evidence = _gather_account_evidence(data_plane, event.account_id)
    account = evidence.account or CRMAccount(
        account_id=event.account_id,
        name=event.account_id,
        owner_id="unknown",
        industry=None,
    )
    trigger_receipt = AdoptionRegressionSourceReceipt(
        source_id=f"adoption-regression-trigger:{event.account_id}:{event.metric_name}:{event.observed_at}",
        source_type=event.source,
        field="metric_name",
        observed_at=event.observed_at,
        claim=(
            f"Usage regression monitor fired for {event.metric_name} "
            f"on {event.account_id}."
        ),
        customer_safe=False,
    )
    receipts = (trigger_receipt, *_build_source_receipts(event, account, evidence))
    comparisons = _metric_comparisons(event, evidence.usage_signals)
    value_model = _build_value_model(account, evidence, as_of=as_of)
    value_context = _value_context(
        account=account,
        evidence=evidence,
        value_model=value_model,
        receipts=receipts,
        as_of=as_of,
    )
    context = _contributing_context(evidence, receipts)
    coverage = _coverage(
        account=account,
        evidence=evidence,
        receipts=receipts,
        comparisons=comparisons,
        value_context=value_context,
    )
    interpretation = _interpret(comparisons, value_context, context, coverage)
    action = _recommended_action(
        account=account,
        evidence=evidence,
        interpretation=interpretation,
        coverage=coverage,
    )
    customer_language = _customer_language(account, action, interpretation)
    status = _packet_status(coverage, interpretation, action)
    risks = _risks(coverage, interpretation, action)
    proposals = _proposals(
        gate=gate,
        event=event,
        account=account,
        evidence=evidence,
        action=action,
        customer_language=customer_language,
        receipts=receipts,
        status=status,
    )
    packet_id = (
        f"adoption-regression:{event.account_id}:"
        f"{event.metric_name}:{_compact_timestamp(event.observed_at)}"
    )
    envelope = _execution_envelope(
        event=event,
        coverage=coverage,
        comparisons=comparisons,
        value_context=value_context,
        context=context,
        interpretation=interpretation,
        action=action,
        receipts=receipts,
        proposals=proposals,
        status=status,
    )
    return AdoptionRegressionPacket(
        workflow_id=ACCOUNT_ADOPTION_REGRESSION.workflow_id,
        workflow_config_version=ACCOUNT_ADOPTION_REGRESSION.config_version,
        execution_envelope=envelope,
        packet_id=packet_id,
        tenant_id=event.tenant_id,
        status=status,
        account_id=account.account_id,
        account_name=account.name,
        generated_at=f"{as_of}T00:00:00Z",
        trigger_receipt=trigger_receipt,
        coverage=coverage,
        metric_comparisons=comparisons,
        value_context=value_context,
        contributing_context=context,
        interpretation=interpretation,
        recommended_action=action,
        customer_language=customer_language,
        risks=risks,
        source_receipts=receipts,
        proposals=proposals,
    )


def _gather_account_evidence(data_plane: CustomerDataPlane, account_id: str) -> _AccountEvidence:
    crm = data_plane.crm
    cs = data_plane.cs
    telemetry = data_plane.telemetry
    comms = data_plane.comms
    onboarding = data_plane.onboarding
    projects = tuple(onboarding.list_projects_for_account(account_id)) if onboarding else ()
    tasks: list[Any] = []
    if onboarding:
        for project in projects:
            tasks.extend(onboarding.list_tasks(project.project_id))
    return _AccountEvidence(
        account=crm.get_account(account_id),
        contacts=tuple(crm.list_contacts(account_id)),
        cases=tuple(crm.list_cases(account_id)),
        company=cs.get_company(account_id),
        health_score=cs.get_health_score(account_id),
        ctas=tuple(cs.list_ctas(account_id, status="open")),
        success_plans=tuple(cs.list_success_plans(account_id)),
        adoption_summary=cs.get_adoption_summary(account_id),
        entitlements=tuple(telemetry.list_entitlements(account_id)),
        usage_signals=tuple(telemetry.list_usage_signals(account_id)),
        ttv_milestones=tuple(telemetry.list_ttv_milestones(account_id)),
        stakeholders=tuple(getattr(crm, "list_stakeholders", lambda _account_id: ())(account_id)),
        job_changes=tuple(getattr(crm, "list_job_changes", lambda _account_id: ())(account_id)),
        gmail_signals=tuple(comms.list_gmail_signals(account_id)) if comms else (),
        call_signals=tuple(comms.list_call_transcript_signals(account_id)) if comms else (),
        internal_notes=tuple(comms.list_internal_notes(account_id)) if comms else (),
        onboarding_projects=projects,
        onboarding_tasks=tuple(tasks),
    )


def _build_source_receipts(
    event: ProductUsageRegressionEvent,
    account: CRMAccount,
    evidence: _AccountEvidence,
) -> tuple[AdoptionRegressionSourceReceipt, ...]:
    receipts: list[AdoptionRegressionSourceReceipt] = [
        AdoptionRegressionSourceReceipt(
            account.account_id,
            "account_identity",
            "account_id",
            event.observed_at,
            f"Regression event maps to account {account.name}.",
            True,
        )
    ]
    if evidence.company is not None:
        receipts.append(AdoptionRegressionSourceReceipt(
            evidence.company.company_id,
            "cs_company",
            "lifecycle_stage",
            event.observed_at,
            f"Lifecycle stage is {evidence.company.lifecycle_stage}.",
            True,
        ))
    if evidence.health_score is not None:
        receipts.append(AdoptionRegressionSourceReceipt(
            evidence.health_score.account_id,
            "health_score",
            "score",
            evidence.health_score.measured_at,
            f"Health score is {evidence.health_score.score}.",
            False,
        ))
    if evidence.adoption_summary is not None:
        adoption = evidence.adoption_summary
        receipts.append(AdoptionRegressionSourceReceipt(
            adoption.account_id,
            "adoption_summary",
            "active_users",
            adoption.measured_at,
            (
                f"{adoption.active_users}/{adoption.licensed_users} users and "
                f"{adoption.active_assets}/{adoption.entitled_assets} assets are active."
            ),
            True,
        ))
    receipts.extend(
        AdoptionRegressionSourceReceipt(
            f"entitlement:{ent.account_id}:{ent.capability}",
            "entitlement",
            "capability",
            ent.starts_at,
            f"Entitled capability: {ent.capability}.",
            True,
        )
        for ent in evidence.entitlements
    )
    receipts.extend(
        AdoptionRegressionSourceReceipt(
            signal.signal_id,
            "product_telemetry",
            signal.metric_name,
            signal.observed_at,
            f"{signal.metric_name} observed with value {signal.value:g} {signal.unit}.",
            True,
        )
        for signal in evidence.usage_signals
    )
    receipts.extend(
        AdoptionRegressionSourceReceipt(
            case.case_id,
            "support_pressure",
            "status",
            case.created_at,
            f"Support case '{case.subject}' is {case.status} priority {case.priority}.",
            True,
        )
        for case in evidence.cases
    )
    receipts.extend(
        AdoptionRegressionSourceReceipt(
            cta.cta_id,
            "cs_platform_cta",
            "reason",
            cta.due_date,
            f"Open CTA: {cta.reason}.",
            False,
        )
        for cta in evidence.ctas
    )
    receipts.extend(
        AdoptionRegressionSourceReceipt(
            plan.plan_id,
            "success_plan",
            "objectives",
            plan.target_date,
            f"Success plan tracks {', '.join(plan.objects if hasattr(plan, 'objects') else plan.objectives)}.",
            False,
        )
        for plan in evidence.success_plans
    )
    receipts.extend(
        AdoptionRegressionSourceReceipt(
            contact.contact_id,
            "relationship_context",
            "email",
            event.observed_at,
            f"{contact.name} is a known contact.",
            True,
        )
        for contact in evidence.contacts
    )
    receipts.extend(
        AdoptionRegressionSourceReceipt(
            signal.signal_id,
            "customer_email_or_call",
            "timestamp",
            signal.timestamp,
            f"Customer {signal.channel} signal reviewed.",
            False,
        )
        for signal in (*evidence.gmail_signals, *evidence.call_signals)
    )
    receipts.extend(
        AdoptionRegressionSourceReceipt(
            note.note_id,
            "internal_note",
            "content",
            note.timestamp,
            f"Internal {note.source} note reviewed.",
            False,
        )
        for note in evidence.internal_notes
    )
    receipts.extend(
        AdoptionRegressionSourceReceipt(
            project.project_id,
            "onboarding_or_delivery",
            "progress",
            project.due_date or event.observed_at,
            f"Delivery project {project.name} is {project.progress}.",
            False,
        )
        for project in evidence.onboarding_projects
    )
    receipts.extend(
        AdoptionRegressionSourceReceipt(
            task.task_id,
            "onboarding_or_delivery",
            "status_label",
            task.due_date or event.observed_at,
            f"Delivery task {task.name} is {task.status_label}.",
            False,
        )
        for task in evidence.onboarding_tasks
    )
    return tuple(receipts)


def _metric_comparisons(
    event: ProductUsageRegressionEvent,
    usage_signals: tuple[UsageSignal, ...],
) -> tuple[MetricWindowComparison, ...]:
    metrics = sorted({signal.metric_name for signal in usage_signals} | {event.metric_name})
    comparisons = [
        _compare_metric(
            metric,
            usage_signals,
            baseline_start=event.baseline_start,
            baseline_end=event.baseline_end,
            current_start=event.current_start,
            current_end=event.current_end,
        )
        for metric in metrics
    ]
    comparisons.sort(key=lambda item: (item.metric_name != event.metric_name, -item.drop_ratio, item.metric_name))
    return tuple(comparisons)


def _compare_metric(
    metric_name: str,
    signals: tuple[UsageSignal, ...],
    *,
    baseline_start: str,
    baseline_end: str,
    current_start: str,
    current_end: str,
) -> MetricWindowComparison:
    baseline = [
        signal for signal in signals
        if signal.metric_name == metric_name and baseline_start <= signal.observed_at <= baseline_end
    ]
    current = [
        signal for signal in signals
        if signal.metric_name == metric_name and current_start <= signal.observed_at <= current_end
    ]
    baseline_value = _avg(signal.value for signal in baseline)
    current_value = _avg(signal.value for signal in current)
    absolute_change = None
    percent_change = None
    drop_ratio = 0.0
    if baseline_value is not None and current_value is not None:
        absolute_change = current_value - baseline_value
        if baseline_value > 0:
            percent_change = absolute_change / baseline_value
            drop_ratio = max(0.0, -percent_change)
    severity: RegressionSeverity = "none"
    if drop_ratio >= 0.50:
        severity = "severe"
    elif drop_ratio >= 0.25:
        severity = "material"
    elif drop_ratio >= 0.10:
        severity = "watch"
    return MetricWindowComparison(
        metric_name=metric_name,
        baseline_value=baseline_value,
        current_value=current_value,
        absolute_change=absolute_change,
        percent_change=percent_change,
        drop_ratio=round(drop_ratio, 4),
        severity=severity,
        baseline_source_ids=tuple(signal.signal_id for signal in baseline),
        current_source_ids=tuple(signal.signal_id for signal in current),
    )


def _build_value_model(
    account: CRMAccount,
    evidence: _AccountEvidence,
    *,
    as_of: str,
) -> CustomerValueModel | None:
    if evidence.company is None or evidence.health_score is None:
        return None
    return build_customer_value_model(
        account=account,
        company=evidence.company,
        health=evidence.health_score,
        adoption=evidence.adoption_summary,
        entitlements=evidence.entitlements,
        usage_signals=evidence.usage_signals,
        success_plans=evidence.success_plans,
        onboarding_milestones=evidence.ttv_milestones,
        stakeholders=evidence.stakeholders,
        job_changes=evidence.job_changes,
        communication_signals=(*evidence.gmail_signals, *evidence.call_signals),
        as_of=as_of,
    )


def _value_context(
    *,
    account: CRMAccount,
    evidence: _AccountEvidence,
    value_model: CustomerValueModel | None,
    receipts: tuple[AdoptionRegressionSourceReceipt, ...],
    as_of: str,
) -> ValueModelRegressionContext | None:
    if value_model is None or evidence.company is None:
        return None
    config = load_value_model_config()
    tier = resolve_tenant_tier(account_attributes(account, evidence.company), config)
    priority = project_ttv_lens(
        value_model,
        company=evidence.company,
        health=evidence.health_score,
        as_of=as_of,
    )
    adoption = evidence.adoption_summary
    source_ids = tuple(
        receipt.source_id for receipt in receipts
        if receipt.source_type in {"adoption_summary", "entitlement", "health_score", "cs_company", "product_telemetry"}
    )
    value_factors = tuple(factor.name for factor in (*priority.factors, *value_model.ttv_factors))
    return ValueModelRegressionContext(
        config_version=value_model.resolved_thresholds.config_version,
        rule_name=value_model.resolved_thresholds.rule_name,
        service_tier=tier.tier,
        lifecycle_stage=value_model.lifecycle_stage,
        adoption_rate=adoption.adoption_rate if adoption else None,
        seat_penetration=value_model.penetration.seat_penetration,
        active_users=adoption.active_users if adoption else None,
        licensed_users=adoption.licensed_users if adoption else None,
        active_assets=adoption.active_assets if adoption else None,
        entitled_assets=adoption.entitled_assets if adoption else None,
        underused_capabilities=value_model.feature_depth.underused_capabilities,
        priority_score=priority.score,
        value_factors=tuple(dict.fromkeys(value_factors)),
        source_ids=source_ids,
    )


def _contributing_context(
    evidence: _AccountEvidence,
    receipts: tuple[AdoptionRegressionSourceReceipt, ...],
) -> RegressionContributingContext:
    high_cases = [
        case for case in evidence.cases
        if str(case.status).lower() != "closed" and str(case.priority).lower() == "high"
    ]
    open_cases = [case for case in evidence.cases if str(case.status).lower() != "closed"]
    support_pressure = "high" if high_cases else "present" if open_cases else "none"
    overdue_or_open_plans = [plan for plan in evidence.success_plans if str(plan.status).lower() != "closed"]
    delivery_risk = "running_late" if any(getattr(project, "progress", "") == "running_late" for project in evidence.onboarding_projects) else "none"
    if any(getattr(task, "at_risk", False) for task in evidence.onboarding_tasks):
        delivery_risk = "task_at_risk"
    source_ids = tuple(
        receipt.source_id for receipt in receipts
        if receipt.source_type in {
            "support_pressure",
            "cs_platform_cta",
            "success_plan",
            "relationship_context",
            "customer_email_or_call",
            "internal_note",
            "onboarding_or_delivery",
        }
    )
    return RegressionContributingContext(
        support_pressure=support_pressure,
        open_high_priority_cases=len(high_cases),
        open_ctas=len(evidence.ctas),
        success_plan_risk="open_or_at_risk" if overdue_or_open_plans else "none",
        relationship_depth=len(evidence.contacts),
        customer_comms_recent=len(evidence.gmail_signals) + len(evidence.call_signals),
        internal_notes_recent=len(evidence.internal_notes),
        delivery_risk=delivery_risk,
        source_ids=source_ids,
    )


def _coverage(
    *,
    account: CRMAccount,
    evidence: _AccountEvidence,
    receipts: tuple[AdoptionRegressionSourceReceipt, ...],
    comparisons: tuple[MetricWindowComparison, ...],
    value_context: ValueModelRegressionContext | None,
) -> AdoptionRegressionCoverage:
    counts: dict[str, int] = {}
    for receipt in receipts:
        counts[receipt.source_type] = counts.get(receipt.source_type, 0) + 1
    normalized = list(counts)
    if evidence.account is not None:
        normalized.append("account_identity")
    if any(item.baseline_source_ids for item in comparisons):
        normalized.append("baseline_usage_window")
    if any(item.current_source_ids for item in comparisons):
        normalized.append("current_usage_window")
    if value_context is not None:
        normalized.append("value_model_alignment")
    shared = evaluate_source_coverage(
        ACCOUNT_ADOPTION_REGRESSION,
        reviewed_sources=tuple(dict.fromkeys(normalized)),
    )
    missing = list(shared.missing_required_sources)
    blockers = list(shared.customer_output_blockers)
    if evidence.account is None:
        blockers.append("account_identity_not_found")
    if not evidence.usage_signals:
        blockers.append("product_telemetry_required_for_regression_judgment")
    if not any(item.baseline_source_ids for item in comparisons):
        blockers.append("baseline_usage_window_missing")
    if not any(item.current_source_ids for item in comparisons):
        blockers.append("current_usage_window_missing")
    if value_context is None:
        blockers.append("value_model_alignment_missing")
    if not _preferred_contact(evidence.contacts):
        blockers.append("no_consented_contact_for_customer_outreach")
    return AdoptionRegressionCoverage(
        reviewed_sources=tuple(sorted(counts)),
        missing_required_sources=tuple(dict.fromkeys(missing)),
        customer_output_blockers=tuple(dict.fromkeys(blockers)),
        source_counts=counts,
    )


def _interpret(
    comparisons: tuple[MetricWindowComparison, ...],
    value_context: ValueModelRegressionContext | None,
    context: RegressionContributingContext,
    coverage: AdoptionRegressionCoverage,
) -> AdoptionRegressionInterpretation:
    top = _top_regression(comparisons)
    source_ids = list(top.baseline_source_ids + top.current_source_ids)
    source_ids.extend(value_context.source_ids if value_context else ())
    source_ids.extend(context.source_ids)
    rationale: list[str] = []
    alternatives: list[str] = [
        "telemetry_noise_or_seasonality",
        "planned_rollout_pause",
        "usage_shifted_to_uninstrumented_workflow",
    ]
    hypothesis = "insufficient_evidence"
    if coverage.customer_output_blockers:
        rationale.append("Required evidence is missing or not customer-safe.")
    if top.drop_ratio > 0:
        rationale.append(
            f"{top.metric_name} changed from {top.baseline_value:g} to {top.current_value:g}."
            if top.baseline_value is not None and top.current_value is not None
            else f"{top.metric_name} has incomplete comparison data."
        )
    if context.support_pressure == "high":
        hypothesis = "usage_regression_with_support_friction"
        rationale.append("Open high-priority support pressure can plausibly explain the drop.")
    elif value_context and value_context.underused_capabilities:
        hypothesis = "feature_depth_or_entitlement_regression"
        rationale.append("Entitled capabilities remain underused, so regression threatens depth of value.")
    elif context.relationship_depth <= 1:
        hypothesis = "relationship_coverage_risk"
        rationale.append("Relationship coverage is thin for diagnosing account behavior.")
    elif top.drop_ratio >= 0.25:
        hypothesis = "material_usage_regression"
        rationale.append("The usage drop is material even without a single confirmed cause.")
    elif top.drop_ratio > 0:
        hypothesis = "watch_level_usage_shift"
        rationale.append("The usage shift is visible but below material severity.")
    confidence = _confidence(top, value_context, context, coverage)
    open_questions = []
    if "customer_email_or_call" not in coverage.reviewed_sources:
        open_questions.append("No recent customer email/call context explains whether this was expected.")
    if context.support_pressure != "high":
        open_questions.append("No high-priority support case fully explains the usage change.")
    if value_context is None:
        open_questions.append("Value-model context is unavailable.")
    return AdoptionRegressionInterpretation(
        selected_hypothesis=hypothesis,
        confidence=confidence,
        severity=top.severity,
        rationale=tuple(dict.fromkeys(rationale)),
        alternatives=tuple(dict.fromkeys(alternatives)),
        source_ids=tuple(dict.fromkeys(source_ids)) or (),
        open_questions=tuple(dict.fromkeys(open_questions)),
    )


def _recommended_action(
    *,
    account: CRMAccount,
    evidence: _AccountEvidence,
    interpretation: AdoptionRegressionInterpretation,
    coverage: AdoptionRegressionCoverage,
) -> AdoptionRegressionRecommendedAction:
    source_ids = interpretation.source_ids
    suppression: list[str] = []
    if interpretation.severity == "none" and not coverage.customer_output_blockers:
        return AdoptionRegressionRecommendedAction(
            action_type="suppress_regression_motion",
            trigger="no_regression_observed",
            label=f"No adoption regression motion for {account.name}",
            customer_safe_message=None,
            source_ids=source_ids,
            suppressed=True,
            suppression_reasons=("no_regression_observed",),
        )
    if coverage.customer_output_blockers:
        suppression.extend(coverage.customer_output_blockers)
    if interpretation.confidence < 0.65:
        suppression.append("low_confidence_or_ambiguous_cause")
    if interpretation.severity in {"none", "watch"}:
        suppression.append("regression_below_customer_motion_threshold")
    contact = _preferred_contact(evidence.contacts)
    if contact is None:
        suppression.append("no_consented_contact")
    if suppression:
        return AdoptionRegressionRecommendedAction(
            action_type="recommend_internal_review",
            trigger="regression_detected_but_customer_output_unsafe",
            label=f"Review adoption regression for {account.name}",
            customer_safe_message=None,
            source_ids=source_ids,
            suppressed=True,
            suppression_reasons=tuple(dict.fromkeys(suppression)),
        )
    return AdoptionRegressionRecommendedAction(
        action_type="draft_regression_review_outreach",
        trigger="source_backed_regression_with_safe_contact",
        label=f"Ask {account.name} about observed adoption shift",
        customer_safe_message=(
            "A source-backed usage shift is visible. Ask for context, confirm "
            "whether the change was expected, and tie the review to the customer's value path."
        ),
        source_ids=source_ids,
        suppressed=False,
        suppression_reasons=(),
    )


def _customer_language(
    account: CRMAccount,
    action: AdoptionRegressionRecommendedAction,
    interpretation: AdoptionRegressionInterpretation,
) -> str | None:
    if action.suppressed:
        return None
    return (
        f"Hi, I noticed a shift in {account.name}'s product usage that may affect "
        "the outcomes we are tracking together. Could we review whether this was "
        "expected, whether anything is blocked, and what should change in the "
        "success plan? I will bring the specific usage receipts so we can keep it concrete."
    )


def _packet_status(
    coverage: AdoptionRegressionCoverage,
    interpretation: AdoptionRegressionInterpretation,
    action: AdoptionRegressionRecommendedAction,
) -> PacketStatus:
    if "account_identity" in coverage.missing_required_sources:
        return "needs_data"
    if coverage.missing_required_sources:
        return "needs_data"
    if interpretation.severity == "none":
        return "ignored"
    if action.suppressed:
        return "internal_only"
    return "ready"


def _risks(
    coverage: AdoptionRegressionCoverage,
    interpretation: AdoptionRegressionInterpretation,
    action: AdoptionRegressionRecommendedAction,
) -> tuple[str, ...]:
    risks = list(coverage.customer_output_blockers)
    risks.extend(action.suppression_reasons)
    if interpretation.confidence < 0.65:
        risks.append("interpretation confidence below customer-motion threshold")
    risks.extend(interpretation.open_questions)
    return tuple(dict.fromkeys(risks))


def _proposals(
    *,
    gate: ActionGate | None,
    event: ProductUsageRegressionEvent,
    account: CRMAccount,
    evidence: _AccountEvidence,
    action: AdoptionRegressionRecommendedAction,
    customer_language: str | None,
    receipts: tuple[AdoptionRegressionSourceReceipt, ...],
    status: PacketStatus,
) -> tuple[AdoptionRegressionProposalRef, ...]:
    if gate is None:
        return ()
    evidence_ids = [receipt.source_id for receipt in receipts]
    contact = _preferred_contact(evidence.contacts)
    if status == "ready" and customer_language and contact is not None:
        gate.record_outreach_contact_ref(
            account_ref=account.account_id,
            contact_ref=contact.contact_id,
            email=contact.email,
            name=contact.name,
            consent=contact.consent_to_contact,
            cause_ref=f"adoption-regression:{event.account_id}:contact-consent",
        )
        proposal = gate.propose(
            intent="account_adoption_regression",
            payload={
                "account_id": account.account_id,
                "account_name": account.name,
                "contact_id": contact.contact_id,
                "contact_email": contact.email,
                "metric_name": event.metric_name,
                "trigger": action.trigger,
                "draft_channel": "email",
                "subject": f"{account.name} adoption review",
                "body": customer_language,
                "evidence_ids": evidence_ids,
            },
            grounding_ref=f"adoption-regression:{event.account_id}",
            cause_ref=f"adoption-regression:{event.account_id}:{event.observed_at}",
            **proposal_fields_for("draft_customer_outreach"),
        )
        return (_proposal_ref(proposal),)
    proposal = gate.propose(
        intent="account_adoption_regression",
        payload={
            "account_id": account.account_id,
            "account_name": account.name,
            "metric_name": event.metric_name,
            "recommended_action": action.to_dict(),
            "evidence_ids": evidence_ids,
        },
        grounding_ref=f"adoption-regression:{event.account_id}",
        cause_ref=f"adoption-regression:{event.account_id}:{event.observed_at}",
        **proposal_fields_for("recommend_next_best_action"),
    )
    return (_proposal_ref(proposal),)


def _execution_envelope(
    *,
    event: ProductUsageRegressionEvent,
    coverage: AdoptionRegressionCoverage,
    comparisons: tuple[MetricWindowComparison, ...],
    value_context: ValueModelRegressionContext | None,
    context: RegressionContributingContext,
    interpretation: AdoptionRegressionInterpretation,
    action: AdoptionRegressionRecommendedAction,
    receipts: tuple[AdoptionRegressionSourceReceipt, ...],
    proposals: tuple[AdoptionRegressionProposalRef, ...],
    status: PacketStatus,
) -> WorkflowExecutionEnvelope:
    evidence = build_evidence_bundle(
        receipts=receipts,
        reviewed_sources=coverage.reviewed_sources,
        missing_required_sources=coverage.missing_required_sources,
        customer_output_blockers=coverage.customer_output_blockers,
    )
    evidence_ids = set(evidence.evidence_ids())
    decision_source_ids = tuple(source_id for source_id in interpretation.source_ids if source_id in evidence_ids)
    validations = (
        WorkflowValidationResult(
            "account_identity_exact",
            "account_identity" not in coverage.missing_required_sources,
            True,
            "Account identity is exact." if "account_identity" not in coverage.missing_required_sources else "Account identity is missing.",
            tuple(receipt.source_id for receipt in receipts if receipt.source_type == "account_identity"),
        ),
        WorkflowValidationResult(
            "baseline_and_current_windows_present",
            any(item.baseline_source_ids for item in comparisons) and any(item.current_source_ids for item in comparisons),
            True,
            "Baseline and current windows both contain usage evidence.",
            tuple(source_id for item in comparisons for source_id in (*item.baseline_source_ids, *item.current_source_ids)),
        ),
        WorkflowValidationResult(
            "regression_magnitude_measured",
            any(item.baseline_value is not None and item.current_value is not None for item in comparisons),
            True,
            "Regression magnitude has numeric baseline/current comparison.",
            tuple(source_id for item in comparisons for source_id in (*item.baseline_source_ids, *item.current_source_ids)),
        ),
        WorkflowValidationResult(
            "value_model_alignment_present",
            value_context is not None,
            True,
            "Value model context is present." if value_context else "Value model context is missing.",
            value_context.source_ids if value_context else (),
        ),
        WorkflowValidationResult(
            "alternatives_preserved",
            bool(interpretation.alternatives),
            False,
            "Alternate explanations remain visible.",
            decision_source_ids,
        ),
    )
    outputs: list[WorkflowOutputContract] = []
    if proposals:
        for proposal in proposals:
            customer_affecting = proposal.action_type == "draft_customer_outreach"
            outputs.append(WorkflowOutputContract(
                artifact_type="adoption_regression_recommendation",
                audience="customer_facing" if customer_affecting else "csm_facing",
                action_type=proposal.action_type,
                customer_affecting=customer_affecting,
                gate_action=proposal.action_type if customer_affecting else None,
                status="proposed",
                source_ids=tuple(source_id for source_id in action.source_ids if source_id in evidence_ids) or (receipts[0].source_id,),
                suppression_reasons=action.suppression_reasons,
                proposal_id=proposal.proposal_id,
            ))
    else:
        outputs.append(WorkflowOutputContract(
            artifact_type="adoption_regression_recommendation",
            audience="csm_facing",
            action_type=action.action_type,
            customer_affecting=False,
            gate_action=None,
            status="prepared" if status in {"ready", "internal_only"} else "suppressed",
            source_ids=tuple(source_id for source_id in action.source_ids if source_id in evidence_ids) or (receipts[0].source_id,),
            suppression_reasons=action.suppression_reasons,
        ))
    top = _top_regression(comparisons)
    return build_execution_envelope(
        ACCOUNT_ADOPTION_REGRESSION,
        trigger_ref=receipts[0].source_id,
        idempotency_key=(
            f"account_adoption_regression:{event.account_id}:"
            f"{event.metric_name}:{event.current_end}:{event.observed_at}"
        ),
        identity_state="exactly_one" if "account_identity" not in coverage.missing_required_sources else "none",
        evidence=evidence,
        decisions=(
            WorkflowDecisionTrace(
                decision_kind="account_adoption_regression",
                selected_hypothesis=interpretation.selected_hypothesis,
                alternatives=interpretation.alternatives,
                confidence=interpretation.confidence,
                confidence_model=(
                    "Compare current usage window against prior baseline by metric.",
                    "Increase confidence with value-model alignment and independent context.",
                    "Suppress customer output when required evidence or consent is missing.",
                ),
                source_ids=decision_source_ids or (receipts[0].source_id,),
                limitations=interpretation.open_questions,
                domain_payload={
                    "status": status,
                    "metric_name": top.metric_name,
                    "severity": interpretation.severity,
                    "drop_ratio": top.drop_ratio,
                    "support_pressure": context.support_pressure,
                    "recommended_action": action.action_type,
                },
            ),
        ),
        validations=validations,
        outputs=tuple(outputs),
    )


def _proposal_ref(proposal: ActionProposal) -> AdoptionRegressionProposalRef:
    return AdoptionRegressionProposalRef(
        proposal_id=proposal.proposal_id,
        action_type=proposal.action,
        status=proposal.status,
        autonomy_tier=proposal.autonomy_tier,
        required_permission=proposal.required_permission,
    )


def _preferred_contact(contacts: tuple[CRMContact, ...]) -> CRMContact | None:
    consented = [contact for contact in contacts if contact.consent_to_contact]
    return sorted(consented, key=lambda contact: (contact.org_level or 99, contact.email))[0] if consented else None


def _top_regression(comparisons: tuple[MetricWindowComparison, ...]) -> MetricWindowComparison:
    if not comparisons:
        return MetricWindowComparison(
            metric_name="unknown",
            baseline_value=None,
            current_value=None,
            absolute_change=None,
            percent_change=None,
            drop_ratio=0.0,
            severity="none",
            baseline_source_ids=(),
            current_source_ids=(),
        )
    return max(comparisons, key=lambda item: (item.drop_ratio, item.metric_name))


def _confidence(
    top: MetricWindowComparison,
    value_context: ValueModelRegressionContext | None,
    context: RegressionContributingContext,
    coverage: AdoptionRegressionCoverage,
) -> float:
    if coverage.missing_required_sources:
        return 0.25
    score = 0.35
    score += min(0.25, top.drop_ratio * 0.5)
    if value_context is not None:
        score += 0.15
    if context.support_pressure != "none":
        score += 0.10
    if context.customer_comms_recent or context.internal_notes_recent:
        score += 0.08
    if context.delivery_risk != "none":
        score += 0.05
    return round(min(score, 0.92), 2)


def _avg(values: Any) -> float | None:
    seq = list(values)
    if not seq:
        return None
    return sum(float(value) for value in seq) / len(seq)


def _compact_timestamp(value: str) -> str:
    return (
        value.replace(":", "")
        .replace("-", "")
        .replace(".", "")
        .replace("Z", "z")
    )


def _days_between(start: str, end: str) -> int:
    try:
        return (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days
    except ValueError:
        return 0
