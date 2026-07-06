"""Deterministic customer value model shared by CSM lenses."""

from __future__ import annotations

import json
import operator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ultra_csm import person_factors
from ultra_csm._util import iso_date
from ultra_csm.data_plane.contracts import (
    AdoptionSummary,
    CommunicationSignal,
    CRMAccount,
    CSCompany,
    Entitlement,
    EvidenceRef,
    HealthScore,
    JobChangeSignal,
    LifecycleStage,
    StakeholderRelationship,
    SuccessPlan,
    TimeToValueMilestone,
    UsageSignal,
)


# Constraint (architecture cleanup, report 42, Sanctioned Exception): this
# anchoring pattern climbs from the installed module's own file location to
# find repo-root `config/`. It resolves correctly for an editable install
# (`pip install -e .`) or when run from a source checkout, because
# `parents[2]` lands on the repo root either way. A NON-EDITABLE install
# (`pip install .` into a clean venv) copies this package into site-packages
# without `config/`/`knowledge/`/`migrations/` alongside it -- those
# directories are not currently declared as package-data in pyproject.toml,
# and declaring them wouldn't be enough on its own: this same
# `parents[N]`-climb pattern recurs in ~9 other production modules
# (api.py, mcp_server.py, cli.py, knowledge.py, triggers.py, tick.py, and
# several agent1/*.py files), all of which would need to switch to
# importlib.resources-style resolution for a non-editable install to work.
# That rewrite is larger than this dispatch's diff budget alongside its four
# other independent items, so this is scoped down to a documented
# constraint per the Sanctioned Exceptions section: **editable install only**
# is the supported install mode until that resolution rewrite happens.
REPO = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO / "config" / "value_model_config.json"

PredicateOp = Literal[">=", ">", "<=", "<", "==", "!=", "in"]
RailState = Literal["known", "unknown"]
OutcomeState = Literal["known", "unknown", "not_instrumented"]
# Keep in sync with ultra_csm.knowledge.PLAYBOOK_SERVICE_TIERS (Universe v2
# Foundations canon, docs/UNIVERSE_V2_CONVENTIONS.md).
TenantTier = Literal["high_touch", "mid_touch", "tech_touch"]

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
    onboarding_activation_gap_points: int
    success_plan_overdue_points: int
    health_red_points: int
    health_yellow_points: int
    arr_review_floor_cents: int
    arr_review_points: int
    # Person-derived factors (Harvest 16), additive.
    champion_departed_window_days: int
    champion_departed_points: int
    single_threaded_recency_days: int
    new_stakeholder_window_days: int
    new_stakeholder_points: int
    usage_concentration_points: int


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
class TierRule:
    """A tenant-tier derivation rule -- same match/most-specific-wins shape
    as :class:`ConfigRule`, but resolves a service tier label instead of a
    threshold set. Kept as a distinct rule list (``tier_rules``) rather than
    merged into ``rules`` so tier derivation can never change existing
    threshold resolution for an account."""

    name: str
    match: tuple[MatchPredicate, ...]
    tier: TenantTier


@dataclass(frozen=True)
class ValueModelConfig:
    config_version: str
    rules: tuple[ConfigRule, ...]
    tier_rules: tuple[TierRule, ...] = ()


@dataclass(frozen=True)
class ResolvedThresholds:
    config_version: str
    rule_name: str
    thresholds: Thresholds


@dataclass(frozen=True)
class ResolvedTier:
    config_version: str
    rule_name: str
    tier: TenantTier


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
    tier_rules = tuple(_parse_tier_rule(item) for item in raw.get("tier_rules", ()))
    config = ValueModelConfig(config_version=raw["config_version"], rules=rules, tier_rules=tier_rules)
    validate_config(config)
    return config


TENANT_TIERS: tuple[TenantTier, ...] = ("high_touch", "mid_touch", "tech_touch")


def validate_config(config: ValueModelConfig) -> None:
    _validate_rule_set(
        config.rules,
        rule_matches=lambda rule: rule.match,
    )
    if config.tier_rules:
        _validate_rule_set(config.tier_rules, rule_matches=lambda rule: rule.match)
        for tier_rule in config.tier_rules:
            if tier_rule.tier not in TENANT_TIERS:
                raise ConfigValidationError(f"unknown tenant tier: {tier_rule.tier}")


def _validate_rule_set(rules: tuple[Any, ...], *, rule_matches: Any) -> None:
    base_rules = [rule for rule in rules if not rule_matches(rule)]
    if len(base_rules) != 1:
        raise ConfigValidationError("rule set requires exactly one empty-match base rule")
    seen_names: set[str] = set()
    for rule in rules:
        if rule.name in seen_names:
            raise ConfigValidationError(f"duplicate config rule name: {rule.name}")
        seen_names.add(rule.name)
        for predicate in rule_matches(rule):
            if predicate.field not in ACCOUNT_MATCH_FIELDS:
                raise ConfigValidationError(f"unknown match field: {predicate.field}")
            if predicate.op not in (*_OPS.keys(), "in"):
                raise ConfigValidationError(f"unsupported predicate op: {predicate.op}")


def _select_most_specific(rules: tuple[Any, ...], attrs: dict[str, Any]) -> Any:
    """Most-specific-wins rule selection: the matching rule with the most
    predicates wins; ties break toward the earliest-declared rule. Shared by
    :func:`resolve_thresholds` and :func:`resolve_tenant_tier` so tier
    derivation reuses the exact same resolution algorithm rather than a
    second one."""

    matches = [(index, rule) for index, rule in enumerate(rules) if _rule_matches(rule, attrs)]
    if not matches:
        raise ConfigValidationError("no config rule matched")
    _, selected = max(matches, key=lambda pair: (len(pair[1].match), -pair[0]))
    return selected


def resolve_thresholds(
    attrs: dict[str, Any],
    config: ValueModelConfig,
) -> ResolvedThresholds:
    validate_config(config)
    selected = _select_most_specific(config.rules, attrs)
    return ResolvedThresholds(
        config_version=config.config_version,
        rule_name=selected.name,
        thresholds=selected.thresholds,
    )


def resolve_tenant_tier(
    attrs: dict[str, Any],
    config: ValueModelConfig,
) -> ResolvedTier:
    """Derive the tenant service tier (high_touch/mid_touch/tech_touch) for
    an account via the same most-specific-wins rule resolver as
    :func:`resolve_thresholds`, applied to the separate ``tier_rules`` list
    so tier derivation can never perturb existing threshold resolution."""

    validate_config(config)
    if not config.tier_rules:
        raise ConfigValidationError("ValueModelConfig has no tier_rules configured")
    selected = _select_most_specific(config.tier_rules, attrs)
    return ResolvedTier(
        config_version=config.config_version,
        rule_name=selected.name,
        tier=selected.tier,
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
    onboarding_milestones: tuple[TimeToValueMilestone, ...] = (),
    stakeholders: tuple[StakeholderRelationship, ...] = (),
    job_changes: tuple[JobChangeSignal, ...] = (),
    communication_signals: tuple[CommunicationSignal, ...] = (),
    as_of: str | None = None,
    config: ValueModelConfig | None = None,
) -> CustomerValueModel:
    """Build the four-rail value model.

    ``onboarding_milestones`` is optional Rocketlane-derived TTV evidence
    (see docs/ROCKETLANE_ONBOARDING_CONNECTOR_SPEC.md's TTV bridge). When
    empty -- no onboarding source mapped for this account, or a connector
    outage that fails closed upstream -- the outcome rail degrades exactly as
    it always has (success-plan-only), never fabricating a milestone.

    ``stakeholders``/``job_changes``/``communication_signals`` are optional
    person-layer inputs (Harvest 16, additive -- default empty so every
    pre-existing caller is unaffected). When empty, the person-derived
    factors below simply do not fire and ``_single_threaded_risk`` falls
    back to its original telemetry-usage-signal proxy unchanged -- see that
    function's docstring for why this keeps zero-drift. ``as_of`` is
    required only for the two window-based person factors (champion_departed,
    new_stakeholder_unengaged); when ``None``, they are skipped (fail-safe).
    """

    cfg = config or load_value_model_config()
    resolved = resolve_thresholds(account_attributes(account, company), cfg)
    thresholds = resolved.thresholds

    penetration = _penetration_rail(adoption, resolved)
    feature_depth = _feature_depth_rail(adoption, entitlements, resolved)
    outcome = _outcome_rail(success_plans, resolved, onboarding_milestones=onboarding_milestones)
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

    threaded = _single_threaded_risk(usage_signals, adoption, resolved, stakeholders=stakeholders)
    if threaded is not None:
        divergences.append(threaded)
    usage_outcome = _usage_outcome_divergence(adoption, outcome, resolved)
    if usage_outcome is not None:
        divergences.append(usage_outcome)

    if as_of is not None:
        champion_factor = _champion_departed_factor(stakeholders, job_changes, resolved, as_of=as_of)
        if champion_factor is not None:
            divergences.append(champion_factor)
        new_stakeholder_factor = _new_stakeholder_unengaged_factor(
            stakeholders, communication_signals, resolved, as_of=as_of
        )
        if new_stakeholder_factor is not None:
            divergences.append(new_stakeholder_factor)

    concentration_factor = _usage_concentration_factor(usage_signals, adoption, resolved)
    if concentration_factor is not None:
        divergences.append(concentration_factor)

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
    onboarding_evidence_ids: frozenset[str] = frozenset(),
    onboarding_activation_gap_ids: tuple[str, ...] = (),
) -> ProjectedPriority:
    """``onboarding_evidence_ids`` are Rocketlane phase/task ids among
    ``open_milestone_gaps``' evidence_signal_ids -- used only to attribute
    evidence correctly as ``EvidenceSource="rocketlane"`` instead of the
    default ``"telemetry"``. Passing none is the honest default: an id not
    listed here is attributed to telemetry, matching pre-Program-4 behavior
    exactly.

    ``onboarding_activation_gap_ids`` are Rocketlane phase/task ids carrying
    delivery-rail activation-gap evidence (RUNNING_LATE progress, an at-risk
    task, or an overdue phase) that ``open_milestone_gaps`` does not already
    cover -- see ``_ttv_base_factors`` for why this is scored only during
    the onboarding lifecycle stage.
    """

    factors = (
        *_ttv_base_factors(
            model,
            company=company,
            health=health,
            open_milestone_gaps=open_milestone_gaps,
            overdue_success_plans=overdue_success_plans,
            as_of=as_of,
            onboarding_evidence_ids=onboarding_evidence_ids,
            onboarding_activation_gap_ids=onboarding_activation_gap_ids,
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


def _parse_tier_rule(raw: dict[str, Any]) -> TierRule:
    return TierRule(
        name=raw["name"],
        match=tuple(
            MatchPredicate(
                field=item["field"],
                op=item["op"],
                value=tuple(item["value"]) if isinstance(item["value"], list) else item["value"],
            )
            for item in raw["match"]
        ),
        tier=raw["tier"],
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
    *,
    onboarding_milestones: tuple[TimeToValueMilestone, ...] = (),
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
    plan_realized = any(
        plan.status in {"realized", "achieved", "complete"} for plan in success_plans
    )
    # A mapped onboarding source (Rocketlane) is real, cited milestone
    # evidence -- an achieved milestone is as valid an outcome signal as a
    # realized success plan. Absence of onboarding_milestones changes
    # nothing: realized_state degrades exactly as it always has.
    onboarding_achieved = tuple(
        m for m in onboarding_milestones if m.achieved_at is not None
    )
    if plan_realized or onboarding_achieved:
        realized_state: OutcomeState = "known"
    else:
        realized_state = "not_instrumented"
    if onboarding_achieved:
        factors = (*factors, _factor(
            "onboarding_milestone_achieved",
            float(len(onboarding_achieved)),
            0,
            tuple(
                EvidenceRef("rocketlane", signal_id, "achieved_at", m.achieved_at or "")
                for m in onboarding_achieved
                for signal_id in m.evidence_signal_ids
            ),
            resolved,
            None,
            None,
        ),)
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
    onboarding_evidence_ids: frozenset[str] = frozenset(),
    onboarding_activation_gap_ids: tuple[str, ...] = (),
) -> tuple[ValueFactor, ...]:
    resolved = model.resolved_thresholds
    thresholds = resolved.thresholds
    factors: list[ValueFactor] = []

    # Lifecycle-aware weighting, not a global loosening of the score>0 gate:
    # during onboarding, a delivery-rail activation gap (RUNNING_LATE
    # progress, an at-risk task, or an overdue phase) is itself positive
    # evidence of a Time-to-Value risk, even when it hasn't yet cleared the
    # date-based ``open_milestone_gaps`` filter above. Outside onboarding
    # this signal is not scored -- an at-risk task on a steady-state account
    # is not the blind spot this closes.
    if model.lifecycle_stage == "onboarding" and onboarding_activation_gap_ids:
        factors.append(_factor(
            "onboarding_activation_gap",
            float(len(onboarding_activation_gap_ids)),
            len(onboarding_activation_gap_ids) * thresholds.onboarding_activation_gap_points,
            tuple(
                EvidenceRef("rocketlane", signal_id, "activation_gap", as_of or "")
                for signal_id in onboarding_activation_gap_ids
            ),
            resolved,
            "onboarding_activation_gap_points",
            thresholds.onboarding_activation_gap_points,
        ))

    if open_milestone_gaps:
        evidence = tuple(
            EvidenceRef(
                "rocketlane" if signal_id in onboarding_evidence_ids else "telemetry",
                signal_id,
                "ttv_milestone",
                milestone.expected_by,
            )
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
    *,
    stakeholders: tuple[StakeholderRelationship, ...] = (),
) -> ValueFactor | None:
    """Single-threaded-risk factor: real-graph-when-available, telemetry-
    usage-signal-proxy-fallback (Harvest 16).

    Zero-drift argument: every pre-existing caller passes no ``stakeholders``
    (default ``()``), so they take the untouched proxy branch below with
    byte-identical evidence/value to before this dispatch --
    ``tests/test_value_model.py::test_single_threaded_risk_requires_person_grain_usage``
    asserts ``evidence[0].source_id == "person-signal-1"`` (a UsageSignal id),
    which only the proxy branch produces. The real graph is consulted ONLY
    when stakeholder data is threaded in by the caller (the sweep, once Phase
    1 wires the fetch) -- this is the "graph-when-available, proxy-fallback"
    resolution recorded in PROGRESS.md's zero-drift analysis.
    """

    if adoption is None or adoption.licensed_users < resolved.thresholds.min_seats_for_risk:
        return None

    if stakeholders:
        count, engaged = person_factors.engaged_contact_count(
            stakeholders,
            as_of=adoption.measured_at,
            recency_days=resolved.thresholds.single_threaded_recency_days,
        )
        if count == 0:
            return None
        if count <= resolved.thresholds.min_threaded_persons:
            return _factor(
                "single_threaded_risk",
                float(count),
                20,
                person_factors.evidence_for_single_threaded_graph(engaged),
                resolved,
                "min_threaded_persons",
                resolved.thresholds.min_threaded_persons,
            )
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


def _champion_departed_factor(
    stakeholders: tuple[StakeholderRelationship, ...],
    job_changes: tuple[JobChangeSignal, ...],
    resolved: ResolvedThresholds,
    *,
    as_of: str,
) -> ValueFactor | None:
    """``champion_departed`` (RISK lens): a JobChangeSignal departure for a
    contact holding the ``champion`` StakeholderRelationship role, within
    ``champion_departed_window_days``. Additive -- returns None (never
    fires) when either input is empty, so pre-existing callers (which pass
    neither) are unaffected."""

    if not stakeholders or not job_changes:
        return None
    found = person_factors.champion_departed(
        stakeholders,
        job_changes,
        as_of=as_of,
        window_days=resolved.thresholds.champion_departed_window_days,
    )
    if found is None:
        return None
    change, role = found
    return _factor(
        "champion_departed",
        float(change.day_offset),
        resolved.thresholds.champion_departed_points,
        person_factors.evidence_for_champion_departed(change, role),
        resolved,
        "champion_departed_window_days",
        resolved.thresholds.champion_departed_window_days,
    )


def _new_stakeholder_unengaged_factor(
    stakeholders: tuple[StakeholderRelationship, ...],
    communication_signals: tuple[CommunicationSignal, ...],
    resolved: ResolvedThresholds,
    *,
    as_of: str,
) -> ValueFactor | None:
    """``new_stakeholder_unengaged`` (RISK lens): an admin/executive_sponsor
    StakeholderRelationship added within ``new_stakeholder_window_days`` with
    no matching CommunicationSignal. Additive -- returns None when there are
    no stakeholder rows to inspect."""

    if not stakeholders:
        return None
    found = person_factors.new_stakeholder_unengaged(
        stakeholders,
        communication_signals,
        as_of=as_of,
        window_days=resolved.thresholds.new_stakeholder_window_days,
    )
    if found is None:
        return None
    return _factor(
        "new_stakeholder_unengaged",
        1.0,
        resolved.thresholds.new_stakeholder_points,
        person_factors.evidence_for_new_stakeholder_unengaged(found),
        resolved,
        "new_stakeholder_window_days",
        resolved.thresholds.new_stakeholder_window_days,
    )


def _usage_concentration_factor(
    signals: tuple[UsageSignal, ...],
    adoption: AdoptionSummary | None,
    resolved: ResolvedThresholds,
) -> ValueFactor | None:
    """``usage_concentration`` (ADOPTION lens): top-user share of person-grain
    usage >= ``concentration_ceiling``, via the promoted
    :func:`ultra_csm.person_factors.top_user_share` helper shared with
    ``value_model_bridge.build_deep_value_model`` (one concentration
    computation, not two). Additive -- distinct ValueFactor name from
    ``single_threaded_risk`` so it never perturbs that factor's existing
    assertions; fires alongside it when both conditions independently hold.
    """

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
    share = person_factors.top_user_share(totals)
    if share is None or share < resolved.thresholds.concentration_ceiling:
        return None
    return _factor(
        "usage_concentration",
        share,
        resolved.thresholds.usage_concentration_points,
        tuple(evidence),
        resolved,
        "concentration_ceiling",
        resolved.thresholds.concentration_ceiling,
    )


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
