"""Enterprise closed-won onboarding launch workflow.

The entrypoint in this module is event-driven from a Salesforce-shaped
Opportunity update, but it never trusts the event payload alone. It re-reads the
opportunity and account through the configured CustomerDataPlane, gathers the
available connected sources, applies coverage gates, and only then proposes
customer-affecting artifacts through ActionGate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Protocol

from ultra_csm._util import iso_date
from ultra_csm.data_plane import onboarding_activation_gap_ids
from ultra_csm.data_plane.contracts import (
    AdoptionSummary,
    CommunicationSignal,
    CRMAccount,
    CRMContact,
    CRMDataConnector,
    CRMOpportunity,
    CSCompany,
    CustomerDataPlane,
    Entitlement,
    EvidenceRef,
    HealthScore,
    OnboardingPhase,
    OnboardingProject,
    OnboardingTask,
    StakeholderRelationship,
    SuccessPlan,
    TimeToValueMilestone,
    UsageSignal,
)
from ultra_csm.governance import ActionGate, ActionProposal, proposal_fields_for
from ultra_csm.value_model import (
    CustomerValueModel,
    ProjectedPriority,
    ValueFactor,
    account_attributes,
    build_customer_value_model,
    load_value_model_config,
    project_ttv_lens,
    resolve_tenant_tier,
)


ENTERPRISE_AMOUNT_CENTS = 10_000_000
ENTERPRISE_SUCCESS_PLAN_CONFIG_VERSION = "enterprise-success-plan-config-v2"

LaunchStatus = Literal["ready", "needs_data", "ignored"]
SourceAuthority = Literal[
    "customer_direct",
    "customer_observed",
    "commercial_record",
    "internal_structured",
    "internal_unstructured",
    "inferred",
]
AccountDomainResolutionState = Literal["exactly_one", "ambiguous", "none"]
IntegrationStatus = Literal["configured", "observed", "missing", "unknown"]

_PERSONAL_EMAIL_DOMAINS = frozenset({
    "aol.com",
    "gmail.com",
    "googlemail.com",
    "hotmail.com",
    "icloud.com",
    "live.com",
    "me.com",
    "msn.com",
    "outlook.com",
    "proton.me",
    "protonmail.com",
    "yahoo.com",
})

_CALL_INTEGRATION_OPTIONS = (
    "gong",
    "salesloft",
    "clari_copilot",
    "avoma",
    "chorus",
    "fathom",
    "granola",
    "attention",
    "fireflies",
    "grain",
)
_SEQUENCE_INTEGRATION_OPTIONS = ("outreach", "gong_engage")


@dataclass(frozen=True)
class SalesforceClosedWonEvent:
    tenant_id: str
    opportunity_id: str
    account_id: str
    stage_name: str
    observed_at: str
    source: str = "salesforce"


class GoogleCalendarEventsProvider(Protocol):
    """Google Calendar events.list provider for account/opportunity context."""

    def list_events(
        self,
        account_id: str,
        *,
        opportunity_id: str | None = None,
        until: str | None = None,
    ) -> dict: ...


@dataclass(frozen=True)
class CalendarAttendance:
    event_id: str
    summary: str
    attendee_email: str
    response_status: str
    start_at: str
    status: str


@dataclass(frozen=True)
class CalendarAccountDomainResolution:
    state: AccountDomainResolutionState
    account_id: str | None
    account_name: str | None
    matched_domains: tuple[str, ...]
    attendee_emails: tuple[str, ...]
    candidate_account_ids: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceReceipt:
    source_id: str
    source_type: str
    field: str
    authority: SourceAuthority
    observed_at: str
    claim: str
    customer_safe: bool


@dataclass(frozen=True)
class SourceCoverage:
    original_success_plan_sources: tuple[str, ...]
    current_state_sources: tuple[str, ...]
    stakeholder_verification_sources: tuple[str, ...]
    missing_required_sources: tuple[str, ...]


@dataclass(frozen=True)
class StakeholderVerification:
    person_key: str
    crm_contact_id: str | None
    crm_role: str | None
    relationship_role: str | None
    observed_sources: tuple[str, ...]
    appearances: int
    confidence: float
    verification_state: Literal[
        "declared_and_observed",
        "declared_not_observed",
        "observed_missing_from_crm",
    ]


@dataclass(frozen=True)
class MilestoneMeasurement:
    metric_name: str
    current_value: float | None
    target_value: float | None
    threshold_name: str | None
    threshold_value: float | int | None
    evidence_source_ids: tuple[str, ...]
    rail: str


@dataclass(frozen=True)
class OnboardingMilestone:
    milestone: str
    owner: str
    target_date: str
    acceptance_criteria: str
    source_ids: tuple[str, ...]
    measurement: MilestoneMeasurement | None = None


@dataclass(frozen=True)
class SuccessPlanValueFactor:
    name: str
    value: float
    contribution: int
    threshold_name: str | None
    threshold_value: float | int | None
    evidence_source_ids: tuple[str, ...]


@dataclass(frozen=True)
class SuccessPlanValueRail:
    rail: str
    state: str
    current_value: float | None
    target_value: float | None
    threshold_name: str | None
    threshold_value: float | int | None
    factors: tuple[SuccessPlanValueFactor, ...]
    evidence_source_ids: tuple[str, ...]
    interpretation: str


@dataclass(frozen=True)
class SuccessPlanValueModelAlignment:
    account_id: str
    lifecycle_stage: str
    service_tier: str | None
    config_version: str
    rule_name: str
    thresholds: dict[str, float | int]
    rails: tuple[SuccessPlanValueRail, ...]
    ttv_priority_score: int
    ttv_factors: tuple[SuccessPlanValueFactor, ...]
    plan_target_formula: tuple[str, ...]


@dataclass(frozen=True)
class SuccessPlanInputEvidence:
    input_name: str
    source_ids: tuple[str, ...]
    customer_safe: bool
    summary: str


@dataclass(frozen=True)
class SuccessPlanOutcomeHypothesis:
    outcome: str
    confidence: float
    evidence_source_ids: tuple[str, ...]
    unresolved_questions: tuple[str, ...]


@dataclass(frozen=True)
class SuccessPlanFirstValueHypothesis:
    capability: str
    selection_state: Literal["selected", "alternative"]
    confidence: float
    evidence_source_ids: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class SuccessPlanValidationCheck:
    check_name: str
    passed: bool
    evidence_source_ids: tuple[str, ...]
    detail: str


@dataclass(frozen=True)
class SuccessPlanMethodology:
    method_version: str
    method_config_version: str
    lifecycle_stage: str
    construction_steps: tuple[str, ...]
    input_evidence: tuple[SuccessPlanInputEvidence, ...]
    outcome_hypotheses: tuple[SuccessPlanOutcomeHypothesis, ...]
    first_value_hypotheses: tuple[SuccessPlanFirstValueHypothesis, ...]
    confidence_model: tuple[str, ...]
    milestone_rationale: tuple[str, ...]
    validation_checks: tuple[SuccessPlanValidationCheck, ...]
    customer_fit_summary: str
    open_questions: tuple[str, ...]
    value_model_alignment: SuccessPlanValueModelAlignment | None = None


@dataclass(frozen=True)
class CustomerIntegrationFootprint:
    family: Literal[
        "mcp",
        "chrome_extension",
        "crm",
        "messaging",
        "email",
        "calendar",
        "calls",
        "sequences",
    ]
    label: str
    status: IntegrationStatus
    provider: str | None
    provider_options: tuple[str, ...]
    evidence_source_ids: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class LaunchProposalRef:
    proposal_id: str
    action_type: str
    status: str


@dataclass(frozen=True)
class EnterpriseOnboardingLaunchPacket:
    packet_id: str
    tenant_id: str
    status: LaunchStatus
    account_id: str
    account_name: str
    opportunity_id: str
    generated_at: str
    trigger_receipt: SourceReceipt
    coverage: SourceCoverage
    customer_safe_baseline: tuple[str, ...]
    internal_context: tuple[str, ...]
    customer_integrations: tuple[CustomerIntegrationFootprint, ...]
    stakeholder_verification: tuple[StakeholderVerification, ...]
    success_plan_methodology: SuccessPlanMethodology | None
    success_plan_v0: tuple[OnboardingMilestone, ...]
    risks: tuple[str, ...]
    recommended_next_action: str
    kickoff_agenda: tuple[str, ...]
    customer_welcome_draft: str | None
    source_receipts: tuple[SourceReceipt, ...]
    proposals: tuple[LaunchProposalRef, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_enterprise_closed_won_onboarding(
    *,
    data_plane: CustomerDataPlane,
    gate: ActionGate | None,
    event: SalesforceClosedWonEvent,
    as_of: str,
    calendar_provider: GoogleCalendarEventsProvider | None = None,
) -> EnterpriseOnboardingLaunchPacket:
    """Run the enterprise closed-won onboarding workflow.

    ``gate`` may be ``None`` for dry-run evaluation. When supplied, customer
    outreach and success-plan creation/update are proposed, never executed.
    """

    account = data_plane.crm.get_account(event.account_id)
    opportunity = _opportunity_for_event(data_plane, event)
    if account is None or opportunity is None:
        return _ignored_packet(
            event=event,
            as_of=as_of,
            account=account,
            reason="Closed-won event did not resolve to exactly one Salesforce account and opportunity.",
        )

    trigger = _trigger_receipt(event, opportunity)
    company = data_plane.cs.get_company(account.account_id)
    enterprise = _is_enterprise(opportunity, company_arr_cents=getattr(company, "arr_cents", None))
    if _normalize_stage(opportunity.stage_name) != "closed won" or _normalize_stage(event.stage_name) != "closed won":
        return _ignored_packet(event=event, as_of=as_of, account=account, reason="Opportunity is not Closed Won.")
    if not enterprise:
        return _ignored_packet(event=event, as_of=as_of, account=account, reason="Opportunity is not enterprise-sized.")

    contacts = tuple(data_plane.crm.list_contacts(account.account_id))
    stakeholders = _list_stakeholders(data_plane, account.account_id)
    success_plans = tuple(data_plane.cs.list_success_plans(account.account_id))
    entitlements = tuple(data_plane.telemetry.list_entitlements(account.account_id))
    usage_signals = tuple(data_plane.telemetry.list_usage_signals(account.account_id))
    ttv_milestones = _ttv_milestones(data_plane, account.account_id)
    ctas = tuple(data_plane.cs.list_ctas(account.account_id, status="open"))
    health = data_plane.cs.get_health_score(account.account_id)
    adoption = data_plane.cs.get_adoption_summary(account.account_id)
    onboarding_projects, onboarding_phases, onboarding_tasks = _onboarding_evidence(data_plane, account.account_id)
    customer_comms, call_or_meeting_comms, internal_notes = _comms_evidence(data_plane, account.account_id)
    calendar_attendance = _calendar_attendance(
        calendar_provider,
        account.account_id,
        opportunity_id=opportunity.opportunity_id,
        until=as_of,
    )

    coverage = _source_coverage(
        account=account,
        opportunity=opportunity,
        contacts=contacts,
        entitlements=entitlements,
        success_plans=success_plans,
        onboarding_projects=onboarding_projects,
        onboarding_phases=onboarding_phases,
        onboarding_tasks=onboarding_tasks,
        customer_comms=customer_comms,
        call_or_meeting_comms=call_or_meeting_comms,
        calendar_attendance=calendar_attendance,
        internal_notes=internal_notes,
        usage_signals=usage_signals,
        ttv_milestones=ttv_milestones,
        stakeholders=stakeholders,
        company=company,
        health=health,
        adoption=adoption,
    )
    receipts = _source_receipts(
        trigger=trigger,
        account=account,
        opportunity=opportunity,
        contacts=contacts,
        entitlements=entitlements,
        success_plans=success_plans,
        customer_comms=customer_comms,
        call_or_meeting_comms=call_or_meeting_comms,
        calendar_attendance=calendar_attendance,
        internal_notes=internal_notes,
        onboarding_projects=onboarding_projects,
        onboarding_phases=onboarding_phases,
        onboarding_tasks=onboarding_tasks,
        ttv_milestones=ttv_milestones,
    )
    stakeholder_rows = _stakeholder_verification(
        contacts=contacts,
        stakeholders=stakeholders,
        customer_comms=customer_comms,
        call_or_meeting_comms=call_or_meeting_comms,
        calendar_attendance=calendar_attendance,
    )
    risks = _risks(
        coverage=coverage,
        stakeholder_rows=stakeholder_rows,
        entitlements=entitlements,
        usage_signals=usage_signals,
        health=health,
    )
    customer_integrations = _customer_integrations(
        opportunity=opportunity,
        entitlements=entitlements,
        usage_signals=usage_signals,
        customer_comms=customer_comms,
        call_or_meeting_comms=call_or_meeting_comms,
        calendar_attendance=calendar_attendance,
        internal_notes=internal_notes,
    )
    coverage_ready = not coverage.missing_required_sources
    success_plan, success_plan_methodology = _build_success_plan(
        as_of=as_of,
        account=account,
        opportunity=opportunity,
        contacts=contacts,
        stakeholder_rows=stakeholder_rows,
        entitlements=entitlements,
        usage_signals=usage_signals,
        customer_comms=customer_comms,
        call_or_meeting_comms=call_or_meeting_comms,
        calendar_attendance=calendar_attendance,
        internal_notes=internal_notes,
        onboarding_projects=onboarding_projects,
        onboarding_phases=onboarding_phases,
        onboarding_tasks=onboarding_tasks,
        success_plans=success_plans,
        company=company,
        health=health,
        adoption=adoption,
        stakeholders=stakeholders,
        ttv_milestones=ttv_milestones,
    ) if coverage_ready else ((), None)
    validation_failures = _failed_success_plan_checks(success_plan_methodology)
    ready = coverage_ready and not validation_failures
    customer_baseline = _customer_safe_baseline(
        account=account,
        opportunity=opportunity,
        entitlements=entitlements,
        customer_comms=customer_comms,
        call_or_meeting_comms=call_or_meeting_comms,
        calendar_attendance=calendar_attendance,
    ) if ready else ()
    internal_context = _internal_context(
        internal_notes=internal_notes,
        ctas=ctas,
        health=health,
        adoption=adoption,
        stakeholder_rows=stakeholder_rows,
    )
    kickoff_agenda = _kickoff_agenda(success_plan) if ready else ()
    selected_contact = _selected_kickoff_contact(contacts, stakeholder_rows)
    draft = (
        _welcome_draft(account=account, contact=selected_contact, kickoff_agenda=kickoff_agenda)
        if ready and selected_contact is not None
        else None
    )
    proposals = _propose_launch_actions(
        gate=gate,
        event=event,
        account=account,
        opportunity=opportunity,
        contact=selected_contact,
        draft=draft,
        success_plan=success_plan,
        receipts=receipts,
    ) if ready else ()

    return EnterpriseOnboardingLaunchPacket(
        packet_id=f"enterprise-onboarding:{opportunity.opportunity_id}:{as_of}",
        tenant_id=event.tenant_id,
        status="ready" if ready else "needs_data",
        account_id=account.account_id,
        account_name=account.name,
        opportunity_id=opportunity.opportunity_id,
        generated_at=as_of,
        trigger_receipt=trigger,
        coverage=coverage,
        customer_safe_baseline=customer_baseline,
        internal_context=internal_context,
        customer_integrations=customer_integrations,
        stakeholder_verification=stakeholder_rows,
        success_plan_methodology=success_plan_methodology,
        success_plan_v0=success_plan,
        risks=tuple(dict.fromkeys((*risks, *validation_failures))),
        recommended_next_action=(
            "Review and approve the kickoff draft plus success-plan v0."
            if ready
            else (
                "Resolve failed success-plan validation checks before customer-facing activity."
                if coverage_ready and validation_failures
                else "Complete missing onboarding evidence before customer-facing activity."
            )
        ),
        kickoff_agenda=kickoff_agenda,
        customer_welcome_draft=draft,
        source_receipts=receipts,
        proposals=proposals,
    )


def _opportunity_for_event(
    data_plane: CustomerDataPlane,
    event: SalesforceClosedWonEvent,
) -> CRMOpportunity | None:
    for opportunity in data_plane.crm.list_opportunities(event.account_id):
        if opportunity.opportunity_id == event.opportunity_id:
            return opportunity
    return None


def _trigger_receipt(event: SalesforceClosedWonEvent, opportunity: CRMOpportunity) -> SourceReceipt:
    return SourceReceipt(
        source_id=opportunity.opportunity_id,
        source_type="salesforce_opportunity",
        field="stage_name",
        authority="commercial_record",
        observed_at=event.observed_at,
        claim=f"Opportunity {opportunity.opportunity_id} is {opportunity.stage_name}.",
        customer_safe=False,
    )


def _is_enterprise(opportunity: CRMOpportunity, *, company_arr_cents: int | None) -> bool:
    return opportunity.amount_cents >= ENTERPRISE_AMOUNT_CENTS or (
        company_arr_cents is not None and company_arr_cents >= ENTERPRISE_AMOUNT_CENTS
    )


def _source_coverage(
    *,
    account: CRMAccount,
    opportunity: CRMOpportunity,
    contacts: tuple[CRMContact, ...],
    entitlements: tuple[Entitlement, ...],
    success_plans: tuple[SuccessPlan, ...],
    onboarding_projects: tuple[OnboardingProject, ...],
    onboarding_phases: tuple[OnboardingPhase, ...],
    onboarding_tasks: tuple[OnboardingTask, ...],
    customer_comms: tuple[CommunicationSignal, ...],
    call_or_meeting_comms: tuple[CommunicationSignal, ...],
    calendar_attendance: tuple[CalendarAttendance, ...],
    internal_notes: tuple,
    usage_signals: tuple[UsageSignal, ...],
    ttv_milestones: tuple[TimeToValueMilestone, ...],
    stakeholders: tuple[StakeholderRelationship, ...],
    company: CSCompany | None,
    health: HealthScore | None,
    adoption: AdoptionSummary | None,
) -> SourceCoverage:
    baseline = ["salesforce_opportunity", "salesforce_account"]
    if contacts:
        baseline.append("salesforce_contacts")
    if company is not None:
        baseline.append("cs_company")
    if health is not None:
        baseline.append("health_score")
    if adoption is not None:
        baseline.append("adoption_summary")
    if entitlements:
        baseline.append("entitlements")
    if success_plans:
        baseline.append("existing_success_plan")
    if onboarding_projects or onboarding_phases or onboarding_tasks:
        baseline.append("onboarding_source")
    if customer_comms:
        baseline.append("customer_email")
    if call_or_meeting_comms:
        baseline.append("call_or_meeting_context")
    if calendar_attendance:
        baseline.append("google_calendar")
    if internal_notes:
        baseline.append("internal_handoff_notes")

    current = []
    if entitlements:
        current.append("provisioning_entitlements")
    if usage_signals:
        current.append("product_usage")
    if adoption is not None:
        current.append("adoption_summary")
    if health is not None:
        current.append("health_score")
    if ttv_milestones:
        current.append("time_to_value_milestones")
    if onboarding_projects or onboarding_tasks:
        current.append("onboarding_project_state")

    stakeholder_sources = []
    if contacts:
        stakeholder_sources.append("salesforce_contacts")
    if stakeholders:
        stakeholder_sources.append("relationship_graph")
    if customer_comms:
        stakeholder_sources.append("customer_email")
    if call_or_meeting_comms:
        stakeholder_sources.append("calendar_or_call_attendance")
    if calendar_attendance:
        stakeholder_sources.append("google_calendar_attendance")

    missing = []
    if account is None:
        missing.append("salesforce_account")
    if opportunity is None:
        missing.append("salesforce_opportunity")
    if not contacts:
        missing.append("salesforce_contacts")
    if not entitlements:
        missing.append("entitlements_or_order_line_items")
    if company is None:
        missing.append("cs_company_value_model_context")
    if health is None:
        missing.append("health_score_value_model_context")
    if adoption is None:
        missing.append("adoption_summary_value_model_context")
    if not (customer_comms or call_or_meeting_comms or calendar_attendance or internal_notes):
        missing.append("sales_or_customer_context")
    if not (customer_comms or call_or_meeting_comms or calendar_attendance):
        missing.append("customer_facing_email_call_or_calendar_context")
    if not usage_signals:
        missing.append("product_tenant_or_provisioning_state")
    return SourceCoverage(
        original_success_plan_sources=tuple(baseline),
        current_state_sources=tuple(current),
        stakeholder_verification_sources=tuple(stakeholder_sources),
        missing_required_sources=tuple(missing),
    )


def _source_receipts(
    *,
    trigger: SourceReceipt,
    account: CRMAccount,
    opportunity: CRMOpportunity,
    contacts: tuple[CRMContact, ...],
    entitlements: tuple[Entitlement, ...],
    success_plans: tuple[SuccessPlan, ...],
    customer_comms: tuple[CommunicationSignal, ...],
    call_or_meeting_comms: tuple[CommunicationSignal, ...],
    calendar_attendance: tuple[CalendarAttendance, ...],
    internal_notes: tuple,
    onboarding_projects: tuple[OnboardingProject, ...],
    onboarding_phases: tuple[OnboardingPhase, ...],
    onboarding_tasks: tuple[OnboardingTask, ...],
    ttv_milestones: tuple[TimeToValueMilestone, ...],
) -> tuple[SourceReceipt, ...]:
    receipts = [trigger]
    receipts.append(SourceReceipt(
        source_id=account.account_id,
        source_type="salesforce_account",
        field="name",
        authority="commercial_record",
        observed_at=opportunity.close_date,
        claim=f"Salesforce account is {account.name}.",
        customer_safe=True,
    ))
    for contact in contacts:
        receipts.append(SourceReceipt(
            source_id=contact.contact_id,
            source_type="salesforce_contact",
            field="email",
            authority="commercial_record",
            observed_at=opportunity.close_date,
            claim=f"{contact.name} is a Salesforce contact with role {contact.role or 'unknown'}.",
            customer_safe=False,
        ))
    for entitlement in entitlements:
        receipts.append(SourceReceipt(
            source_id=f"{entitlement.account_id}:{entitlement.capability}",
            source_type="entitlement",
            field="capability",
            authority="customer_observed",
            observed_at=entitlement.starts_at,
            claim=f"Entitled capability: {entitlement.capability} ({entitlement.entitled_quantity} {entitlement.unit}).",
            customer_safe=True,
        ))
    for plan in success_plans:
        receipts.append(SourceReceipt(
            source_id=plan.plan_id,
            source_type="success_plan",
            field="objectives",
            authority="internal_structured",
            observed_at=plan.target_date,
            claim=f"Existing success-plan objectives: {', '.join(plan.objectives)}.",
            customer_safe=False,
        ))
    for signal in (*customer_comms, *call_or_meeting_comms):
        receipts.append(SourceReceipt(
            source_id=signal.signal_id,
            source_type=f"comms_{signal.channel}",
            field="timestamp",
            authority="customer_direct",
            observed_at=signal.timestamp,
            claim=f"Customer-facing {signal.channel} evidence exists.",
            customer_safe=True,
        ))
    for attendance in calendar_attendance:
        receipts.append(SourceReceipt(
            source_id=attendance.event_id,
            source_type="google_calendar_event",
            field="attendees",
            authority="customer_direct",
            observed_at=attendance.start_at,
            claim=(
                f"{attendance.attendee_email} was listed on calendar event "
                f"{attendance.summary!r} with response {attendance.response_status}."
            ),
            customer_safe=False,
        ))
    for note in internal_notes:
        receipts.append(SourceReceipt(
            source_id=note.note_id,
            source_type=f"internal_{note.source}",
            field="content",
            authority="internal_unstructured",
            observed_at=note.timestamp,
            claim="Internal customer context exists.",
            customer_safe=False,
        ))
    for project in onboarding_projects:
        receipts.append(SourceReceipt(
            source_id=project.project_id,
            source_type="onboarding_project",
            field="name",
            authority="internal_structured",
            observed_at=project.start_date or opportunity.close_date,
            claim=f"Onboarding project evidence: {project.name}.",
            customer_safe=False,
        ))
    for phase in onboarding_phases:
        receipts.append(SourceReceipt(
            source_id=phase.phase_id,
            source_type="onboarding_phase",
            field="name",
            authority="internal_structured",
            observed_at=phase.start_date or opportunity.close_date,
            claim=f"Onboarding phase evidence: {phase.name}.",
            customer_safe=False,
        ))
    for task in onboarding_tasks:
        receipts.append(SourceReceipt(
            source_id=task.task_id,
            source_type="onboarding_task",
            field="name",
            authority="internal_structured",
            observed_at=task.start_date or task.due_date or opportunity.close_date,
            claim=f"Onboarding task evidence: {task.name}.",
            customer_safe=False,
        ))
    for milestone in ttv_milestones:
        receipts.append(SourceReceipt(
            source_id=f"{milestone.account_id}:{milestone.milestone}",
            source_type="time_to_value_milestone",
            field="expected_by",
            authority="customer_observed",
            observed_at=milestone.achieved_at or milestone.expected_by,
            claim=(
                f"TTV milestone {milestone.milestone} is expected by "
                f"{milestone.expected_by}."
            ),
            customer_safe=False,
        ))
    return tuple(receipts)


def _stakeholder_verification(
    *,
    contacts: tuple[CRMContact, ...],
    stakeholders: tuple[StakeholderRelationship, ...],
    customer_comms: tuple[CommunicationSignal, ...],
    call_or_meeting_comms: tuple[CommunicationSignal, ...],
    calendar_attendance: tuple[CalendarAttendance, ...],
) -> tuple[StakeholderVerification, ...]:
    contact_by_id = {contact.contact_id: contact for contact in contacts}
    relationship_by_contact = {item.contact_id: item for item in stakeholders}
    observed: dict[str, set[str]] = {}
    for signal in (*customer_comms, *call_or_meeting_comms):
        if signal.contact_id:
            observed.setdefault(signal.contact_id, set()).add(signal.channel)
        for attendee in signal.attendees:
            observed.setdefault(attendee.lower(), set()).add(f"{signal.channel}:attendee")
    for attendance in calendar_attendance:
        if attendance.status == "confirmed" and attendance.response_status != "declined":
            observed.setdefault(attendance.attendee_email.lower(), set()).add("google_calendar:attendee")

    rows: list[StakeholderVerification] = []
    for contact in contacts:
        contact_sources = set(observed.get(contact.contact_id, set()))
        contact_sources.update(observed.get(contact.email.lower(), set()))
        sources = tuple(sorted(contact_sources))
        relationship = relationship_by_contact.get(contact.contact_id)
        rows.append(StakeholderVerification(
            person_key=contact.email.lower(),
            crm_contact_id=contact.contact_id,
            crm_role=contact.role,
            relationship_role=relationship.relationship_type if relationship else None,
            observed_sources=sources,
            appearances=len(sources),
            confidence=0.9 if sources and relationship else 0.7 if sources else 0.45,
            verification_state="declared_and_observed" if sources else "declared_not_observed",
        ))
    known_emails = {contact.email.lower() for contact in contacts}
    known_ids = {contact.contact_id for contact in contacts}
    for person_key, sources in sorted(observed.items()):
        if person_key in known_ids:
            continue
        if "@" in person_key and person_key not in known_emails:
            rows.append(StakeholderVerification(
                person_key=person_key,
                crm_contact_id=None,
                crm_role=None,
                relationship_role=None,
                observed_sources=tuple(sorted(sources)),
                appearances=len(sources),
                confidence=0.62,
                verification_state="observed_missing_from_crm",
            ))
    return tuple(rows)


def _build_success_plan(
    *,
    as_of: str,
    account: CRMAccount,
    opportunity: CRMOpportunity,
    contacts: tuple[CRMContact, ...],
    stakeholder_rows: tuple[StakeholderVerification, ...],
    entitlements: tuple[Entitlement, ...],
    usage_signals: tuple[UsageSignal, ...],
    customer_comms: tuple[CommunicationSignal, ...],
    call_or_meeting_comms: tuple[CommunicationSignal, ...],
    calendar_attendance: tuple[CalendarAttendance, ...],
    internal_notes: tuple,
    onboarding_projects: tuple[OnboardingProject, ...],
    onboarding_phases: tuple[OnboardingPhase, ...],
    onboarding_tasks: tuple[OnboardingTask, ...],
    success_plans: tuple[SuccessPlan, ...],
    company: CSCompany | None,
    health: HealthScore | None,
    adoption: AdoptionSummary | None,
    stakeholders: tuple[StakeholderRelationship, ...],
    ttv_milestones: tuple[TimeToValueMilestone, ...],
) -> tuple[tuple[OnboardingMilestone, ...], SuccessPlanMethodology]:
    owner = _owner_name(contacts) or account.owner_id
    source_ids = (opportunity.opportunity_id, *(f"{e.account_id}:{e.capability}" for e in entitlements[:3]))
    kickoff_date = as_of
    first_value_hypotheses = _first_value_hypotheses(
        entitlements=entitlements,
        success_plans=success_plans,
        internal_notes=internal_notes,
        usage_signals=usage_signals,
    )
    selected_first_value = next(
        (item for item in first_value_hypotheses if item.selection_state == "selected"),
        None,
    )
    first_capability = (
        selected_first_value.capability if selected_first_value is not None else "purchased workflow"
    )
    outcome = _primary_success_outcome(
        entitlements=entitlements,
        success_plans=success_plans,
        internal_notes=internal_notes,
    )
    first_value_criteria = _first_value_acceptance_criteria(first_capability, outcome)
    value_alignment = _success_plan_value_model_alignment(
        as_of=as_of,
        account=account,
        opportunity=opportunity,
        company=company,
        health=health,
        adoption=adoption,
        entitlements=entitlements,
        usage_signals=usage_signals,
        success_plans=success_plans,
        ttv_milestones=ttv_milestones,
        stakeholders=stakeholders,
        customer_comms=customer_comms,
        call_or_meeting_comms=call_or_meeting_comms,
        onboarding_projects=onboarding_projects,
        onboarding_phases=onboarding_phases,
        onboarding_tasks=onboarding_tasks,
    )
    milestones = (
        OnboardingMilestone(
            "Internal AE-to-CS handoff complete",
            account.owner_id,
            kickoff_date,
            (
                "CSM can name customer goal, first-value definition, stakeholder map, "
                "purchased scope, integration footprint, and implementation dependencies."
            ),
            _non_empty_sources((opportunity.opportunity_id, *(note.note_id for note in internal_notes))),
            _measurement_for_rail(value_alignment, "ttv_priority", "unresolved_priority_score"),
        ),
        OnboardingMilestone(
            "Customer kickoff scheduled",
            owner,
            kickoff_date,
            "Kickoff invite includes verified champion, admin or technical owner, and executive sponsor if known.",
            _non_empty_sources(source_ids + tuple(row.person_key for row in stakeholder_rows if row.appearances)),
            _measurement_for_rail(value_alignment, "relationship_coverage", "verified_relationship_roles"),
        ),
        OnboardingMilestone(
            "Entitlements and workspace provisioned",
            account.owner_id,
            opportunity.close_date,
            "Purchased package is enabled and admin can access the workspace.",
            _non_empty_sources(source_ids + tuple(signal.signal_id for signal in usage_signals[:3])),
            _measurement_for_rail(value_alignment, "activation", "adoption_rate"),
        ),
        OnboardingMilestone(
            "First value event achieved",
            owner,
            opportunity.close_date,
            first_value_criteria,
            _non_empty_sources(source_ids + tuple(plan.plan_id for plan in success_plans[:2])),
            _measurement_for_rail(value_alignment, "feature_depth", "entitled_capability_depth"),
        ),
        OnboardingMilestone(
            "Executive checkpoint completed",
            account.owner_id,
            opportunity.close_date,
            f"CSM confirms progress toward {outcome}, blockers, and next adoption motion with sponsor or buyer.",
            _non_empty_sources((
                opportunity.opportunity_id,
                *(row.person_key for row in stakeholder_rows if row.relationship_role == "executive_sponsor"),
            )),
            _measurement_for_rail(value_alignment, "outcome_realization", "realized_outcome_state"),
        ),
    )
    methodology = _success_plan_methodology(
        account=account,
        opportunity=opportunity,
        lifecycle_stage="enterprise_closed_won_onboarding",
        first_capability=first_capability,
        outcome=outcome,
        milestones=milestones,
        contacts=contacts,
        stakeholder_rows=stakeholder_rows,
        entitlements=entitlements,
        usage_signals=usage_signals,
        customer_comms=customer_comms,
        call_or_meeting_comms=call_or_meeting_comms,
        calendar_attendance=calendar_attendance,
        internal_notes=internal_notes,
        onboarding_projects=onboarding_projects,
        onboarding_phases=onboarding_phases,
        onboarding_tasks=onboarding_tasks,
        success_plans=success_plans,
        value_alignment=value_alignment,
        first_value_hypotheses=first_value_hypotheses,
    )
    return milestones, methodology


def _success_plan_methodology(
    *,
    account: CRMAccount,
    opportunity: CRMOpportunity,
    lifecycle_stage: str,
    first_capability: str,
    outcome: str,
    milestones: tuple[OnboardingMilestone, ...],
    contacts: tuple[CRMContact, ...],
    stakeholder_rows: tuple[StakeholderVerification, ...],
    entitlements: tuple[Entitlement, ...],
    usage_signals: tuple,
    customer_comms: tuple,
    call_or_meeting_comms: tuple,
    calendar_attendance: tuple[CalendarAttendance, ...],
    internal_notes: tuple,
    onboarding_projects: tuple[OnboardingProject, ...],
    onboarding_phases: tuple[OnboardingPhase, ...],
    onboarding_tasks: tuple[OnboardingTask, ...],
    success_plans: tuple[SuccessPlan, ...],
    value_alignment: SuccessPlanValueModelAlignment | None,
    first_value_hypotheses: tuple[SuccessPlanFirstValueHypothesis, ...],
) -> SuccessPlanMethodology:
    input_evidence = (
        SuccessPlanInputEvidence(
            "commercial_trigger",
            (opportunity.opportunity_id,),
            False,
            f"Closed-won Salesforce opportunity for {account.name}.",
        ),
        SuccessPlanInputEvidence(
            "purchased_scope",
            tuple(f"{item.account_id}:{item.capability}" for item in entitlements),
            True,
            "Entitlements define the purchased capabilities the plan may activate.",
        ),
        SuccessPlanInputEvidence(
            "sales_and_customer_context",
            tuple(
                [signal.signal_id for signal in (*customer_comms, *call_or_meeting_comms)]
                + [attendance.event_id for attendance in calendar_attendance]
                + [note.note_id for note in internal_notes]
            ),
            False,
            "Customer emails, calls, calendar attendance, and internal notes shape outcome and kickoff context.",
        ),
        SuccessPlanInputEvidence(
            "stakeholder_map",
            tuple(row.person_key for row in stakeholder_rows),
            False,
            "Salesforce contacts plus observed communication/calendar participants identify owners and gaps.",
        ),
        SuccessPlanInputEvidence(
            "current_state",
            tuple([signal.signal_id for signal in usage_signals] + [task.task_id for task in onboarding_tasks]),
            False,
            "Usage/provisioning and onboarding tasks show what has already started.",
        ),
        SuccessPlanInputEvidence(
            "value_model_thresholds",
            tuple(
                item
                for rail in value_alignment.rails
                for item in rail.evidence_source_ids
            ) if value_alignment is not None else (),
            False,
            (
                "Lifecycle-aware value-model thresholds define the measurable targets "
                "for activation, penetration, feature depth, outcome realization, and TTV priority."
            ),
        ),
    )
    validation_checks = _success_plan_validation_checks(
        opportunity=opportunity,
        milestones=milestones,
        stakeholder_rows=stakeholder_rows,
        entitlements=entitlements,
        usage_signals=usage_signals,
        customer_comms=customer_comms,
        call_or_meeting_comms=call_or_meeting_comms,
        calendar_attendance=calendar_attendance,
        value_alignment=value_alignment,
        first_value_hypotheses=first_value_hypotheses,
    )
    open_questions = _success_plan_open_questions(
        stakeholder_rows=stakeholder_rows,
        usage_signals=usage_signals,
        onboarding_projects=onboarding_projects,
        entitlements=entitlements,
    )
    confidence = _success_plan_confidence(
        success_plans=success_plans,
        customer_comms=customer_comms,
        call_or_meeting_comms=call_or_meeting_comms,
        calendar_attendance=calendar_attendance,
        internal_notes=internal_notes,
        usage_signals=usage_signals,
        value_alignment=value_alignment,
        first_value_hypotheses=first_value_hypotheses,
    )
    return SuccessPlanMethodology(
        method_version="enterprise_closed_won_success_plan_v1",
        method_config_version=ENTERPRISE_SUCCESS_PLAN_CONFIG_VERSION,
        lifecycle_stage=lifecycle_stage,
        construction_steps=(
            "Confirm the opportunity is Closed Won and enterprise-sized from Salesforce.",
            "Resolve customer organization identity and verify stakeholders from CRM, email/call, and Calendar evidence.",
            "Use entitlements as the hard boundary for promised activation scope.",
            "Build the deterministic customer value model from company, health, adoption, entitlement, telemetry, success-plan, stakeholder, communication, and TTV evidence.",
            "Resolve lifecycle-aware thresholds and tenant service tier before selecting targets.",
            "Project TTV priority from the value-model rails, open milestones, onboarding activation gaps, overdue plans, health, and ARR tier.",
            "Infer the primary outcome from existing success-plan objectives, internal handoff notes, and purchased capabilities.",
            "Rank candidate first-value hypotheses from entitlements, success-plan objectives, internal notes, and telemetry; preserve alternatives instead of flattening them.",
            "Build milestones in CSM order and bind each milestone to a measurable rail target.",
            "Attach source IDs to every milestone and keep customer-facing language behind ActionGate.",
        ),
        input_evidence=input_evidence,
        outcome_hypotheses=(
            SuccessPlanOutcomeHypothesis(
                outcome=outcome,
                confidence=confidence,
                evidence_source_ids=tuple(
                    [plan.plan_id for plan in success_plans]
                    + [f"{item.account_id}:{item.capability}" for item in entitlements[:3]]
                    + [note.note_id for note in internal_notes[:2]]
                ),
                unresolved_questions=open_questions,
            ),
        ),
        first_value_hypotheses=first_value_hypotheses,
        confidence_model=(
            "Start from source diversity and value-model availability.",
            "Add confidence for customer/call/calendar context, success-plan objectives, telemetry, and explicit first-value evidence.",
            "Subtract confidence when first-value alternatives exist without customer-confirmed selection.",
            "Never infer first value from completed milestone count alone.",
        ),
        milestone_rationale=tuple(
            f"{item.milestone}: {item.acceptance_criteria}" for item in milestones
        ),
        validation_checks=validation_checks,
        customer_fit_summary=(
            f"The plan is tailored to {account.name} by anchoring first value on "
            f"{first_capability}, outcome on {outcome}, owners on verified stakeholder evidence, "
            "and measurable targets on the account's resolved value-model thresholds."
        ),
        open_questions=open_questions,
        value_model_alignment=value_alignment,
    )


def _primary_success_outcome(
    *,
    entitlements: tuple[Entitlement, ...],
    success_plans: tuple,
    internal_notes: tuple,
) -> str:
    if success_plans:
        objectives = tuple(
            objective.replace("_", " ")
            for plan in success_plans
            for objective in getattr(plan, "objectives", ())
        )
        if objectives:
            return objectives[0]
    note_text = " ".join(getattr(note, "content", "") for note in internal_notes).lower()
    if "first value" in note_text:
        return "achieve first measurable value from the purchased workflow"
    if entitlements:
        return f"activate {entitlements[0].capability.replace('_', ' ')} for the launch team"
    return "confirm the customer success outcome during kickoff"


def _first_value_hypotheses(
    *,
    entitlements: tuple[Entitlement, ...],
    success_plans: tuple,
    internal_notes: tuple,
    usage_signals: tuple[UsageSignal, ...],
) -> tuple[SuccessPlanFirstValueHypothesis, ...]:
    objective_text = " ".join(
        objective.replace("_", " ").lower()
        for plan in success_plans
        for objective in getattr(plan, "objectives", ())
    )
    note_text = " ".join(getattr(note, "content", "") for note in internal_notes).lower()
    usage_metrics = {signal.metric_name.lower(): signal.signal_id for signal in usage_signals}
    hypotheses: list[tuple[float, SuccessPlanFirstValueHypothesis]] = []
    for idx, entitlement in enumerate(entitlements):
        capability = entitlement.capability.replace("_", " ")
        raw_capability = entitlement.capability.lower()
        evidence = [f"{entitlement.account_id}:{entitlement.capability}"]
        score = 0.35
        rationale = ["purchased capability"]
        if raw_capability in objective_text or capability in objective_text:
            score += 0.2
            rationale.append("named in existing success-plan objective")
            evidence.extend(plan.plan_id for plan in success_plans)
        if raw_capability in note_text or capability in note_text:
            score += 0.15
            rationale.append("referenced in internal handoff notes")
            evidence.extend(note.note_id for note in internal_notes)
        metric_matches = tuple(
            signal_id for metric, signal_id in usage_metrics.items()
            if raw_capability in metric or metric in raw_capability
        )
        if metric_matches:
            score += 0.15
            rationale.append("has related product telemetry")
            evidence.extend(metric_matches)
        score += max(0.0, 0.05 - (idx * 0.01))
        hypotheses.append((
            round(min(0.95, score), 2),
            SuccessPlanFirstValueHypothesis(
                capability=capability,
                selection_state="alternative",
                confidence=round(min(0.95, score), 2),
                evidence_source_ids=_non_empty_sources(tuple(evidence)),
                rationale=", ".join(rationale),
            ),
        ))
    if not hypotheses:
        return (SuccessPlanFirstValueHypothesis(
            capability="purchased workflow",
            selection_state="selected",
            confidence=0.2,
            evidence_source_ids=(),
            rationale="No entitlement record was available; kickoff must confirm first value before customer-facing plan language.",
        ),)
    ranked = [item for _, item in sorted(hypotheses, key=lambda pair: (-pair[0], pair[1].capability))]
    selected = ranked[0]
    return (
        SuccessPlanFirstValueHypothesis(
            capability=selected.capability,
            selection_state="selected",
            confidence=selected.confidence,
            evidence_source_ids=selected.evidence_source_ids,
            rationale=selected.rationale,
        ),
        *ranked[1:],
    )


def _success_plan_confidence(
    *,
    success_plans: tuple[SuccessPlan, ...],
    customer_comms: tuple,
    call_or_meeting_comms: tuple,
    calendar_attendance: tuple[CalendarAttendance, ...],
    internal_notes: tuple,
    usage_signals: tuple,
    value_alignment: SuccessPlanValueModelAlignment | None,
    first_value_hypotheses: tuple[SuccessPlanFirstValueHypothesis, ...],
) -> float:
    source_support = sum((
        1 if success_plans else 0,
        1 if customer_comms else 0,
        1 if call_or_meeting_comms else 0,
        1 if calendar_attendance else 0,
        1 if internal_notes else 0,
        1 if usage_signals else 0,
        1 if value_alignment is not None else 0,
    ))
    selected = next(
        (item for item in first_value_hypotheses if item.selection_state == "selected"),
        None,
    )
    ambiguity_penalty = 0.05 if len(first_value_hypotheses) > 1 else 0.0
    confidence = (
        0.35
        + min(0.28, source_support * 0.04)
        + (selected.confidence * 0.25 if selected is not None else 0.0)
        + (0.08 if value_alignment is not None else 0.0)
        - ambiguity_penalty
    )
    return round(max(0.0, min(0.95, confidence)), 2)


def _first_value_acceptance_criteria(first_capability: str, outcome: str) -> str:
    return (
        f"Customer completes one observable {first_capability} workflow tied to "
        f"{outcome}, with owner, date, and evidence captured before executive checkpoint."
    )


def _success_plan_validation_checks(
    *,
    opportunity: CRMOpportunity,
    milestones: tuple[OnboardingMilestone, ...],
    stakeholder_rows: tuple[StakeholderVerification, ...],
    entitlements: tuple[Entitlement, ...],
    usage_signals: tuple[UsageSignal, ...],
    customer_comms: tuple[CommunicationSignal, ...],
    call_or_meeting_comms: tuple[CommunicationSignal, ...],
    calendar_attendance: tuple[CalendarAttendance, ...],
    value_alignment: SuccessPlanValueModelAlignment | None,
    first_value_hypotheses: tuple[SuccessPlanFirstValueHypothesis, ...],
) -> tuple[SuccessPlanValidationCheck, ...]:
    customer_context_ids = tuple(
        [signal.signal_id for signal in (*customer_comms, *call_or_meeting_comms)]
        + [attendance.event_id for attendance in calendar_attendance]
    )
    technical = tuple(
        row.person_key for row in stakeholder_rows
        if row.crm_role == "technical_lead" or row.relationship_role == "technical_lead"
    )
    sponsor = tuple(
        row.person_key for row in stakeholder_rows
        if row.relationship_role == "executive_sponsor" or row.crm_role == "executive_sponsor"
    )
    milestone_ids = tuple(source for milestone in milestones for source in milestone.source_ids)
    entitlement_ids = tuple(f"{item.account_id}:{item.capability}" for item in entitlements)
    value_rail_ids = tuple(
        source
        for rail in value_alignment.rails
        for source in rail.evidence_source_ids
    ) if value_alignment is not None else ()
    measured_milestone_ids = tuple(
        source
        for milestone in milestones
        if milestone.measurement is not None
        for source in milestone.measurement.evidence_source_ids
    )
    first_value_milestone = next(
        (milestone for milestone in milestones if milestone.milestone == "First value event achieved"),
        None,
    )
    selected_first_value = tuple(
        hypothesis.capability for hypothesis in first_value_hypotheses
        if hypothesis.selection_state == "selected"
    )
    selected_first_value_ids = tuple(
        source
        for hypothesis in first_value_hypotheses
        if hypothesis.selection_state == "selected"
        for source in hypothesis.evidence_source_ids
    )
    expected_rails = {
        "activation",
        "seat_penetration",
        "feature_depth",
        "outcome_realization",
        "ttv_priority",
        "relationship_coverage",
    }
    actual_rails = {rail.rail for rail in value_alignment.rails} if value_alignment is not None else set()
    return (
        SuccessPlanValidationCheck(
            "closed_won_source_confirmed",
            _normalize_stage(opportunity.stage_name) == "closed won",
            (opportunity.opportunity_id,),
            "Opportunity stage must be read from Salesforce and be Closed Won.",
        ),
        SuccessPlanValidationCheck(
            "purchased_scope_present",
            bool(entitlements),
            entitlement_ids,
            "At least one entitlement or order-line capability must bound the plan.",
        ),
        SuccessPlanValidationCheck(
            "customer_context_present",
            bool(customer_context_ids),
            customer_context_ids,
            "Customer-facing email, call, meeting, or calendar evidence must support the handoff.",
        ),
        SuccessPlanValidationCheck(
            "technical_owner_identified",
            bool(technical),
            technical,
            "A technical/admin owner should be declared or observed before kickoff.",
        ),
        SuccessPlanValidationCheck(
            "executive_sponsor_identified",
            bool(sponsor),
            sponsor,
            "Executive sponsor or buyer coverage should be present for enterprise launch.",
        ),
        SuccessPlanValidationCheck(
            "current_state_observed",
            bool(usage_signals),
            tuple(signal.signal_id for signal in usage_signals),
            "Provisioning or product state should be observed before customer-facing plan language.",
        ),
        SuccessPlanValidationCheck(
            "milestones_have_evidence",
            all(milestone.source_ids for milestone in milestones),
            milestone_ids,
            "Every success-plan milestone must carry source IDs.",
        ),
        SuccessPlanValidationCheck(
            "value_model_available",
            value_alignment is not None,
            value_rail_ids,
            "Success plan must be built from the deterministic customer value model.",
        ),
        SuccessPlanValidationCheck(
            "resolved_thresholds_applied",
            value_alignment is not None
            and bool(value_alignment.config_version)
            and bool(value_alignment.rule_name)
            and bool(value_alignment.thresholds),
            value_rail_ids,
            "Lifecycle-aware threshold config version and rule name must be recorded.",
        ),
        SuccessPlanValidationCheck(
            "ttv_projection_calculated",
            value_alignment is not None and value_alignment.ttv_priority_score >= 0,
            tuple(
                factor_source
                for factor in (value_alignment.ttv_factors if value_alignment is not None else ())
                for factor_source in factor.evidence_source_ids
            ),
            "TTV priority must be projected from value-model and onboarding evidence.",
        ),
        SuccessPlanValidationCheck(
            "milestones_map_to_value_model_rails",
            value_alignment is not None
            and expected_rails <= actual_rails
            and all(milestone.measurement is not None for milestone in milestones),
            measured_milestone_ids,
            "Every milestone must carry a measurable rail target from the value-model alignment.",
        ),
        SuccessPlanValidationCheck(
            "first_value_milestone_explicit",
            first_value_milestone is not None
            and first_value_milestone.measurement is not None
            and first_value_milestone.measurement.rail == "feature_depth"
            and bool(selected_first_value)
            and selected_first_value[0] in first_value_milestone.acceptance_criteria,
            (*selected_first_value_ids, *(first_value_milestone.source_ids if first_value_milestone else ())),
            "First value must be an explicit selected hypothesis bound to the feature-depth rail.",
        ),
        SuccessPlanValidationCheck(
            "alternative_first_value_hypotheses_preserved",
            bool(first_value_hypotheses)
            and sum(1 for hypothesis in first_value_hypotheses if hypothesis.selection_state == "selected") == 1,
            tuple(
                source
                for hypothesis in first_value_hypotheses
                for source in hypothesis.evidence_source_ids
            ),
            "The plan must keep candidate first-value hypotheses instead of flattening them into one opaque choice.",
        ),
    )


def _failed_success_plan_checks(methodology: SuccessPlanMethodology | None) -> tuple[str, ...]:
    if methodology is None:
        return ()
    return tuple(
        f"success_plan_validation_failed:{check.check_name}"
        for check in methodology.validation_checks
        if not check.passed
    )


def _success_plan_value_model_alignment(
    *,
    as_of: str,
    account: CRMAccount,
    opportunity: CRMOpportunity,
    company: CSCompany | None,
    health: HealthScore | None,
    adoption: AdoptionSummary | None,
    entitlements: tuple[Entitlement, ...],
    usage_signals: tuple[UsageSignal, ...],
    success_plans: tuple[SuccessPlan, ...],
    ttv_milestones: tuple[TimeToValueMilestone, ...],
    stakeholders: tuple[StakeholderRelationship, ...],
    customer_comms: tuple[CommunicationSignal, ...],
    call_or_meeting_comms: tuple[CommunicationSignal, ...],
    onboarding_projects: tuple[OnboardingProject, ...],
    onboarding_phases: tuple[OnboardingPhase, ...],
    onboarding_tasks: tuple[OnboardingTask, ...],
) -> SuccessPlanValueModelAlignment | None:
    if company is None or health is None or adoption is None:
        return None

    cfg = load_value_model_config()
    model = build_customer_value_model(
        account=account,
        company=company,
        health=health,
        adoption=adoption,
        entitlements=entitlements,
        usage_signals=usage_signals,
        success_plans=success_plans,
        opportunities=(opportunity,),
        onboarding_milestones=ttv_milestones,
        stakeholders=stakeholders,
        communication_signals=(*customer_comms, *call_or_meeting_comms),
        as_of=as_of,
        config=cfg,
    )
    open_milestone_gaps = tuple(
        milestone
        for milestone in ttv_milestones
        if milestone.achieved_at is None and iso_date(milestone.expected_by) <= iso_date(as_of)
    )
    overdue_success_plans = tuple(
        plan
        for plan in success_plans
        if plan.status not in {"realized", "achieved", "complete"}
        and iso_date(plan.target_date) <= iso_date(as_of)
    )
    activation_gap_ids = onboarding_activation_gap_ids(
        projects=onboarding_projects,
        phases=onboarding_phases,
        tasks=onboarding_tasks,
        as_of=as_of,
        covered_milestone_names=frozenset(milestone.milestone for milestone in open_milestone_gaps),
    )
    onboarding_evidence_ids = frozenset(
        [phase.phase_id for phase in onboarding_phases]
        + [task.task_id for task in onboarding_tasks]
    )
    projected = project_ttv_lens(
        model,
        company=company,
        health=health,
        open_milestone_gaps=open_milestone_gaps,
        overdue_success_plans=overdue_success_plans,
        as_of=as_of,
        onboarding_evidence_ids=onboarding_evidence_ids,
        onboarding_activation_gap_ids=activation_gap_ids,
    )
    tier = resolve_tenant_tier(account_attributes(account, company), cfg).tier
    thresholds = asdict(model.resolved_thresholds.thresholds)
    rails = _success_plan_value_rails(
        model=model,
        projected=projected,
        adoption=adoption,
        entitlements=entitlements,
        stakeholders=stakeholders,
        activation_gap_ids=activation_gap_ids,
    )
    return SuccessPlanValueModelAlignment(
        account_id=account.account_id,
        lifecycle_stage=model.lifecycle_stage,
        service_tier=tier,
        config_version=model.resolved_thresholds.config_version,
        rule_name=model.resolved_thresholds.rule_name,
        thresholds=thresholds,
        rails=rails,
        ttv_priority_score=projected.score,
        ttv_factors=tuple(_factor_snapshot(factor) for factor in projected.factors),
        plan_target_formula=(
            "Use resolved lifecycle thresholds, not a global account score.",
            "Set activation target from adoption_floor and seat_penetration_floor.",
            "Set feature-depth target from entitled capabilities minus underused capabilities.",
            "Set outcome target from stated objectives and realized-state evidence.",
            "Escalate TTV work until projected priority factors have owners or fall to zero.",
        ),
    )


def _success_plan_value_rails(
    *,
    model: CustomerValueModel,
    projected: ProjectedPriority,
    adoption: AdoptionSummary,
    entitlements: tuple[Entitlement, ...],
    stakeholders: tuple[StakeholderRelationship, ...],
    activation_gap_ids: tuple[str, ...],
) -> tuple[SuccessPlanValueRail, ...]:
    thresholds = model.resolved_thresholds.thresholds
    depth_current = _feature_depth_ratio(model)
    relationship_current = float(len({
        item.relationship_type
        for item in stakeholders
        if item.relationship_type in {"champion", "technical_lead", "executive_sponsor", "admin"}
    }))
    relationship_target = float(thresholds.min_threaded_persons + 1)
    activation_factors = _factors_by_name(
        (*model.usage.factors, *model.divergences),
        {"health_usage_divergence"},
    )
    return (
        SuccessPlanValueRail(
            rail="activation",
            state="known",
            current_value=adoption.adoption_rate,
            target_value=thresholds.adoption_floor,
            threshold_name="adoption_floor",
            threshold_value=thresholds.adoption_floor,
            factors=tuple(_factor_snapshot(factor) for factor in activation_factors),
            evidence_source_ids=_non_empty_sources((
                _source_id("cs_platform", adoption.account_id, "adoption_rate", adoption.measured_at),
            )),
            interpretation="Are users activating at the lifecycle-aware adoption floor for this account?",
        ),
        SuccessPlanValueRail(
            rail="seat_penetration",
            state=model.penetration.state,
            current_value=model.penetration.seat_penetration,
            target_value=thresholds.seat_penetration_floor,
            threshold_name="seat_penetration_floor",
            threshold_value=thresholds.seat_penetration_floor,
            factors=tuple(_factor_snapshot(factor) for factor in model.penetration.factors),
            evidence_source_ids=_rail_evidence_ids(
                model.penetration.factors,
                fallback=(_source_id("cs_platform", adoption.account_id, "active_users", adoption.measured_at),),
            ),
            interpretation="Are active users keeping pace with the seat entitlement?",
        ),
        SuccessPlanValueRail(
            rail="feature_depth",
            state="known" if entitlements else "unknown",
            current_value=depth_current,
            target_value=thresholds.depth_floor,
            threshold_name="depth_floor",
            threshold_value=thresholds.depth_floor,
            factors=tuple(_factor_snapshot(factor) for factor in model.feature_depth.factors),
            evidence_source_ids=_rail_evidence_ids(
                model.feature_depth.factors,
                fallback=tuple(f"{item.account_id}:{item.capability}" for item in entitlements),
            ),
            interpretation="Are the purchased capabilities being used broadly enough for first value?",
        ),
        SuccessPlanValueRail(
            rail="outcome_realization",
            state=model.outcome.realized_state,
            current_value=1.0 if model.outcome.realized_state == "known" else 0.0,
            target_value=1.0,
            threshold_name="outcome_realized",
            threshold_value=1.0,
            factors=tuple(_factor_snapshot(factor) for factor in model.outcome.factors),
            evidence_source_ids=_rail_evidence_ids(model.outcome.factors),
            interpretation="Has a stated customer outcome been realized with source-backed evidence?",
        ),
        SuccessPlanValueRail(
            rail="ttv_priority",
            state="known",
            current_value=float(projected.score),
            target_value=0.0,
            threshold_name="unresolved_priority_score",
            threshold_value=0,
            factors=tuple(_factor_snapshot(factor) for factor in projected.factors),
            evidence_source_ids=_rail_evidence_ids(
                projected.factors,
                fallback=activation_gap_ids,
            ),
            interpretation="How much unresolved onboarding and value risk remains after lifecycle weighting?",
        ),
        SuccessPlanValueRail(
            rail="relationship_coverage",
            state="known" if stakeholders else "unknown",
            current_value=relationship_current,
            target_value=relationship_target,
            threshold_name="min_threaded_persons_plus_one",
            threshold_value=thresholds.min_threaded_persons + 1,
            factors=tuple(
                _factor_snapshot(factor)
                for factor in _factors_by_name(model.divergences, {"single_threaded_risk", "new_stakeholder_unengaged"})
            ),
            evidence_source_ids=tuple(item.contact_id for item in stakeholders),
            interpretation="Does the launch have enough verified relationship coverage for enterprise governance?",
        ),
    )


def _measurement_for_rail(
    alignment: SuccessPlanValueModelAlignment | None,
    rail_name: str,
    metric_name: str,
) -> MilestoneMeasurement | None:
    if alignment is None:
        return None
    rail = next((item for item in alignment.rails if item.rail == rail_name), None)
    if rail is None:
        return None
    return MilestoneMeasurement(
        metric_name=metric_name,
        current_value=rail.current_value,
        target_value=rail.target_value,
        threshold_name=rail.threshold_name,
        threshold_value=rail.threshold_value,
        evidence_source_ids=rail.evidence_source_ids,
        rail=rail.rail,
    )


def _feature_depth_ratio(model: CustomerValueModel) -> float | None:
    entitled = model.feature_depth.entitled_capabilities
    if not entitled:
        return None
    used_count = len(entitled) - len(model.feature_depth.underused_capabilities)
    return used_count / len(entitled)


def _factors_by_name(
    factors: tuple[ValueFactor, ...],
    names: set[str],
) -> tuple[ValueFactor, ...]:
    return tuple(factor for factor in factors if factor.name in names)


def _factor_snapshot(factor: ValueFactor) -> SuccessPlanValueFactor:
    return SuccessPlanValueFactor(
        name=factor.name,
        value=factor.value,
        contribution=factor.contribution,
        threshold_name=factor.threshold_name,
        threshold_value=factor.threshold_value,
        evidence_source_ids=tuple(_evidence_ref_id(ref) for ref in factor.evidence),
    )


def _rail_evidence_ids(
    factors: tuple[ValueFactor, ...],
    *,
    fallback: tuple[str, ...] = (),
) -> tuple[str, ...]:
    ids = tuple(
        _evidence_ref_id(ref)
        for factor in factors
        for ref in factor.evidence
    )
    return _non_empty_sources(ids or fallback)


def _evidence_ref_id(ref: EvidenceRef) -> str:
    return _source_id(ref.source, ref.source_id, ref.field, ref.observed_at)


def _source_id(source: str, source_id: str, field: str, observed_at: str) -> str:
    return f"{source}:{source_id}:{field}:{observed_at}"


def _success_plan_open_questions(
    *,
    stakeholder_rows: tuple[StakeholderVerification, ...],
    usage_signals: tuple,
    onboarding_projects: tuple,
    entitlements: tuple[Entitlement, ...],
) -> tuple[str, ...]:
    questions: list[str] = []
    if not any(row.relationship_role == "executive_sponsor" or row.crm_role == "executive_sponsor" for row in stakeholder_rows):
        questions.append("Who is the executive sponsor or buyer accountable for value?")
    if not any(row.relationship_role == "technical_lead" or row.crm_role == "technical_lead" for row in stakeholder_rows):
        questions.append("Who owns admin setup, data access, and technical dependencies?")
    if not usage_signals:
        questions.append("Has the workspace or tenant been provisioned yet?")
    if not onboarding_projects:
        questions.append("Has an implementation/onboarding project been created?")
    if not entitlements:
        questions.append("Which purchased capabilities and quantities are in scope?")
    return tuple(questions)


def _non_empty_sources(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(item for item in dict.fromkeys(values) if item)


def _customer_integrations(
    *,
    opportunity: CRMOpportunity,
    entitlements: tuple[Entitlement, ...],
    usage_signals: tuple,
    customer_comms: tuple,
    call_or_meeting_comms: tuple,
    calendar_attendance: tuple[CalendarAttendance, ...],
    internal_notes: tuple,
) -> tuple[CustomerIntegrationFootprint, ...]:
    capability_tokens = _tokens(
        *(entitlement.capability for entitlement in entitlements),
        *(getattr(signal, "metric_name", "") for signal in usage_signals),
    )
    internal_tokens = _tokens(*(getattr(note, "source", "") for note in internal_notes))
    call_signals = tuple(signal for signal in call_or_meeting_comms if getattr(signal, "channel", None) == "call")
    meeting_signals = tuple(signal for signal in call_or_meeting_comms if getattr(signal, "channel", None) == "meeting")

    return (
        CustomerIntegrationFootprint(
            family="mcp",
            label="MCP",
            status="configured" if _contains_any(capability_tokens, ("mcp", "meeting_prep")) else "unknown",
            provider="centralize_mcp" if _contains_any(capability_tokens, ("mcp", "meeting_prep")) else None,
            provider_options=("centralize_mcp",),
            evidence_source_ids=_matching_entitlement_ids(entitlements, ("mcp", "meeting_prep")),
            note="MCP connection should be verified before kickoff.",
        ),
        CustomerIntegrationFootprint(
            family="chrome_extension",
            label="Chrome extension",
            status="configured" if _contains_any(capability_tokens, ("chrome", "extension")) else "unknown",
            provider="centralize_chrome_extension" if _contains_any(capability_tokens, ("chrome", "extension")) else None,
            provider_options=("centralize_chrome_extension",),
            evidence_source_ids=_matching_entitlement_ids(entitlements, ("chrome", "extension")),
            note="Confirm whether the browser extension is installed for admins or sellers.",
        ),
        CustomerIntegrationFootprint(
            family="crm",
            label="CRM",
            status="configured",
            provider="salesforce",
            provider_options=("salesforce",),
            evidence_source_ids=(opportunity.opportunity_id,),
            note="Salesforce account/opportunity context is the commercial source of truth.",
        ),
        CustomerIntegrationFootprint(
            family="messaging",
            label="Messaging",
            status="observed" if _contains_any(internal_tokens, ("slack",)) else "unknown",
            provider="slack" if _contains_any(internal_tokens, ("slack",)) else None,
            provider_options=("slack",),
            evidence_source_ids=tuple(note.note_id for note in internal_notes if "slack" in getattr(note, "source", "").lower()),
            note="Verify whether customer or internal Slack context should be synced.",
        ),
        CustomerIntegrationFootprint(
            family="email",
            label="Email",
            status="observed" if customer_comms else "unknown",
            provider=None,
            provider_options=("gmail", "outlook"),
            evidence_source_ids=tuple(signal.signal_id for signal in customer_comms),
            note="Provider must be confirmed as Gmail or Outlook before relying on email sync.",
        ),
        CustomerIntegrationFootprint(
            family="calendar",
            label="Calendar",
            status="observed" if calendar_attendance or meeting_signals else "unknown",
            provider="google_calendar" if calendar_attendance else None,
            provider_options=("google_calendar", "outlook_calendar"),
            evidence_source_ids=tuple(
                dict.fromkeys(
                    [attendance.event_id for attendance in calendar_attendance]
                    + [signal.signal_id for signal in meeting_signals]
                )
            ),
            note="Calendar attendee evidence can verify stakeholders and account-domain identity.",
        ),
        CustomerIntegrationFootprint(
            family="calls",
            label="Calls",
            status="observed" if call_signals else "unknown",
            provider=None,
            provider_options=_CALL_INTEGRATION_OPTIONS,
            evidence_source_ids=tuple(signal.signal_id for signal in call_signals),
            note="Confirm the connected call source: Gong, Salesloft, Clari Copilot, Avoma, Chorus, Fathom, Granola, Attention, Fireflies, or Grain.",
        ),
        CustomerIntegrationFootprint(
            family="sequences",
            label="Sequences",
            status="unknown",
            provider=None,
            provider_options=_SEQUENCE_INTEGRATION_OPTIONS,
            evidence_source_ids=(),
            note="Confirm whether Outreach or Gong Engage sequence activity should be included in the handoff.",
        ),
    )


def _customer_safe_baseline(
    *,
    account: CRMAccount,
    opportunity: CRMOpportunity,
    entitlements: tuple[Entitlement, ...],
    customer_comms: tuple,
    call_or_meeting_comms: tuple,
    calendar_attendance: tuple[CalendarAttendance, ...],
) -> tuple[str, ...]:
    capabilities = ", ".join(entitlement.capability.replace("_", " ") for entitlement in entitlements) or "the purchased package"
    return (
        f"{account.name} closed an enterprise opportunity on {opportunity.close_date}.",
        f"The launch plan should focus on enabling {capabilities}.",
        f"Customer-facing context is supported by {len(customer_comms)} email signal(s), "
        f"{len(call_or_meeting_comms)} call/meeting signal(s), and "
        f"{len(calendar_attendance)} Google Calendar attendee record(s).",
    )


def _internal_context(
    *,
    internal_notes: tuple,
    ctas: tuple,
    health: Any,
    adoption: Any,
    stakeholder_rows: tuple[StakeholderVerification, ...],
) -> tuple[str, ...]:
    context = []
    if internal_notes:
        context.append(f"Internal notes available: {len(internal_notes)}.")
    if ctas:
        context.append("Open CS CTAs: " + ", ".join(cta.reason for cta in ctas[:3]) + ".")
    if health is not None:
        context.append(f"Current health is {health.band} ({health.score:g}).")
    if adoption is not None:
        context.append(f"Current adoption is {adoption.active_users}/{adoption.licensed_users} users.")
    missing = [row.person_key for row in stakeholder_rows if row.verification_state == "observed_missing_from_crm"]
    if missing:
        context.append("Observed stakeholders missing from CRM: " + ", ".join(missing[:5]) + ".")
    return tuple(context)


def _risks(
    *,
    coverage: SourceCoverage,
    stakeholder_rows: tuple[StakeholderVerification, ...],
    entitlements: tuple[Entitlement, ...],
    usage_signals: tuple,
    health: Any,
) -> tuple[str, ...]:
    risks = list(coverage.missing_required_sources)
    if not any(row.relationship_role == "technical_lead" or row.crm_role == "technical_lead" for row in stakeholder_rows):
        risks.append("technical_owner_not_verified")
    if not any(row.relationship_role == "executive_sponsor" for row in stakeholder_rows):
        risks.append("executive_sponsor_not_verified")
    if not entitlements:
        risks.append("purchased_package_not_mapped_to_entitlements")
    if not usage_signals:
        risks.append("workspace_or_provisioning_not_observed")
    if health is not None and health.band in {"red", "yellow"}:
        risks.append(f"starting_health_{health.band}")
    return tuple(dict.fromkeys(risks))


def _kickoff_agenda(success_plan: tuple[OnboardingMilestone, ...]) -> tuple[str, ...]:
    return (
        "Confirm business outcome and first-value definition.",
        "Verify kickoff attendees and implementation owners.",
        "Review purchased package, entitlements, and provisioning state.",
        "Align on milestone dates, acceptance criteria, and escalation path.",
        "Agree on first executive checkpoint.",
        *tuple(f"Milestone: {item.milestone}" for item in success_plan[:3]),
    )


def _welcome_draft(
    *,
    account: CRMAccount,
    contact: CRMContact,
    kickoff_agenda: tuple[str, ...],
) -> str:
    agenda = "; ".join(kickoff_agenda[:4])
    return (
        f"Hi {contact.name}, congratulations on moving forward with {account.name}. "
        f"I would like to schedule the onboarding kickoff so we can {agenda}. "
        "I will use the kickoff to confirm owners, dates, and the first value checkpoint before we begin execution."
    )


def _propose_launch_actions(
    *,
    gate: ActionGate | None,
    event: SalesforceClosedWonEvent,
    account: CRMAccount,
    opportunity: CRMOpportunity,
    contact: CRMContact | None,
    draft: str | None,
    success_plan: tuple[OnboardingMilestone, ...],
    receipts: tuple[SourceReceipt, ...],
) -> tuple[LaunchProposalRef, ...]:
    if gate is None:
        return ()
    refs: list[LaunchProposalRef] = []
    source_ids = [receipt.source_id for receipt in receipts]
    if contact is not None and draft:
        gate.record_outreach_contact_ref(
            account_ref=account.account_id,
            contact_ref=contact.contact_id,
            email=contact.email,
            name=contact.name,
            consent=contact.consent_to_contact,
            cause_ref=f"enterprise-onboarding:{opportunity.opportunity_id}:contact-consent",
        )
        proposal = gate.propose(
            intent="enterprise_closed_won_onboarding",
            payload={
                "account_id": account.account_id,
                "account_name": account.name,
                "opportunity_id": opportunity.opportunity_id,
                "contact_id": contact.contact_id,
                "contact_email": contact.email,
                "draft_channel": "email",
                "subject": f"{account.name} onboarding kickoff",
                "body": draft,
                "evidence_ids": source_ids,
            },
            grounding_ref=f"enterprise-onboarding:{opportunity.opportunity_id}",
            cause_ref=f"enterprise-onboarding:{opportunity.opportunity_id}:{event.observed_at}",
            **proposal_fields_for("draft_customer_outreach"),
        )
        refs.append(_proposal_ref(proposal))
    proposal = gate.propose(
        intent="enterprise_closed_won_onboarding",
        payload={
            "account_id": account.account_id,
            "account_name": account.name,
            "opportunity_id": opportunity.opportunity_id,
            "success_plan_v0": [asdict(item) for item in success_plan],
            "evidence_ids": source_ids,
        },
        grounding_ref=f"enterprise-onboarding:{opportunity.opportunity_id}",
        cause_ref=f"enterprise-onboarding:{opportunity.opportunity_id}:{event.observed_at}",
        **proposal_fields_for("edit_success_plan"),
    )
    refs.append(_proposal_ref(proposal))
    return tuple(refs)


def _proposal_ref(proposal: ActionProposal) -> LaunchProposalRef:
    return LaunchProposalRef(
        proposal_id=proposal.proposal_id,
        action_type=proposal.action,
        status=proposal.status,
    )


def _ignored_packet(
    *,
    event: SalesforceClosedWonEvent,
    as_of: str,
    account: CRMAccount | None,
    reason: str,
) -> EnterpriseOnboardingLaunchPacket:
    account_id = account.account_id if account else event.account_id
    account_name = account.name if account else "Unresolved account"
    trigger = SourceReceipt(
        source_id=event.opportunity_id,
        source_type="salesforce_opportunity_event",
        field="stage_name",
        authority="commercial_record",
        observed_at=event.observed_at,
        claim=reason,
        customer_safe=False,
    )
    return EnterpriseOnboardingLaunchPacket(
        packet_id=f"enterprise-onboarding:{event.opportunity_id}:{as_of}",
        tenant_id=event.tenant_id,
        status="ignored",
        account_id=account_id,
        account_name=account_name,
        opportunity_id=event.opportunity_id,
        generated_at=as_of,
        trigger_receipt=trigger,
        coverage=SourceCoverage((), (), (), (reason,)),
        customer_safe_baseline=(),
        internal_context=(reason,),
        customer_integrations=(),
        stakeholder_verification=(),
        success_plan_methodology=None,
        success_plan_v0=(),
        risks=(reason,),
        recommended_next_action="No enterprise onboarding workflow was launched.",
        kickoff_agenda=(),
        customer_welcome_draft=None,
        source_receipts=(trigger,),
        proposals=(),
    )


def _onboarding_evidence(data_plane: CustomerDataPlane, account_id: str) -> tuple[tuple, tuple, tuple]:
    if data_plane.onboarding is None:
        return (), (), ()
    projects = tuple(data_plane.onboarding.list_projects_for_account(account_id))
    phases = tuple(
        phase
        for project in projects
        for phase in data_plane.onboarding.list_phases(project.project_id)
    )
    tasks = tuple(
        task
        for project in projects
        for task in data_plane.onboarding.list_tasks(project.project_id)
    )
    return projects, phases, tasks


def _ttv_milestones(data_plane: CustomerDataPlane, account_id: str) -> tuple[TimeToValueMilestone, ...]:
    telemetry_milestones = tuple(data_plane.telemetry.list_ttv_milestones(account_id))
    onboarding_milestones: tuple[TimeToValueMilestone, ...] = ()
    if data_plane.onboarding is not None:
        try:
            onboarding_milestones = tuple(data_plane.onboarding.derive_ttv_milestones(account_id))
        except Exception:
            onboarding_milestones = ()
    seen: set[tuple[str, str, str]] = set()
    merged: list[TimeToValueMilestone] = []
    for milestone in (*telemetry_milestones, *onboarding_milestones):
        key = (milestone.account_id, milestone.milestone, milestone.expected_by)
        if key in seen:
            continue
        seen.add(key)
        merged.append(milestone)
    return tuple(merged)


def _comms_evidence(data_plane: CustomerDataPlane, account_id: str) -> tuple[tuple, tuple, tuple]:
    if data_plane.comms is None:
        return (), (), ()
    gmail = tuple(data_plane.comms.list_gmail_signals(account_id))
    calls = tuple(data_plane.comms.list_call_transcript_signals(account_id))
    meetings = tuple(signal for signal in gmail if signal.channel == "meeting") + tuple(
        signal for signal in calls if signal.channel in {"call", "meeting"}
    )
    customer_emails = tuple(signal for signal in gmail if signal.channel == "email")
    internal_notes = tuple(data_plane.comms.list_internal_notes(account_id))
    return customer_emails, meetings, internal_notes


def resolve_account_by_calendar_attendee_domain(
    crm: CRMDataConnector,
    calendar_events: dict[str, Any] | None,
    *,
    tenant_id: str | None = None,
) -> CalendarAccountDomainResolution:
    """Resolve a customer account from Google Calendar attendee email domains.

    Salesforce remains the identity source. Calendar contributes observed email
    domains only; those domains must map to exactly one Salesforce account's
    Contact domain before the resolver returns an account UUID.
    """

    attendee_emails = _calendar_attendee_emails(calendar_events or {})
    attendee_domains = tuple(sorted({
        domain for email in attendee_emails
        if (domain := _email_domain(email)) and domain not in _PERSONAL_EMAIL_DOMAINS
    }))
    if not attendee_domains:
        return CalendarAccountDomainResolution(
            state="none",
            account_id=None,
            account_name=None,
            matched_domains=(),
            attendee_emails=attendee_emails,
            candidate_account_ids=(),
            reason="No non-personal attendee email domains were present on the calendar events.",
        )

    accounts_by_domain: dict[str, set[str]] = {}
    for account in crm.list_accounts(tenant_id=tenant_id):
        for contact in crm.list_contacts(account.account_id):
            domain = _email_domain(contact.email)
            if domain and domain not in _PERSONAL_EMAIL_DOMAINS:
                accounts_by_domain.setdefault(domain, set()).add(account.account_id)

    matched: dict[str, set[str]] = {
        domain: accounts_by_domain[domain]
        for domain in attendee_domains
        if domain in accounts_by_domain
    }
    candidate_ids = tuple(sorted({account_id for ids in matched.values() for account_id in ids}))
    matched_domains = tuple(sorted(matched))
    if len(candidate_ids) == 1:
        account = crm.get_account(candidate_ids[0])
        return CalendarAccountDomainResolution(
            state="exactly_one",
            account_id=candidate_ids[0],
            account_name=account.name if account is not None else None,
            matched_domains=matched_domains,
            attendee_emails=attendee_emails,
            candidate_account_ids=candidate_ids,
            reason="Calendar attendee domain matched exactly one Salesforce account Contact domain.",
        )
    if len(candidate_ids) > 1:
        return CalendarAccountDomainResolution(
            state="ambiguous",
            account_id=None,
            account_name=None,
            matched_domains=matched_domains,
            attendee_emails=attendee_emails,
            candidate_account_ids=candidate_ids,
            reason="Calendar attendee domains matched multiple Salesforce accounts; no account was selected.",
        )
    return CalendarAccountDomainResolution(
        state="none",
        account_id=None,
        account_name=None,
        matched_domains=(),
        attendee_emails=attendee_emails,
        candidate_account_ids=(),
        reason="Calendar attendee domains did not match Salesforce Contact domains.",
    )


def _calendar_attendance(
    calendar_provider: GoogleCalendarEventsProvider | None,
    account_id: str,
    *,
    opportunity_id: str,
    until: str,
) -> tuple[CalendarAttendance, ...]:
    if calendar_provider is None:
        return ()
    events = calendar_provider.list_events(account_id, opportunity_id=opportunity_id, until=until)
    rows: list[CalendarAttendance] = []
    for item in events.get("items", ()):
        event_id = str(item.get("id") or "")
        start_at = str((item.get("start") or {}).get("dateTime") or "")
        if until and start_at and start_at[:10] > until[:10]:
            continue
        for attendee in item.get("attendees") or ():
            email = str(attendee.get("email") or "").strip().lower()
            if not email:
                continue
            rows.append(CalendarAttendance(
                event_id=event_id,
                summary=str(item.get("summary") or ""),
                attendee_email=email,
                response_status=str(attendee.get("responseStatus") or "unknown"),
                start_at=start_at,
                status=str(item.get("status") or "unknown"),
            ))
    return tuple(rows)


def _calendar_attendee_emails(events: dict[str, Any]) -> tuple[str, ...]:
    emails: list[str] = []
    for item in events.get("items", ()):
        if str(item.get("status") or "unknown") == "cancelled":
            continue
        for attendee in item.get("attendees") or ():
            if str(attendee.get("responseStatus") or "unknown") == "declined":
                continue
            email = str(attendee.get("email") or "").strip().lower()
            if email and "@" in email:
                emails.append(email)
    return tuple(sorted(set(emails)))


def _tokens(*values: str) -> tuple[str, ...]:
    tokens: list[str] = []
    for value in values:
        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized:
            tokens.append(normalized)
    return tuple(tokens)


def _contains_any(tokens: tuple[str, ...], needles: tuple[str, ...]) -> bool:
    return any(needle in token for token in tokens for needle in needles)


def _matching_entitlement_ids(
    entitlements: tuple[Entitlement, ...],
    needles: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        f"{entitlement.account_id}:{entitlement.capability}"
        for entitlement in entitlements
        if _contains_any(_tokens(entitlement.capability), needles)
    )


def _email_domain(email: str) -> str | None:
    parts = email.strip().lower().rsplit("@", 1)
    if len(parts) != 2 or not parts[0] or "." not in parts[1]:
        return None
    return parts[1]


def _list_stakeholders(
    data_plane: CustomerDataPlane,
    account_id: str,
) -> tuple[StakeholderRelationship, ...]:
    reader = getattr(data_plane.crm, "list_stakeholders", None)
    if reader is None:
        return ()
    return tuple(reader(account_id))


def _selected_kickoff_contact(
    contacts: tuple[CRMContact, ...],
    stakeholder_rows: tuple[StakeholderVerification, ...],
) -> CRMContact | None:
    consented = {contact.contact_id: contact for contact in contacts if contact.consent_to_contact}
    for row in stakeholder_rows:
        if row.relationship_role == "champion" and row.crm_contact_id in consented:
            return consented[row.crm_contact_id]
    for row in stakeholder_rows:
        if row.verification_state == "declared_and_observed" and row.crm_contact_id in consented:
            return consented[row.crm_contact_id]
    return next(iter(consented.values()), None)


def _owner_name(contacts: tuple[CRMContact, ...]) -> str | None:
    contact = next((item for item in contacts if item.consent_to_contact), None)
    return contact.name if contact else None


def _normalize_stage(value: str) -> str:
    return value.strip().lower().replace("-", " ")
