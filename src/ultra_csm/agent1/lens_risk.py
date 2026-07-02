"""Agent 1 Risk lens over the shared customer value model.

The lens is deterministic. Slot B prompt metadata is versioned here, but the
module makes no quality claim about generated wording without judge validation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from ultra_csm.agent1.lens_spec import LensSpec
from ultra_csm._util import iso_date
from ultra_csm.agent1.sweep import _trajectory_decline_evaluation
from ultra_csm.data_plane import CRMAccount, CustomerDataPlane, EvidenceRef
from ultra_csm.governance import ActionGate, ActionProposal, proposal_fields_for
from ultra_csm.governance.csm_actions import CSMActionType
from ultra_csm.snapshot_store import SnapshotStore
from ultra_csm.value_model import (
    CustomerValueModel,
    ValueFactor,
    build_customer_value_model,
)

RISK_LENS_VERSION = "agent1-risk-lens-v1"
RISK_SLOT_B_PROMPT_VERSION = "agent1-risk-slot-b-v1"
RISK_SLOT_B_PROMPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "prompts"
    / "agent1_slot_b_risk_v1.md"
)
RISK_LENS_SPEC = LensSpec(
    lens_id="risk",
    lens_version=RISK_LENS_VERSION,
    trigger_subscriptions=(
        "weekly_book_sweep",
        "renewal_window",
        "band_drop",
        "champion_inactive",
    ),
    factor_profile=(
        "trajectory_decline",
        "renewal_proximity_health_band",
        "champion_fragility",
        "engagement_collapse",
        "survey_detractor",
        "billing_friction",
        "open_support_pressure",
        "open_risk_cta",
        "overdue_success_plan",
    ),
    action_bindings=("recommend_next_best_action",),
    prompt_version=RISK_SLOT_B_PROMPT_VERSION,
    customer_facing=False,
    claim_boundary="deterministic risk findings only; no churn probability claim",
)


@dataclass(frozen=True)
class RiskLensWeights:
    health: float = 1.0
    support: float = 1.0
    shared_model: float = 1.0
    arr: float = 1.0
    trajectory: float = 1.0


@dataclass(frozen=True)
class RiskPriority:
    score: int
    factors: tuple[ValueFactor, ...]


@dataclass(frozen=True)
class RiskProposalRef:
    proposal_id: str
    status: str
    action_type: CSMActionType
    channel: str
    created_by_principal: str
    autonomy_tier: int
    required_permission: str


@dataclass(frozen=True)
class RiskLensItem:
    tenant_id: str
    account_id: str
    account_name: str
    disposition: str
    recommended_action: CSMActionType
    reason: str
    priority: RiskPriority
    evidence: tuple[EvidenceRef, ...]
    customer_contact_allowed: bool
    proposal: RiskProposalRef | None
    swept_at: str
    customer_draft: str | None = None


@dataclass(frozen=True)
class RiskLensResult:
    tenant_id: str
    lens_version: str
    work_items: tuple[RiskLensItem, ...]
    swept_accounts: tuple[str, ...]


def run_risk_lens(
    data_plane: CustomerDataPlane,
    tenant_id: str,
    gate: ActionGate,
    *,
    sweep_principal_id: str,
    as_of: str,
    snapshot_store: SnapshotStore | None = None,
    weights: RiskLensWeights | None = None,
) -> RiskLensResult:
    """Project churn/contraction risk as internal-only next-best actions."""

    lens_weights = weights or RiskLensWeights()
    accounts = tuple(data_plane.crm.list_accounts(tenant_id=tenant_id))
    items: list[RiskLensItem] = []
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

    return RiskLensResult(
        tenant_id=tenant_id,
        lens_version=RISK_LENS_VERSION,
        work_items=tuple(sorted(
            items,
            key=lambda item: (item.priority.score, item.account_name),
            reverse=True,
        )),
        swept_accounts=tuple(account.account_id for account in accounts),
    )


def unsafe_placeholder_risk_lens(
    data_plane: CustomerDataPlane,
    tenant_id: str,
    gate: ActionGate,
    *,
    sweep_principal_id: str,
    as_of: str,
) -> RiskLensResult:
    """Deliberately unsafe foil. Scorecards must reject this runner."""

    accounts = tuple(data_plane.crm.list_accounts())
    items: list[RiskLensItem] = []
    for account in accounts:
        action: CSMActionType = "initiate_customer_call"
        proposal = gate.propose(
            intent="unsafe_risk_placeholder",
            payload={
                "account_id": account.account_id,
                "subject": "Churn emergency",
                "body": "Fabricated customer escalation without evidence.",
            },
            grounding_ref=f"unsafe-risk:{account.account_id}",
            cause_ref=f"unsafe-risk:{account.account_id}:{as_of}",
            **proposal_fields_for(action),
        )
        factor = ValueFactor(
            name="arr_only_risk",
            value=999.0,
            contribution=999,
            evidence=(),
            config_version="unsafe-placeholder",
            rule_name="unsafe",
            threshold_name=None,
            threshold_value=None,
        )
        items.append(RiskLensItem(
            tenant_id=tenant_id,
            account_id=account.account_id,
            account_name=account.name,
            disposition="propose_customer_action",
            recommended_action=action,
            reason="Declare churn risk from fabricated urgency.",
            priority=RiskPriority(999, (factor,)),
            evidence=(),
            customer_contact_allowed=True,
            proposal=RiskProposalRef(
                proposal_id=proposal.proposal_id,
                status="approved",
                action_type=action,
                channel="call",
                created_by_principal=sweep_principal_id,
                autonomy_tier=proposal.autonomy_tier,
                required_permission=proposal.required_permission,
            ),
            swept_at=as_of,
            customer_draft="We must escalate immediately.",
        ))
    return RiskLensResult(
        tenant_id=tenant_id,
        lens_version=RISK_LENS_VERSION,
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
    weights: RiskLensWeights,
) -> RiskLensItem | None:
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
    model = build_customer_value_model(
        account=account,
        company=company,
        health=health,
        adoption=adoption,
        entitlements=entitlements,
        usage_signals=signals,
        success_plans=plans,
    )
    trajectory = _trajectory_decline_evaluation(
        snapshot_store,
        account_id=account.account_id,
        model=model,
    )
    factors = _risk_factors(
        model,
        account=account,
        arr_cents=company.arr_cents,
        arr_observed_at=company.original_contract_date,
        health_band=health.band,
        health_observed_at=health.measured_at,
        ctas=ctas,
        plans=plans,
        cases=cases,
        as_of=as_of,
        trajectory_factor=trajectory.factor,
        weights=weights,
    )
    if not factors:
        return None

    priority = RiskPriority(
        score=sum(factor.contribution for factor in factors),
        factors=factors,
    )
    evidence = _evidence_from_factors(factors)
    if not evidence:
        return None

    action: CSMActionType = "recommend_next_best_action"
    proposal = _propose_internal_recommendation(
        gate,
        account=account,
        action=action,
        priority=priority,
        evidence=evidence,
        as_of=as_of,
    )
    return RiskLensItem(
        tenant_id=tenant_id,
        account_id=account.account_id,
        account_name=account.name,
        disposition="internal_review",
        recommended_action=action,
        reason=_reason(account.name, priority, evidence),
        priority=priority,
        evidence=evidence,
        customer_contact_allowed=False,
        proposal=_proposal_ref(
            proposal,
            action=action,
            principal_id=sweep_principal_id,
            channel="internal",
        ),
        swept_at=as_of,
        customer_draft=None,
    )


def _risk_factors(
    model: CustomerValueModel,
    *,
    account: CRMAccount,
    arr_cents: int,
    arr_observed_at: str,
    health_band: str,
    health_observed_at: str,
    ctas: tuple,
    plans: tuple,
    cases: tuple,
    as_of: str,
    trajectory_factor: ValueFactor | None,
    weights: RiskLensWeights,
) -> tuple[ValueFactor, ...]:
    resolved = model.resolved_thresholds
    thresholds = resolved.thresholds
    factors: list[ValueFactor] = []

    if health_band in {"red", "yellow"}:
        base = thresholds.health_red_points if health_band == "red" else thresholds.health_yellow_points
        factors.append(_factor(
            "health_red" if health_band == "red" else "health_yellow",
            1.0,
            base,
            (EvidenceRef("cs_platform", account.account_id, "health_score", health_observed_at),),
            model,
            weights.health,
            "health_red_points" if health_band == "red" else "health_yellow_points",
            base,
        ))

    open_cases = tuple(case for case in cases if case.closed_at is None)
    if open_cases:
        high_priority = sum(1 for case in open_cases if case.priority.lower() == "high")
        base = 18 + (6 * high_priority)
        factors.append(_factor(
            "open_support_pressure",
            float(len(open_cases)),
            base,
            tuple(
                EvidenceRef("crm", case.case_id, "status", case.created_at)
                for case in open_cases
            ),
            model,
            weights.support,
            None,
            None,
        ))

    if ctas:
        factors.append(_factor(
            "open_risk_cta",
            float(len(ctas)),
            8 * len(ctas),
            tuple(EvidenceRef("cs_platform", cta.cta_id, "due_date", cta.due_date) for cta in ctas),
            model,
            weights.support,
            None,
            None,
        ))

    overdue_plans = tuple(plan for plan in plans if iso_date(plan.target_date) <= iso_date(as_of))
    if overdue_plans:
        factors.append(_factor(
            "overdue_success_plan",
            float(len(overdue_plans)),
            thresholds.success_plan_overdue_points * len(overdue_plans),
            tuple(
                EvidenceRef("cs_platform", plan.plan_id, "target_date", plan.target_date)
                for plan in overdue_plans
            ),
            model,
            weights.support,
            "success_plan_overdue_points",
            thresholds.success_plan_overdue_points,
        ))

    if arr_cents >= thresholds.arr_review_floor_cents:
        factors.append(_factor(
            "arr_risk_exposure",
            float(arr_cents),
            6,
            (EvidenceRef("cs_platform", account.account_id, "arr_cents", arr_observed_at),),
            model,
            weights.arr,
            "arr_review_floor_cents",
            thresholds.arr_review_floor_cents,
        ))

    shared = (
        *model.penetration.factors,
        *model.feature_depth.factors,
        *model.divergences,
    )
    for factor in shared:
        if factor.contribution > 0 and factor.evidence:
            factors.append(_scale_factor(factor, weights.shared_model))

    if trajectory_factor is not None:
        factors.append(_scale_factor(trajectory_factor, weights.trajectory))

    return tuple(factor for factor in factors if factor.contribution > 0 and factor.evidence)


def _propose_internal_recommendation(
    gate: ActionGate,
    *,
    account: CRMAccount,
    action: CSMActionType,
    priority: RiskPriority,
    evidence: tuple[EvidenceRef, ...],
    as_of: str,
) -> ActionProposal:
    payload = {
        "account_id": account.account_id,
        "account_name": account.name,
        "as_of": as_of,
        "subject": f"Risk next-best action for {account.name}",
        "priority": _priority_payload(priority),
        "evidence_ids": [ref.source_id for ref in evidence],
        "claim_boundary": "deterministic risk lens; no Slot-B quality claim",
    }
    return gate.propose(
        intent="agent1_risk_lens",
        payload=payload,
        grounding_ref=f"risk:{account.account_id}:{as_of}",
        cause_ref=f"agent1:risk:{account.account_id}:{as_of}",
        **proposal_fields_for(action),
    )


def _proposal_ref(
    proposal: ActionProposal,
    *,
    action: CSMActionType,
    principal_id: str,
    channel: str,
) -> RiskProposalRef:
    return RiskProposalRef(
        proposal_id=proposal.proposal_id,
        status=proposal.status,
        action_type=action,
        channel=channel,
        created_by_principal=principal_id,
        autonomy_tier=proposal.autonomy_tier,
        required_permission=proposal.required_permission,
    )


def _priority_payload(priority: RiskPriority) -> dict:
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
    priority: RiskPriority,
    evidence: tuple[EvidenceRef, ...],
) -> str:
    drivers = ", ".join(
        f"{factor.name}={factor.contribution}"
        for factor in priority.factors[:3]
    )
    refs = ", ".join(f"[evidence:{ref.source_id}]" for ref in evidence[:3])
    return f"{account_name} Risk score {priority.score} from {drivers}. Evidence {refs}."
