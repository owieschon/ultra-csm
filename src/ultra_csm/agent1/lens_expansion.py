"""Agent 1 Expansion lens over the shared customer value model.

The lens is deterministic. Slot B prompt metadata is versioned here, but the
module makes no quality claim about generated wording without judge validation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from ultra_csm.agent1.lens_spec import LensSpec
from ultra_csm.data_plane import (
    CRMAccount,
    CRMContact,
    CRMOpportunity,
    CustomerDataPlane,
    EvidenceRef,
)
from ultra_csm.governance import ActionGate, ActionProposal, proposal_fields_for
from ultra_csm.governance.csm_actions import CSMActionType
from ultra_csm.snapshot_store import SnapshotStore
from ultra_csm.value_model import (
    CustomerValueModel,
    ValueFactor,
    build_customer_value_model,
)

EXPANSION_LENS_VERSION = "agent1-expansion-lens-v1"
EXPANSION_SLOT_B_PROMPT_VERSION = "agent1-expansion-slot-b-v1"
EXPANSION_SLOT_B_PROMPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "prompts"
    / "agent1_slot_b_expansion_v1.md"
)
EXPANSION_LENS_SPEC = LensSpec(
    lens_id="expansion",
    lens_version=EXPANSION_LENS_VERSION,
    trigger_subscriptions=(
        "weekly_book_sweep",
        "renewal_window",
        "band_drop",
        "hold_released",
    ),
    factor_profile=(
        "sustained_healthy_trajectory",
        "consumption_vs_entitlement",
        "new_function_activity",
        "unrealized_value_prop",
        "overage_signal",
        "open_expansion_opportunity",
        "expansion_readiness_high_adoption",
        "arr_expansion_surface",
    ),
    action_bindings=("initiate_customer_call",),
    prompt_version=EXPANSION_SLOT_B_PROMPT_VERSION,
    customer_facing=True,
    claim_boundary="deterministic expansion findings only; customer action precedence-gated",
)


@dataclass(frozen=True)
class ExpansionLensWeights:
    opportunity: float = 1.0
    shared_model: float = 1.0
    customer_readiness: float = 1.0
    arr: float = 1.0
    trajectory: float = 1.0


@dataclass(frozen=True)
class ExpansionPriority:
    score: int
    factors: tuple[ValueFactor, ...]


@dataclass(frozen=True)
class ExpansionProposalRef:
    proposal_id: str
    status: str
    action_type: CSMActionType
    channel: str
    created_by_principal: str
    autonomy_tier: int
    required_permission: str


@dataclass(frozen=True)
class ExpansionLensItem:
    tenant_id: str
    account_id: str
    account_name: str
    contact_id: str
    disposition: str
    recommended_action: CSMActionType
    reason: str
    priority: ExpansionPriority
    evidence: tuple[EvidenceRef, ...]
    customer_contact_allowed: bool
    proposal: ExpansionProposalRef | None
    swept_at: str
    customer_draft: str | None = None


@dataclass(frozen=True)
class ExpansionLensResult:
    tenant_id: str
    lens_version: str
    work_items: tuple[ExpansionLensItem, ...]
    swept_accounts: tuple[str, ...]


def run_expansion_lens(
    data_plane: CustomerDataPlane,
    tenant_id: str,
    gate: ActionGate,
    *,
    sweep_principal_id: str,
    as_of: str,
    snapshot_store: SnapshotStore | None = None,
    weights: ExpansionLensWeights | None = None,
) -> ExpansionLensResult:
    """Project expansion candidates through the strictest customer-facing tier."""

    lens_weights = weights or ExpansionLensWeights()
    accounts = tuple(data_plane.crm.list_accounts(tenant_id=tenant_id))
    items: list[ExpansionLensItem] = []
    for account in accounts:
        item = _item_for_account(
            data_plane,
            account,
            tenant_id=tenant_id,
            gate=gate,
            sweep_principal_id=sweep_principal_id,
            as_of=as_of,
            snapshot_store=snapshot_store,
            weights=lens_weights,
        )
        if item is not None:
            items.append(item)

    return ExpansionLensResult(
        tenant_id=tenant_id,
        lens_version=EXPANSION_LENS_VERSION,
        work_items=tuple(sorted(
            items,
            key=lambda item: (item.priority.score, item.account_name),
            reverse=True,
        )),
        swept_accounts=tuple(account.account_id for account in accounts),
    )


def unsafe_placeholder_expansion_lens(
    data_plane: CustomerDataPlane,
    tenant_id: str,
    gate: ActionGate,
    *,
    sweep_principal_id: str,
    as_of: str,
) -> ExpansionLensResult:
    """Deliberately unsafe foil. Scorecards must reject this runner."""

    accounts = tuple(data_plane.crm.list_accounts())
    items: list[ExpansionLensItem] = []
    for account in accounts:
        action: CSMActionType = "draft_customer_outreach"
        proposal = gate.propose(
            intent="unsafe_expansion_placeholder",
            payload={
                "account_id": account.account_id,
                "subject": "Expansion now",
                "body": "Fabricated expansion urgency without evidence.",
            },
            grounding_ref=f"unsafe-expansion:{account.account_id}",
            cause_ref=f"unsafe-expansion:{account.account_id}:{as_of}",
            **proposal_fields_for(action),
        )
        factor = ValueFactor(
            name="arr_only_expansion",
            value=999.0,
            contribution=999,
            evidence=(),
            config_version="unsafe-placeholder",
            rule_name="unsafe",
            threshold_name=None,
            threshold_value=None,
        )
        items.append(ExpansionLensItem(
            tenant_id=tenant_id,
            account_id=account.account_id,
            account_name=account.name,
            contact_id="unsafe-contact",
            disposition="propose_customer_action",
            recommended_action=action,
            reason="Pitch expansion immediately from fabricated upside.",
            priority=ExpansionPriority(999, (factor,)),
            evidence=(),
            customer_contact_allowed=True,
            proposal=ExpansionProposalRef(
                proposal_id=proposal.proposal_id,
                status="approved",
                action_type=action,
                channel="email",
                created_by_principal=sweep_principal_id,
                autonomy_tier=proposal.autonomy_tier,
                required_permission=proposal.required_permission,
            ),
            swept_at=as_of,
            customer_draft="Please approve a larger contract today.",
        ))
    return ExpansionLensResult(
        tenant_id=tenant_id,
        lens_version=EXPANSION_LENS_VERSION,
        work_items=tuple(sorted(
            items,
            key=lambda item: (item.priority.score, item.account_name),
            reverse=True,
        )),
        swept_accounts=tuple(account.account_id for account in accounts),
    )


def _item_for_account(
    data_plane: CustomerDataPlane,
    account: CRMAccount,
    *,
    tenant_id: str,
    gate: ActionGate,
    sweep_principal_id: str,
    as_of: str,
    snapshot_store: SnapshotStore | None,
    weights: ExpansionLensWeights,
) -> ExpansionLensItem | None:
    contact = _exact_consent_contact(data_plane, account)
    if contact is None:
        return None

    company = data_plane.cs.get_company(account.account_id)
    health = data_plane.cs.get_health_score(account.account_id)
    adoption = data_plane.cs.get_adoption_summary(account.account_id)
    if company is None or health is None or adoption is None:
        return None

    entitlements = tuple(data_plane.telemetry.list_entitlements(account.account_id))
    signals = tuple(data_plane.telemetry.list_usage_signals(account.account_id))
    plans = tuple(data_plane.cs.list_success_plans(account.account_id))
    opportunities = tuple(data_plane.crm.list_opportunities(account.account_id))
    model = build_customer_value_model(
        account=account,
        company=company,
        health=health,
        adoption=adoption,
        entitlements=entitlements,
        usage_signals=signals,
        success_plans=plans,
    )
    factors = _expansion_factors(
        model,
        account=account,
        arr_cents=company.arr_cents,
        arr_observed_at=company.original_contract_date,
        adoption_measured_at=adoption.measured_at,
        opportunities=opportunities,
        snapshot_store=snapshot_store,
        weights=weights,
    )
    if not factors:
        return None

    priority = ExpansionPriority(
        score=sum(factor.contribution for factor in factors),
        factors=factors,
    )
    evidence = _evidence_from_factors(factors)
    if not evidence:
        return None

    action: CSMActionType = "initiate_customer_call"
    proposal = _propose_expansion_call(
        gate,
        account=account,
        contact=contact,
        action=action,
        priority=priority,
        evidence=evidence,
        as_of=as_of,
    )
    return ExpansionLensItem(
        tenant_id=tenant_id,
        account_id=account.account_id,
        account_name=account.name,
        contact_id=contact.contact_id,
        disposition="propose_customer_action",
        recommended_action=action,
        reason=_reason(account.name, "Expansion", priority, evidence),
        priority=priority,
        evidence=evidence,
        customer_contact_allowed=True,
        proposal=_proposal_ref(
            proposal,
            action=action,
            principal_id=sweep_principal_id,
            channel="call",
        ),
        swept_at=as_of,
        customer_draft=None,
    )


def _expansion_factors(
    model: CustomerValueModel,
    *,
    account: CRMAccount,
    arr_cents: int,
    arr_observed_at: str,
    adoption_measured_at: str,
    opportunities: tuple[CRMOpportunity, ...],
    snapshot_store: SnapshotStore | None,
    weights: ExpansionLensWeights,
) -> tuple[ValueFactor, ...]:
    resolved = model.resolved_thresholds
    factors: list[ValueFactor] = []

    expansion_opps = tuple(
        opp for opp in opportunities
        if opp.opportunity_type.lower() == "expansion"
    )
    if expansion_opps:
        evidence = tuple(
            EvidenceRef("crm", opp.opportunity_id, "opportunity_type", opp.close_date)
            for opp in expansion_opps
        )
        factors.append(_factor(
            "open_expansion_opportunity",
            float(sum(opp.amount_cents for opp in expansion_opps)),
            28,
            evidence,
            model,
            weights.opportunity,
            None,
            None,
        ))

    if model.usage.adoption_rate is not None and model.usage.adoption_rate >= 0.75:
        factors.append(_factor(
            "expansion_readiness_high_adoption",
            model.usage.adoption_rate,
            10,
            (EvidenceRef(
                "cs_platform",
                account.account_id,
                "adoption_rate",
                adoption_measured_at,
            ),),
            model,
            weights.customer_readiness,
            "outcome_activity_floor",
            resolved.thresholds.outcome_activity_floor,
        ))

    if arr_cents >= resolved.thresholds.arr_review_floor_cents:
        factors.append(_factor(
            "arr_expansion_surface",
            float(arr_cents),
            20,
            (EvidenceRef("cs_platform", account.account_id, "arr_cents", arr_observed_at),),
            model,
            weights.arr,
            "arr_review_floor_cents",
            resolved.thresholds.arr_review_floor_cents,
        ))

    shared = (
        *model.feature_depth.factors,
        *(
            factor for factor in model.divergences
            if factor.name == "usage_outcome_unverified"
        ),
    )
    for factor in shared:
        if factor.contribution > 0 and factor.evidence:
            factors.append(_scale_factor(factor, weights.shared_model))

    trajectory = _trajectory_improvement_factor(
        snapshot_store,
        account_id=account.account_id,
        model=model,
    )
    if trajectory is not None:
        factors.append(_scale_factor(trajectory, weights.trajectory))

    return tuple(factor for factor in factors if factor.contribution > 0 and factor.evidence)


def _trajectory_improvement_factor(
    snapshot_store: SnapshotStore | None,
    *,
    account_id: str,
    model: CustomerValueModel,
) -> ValueFactor | None:
    if snapshot_store is None:
        return None
    resolved = model.resolved_thresholds
    trajectory = snapshot_store.build_trajectory(
        account_id,
        window_days=resolved.thresholds.trend_window_days,
    )
    if len(trajectory.points) < 2:
        return None
    threshold = abs(resolved.thresholds.decline_slope)
    if trajectory.trend_velocity <= threshold:
        return None
    evidence = tuple(
        EvidenceRef(
            "cs_platform",
            account_id,
            f"snapshot_day_{point.day}_health_score",
            f"day:{point.day}",
        )
        for point in trajectory.points
    )
    return ValueFactor(
        name="trajectory_improvement",
        value=trajectory.trend_velocity,
        contribution=10,
        evidence=evidence,
        config_version=resolved.config_version,
        rule_name=resolved.rule_name,
        threshold_name="decline_slope_abs",
        threshold_value=threshold,
    )


def _exact_consent_contact(
    data_plane: CustomerDataPlane,
    account: CRMAccount,
) -> CRMContact | None:
    for contact in data_plane.crm.list_contacts(account.account_id):
        if not contact.consent_to_contact:
            continue
        resolution = data_plane.crm.resolve_account_by_email(contact.email)
        if resolution.state == "exactly_one" and resolution.account_id == account.account_id:
            return contact
    return None


def _propose_expansion_call(
    gate: ActionGate,
    *,
    account: CRMAccount,
    contact: CRMContact,
    action: CSMActionType,
    priority: ExpansionPriority,
    evidence: tuple[EvidenceRef, ...],
    as_of: str,
) -> ActionProposal:
    payload = {
        "account_id": account.account_id,
        "account_name": account.name,
        "contact_id": contact.contact_id,
        "contact_email": contact.email,
        "as_of": as_of,
        "subject": f"Expansion discovery call for {account.name}",
        "priority": _priority_payload(priority),
        "evidence_ids": [ref.source_id for ref in evidence],
        "claim_boundary": "deterministic expansion lens; no Slot-B quality claim",
    }
    if action == "draft_customer_outreach":
        gate.record_outreach_contact_ref(
            account_ref=account.account_id,
            contact_ref=contact.contact_id,
            email=contact.email,
            name=contact.name,
            consent=contact.consent_to_contact,
            cause_ref=f"agent1:expansion:{account.account_id}:{as_of}:contact-consent",
        )
    return gate.propose(
        intent="agent1_expansion_lens",
        payload=payload,
        grounding_ref=f"expansion:{account.account_id}:{as_of}",
        cause_ref=f"agent1:expansion:{account.account_id}:{as_of}",
        **proposal_fields_for(action),
    )


def _proposal_ref(
    proposal: ActionProposal,
    *,
    action: CSMActionType,
    principal_id: str,
    channel: str,
) -> ExpansionProposalRef:
    return ExpansionProposalRef(
        proposal_id=proposal.proposal_id,
        status=proposal.status,
        action_type=action,
        channel=channel,
        created_by_principal=principal_id,
        autonomy_tier=proposal.autonomy_tier,
        required_permission=proposal.required_permission,
    )


def _priority_payload(priority: ExpansionPriority) -> dict:
    return {
        "score": priority.score,
        "factors": [
            {
                "name": factor.name,
                "value": factor.value,
                "contribution": factor.contribution,
                "evidence_ids": [ref.source_id for ref in factor.evidence],
            }
            for factor in priority.factors
        ],
    }


def _factor(
    name: str,
    value: float,
    base_contribution: int,
    evidence: tuple[EvidenceRef, ...],
    model: CustomerValueModel,
    weight: float,
    threshold_name: str | None,
    threshold_value: float | int | None,
) -> ValueFactor:
    resolved = model.resolved_thresholds
    return ValueFactor(
        name=name,
        value=value,
        contribution=max(0, int(round(base_contribution * weight))),
        evidence=evidence,
        config_version=resolved.config_version,
        rule_name=resolved.rule_name,
        threshold_name=threshold_name,
        threshold_value=threshold_value,
    )


def _scale_factor(factor: ValueFactor, weight: float) -> ValueFactor:
    return replace(
        factor,
        contribution=max(0, int(round(factor.contribution * weight))),
    )


def _evidence_from_factors(factors: tuple[ValueFactor, ...]) -> tuple[EvidenceRef, ...]:
    seen: set[tuple[str, str, str]] = set()
    refs: list[EvidenceRef] = []
    for factor in factors:
        for ref in factor.evidence:
            key = (ref.source, ref.source_id, ref.field)
            if key not in seen:
                refs.append(ref)
                seen.add(key)
    return tuple(refs)


def _reason(
    account_name: str,
    lens_name: str,
    priority: ExpansionPriority,
    evidence: tuple[EvidenceRef, ...],
) -> str:
    drivers = ", ".join(
        f"{factor.name}={factor.contribution}"
        for factor in priority.factors[:3]
    )
    refs = ", ".join(f"[evidence:{ref.source_id}]" for ref in evidence[:3])
    return f"{account_name} {lens_name} score {priority.score} from {drivers}. Evidence {refs}."
