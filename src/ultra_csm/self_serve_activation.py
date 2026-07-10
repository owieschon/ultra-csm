"""Product-led self-serve activation workflow.

Workflow 1b is deliberately path-first: the agent must define the user's path
to value before it judges whether first value happened. Product signals select
the path, all available customer sources ground the current state, and
customer-affecting work stays behind ActionGate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Literal

from ultra_csm.data_plane.contracts import (
    CRMAccount,
    CRMContact,
    CustomerDataPlane,
    UsageSignal,
)
from ultra_csm.governance import ActionGate, ActionProposal, proposal_fields_for
from ultra_csm.workflow_core import (
    WorkflowDecisionTrace,
    WorkflowExecutionEnvelope,
    WorkflowOutputContract,
    WorkflowValidationResult,
    build_evidence_bundle,
    build_execution_envelope,
)
from ultra_csm.workflow_playbooks import (
    SELF_SERVE_SIGNUP_ACTIVATION,
    evaluate_source_coverage,
    workflow_packet_metadata,
)


PacketStatus = Literal["ready", "needs_data", "internal_only", "ignored"]
MilestoneStatus = Literal["completed", "current", "blocked", "stale", "not_started"]
CompletionOperator = Literal["any", "all"]
VALUE_PATH_CONFIG_VERSION = SELF_SERVE_SIGNUP_ACTIVATION.config_version

PERSONAL_EMAIL_DOMAINS = {
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
}

ACTION_TRIGGERS: dict[str, str] = {
    "send_activation_nudge": "workspace_created_without_first_value",
    "send_invite_followup": "invites_sent_without_activation",
    "recommend_next_feature": "first_value_reached_with_feature_depth_gap",
    "surface_in_app_checklist": "setup_incomplete_active_user",
    "route_to_scaled_csm_review": "persistent_activation_friction",
    "route_to_sales_assisted_expansion": "enterprise_only_crm_interest",
    "offer_enterprise_crm_path": "crm_connection_interest_on_self_serve",
    "suppress_customer_action": "personal_email_or_no_consent_or_recent_nudge_or_missing_telemetry",
    "internal_only_packet": "strong_signal_but_unsafe_customer_action",
}


@dataclass(frozen=True)
class SelfServeSignupEvent:
    tenant_id: str
    workspace_id: str
    signup_email: str
    observed_at: str
    account_id: str | None = None
    plan: str | None = None
    source: str = "product_signup"


@dataclass(frozen=True)
class SelfServeSourceReceipt:
    source_id: str
    source_type: str
    field: str
    observed_at: str
    claim: str
    customer_safe: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SelfServeIdentityResolution:
    state: Literal["exactly_one", "ambiguous", "none"]
    account_id: str | None
    account_name: str | None
    matched_domains: tuple[str, ...]
    reason: str
    personal_email_domain: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SelfServeCoverage:
    reviewed_sources: tuple[str, ...]
    missing_required_sources: tuple[str, ...]
    customer_output_blockers: tuple[str, ...]
    source_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SelfServeValuePathMilestone:
    milestone_id: str
    label: str
    completion_rule: str
    required_signals: tuple[str, ...]
    completion_operator: CompletionOperator
    min_signal_value: float
    min_signal_occurrences: int
    target_day: int
    customer_safe_interpretation: str
    allowed_actions_if_incomplete: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SelfServeMilestoneProgress:
    milestone_id: str
    label: str
    status: MilestoneStatus
    completed_at: str | None
    evidence_source_ids: tuple[str, ...]
    customer_safe_interpretation: str
    allowed_actions_if_incomplete: tuple[str, ...]
    suppression_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SelfServePathHypothesis:
    path_id: str
    archetype: str
    score: float
    evidence_source_ids: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SelfServeValuePath:
    config_version: str
    path_id: str
    archetype: str
    first_value_definition: str
    first_value_milestone_id: str
    selection_rule: str
    selection_reason: str
    selection_evidence_ids: tuple[str, ...]
    secondary_hypotheses: tuple[SelfServePathHypothesis, ...]
    milestones: tuple[SelfServeMilestoneProgress, ...]
    current_milestone_id: str | None
    completed_milestone_ids: tuple[str, ...]
    blocked_milestone_ids: tuple[str, ...]
    next_best_milestone_id: str | None
    first_value_reached: bool
    enterprise_interest_signals: tuple[str, ...]
    confidence: float
    open_questions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SelfServeRecommendedAction:
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
class SelfServeProposalRef:
    proposal_id: str
    action_type: str
    status: str
    autonomy_tier: int
    required_permission: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SelfServeActivationPacket:
    workflow_id: str
    workflow_config_version: str
    execution_envelope: WorkflowExecutionEnvelope
    packet_id: str
    tenant_id: str
    status: PacketStatus
    account_id: str
    account_name: str
    workspace_id: str
    signup_email: str
    generated_at: str
    trigger_receipt: SelfServeSourceReceipt
    identity_resolution: SelfServeIdentityResolution
    coverage: SelfServeCoverage
    value_path: SelfServeValuePath
    recommended_action: SelfServeRecommendedAction
    customer_language: str | None
    risks: tuple[str, ...]
    source_receipts: tuple[SelfServeSourceReceipt, ...]
    proposals: tuple[SelfServeProposalRef, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "workflow": workflow_packet_metadata(SELF_SERVE_SIGNUP_ACTIVATION),
            "workflow_id": self.workflow_id,
            "workflow_config_version": self.workflow_config_version,
            "execution_envelope": self.execution_envelope.to_dict(),
            "tenant_id": self.tenant_id,
            "status": self.status,
            "account_id": self.account_id,
            "account_name": self.account_name,
            "workspace_id": self.workspace_id,
            "signup_email": self.signup_email,
            "generated_at": self.generated_at,
            "trigger_receipt": self.trigger_receipt.to_dict(),
            "identity_resolution": self.identity_resolution.to_dict(),
            "coverage": self.coverage.to_dict(),
            "value_path": self.value_path.to_dict(),
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
    opportunities: tuple[Any, ...]
    company: Any | None
    health_score: Any | None
    success_plans: tuple[Any, ...]
    adoption_summary: Any | None
    entitlements: tuple[Any, ...]
    usage_signals: tuple[UsageSignal, ...]
    ttv_milestones: tuple[Any, ...]
    gmail_signals: tuple[Any, ...]
    call_signals: tuple[Any, ...]
    internal_notes: tuple[Any, ...]


@dataclass(frozen=True)
class _PathDefinition:
    path_id: str
    archetype: str
    first_value_definition: str
    first_value_milestone_id: str
    selection_metrics: tuple[str, ...]
    selection_reason: str
    milestones: tuple[SelfServeValuePathMilestone, ...]


def run_self_serve_signup_activation(
    *,
    data_plane: CustomerDataPlane,
    gate: ActionGate | None,
    event: SelfServeSignupEvent,
    as_of: str,
) -> SelfServeActivationPacket:
    identity = resolve_self_serve_account_identity(data_plane.crm, event)
    account_id = identity.account_id or event.account_id or event.workspace_id
    evidence = _gather_account_evidence(data_plane, account_id)
    account = evidence.account or CRMAccount(
        account_id=account_id,
        name=identity.account_name or _workspace_name_from_email(event.signup_email),
        owner_id="self-serve",
        industry=None,
    )
    receipts = _build_source_receipts(event, account, evidence)
    trigger_receipt = SelfServeSourceReceipt(
        source_id=f"self-serve-signup:{event.workspace_id}:{event.observed_at}",
        source_type=event.source,
        field="signup_email",
        observed_at=event.observed_at,
        claim=f"{event.signup_email} created or activated workspace {event.workspace_id}.",
        customer_safe=True,
    )
    receipts = (trigger_receipt, *receipts)
    coverage = _coverage(identity, evidence, receipts)
    path = _build_value_path(event, evidence, receipts, as_of=as_of)
    action = _recommended_action(event, identity, evidence, path, coverage)
    customer_language = _customer_language(action, path, identity)
    status = _packet_status(coverage, action)
    risks = _risks(identity, coverage, path, action)
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
        f"self-serve-activation:{event.workspace_id}:"
        f"{_compact_timestamp(event.observed_at)}"
    )
    envelope = _execution_envelope(
        event=event,
        identity=identity,
        coverage=coverage,
        path=path,
        action=action,
        receipts=receipts,
        proposals=proposals,
        status=status,
    )
    return SelfServeActivationPacket(
        workflow_id=SELF_SERVE_SIGNUP_ACTIVATION.workflow_id,
        workflow_config_version=SELF_SERVE_SIGNUP_ACTIVATION.config_version,
        execution_envelope=envelope,
        packet_id=packet_id,
        tenant_id=event.tenant_id,
        status=status,
        account_id=account.account_id,
        account_name=account.name,
        workspace_id=event.workspace_id,
        signup_email=event.signup_email,
        generated_at=_generated_at(as_of),
        trigger_receipt=trigger_receipt,
        identity_resolution=identity,
        coverage=coverage,
        value_path=path,
        recommended_action=action,
        customer_language=customer_language,
        risks=risks,
        source_receipts=receipts,
        proposals=proposals,
    )


def resolve_self_serve_account_identity(crm, event: SelfServeSignupEvent) -> SelfServeIdentityResolution:
    domain = _email_domain(event.signup_email)
    personal = domain in PERSONAL_EMAIL_DOMAINS
    if event.account_id:
        account = crm.get_account(event.account_id)
        return SelfServeIdentityResolution(
            state="exactly_one" if account else "none",
            account_id=event.account_id if account else None,
            account_name=account.name if account else None,
            matched_domains=(domain,) if domain else (),
            reason="trigger_account_id" if account else "trigger_account_id_not_found",
            personal_email_domain=personal,
        )

    exact = crm.resolve_account_by_email(event.signup_email)
    if exact.state == "exactly_one":
        account = crm.get_account(exact.account_id or "")
        return SelfServeIdentityResolution(
            state="exactly_one",
            account_id=exact.account_id,
            account_name=account.name if account else None,
            matched_domains=(domain,) if domain else (),
            reason="salesforce_contact_email_match",
            personal_email_domain=personal,
        )
    if exact.state == "ambiguous":
        return SelfServeIdentityResolution(
            state="ambiguous",
            account_id=None,
            account_name=None,
            matched_domains=(domain,) if domain else (),
            reason="salesforce_contact_email_ambiguous",
            personal_email_domain=personal,
        )
    if not domain or personal:
        return SelfServeIdentityResolution(
            state="none",
            account_id=None,
            account_name=None,
            matched_domains=(domain,) if domain else (),
            reason="personal_email_domain_no_org_inference" if personal else "missing_email_domain",
            personal_email_domain=personal,
        )

    candidates: set[str] = set()
    for account in crm.list_accounts(tenant_id=event.tenant_id):
        for contact in crm.list_contacts(account.account_id):
            if _email_domain(contact.email) == domain:
                candidates.add(account.account_id)
    if len(candidates) == 1:
        account_id = next(iter(candidates))
        account = crm.get_account(account_id)
        return SelfServeIdentityResolution(
            state="exactly_one",
            account_id=account_id,
            account_name=account.name if account else None,
            matched_domains=(domain,),
            reason="salesforce_contact_domain_match",
            personal_email_domain=False,
        )
    if len(candidates) > 1:
        return SelfServeIdentityResolution(
            state="ambiguous",
            account_id=None,
            account_name=None,
            matched_domains=(domain,),
            reason="salesforce_contact_domain_ambiguous",
            personal_email_domain=False,
        )
    return SelfServeIdentityResolution(
        state="none",
        account_id=None,
        account_name=None,
        matched_domains=(domain,),
        reason="no_salesforce_domain_match",
        personal_email_domain=False,
    )


def _gather_account_evidence(data_plane: CustomerDataPlane, account_id: str) -> _AccountEvidence:
    comms = data_plane.comms
    return _AccountEvidence(
        account=data_plane.crm.get_account(account_id),
        contacts=tuple(data_plane.crm.list_contacts(account_id)),
        cases=tuple(data_plane.crm.list_cases(account_id)),
        opportunities=tuple(data_plane.crm.list_opportunities(account_id)),
        company=data_plane.cs.get_company(account_id),
        health_score=data_plane.cs.get_health_score(account_id),
        success_plans=tuple(data_plane.cs.list_success_plans(account_id)),
        adoption_summary=data_plane.cs.get_adoption_summary(account_id),
        entitlements=tuple(data_plane.telemetry.list_entitlements(account_id)),
        usage_signals=tuple(data_plane.telemetry.list_usage_signals(account_id)),
        ttv_milestones=tuple(data_plane.telemetry.list_ttv_milestones(account_id)),
        gmail_signals=tuple(comms.list_gmail_signals(account_id)) if comms else (),
        call_signals=tuple(comms.list_call_transcript_signals(account_id)) if comms else (),
        internal_notes=tuple(comms.list_internal_notes(account_id)) if comms else (),
    )


def _build_source_receipts(
    event: SelfServeSignupEvent,
    account: CRMAccount,
    evidence: _AccountEvidence,
) -> tuple[SelfServeSourceReceipt, ...]:
    receipts: list[SelfServeSourceReceipt] = [
        SelfServeSourceReceipt(
            account.account_id,
            "salesforce_account",
            "account_id",
            event.observed_at,
            f"Workspace is associated with {account.name}.",
            True,
        )
    ]
    receipts.extend(
        SelfServeSourceReceipt(
            contact.contact_id,
            "salesforce_contact",
            "email",
            event.observed_at,
            f"{contact.email} is a known customer contact.",
            True,
        )
        for contact in evidence.contacts
    )
    receipts.extend(
        SelfServeSourceReceipt(
            case.case_id,
            "salesforce_case",
            "status",
            case.created_at,
            f"Support case '{case.subject}' is {case.status}.",
            True,
        )
        for case in evidence.cases
    )
    receipts.extend(
        SelfServeSourceReceipt(
            opp.opportunity_id,
            "salesforce_opportunity",
            "stage_name",
            opp.close_date,
            f"Related opportunity is {opp.stage_name}.",
            False,
        )
        for opp in evidence.opportunities
    )
    if evidence.company is not None:
        receipts.append(SelfServeSourceReceipt(
            evidence.company.company_id,
            "cs_company",
            "lifecycle_stage",
            event.observed_at,
            f"CS lifecycle stage is {evidence.company.lifecycle_stage}.",
            True,
        ))
    if evidence.health_score is not None:
        receipts.append(SelfServeSourceReceipt(
            evidence.health_score.account_id,
            "health_score",
            "score",
            evidence.health_score.measured_at,
            f"Health score is {evidence.health_score.score}.",
            False,
        ))
    if evidence.adoption_summary is not None:
        receipts.append(SelfServeSourceReceipt(
            evidence.adoption_summary.account_id,
            "adoption_summary",
            "active_users",
            evidence.adoption_summary.measured_at,
            (
                f"{evidence.adoption_summary.active_users}/"
                f"{evidence.adoption_summary.licensed_users} users active."
            ),
            True,
        ))
    receipts.extend(
        SelfServeSourceReceipt(
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
        SelfServeSourceReceipt(
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
        SelfServeSourceReceipt(
            f"ttv:{milestone.account_id}:{milestone.milestone}",
            "time_to_value_milestone",
            "achieved_at",
            milestone.achieved_at or milestone.expected_by,
            f"Existing TTV milestone {milestone.milestone}.",
            True,
        )
        for milestone in evidence.ttv_milestones
    )
    receipts.extend(
        SelfServeSourceReceipt(
            signal.signal_id,
            "customer_email",
            "timestamp",
            signal.timestamp,
            f"Customer-facing email signal {signal.direction}.",
            False,
        )
        for signal in evidence.gmail_signals
    )
    receipts.extend(
        SelfServeSourceReceipt(
            signal.signal_id,
            "call_transcript",
            "timestamp",
            signal.timestamp,
            f"Customer call/meeting signal {signal.direction}.",
            False,
        )
        for signal in evidence.call_signals
    )
    receipts.extend(
        SelfServeSourceReceipt(
            note.note_id,
            "internal_slack_or_note",
            "content",
            note.timestamp,
            f"Internal {note.source} note reviewed.",
            False,
        )
        for note in evidence.internal_notes
    )
    return tuple(receipts)


def _coverage(
    identity: SelfServeIdentityResolution,
    evidence: _AccountEvidence,
    receipts: tuple[SelfServeSourceReceipt, ...],
) -> SelfServeCoverage:
    counts: dict[str, int] = {}
    for receipt in receipts:
        counts[receipt.source_type] = counts.get(receipt.source_type, 0) + 1
    reviewed = tuple(sorted(counts))
    normalized_source_list = list(reviewed)
    if identity.state == "exactly_one":
        normalized_source_list.append("resolved_organization")
    if evidence.contacts:
        normalized_source_list.append("contact_record")
    normalized_reviewed = tuple(dict.fromkeys(normalized_source_list))
    shared = evaluate_source_coverage(
        SELF_SERVE_SIGNUP_ACTIVATION,
        reviewed_sources=normalized_reviewed,
    )
    missing: list[str] = []
    blockers: list[str] = []
    missing.extend(shared.missing_required_sources)
    blockers.extend(shared.customer_output_blockers)
    if identity.state != "exactly_one":
        blockers.append("organization_identity_not_exactly_one")
    if not evidence.usage_signals:
        blockers.append("product_telemetry_required_for_activation_judgment")
    if not evidence.contacts:
        blockers.append("contact_record_missing")
    consent_contact = _preferred_contact(evidence.contacts)
    if consent_contact is None:
        blockers.append("no_consented_contact_for_customer_outreach")
    if identity.personal_email_domain:
        blockers.append("personal_email_domain_suppresses_org_outreach")
    return SelfServeCoverage(
        reviewed_sources=normalized_reviewed,
        missing_required_sources=tuple(dict.fromkeys(missing)),
        customer_output_blockers=tuple(dict.fromkeys(blockers)),
        source_counts=counts,
    )


def _build_value_path(
    event: SelfServeSignupEvent,
    evidence: _AccountEvidence,
    receipts: tuple[SelfServeSourceReceipt, ...],
    *,
    as_of: str,
) -> SelfServeValuePath:
    hypotheses = _rank_path_hypotheses(evidence, receipts)
    primary = hypotheses[0]
    path_def = _path_definitions()[primary.path_id]
    selected_ids = primary.evidence_source_ids
    by_metric: dict[str, list[UsageSignal]] = {}
    for signal in evidence.usage_signals:
        by_metric.setdefault(signal.metric_name, []).append(signal)
    progress: list[SelfServeMilestoneProgress] = []
    first_incomplete: SelfServeValuePathMilestone | None = None
    for milestone in path_def.milestones:
        matching, completed = _matching_milestone_signals(milestone, by_metric)
        overdue = _days_between(event.observed_at, as_of) > milestone.target_day
        status: MilestoneStatus
        if completed:
            status = "completed"
        elif first_incomplete is None:
            status = "stale" if overdue else "current"
            first_incomplete = milestone
        else:
            status = "not_started"
        suppression = ()
        if status == "stale":
            suppression = ("milestone_past_target_window",)
        progress.append(SelfServeMilestoneProgress(
            milestone_id=milestone.milestone_id,
            label=milestone.label,
            status=status,
            completed_at=max((signal.observed_at for signal in matching), default=None),
            evidence_source_ids=tuple(signal.signal_id for signal in matching),
            customer_safe_interpretation=milestone.customer_safe_interpretation,
            allowed_actions_if_incomplete=milestone.allowed_actions_if_incomplete,
            suppression_reasons=suppression,
        ))
    completed_ids = tuple(item.milestone_id for item in progress if item.status == "completed")
    blocked_ids = tuple(item.milestone_id for item in progress if item.status in {"blocked", "stale"})
    current = next((item for item in progress if item.status in {"current", "stale"}), None)
    enterprise_interest = tuple(
        signal.signal_id
        for signal in evidence.usage_signals
        if signal.metric_name in {
            "crm_integration_viewed",
            "crm_connect_clicked",
            "crm_connection_requested",
            "integration_boundary_hit",
            "enterprise_plan_viewed",
        }
        and signal.value > 0
    )
    confidence = _path_confidence(progress, evidence)
    open_questions = _open_questions(evidence, path_def.path_id)
    first_value_reached = any(
        item.milestone_id == path_def.first_value_milestone_id
        and item.status == "completed"
        for item in progress
    )
    return SelfServeValuePath(
        config_version=VALUE_PATH_CONFIG_VERSION,
        path_id=path_def.path_id,
        archetype=path_def.archetype,
        first_value_definition=path_def.first_value_definition,
        first_value_milestone_id=path_def.first_value_milestone_id,
        selection_rule="rank paths by source-backed metric fit; preserve non-primary hypotheses for review",
        selection_reason=primary.reason,
        selection_evidence_ids=selected_ids,
        secondary_hypotheses=tuple(hypotheses[1:4]),
        milestones=tuple(progress),
        current_milestone_id=current.milestone_id if current else None,
        completed_milestone_ids=completed_ids,
        blocked_milestone_ids=blocked_ids,
        next_best_milestone_id=current.milestone_id if current else None,
        first_value_reached=first_value_reached,
        enterprise_interest_signals=enterprise_interest,
        confidence=confidence,
        open_questions=open_questions,
    )


def _matching_milestone_signals(
    milestone: SelfServeValuePathMilestone,
    by_metric: dict[str, list[UsageSignal]],
) -> tuple[list[UsageSignal], bool]:
    per_metric: dict[str, list[UsageSignal]] = {}
    matching: list[UsageSignal] = []
    for metric in milestone.required_signals:
        accepted = [
            signal for signal in by_metric.get(metric, ())
            if signal.value >= milestone.min_signal_value
        ]
        if accepted:
            per_metric[metric] = accepted
            matching.extend(accepted)
    enough_occurrences = len(matching) >= milestone.min_signal_occurrences
    if milestone.completion_operator == "all":
        completed = all(metric in per_metric for metric in milestone.required_signals) and enough_occurrences
    else:
        completed = bool(per_metric) and enough_occurrences
    return matching, completed


def _rank_path_hypotheses(
    evidence: _AccountEvidence,
    receipts: tuple[SelfServeSourceReceipt, ...],
) -> tuple[SelfServePathHypothesis, ...]:
    signal_ids_by_metric: dict[str, tuple[str, ...]] = {}
    for signal in evidence.usage_signals:
        if signal.value > 0:
            signal_ids_by_metric.setdefault(signal.metric_name, ())
            signal_ids_by_metric[signal.metric_name] = (
                *signal_ids_by_metric[signal.metric_name],
                signal.signal_id,
            )
    hypotheses: list[SelfServePathHypothesis] = []
    for definition in _path_definitions().values():
        evidence_ids = tuple(
            source_id
            for metric in definition.selection_metrics
            for source_id in signal_ids_by_metric.get(metric, ())
        )
        score = float(len(evidence_ids))
        if definition.path_id == "support_friction_signup":
            case_ids = tuple(
                receipt.source_id for receipt in receipts
                if receipt.source_type == "salesforce_case"
            )
            evidence_ids = (*evidence_ids, *case_ids)
            score += len(case_ids) * 0.75
        if definition.path_id == "crm_enterprise_curious" and evidence_ids:
            score += 0.5
        if definition.path_id == "team_workspace_creator" and evidence.adoption_summary is not None:
            score += 0.25
        if evidence_ids:
            hypotheses.append(SelfServePathHypothesis(
                path_id=definition.path_id,
                archetype=definition.archetype,
                score=round(score, 2),
                evidence_source_ids=tuple(dict.fromkeys(evidence_ids)),
                reason=definition.selection_reason,
            ))
    if not hypotheses:
        definition = _path_definitions()["solo_evaluator"]
        fallback_ids = tuple(
            signal_ids_by_metric[m][0]
            for m in ("workspace_created", "profile_completed", "first_search_run", "insight_viewed")
            if m in signal_ids_by_metric
        )
        hypotheses.append(SelfServePathHypothesis(
            path_id=definition.path_id,
            archetype=definition.archetype,
            score=0.1 if fallback_ids else 0.0,
            evidence_source_ids=fallback_ids,
            reason="No stronger path evidence was present; default to individual evaluation until telemetry narrows the path.",
        ))
    return tuple(sorted(hypotheses, key=lambda item: (-item.score, item.path_id)))


def _path_definitions() -> dict[str, _PathDefinition]:
    return {
        "solo_evaluator": _PathDefinition(
            "solo_evaluator",
            "Solo evaluator",
            "The user reaches first value when they complete setup and produce one saved or reusable insight.",
            "first_value",
            ("workspace_created", "profile_completed", "context_added", "saved_view_created", "insight_saved", "first_search_run", "insight_viewed"),
            "Individual setup and exploration signals indicate a solo evaluation path.",
            (
                _milestone("signup", "Workspace created", ("workspace_created",), 0, "Your workspace is active.", ("surface_in_app_checklist",)),
                _milestone("setup", "Profile and context completed", ("profile_completed", "context_added"), 1, "Your workspace has enough context to personalize the experience.", ("surface_in_app_checklist",)),
                _milestone("first_value", "First useful insight saved", ("saved_view_created", "insight_saved", "first_search_run"), 3, "You have produced a reusable insight.", ("send_activation_nudge", "content_route")),
                _milestone("habit", "Returned to use the result", ("return_session", "insight_viewed"), 7, "You came back to use the work again.", ("recommend_next_feature",), min_occurrences=2),
            ),
        ),
        "team_workspace_creator": _PathDefinition(
            "team_workspace_creator",
            "Team workspace creator",
            "The user reaches first value when at least one teammate activates and shared work exists.",
            "first_value",
            ("team_workspace_created", "invite_sent", "invited_user_activated", "shared_workflow_created", "weekly_active_team_members"),
            "Team creation and invite behavior indicate the user is trying to create shared value.",
            (
                _milestone("signup", "Workspace created", ("workspace_created", "team_workspace_created"), 0, "Your team workspace is active.", ("surface_in_app_checklist",)),
                _milestone("invite", "Teammates invited", ("invite_sent",), 2, "A teammate has been invited into the workspace.", ("send_invite_followup",)),
                _milestone("first_value", "Teammate activated or shared workflow used", ("invited_user_activated", "shared_workflow_created"), 5, "At least one teammate has started participating.", ("send_invite_followup", "content_route")),
                _milestone("depth", "Shared workflow repeats", ("shared_workflow_run", "weekly_active_team_members"), 10, "The team is using a repeated shared workflow.", ("recommend_next_feature",), min_occurrences=2),
            ),
        ),
        "integration_led_evaluator": _PathDefinition(
            "integration_led_evaluator",
            "Integration-led evaluator",
            "The user reaches first value when a non-enterprise integration syncs data and powers one workflow.",
            "first_value",
            ("integration_catalog_viewed", "integration_connected", "sync_succeeded", "workflow_run", "synced_record_used"),
            "Integration setup behavior indicates the user is trying to unlock connected-system value.",
            (
                _milestone("signup", "Workspace created", ("workspace_created",), 0, "Your workspace is active.", ("surface_in_app_checklist",)),
                _milestone("integration_selected", "Integration selected", ("integration_catalog_viewed",), 2, "You found a connected-system path to try.", ("content_route",)),
                _milestone("first_value", "Data synced into a workflow", ("integration_connected", "sync_succeeded"), 5, "Connected data is available in the workspace.", ("send_activation_nudge", "content_route"), operator="all", min_occurrences=2),
                _milestone("workflow", "Synced data used in workflow", ("workflow_run", "synced_record_used"), 8, "Connected data has been used in actual work.", ("recommend_next_feature",)),
            ),
        ),
        "crm_enterprise_curious": _PathDefinition(
            "crm_enterprise_curious",
            "CRM-enterprise curious evaluator",
            "The user reaches first value when they clarify the enterprise CRM path or invite a stakeholder who can sponsor it.",
            "first_value",
            ("crm_integration_viewed", "crm_connect_clicked", "crm_connection_requested", "integration_boundary_hit", "enterprise_plan_viewed", "stakeholder_invited", "champion_invited"),
            "CRM interest was observed in self-serve telemetry; CRM remains an enterprise-only connection, so the path treats this as expansion interest.",
            (
                _milestone("signup", "Workspace created", ("workspace_created",), 0, "Your workspace is active.", ("surface_in_app_checklist",)),
                _milestone("crm_interest", "CRM interest observed", ("crm_integration_viewed", "crm_connect_clicked", "crm_connection_requested"), 2, "You explored CRM connectivity.", ("offer_enterprise_crm_path", "content_route")),
                _milestone("first_value", "Enterprise path or champion identified", ("enterprise_plan_viewed", "stakeholder_invited", "champion_invited"), 7, "A path to evaluate CRM with the right stakeholder is visible.", ("route_to_sales_assisted_expansion",)),
                _milestone("next_step", "Sales-assisted next step accepted", ("enterprise_intro_requested", "demo_requested"), 14, "Your team has asked to explore the enterprise path.", ("route_to_sales_assisted_expansion",)),
            ),
        ),
        "workflow_automation_evaluator": _PathDefinition(
            "workflow_automation_evaluator",
            "Workflow automation evaluator",
            "The user reaches first value when a workflow runs successfully on real work.",
            "first_value",
            ("workflow_created", "workflow_run", "automation_success", "repeat_workflow_run"),
            "Workflow activity indicates the user is evaluating automation value.",
            (
                _milestone("signup", "Workspace created", ("workspace_created",), 0, "Your workspace is active.", ("surface_in_app_checklist",)),
                _milestone("workflow_created", "Workflow created", ("workflow_created",), 2, "You created a workflow.", ("surface_in_app_checklist", "content_route")),
                _milestone("first_value", "Workflow completed successfully", ("workflow_run", "automation_success"), 5, "A workflow completed successfully.", ("send_activation_nudge",), operator="all", min_occurrences=2),
                _milestone("habit", "Workflow repeated", ("repeat_workflow_run",), 10, "The workflow is starting to become repeatable.", ("recommend_next_feature",), min_occurrences=2),
            ),
        ),
        "reporting_visibility_evaluator": _PathDefinition(
            "reporting_visibility_evaluator",
            "Reporting and visibility evaluator",
            "The user reaches first value when a report is created and shared or revisited.",
            "first_value",
            ("dashboard_viewed", "report_viewed", "report_created", "export_shared", "report_revisited"),
            "Reporting activity indicates the user is evaluating visibility and sharing.",
            (
                _milestone("signup", "Workspace created", ("workspace_created",), 0, "Your workspace is active.", ("surface_in_app_checklist",)),
                _milestone("report_viewed", "Dashboard or report viewed", ("dashboard_viewed", "report_viewed"), 2, "You reviewed operational visibility in the workspace.", ("content_route",)),
                _milestone("first_value", "Report created or shared", ("report_created", "export_shared"), 5, "A reusable report was created or shared.", ("send_activation_nudge", "content_route")),
                _milestone("habit", "Report revisited", ("return_session", "report_revisited"), 10, "The report was used again after creation.", ("recommend_next_feature",), min_occurrences=2),
            ),
        ),
        "support_friction_signup": _PathDefinition(
            "support_friction_signup",
            "Support-friction signup",
            "The user reaches first value when the blocker is resolved and setup resumes.",
            "first_value",
            ("support_chat_opened", "help_doc_viewed", "resolution_confirmed", "profile_completed", "workflow_created"),
            "Support or help-seeking behavior indicates activation is gated by friction.",
            (
                _milestone("signup", "Workspace created", ("workspace_created",), 0, "Your workspace is active.", ("surface_in_app_checklist",)),
                _milestone("friction", "Activation friction identified", ("support_chat_opened", "help_doc_viewed"), 1, "You asked for help during setup.", ("route_to_scaled_csm_review",)),
                _milestone("first_value", "Setup resumed after help", ("resolution_confirmed", "profile_completed", "workflow_created"), 4, "Setup moved forward after the blocker.", ("route_to_scaled_csm_review", "send_activation_nudge")),
                _milestone("habit", "Returned after resolution", ("return_session",), 8, "You returned after the blocker was resolved.", ("recommend_next_feature",)),
            ),
        ),
    }


def _milestone(
    milestone_id: str,
    label: str,
    signals: tuple[str, ...],
    target_day: int,
    interpretation: str,
    actions: tuple[str, ...],
    *,
    operator: CompletionOperator = "any",
    min_value: float = 1.0,
    min_occurrences: int = 1,
) -> SelfServeValuePathMilestone:
    return SelfServeValuePathMilestone(
        milestone_id=milestone_id,
        label=label,
        completion_rule=(
            f"complete when {operator} required signal set has at least "
            f"{min_occurrences} observation(s) with value >= {min_value:g}"
        ),
        required_signals=signals,
        completion_operator=operator,
        min_signal_value=min_value,
        min_signal_occurrences=min_occurrences,
        target_day=target_day,
        customer_safe_interpretation=interpretation,
        allowed_actions_if_incomplete=actions,
    )


def _recommended_action(
    event: SelfServeSignupEvent,
    identity: SelfServeIdentityResolution,
    evidence: _AccountEvidence,
    path: SelfServeValuePath,
    coverage: SelfServeCoverage,
) -> SelfServeRecommendedAction:
    suppression = list(coverage.customer_output_blockers)
    if _has_recent_signal(evidence, "activation_nudge_sent"):
        suppression.append("recent_activation_nudge_already_sent")
    if path.path_id == "crm_enterprise_curious":
        action_type = "route_to_sales_assisted_expansion"
        trigger = ACTION_TRIGGERS[action_type]
        label = "Route CRM interest to sales-assisted expansion review"
        message = (
            "CRM connection is available on enterprise plans. If your team wants "
            "Salesforce context in the workspace, we can help map the evaluation path."
        )
    elif path.first_value_reached:
        action_type = "recommend_next_feature"
        trigger = ACTION_TRIGGERS[action_type]
        label = "Recommend the next depth milestone"
        message = "You have reached an early value point; the next step is to deepen the workflow."
    elif path.current_milestone_id == "invite":
        action_type = "send_invite_followup"
        trigger = ACTION_TRIGGERS[action_type]
        label = "Follow up on teammate activation"
        message = "Your workspace is started; the next step is getting the invited teammate active."
    elif path.blocked_milestone_ids:
        action_type = "route_to_scaled_csm_review"
        trigger = ACTION_TRIGGERS[action_type]
        label = "Route stalled activation to scaled CSM review"
        message = "Setup appears stalled at the current value milestone."
    else:
        action_type = "send_activation_nudge"
        trigger = ACTION_TRIGGERS[action_type]
        label = "Nudge toward the next value milestone"
        message = "Your workspace is started; the next step is completing the current setup milestone."
    if event.plan and event.plan.lower() in {"enterprise", "enterprise_trial"}:
        suppression.append("self_serve_workflow_received_enterprise_plan")
    suppressed = bool(suppression) or action_type == "route_to_sales_assisted_expansion"
    if action_type == "route_to_sales_assisted_expansion":
        suppression.append("customer_outreach_requires_sales_assisted_review")
    return SelfServeRecommendedAction(
        action_type=action_type if not suppressed else "internal_only_packet",
        trigger=ACTION_TRIGGERS["internal_only_packet"] if suppressed else trigger,
        label=label,
        customer_safe_message=None if suppressed else message,
        source_ids=tuple(
            source_id
            for source_id in (
                *path.selection_evidence_ids,
                *(path.enterprise_interest_signals if path.path_id == "crm_enterprise_curious" else ()),
            )
            if source_id
        ),
        suppressed=suppressed,
        suppression_reasons=tuple(dict.fromkeys(suppression)),
    )


def _customer_language(
    action: SelfServeRecommendedAction,
    path: SelfServeValuePath,
    identity: SelfServeIdentityResolution,
) -> str | None:
    if action.suppressed:
        return None
    if path.path_id == "crm_enterprise_curious":
        return (
            "CRM connection is available on enterprise plans. If Salesforce context "
            "is important to your workflow, we can help you map the enterprise path."
        )
    if identity.personal_email_domain:
        return None
    return action.customer_safe_message


def _packet_status(coverage: SelfServeCoverage, action: SelfServeRecommendedAction) -> PacketStatus:
    if "product_telemetry" in coverage.missing_required_sources:
        return "needs_data"
    if coverage.customer_output_blockers or action.suppressed:
        return "internal_only"
    return "ready"


def _risks(
    identity: SelfServeIdentityResolution,
    coverage: SelfServeCoverage,
    path: SelfServeValuePath,
    action: SelfServeRecommendedAction,
) -> tuple[str, ...]:
    risks: list[str] = []
    if identity.state != "exactly_one":
        risks.append("organization identity is not exact")
    if path.confidence < 0.6:
        risks.append("value path confidence is low")
    risks.extend(coverage.customer_output_blockers)
    risks.extend(action.suppression_reasons)
    return tuple(dict.fromkeys(risks))


def _proposals(
    *,
    gate: ActionGate | None,
    event: SelfServeSignupEvent,
    account: CRMAccount,
    evidence: _AccountEvidence,
    action: SelfServeRecommendedAction,
    customer_language: str | None,
    receipts: tuple[SelfServeSourceReceipt, ...],
    status: PacketStatus,
) -> tuple[SelfServeProposalRef, ...]:
    if gate is None:
        return ()
    source_ids = [receipt.source_id for receipt in receipts]
    if status == "ready" and customer_language:
        contact = _preferred_contact(evidence.contacts)
        if contact is None:
            return ()
        gate.record_outreach_contact_ref(
            account_ref=account.account_id,
            contact_ref=contact.contact_id,
            email=contact.email,
            name=contact.name,
            consent=contact.consent_to_contact,
            cause_ref=f"self-serve-activation:{event.workspace_id}:contact-consent",
        )
        proposal = gate.propose(
            intent="self_serve_activation",
            payload={
                "account_id": account.account_id,
                "account_name": account.name,
                "workspace_id": event.workspace_id,
                "contact_id": contact.contact_id,
                "contact_email": contact.email,
                "trigger": action.trigger,
                "draft_channel": "email",
                "subject": "Next step for your workspace",
                "body": customer_language,
                "evidence_ids": source_ids,
            },
            grounding_ref=f"self-serve-activation:{event.workspace_id}",
            cause_ref=f"self-serve-activation:{event.workspace_id}:{event.observed_at}",
            **proposal_fields_for("draft_customer_outreach"),
        )
        return (_proposal_ref(proposal),)
    proposal = gate.propose(
        intent="self_serve_activation",
        payload={
            "account_id": account.account_id,
            "account_name": account.name,
            "workspace_id": event.workspace_id,
            "recommended_action": action.to_dict(),
            "evidence_ids": source_ids,
        },
        grounding_ref=f"self-serve-activation:{event.workspace_id}",
        cause_ref=f"self-serve-activation:{event.workspace_id}:{event.observed_at}",
        **proposal_fields_for("recommend_next_best_action"),
    )
    return (_proposal_ref(proposal),)


def _execution_envelope(
    *,
    event: SelfServeSignupEvent,
    identity: SelfServeIdentityResolution,
    coverage: SelfServeCoverage,
    path: SelfServeValuePath,
    action: SelfServeRecommendedAction,
    receipts: tuple[SelfServeSourceReceipt, ...],
    proposals: tuple[SelfServeProposalRef, ...],
    status: PacketStatus,
) -> WorkflowExecutionEnvelope:
    evidence = build_evidence_bundle(
        receipts=receipts,
        reviewed_sources=coverage.reviewed_sources,
        missing_required_sources=coverage.missing_required_sources,
        customer_output_blockers=coverage.customer_output_blockers,
    )
    decision_source_ids = tuple(
        source_id
        for source_id in (
            *path.selection_evidence_ids,
            *(
                source_id
                for milestone in path.milestones
                for source_id in milestone.evidence_source_ids
            ),
        )
        if source_id in evidence.evidence_ids()
    )
    validations = (
        WorkflowValidationResult(
            "organization_identity_exact",
            identity.state == "exactly_one",
            True,
            "Organization identity must resolve exactly for customer outreach.",
            tuple(receipt.source_id for receipt in receipts if receipt.source_type == "salesforce_account"),
        ),
        WorkflowValidationResult(
            "product_telemetry_present",
            "product_telemetry" not in coverage.missing_required_sources,
            True,
            "Telemetry is required before activation claims.",
            tuple(receipt.source_id for receipt in receipts if receipt.source_type == "product_telemetry"),
        ),
        WorkflowValidationResult(
            "first_value_not_inferred_from_count",
            path.first_value_reached
            == ("first_value" in path.completed_milestone_ids),
            True,
            "First value can only come from the configured first-value milestone.",
            decision_source_ids,
        ),
        WorkflowValidationResult(
            "secondary_hypotheses_preserved",
            bool(path.secondary_hypotheses) or path.confidence < 0.8,
            False,
            "Alternate interpretations should remain visible when confidence is not decisive.",
            tuple(
                source_id
                for hypothesis in path.secondary_hypotheses
                for source_id in hypothesis.evidence_source_ids
                if source_id in evidence.evidence_ids()
            ),
        ),
    )
    customer_affecting = any(proposal.action_type == "draft_customer_outreach" for proposal in proposals)
    proposed = next((proposal for proposal in proposals if proposal.action_type == "draft_customer_outreach"), None)
    outputs = (
        WorkflowOutputContract(
            artifact_type="activation_recommendation",
            audience="customer_facing" if customer_affecting else "csm_facing",
            action_type=action.action_type,
            customer_affecting=customer_affecting,
            gate_action="draft_customer_outreach" if customer_affecting else "recommend_next_best_action",
            status="proposed" if proposed is not None else "suppressed" if action.suppressed else "prepared",
            source_ids=tuple(
                source_id for source_id in action.source_ids if source_id in evidence.evidence_ids()
            ) or (receipts[0].source_id,),
            suppression_reasons=action.suppression_reasons,
            proposal_id=proposed.proposal_id if proposed is not None else None,
        ),
    )
    return build_execution_envelope(
        SELF_SERVE_SIGNUP_ACTIVATION,
        trigger_ref=event.workspace_id,
        idempotency_key=f"{SELF_SERVE_SIGNUP_ACTIVATION.workflow_id}:{event.workspace_id}:{event.signup_email}:{event.observed_at}",
        identity_state=identity.state,
        evidence=evidence,
        decisions=(
            WorkflowDecisionTrace(
                decision_kind="self_serve_value_path",
                selected_hypothesis=path.path_id,
                alternatives=tuple(item.path_id for item in path.secondary_hypotheses),
                confidence=path.confidence,
                confidence_model=(
                    "Score path hypotheses from source-backed metrics.",
                    "Require explicit first-value milestone completion.",
                    "Calibrate confidence by source diversity and stale milestones.",
                ),
                source_ids=decision_source_ids or (receipts[0].source_id,),
                limitations=path.open_questions,
                domain_payload={
                    "status": status,
                    "first_value_reached": path.first_value_reached,
                    "current_milestone_id": path.current_milestone_id,
                    "recommended_action": action.action_type,
                },
            ),
        ),
        validations=validations,
        outputs=outputs,
    )


def _proposal_ref(proposal: ActionProposal) -> SelfServeProposalRef:
    return SelfServeProposalRef(
        proposal_id=proposal.proposal_id,
        action_type=proposal.action,
        status=proposal.status,
        autonomy_tier=proposal.autonomy_tier,
        required_permission=proposal.required_permission,
    )


def _preferred_contact(contacts: tuple[CRMContact, ...]) -> CRMContact | None:
    consented = [contact for contact in contacts if contact.consent_to_contact]
    return sorted(consented, key=lambda contact: (contact.org_level or 99, contact.email))[0] if consented else None


def _has_recent_signal(evidence: _AccountEvidence, metric_name: str) -> bool:
    return any(signal.metric_name == metric_name and signal.value > 0 for signal in evidence.usage_signals)


def _path_confidence(progress: list[SelfServeMilestoneProgress], evidence: _AccountEvidence) -> float:
    if not evidence.usage_signals:
        return 0.0
    completed = sum(1 for item in progress if item.status == "completed")
    first_value_evidence = any(
        item.milestone_id == "first_value" and item.evidence_source_ids
        for item in progress
    )
    source_support = sum((
        1 if evidence.contacts else 0,
        1 if evidence.adoption_summary is not None else 0,
        1 if evidence.entitlements else 0,
        1 if evidence.gmail_signals or evidence.call_signals else 0,
        1 if evidence.internal_notes else 0,
    ))
    stale_penalty = 0.1 * sum(1 for item in progress if item.status == "stale")
    confidence = (
        0.25
        + min(0.30, completed * 0.08)
        + (0.20 if first_value_evidence else 0.0)
        + min(0.20, source_support * 0.04)
        - stale_penalty
    )
    return round(max(0.0, min(0.95, confidence)), 2)


def _open_questions(evidence: _AccountEvidence, path_id: str) -> tuple[str, ...]:
    questions: list[str] = []
    if not evidence.contacts:
        questions.append("Which contact should receive self-serve activation guidance?")
    if path_id == "crm_enterprise_curious":
        questions.append("Who can sponsor the enterprise CRM connection evaluation?")
    if not evidence.usage_signals:
        questions.append("Which product telemetry events have fired since signup?")
    if not evidence.entitlements:
        questions.append("Which self-serve capabilities is this workspace entitled to use?")
    if evidence.cases:
        questions.append("Did the support issue block the next value-path milestone?")
    if not evidence.gmail_signals and not evidence.call_signals and not evidence.internal_notes:
        questions.append("Is there any customer or internal context explaining the signup intent?")
    return tuple(questions)


def _email_domain(email: str) -> str:
    parts = email.lower().split("@", 1)
    return parts[1].strip() if len(parts) == 2 else ""


def _workspace_name_from_email(email: str) -> str:
    domain = _email_domain(email)
    if not domain:
        return "Self-serve workspace"
    if domain in PERSONAL_EMAIL_DOMAINS:
        return "Personal self-serve workspace"
    return domain.split(".", 1)[0].replace("-", " ").title()


def _compact_timestamp(value: str) -> str:
    return "".join(char for char in value if char.isdigit())[:14] or "unknown"


def _generated_at(as_of: str) -> str:
    return f"{as_of}T00:00:00Z" if "T" not in as_of else as_of


def _days_between(start: str, end: str) -> int:
    try:
        s = _parse_date(start)
        e = _parse_date(end)
    except ValueError:
        return 0
    return max(0, (e - s).days)


def _parse_date(value: str) -> date:
    text = value.replace("Z", "+00:00")
    if "T" in text:
        return datetime.fromisoformat(text).date()
    return date.fromisoformat(text[:10])
