"""Deterministic time-evolution simulator for the 35-account synthetic book.

Takes a base ``FixtureCustomerData`` (from ``build_synthetic_book()``) and
applies a pre-programmed 365-day scenario timeline of mutations to produce a
new snapshot at any given ``day_offset``.  All mutations are deterministic
given the day offset — no randomness is involved.

Usage::

    from ultra_csm.data_plane.synthetic_book import build_synthetic_book
    from ultra_csm.data_plane.book_simulator import simulate_book

    base = build_synthetic_book()
    day_90 = simulate_book(base, day_offset=90)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ultra_csm.data_plane.contracts import (
    AdoptionSummary,
    CRMCase,
    CRMContact,
    CSCompany,
    HealthScore,
    TimeToValueMilestone,
    UsageSignal,
)
from ultra_csm.data_plane.fixtures import FixtureCustomerData, det_id
from ultra_csm.data_plane.synthetic_book import (
    SEED_DATE,
    _ADOPTION,
    _id,
)


# ---------------------------------------------------------------------------
# Mutation dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UsageDecline:
    """Reduce active_users and active_assets by a fixed rate each day.

    When *end_day* is set, accumulation stops at that day.
    """

    account_slug: str
    day_offset: int
    user_rate_per_day: float
    asset_rate_per_day: float
    end_day: int | None = None


@dataclass(frozen=True)
class UsageGrowth:
    """Increase active_users and active_assets by a fixed rate each day."""

    account_slug: str
    day_offset: int
    user_rate_per_day: float
    asset_rate_per_day: float
    end_day: int | None = None


@dataclass(frozen=True)
class ChampionGoesQuiet:
    """After the trigger day the champion contact is effectively silent."""

    account_slug: str
    day_offset: int


@dataclass(frozen=True)
class NewContactAppears:
    """A new stakeholder appears at the given day."""

    account_slug: str
    day_offset: int
    name: str
    role: str
    title: str
    email: str


@dataclass(frozen=True)
class MilestoneCompleted:
    """Mark a TTV milestone as achieved at the given day."""

    account_slug: str
    milestone_name: str
    day_offset: int


@dataclass(frozen=True)
class TicketSpike:
    """Add new open support tickets at the given day."""

    account_slug: str
    day_offset: int
    count: int


@dataclass(frozen=True)
class CSATDecline:
    """Health score drifts by *rate_per_day* each day after the trigger.

    Positive rate = score drops.  Negative rate = score improves (recovery).
    """

    account_slug: str
    day_offset: int
    rate_per_day: float
    end_day: int | None = None


@dataclass(frozen=True)
class HealthBandChange:
    """Directly set the health band and drivers at the given day."""

    account_slug: str
    day_offset: int
    new_band: str
    new_drivers: tuple[str, ...]


@dataclass(frozen=True)
class LifecycleChange:
    """Change an account's lifecycle stage."""

    account_slug: str
    day_offset: int
    new_stage: str


@dataclass(frozen=True)
class StatusChange:
    """Change an account's status (e.g. Active → Churned).

    A change to "Churned" also zeroes adoption and forces red health.
    """

    account_slug: str
    day_offset: int
    new_status: str


@dataclass(frozen=True)
class ARRChange:
    """Change an account's ARR (expansion or contraction)."""

    account_slug: str
    day_offset: int
    new_arr_cents: int


Mutation = (
    UsageDecline
    | UsageGrowth
    | ChampionGoesQuiet
    | NewContactAppears
    | MilestoneCompleted
    | TicketSpike
    | CSATDecline
    | HealthBandChange
    | LifecycleChange
    | StatusChange
    | ARRChange
)


# ---------------------------------------------------------------------------
# 365-day scenario timeline
#
# Organized by quarter.  Events are distributed realistically — some months
# are quiet, some are busy.  The narrative arcs:
#
#   Onboarding cohort (6) → most complete by day 60, one (Pinehill) drags
#   At-risk cohort (5) → 3 churn, 2 recover (Cypress, Copperfield)
#   Renewal cohort (3) → 2 renew, 1 saved with conditions
#   Expansion cohort (4) → 2 close expansions, 1 new dept ramp
#   Steady-state (15) → seasonal dips, one crisis (Hawkstone),
#                        one champion departure (Blueridge), advocacy (Trailhead)
#   Churned (2) → stay churned (already at day 0)
# ---------------------------------------------------------------------------

SCENARIO_TIMELINE: list[Mutation] = [
    # =====================================================================
    # Q1  MONTH 1 (Days 1-30)
    # Early signals, onboarding momentum, first fires
    # =====================================================================

    # Day 3 — Pinnacle's sole champion goes quiet; Sagebrush bleeds
    ChampionGoesQuiet("pinnacle-supply", 3),
    UsageDecline("sagebrush-transport", 3, 0.4, 0.6, end_day=70),
    # --- Synthetic Universe Bible: single-threaded-risk extension
    # (Pinnacle) --- The champion-quiet health penalty above moves the
    # band, but adoption/seat-penetration never moved without this: no
    # UsageDecline existed for this account, so a seat-penetration/
    # feature-depth-reading pillar saw a frozen day-0 snapshot for the
    # entire arc. Sized to stay under the ~9.5% mark -- real and visible
    # in raw usage/adoption data, but not large enough to trip the
    # engine's own >20% auto health-adjustment on top of the explicit
    # champion-quiet penalty already driving the band.
    UsageDecline("pinnacle-supply", 3, 0.05, 0.15, end_day=130),

    # Day 5 — Harborview CSAT drops toward renewal; Cedar Valley wobbles
    CSATDecline("harborview-fleet", 5, 1.0, end_day=45),
    UsageDecline("cedar-valley", 5, 0.2, 0.3, end_day=30),

    # Day 7 — Pinehill milestone; Ironhorse momentum; Cypress escalates
    MilestoneCompleted("pinehill-transport", "activate_50pct_assets", 7),
    UsageGrowth("ironhorse-freight", 7, 1.5, 2.0, end_day=35),
    # --- Synthetic Universe Bible: onboarding-stall extension (Pinehill) ---
    # Real adoption drag paired with the legacy-dispatch-integration cases
    # (day 0/30/80, _CASE_SCHEDULE) -- previously the stall was visible
    # only in cases/champion-latency/Rocketlane, leaving the seat-
    # penetration/feature-depth pillars reading a frozen day-0 snapshot
    # through the whole arc. -20%+ of the tiny 12-asset baseline, large
    # enough to also trip the engine's own usage-derived health penalty
    # (Pinehill carries no other score-affecting mutation), so the
    # briefing's own score finally tracks the stall too.
    UsageDecline("pinehill-transport", 10, 0.03, 0.04, end_day=100),
    UsageGrowth("pinehill-transport", 100, 0.025, 0.035, end_day=300),
    TicketSpike("cypress-field", 7, 3),

    # Day 10 — Harborview goes red; Meridian expansion contact appears
    HealthBandChange("harborview-fleet", 10, "red",
                     ("declining_csat", "renewal_at_risk", "erp_integration_blocker")),
    TicketSpike("harborview-fleet", 10, 1),
    NewContactAppears("meridian-fleet", 10, "Sarah Chen", "facilities",
                      "Facilities Manager", "sarah.chen@meridian-fleet.example"),

    # Day 14 — Meridian new-dept ramp; Bison slow bleed; Pinnacle risk visible
    UsageGrowth("meridian-fleet", 14, 0.15, 0.1, end_day=180),
    UsageDecline("bison-transport", 14, 0.5, 1.0, end_day=160),
    HealthBandChange("pinnacle-supply", 14, "yellow",
                     ("champion_inactive", "single_threaded_risk")),

    # Day 21 — Copperfield cliff; Summit milestone
    UsageDecline("copperfield-warehousing", 21, 1.5, 3.0, end_day=55),
    HealthBandChange("copperfield-warehousing", 21, "yellow",
                     ("usage_cliff", "sudden_disengagement")),
    MilestoneCompleted("summit-industrial", "activate_50pct_assets", 21),

    # =====================================================================
    # Q1  MONTH 2 (Days 31-60)
    # Onboarding completions, renewals, first churn
    # =====================================================================

    # Day 30 — Cedar Valley renewal closes (barely); Ironhorse graduates
    HealthBandChange("cedar-valley", 30, "green", ("renewed", "stabilizing")),
    LifecycleChange("ironhorse-freight", 30, "adopting"),

    # Day 35 — Pinehill routing milestone; Ironhorse health green
    MilestoneCompleted("pinehill-transport", "configure_routing", 35),
    HealthBandChange("ironhorse-freight", 35, "green",
                     ("activation_complete", "growing_usage")),

    # Day 40 — Summit + Northstar graduate; Clearwater milestone
    LifecycleChange("summit-industrial", 40, "adopting"),
    LifecycleChange("northstar-couriers", 40, "adopting"),
    MilestoneCompleted("clearwater-field-ops", "activate_50pct_assets", 40),

    # Day 45 — Harborview save play succeeds; slow recovery begins
    HealthBandChange("harborview-fleet", 45, "yellow",
                     ("save_play_active", "renewal_negotiating")),
    CSATDecline("harborview-fleet", 45, -0.3, end_day=280),

    # Day 50 — Driftwood churns (at-risk, zero engagement for months)
    StatusChange("driftwood-warehousing", 50, "Churned"),
    HealthBandChange("driftwood-warehousing", 50, "red",
                     ("churned", "no_engagement_recovery")),

    # Day 55 — Copperfield cliff bottoms; CSM intervenes, usage rebuilds
    HealthBandChange("copperfield-warehousing", 55, "yellow",
                     ("csm_intervention", "stabilizing")),
    UsageGrowth("copperfield-warehousing", 55, 0.5, 1.0, end_day=170),

    # =====================================================================
    # Q1  MONTH 3 (Days 61-90)
    # Expansion, churn, advocacy
    # =====================================================================

    # Day 65 — Oakmont expansion contact
    NewContactAppears("oakmont-logistics", 65, "Rachel Torres", "fleet_operations",
                      "Fleet Ops Director",
                      "rachel.torres@oakmont-logistics.example"),

    # Day 70 — Sagebrush churns
    StatusChange("sagebrush-transport", 70, "Churned"),
    HealthBandChange("sagebrush-transport", 70, "red",
                     ("churned", "usage_zero", "no_response")),

    # Day 75 — Cypress support issues resolving
    HealthBandChange("cypress-field", 75, "yellow",
                     ("support_issues_resolving", "engagement_improving")),

    # Day 80 — Trailhead advocacy: reference call
    HealthBandChange("trailhead-logistics", 80, "green",
                     ("exemplary_adoption", "strong_champion", "advocacy_active")),

    # Day 90 — Ridgeline late onboarding; Clearwater + Ridgeline graduate
    MilestoneCompleted("ridgeline-warehousing", "admin_setup", 90),
    LifecycleChange("clearwater-field-ops", 90, "adopting"),
    LifecycleChange("ridgeline-warehousing", 90, "adopting"),

    # =====================================================================
    # Q2  MONTHS 4-5 (Days 91-150)
    # Summer dip, expansion close, Pinnacle save play
    # =====================================================================

    # --- Synthetic Universe Bible: silent-decline extension (Aspenridge) ---
    # Slow continuous decline, day 90 onward. Deliberately calibrated to
    # stay under the engine's own automatic usage-derived health adjustment
    # (book_simulator.py's ">20% change from active_assets baseline"
    # penalty, applied to any account not already carrying an explicit
    # score delta) -- that threshold is exactly what this arc is testing:
    # a real, sustained decline too small for the existing scoring engine
    # to catch on its own, so the band never moves and no HealthBandChange
    # ever fires for this account across the full 365 days.
    UsageDecline("aspenridge-supply", 90, 0.006, 0.008, end_day=340),

    # Day 100 — Summer usage dip across fleet accounts
    UsageDecline("trailhead-logistics", 100, 0.3, 0.5, end_day=150),
    UsageDecline("bison-transport", 100, 0.3, 0.5, end_day=150),
    UsageDecline("redwood-fleet", 100, 0.15, 0.2, end_day=150),
    UsageDecline("stonebridge-fleet", 100, 0.1, 0.15, end_day=150),

    # Day 110 — New champion candidate surfaces at Pinnacle
    NewContactAppears("pinnacle-supply", 110, "Monica Reeves", "supply_chain",
                      "VP Supply Chain Operations",
                      "monica.reeves@pinnacle-supply.example"),

    # Day 120 — Oakmont expansion closes ($11.5M → $15.5M)
    ARRChange("oakmont-logistics", 120, 15_500_000),
    HealthBandChange("oakmont-logistics", 120, "green",
                     ("expansion_closed", "high_adoption")),

    # Day 130 — Pinnacle new champion engaged; recovery starts
    HealthBandChange("pinnacle-supply", 130, "yellow",
                     ("new_champion_engaged", "recovery_in_progress")),
    CSATDecline("pinnacle-supply", 130, -0.2, end_day=240),
    # Adoption recovery paired with the new champion, not just a band flip.
    UsageGrowth("pinnacle-supply", 130, 0.06, 0.2, end_day=240),

    # Day 140 — Cypress fully recovered
    HealthBandChange("cypress-field", 140, "green",
                     ("support_resolved", "engagement_restored")),

    # =====================================================================
    # Q2  MONTH 6 (Days 151-180)
    # Recovery, case study, champion departure
    # =====================================================================

    # Day 160 — Summer recovery; Bison CSM intervention kicks in
    UsageGrowth("trailhead-logistics", 160, 0.3, 0.5, end_day=230),
    UsageGrowth("redwood-fleet", 160, 0.15, 0.2, end_day=230),
    UsageGrowth("bison-transport", 160, 0.8, 1.5, end_day=230),
    HealthBandChange("bison-transport", 160, "yellow",
                     ("csm_intervention", "usage_recovering")),

    # Day 165 — Trailhead case study published
    HealthBandChange("trailhead-logistics", 165, "green",
                     ("exemplary_adoption", "strong_champion",
                      "case_study_published")),

    # Day 170 — Copperfield recovery crosses threshold
    HealthBandChange("copperfield-warehousing", 170, "green",
                     ("recovered", "csm_intervention_success")),

    # Day 180 — Meridian expansion ($28M → $36M); Blueridge champion departs
    ARRChange("meridian-fleet", 180, 36_000_000),
    ChampionGoesQuiet("blueridge-transport", 180),
    HealthBandChange("blueridge-transport", 180, "yellow",
                     ("champion_departed", "transition_risk")),

    # =====================================================================
    # Q3  MONTHS 7-9 (Days 181-270)
    # Hawkstone crisis, Quarrystone churn, recoveries, Q4 prep
    # =====================================================================

    # Day 200 — Hawkstone sudden crisis: new CFO, competitor eval
    HealthBandChange("hawkstone-industries", 200, "yellow",
                     ("leadership_change", "competitor_evaluation",
                      "budget_review")),
    CSATDecline("hawkstone-industries", 200, 0.8, end_day=260),

    # Day 205 — Hawkstone ticket spike
    TicketSpike("hawkstone-industries", 205, 3),

    # --- Synthetic Universe Bible: churn-brewing extension (Quarrystone) ---
    # Base fixture data already starts this account red at day 0
    # (champion_departed/no_successor -- see synthetic_book.py's _HEALTH
    # dict), so the "brewing" here is NOT a health-band transition (there
    # is no green-to-red arc to script; a HealthBandChange to "yellow"
    # here would read as an unearned improvement right before churn, which
    # was an authoring mistake in an earlier draft of this extension).
    # The actual brewing signal is the ABSENCE of remediation despite the
    # account being visibly flagged the entire time: no replacement
    # contact ever appears (contrast Pinnacle's day-110 NewContactAppears),
    # a rising ticket count, and a renewal conversation that goes
    # unanswered -- all still red/at-risk the whole way to the day-220
    # churn below.
    ChampionGoesQuiet("quarrystone-logistics", 0),
    TicketSpike("quarrystone-logistics", 160, 2),

    # Day 220 — Quarrystone churns (champion departed at day 0, never replaced)
    StatusChange("quarrystone-logistics", 220, "Churned"),
    HealthBandChange("quarrystone-logistics", 220, "red",
                     ("churned", "champion_never_replaced")),

    # Day 230 — Bison fully recovered
    HealthBandChange("bison-transport", 230, "green",
                     ("recovered", "stable_usage")),

    # Day 240 — Pinnacle recovery succeeds
    HealthBandChange("pinnacle-supply", 240, "green",
                     ("new_champion_active", "recovery_complete")),

    # Day 250 — Blueridge new champion identified
    NewContactAppears("blueridge-transport", 250, "Jessica Huang",
                      "transportation", "Director of Transportation",
                      "jessica.huang@blueridge-transport.example"),
    HealthBandChange("blueridge-transport", 250, "yellow",
                     ("new_champion_onboarding", "transition_in_progress")),

    # Day 260 — Hawkstone competitive threat defeated
    HealthBandChange("hawkstone-industries", 260, "green",
                     ("competitor_defeated", "cfo_aligned",
                      "renewal_path_clear")),

    # Day 270 — Year-end usage uptick (holiday logistics)
    UsageGrowth("trailhead-logistics", 270, 0.5, 0.8, end_day=330),
    UsageGrowth("bison-transport", 270, 0.3, 0.5, end_day=330),
    UsageGrowth("meridian-fleet", 270, 0.4, 0.6, end_day=330),

    # =====================================================================
    # Q4  MONTHS 10-12 (Days 271-365)
    # Renewals, recoveries, year-end
    # =====================================================================

    # Day 280 — Hawkstone fully recovered
    HealthBandChange("hawkstone-industries", 280, "green",
                     ("exemplary_adoption", "leadership_aligned")),

    # Day 290 — Blueridge recovery complete
    HealthBandChange("blueridge-transport", 290, "green",
                     ("new_champion_active", "growing_usage")),
    UsageGrowth("blueridge-transport", 290, 0.2, 0.3, end_day=365),

    # Day 300 — Pinehill finally graduates to steady state
    LifecycleChange("pinehill-transport", 300, "steady_state"),
    HealthBandChange("pinehill-transport", 300, "green",
                     ("onboarding_complete", "stable_adoption")),

    # Day 320 — Falcon growth; small but consistent
    UsageGrowth("falcon-delivery", 320, 0.1, 0.15, end_day=365),
    HealthBandChange("falcon-delivery", 320, "green",
                     ("growing_adoption", "on_track")),

    # Day 340 — Prairie Wind expansion signal
    NewContactAppears("prairie-wind", 340, "Greg Patterson", "operations",
                      "Operations Expansion Lead",
                      "greg.patterson@prairie-wind.example"),
    HealthBandChange("prairie-wind", 340, "green",
                     ("expansion_signal", "growing_usage")),

    # Day 350 — Mesa steady through renewal
    HealthBandChange("mesa-industrial", 350, "green",
                     ("stable_adoption", "renewal_complete")),
]


# ---------------------------------------------------------------------------
# Health-band thresholds
# ---------------------------------------------------------------------------

_GREEN_THRESHOLD = 75.0
_YELLOW_THRESHOLD = 40.0


def _band_for_score(score: float) -> str:
    if score >= _GREEN_THRESHOLD:
        return "green"
    if score >= _YELLOW_THRESHOLD:
        return "yellow"
    return "red"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEED_DT = datetime.fromisoformat(SEED_DATE)


def _day_iso(day_offset: int) -> str:
    return (_SEED_DT + timedelta(days=day_offset)).strftime("%Y-%m-%d")


def _day_clock(day_offset: int) -> str:
    base = datetime(2026, 6, 21, 0, 0, 0, tzinfo=timezone.utc)
    return (base + timedelta(days=day_offset)).strftime("%Y-%m-%dT%H:%M:%SZ")


# Reverse lookup: account_id → slug
_id_to_slug: dict[str, str] = {v: k for k, v in _id.items()}


def _slug_for_id(account_id: str) -> str | None:
    return _id_to_slug.get(account_id)


def _effective_days(mutation_day: int, day_offset: int,
                    end_day: int | None) -> int:
    """Compute how many days a rate-based mutation has been active."""
    cap = min(day_offset, end_day) if end_day is not None else day_offset
    return max(0, cap - mutation_day)


# ---------------------------------------------------------------------------
# Core simulator
# ---------------------------------------------------------------------------


def simulate_book(
    base_book: FixtureCustomerData,
    day_offset: int,
) -> FixtureCustomerData:
    """Apply deterministic mutations for *day_offset* days past SEED_DATE.

    Returns a new ``FixtureCustomerData`` with all applicable mutations from
    ``SCENARIO_TIMELINE`` applied.  The base book is never modified.
    """
    if day_offset <= 0:
        return base_book

    # Build mutable working copies keyed by account_id.
    health_by_id: dict[str, HealthScore] = {
        h.account_id: h for h in base_book.health_scores
    }
    adoption_by_id: dict[str, AdoptionSummary] = {
        a.account_id: a for a in base_book.adoption_summaries
    }
    signals_by_key: dict[tuple[str, str], UsageSignal] = {
        (s.account_id, s.metric_name): s for s in base_book.usage_signals
    }
    company_by_id: dict[str, CSCompany] = {
        c.company_id: c for c in base_book.companies
    }
    milestones_list: list[TimeToValueMilestone] = list(base_book.milestones)
    cases_list: list[CRMCase] = list(base_book.cases)
    contacts_list: list[CRMContact] = list(base_book.contacts)

    # Cumulative deltas from rate-based mutations.
    user_deltas: dict[str, float] = {}
    asset_deltas: dict[str, float] = {}
    score_deltas: dict[str, float] = {}

    # Deferred overrides (latest trigger wins per account).
    band_overrides: dict[str, HealthBandChange] = {}
    churned_accounts: set[str] = set()

    for mutation in SCENARIO_TIMELINE:
        if mutation.day_offset > day_offset:
            continue

        acct_id = _id[mutation.account_slug]

        if isinstance(mutation, UsageDecline):
            eff = _effective_days(mutation.day_offset, day_offset,
                                 mutation.end_day)
            user_deltas[acct_id] = user_deltas.get(acct_id, 0.0) - (
                mutation.user_rate_per_day * eff
            )
            asset_deltas[acct_id] = asset_deltas.get(acct_id, 0.0) - (
                mutation.asset_rate_per_day * eff
            )

        elif isinstance(mutation, UsageGrowth):
            eff = _effective_days(mutation.day_offset, day_offset,
                                 mutation.end_day)
            user_deltas[acct_id] = user_deltas.get(acct_id, 0.0) + (
                mutation.user_rate_per_day * eff
            )
            asset_deltas[acct_id] = asset_deltas.get(acct_id, 0.0) + (
                mutation.asset_rate_per_day * eff
            )

        elif isinstance(mutation, CSATDecline):
            eff = _effective_days(mutation.day_offset, day_offset,
                                 mutation.end_day)
            score_deltas[acct_id] = score_deltas.get(acct_id, 0.0) - (
                mutation.rate_per_day * eff
            )

        elif isinstance(mutation, HealthBandChange):
            prev = band_overrides.get(acct_id)
            if prev is None or mutation.day_offset >= prev.day_offset:
                band_overrides[acct_id] = mutation

        elif isinstance(mutation, ChampionGoesQuiet):
            hs = health_by_id[acct_id]
            new_score = max(0.0, hs.score - 5.0)
            drivers = set(hs.drivers)
            drivers.add("champion_inactive")
            health_by_id[acct_id] = HealthScore(
                account_id=acct_id,
                score=new_score,
                band=_band_for_score(new_score),
                drivers=tuple(sorted(drivers)),
                measured_at=_day_clock(mutation.day_offset),
            )

        elif isinstance(mutation, MilestoneCompleted):
            achieved_clock = _day_clock(mutation.day_offset)
            for i, ms in enumerate(milestones_list):
                if (ms.account_id == acct_id
                        and ms.milestone == mutation.milestone_name
                        and ms.achieved_at is None):
                    milestones_list[i] = TimeToValueMilestone(
                        account_id=ms.account_id,
                        milestone=ms.milestone,
                        expected_by=ms.expected_by,
                        achieved_at=achieved_clock,
                        evidence_signal_ids=ms.evidence_signal_ids,
                    )
                    break

        elif isinstance(mutation, TicketSpike):
            for idx in range(mutation.count):
                cases_list.append(CRMCase(
                    case_id=det_id("case", acct_id,
                                   f"sim-d{mutation.day_offset}-{idx}"),
                    account_id=acct_id,
                    status="Open",
                    priority="High",
                    origin="Email",
                    subject=(f"Simulated escalation "
                             f"(day {mutation.day_offset}, #{idx + 1})"),
                    created_at=_day_clock(mutation.day_offset),
                ))

        elif isinstance(mutation, NewContactAppears):
            contacts_list.append(CRMContact(
                contact_id=det_id("contact", acct_id, mutation.email),
                account_id=acct_id,
                email=mutation.email,
                name=mutation.name,
                role=mutation.role,
                title=mutation.title,
                consent_to_contact=True,
            ))

        elif isinstance(mutation, LifecycleChange):
            co = company_by_id[acct_id]
            company_by_id[acct_id] = CSCompany(
                company_id=co.company_id,
                name=co.name,
                industry=co.industry,
                arr_cents=co.arr_cents,
                lifecycle_stage=mutation.new_stage,
                status=co.status,
                original_contract_date=co.original_contract_date,
                renewal_date=co.renewal_date,
                csm_owner_id=co.csm_owner_id,
                current_score=co.current_score,
            )

        elif isinstance(mutation, StatusChange):
            co = company_by_id[acct_id]
            company_by_id[acct_id] = CSCompany(
                company_id=co.company_id,
                name=co.name,
                industry=co.industry,
                arr_cents=co.arr_cents,
                lifecycle_stage=co.lifecycle_stage,
                status=mutation.new_status,
                original_contract_date=co.original_contract_date,
                renewal_date=co.renewal_date,
                csm_owner_id=co.csm_owner_id,
                current_score=co.current_score,
            )
            if mutation.new_status == "Churned":
                churned_accounts.add(acct_id)

        elif isinstance(mutation, ARRChange):
            co = company_by_id[acct_id]
            company_by_id[acct_id] = CSCompany(
                company_id=co.company_id,
                name=co.name,
                industry=co.industry,
                arr_cents=mutation.new_arr_cents,
                lifecycle_stage=co.lifecycle_stage,
                status=co.status,
                original_contract_date=co.original_contract_date,
                renewal_date=co.renewal_date,
                csm_owner_id=co.csm_owner_id,
                current_score=co.current_score,
            )

    # ------------------------------------------------------------------
    # Apply cumulative usage deltas
    # ------------------------------------------------------------------
    for acct_id in set(user_deltas) | set(asset_deltas):
        if acct_id in churned_accounts:
            continue  # churned accounts are zeroed below

        adoption = adoption_by_id.get(acct_id)
        if adoption is None:
            continue

        u_delta = user_deltas.get(acct_id, 0.0)
        a_delta = asset_deltas.get(acct_id, 0.0)

        new_users = max(0, int(adoption.active_users + u_delta))
        new_users = min(new_users, adoption.licensed_users)
        new_assets = max(0, int(adoption.active_assets + a_delta))
        entitled = adoption.entitled_assets
        new_rate = round(new_assets / entitled, 2) if entitled > 0 else 0.0

        adoption_by_id[acct_id] = AdoptionSummary(
            account_id=acct_id,
            active_users=new_users,
            licensed_users=adoption.licensed_users,
            active_assets=new_assets,
            entitled_assets=entitled,
            adoption_rate=new_rate,
            underused_capabilities=adoption.underused_capabilities,
            measured_at=_day_clock(day_offset),
        )

        sig_key = (acct_id, "daily_active_assets")
        if sig_key in signals_by_key:
            old = signals_by_key[sig_key]
            signals_by_key[sig_key] = UsageSignal(
                signal_id=old.signal_id,
                account_id=acct_id,
                grain=old.grain,
                subject_id=old.subject_id,
                metric_name=old.metric_name,
                value=float(new_assets),
                unit=old.unit,
                observed_at=_day_clock(day_offset),
                source_ref=old.source_ref,
            )

    # ------------------------------------------------------------------
    # Zero out churned accounts
    # ------------------------------------------------------------------
    for acct_id in churned_accounts:
        adoption = adoption_by_id.get(acct_id)
        if adoption is not None:
            adoption_by_id[acct_id] = AdoptionSummary(
                account_id=acct_id,
                active_users=0,
                licensed_users=0,
                active_assets=0,
                entitled_assets=0,
                adoption_rate=0.0,
                underused_capabilities=(),
                measured_at=_day_clock(day_offset),
            )
        sig_key = (acct_id, "daily_active_assets")
        if sig_key in signals_by_key:
            old = signals_by_key[sig_key]
            signals_by_key[sig_key] = UsageSignal(
                signal_id=old.signal_id,
                account_id=acct_id,
                grain=old.grain,
                subject_id=old.subject_id,
                metric_name=old.metric_name,
                value=0.0,
                unit=old.unit,
                observed_at=_day_clock(day_offset),
                source_ref=old.source_ref,
            )

    # ------------------------------------------------------------------
    # Apply cumulative score deltas
    # ------------------------------------------------------------------
    for acct_id, delta in score_deltas.items():
        if acct_id in churned_accounts:
            continue
        hs = health_by_id[acct_id]
        new_score = max(0.0, min(100.0, hs.score + delta))
        health_by_id[acct_id] = HealthScore(
            account_id=acct_id,
            score=round(new_score, 1),
            band=_band_for_score(new_score),
            drivers=hs.drivers,
            measured_at=_day_clock(day_offset),
        )

    # ------------------------------------------------------------------
    # Usage-derived health adjustments (> 20% change from baseline)
    # ------------------------------------------------------------------
    for acct_id in set(user_deltas) | set(asset_deltas):
        if acct_id in score_deltas or acct_id in churned_accounts:
            continue
        adoption = adoption_by_id.get(acct_id)
        if adoption is None:
            continue
        slug = _slug_for_id(acct_id)
        if slug is None or slug not in _ADOPTION:
            continue
        orig_assets = _ADOPTION[slug][2]
        if orig_assets <= 0:
            continue
        pct = (adoption.active_assets - orig_assets) / orig_assets
        if abs(pct) < 0.20:
            continue
        hs = health_by_id[acct_id]
        adj = pct * 30.0
        new_score = max(0.0, min(100.0, hs.score + adj))
        drivers = set(hs.drivers)
        if pct < -0.20:
            drivers.add("usage_decline")
        elif pct > 0.20:
            drivers.add("usage_growth")
        health_by_id[acct_id] = HealthScore(
            account_id=acct_id,
            score=round(new_score, 1),
            band=_band_for_score(new_score),
            drivers=tuple(sorted(drivers)),
            measured_at=_day_clock(day_offset),
        )

    # ------------------------------------------------------------------
    # Explicit HealthBandChange overrides (applied last, never clobbered).
    # Score is also adjusted so it stays consistent with the forced band.
    # ------------------------------------------------------------------
    for acct_id, mutation in band_overrides.items():
        hs = health_by_id[acct_id]
        score = hs.score
        if mutation.new_band == "green" and score < _GREEN_THRESHOLD:
            score = _GREEN_THRESHOLD
        elif mutation.new_band == "yellow":
            score = max(min(score, _GREEN_THRESHOLD - 0.1), _YELLOW_THRESHOLD)
        elif mutation.new_band == "red" and score >= _YELLOW_THRESHOLD:
            score = _YELLOW_THRESHOLD - 1.0
        health_by_id[acct_id] = HealthScore(
            account_id=acct_id,
            score=round(score, 1),
            band=mutation.new_band,
            drivers=mutation.new_drivers,
            measured_at=_day_clock(mutation.day_offset),
        )

    # ------------------------------------------------------------------
    # Sync company current_score with health
    # ------------------------------------------------------------------
    for acct_id, hs in health_by_id.items():
        co = company_by_id.get(acct_id)
        if co is not None and co.current_score != hs.score:
            company_by_id[acct_id] = CSCompany(
                company_id=co.company_id,
                name=co.name,
                industry=co.industry,
                arr_cents=co.arr_cents,
                lifecycle_stage=co.lifecycle_stage,
                status=co.status,
                original_contract_date=co.original_contract_date,
                renewal_date=co.renewal_date,
                csm_owner_id=co.csm_owner_id,
                current_score=hs.score,
            )

    # ------------------------------------------------------------------
    # Reassemble FixtureCustomerData
    # ------------------------------------------------------------------
    new_health = tuple(
        health_by_id.get(h.account_id, h) for h in base_book.health_scores
    )
    new_adoption = tuple(
        adoption_by_id.get(a.account_id, a)
        for a in base_book.adoption_summaries
    )
    new_companies = tuple(
        company_by_id.get(c.company_id, c) for c in base_book.companies
    )

    seen_keys: set[tuple[str, str]] = set()
    new_signals: list[UsageSignal] = []
    for sig in base_book.usage_signals:
        key = (sig.account_id, sig.metric_name)
        replacement = signals_by_key.get(key)
        if replacement is not None and key not in seen_keys:
            new_signals.append(replacement)
            seen_keys.add(key)
        else:
            new_signals.append(sig)

    return FixtureCustomerData(
        accounts=base_book.accounts,
        companies=new_companies,
        contacts=tuple(contacts_list),
        cases=tuple(cases_list),
        opportunities=base_book.opportunities,
        health_scores=new_health,
        ctas=base_book.ctas,
        success_plans=base_book.success_plans,
        adoption_summaries=new_adoption,
        entitlements=base_book.entitlements,
        usage_signals=tuple(new_signals),
        milestones=tuple(milestones_list),
        tenant_accounts=base_book.tenant_accounts,
    )
