"""Bridge: compute CustomerValueModel from deep data simulation.

Instead of consuming pre-computed AdoptionSummary and HealthScore objects
from the CS platform, this module computes the four value-model rails
directly from :class:`SimulatedDataBundle` granular data streams.

Usage::

    from ultra_csm.data_plane.data_simulator import simulate_data
    from ultra_csm.data_plane.synthetic_book import build_synthetic_book
    from ultra_csm.value_model_bridge import build_deep_value_model

    base = build_synthetic_book()
    bundle = simulate_data(base, day=14)
    model, health = build_deep_value_model(
        bundle=bundle,
        account_id=some_id,
        account=crm_account,
        company=cs_company,
        entitlements=entitlements,
        success_plans=plans,
        licensed_users=50,
    )
"""

from __future__ import annotations

from ultra_csm.data_plane.contracts import (
    CRMAccount,
    CSCompany,
    Entitlement,
    EvidenceRef,
    HealthBand,
    HealthScore,
    SuccessPlan,
)
from ultra_csm.data_plane.data_simulator import (
    AccountDataBundle,
    SimulatedDataBundle,
)
from ultra_csm.person_factors import top_user_share
from ultra_csm.value_model import (
    CustomerValueModel,
    FeatureDepthRail,
    OutcomeRail,
    OutcomeState,
    PenetrationRail,
    ResolvedThresholds,
    UsageRail,
    ValueFactor,
    ValueModelConfig,
    account_attributes,
    load_value_model_config,
    resolve_thresholds,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Health score from data
# ---------------------------------------------------------------------------

def compute_health_from_data(
    ab: AccountDataBundle,
    licensed_users: int,
    as_of: str,
) -> HealthScore:
    """Compute a HealthScore from the underlying deep-data signals.

    Score is on a 0–100 scale with bands:
      green >= 65, yellow >= 40, red < 40.

    Components (summing to 100 max):
      * Active-user ratio   (0–30)
      * Feature depth       (0–25)
      * Champion active     (0 or 15)
      * CSAT                (0–15)
      * Activity consistency (0–15)
    """
    score = 0.0
    drivers: list[str] = []

    # --- Active user ratio: 0–30 ---
    if licensed_users > 0:
        ratio = min(1.0, ab.active_user_count / licensed_users)
        score += ratio * 30.0
        if ratio < 0.3:
            drivers.append("low_active_users")
    else:
        score += 15.0  # neutral when no seat data

    # --- Feature depth: 0–25 ---
    score += ab.feature_depth_score * 25.0
    if ab.feature_depth_score < 0.4:
        drivers.append("low_feature_adoption")

    # --- Champion active: 0 or 15 ---
    if ab.champion_active:
        score += 15.0
    else:
        drivers.append("champion_inactive")

    # --- CSAT: 0–15 ---
    if ab.overall_csat is not None:
        csat_norm = max(0.0, (ab.overall_csat - 1.0) / 4.0)
        score += csat_norm * 15.0
        if ab.overall_csat < 3.0:
            drivers.append("low_csat")
    else:
        score += 7.5  # neutral when no cases

    # --- Activity consistency: 0–15 ---
    if ab.mau > 0:
        wau_mau = min(1.0, ab.wau / ab.mau)
        score += wau_mau * 15.0
    else:
        drivers.append("no_recent_activity")

    band: HealthBand
    if score >= 65:
        band = "green"
    elif score >= 40:
        band = "yellow"
    else:
        band = "red"

    return HealthScore(
        account_id=ab.account_id,
        score=round(score, 1),
        band=band,
        drivers=tuple(drivers),
        measured_at=as_of,
    )


# ---------------------------------------------------------------------------
# Usage trend helpers
# ---------------------------------------------------------------------------

def _usage_trend_30d(ab: AccountDataBundle, day: int) -> float:
    """Ratio of users active in last 30 days vs the prior 30 days."""
    recent_start = max(0, day - 29)
    prior_start = max(0, day - 59)
    recent_window = set(range(recent_start, day + 1))
    prior_window = set(range(prior_start, recent_start))

    recent = sum(1 for lh in ab.login_histories if recent_window & set(lh.login_days))
    prior = sum(1 for lh in ab.login_histories if prior_window & set(lh.login_days))
    if prior == 0:
        return 1.0 if recent > 0 else 0.0
    return recent / prior


# ---------------------------------------------------------------------------
# Rail builders (from deep data)
# ---------------------------------------------------------------------------

def _usage_rail_from_data(
    ab: AccountDataBundle,
    licensed_users: int,
    as_of: str,
) -> UsageRail:
    """Build the usage rail from login histories and feature adoptions."""
    active_users = ab.active_user_count
    adoption_rate = (
        round(active_users / licensed_users, 3)
        if licensed_users > 0
        else None
    )
    underused = tuple(sorted(
        f.feature for f in ab.feature_adoptions
        if f.status in ("not_started", "exploring")
    ))
    return UsageRail(
        adoption_rate=adoption_rate,
        active_users=active_users,
        licensed_users=licensed_users,
        underused_capabilities=underused,
        factors=(),  # usage factors do not flow into ttv_factors
    )


def _penetration_rail_from_data(
    ab: AccountDataBundle,
    licensed_users: int,
    as_of: str,
    resolved: ResolvedThresholds,
) -> PenetrationRail:
    """Build the penetration rail from contact engagement and login data.

    Considers:
    * Seat penetration (active users / licensed users)
    * Multi-threading depth (distinct active contacts)
    * Role diversity (distinct role types among active contacts)
    """
    if licensed_users <= 0:
        return PenetrationRail(None, None, None, "unknown", ())

    active_users = ab.active_user_count
    seat_penetration = active_users / licensed_users
    thresholds = resolved.thresholds
    factors: list[ValueFactor] = []

    if seat_penetration < thresholds.seat_penetration_floor:
        factors.append(_factor(
            "low_seat_penetration",
            seat_penetration,
            12,
            (EvidenceRef("telemetry", ab.account_id, "mau", as_of),),
            resolved,
            "seat_penetration_floor",
            thresholds.seat_penetration_floor,
        ))

    return PenetrationRail(
        seat_penetration=round(seat_penetration, 3),
        active_users=active_users,
        licensed_users=licensed_users,
        state="known",
        factors=tuple(factors),
    )


def _feature_depth_rail_from_data(
    ab: AccountDataBundle,
    entitlements: tuple[Entitlement, ...],
    as_of: str,
    resolved: ResolvedThresholds,
) -> FeatureDepthRail:
    """Build the feature-depth rail from per-feature adoption states."""
    entitled_caps = tuple(sorted({e.capability for e in entitlements}))
    underused = tuple(sorted(
        f.feature for f in ab.feature_adoptions
        if f.status in ("not_started", "exploring")
    ))

    if not ab.feature_adoptions or not entitled_caps:
        return FeatureDepthRail(entitled_caps, underused, ())

    total = len(ab.feature_adoptions)
    adopted_count = sum(
        1 for f in ab.feature_adoptions
        if f.status in ("adopted", "power_user") and f.users_active > 0
    )
    ratio = adopted_count / total if total > 0 else 0.0

    factors: list[ValueFactor] = []
    if ratio < resolved.thresholds.depth_floor:
        evidence = (
            EvidenceRef("telemetry", ab.account_id, "feature_adoption", as_of),
            *(
                EvidenceRef(
                    "telemetry",
                    f"{e.account_id}:{e.capability}",
                    "capability",
                    e.starts_at,
                )
                for e in entitlements
            ),
        )
        factors.append(_factor(
            "feature_depth_gap",
            ratio,
            15,
            evidence,
            resolved,
            "depth_floor",
            resolved.thresholds.depth_floor,
        ))

    return FeatureDepthRail(entitled_caps, underused, tuple(factors))


def _outcome_rail_from_data(
    ab: AccountDataBundle,
    success_plans: tuple[SuccessPlan, ...],
    as_of: str,
    resolved: ResolvedThresholds,
) -> OutcomeRail:
    """Build the outcome rail from success plans, renewal outcomes, and cases.

    Case analysis adds a ``repeat_case_topics`` factor when the same
    support topic recurs (negative signal) and notes high average CSAT
    as a positive.
    """
    objectives = tuple(
        objective
        for plan in success_plans
        for objective in plan.objectives
    )

    factors: list[ValueFactor] = []
    if objectives:
        factors.append(_factor(
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
        ))

    # Repeat-topic detection from case data
    if ab.cases:
        topic_counts: dict[str, int] = {}
        for case in ab.cases:
            topic_counts[case.topic] = topic_counts.get(case.topic, 0) + 1
        repeat_topics = [t for t, c in topic_counts.items() if c >= 2]
        if repeat_topics:
            factors.append(_factor(
                "repeat_case_topics",
                float(len(repeat_topics)),
                0,  # informational — does not add to priority
                (EvidenceRef("crm", ab.account_id, "case_topics", as_of),),
                resolved,
                None,
                None,
            ))

    renewal_outcome_factors = _terminal_renewal_outcome_factors_from_data(
        ab,
        resolved,
        as_of=as_of,
    )
    if renewal_outcome_factors:
        factors.extend(renewal_outcome_factors)

    realized_state: OutcomeState = (
        "known"
        if renewal_outcome_factors or any(
            plan.status in {"realized", "achieved", "complete"}
            for plan in success_plans
        )
        else "not_instrumented"
    )

    return OutcomeRail(
        stated_objectives=objectives,
        realized_state=realized_state,
        factors=tuple(factors),
    )


def _terminal_renewal_outcome_factors_from_data(
    ab: AccountDataBundle,
    resolved: ResolvedThresholds,
    *,
    as_of: str,
) -> tuple[ValueFactor, ...]:
    factors: list[ValueFactor] = []
    for opportunity in ab.opportunities:
        if "renew" not in opportunity.opportunity_type.lower():
            continue
        stage = opportunity.current_stage.strip().lower()
        if stage == "closed won":
            name = "renewal_outcome_closed_won"
            value = 1.0
        elif stage == "closed lost":
            name = "renewal_outcome_closed_lost"
            value = -1.0
        else:
            continue
        factors.append(_factor(
            name,
            value,
            0,
            (
                EvidenceRef(
                    "crm",
                    opportunity.opportunity_id,
                    "current_stage",
                    as_of,
                ),
            ),
            resolved,
            None,
            None,
        ))
    return tuple(factors)


# ---------------------------------------------------------------------------
# Divergence computation
# ---------------------------------------------------------------------------

def _compute_divergences(
    ab: AccountDataBundle,
    health: HealthScore,
    licensed_users: int,
    day: int,
    as_of: str,
    resolved: ResolvedThresholds,
    outcome: OutcomeRail,
) -> tuple[ValueFactor, ...]:
    thresholds = resolved.thresholds
    divergences: list[ValueFactor] = []

    # --- Health-usage divergence ---
    if licensed_users > 0:
        adoption_ratio = ab.active_user_count / licensed_users
        if health.band == "green" and adoption_ratio < thresholds.adoption_floor:
            divergences.append(_factor(
                "health_usage_divergence",
                adoption_ratio,
                35,
                (
                    EvidenceRef("cs_platform", health.account_id, "health_score", health.measured_at),
                    EvidenceRef("telemetry", ab.account_id, "active_users", as_of),
                ),
                resolved,
                "adoption_floor",
                thresholds.adoption_floor,
            ))

    # --- Single-threaded risk ---
    # top_user_share is the promoted concentration helper (person_factors.py,
    # Harvest 16) shared with the sweep-path value model's
    # usage_concentration factor -- one computation, not two parallel
    # copies (the motion-wiring lesson this dispatch's Reading list names).
    if licensed_users >= thresholds.min_seats_for_risk:
        totals: dict[str, float] = {}
        evidence: list[EvidenceRef] = []
        for lh in ab.login_histories:
            recent = sum(1 for d in lh.login_days if d >= max(0, day - 29))
            if recent > 0:
                totals[lh.contact_id] = float(recent)
                evidence.append(
                    EvidenceRef("telemetry", lh.contact_id, "login_count", as_of),
                )
        top_share = top_user_share(totals)
        if top_share is not None:
            if (
                top_share >= thresholds.concentration_ceiling
                and len(totals) <= thresholds.min_threaded_persons
            ):
                divergences.append(_factor(
                    "single_threaded_risk",
                    top_share,
                    20,
                    tuple(evidence),
                    resolved,
                    "concentration_ceiling",
                    thresholds.concentration_ceiling,
                ))

    # --- Champion inactive ---
    if not ab.champion_active:
        champion_histories = [lh for lh in ab.login_histories if lh.is_champion]
        if champion_histories:
            divergences.append(_factor(
                "champion_inactive",
                0.0,
                15,
                (EvidenceRef("telemetry", ab.account_id, "champion_activity", as_of),),
                resolved,
                None,
                None,
            ))

    # --- Usage-outcome unverified ---
    if (
        licensed_users > 0
        and outcome.stated_objectives
        and outcome.realized_state != "known"
    ):
        activity = ab.active_user_count / licensed_users
        if activity >= thresholds.outcome_activity_floor:
            outcome_evidence = outcome.factors[0].evidence if outcome.factors else ()
            divergences.append(_factor(
                "usage_outcome_unverified",
                activity,
                18,
                (
                    EvidenceRef("telemetry", ab.account_id, "active_users", as_of),
                    *outcome_evidence,
                ),
                resolved,
                "outcome_activity_floor",
                thresholds.outcome_activity_floor,
            ))

    # --- Usage decline ---
    trend = _usage_trend_30d(ab, day)
    # decline_slope is negative (e.g. -0.15); fire when trend < 1 + slope
    if trend < (1.0 + thresholds.decline_slope):
        divergences.append(_factor(
            "usage_decline",
            round(trend, 3),
            12,
            (EvidenceRef("telemetry", ab.account_id, "usage_trend_30d", as_of),),
            resolved,
            "decline_slope",
            thresholds.decline_slope,
        ))

    return tuple(divergences)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_deep_value_model(
    *,
    bundle: SimulatedDataBundle,
    account_id: str,
    account: CRMAccount,
    company: CSCompany,
    entitlements: tuple[Entitlement, ...],
    success_plans: tuple[SuccessPlan, ...],
    licensed_users: int,
    config: ValueModelConfig | None = None,
) -> tuple[CustomerValueModel, HealthScore]:
    """Build a CustomerValueModel from deep simulation data.

    Returns ``(model, health)`` — the health score is computed from the
    underlying data streams rather than read from a pre-set fixture.

    Parameters
    ----------
    bundle:
        The :class:`SimulatedDataBundle` produced by ``simulate_data()``.
    account_id:
        Account to score.
    account:
        CRM account record (used for threshold resolution).
    company:
        CS-platform company record (ARR, lifecycle, etc.).
    entitlements:
        What the account is entitled to use.
    success_plans:
        Active success plans for outcome-rail analysis.
    licensed_users:
        Total licensed seat count (from the adoption summary).
    config:
        Optional override for the value-model config.
    """
    cfg = config or load_value_model_config()
    resolved = resolve_thresholds(account_attributes(account, company), cfg)

    ab = bundle.accounts.get(account_id)
    if ab is None:
        raise ValueError(f"account {account_id} not found in SimulatedDataBundle")

    day = bundle.day
    as_of = bundle.as_of_date

    # Health from data
    health = compute_health_from_data(ab, licensed_users, as_of)

    # Four rails
    usage = _usage_rail_from_data(ab, licensed_users, as_of)
    penetration = _penetration_rail_from_data(ab, licensed_users, as_of, resolved)
    feature_depth = _feature_depth_rail_from_data(ab, entitlements, as_of, resolved)
    outcome = _outcome_rail_from_data(ab, success_plans, as_of, resolved)

    # Divergences
    divergences = _compute_divergences(
        ab, health, licensed_users, day, as_of, resolved, outcome,
    )

    model = CustomerValueModel(
        account_id=account_id,
        lifecycle_stage=company.lifecycle_stage,
        resolved_thresholds=resolved,
        usage=usage,
        penetration=penetration,
        feature_depth=feature_depth,
        outcome=outcome,
        divergences=divergences,
    )

    return model, health
