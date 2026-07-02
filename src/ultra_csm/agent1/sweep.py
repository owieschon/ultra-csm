"""Book-sweep work queue for Agent 1 Time-to-Value triage."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Literal

from ultra_csm._util import compact_asdict, iso_date
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
from ultra_csm.data_plane import (
    CRMAccount,
    CRMContact,
    CustomerDataPlane,
    EvidenceRef,
    TimeToValueMilestone,
)
from ultra_csm.data_plane.contracts import ResolutionState
from ultra_csm.governance import ActionGate, ActionProposal, proposal_fields_for
from ultra_csm.governance.csm_actions import CSMActionType
from ultra_csm.knowledge import load_org_pack
from ultra_csm.quality_breaker import (
    QualityBreakerConfig,
    QualityBreakerDecision,
    evaluate_quality_breaker,
)
from ultra_csm.value_model import (
    CustomerValueModel,
    ValueFactor,
    build_customer_value_model,
    project_ttv_lens,
)

if TYPE_CHECKING:
    from ultra_csm.cost_tracker import CostBudget, CostTracker

log = logging.getLogger(__name__)

Disposition = Literal["propose_customer_action", "internal_review", "escalate"]
ProposalStatus = Literal["pending", "approved", "denied"]
PriorityFactor = ValueFactor
DraftMode = Literal["fixture", "live", "template_fallback", "none"]


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


@dataclass
class _SweepTimingAccum:
    """Mutable accumulator for sweep phase timing (internal)."""

    value_model_ms: float = 0.0
    slot_b_ms: float = 0.0
    slot_b_calls: int = 0
    governance_ms: float = 0.0


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
) -> SweepResult:
    """Run Agent 1 across a tenant book and emit a deterministic work queue."""

    from ultra_csm.cost_tracker import estimate_call_cost

    sweep_start = time.perf_counter()
    writer = reason_draft_writer or FixtureReasonDraftWriter()
    slot_b_org_context = (
        org_context
        if org_context is not None
        else load_org_pack().slot_b_context()
    )
    breaker_decision = (
        evaluate_quality_breaker(quality_breaker)
        if quality_breaker is not None
        else None
    )

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
            org_context=slot_b_org_context,
            timing=timing,
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
    timing: _SweepTimingAccum | None = None,
) -> CSMWorkItem | None:
    company = data_plane.cs.get_company(account.account_id)
    health = data_plane.cs.get_health_score(account.account_id)
    adoption = data_plane.cs.get_adoption_summary(account.account_id)
    if company is None or health is None or adoption is None:
        return None

    ctas = tuple(data_plane.cs.list_ctas(account.account_id, status="open"))
    plans = tuple(data_plane.cs.list_success_plans(account.account_id))
    cases = tuple(data_plane.crm.list_cases(account.account_id))
    signals = tuple(data_plane.telemetry.list_usage_signals(account.account_id))
    entitlements = tuple(data_plane.telemetry.list_entitlements(account.account_id))
    signal_ids = {signal.signal_id for signal in signals}
    milestones = tuple(data_plane.telemetry.list_ttv_milestones(account.account_id))
    open_gaps = tuple(
        milestone for milestone in milestones
        if milestone.achieved_at is None and iso_date(milestone.expected_by) <= iso_date(as_of)
    )
    telemetry_backed_gaps = tuple(
        milestone for milestone in open_gaps
        if any(signal_id in signal_ids for signal_id in milestone.evidence_signal_ids)
    )
    overdue_plans = tuple(plan for plan in plans if iso_date(plan.target_date) <= iso_date(as_of))

    evidence = _evidence_refs(
        account.account_id,
        as_of=as_of,
        open_gaps=telemetry_backed_gaps,
        signals=signals,
        ctas=ctas,
        plans=overdue_plans,
        cases=cases,
        health_observed_at=health.measured_at,
    )
    if not evidence:
        return None

    value_start = time.perf_counter()
    model = build_customer_value_model(
        account=account,
        company=company,
        health=health,
        adoption=adoption,
        entitlements=entitlements,
        usage_signals=signals,
        success_plans=plans,
    )
    priority = _priority(
        model,
        company=company,
        health=health,
        open_gaps=telemetry_backed_gaps,
        overdue_plans=overdue_plans,
        as_of=as_of,
    )
    if timing is not None:
        timing.value_model_ms += (time.perf_counter() - value_start) * 1000.0
    if priority.score <= 0:
        return None

    contact = next((contact for contact in contacts if contact.consent_to_contact), None)
    customer_contact_allowed = contact is not None
    customer_action_blocked = (
        customer_contact_allowed
        and quality_breaker is not None
        and quality_breaker.triggered
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
    slot_b_request = _slot_b_request(
        tenant_id=tenant_id,
        account=account,
        disposition=disposition,
        action=action,
        customer_contact_allowed=customer_contact_allowed and not customer_action_blocked,
        priority=priority,
        evidence=evidence,
        as_of=as_of,
        contact=contact if not customer_action_blocked else None,
        cases=cases,
        org_context=org_context,
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
            evidence=evidence,
            priority=priority,
            draft_body=slot_b.customer_draft,
        )
        if timing is not None:
            timing.governance_ms += (time.perf_counter() - governance_start) * 1000.0
        proposal_ref = _proposal_ref(proposal, action=action, principal_id=sweep_principal_id)

    return CSMWorkItem(
        tenant_id=tenant_id,
        account_resolution="exactly_one",
        account_id=account.account_id,
        candidate_account_ids=(),
        disposition=disposition,
        recommended_action=action,
        reason=slot_b.reason,
        priority=priority,
        evidence=evidence,
        customer_contact_allowed=customer_contact_allowed,
        proposal=proposal_ref,
        swept_at=as_of,
        draft_mode=draft_mode,
        customer_draft=slot_b.customer_draft,
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
    return gate.propose(
        intent="agent1_time_to_value_sweep",
        payload=payload,
        grounding_ref=f"sweep:{account.account_id}:{as_of}",
        cause_ref=f"agent1:sweep:{account.account_id}:{as_of}",
        **proposal_fields_for(action),
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
) -> CSMWorkItem:
    evidence = tuple(
        EvidenceRef("crm", contact.contact_id, "email", as_of)
        for contact in contacts
    )
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
) -> tuple[EvidenceRef, ...]:
    signal_by_id = {signal.signal_id: signal for signal in signals}
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


def _priority(
    model: CustomerValueModel,
    *,
    company,
    health,
    open_gaps: tuple[TimeToValueMilestone, ...],
    overdue_plans: tuple,
    as_of: str,
) -> Priority:
    projected = project_ttv_lens(
        model,
        company=company,
        health=health,
        open_milestone_gaps=open_gaps,
        overdue_success_plans=overdue_plans,
        as_of=as_of,
    )
    return Priority(
        score=projected.score,
        factors=tuple(factor for factor in projected.factors if factor.contribution != 0),
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
