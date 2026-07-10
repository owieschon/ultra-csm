"""Book-sweep work queue for Agent 1 Time-to-Value triage."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, replace
from typing import TYPE_CHECKING, Literal

from ultra_csm._util import compact_asdict, iso_date
from ultra_csm.agent1.content_route_matcher import (
    ContentCatalogEntry,
    load_tenant_content_catalog,
    match_content,
)
from ultra_csm.agent1.slot_b import (
    FIXTURE_SLOT_B_MODEL_ID,
    FixtureReasonDraftWriter,
    ReasonDraftOutput,
    ReasonDraftRequest,
    ReasonDraftWriter,
    SlotBContractError,
    SlotBEvidence,
    SlotBPriority,
    SlotBPriorityFactor,
    validate_reason_draft_output,
)
from ultra_csm.agent1.slot_a import (
    CaseNoteClassificationOutput,
    CaseNoteClassificationRequest,
    CaseNoteClassifier,
    FixtureCaseNoteClassifier,
    SlotACaseRef,
)
from ultra_csm.data_plane import (
    CRMAccount,
    CRMContact,
    CustomerDataPlane,
    EvidenceRef,
    OnboardingPhase,
    OnboardingProject,
    OnboardingTask,
    TimeToValueMilestone,
    onboarding_activation_gap_ids,
)
from ultra_csm.data_plane.contracts import ResolutionState
from ultra_csm.governance import ActionGate, ActionProposal, proposal_fields_for
from ultra_csm.governance.csm_actions import CSMActionType, implied_motion_for_action
from ultra_csm.internal_bridge import InternalBridgeDecision, route_internal_bridge
from ultra_csm.knowledge import OrgPack, PlaybookSet, load_org_pack, load_playbooks
from ultra_csm.motion_resolver import resolve_motions
from ultra_csm.quality_breaker import (
    QualityBreakerConfig,
    QualityBreakerDecision,
    evaluate_quality_breaker,
)
from ultra_csm.recipient_resolver import resolve_recipient
from ultra_csm.snapshot_store import SnapshotStore
from ultra_csm.value_model import (
    CustomerValueModel,
    ValueFactor,
    ValueModelConfig,
    account_attributes,
    build_customer_value_model,
    load_value_model_config,
    project_ttv_lens,
    resolve_tenant_tier,
)
from ultra_csm.work_packets import CSMWorkPacket, PacketInputs, build_work_packet

if TYPE_CHECKING:
    from ultra_csm.cost_tracker import CostBudget, CostTracker
    from ultra_csm.data_plane.contracts import StakeholderRelationship
    from ultra_csm.data_plane.relationship_signals import JobChangeSignal

log = logging.getLogger(__name__)

Disposition = Literal["propose_customer_action", "internal_review", "escalate"]
ProposalStatus = Literal["pending", "approved", "denied"]
PriorityFactor = ValueFactor
DraftMode = Literal["fixture", "live", "template_fallback", "none"]
TrajectoryFactorState = Literal["known", "unknown"]


@dataclass(frozen=True)
class TrajectoryFactorEvaluation:
    """Result of folding snapshot history into deterministic priority."""

    state: TrajectoryFactorState
    factor: PriorityFactor | None


@dataclass(frozen=True)
class Priority:
    """Deterministic priority; no model output may mint this value."""

    score: int
    factors: tuple[PriorityFactor, ...]


@dataclass(frozen=True)
class ProposalRef:
    """Reference to the existing ActionGate state machine."""

    proposal_id: str
    status: ProposalStatus
    action_type: CSMActionType
    channel: str
    created_by_principal: str


@dataclass(frozen=True)
class CSMWorkItem:
    tenant_id: str
    account_resolution: ResolutionState
    account_id: str | None
    candidate_account_ids: tuple[str, ...]
    disposition: Disposition
    recommended_action: CSMActionType | None
    reason: str
    priority: Priority | None
    evidence: tuple[EvidenceRef, ...]
    customer_contact_allowed: bool
    proposal: ProposalRef | None
    swept_at: str
    draft_mode: DraftMode = "none"
    customer_draft: str | None = None
    motion: str | None = None
    recipient_resolution: str | None = None
    slot_a_classifications: tuple[CaseNoteClassificationOutput, ...] = ()
    # Person UI depth (Harvest 17), additive: the resolved recipient's
    # identity, discarded before this (resolve_recipient's CRMContact was
    # checked for truthiness only) -- captured here for the recipient chip.
    recipient_name: str | None = None
    recipient_role: str | None = None
    # MP-B internal bridge: additive deterministic routing to the internal
    # specialist pair. This does not alter disposition or customer action.
    internal_bridge_decision: InternalBridgeDecision | None = None
    # MP-D2 packet contract: deterministic read-side envelope over the
    # existing sweep, Slot B, internal bridge, value-model, and gate outputs.
    work_packet: CSMWorkPacket | None = None


@dataclass
class _SweepTimingAccum:
    """Mutable accumulator for sweep phase timing (internal)."""

    value_model_ms: float = 0.0
    slot_b_ms: float = 0.0
    slot_b_calls: int = 0
    governance_ms: float = 0.0


@dataclass(frozen=True)
class _SlotBInputs:
    cases: tuple
    evidence: tuple[EvidenceRef, ...]
    priority: Priority
    slot_a_classifications: tuple[CaseNoteClassificationOutput, ...] = ()
    stakeholders: tuple = ()


@dataclass(frozen=True)
class SweepResult:
    tenant_id: str
    work_items: tuple[CSMWorkItem, ...]
    escalations: tuple[CSMWorkItem, ...]
    swept_accounts: tuple[str, ...]
    degraded_items: int = 0
    budget_skipped: int = 0
    quality_breaker: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def run_time_to_value_sweep(
    data_plane: CustomerDataPlane,
    tenant_id: str,
    gate: ActionGate,
    *,
    sweep_principal_id: str,
    as_of: str,
    reason_draft_writer: ReasonDraftWriter | None = None,
    quality_breaker: QualityBreakerConfig | None = None,
    cost_tracker: "CostTracker | None" = None,
    cost_budget: "CostBudget | None" = None,
    org_context: dict | None = None,
    snapshot_store: SnapshotStore | None = None,
    playbooks: PlaybookSet | None = None,
    playbook_tenant_slug: str | None = None,
    value_model_config: ValueModelConfig | None = None,
    case_note_classifier: CaseNoteClassifier | None = None,
) -> SweepResult:
    """Run Agent 1 across a tenant book and emit a deterministic work queue.

    *tenant_id* is the data-plane/CRM tenant identity (e.g. ``"ultra-demo"``)
    and is NOT assumed to match a ``knowledge/tenants/<slug>/playbooks.json``
    slug -- those are two separate identity namespaces in this codebase
    today (verified: no existing caller passes a knowledge-tenant slug as
    *tenant_id*). Pass *playbooks* directly, or *playbook_tenant_slug* to
    auto-load one, to opt a caller into motion resolution; without either,
    every emitted ``CSMWorkItem.motion`` stays ``None`` (unchanged
    pre-existing behavior).
    """

    from ultra_csm.cost_tracker import estimate_call_cost

    sweep_start = time.perf_counter()
    writer = reason_draft_writer or FixtureReasonDraftWriter()
    # When the caller supplies org_context explicitly (e.g. a hostile-pack
    # test fixture), use it verbatim for every account -- same
    # authority-invariance contract as before this dispatch. Only the
    # caller-absent default path resolves org context per account, so
    # golden-exemplar selection (disposition-keyed) can vary per work item.
    default_org_pack = load_org_pack() if org_context is None else None
    breaker_decision = (
        evaluate_quality_breaker(quality_breaker)
        if quality_breaker is not None
        else None
    )
    if playbooks is None and playbook_tenant_slug is not None:
        playbooks = load_playbooks(playbook_tenant_slug)
    if value_model_config is None:
        value_model_config = load_value_model_config()
    classifier = case_note_classifier or FixtureCaseNoteClassifier()

    if cost_tracker is not None:
        cost_tracker.reset_sweep()

    accounts = tuple(data_plane.crm.list_accounts(tenant_id=tenant_id))
    swept_accounts = tuple(account.account_id for account in accounts)
    items: list[CSMWorkItem] = []
    escalations: list[CSMWorkItem] = []
    degraded_items = 0
    budget_skipped = 0
    budget_exceeded = False
    emitted_escalations: set[tuple[str, ...]] = set()
    timing = _SweepTimingAccum()

    for account in accounts:
        contacts = tuple(data_plane.crm.list_contacts(account.account_id))
        resolution = _account_resolution_for_contacts(data_plane, contacts)
        if resolution != "exactly_one":
            candidates = _candidate_account_ids(data_plane, contacts)
            key = candidates or (account.account_id,)
            if resolution == "ambiguous" and key not in emitted_escalations:
                escalations.append(_escalation_item(
                    tenant_id=tenant_id,
                    candidates=key,
                    contacts=contacts,
                    as_of=as_of,
                    accounts_scanned=len(swept_accounts),
                    accounts_in_book=len(accounts),
                ))
                emitted_escalations.add(key)
            continue

        # Budget check before Slot B call.
        if cost_budget is not None and not budget_exceeded:
            estimated = estimate_call_cost(writer.model_id)
            sweep_cost = (
                cost_tracker.current_sweep_cost if cost_tracker else 0.0
            )
            daily_cost = (
                cost_tracker.today_cost_usd() if cost_tracker else 0.0
            )
            if cost_budget.would_exceed_sweep(sweep_cost, estimated):
                log.warning(
                    "Sweep cost budget exceeded, skipping Slot B for "
                    "remaining accounts",
                    extra={
                        "sweep_cost_usd": round(sweep_cost, 6),
                        "estimated_next_usd": round(estimated, 6),
                        "max_per_sweep_usd": cost_budget.max_cost_per_sweep_usd,
                    },
                )
                budget_exceeded = True
            elif cost_budget.would_exceed_daily(daily_cost, estimated):
                log.warning(
                    "Daily cost budget exceeded, skipping Slot B for "
                    "remaining accounts",
                    extra={
                        "daily_cost_usd": round(daily_cost, 6),
                        "estimated_next_usd": round(estimated, 6),
                        "max_per_day_usd": cost_budget.max_cost_per_day_usd,
                    },
                )
                budget_exceeded = True

        current_writer: ReasonDraftWriter = (
            FixtureReasonDraftWriter() if budget_exceeded else writer
        )

        built = _work_item_for_account(
            data_plane,
            account,
            tenant_id=tenant_id,
            gate=gate,
            sweep_principal_id=sweep_principal_id,
            as_of=as_of,
            contacts=contacts,
            reason_draft_writer=current_writer,
            quality_breaker=breaker_decision,
            org_context=org_context,
            default_org_pack=default_org_pack,
            timing=timing,
            snapshot_store=snapshot_store,
            playbooks=playbooks,
            value_model_config=value_model_config,
            case_note_classifier=classifier,
            accounts_scanned=len(swept_accounts),
            accounts_in_book=len(accounts),
        )
        if built is not None:
            if budget_exceeded:
                budget_skipped += 1
            if built.draft_mode == "template_fallback":
                degraded_items += 1
            items.append(built)

    sweep_elapsed_ms = (time.perf_counter() - sweep_start) * 1000.0
    slot_b_avg = (
        timing.slot_b_ms / timing.slot_b_calls
        if timing.slot_b_calls > 0
        else 0.0
    )

    log.info(
        "sweep_timing",
        extra={
            "total_sweep_ms": round(sweep_elapsed_ms, 2),
            "value_model_ms": round(timing.value_model_ms, 2),
            "slot_b_total_ms": round(timing.slot_b_ms, 2),
            "slot_b_avg_per_account_ms": round(slot_b_avg, 2),
            "slot_b_call_count": timing.slot_b_calls,
            "governance_ms": round(timing.governance_ms, 2),
            "accounts_swept": len(swept_accounts),
            "budget_skipped": budget_skipped,
        },
    )

    ordered = tuple(sorted(
        items,
        key=lambda item: (
            item.priority.score if item.priority else -1,
            item.account_id or "|".join(item.candidate_account_ids),
        ),
        reverse=True,
    ))
    return SweepResult(
        tenant_id=tenant_id,
        work_items=ordered,
        escalations=tuple(sorted(
            escalations,
            key=lambda item: (item.swept_at, item.candidate_account_ids),
            reverse=True,
        )),
        swept_accounts=swept_accounts,
        degraded_items=degraded_items,
        budget_skipped=budget_skipped,
        quality_breaker=(
            breaker_decision.to_dict()
            if breaker_decision is not None
            else None
        ),
    )


def build_reason_draft_request_for_account(
    data_plane: CustomerDataPlane,
    tenant_id: str,
    account_id: str,
    *,
    as_of: str,
    action: CSMActionType = "draft_customer_outreach",
    evidence_source_ids: tuple[str, ...] | None = None,
    contact_id: str | None = None,
    org_context: dict | None = None,
) -> ReasonDraftRequest | None:
    """Reconstruct the Slot B request for a current fixture account.

    This is used by the bounded revise path. It reuses the same deterministic
    evidence and priority helpers as the sweep, then optionally narrows evidence
    to the ids captured in the original proposal.
    """

    account = data_plane.crm.get_account(account_id)
    if account is None:
        return None

    contacts = tuple(data_plane.crm.list_contacts(account.account_id))
    inputs = _slot_b_inputs_for_account(
        data_plane,
        account,
        tenant_id=tenant_id,
        as_of=as_of,
        evidence_source_ids=evidence_source_ids,
        case_note_classifier=FixtureCaseNoteClassifier(),
    )
    if inputs is None:
        return None

    contact = _proposal_contact(contacts, contact_id)
    customer_contact_allowed = action == "draft_customer_outreach" and contact is not None
    if action == "draft_customer_outreach" and not customer_contact_allowed:
        return None
    disposition: Disposition = (
        "propose_customer_action" if customer_contact_allowed else "internal_review"
    )
    return _slot_b_request(
        tenant_id=tenant_id,
        account=account,
        disposition=disposition,
        action=action,
        customer_contact_allowed=customer_contact_allowed,
        priority=inputs.priority,
        evidence=inputs.evidence,
        as_of=as_of,
        contact=contact,
        cases=inputs.cases,
        org_context=(
            org_context
            if org_context is not None
            else load_org_pack().slot_b_context(
                disposition=disposition, recommended_action=action
            )
        ),
    )


def _person_layer_inputs(
    data_plane: CustomerDataPlane,
    account_id: str,
) -> tuple[tuple["StakeholderRelationship", ...], tuple["JobChangeSignal", ...]]:
    """Additive person-layer fetch (Harvest 16): stakeholders + job-change
    signals for *account_id*, in the same per-account data_plane pass
    ``_slot_b_inputs_for_account`` already makes -- never a second fetch
    pass. ``list_stakeholders``/``list_job_changes`` are NOT part of the
    ``CRMDataConnector`` Protocol (only ``FixtureCRMDataConnector``
    implements them for the fleetops fixture book); connectors that lack
    them degrade to an empty tuple rather than raising, so this is fail-safe
    for every other connector (Sim/Fieldstone) unchanged.
    """

    list_stakeholders = getattr(data_plane.crm, "list_stakeholders", None)
    list_job_changes = getattr(data_plane.crm, "list_job_changes", None)
    stakeholders = tuple(list_stakeholders(account_id)) if list_stakeholders else ()
    job_changes = tuple(list_job_changes(account_id)) if list_job_changes else ()
    return stakeholders, job_changes


def _classify_case_notes(
    classifier: CaseNoteClassifier,
    *,
    tenant_id: str,
    account_id: str,
    cases: tuple,
) -> tuple[CaseNoteClassificationOutput, ...]:
    case_refs = tuple(
        SlotACaseRef(case_id=case.case_id, account_id=case.account_id)
        for case in cases
    )
    outputs: list[CaseNoteClassificationOutput] = []
    for case in cases:
        note = getattr(case, "subject", "")
        if not note:
            continue
        request = CaseNoteClassificationRequest(
            tenant_id=tenant_id,
            account_id=account_id,
            case_id=case.case_id,
            case_note_text=note,
            account_case_refs=case_refs,
        )
        outputs.append(classifier.classify(request))
    return tuple(outputs)


def _slot_b_inputs_for_account(
    data_plane: CustomerDataPlane,
    account: CRMAccount,
    *,
    tenant_id: str,
    as_of: str,
    evidence_source_ids: tuple[str, ...] | None = None,
    snapshot_store: SnapshotStore | None = None,
    case_note_classifier: CaseNoteClassifier,
) -> _SlotBInputs | None:
    company = data_plane.cs.get_company(account.account_id)
    health = data_plane.cs.get_health_score(account.account_id)
    adoption = data_plane.cs.get_adoption_summary(account.account_id)
    if company is None or health is None or adoption is None:
        return None

    ctas = tuple(data_plane.cs.list_ctas(account.account_id, status="open"))
    plans = tuple(data_plane.cs.list_success_plans(account.account_id))
    cases = tuple(data_plane.crm.list_cases(account.account_id))
    opportunities = tuple(data_plane.crm.list_opportunities(account.account_id))
    slot_a_classifications = _classify_case_notes(
        case_note_classifier,
        tenant_id=tenant_id,
        account_id=account.account_id,
        cases=cases,
    )
    signals = tuple(data_plane.telemetry.list_usage_signals(account.account_id))
    entitlements = tuple(data_plane.telemetry.list_entitlements(account.account_id))
    stakeholders, job_changes = _person_layer_inputs(data_plane, account.account_id)
    signal_ids = {signal.signal_id for signal in signals}
    onboarding_projects, onboarding_phases, onboarding_tasks = _onboarding_evidence(
        data_plane, account.account_id
    )
    onboarding_ids = {p.phase_id for p in onboarding_phases} | {t.task_id for t in onboarding_tasks}
    milestones = tuple(data_plane.telemetry.list_ttv_milestones(account.account_id))
    onboarding_milestones = _onboarding_milestones(data_plane, account.account_id)
    all_milestones = milestones + tuple(
        milestone for milestone in onboarding_milestones if milestone not in milestones
    )
    open_gaps = tuple(
        milestone for milestone in all_milestones
        if milestone.achieved_at is None and iso_date(milestone.expected_by) <= iso_date(as_of)
    )
    grounded_ids = signal_ids | onboarding_ids
    telemetry_backed_gaps = tuple(
        milestone for milestone in open_gaps
        if any(signal_id in grounded_ids for signal_id in milestone.evidence_signal_ids)
    )
    overdue_plans = tuple(plan for plan in plans if iso_date(plan.target_date) <= iso_date(as_of))

    # Lifecycle-aware TTV: an onboarding-stage account whose only signal is
    # delivery slippage (RUNNING_LATE progress / at-risk task / overdue
    # phase with no actual) clears no date-based gap above -- surface that
    # activation-gap evidence directly rather than leave the account
    # invisible to the sweep. Scored only in the onboarding stage (see
    # ``_ttv_base_factors``); excludes phases already counted as an open gap.
    activation_gap_ids: tuple[str, ...] = ()
    if company.lifecycle_stage == "onboarding":
        activation_gap_ids = onboarding_activation_gap_ids(
            projects=onboarding_projects,
            phases=onboarding_phases,
            tasks=onboarding_tasks,
            as_of=as_of,
            covered_milestone_names=frozenset(m.milestone for m in open_gaps),
        )

    evidence = _evidence_refs(
        account.account_id,
        as_of=as_of,
        open_gaps=telemetry_backed_gaps,
        signals=signals,
        ctas=ctas,
        plans=overdue_plans,
        cases=cases,
        health_observed_at=health.measured_at,
        onboarding_phases=onboarding_phases,
        onboarding_tasks=onboarding_tasks,
    )
    if activation_gap_ids:
        evidence = evidence + _onboarding_activation_gap_evidence_refs(
            activation_gap_ids,
            onboarding_phases=onboarding_phases,
            onboarding_tasks=onboarding_tasks,
            as_of=as_of,
        )
    if evidence_source_ids is not None:
        evidence = _filter_evidence_refs_by_source_id(evidence, evidence_source_ids)
    if not evidence:
        return None

    model = build_customer_value_model(
        account=account,
        company=company,
        health=health,
        adoption=adoption,
        entitlements=entitlements,
        usage_signals=signals,
        success_plans=plans,
        opportunities=opportunities,
        onboarding_milestones=onboarding_milestones,
        stakeholders=stakeholders,
        job_changes=job_changes,
        as_of=as_of,
    )
    trajectory = _trajectory_decline_evaluation(
        snapshot_store,
        account_id=account.account_id,
        model=model,
    )
    priority = _priority(
        model,
        company=company,
        health=health,
        open_gaps=telemetry_backed_gaps,
        overdue_plans=overdue_plans,
        as_of=as_of,
        trajectory_factor=trajectory.factor,
        onboarding_evidence_ids=frozenset(onboarding_ids),
        onboarding_activation_gap_ids=activation_gap_ids,
        slot_a_classifications=slot_a_classifications,
    )
    if priority.score <= 0:
        return None
    return _SlotBInputs(
        cases=cases,
        evidence=evidence,
        priority=priority,
        slot_a_classifications=slot_a_classifications,
        stakeholders=stakeholders,
    )


def _proposal_contact(
    contacts: tuple[CRMContact, ...],
    contact_id: str | None,
) -> CRMContact | None:
    if contact_id:
        contact = next((item for item in contacts if item.contact_id == contact_id), None)
        return contact if contact is not None and contact.consent_to_contact else None
    return next((item for item in contacts if item.consent_to_contact), None)


def _filter_evidence_refs_by_source_id(
    evidence: tuple[EvidenceRef, ...],
    source_ids: tuple[str, ...],
) -> tuple[EvidenceRef, ...]:
    refs_by_id: dict[str, EvidenceRef] = {}
    for ref in evidence:
        refs_by_id.setdefault(ref.source_id, ref)

    filtered: list[EvidenceRef] = []
    for source_id in source_ids:
        ref = refs_by_id.get(source_id)
        if ref is None:
            return ()
        filtered.append(ref)
    return tuple(filtered)


def unsafe_placeholder_sweep(
    data_plane: CustomerDataPlane,
    tenant_id: str,
    gate: ActionGate,
    *,
    sweep_principal_id: str,
    as_of: str,
) -> SweepResult:
    """Deliberately unsafe foil. The scorecard must fail this runner."""

    accounts = tuple(data_plane.crm.list_accounts(tenant_id=tenant_id))
    items: list[CSMWorkItem] = []
    for account in accounts:
        proposal = None
        if account.account_id:
            action = "draft_customer_outreach"
            prop = gate.propose(
                intent="unsafe_placeholder",
                payload={
                    "account_id": account.account_id,
                    "subject": "Unsafe placeholder",
                    "body": "This placeholder fabricates urgency.",
                },
                grounding_ref=f"unsafe:{account.account_id}",
                cause_ref=f"unsafe:{account.account_id}:{as_of}",
                **proposal_fields_for(action),
            )
            proposal = ProposalRef(
                proposal_id=prop.proposal_id,
                status="approved",  # intentionally violates proposal-only gate
                action_type=action,
                channel="email",
                created_by_principal=sweep_principal_id,
            )
        items.append(CSMWorkItem(
            tenant_id=tenant_id,
            account_resolution="exactly_one",
            account_id=account.account_id,
            candidate_account_ids=(),
            disposition="propose_customer_action",
            recommended_action="draft_customer_outreach",
            reason="Fabricated high ARR urgency without grounded evidence.",
            priority=Priority(
                score=_arr_score(data_plane, account.account_id),
                factors=(PriorityFactor(
                    "arr_only",
                    float(_arr_score(data_plane, account.account_id)),
                    _arr_score(data_plane, account.account_id),
                    evidence=(),
                    config_version="unsafe-placeholder",
                    rule_name="unsafe",
                    threshold_name=None,
                    threshold_value=None,
                ),),
            ),
            evidence=(),
            customer_contact_allowed=True,
            proposal=proposal,
            swept_at=as_of,
        ))
    return SweepResult(
        tenant_id=tenant_id,
        work_items=tuple(sorted(
            items,
            key=lambda item: item.priority.score if item.priority else -1,
            reverse=True,
        )),
        escalations=(),
        swept_accounts=tuple(account.account_id for account in accounts),
    )


def _account_triggers_for_motion(
    health,
    adoption,
    entitlements,
    *,
    value_model: CustomerValueModel | None = None,
    open_milestone_gaps: tuple[TimeToValueMilestone, ...] = (),
) -> set[str]:
    """Mirrors eval/tier_policy_battery.py's ``_account_triggers`` for the
    first two (health/adoption-only) triggers, then extends with the
    fleetops playbook's remaining five, each reusing an EXISTING computed
    signal rather than inventing a threshold (per this dispatch's
    Decisions section):

    - ``health_red``/``health_yellow``: ``health.band``, the exact band
      ``value_model.py``'s ``_ttv_base_factors`` already keys off.
    - ``low_seat_penetration``: ``value_model.penetration.factors``, whose
      factor name is literally ``"low_seat_penetration"``
      (``_penetration_rail``, ``seat_penetration_floor`` threshold).
    - ``milestones_overdue``: an achieved-null milestone whose
      ``expected_by`` is on/before *as_of* -- the same
      ``open_milestone_gaps`` shape ``_slot_b_inputs_for_account`` already
      computes for priority scoring.
    - ``outcome_unknown``: ``value_model.outcome.realized_state ==
      "not_instrumented"`` (``_outcome_rail``): no success plan realized
      and no onboarding milestone achieved.

    ``value_model``/``open_milestone_gaps`` are optional so existing
    single-signal callers (none currently pass them) keep working
    unchanged; callers that want the full 7-trigger set pass both."""

    triggers: set[str] = set()
    if health is not None and "champion_inactive" in health.drivers:
        triggers.add("champion_inactive")
    if adoption is not None and adoption.underused_capabilities:
        entitled_caps = {e.capability for e in entitlements}
        if any(cap in entitled_caps for cap in adoption.underused_capabilities):
            triggers.add("feature_shallow_depth")
    if health is not None and health.band in {"red", "yellow"}:
        triggers.add("health_red" if health.band == "red" else "health_yellow")
    if open_milestone_gaps:
        triggers.add("milestones_overdue")
    if value_model is not None:
        if value_model.penetration.factors:
            triggers.add("low_seat_penetration")
        if value_model.outcome.realized_state == "not_instrumented":
            triggers.add("outcome_unknown")
    return triggers


def _account_tier_and_triggers(
    data_plane: CustomerDataPlane,
    account: CRMAccount,
    *,
    value_model_config: ValueModelConfig,
    as_of: str | None = None,
) -> tuple[str, set[str]] | None:
    """This account's tier and fired trigger_factor set (one data_plane
    pass). Returns None if the account has no CS-platform company record;
    in practice callers only reach this after ``_slot_b_inputs_for_account``
    already required one, so this branch mirrors that check rather than
    adding a new failure mode.

    Widened (Phase 2, full 7-trigger coverage) to additionally fetch
    ``success_plans``/``usage_signals``/onboarding milestones in this SAME
    single per-account pass -- never a second fetch pass -- and build the
    same ``CustomerValueModel`` ``_slot_b_inputs_for_account`` builds, so
    the remaining 5 detectors reuse its penetration/outcome rails rather
    than re-deriving them. ``milestones_overdue`` needs *as_of*; omitting
    it (existing callers before Phase 2) simply skips that one trigger,
    never raises.
    """

    company = data_plane.cs.get_company(account.account_id)
    if company is None:
        return None
    health = data_plane.cs.get_health_score(account.account_id)
    adoption = data_plane.cs.get_adoption_summary(account.account_id)
    entitlements = tuple(data_plane.telemetry.list_entitlements(account.account_id))
    tier = resolve_tenant_tier(account_attributes(account, company), value_model_config).tier

    if health is None or adoption is None:
        triggers = _account_triggers_for_motion(health, adoption, entitlements)
        return tier, triggers

    success_plans = tuple(data_plane.cs.list_success_plans(account.account_id))
    usage_signals = tuple(data_plane.telemetry.list_usage_signals(account.account_id))
    opportunities = tuple(data_plane.crm.list_opportunities(account.account_id))
    onboarding_milestones = _onboarding_milestones(data_plane, account.account_id)
    value_model = build_customer_value_model(
        account=account,
        company=company,
        health=health,
        adoption=adoption,
        entitlements=entitlements,
        usage_signals=usage_signals,
        success_plans=success_plans,
        opportunities=opportunities,
        onboarding_milestones=onboarding_milestones,
        as_of=as_of,
        config=value_model_config,
    )
    open_milestone_gaps: tuple[TimeToValueMilestone, ...] = ()
    if as_of is not None:
        milestones = tuple(data_plane.telemetry.list_ttv_milestones(account.account_id))
        all_milestones = milestones + tuple(
            m for m in onboarding_milestones if m not in milestones
        )
        open_milestone_gaps = tuple(
            m for m in all_milestones
            if m.achieved_at is None and iso_date(m.expected_by) <= iso_date(as_of)
        )
    triggers = _account_triggers_for_motion(
        health,
        adoption,
        entitlements,
        value_model=value_model,
        open_milestone_gaps=open_milestone_gaps,
    )
    return tier, triggers


def _account_tier_and_motion(
    data_plane: CustomerDataPlane,
    account: CRMAccount,
    *,
    playbooks: PlaybookSet,
    value_model_config: ValueModelConfig,
    as_of: str | None = None,
) -> tuple[str, str | None, set[str]] | None:
    """Resolve this one account's tier and tier-appropriate motion together
    via the promoted ``motion_resolver.resolve_motions`` -- a single-account
    map naturally never reaches cohort-collapse threshold, so this yields
    the same per-account motion a whole-book sweep would (see
    motion_resolver's docstring). *as_of* is optional (default None) so
    existing callers that predate Phase 2's ``milestones_overdue``
    detector keep working unchanged; it just skips that one date-based
    trigger.

    Widened (19_CONTENT_ROADMAP.md Phase 5) to also return the raw
    trigger set: its one caller, ``_work_item_for_account``, needs it for
    the ``content_route`` matcher and would otherwise have to call
    ``_account_tier_and_triggers`` a second time -- a second data-plane
    fetch pass this function's own docstring precedent (see
    ``_account_tier_and_triggers``) explicitly avoids."""

    tier_and_triggers = _account_tier_and_triggers(
        data_plane, account, value_model_config=value_model_config, as_of=as_of
    )
    if tier_and_triggers is None:
        return None
    tier, triggers = tier_and_triggers
    resolved = resolve_motions({account.account_id: tier}, {account.account_id: triggers}, playbooks)
    plays = resolved["per_account"].get(account.account_id, ())
    motion = plays[0]["motion"] if plays else None
    return tier, motion, triggers


def collapse_cohorts(
    sweep: SweepResult,
    data_plane: CustomerDataPlane,
    *,
    tenant_id: str,
    playbooks: PlaybookSet,
    value_model_config: ValueModelConfig,
    as_of: str,
) -> SweepResult:
    """Post-sweep pass, additive and SEPARATE from per-account work-item
    construction: collapse per-account items sharing a (trigger_factor,
    tier) pair at or above cohort threshold into ONE cohort_action work
    item, exactly mirroring ``motion_resolver.resolve_motions``'s
    cohort-collapse branch -- a single account's work-item construction
    cannot see its siblings, so this runs over *tenant_id*'s whole book at
    *as_of* instead, the same way ``eval/tier_policy_battery.py``'s battery
    already proves offline. Collapsed per-account items are DROPPED from
    ``work_items`` (not flagged) -- this matches ``resolve_motions``'s own
    precedent of simply omitting collapsed accounts from ``per_account``
    rather than marking them, so no new suppression concept is introduced.

    A cohort item has no single ``account_id`` (it covers many), which
    ``CSMWorkItem.account_resolution`` has no dedicated value for --
    ``"ambiguous"`` (account_id=None + candidate_account_ids=many) is the
    closest existing fit, reused here NOT because identity is uncertain
    (every member account is known) but because it is the only existing
    state shaped like "no single account_id, see candidate_account_ids".
    Nothing in this codebase currently branches on ``account_resolution``
    (verified), so this reuse carries no known behavioral risk; a
    dedicated value is a follow-on Owner Ask, not added here (would touch
    ``data_plane/contracts.py``'s shared ``ResolutionState``, outside this
    dispatch's ownership map).
    """

    accounts = tuple(data_plane.crm.list_accounts(tenant_id=tenant_id))
    tier_by_account_id: dict[str, str] = {}
    triggers_by_account_id: dict[str, set[str]] = {}
    for account in accounts:
        tier_and_triggers = _account_tier_and_triggers(
            data_plane, account, value_model_config=value_model_config, as_of=as_of
        )
        if tier_and_triggers is None:
            continue
        tier_by_account_id[account.account_id] = tier_and_triggers[0]
        triggers_by_account_id[account.account_id] = tier_and_triggers[1]

    resolved = resolve_motions(tier_by_account_id, triggers_by_account_id, playbooks)
    cohort_actions = resolved["cohort_actions"]
    if not cohort_actions:
        return sweep

    cohort_account_ids: set[str] = set()
    cohort_items: list[CSMWorkItem] = []
    for cohort in cohort_actions:
        cohort_account_ids.update(cohort["account_ids"])
        reason = (
            f"Cohort collapse: {cohort['trigger_factor']} affects "
            f"{len(cohort['account_ids'])} {cohort['tier']} accounts via play "
            f"{cohort['play_id']!r} -- one cohort_action covers all, not "
            f"{len(cohort['account_ids'])} individual motions."
        )
        work_packet = build_work_packet(PacketInputs(
            tenant_id=tenant_id,
            account=None,
            as_of=as_of,
            account_resolution="ambiguous",
            candidate_account_ids=tuple(cohort["account_ids"]),
            disposition="propose_customer_action",
            recommended_action="cohort_action",
            motion="cohort_action",
            reason=reason,
            priority_score=None,
            priority_factors=(),
            evidence=(),
            customer_contact_allowed=False,
            accounts_scanned=len(sweep.swept_accounts),
            accounts_in_book=len(accounts),
        ))
        cohort_items.append(CSMWorkItem(
            tenant_id=tenant_id,
            account_resolution="ambiguous",
            account_id=None,
            candidate_account_ids=tuple(cohort["account_ids"]),
            disposition="propose_customer_action",
            recommended_action="cohort_action",
            reason=reason,
            priority=None,
            evidence=(),
            customer_contact_allowed=False,
            proposal=None,
            swept_at=as_of,
            motion="cohort_action",
            work_packet=work_packet,
        ))

    kept_items = tuple(item for item in sweep.work_items if item.account_id not in cohort_account_ids)
    return replace(sweep, work_items=kept_items + tuple(cohort_items))


def _work_item_for_account(
    data_plane: CustomerDataPlane,
    account: CRMAccount,
    *,
    tenant_id: str,
    gate: ActionGate,
    sweep_principal_id: str,
    as_of: str,
    contacts: tuple[CRMContact, ...],
    reason_draft_writer: ReasonDraftWriter,
    quality_breaker: QualityBreakerDecision | None = None,
    org_context: dict | None = None,
    default_org_pack: OrgPack | None = None,
    timing: _SweepTimingAccum | None = None,
    snapshot_store: SnapshotStore | None = None,
    playbooks: PlaybookSet | None = None,
    value_model_config: ValueModelConfig | None = None,
    case_note_classifier: CaseNoteClassifier | None = None,
    accounts_scanned: int = 0,
    accounts_in_book: int = 0,
) -> CSMWorkItem | None:
    value_start = time.perf_counter()
    inputs = _slot_b_inputs_for_account(
        data_plane,
        account,
        tenant_id=tenant_id,
        as_of=as_of,
        snapshot_store=snapshot_store,
        case_note_classifier=case_note_classifier or FixtureCaseNoteClassifier(),
    )
    if timing is not None:
        timing.value_model_ms += (time.perf_counter() - value_start) * 1000.0
    if inputs is None:
        return None

    tier_and_motion = (
        _account_tier_and_motion(
            data_plane, account, playbooks=playbooks, value_model_config=value_model_config
        )
        if playbooks is not None
        else None
    )
    tier = tier_and_motion[0] if tier_and_motion is not None else None
    motion = tier_and_motion[1] if tier_and_motion is not None else None
    triggers = tier_and_motion[2] if tier_and_motion is not None else set()
    internal_bridge_decision = route_internal_bridge(inputs.cases, as_of=as_of)

    contact, recipient_resolution = resolve_recipient(motion, inputs.stakeholders, contacts)
    customer_contact_allowed = contact is not None
    recipient_name = contact.name if contact else None
    recipient_role = None
    if contact:
        recipient_role = next(
            (s.relationship_type for s in inputs.stakeholders if s.contact_id == contact.contact_id),
            contact.role,
        )
    # Tier-forbidden-motion guard: narrows customer_contact_allowed exactly
    # like the quality breaker already does -- it never touches
    # recommended_action's derivation below, only whether this item is
    # allowed to proceed as a customer-facing draft. Fail-open when tier
    # can't be resolved or motion resolution wasn't requested (playbooks
    # is None); fail-closed only when a resolved tier actively forbids the
    # action's implied motion.
    tier_forbids_motion = (
        customer_contact_allowed
        and tier is not None
        and playbooks is not None
        and implied_motion_for_action("draft_customer_outreach") in playbooks.tier_for(tier).forbidden_motions
    )
    customer_action_blocked = (
        customer_contact_allowed
        and (
            (quality_breaker is not None and quality_breaker.triggered)
            or tier_forbids_motion
        )
    )
    disposition: Disposition = (
        "propose_customer_action"
        if customer_contact_allowed and not customer_action_blocked
        else "internal_review"
    )
    action: CSMActionType = (
        "draft_customer_outreach"
        if customer_contact_allowed and not customer_action_blocked
        else "recommend_next_best_action"
    )
    # content_route (19_CONTENT_ROADMAP.md Decision 7): only considered
    # when draft_customer_outreach did NOT already claim this account this
    # pass (action is still "recommend_next_best_action" at this point).
    # implied_motion_for_action("content_route") has no ACTION_IMPLIED_MOTION
    # entry (verified: governance/csm_actions.py) -- per that function's own
    # docstring this means "no forbidden-motion implication", so
    # tier_forbids_motion (which is specific to draft_customer_outreach's
    # motion) does not gate content_route; only the quality breaker does,
    # matching customer_action_blocked's OTHER guard.
    content_route_match: ContentCatalogEntry | None = None
    if (
        action == "recommend_next_best_action"
        and customer_contact_allowed
        and not (quality_breaker is not None and quality_breaker.triggered)
        and playbooks is not None
    ):
        catalog = load_tenant_content_catalog(playbooks.tenant)
        matches = match_content(triggers, catalog)
        if matches:
            content_route_match = matches[0]
            action = "content_route"
            disposition = "propose_customer_action"
    # Caller-supplied org_context (e.g. a hostile-pack test fixture) is used
    # verbatim, unchanged from before this dispatch. Only the default org
    # pack path is disposition-aware, so golden-exemplar selection can vary
    # per work item within one sweep.
    resolved_org_context = (
        org_context
        if org_context is not None
        else default_org_pack.slot_b_context(
            disposition=disposition, recommended_action=action
        )
        if default_org_pack is not None
        else None
    )
    slot_b_request = _slot_b_request(
        tenant_id=tenant_id,
        account=account,
        disposition=disposition,
        action=action,
        customer_contact_allowed=customer_contact_allowed and not customer_action_blocked,
        priority=inputs.priority,
        evidence=inputs.evidence,
        as_of=as_of,
        contact=contact if not customer_action_blocked else None,
        cases=inputs.cases,
        org_context=resolved_org_context,
    )
    slot_start = time.perf_counter()
    slot_b, draft_mode = _write_slot_b_with_fallback(slot_b_request, reason_draft_writer)
    if timing is not None:
        timing.slot_b_ms += (time.perf_counter() - slot_start) * 1000.0
        timing.slot_b_calls += 1
    if customer_action_blocked:
        draft_mode = "template_fallback"
    proposal_ref = None
    if customer_contact_allowed and not customer_action_blocked:
        governance_start = time.perf_counter()
        proposal = _propose_outreach(
            gate,
            account=account,
            contact=contact,
            action=action,
            as_of=as_of,
            evidence=inputs.evidence,
            priority=inputs.priority,
            draft_body=slot_b.customer_draft,
        )
        if timing is not None:
            timing.governance_ms += (time.perf_counter() - governance_start) * 1000.0
        proposal_ref = _proposal_ref(proposal, action=action, principal_id=sweep_principal_id)
    elif content_route_match is not None and contact is not None:
        governance_start = time.perf_counter()
        proposal = _propose_content_route(
            gate,
            account=account,
            contact=contact,
            as_of=as_of,
            matched_entry=content_route_match,
        )
        if timing is not None:
            timing.governance_ms += (time.perf_counter() - governance_start) * 1000.0
        proposal_ref = _proposal_ref(proposal, action=action, principal_id=sweep_principal_id)

    work_packet = build_work_packet(PacketInputs(
        tenant_id=tenant_id,
        account=account,
        as_of=as_of,
        account_resolution="exactly_one",
        candidate_account_ids=(),
        disposition=disposition,
        recommended_action=action,
        motion=motion,
        reason=slot_b.reason,
        priority_score=inputs.priority.score,
        priority_factors=inputs.priority.factors,
        evidence=inputs.evidence,
        contacts=contacts,
        selected_contact=contact if not customer_action_blocked else None,
        recipient_resolution=recipient_resolution,
        customer_contact_allowed=customer_contact_allowed and not customer_action_blocked,
        proposal_id=proposal_ref.proposal_id if proposal_ref else None,
        proposal_status=proposal_ref.status if proposal_ref else None,
        draft_body=slot_b.customer_draft,
        draft_mode=draft_mode,
        internal_bridge_decision=internal_bridge_decision,
        content_route_title=content_route_match.title if content_route_match else None,
        accounts_scanned=accounts_scanned,
        accounts_in_book=accounts_in_book,
    ))

    return CSMWorkItem(
        tenant_id=tenant_id,
        account_resolution="exactly_one",
        account_id=account.account_id,
        candidate_account_ids=(),
        disposition=disposition,
        recommended_action=action,
        reason=slot_b.reason,
        priority=inputs.priority,
        evidence=inputs.evidence,
        customer_contact_allowed=customer_contact_allowed,
        proposal=proposal_ref,
        swept_at=as_of,
        draft_mode=draft_mode,
        customer_draft=slot_b.customer_draft,
        motion=motion,
        recipient_resolution=recipient_resolution,
        recipient_name=recipient_name,
        recipient_role=recipient_role,
        slot_a_classifications=inputs.slot_a_classifications,
        internal_bridge_decision=internal_bridge_decision,
        work_packet=work_packet,
    )


def _write_slot_b_with_fallback(
    request: ReasonDraftRequest,
    writer: ReasonDraftWriter,
) -> tuple[ReasonDraftOutput, DraftMode]:
    try:
        output = writer.write(request)
        validate_reason_draft_output(request, output)
        mode: DraftMode = "fixture" if output.model_id == FIXTURE_SLOT_B_MODEL_ID else "live"
        return output, mode
    except (Exception, SlotBContractError):
        fallback = FixtureReasonDraftWriter().write(request)
        return fallback, "template_fallback"


def _propose_outreach(
    gate: ActionGate,
    *,
    account: CRMAccount,
    contact: CRMContact,
    action: CSMActionType,
    as_of: str,
    evidence: tuple[EvidenceRef, ...],
    priority: Priority,
    draft_body: str | None,
) -> ActionProposal:
    payload = {
        "account_id": account.account_id,
        "account_name": account.name,
        "contact_id": contact.contact_id,
        "contact_email": contact.email,
        "draft_channel": "email",
        "as_of": as_of,
        "subject": f"Time-to-Value follow-up for {account.name}",
        "body": draft_body,
        "priority": {
            "score": priority.score,
            "factors": [_priority_factor_payload(factor) for factor in priority.factors],
        },
        "evidence_ids": [ref.source_id for ref in evidence],
    }
    if action == "draft_customer_outreach":
        gate.record_outreach_contact_ref(
            account_ref=account.account_id,
            contact_ref=contact.contact_id,
            email=contact.email,
            name=contact.name,
            consent=contact.consent_to_contact,
            cause_ref=f"agent1:sweep:{account.account_id}:{as_of}:contact-consent",
        )
    return gate.propose(
        intent="agent1_time_to_value_sweep",
        payload=payload,
        grounding_ref=f"sweep:{account.account_id}:{as_of}",
        cause_ref=f"agent1:sweep:{account.account_id}:{as_of}",
        **proposal_fields_for(action),
    )


def _propose_content_route(
    gate: ActionGate,
    *,
    account: CRMAccount,
    contact: CRMContact,
    as_of: str,
    matched_entry: ContentCatalogEntry,
) -> ActionProposal:
    """Mirrors ``_propose_outreach``'s gate-integration shape exactly
    (same ``gate.propose`` call, same ``proposal_fields_for`` unpack), but
    the payload routes a PRE-APPROVED catalog asset -- content_id/title/
    format -- rather than an LLM-drafted email body, since that is what
    ``content_route``'s own spec describes (governance/csm_actions.py:
    "only the routing decision is proposed")."""

    payload = {
        "account_id": account.account_id,
        "account_name": account.name,
        "contact_id": contact.contact_id,
        "contact_email": contact.email,
        "draft_channel": "email",
        "as_of": as_of,
        "content_id": matched_entry.content_id,
        "content_title": matched_entry.title,
        "content_format": matched_entry.format,
        "addresses_gap": matched_entry.addresses_gap,
    }
    return gate.propose(
        intent="agent1_time_to_value_sweep",
        payload=payload,
        grounding_ref=f"sweep:{account.account_id}:{as_of}",
        cause_ref=f"agent1:sweep:{account.account_id}:{as_of}",
        **proposal_fields_for("content_route"),
    )


def _proposal_ref(
    proposal: ActionProposal,
    *,
    action: CSMActionType,
    principal_id: str,
) -> ProposalRef:
    return ProposalRef(
        proposal_id=proposal.proposal_id,
        status=proposal.status,  # type: ignore[arg-type]
        action_type=action,
        channel="email",
        created_by_principal=principal_id,
    )


def _priority_factor_payload(factor: PriorityFactor) -> dict:
    return compact_asdict(factor)


def _escalation_item(
    *,
    tenant_id: str,
    candidates: tuple[str, ...],
    contacts: tuple[CRMContact, ...],
    as_of: str,
    accounts_scanned: int = 0,
    accounts_in_book: int = 0,
) -> CSMWorkItem:
    evidence = tuple(
        EvidenceRef("crm", contact.contact_id, "email", as_of)
        for contact in contacts
    )
    work_packet = build_work_packet(PacketInputs(
        tenant_id=tenant_id,
        account=None,
        as_of=as_of,
        account_resolution="ambiguous",
        candidate_account_ids=candidates,
        disposition="escalate",
        recommended_action=None,
        motion=None,
        reason="Ambiguous contact identity; no account was auto-selected.",
        priority_score=None,
        priority_factors=(),
        evidence=evidence,
        contacts=contacts,
        customer_contact_allowed=False,
        accounts_scanned=accounts_scanned,
        accounts_in_book=accounts_in_book,
    ))
    return CSMWorkItem(
        tenant_id=tenant_id,
        account_resolution="ambiguous",
        account_id=None,
        candidate_account_ids=candidates,
        disposition="escalate",
        recommended_action=None,
        reason="Ambiguous contact identity; no account was auto-selected.",
        priority=None,
        evidence=evidence,
        customer_contact_allowed=False,
        proposal=None,
        swept_at=as_of,
        customer_draft=None,
        work_packet=work_packet,
    )


def _account_resolution_for_contacts(
    data_plane: CustomerDataPlane,
    contacts: tuple[CRMContact, ...],
) -> ResolutionState:
    states = {
        data_plane.crm.resolve_account_by_email(contact.email).state
        for contact in contacts
    }
    if "ambiguous" in states:
        return "ambiguous"
    if "exactly_one" in states:
        return "exactly_one"
    return "none"


def _candidate_account_ids(
    data_plane: CustomerDataPlane,
    contacts: tuple[CRMContact, ...],
) -> tuple[str, ...]:
    candidates: set[str] = set()
    for contact in contacts:
        resolution = data_plane.crm.resolve_account_by_email(contact.email)
        candidates.update(resolution.candidates)
    return tuple(sorted(candidates))


def _onboarding_milestones(
    data_plane: CustomerDataPlane,
    account_id: str,
) -> tuple[TimeToValueMilestone, ...]:
    """Rocketlane-derived milestones, when an onboarding source is mapped.

    Absence of an onboarding connector is the honest degraded state, not an
    error. Fail-closed on a connector error too (never fabricate evidence
    from an outage).
    """

    if data_plane.onboarding is None:
        return ()
    try:
        return tuple(data_plane.onboarding.derive_ttv_milestones(account_id))
    except Exception:
        return ()


def _onboarding_evidence(
    data_plane: CustomerDataPlane,
    account_id: str,
) -> tuple[tuple[OnboardingProject, ...], tuple[OnboardingPhase, ...], tuple[OnboardingTask, ...]]:
    """Rocketlane projects/phases/tasks groundable as evidence for this account."""

    if data_plane.onboarding is None:
        return (), (), ()
    try:
        projects = tuple(data_plane.onboarding.list_projects_for_account(account_id))
        phases: list[OnboardingPhase] = []
        tasks: list[OnboardingTask] = []
        for project in projects:
            phases.extend(data_plane.onboarding.list_phases(project.project_id))
            tasks.extend(data_plane.onboarding.list_tasks(project.project_id))
        return projects, tuple(phases), tuple(tasks)
    except Exception:
        return (), (), ()


def _evidence_refs(
    account_id: str,
    *,
    as_of: str,
    open_gaps: tuple[TimeToValueMilestone, ...],
    signals: tuple,
    ctas: tuple,
    plans: tuple,
    cases: tuple,
    health_observed_at: str,
    onboarding_phases: tuple[OnboardingPhase, ...] = (),
    onboarding_tasks: tuple[OnboardingTask, ...] = (),
) -> tuple[EvidenceRef, ...]:
    signal_by_id = {signal.signal_id: signal for signal in signals}
    phase_by_id = {phase.phase_id: phase for phase in onboarding_phases}
    task_by_id = {task.task_id: task for task in onboarding_tasks}
    refs: list[EvidenceRef] = []
    seen: set[tuple[str, str, str]] = set()
    def add(ref: EvidenceRef) -> None:
        key = (ref.source, ref.source_id, ref.field)
        if key not in seen:
            refs.append(ref)
            seen.add(key)

    for milestone in open_gaps:
        for signal_id in milestone.evidence_signal_ids:
            signal = signal_by_id.get(signal_id)
            if signal is not None:
                add(EvidenceRef("telemetry", signal.signal_id, signal.metric_name, signal.observed_at))
                continue
            phase = phase_by_id.get(signal_id)
            if phase is not None:
                add(EvidenceRef("rocketlane", phase.phase_id, "due_date", phase.due_date or as_of))
                continue
            task = task_by_id.get(signal_id)
            if task is not None:
                add(EvidenceRef("rocketlane", task.task_id, "due_date", task.due_date or as_of))
    for cta in ctas:
        add(EvidenceRef("cs_platform", cta.cta_id, "due_date", cta.due_date))
    for plan in plans:
        add(EvidenceRef("cs_platform", plan.plan_id, "target_date", plan.target_date))
    for case in cases:
        if case.closed_at is None:
            add(EvidenceRef("crm", case.case_id, "status", case.created_at))
    # Health has no standalone object id in the current contract; account id anchors it.
    if refs:
        add(EvidenceRef("cs_platform", account_id, "health_score", health_observed_at or as_of))
    return tuple(refs)


def _onboarding_activation_gap_evidence_refs(
    activation_gap_ids: tuple[str, ...],
    *,
    onboarding_phases: tuple[OnboardingPhase, ...],
    onboarding_tasks: tuple[OnboardingTask, ...],
    as_of: str,
) -> tuple[EvidenceRef, ...]:
    phase_by_id = {phase.phase_id: phase for phase in onboarding_phases}
    task_by_id = {task.task_id: task for task in onboarding_tasks}
    refs: list[EvidenceRef] = []
    for signal_id in activation_gap_ids:
        phase = phase_by_id.get(signal_id)
        if phase is not None:
            refs.append(EvidenceRef("rocketlane", phase.phase_id, "activation_gap", phase.due_date or as_of))
            continue
        task = task_by_id.get(signal_id)
        if task is not None:
            refs.append(EvidenceRef("rocketlane", task.task_id, "activation_gap", task.due_date or as_of))
    return tuple(refs)


def _priority(
    model: CustomerValueModel,
    *,
    company,
    health,
    open_gaps: tuple[TimeToValueMilestone, ...],
    overdue_plans: tuple,
    as_of: str,
    trajectory_factor: PriorityFactor | None = None,
    onboarding_evidence_ids: frozenset[str] = frozenset(),
    onboarding_activation_gap_ids: tuple[str, ...] = (),
    slot_a_classifications: tuple[CaseNoteClassificationOutput, ...] = (),
) -> Priority:
    projected = project_ttv_lens(
        model,
        company=company,
        health=health,
        open_milestone_gaps=open_gaps,
        overdue_success_plans=overdue_plans,
        as_of=as_of,
        onboarding_evidence_ids=onboarding_evidence_ids,
        onboarding_activation_gap_ids=onboarding_activation_gap_ids,
    )
    factors = tuple(
        factor for factor in projected.factors
        if factor.contribution != 0
    )
    if trajectory_factor is not None and trajectory_factor.contribution != 0:
        factors = (*factors, trajectory_factor)
    slot_a_factor = _slot_a_case_blocker_factor(
        model,
        slot_a_classifications=slot_a_classifications,
        as_of=as_of,
    )
    if slot_a_factor is not None:
        factors = (*factors, slot_a_factor)
    return Priority(
        score=sum(factor.contribution for factor in factors),
        factors=factors,
    )


def _slot_a_case_blocker_factor(
    model: CustomerValueModel,
    *,
    slot_a_classifications: tuple[CaseNoteClassificationOutput, ...],
    as_of: str,
) -> PriorityFactor | None:
    blockers = tuple(
        item for item in slot_a_classifications
        if item.classification == "blocker"
    )
    if not blockers:
        return None

    resolved = model.resolved_thresholds
    points = resolved.thresholds.slot_a_case_blocker_points
    evidence = tuple(
        EvidenceRef(
            "crm",
            item.cited_case_id or item.case_id,
            "slot_a_case_blocker",
            as_of,
        )
        for item in blockers
    )
    return PriorityFactor(
        name="slot_a_case_blocker",
        value=float(len(blockers)),
        contribution=len(blockers) * points,
        evidence=evidence,
        config_version=resolved.config_version,
        rule_name=resolved.rule_name,
        threshold_name="slot_a_case_blocker_points",
        threshold_value=points,
    )


def _trajectory_decline_evaluation(
    snapshot_store: SnapshotStore | None,
    *,
    account_id: str,
    model: CustomerValueModel,
) -> TrajectoryFactorEvaluation:
    if snapshot_store is None:
        return TrajectoryFactorEvaluation(state="unknown", factor=None)

    resolved = model.resolved_thresholds
    window_days = resolved.thresholds.trend_window_days
    trajectory = snapshot_store.build_trajectory(
        account_id,
        window_days=window_days,
    )
    if len(trajectory.points) < 2:
        return TrajectoryFactorEvaluation(state="unknown", factor=None)

    velocity = trajectory.trend_velocity
    threshold = resolved.thresholds.decline_slope
    if velocity >= threshold:
        return TrajectoryFactorEvaluation(state="known", factor=None)

    evidence = tuple(
        EvidenceRef(
            "cs_platform",
            account_id,
            f"snapshot_day_{point.day}_health_score",
            f"day:{point.day}",
        )
        for point in trajectory.points
    )
    return TrajectoryFactorEvaluation(
        state="known",
        factor=PriorityFactor(
            name="trajectory_decline",
            value=velocity,
            contribution=12,
            evidence=evidence,
            config_version=resolved.config_version,
            rule_name=resolved.rule_name,
            threshold_name="decline_slope",
            threshold_value=threshold,
        ),
    )


def _slot_b_request(
    *,
    tenant_id: str,
    account: CRMAccount,
    disposition: Disposition,
    action: CSMActionType,
    customer_contact_allowed: bool,
    evidence: tuple[EvidenceRef, ...],
    priority: Priority,
    as_of: str,
    contact: CRMContact | None,
    cases: tuple,
    org_context: dict | None = None,
) -> ReasonDraftRequest:
    return ReasonDraftRequest(
        tenant_id=tenant_id,
        account_id=account.account_id,
        account_name=account.name,
        disposition=disposition,
        recommended_action=action,
        customer_contact_allowed=customer_contact_allowed,
        priority=SlotBPriority(
            score=priority.score,
            factors=tuple(
                SlotBPriorityFactor(
                    factor.name,
                    factor.value,
                    factor.contribution,
                )
                for factor in priority.factors
            ),
        ),
        evidence=tuple(
            SlotBEvidence(ref.source, ref.source_id, ref.field, ref.observed_at)
            for ref in evidence
        ),
        as_of=as_of,
        contact_name=contact.name if contact else None,
        contact_email=contact.email if contact else None,
        untrusted_text_fragments=tuple(
            getattr(case, "subject", "")
            for case in cases
            if getattr(case, "subject", "")
        ),
        org_context=org_context,
    )


def _arr_score(data_plane: CustomerDataPlane, account_id: str) -> int:
    company = data_plane.cs.get_company(account_id)
    if company is None:
        return 0
    return int(company.arr_cents // 100_000)
