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

from ultra_csm.data_plane.contracts import (
    CRMAccount,
    CRMContact,
    CRMOpportunity,
    CustomerDataPlane,
    Entitlement,
    EvidenceRef,
    StakeholderRelationship,
)
from ultra_csm.governance import ActionGate, ActionProposal, proposal_fields_for


ENTERPRISE_AMOUNT_CENTS = 10_000_000

LaunchStatus = Literal["ready", "needs_data", "ignored"]
SourceAuthority = Literal[
    "customer_direct",
    "customer_observed",
    "commercial_record",
    "internal_structured",
    "internal_unstructured",
    "inferred",
]


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
class OnboardingMilestone:
    milestone: str
    owner: str
    target_date: str
    acceptance_criteria: str
    source_ids: tuple[str, ...]


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
    stakeholder_verification: tuple[StakeholderVerification, ...]
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
        stakeholders=stakeholders,
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
    ready = not coverage.missing_required_sources
    success_plan = _success_plan_v0(
        as_of=as_of,
        account=account,
        opportunity=opportunity,
        contacts=contacts,
        entitlements=entitlements,
        onboarding_projects=onboarding_projects,
        success_plans=success_plans,
    ) if ready else ()
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
        stakeholder_verification=stakeholder_rows,
        success_plan_v0=success_plan,
        risks=risks,
        recommended_next_action=(
            "Review and approve the kickoff draft plus success-plan v0."
            if ready
            else "Complete missing onboarding evidence before customer-facing activity."
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
    success_plans: tuple,
    onboarding_projects: tuple,
    onboarding_phases: tuple,
    onboarding_tasks: tuple,
    customer_comms: tuple,
    call_or_meeting_comms: tuple,
    calendar_attendance: tuple[CalendarAttendance, ...],
    internal_notes: tuple,
    usage_signals: tuple,
    stakeholders: tuple[StakeholderRelationship, ...],
) -> SourceCoverage:
    baseline = ["salesforce_opportunity", "salesforce_account"]
    if contacts:
        baseline.append("salesforce_contacts")
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
    success_plans: tuple,
    customer_comms: tuple,
    call_or_meeting_comms: tuple,
    calendar_attendance: tuple[CalendarAttendance, ...],
    internal_notes: tuple,
    onboarding_projects: tuple,
    onboarding_phases: tuple,
    onboarding_tasks: tuple,
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
    return tuple(receipts)


def _stakeholder_verification(
    *,
    contacts: tuple[CRMContact, ...],
    stakeholders: tuple[StakeholderRelationship, ...],
    customer_comms: tuple,
    call_or_meeting_comms: tuple,
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


def _success_plan_v0(
    *,
    as_of: str,
    account: CRMAccount,
    opportunity: CRMOpportunity,
    contacts: tuple[CRMContact, ...],
    entitlements: tuple[Entitlement, ...],
    onboarding_projects: tuple,
    success_plans: tuple,
) -> tuple[OnboardingMilestone, ...]:
    owner = _owner_name(contacts) or account.owner_id
    source_ids = (opportunity.opportunity_id, *(f"{e.account_id}:{e.capability}" for e in entitlements[:3]))
    kickoff_date = as_of
    first_capability = entitlements[0].capability.replace("_", " ") if entitlements else "purchased workflow"
    return (
        OnboardingMilestone(
            "Internal AE-to-CS handoff complete",
            account.owner_id,
            kickoff_date,
            "CSM can name customer goal, first-value definition, stakeholders, and implementation dependencies.",
            (opportunity.opportunity_id,),
        ),
        OnboardingMilestone(
            "Customer kickoff scheduled",
            owner,
            kickoff_date,
            "Kickoff invite includes verified champion, admin or technical owner, and executive sponsor if known.",
            source_ids,
        ),
        OnboardingMilestone(
            "Entitlements and workspace provisioned",
            account.owner_id,
            opportunity.close_date,
            "Purchased package is enabled and admin can access the workspace.",
            source_ids,
        ),
        OnboardingMilestone(
            "First value event achieved",
            owner,
            opportunity.close_date,
            f"Customer completes first {first_capability} workflow tied to the closed-won use case.",
            source_ids,
        ),
        OnboardingMilestone(
            "Executive checkpoint completed",
            account.owner_id,
            opportunity.close_date,
            "CSM confirms value progress, blockers, and next adoption motion with sponsor or buyer.",
            (opportunity.opportunity_id,),
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
        stakeholder_verification=(),
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
