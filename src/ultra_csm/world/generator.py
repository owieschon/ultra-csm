"""Seeded living-world generator built on the repo's fixture contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ultra_csm.data_plane import CustomerDataPlane
from ultra_csm.data_plane.contracts import (
    AdoptionSummary,
    CRMAccount,
    CRMCase,
    CRMContact,
    CRMOpportunity,
    CSCompany,
    CTA,
    Entitlement,
    HealthScore,
    SuccessPlan,
    TimeToValueMilestone,
    UsageSignal,
)
from ultra_csm.data_plane.data_simulator import simulate_data
from ultra_csm.data_plane.fixtures import (
    FixtureCRMDataConnector,
    FixtureCSPlatformConnector,
    FixtureCustomerData,
    FixtureProductTelemetryConnector,
    det_id,
)
from ultra_csm.data_plane.synthetic_book import SEED_DATE, build_synthetic_book


@dataclass(frozen=True)
class WorldConfig:
    seed: int
    scale: int = 180
    quiet_majority_rate: float = 0.72
    doomed_rate: float = 0.12
    corruption_rate: float = 0.18
    red_herring_rate: float = 0.22
    anchor_account_count: int = 35
    # D3 (MP-W1R): three INDEPENDENT dirty-data rates, distinct from
    # corruption_rate above (a single rate choosing ONE of three mutually
    # exclusive corruption kinds). These can co-occur on the same account --
    # the calibration/abstention story needs independent axes of dirtiness,
    # not one flag from a fixed set.
    field_missingness_rate: float = 0.12
    stale_observation_rate: float = 0.15
    contradictory_source_rate: float = 0.05


@dataclass(frozen=True)
class LatentAccountTruth:
    account_id: str
    account_slug: str
    anchor_account: bool
    doomed: bool
    thriving: bool
    champion_engagement: str
    product_fit: str
    org_state: str
    latent_label: str
    corruption_flags: tuple[str, ...]
    causal_chain: tuple[str, ...]
    observed_day: int
    # D3 (MP-W1R): independent dirty-data flags, any combination of
    # "missing_field", "stale_observation", "contradictory_source".
    data_quality_flags: tuple[str, ...] = ()
    # D5 (MP-W1R): richer outcome than the boolean doomed/thriving pair.
    # doomed/thriving are UNCHANGED (backward-compat, still the deterministic
    # source of truth); latent_outcome is a pure derived view: doomed splits
    # 50/50 seeded into churned/downgraded, thriving maps to expanded, else
    # flat.
    latent_outcome: str = "flat"


@dataclass(frozen=True)
class SurfaceDecision:
    decision_id: str
    account_id: str
    decision_time: str
    surfaced: bool
    disposition: str
    recommended_action: str | None
    evidence_ids: tuple[str, ...]
    consulted_fact_keys: tuple[str, ...]
    abstained: bool
    transport: str = "deterministic"
    model_id: str = "world-surface-v1"
    prompt_version: str = "world-surface-v1"


@dataclass(frozen=True)
class WorldBuildResult:
    config: WorldConfig
    data: FixtureCustomerData
    latent_truth: tuple[LatentAccountTruth, ...]
    surface_decisions: tuple[SurfaceDecision, ...]


def generate_world(config: WorldConfig) -> WorldBuildResult:
    base_book = build_synthetic_book()
    anchors = _anchor_slice(base_book, count=min(config.anchor_account_count, config.scale))
    generated_needed = max(0, config.scale - len(anchors.accounts))
    generated = _generate_accounts(config, start_index=0, count=generated_needed)
    merged = _merge_fixture_data(anchors, generated)
    latent = _latent_truth_for_world(config, merged)
    decisions = surface_world(merged)
    return WorldBuildResult(
        config=config,
        data=merged,
        latent_truth=latent,
        surface_decisions=decisions,
    )


def build_data_plane(data: FixtureCustomerData) -> CustomerDataPlane:
    return CustomerDataPlane(
        crm=FixtureCRMDataConnector(data=data),
        cs=FixtureCSPlatformConnector(data=data),
        telemetry=FixtureProductTelemetryConnector(data=data),
    )


def surface_world(data: FixtureCustomerData) -> tuple[SurfaceDecision, ...]:
    """Surfacing decisions computed from OBSERVABLE data only. Takes no latent
    truth by construction, so a surface decision cannot leak it -- the
    knowability property the audit now also checks semantically."""
    health_by_id = {row.account_id: row for row in data.health_scores}
    adoption_by_id = {row.account_id: row for row in data.adoption_summaries}
    cases_by_id: dict[str, list[CRMCase]] = {}
    usage_by_id: dict[str, list[UsageSignal]] = {}
    milestones_by_id: dict[str, list[TimeToValueMilestone]] = {}
    for case in data.cases:
        cases_by_id.setdefault(case.account_id, []).append(case)
    for signal in data.usage_signals:
        usage_by_id.setdefault(signal.account_id, []).append(signal)
    for milestone in data.milestones:
        milestones_by_id.setdefault(milestone.account_id, []).append(milestone)
    emails_by_id: dict[str, list[str]] = {}
    for contact in data.contacts:
        emails_by_id.setdefault(contact.account_id, []).append(contact.email)

    decisions: list[SurfaceDecision] = []
    for account in sorted(data.accounts, key=lambda row: row.account_id):
        health = health_by_id[account.account_id]
        adoption = adoption_by_id[account.account_id]
        cases = tuple(cases_by_id.get(account.account_id, ()))
        usage = tuple(usage_by_id.get(account.account_id, ()))
        milestones = tuple(milestones_by_id.get(account.account_id, ()))
        evidence_ids = _surface_evidence_ids(usage, cases, milestones)
        consulted = ("health.band", "adoption.rate", "cases.open", "milestones.open")
        surfaced = (
            health.band == "red"
            or adoption.adoption_rate < 0.45
            or any(case.priority.lower() == "high" and case.closed_at is None for case in cases)
            or any(milestone.achieved_at is None for milestone in milestones)
        )
        emails = emails_by_id.get(account.account_id, ())
        has_identity_conflict = len(emails) != len(set(emails))
        abstained = has_identity_conflict and not surfaced
        if surfaced:
            if health.band == "red":
                disposition = "escalate"
                action = "recommend_next_best_action"
            else:
                disposition = "propose_customer_action"
                action = "draft_customer_outreach"
        else:
            disposition = "internal_review"
            action = None
        decisions.append(
            SurfaceDecision(
                decision_id=det_id("world-decision", account.account_id, SEED_DATE),
                account_id=account.account_id,
                decision_time=f"{SEED_DATE}T00:00:00Z",
                surfaced=surfaced,
                disposition=disposition,
                recommended_action=action,
                evidence_ids=evidence_ids,
                consulted_fact_keys=consulted,
                abstained=abstained,
            )
        )
    return tuple(decisions)


def write_world_artifacts(
    result: WorldBuildResult,
    *,
    root: Path | None = None,
) -> Path:
    out_root = root or Path("build/world")
    seed_dir = out_root / f"seed-{result.config.seed}"
    seed_dir.mkdir(parents=True, exist_ok=True)
    (seed_dir / "world.json").write_text(
        json.dumps(serialize_world_build(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return seed_dir


def serialize_world_build(result: WorldBuildResult) -> dict[str, Any]:
    return {
        "artifact": "living_world",
        "schema_version": 1,
        "config": asdict(result.config),
        "counts": {
            "accounts": len(result.data.accounts),
            "contacts": len(result.data.contacts),
            "cases": len(result.data.cases),
            "opportunities": len(result.data.opportunities),
            "usage_signals": len(result.data.usage_signals),
            "latent_truth": len(result.latent_truth),
            "surface_decisions": len(result.surface_decisions),
        },
        "data": _serialize_fixture_data(result.data),
        "latent_truth": [asdict(row) for row in result.latent_truth],
        "surface_decisions": [asdict(row) for row in result.surface_decisions],
    }


def _anchor_slice(base: FixtureCustomerData, *, count: int) -> FixtureCustomerData:
    allowed = {account.account_id for account in base.accounts[:count]}
    return FixtureCustomerData(
        accounts=tuple(account for account in base.accounts if account.account_id in allowed),
        companies=tuple(company for company in base.companies if company.company_id in allowed),
        contacts=tuple(contact for contact in base.contacts if contact.account_id in allowed),
        cases=tuple(case for case in base.cases if case.account_id in allowed),
        opportunities=tuple(opp for opp in base.opportunities if opp.account_id in allowed),
        health_scores=tuple(row for row in base.health_scores if row.account_id in allowed),
        ctas=tuple(row for row in base.ctas if row.account_id in allowed),
        success_plans=tuple(row for row in base.success_plans if row.account_id in allowed),
        adoption_summaries=tuple(row for row in base.adoption_summaries if row.account_id in allowed),
        entitlements=tuple(row for row in base.entitlements if row.account_id in allowed),
        usage_signals=tuple(row for row in base.usage_signals if row.account_id in allowed),
        milestones=tuple(row for row in base.milestones if row.account_id in allowed),
        tenant_accounts=base.tenant_accounts,
        stakeholder_relationships=tuple(
            row for row in base.stakeholder_relationships if getattr(row, "account_id", None) in allowed
        ),
        job_change_signals=tuple(
            row for row in base.job_change_signals if getattr(row, "account_id", None) in allowed
        ),
        communication_signals=tuple(
            row for row in base.communication_signals if getattr(row, "account_id", None) in allowed
        ),
        internal_notes=tuple(
            row for row in base.internal_notes if getattr(row, "account_id", None) in allowed
        ),
    )


def _generate_accounts(
    config: WorldConfig,
    *,
    start_index: int,
    count: int,
) -> FixtureCustomerData:
    accounts: list[CRMAccount] = []
    companies: list[CSCompany] = []
    contacts: list[CRMContact] = []
    cases: list[CRMCase] = []
    opportunities: list[CRMOpportunity] = []
    health_scores: list[HealthScore] = []
    ctas: list[CTA] = []
    success_plans: list[SuccessPlan] = []
    adoption_summaries: list[AdoptionSummary] = []
    entitlements: list[Entitlement] = []
    usage_signals: list[UsageSignal] = []
    milestones: list[TimeToValueMilestone] = []

    for offset in range(count):
        index = start_index + offset
        slug = f"world-{config.seed:04d}-{index:04d}"
        account_id = det_id("world-account", config.seed, index)
        latent = _latent_tuple(config, index)
        industry = _pick(
            ("transportation", "logistics", "field_services", "manufacturing"),
            config.seed,
            index,
            "industry",
        )
        arr_cents = _range_value(config.seed, index, "arr", 1_500_000, 25_000_000)
        lifecycle_stage = "steady_state" if latent["quiet"] else "onboarding"
        health_band = "red" if latent["doomed"] else "green" if latent["thriving"] else "yellow"
        health_score = 32.0 if latent["doomed"] else 88.0 if latent["thriving"] else 63.0
        active_users = _range_value(config.seed, index, "users", 4, 42)
        licensed_users = max(
            active_users + _range_value(config.seed, index, "licensed", 2, 25),
            active_users,
        )
        active_assets = _range_value(config.seed, index, "assets", 8, 160)
        entitled_assets = max(
            active_assets + _range_value(config.seed, index, "entitled", 5, 80),
            active_assets,
        )
        if latent["doomed"]:
            active_users = max(2, active_users // 3)
            active_assets = max(4, active_assets // 3)
        elif latent["quiet"]:
            active_users = max(3, int(active_users * 0.6))
            active_assets = max(6, int(active_assets * 0.65))
        adoption_rate = round(active_assets / entitled_assets, 4)
        owner_id = f"csm-{100 + (index % 7)}"

        accounts.append(
            CRMAccount(
                account_id=account_id,
                name=_title_from_slug(slug),
                owner_id=owner_id,
                industry=industry,
            )
        )
        companies.append(
            CSCompany(
                company_id=account_id,
                name=_title_from_slug(slug),
                industry=industry,
                arr_cents=arr_cents,
                lifecycle_stage=lifecycle_stage,
                status="Active",
                original_contract_date="2026-01-01",
                renewal_date="2027-01-01",
                csm_owner_id=owner_id,
                current_score=health_score,
            )
        )
        champion_email = f"champion-{index}@{slug}.example"
        contacts.append(
            CRMContact(
                contact_id=det_id("world-contact", account_id, "champion"),
                account_id=account_id,
                email=champion_email,
                name=f"Champion {index}",
                role="champion",
                title="Director of Operations",
                consent_to_contact=True,
                org_level=3,
            )
        )
        if "duplicate_contact" in latent["corruption_flags"]:
            contacts.append(
                CRMContact(
                    contact_id=det_id("world-contact", account_id, "champion-dup"),
                    account_id=account_id,
                    email=champion_email,
                    name=f"Champion Duplicate {index}",
                    role="champion",
                    title="Ops Lead",
                    consent_to_contact=True,
                    org_level=3,
                )
            )
        health_scores.append(
            HealthScore(
                account_id=account_id,
                score=health_score,
                band=health_band,
                drivers=_drivers_for_band(health_band),
                measured_at=f"{SEED_DATE}T00:00:00Z",
            )
        )
        adoption_summaries.append(
            AdoptionSummary(
                account_id=account_id,
                active_users=active_users,
                licensed_users=licensed_users,
                active_assets=active_assets,
                entitled_assets=entitled_assets,
                adoption_rate=adoption_rate,
                underused_capabilities=("route_optimization",) if adoption_rate < 0.65 else (),
                measured_at=f"{SEED_DATE}T00:00:00Z",
            )
        )
        entitlements.extend(
            (
                Entitlement(
                    account_id=account_id,
                    capability="core_dispatch",
                    entitled_quantity=licensed_users,
                    unit="users",
                    starts_at="2026-01-01",
                ),
                Entitlement(
                    account_id=account_id,
                    capability="route_optimization",
                    entitled_quantity=entitled_assets,
                    unit="assets",
                    starts_at="2026-01-01",
                ),
            )
        )
        usage_signals.extend(
            (
                UsageSignal(
                    signal_id=det_id("world-signal", account_id, "active_assets"),
                    account_id=account_id,
                    grain="company",
                    subject_id=None,
                    metric_name="daily_active_assets",
                    value=float(active_assets),
                    unit="assets",
                    observed_at=f"{SEED_DATE}T00:00:00Z",
                    source_ref="world",
                ),
                UsageSignal(
                    signal_id=det_id("world-signal", account_id, "active_users"),
                    account_id=account_id,
                    grain="company",
                    subject_id=None,
                    metric_name="weekly_active_users",
                    value=float(active_users),
                    unit="users",
                    observed_at=f"{SEED_DATE}T00:00:00Z",
                    source_ref="world",
                ),
            )
        )
        milestones.append(
            TimeToValueMilestone(
                account_id=account_id,
                milestone="activate_50pct_assets",
                expected_by="2026-02-15",
                achieved_at=None if latent["doomed"] else "2026-02-07",
                evidence_signal_ids=(det_id("world-signal", account_id, "active_assets"),),
            )
        )
        success_plans.append(
            SuccessPlan(
                plan_id=det_id("world-plan", account_id),
                account_id=account_id,
                status="active",
                objectives=("activation", "adoption"),
                target_date="2026-03-01",
            )
        )
        if latent["doomed"]:
            cases.append(
                CRMCase(
                    case_id=det_id("world-case", account_id, "blocker"),
                    account_id=account_id,
                    status="Open",
                    priority="High",
                    origin="Email",
                    subject="Implementation blocker remains unresolved",
                    created_at=f"{SEED_DATE}T00:00:00Z",
                )
            )
            ctas.append(
                CTA(
                    cta_id=det_id("world-cta", account_id),
                    account_id=account_id,
                    reason="Red health with open high-priority blocker",
                    priority="High",
                    status="open",
                    due_date="2026-06-28",
                    owner_id=owner_id,
                )
            )
        elif latent["thriving"]:
            opportunities.append(
                CRMOpportunity(
                    opportunity_id=det_id("world-opp", account_id),
                    account_id=account_id,
                    stage_name="Qualification",
                    amount_cents=max(500_000, arr_cents // 4),
                    close_date="2026-09-30",
                    opportunity_type="Expansion",
                )
            )

    return FixtureCustomerData(
        accounts=tuple(accounts),
        companies=tuple(companies),
        contacts=tuple(contacts),
        cases=tuple(cases),
        opportunities=tuple(opportunities),
        health_scores=tuple(health_scores),
        ctas=tuple(ctas),
        success_plans=tuple(success_plans),
        adoption_summaries=tuple(adoption_summaries),
        entitlements=tuple(entitlements),
        usage_signals=tuple(usage_signals),
        milestones=tuple(milestones),
    )


def _latent_truth_for_world(
    config: WorldConfig,
    data: FixtureCustomerData,
) -> tuple[LatentAccountTruth, ...]:
    base_book = build_synthetic_book()
    base_ids = {account.account_id for account in base_book.accounts}
    simulated = simulate_data(base_book, day=180)
    health_by_id = {row.account_id: row for row in data.health_scores}

    # Single source of truth for the latent index each account was generated
    # at. A generated account's id is det_id("world-account", seed, gen_index),
    # so the generation index is recoverable from identity -- recording latent
    # at that SAME index makes recorded truth match the state that produced the
    # observables. Anchors (fixture-book accounts) have no generation index, so
    # they get a stable index past the generated range, keyed by fixture-book
    # position -- NOT by account_id sort order, which was the F1 bug.
    generated_count = sum(1 for row in data.accounts if row.account_id not in base_ids)
    latent_index_by_id: dict[str, int] = {
        det_id("world-account", config.seed, i): i for i in range(generated_count)
    }
    for book_pos, book_account in enumerate(base_book.accounts):
        latent_index_by_id.setdefault(book_account.account_id, generated_count + book_pos)

    latent_rows: list[LatentAccountTruth] = []
    for account in sorted(data.accounts, key=lambda row: row.account_id):
        latent_index = latent_index_by_id[account.account_id]
        anchor = account.account_id in base_ids and account.account_id in simulated.accounts
        if anchor:
            deep = simulated.accounts[account.account_id]
            doomed = (
                not deep.champion_active
                and deep.overall_csat is not None
                and deep.overall_csat < 3.2
            )
            thriving = deep.feature_depth_score >= 0.75 and deep.dau >= 8
            champion_engagement = "quiet" if not deep.champion_active else "engaged"
            product_fit = "strong" if deep.feature_depth_score >= 0.75 else "partial"
            org_state = "stable"
            corruption_flags: tuple[str, ...] = ()
            causal_chain = _anchor_causal_chain(health_by_id[account.account_id])
        else:
            latent = _latent_tuple(config, latent_index)
            doomed = latent["doomed"]
            thriving = latent["thriving"]
            champion_engagement = latent["champion_engagement"]
            product_fit = latent["product_fit"]
            org_state = latent["org_state"]
            corruption_flags = latent["corruption_flags"]
            causal_chain = latent["causal_chain"]
        latent_label = (
            "conflicted"
            if "duplicate_contact" in corruption_flags and doomed
            else "doomed"
            if doomed
            else "thriving"
            if thriving
            else "quiet"
        )
        latent_rows.append(
            LatentAccountTruth(
                account_id=account.account_id,
                account_slug=_slugify(account.name),
                anchor_account=anchor,
                doomed=doomed,
                thriving=thriving,
                champion_engagement=champion_engagement,
                product_fit=product_fit,
                org_state=org_state,
                latent_label=latent_label,
                corruption_flags=tuple(corruption_flags),
                causal_chain=tuple(causal_chain),
                observed_day=180 if anchor else 0,
                data_quality_flags=_data_quality_flags(config, latent_index),
                latent_outcome=_latent_outcome(config, latent_index, doomed=doomed, thriving=thriving),
            )
        )
    return tuple(latent_rows)


def _data_quality_flags(config: WorldConfig, index: int) -> tuple[str, ...]:
    """D3: three independent seeded rolls -- these CAN co-occur, unlike
    corruption_flags' single mutually-exclusive-kind roll above."""
    flags: list[str] = []
    if _fraction(config.seed, index, "missingness") < config.field_missingness_rate:
        flags.append("missing_field")
    if _fraction(config.seed, index, "staleness") < config.stale_observation_rate:
        flags.append("stale_observation")
    if _fraction(config.seed, index, "contradiction") < config.contradictory_source_rate:
        flags.append("contradictory_source")
    return tuple(flags)


def _latent_outcome(config: WorldConfig, index: int, *, doomed: bool, thriving: bool) -> str:
    """D5: pure derived view of doomed/thriving -- doomed splits 50/50
    seeded into churned/downgraded; thriving maps to expanded; else flat."""
    if doomed:
        return "churned" if _fraction(config.seed, index, "outcome-split") < 0.5 else "downgraded"
    if thriving:
        return "expanded"
    return "flat"


def _latent_tuple(config: WorldConfig, index: int) -> dict[str, Any]:
    doomed = _fraction(config.seed, index, "doomed") < config.doomed_rate
    thriving = (not doomed) and _fraction(config.seed, index, "thriving") < 0.18
    quiet = (
        (not doomed)
        and (not thriving)
        and _fraction(config.seed, index, "quiet") < config.quiet_majority_rate
    )
    corruption_flags: list[str] = []
    if _fraction(config.seed, index, "corruption") < config.corruption_rate:
        corruption_flags.append(
            _pick(
                ("duplicate_contact", "stale_field", "mislinked_case"),
                config.seed,
                index,
                "corruption-kind",
            )
        )
    if quiet and _fraction(config.seed, index, "red-herring") < config.red_herring_rate:
        corruption_flags.append("red_herring")
    champion_engagement = "quiet" if doomed else "high" if thriving else "medium"
    product_fit = "weak" if doomed else "strong" if thriving else "adequate"
    org_state = _pick(("stable", "reorg", "budget_pressure"), config.seed, index, "org")
    causal_chain = (
        "champion_disengaged" if doomed else "healthy_champion",
        "product_fit_gap" if doomed else "fit_confirmed",
        "org_change" if org_state != "stable" else "no_major_org_change",
    )
    return {
        "doomed": doomed,
        "thriving": thriving,
        "quiet": quiet,
        "champion_engagement": champion_engagement,
        "product_fit": product_fit,
        "org_state": org_state,
        "corruption_flags": tuple(dict.fromkeys(corruption_flags)),
        "causal_chain": causal_chain,
    }


def _merge_fixture_data(left: FixtureCustomerData, right: FixtureCustomerData) -> FixtureCustomerData:
    return FixtureCustomerData(
        accounts=left.accounts + right.accounts,
        companies=left.companies + right.companies,
        contacts=left.contacts + right.contacts,
        cases=left.cases + right.cases,
        opportunities=left.opportunities + right.opportunities,
        health_scores=left.health_scores + right.health_scores,
        ctas=left.ctas + right.ctas,
        success_plans=left.success_plans + right.success_plans,
        adoption_summaries=left.adoption_summaries + right.adoption_summaries,
        entitlements=left.entitlements + right.entitlements,
        usage_signals=left.usage_signals + right.usage_signals,
        milestones=left.milestones + right.milestones,
        tenant_accounts=left.tenant_accounts,
        stakeholder_relationships=left.stakeholder_relationships + right.stakeholder_relationships,
        job_change_signals=left.job_change_signals + right.job_change_signals,
        communication_signals=left.communication_signals + right.communication_signals,
        internal_notes=left.internal_notes + right.internal_notes,
    )


def _serialize_fixture_data(data: FixtureCustomerData) -> dict[str, Any]:
    return {
        "accounts": [asdict(row) for row in data.accounts],
        "companies": [asdict(row) for row in data.companies],
        "contacts": [asdict(row) for row in data.contacts],
        "cases": [asdict(row) for row in data.cases],
        "opportunities": [asdict(row) for row in data.opportunities],
        "health_scores": [asdict(row) for row in data.health_scores],
        "ctas": [asdict(row) for row in data.ctas],
        "success_plans": [asdict(row) for row in data.success_plans],
        "adoption_summaries": [asdict(row) for row in data.adoption_summaries],
        "entitlements": [asdict(row) for row in data.entitlements],
        "usage_signals": [asdict(row) for row in data.usage_signals],
        "milestones": [asdict(row) for row in data.milestones],
    }


def _drivers_for_band(band: str) -> tuple[str, ...]:
    """Health drivers derived from the OBSERVABLE band -- never from latent
    truth. Used for both generated and anchor accounts so an agent reading
    health.drivers learns nothing it could not compute from the band itself."""
    if band == "red":
        return ("health_red", "usage_decline", "support_pressure")
    if band == "yellow":
        return ("slow_activation", "partial_adoption", "routine_friction")
    return ("healthy_usage", "stable_contacts", "base_rate_boring")


def _anchor_causal_chain(health: HealthScore) -> tuple[str, ...]:
    return _drivers_for_band(health.band)


def _surface_evidence_ids(
    usage: tuple[UsageSignal, ...],
    cases: tuple[CRMCase, ...],
    milestones: tuple[TimeToValueMilestone, ...],
) -> tuple[str, ...]:
    evidence_ids: list[str] = []
    if usage:
        evidence_ids.append(usage[0].signal_id)
    if cases:
        evidence_ids.append(cases[0].case_id)
    if milestones:
        evidence_ids.extend(milestones[0].evidence_signal_ids[:1])
    return tuple(dict.fromkeys(evidence_ids))


def _fraction(seed: int, index: int, label: str) -> float:
    digest = hashlib.md5(f"{seed}:{index}:{label}".encode(), usedforsecurity=False).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _pick(options: tuple[str, ...], seed: int, index: int, label: str) -> str:
    return options[int(_fraction(seed, index, label) * len(options)) % len(options)]


def _range_value(seed: int, index: int, label: str, lo: int, hi: int) -> int:
    return lo + int(_fraction(seed, index, label) * (hi - lo))


def _slugify(name: str) -> str:
    return name.lower().replace(" ", "-")


def _title_from_slug(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))
