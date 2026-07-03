"""Deterministic customer value model shared by CSM lenses."""

from __future__ import annotations

import json
import operator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ultra_csm._util import iso_date
from ultra_csm.data_plane.contracts import (
    AdoptionSummary,
    CRMAccount,
    CSCompany,
    Entitlement,
    EvidenceRef,
    HealthScore,
    LifecycleStage,
    SuccessPlan,
    TimeToValueMilestone,
    UsageSignal,
)

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO / "config" / "value_model_config.json"

PredicateOp = Literal[">=", ">", "<=", "<", "==", "!=", "in"]
RailState = Literal["known", "unknown"]
OutcomeState = Literal["known", "unknown", "not_instrumented"]

ACCOUNT_MATCH_FIELDS = frozenset({
    "account_id",
    "account_name",
    "owner_id",
    "industry",
    "arr_cents",
    "lifecycle_stage",
    "status",
    "current_score",
})


@dataclass(frozen=True)
class Thresholds:
    adoption_floor: float
    depth_floor: float
    seat_penetration_floor: float
    outcome_activity_floor: float
    decline_slope: float
    concentration_ceiling: float
    min_threaded_persons: int
    min_seats_for_risk: int
    activation_window_days: int
    trend_window_days: int
    milestone_overdue_points: int
    days_overdue_points: int
    days_overdue_cap: int
    success_plan_overdue_points: int
    health_red_points: int
    health_yellow_points: int
    arr_review_floor_cents: int
    arr_review_points: int


@dataclass(frozen=True)
class MatchPredicate:
    field: str
    op: PredicateOp
    value: float | int | str | tuple[float | int | str, ...]


@dataclass(frozen=True)
class ConfigRule:
    name: str
    match: tuple[MatchPredicate, ...]
    thresholds: Thresholds


@dataclass(frozen=True)
class ValueModelConfig:
    config_version: str
    rules: tuple[ConfigRule, ...]


@dataclass(frozen=True)
class ResolvedThresholds:
    config_version: str
    rule_name: str
    thresholds: Thresholds


@dataclass(frozen=True)
class ValueFactor:
    name: str
    value: float
    contribution: int
    evidence: tuple[EvidenceRef, ...]
    config_version: str
    rule_name: str
    threshold_name: str | None
    threshold_value: float | int | None


@dataclass(frozen=True)
class UsageRail:
    adoption_rate: float | None
    active_users: int | None
    licensed_users: int | None
    underused_capabilities: tuple[str, ...]
    factors: tuple[ValueFactor, ...]


@dataclass(frozen=True)
class PenetrationRail:
    seat_penetration: float | None
    active_users: int | None
    licensed_users: int | None
    state: RailState
    factors: tuple[ValueFactor, ...]


@dataclass(frozen=True)
class FeatureDepthRail:
    entitled_capabilities: tuple[str, ...]
    underused_capabilities: tuple[str, ...]
    factors: tuple[ValueFactor, ...]


@dataclass(frozen=True)
class OutcomeRail:
    stated_objectives: tuple[str, ...]
    realized_state: OutcomeState
    factors: tuple[ValueFactor, ...]


@dataclass(frozen=True)
class CustomerValueModel:
    account_id: str
    lifecycle_stage: LifecycleStage
    resolved_thresholds: ResolvedThresholds
    usage: UsageRail
    penetration: PenetrationRail
    feature_depth: FeatureDepthRail
    outcome: OutcomeRail
    divergences: tuple[ValueFactor, ...]

    @property
    def ttv_factors(self) -> tuple[ValueFactor, ...]:
        return (
            *self.penetration.factors,
            *self.feature_depth.factors,
            *self.divergences,
        )


@dataclass(frozen=True)
class ProjectedPriority:
    score: int
    factors: tuple[ValueFactor, ...]


class ConfigValidationError(ValueError):
    pass


_OPS = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}


def load_value_model_config(path: Path = DEFAULT_CONFIG_PATH) -> ValueModelConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rules = tuple(_parse_rule(item) for item in raw["rules"])
    config = ValueModelConfig(config_version=raw["config_version"], rules=rules)
    validate_config(config)
    return config


def validate_config(config: ValueModelConfig) -> None:
    base_rules = [rule for rule in config.rules if not rule.match]
    if len(base_rules) != 1:
        raise ConfigValidationError("ValueModelConfig requires exactly one empty-match base rule")
    seen_names: set[str] = set()
    for rule in config.rules:
        if rule.name in seen_names:
            raise ConfigValidationError(f"duplicate config rule name: {rule.name}")
        seen_names.add(rule.name)
        for predicate in rule.match:
            if predicate.field not in ACCOUNT_MATCH_FIELDS:
                raise ConfigValidationError(f"unknown match field: {predicate.field}")
            if predicate.op not in (*_OPS.keys(), "in"):
                raise ConfigValidationError(f"unsupported predicate op: {predicate.op}")


def resolve_thresholds(
    attrs: dict[str, Any],
    config: ValueModelConfig,
) -> ResolvedThresholds:
    validate_config(config)
    matches = [
        (index, rule) for index, rule in enumerate(config.rules)
        if _rule_matches(rule, attrs)
    ]
    if not matches:
        raise ConfigValidationError("no value-model config rule matched")
    _, selected = max(matches, key=lambda pair: (len(pair[1].match), -pair[0]))
    return ResolvedThresholds(
        config_version=config.config_version,
        rule_name=selected.name,
        thresholds=selected.thresholds,
    )


def account_attributes(account: CRMAccount, company: CSCompany) -> dict[str, Any]:
    return {
        "account_id": account.account_id,
        "account_name": account.name,
        "owner_id": account.owner_id,
        "industry": account.industry,
        "arr_cents": company.arr_cents,
        "lifecycle_stage": company.lifecycle_stage,
        "status": company.status,
        "current_score": company.current_score,
    }


def build_customer_value_model(
    *,
    account: CRMAccount,
    company: CSCompany,
    health: HealthScore,
    adoption: AdoptionSummary | None,
    entitlements: tuple[Entitlement, ...],
    usage_signals: tuple[UsageSignal, ...],
    success_plans: tuple[SuccessPlan, ...],
    config: ValueModelConfig | None = None,
) -> CustomerValueModel:
    cfg = config or load_value_model_config()
    resolved = resolve_thresholds(account_attributes(account, company), cfg)
    thresholds = resolved.thresholds

    penetration = _penetration_rail(adoption, resolved)
    feature_depth = _feature_depth_rail(adoption, entitlements, resolved)
    outcome = _outcome_rail(success_plans, resolved)
    usage = UsageRail(
        adoption_rate=adoption.adoption_rate if adoption else None,
        active_users=adoption.active_users if adoption else None,
        licensed_users=adoption.licensed_users if adoption else None,
        underused_capabilities=adoption.underused_capabilities if adoption else (),
        factors=(),
    )

    divergences: list[ValueFactor] = []
    if adoption and adoption.licensed_users > 0:
        adoption_ratio = adoption.active_users / adoption.licensed_users
        if health.band == "green" and adoption_ratio < thresholds.adoption_floor:
            divergences.append(_factor(
                "health_usage_divergence",
                adoption_ratio,
                35,
                (
                    EvidenceRef("cs_platform", health.account_id, "health_score", health.measured_at),
                    EvidenceRef("cs_platform", adoption.account_id, "active_users", adoption.measured_at),
                ),
                resolved,
                "adoption_floor",
                thresholds.adoption_floor,
            ))

    threaded = _single_threaded_risk(usage_signals, adoption, resolved)
    if threaded is not None:
        divergences.append(threaded)
    usage_outcome = _usage_outcome_divergence(adoption, outcome, resolved)
    if usage_outcome is not None:
        divergences.append(usage_outcome)

    return CustomerValueModel(
        account_id=account.account_id,
        lifecycle_stage=company.lifecycle_stage,
        resolved_thresholds=resolved,
        usage=usage,
        penetration=penetration,
        feature_depth=feature_depth,
        outcome=outcome,
        divergences=tuple(divergences),
    )


def project_ttv_lens(
    model: CustomerValueModel,
    *,
    company: CSCompany | None = None,
    health: HealthScore | None = None,
    open_milestone_gaps: tuple[TimeToValueMilestone, ...] = (),
    overdue_success_plans: tuple[SuccessPlan, ...] = (),
    as_of: str | None = None,
) -> ProjectedPriority:
    factors = (
        *_ttv_base_factors(
            model,
            company=company,
            health=health,
            open_milestone_gaps=open_milestone_gaps,
            overdue_success_plans=overdue_success_plans,
            as_of=as_of,
        ),
        *model.ttv_factors,
    )
    return ProjectedPriority(
        score=sum(factor.contribution for factor in factors),
        factors=factors,
    )


def _parse_rule(raw: dict[str, Any]) -> ConfigRule:
    return ConfigRule(
        name=raw["name"],
        match=tuple(
            MatchPredicate(
                field=item["field"],
                op=item["op"],
                value=tuple(item["value"]) if isinstance(item["value"], list) else item["value"],
            )
            for item in raw["match"]
        ),
        thresholds=Thresholds(**raw["thresholds"]),
    )


def _rule_matches(rule: ConfigRule, attrs: dict[str, Any]) -> bool:
    return all(_predicate_matches(predicate, attrs) for predicate in rule.match)


def _predicate_matches(predicate: MatchPredicate, attrs: dict[str, Any]) -> bool:
    if predicate.field not in attrs:
        raise ConfigValidationError(f"missing match field value: {predicate.field}")
    left = attrs[predicate.field]
    if predicate.op == "in":
        values = predicate.value if isinstance(predicate.value, tuple) else (predicate.value,)
        return left in values
    return _OPS[predicate.op](left, predicate.value)


def _penetration_rail(
    adoption: AdoptionSummary | None,
    resolved: ResolvedThresholds,
) -> PenetrationRail:
    if adoption is None or adoption.licensed_users <= 0:
        return PenetrationRail(None, None, None, "unknown", ())
    ratio = adoption.active_users / adoption.licensed_users
    factors = ()
    if ratio < resolved.thresholds.seat_penetration_floor:
        factors = (_factor(
            "low_seat_penetration",
            ratio,
            12,
            (EvidenceRef("cs_platform", adoption.account_id, "active_users", adoption.measured_at),),
            resolved,
            "seat_penetration_floor",
            resolved.thresholds.seat_penetration_floor,
        ),)
    return PenetrationRail(
        seat_penetration=ratio,
        active_users=adoption.active_users,
        licensed_users=adoption.licensed_users,
        state="known",
        factors=factors,
    )


def _feature_depth_rail(
    adoption: AdoptionSummary | None,
    entitlements: tuple[Entitlement, ...],
    resolved: ResolvedThresholds,
) -> FeatureDepthRail:
    entitled = tuple(sorted({item.capability for item in entitlements}))
    underused = tuple(sorted(set(adoption.underused_capabilities if adoption else ()) & set(entitled)))
    if adoption is None or not entitled:
        return FeatureDepthRail(entitled, underused, ())
    used_count = len(entitled) - len(underused)
    ratio = used_count / len(entitled)
    factors = ()
    if ratio < resolved.thresholds.depth_floor:
        evidence = (
            EvidenceRef("cs_platform", adoption.account_id, "underused_capabilities", adoption.measured_at),
            *(
                EvidenceRef("telemetry", f"{ent.account_id}:{ent.capability}", "capability", ent.starts_at)
                for ent in entitlements
            ),
        )
        factors = (_factor(
            "feature_depth_gap",
            ratio,
            15,
            evidence,
            resolved,
            "depth_floor",
            resolved.thresholds.depth_floor,
        ),)
    return FeatureDepthRail(entitled, underused, factors)


def _outcome_rail(
    success_plans: tuple[SuccessPlan, ...],
    resolved: ResolvedThresholds,
) -> OutcomeRail:
    objectives = tuple(
        objective
        for plan in success_plans
        for objective in plan.objectives
    )
    factors = ()
    if objectives:
        factors = (_factor(
            "outcome_stated",
            float(len(objectives)),
            0,
            tuple(
                EvidenceRef("cs_platform", plan.plan_id, "objectives", plan.target_date)
                for plan in success_plans
                if plan.objectives
            ),
            resolved,
            None,
            None,
        ),)
    realized_state: OutcomeState = (
        "known"
        if any(plan.status in {"realized", "achieved", "complete"} for plan in success_plans)
        else "not_instrumented"
    )
    return OutcomeRail(
        stated_objectives=objectives,
        realized_state=realized_state,
        factors=factors,
    )


def _ttv_base_factors(
    model: CustomerValueModel,
    *,
    company: CSCompany | None,
    health: HealthScore | None,
    open_milestone_gaps: tuple[TimeToValueMilestone, ...],
    overdue_success_plans: tuple[SuccessPlan, ...],
    as_of: str | None,
) -> tuple[ValueFactor, ...]:
    resolved = model.resolved_thresholds
    thresholds = resolved.thresholds
    factors: list[ValueFactor] = []

    if open_milestone_gaps:
        evidence = tuple(
            EvidenceRef("telemetry", signal_id, "ttv_milestone", milestone.expected_by)
            for milestone in open_milestone_gaps
            for signal_id in milestone.evidence_signal_ids
        )
        factors.append(_factor(
            "milestones_overdue",
            float(len(open_milestone_gaps)),
            len(open_milestone_gaps) * thresholds.milestone_overdue_points,
            evidence,
            resolved,
            "milestone_overdue_points",
            thresholds.milestone_overdue_points,
        ))
        if as_of is not None:
            max_days = max(
                (iso_date(as_of) - iso_date(milestone.expected_by)).days
                for milestone in open_milestone_gaps
            )
            factors.append(_factor(
                "days_overdue",
                float(max_days),
                min(max_days * thresholds.days_overdue_points, thresholds.days_overdue_cap),
                evidence,
                resolved,
                "days_overdue_cap",
                thresholds.days_overdue_cap,
            ))

    if overdue_success_plans:
        evidence = tuple(
            EvidenceRef("cs_platform", plan.plan_id, "target_date", plan.target_date)
            for plan in overdue_success_plans
        )
        factors.append(_factor(
            "success_plan_overdue",
            float(len(overdue_success_plans)),
            len(overdue_success_plans) * thresholds.success_plan_overdue_points,
            evidence,
            resolved,
            "success_plan_overdue_points",
            thresholds.success_plan_overdue_points,
        ))

    if health is not None and health.band in {"red", "yellow"}:
        name = "health_red" if health.band == "red" else "health_yellow"
        threshold_name = "health_red_points" if health.band == "red" else "health_yellow_points"
        contribution = (
            thresholds.health_red_points
            if health.band == "red"
            else thresholds.health_yellow_points
        )
        factors.append(_factor(
            name,
            1.0,
            contribution,
            (EvidenceRef("cs_platform", health.account_id, "health_score", health.measured_at),),
            resolved,
            threshold_name,
            contribution,
        ))

    if company is not None and company.arr_cents >= thresholds.arr_review_floor_cents:
        factors.append(_factor(
            "arr_tier",
            float(company.arr_cents),
            thresholds.arr_review_points,
            (EvidenceRef("cs_platform", company.company_id, "arr_cents", company.original_contract_date),),
            resolved,
            "arr_review_floor_cents",
            thresholds.arr_review_floor_cents,
        ))

    return tuple(factors)


def _usage_outcome_divergence(
    adoption: AdoptionSummary | None,
    outcome: OutcomeRail,
    resolved: ResolvedThresholds,
) -> ValueFactor | None:
    if (
        adoption is None
        or adoption.licensed_users <= 0
        or not outcome.stated_objectives
        or outcome.realized_state == "known"
    ):
        return None
    activity = adoption.active_users / adoption.licensed_users
    if activity < resolved.thresholds.outcome_activity_floor:
        return None
    return _factor(
        "usage_outcome_unverified",
        activity,
        18,
        (
            EvidenceRef("cs_platform", adoption.account_id, "active_users", adoption.measured_at),
            *outcome.factors[0].evidence,
        ),
        resolved,
        "outcome_activity_floor",
        resolved.thresholds.outcome_activity_floor,
    )


def _single_threaded_risk(
    signals: tuple[UsageSignal, ...],
    adoption: AdoptionSummary | None,
    resolved: ResolvedThresholds,
) -> ValueFactor | None:
    if adoption is None or adoption.licensed_users < resolved.thresholds.min_seats_for_risk:
        return None
    person_signals = [
        signal for signal in signals
        if signal.grain == "person" and signal.subject_id and signal.value > 0
    ]
    if not person_signals:
        return None
    totals: dict[str, float] = {}
    evidence: list[EvidenceRef] = []
    for signal in person_signals:
        totals[signal.subject_id or ""] = totals.get(signal.subject_id or "", 0.0) + signal.value
        evidence.append(EvidenceRef("telemetry", signal.signal_id, signal.metric_name, signal.observed_at))
    total = sum(totals.values())
    if total <= 0:
        return None
    top_share = max(totals.values()) / total
    if (
        top_share >= resolved.thresholds.concentration_ceiling
        and len(totals) <= resolved.thresholds.min_threaded_persons
    ):
        return _factor(
            "single_threaded_risk",
            top_share,
            20,
            tuple(evidence),
            resolved,
            "concentration_ceiling",
            resolved.thresholds.concentration_ceiling,
        )
    return None


def _factor(
    name: str,
    value: float,
    contribution: int,
    evidence: tuple[EvidenceRef, ...],
    resolved: ResolvedThresholds,
    threshold_name: str | None,
    threshold_value: float | int | None,
) -> ValueFactor:
    return ValueFactor(
        name=name,
        value=value,
        contribution=contribution,
        evidence=evidence,
        config_version=resolved.config_version,
        rule_name=resolved.rule_name,
        threshold_name=threshold_name,
        threshold_value=threshold_value,
    )
