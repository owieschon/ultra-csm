"""Deep data simulation layer for the 35-account synthetic book.

Instead of mutating health scores directly (as ``book_simulator`` does), this
module simulates the *underlying data streams* from which the value model
should compute scores:

1. Per-user activity timelines (login histories)
2. Feature adoption progression
3. Per-case lifecycles with CSAT
4. Opportunity stage progression
5. Contact role / title changes
6. CSM ↔ customer activity records

All simulation is **deterministic** given the day offset — the same day always
produces the same data.  Determinism is achieved via ``hashlib.md5`` keyed on
stable identifiers (account slug, contact id, day) rather than stdlib random.

Usage::

    from ultra_csm.data_plane.synthetic_book import build_synthetic_book
    from ultra_csm.data_plane.data_simulator import simulate_data

    base = build_synthetic_book()
    bundle = simulate_data(base, day=90)
    acct_data = bundle.accounts[some_account_id]
    print(acct_data.dau, acct_data.mau, acct_data.feature_depth_score)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from ultra_csm.data_plane.contracts import (
    CRMContact,
)
from ultra_csm.data_plane.fixtures import FixtureCustomerData, det_id
from ultra_csm.data_plane.synthetic_book import (
    SEED_DATE,
    _ACCT_DATA,
    _ADOPTION,
    _CONTACTS,
    _ENTITLEMENTS,
    _COMPANY,
    _HEALTH,
    _OPPS,
    _id,
)

# Re-use the date helpers from book_simulator.
from ultra_csm.data_plane.book_simulator import _SEED_DT, _day_iso, _day_clock

# ---------------------------------------------------------------------------
# Deterministic pseudo-random utilities
# ---------------------------------------------------------------------------

def _det_float(seed: str) -> float:
    """Deterministic float in [0, 1) from an arbitrary seed string."""
    digest = hashlib.md5(seed.encode(), usedforsecurity=False).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _det_int(seed: str, lo: int, hi: int) -> int:
    """Deterministic integer in [lo, hi] inclusive."""
    return lo + int(_det_float(seed) * (hi - lo + 1))


def _is_weekday(day: int) -> bool:
    """True if ``SEED_DATE + day`` falls on Mon-Fri."""
    return (_SEED_DT + timedelta(days=day)).weekday() < 5


def _tenure_days(slug: str, sim_day: int) -> int:
    """Total days since original contract date at simulation *sim_day*.

    Feature adoption timelines are relative to contract start, not SEED_DATE.
    A steady-state account with an 18-month history will show mature adoption
    even at simulation day 0.
    """
    contract_date_str = _COMPANY[slug][3]  # original_contract_date
    contract_dt = datetime.strptime(contract_date_str, "%Y-%m-%d")
    sim_dt = _SEED_DT + timedelta(days=sim_day)
    return max(0, (sim_dt - contract_dt).days)


# Mid-simulation churn days: accounts that churn during the 365-day simulation.
# (Riverstone and Dustbowl are already churned at day 0 via the "churned" persona.)
_CHURN_DAYS: dict[str, int] = {
    "driftwood-warehousing": 50,
    "sagebrush-transport": 70,
    "quarrystone-logistics": 220,
}


# ---------------------------------------------------------------------------
# Data types for the deep simulation bundle
# ---------------------------------------------------------------------------

FeatureStatus = Literal["not_started", "exploring", "adopted", "power_user"]
RoleType = Literal[
    "champion", "executive_sponsor", "technical_lead", "end_user", "admin"
]
EngagementLevel = Literal["high", "medium", "low", "inactive"]


@dataclass(frozen=True)
class UserLoginHistory:
    """Per-user login history across the simulation window."""

    contact_id: str
    account_id: str
    login_days: tuple[int, ...]
    role_type: RoleType
    is_champion: bool


@dataclass(frozen=True)
class FeatureAdoptionState:
    """Per-feature adoption state for an account at a point in time."""

    account_id: str
    feature: str
    status: FeatureStatus
    first_used_day: int | None
    users_active: int
    total_entitled_users: int


@dataclass(frozen=True)
class CaseLifecycle:
    """Individual support case with full lifecycle history."""

    case_id: str
    account_id: str
    open_day: int
    subject: str
    priority: str
    status: str  # Open, In Progress, Escalated, Resolved
    resolution_day: int | None
    csat_score: float | None  # 1.0–5.0 scale
    topic: str  # for repeat-topic detection


@dataclass(frozen=True)
class OpportunityTimeline:
    """Opportunity with stage progression history."""

    opportunity_id: str
    account_id: str
    opportunity_type: str
    amount_cents: int
    stages: tuple[tuple[str, int], ...]  # (stage_name, day_entered)
    current_stage: str


@dataclass(frozen=True)
class ContactEvolution:
    """Contact snapshot with role/title evolution."""

    contact_id: str
    account_id: str
    name: str
    current_title: str
    current_role_type: RoleType
    engagement_level: EngagementLevel
    appeared_day: int
    departed_day: int | None
    title_changes: tuple[tuple[str, int], ...]  # (new_title, day)


@dataclass(frozen=True)
class CSMActivityRecord:
    """Activity record between CSM and customer contact."""

    activity_id: str
    account_id: str
    contact_id: str | None
    channel: str  # call, email, meeting
    direction: str  # outbound, inbound
    day: int
    attendees: tuple[str, ...]


@dataclass(frozen=True)
class AccountDataBundle:
    """All granular data for a single account at a point in time."""

    account_id: str
    account_slug: str
    login_histories: tuple[UserLoginHistory, ...]
    feature_adoptions: tuple[FeatureAdoptionState, ...]
    cases: tuple[CaseLifecycle, ...]
    opportunities: tuple[OpportunityTimeline, ...]
    contacts: tuple[ContactEvolution, ...]
    activities: tuple[CSMActivityRecord, ...]
    # Computed aggregates — derived FROM the granular data above
    dau: int
    wau: int
    mau: int
    overall_csat: float | None
    feature_depth_score: float
    active_user_count: int
    champion_active: bool


@dataclass(frozen=True)
class SimulatedDataBundle:
    """Complete deep data simulation for all 35 accounts at a point in time."""

    day: int
    as_of_date: str
    accounts: dict[str, AccountDataBundle]


# ---------------------------------------------------------------------------
# Account persona definitions
#
# Each persona drives the base simulation parameters.  The SCENARIO_TIMELINE
# events in book_simulator are reflected here as day-keyed modifiers.
# ---------------------------------------------------------------------------

# Persona type → base parameters
#   login_weekday_p:  base probability a user logs in on a weekday
#   login_weekend_p:  base probability a user logs in on a weekend
#   feature_speed:    multiplier for feature adoption timeline (1.0 = normal)
#   case_rate:        average cases per 30-day period
#   csm_activity_rate: average CSM activities per 30-day period

@dataclass(frozen=True)
class _Persona:
    login_weekday_p: float
    login_weekend_p: float
    feature_speed: float
    case_rate: float
    csm_activity_rate: float


_PERSONAS: dict[str, _Persona] = {
    "fast_onboarding":    _Persona(0.70, 0.15, 1.4, 0.8, 6.0),
    "normal_onboarding":  _Persona(0.55, 0.10, 1.0, 1.2, 5.0),
    "stalled_onboarding": _Persona(0.30, 0.05, 0.5, 2.0, 7.0),
    "exemplary":          _Persona(0.90, 0.30, 2.0, 0.3, 3.0),
    "stable":             _Persona(0.75, 0.20, 1.2, 0.5, 2.5),
    "moderate":           _Persona(0.55, 0.12, 0.9, 0.8, 3.0),
    "expanding":          _Persona(0.80, 0.25, 1.5, 0.4, 4.0),
    "at_risk_champion":   _Persona(0.40, 0.08, 0.6, 1.5, 6.0),
    "at_risk_declining":  _Persona(0.25, 0.05, 0.3, 1.8, 5.0),
    "at_risk_support":    _Persona(0.50, 0.10, 0.7, 3.0, 7.0),
    "renewal_risk":       _Persona(0.50, 0.10, 0.8, 1.5, 5.0),
    "renewal_stable":     _Persona(0.70, 0.18, 1.1, 0.5, 3.0),
    "churned":            _Persona(0.00, 0.00, 0.0, 0.0, 0.0),
}

_ACCOUNT_PERSONA: dict[str, str] = {
    # Onboarding
    "ironhorse-freight":      "normal_onboarding",
    "pinehill-transport":     "stalled_onboarding",
    "ridgeline-warehousing":  "normal_onboarding",
    "northstar-couriers":     "fast_onboarding",
    "clearwater-field-ops":   "normal_onboarding",
    "summit-industrial":      "fast_onboarding",
    # Steady state
    "trailhead-logistics":    "exemplary",
    "crestline-distribution": "stable",
    "redwood-fleet":          "stable",
    "bison-transport":        "moderate",
    "copperfield-warehousing": "stable",
    "cascade-field":          "moderate",
    "timberline-logistics":   "stable",
    "falcon-delivery":        "moderate",
    "mesa-industrial":        "stable",
    "stonebridge-fleet":      "moderate",
    "prairie-wind":           "moderate",
    "aspenridge-supply":      "stable",
    "granite-peak":           "moderate",
    "ironridge-fleet":        "stable",
    "hawkstone-industries":   "stable",
    # Expanding
    "meridian-fleet":         "expanding",
    "oakmont-logistics":      "expanding",
    "blueridge-transport":    "expanding",
    "westfield-industrial":   "expanding",
    # At risk
    "pinnacle-supply":        "at_risk_champion",
    "sagebrush-transport":    "at_risk_declining",
    "driftwood-warehousing":  "at_risk_declining",
    "cypress-field":          "at_risk_support",
    "quarrystone-logistics":  "at_risk_champion",
    # Renewal
    "harborview-fleet":       "renewal_risk",
    "windmill-transport":     "renewal_stable",
    "cedar-valley":           "renewal_stable",
    # Churned
    "riverstone-logistics":   "churned",
    "dustbowl-freight":       "churned",
}

# ---------------------------------------------------------------------------
# Day-keyed modifiers aligned with SCENARIO_TIMELINE
#
# These override persona parameters at specific days to mirror the narrative
# arcs defined in book_simulator.py.
# ---------------------------------------------------------------------------

# (slug, start_day, end_day|None) → login probability multiplier
_LOGIN_MODIFIERS: list[tuple[str, int, int | None, float]] = [
    # Pinnacle champion goes quiet day 3
    ("pinnacle-supply",        3,   None, 0.3),
    # Sagebrush bleeds day 3–70 then churns
    ("sagebrush-transport",    3,   70,   0.4),
    ("sagebrush-transport",    70,  None, 0.0),
    # Ironhorse momentum day 7–35
    ("ironhorse-freight",      7,   35,   1.4),
    # Bison slow bleed day 14–160
    ("bison-transport",        14,  160,  0.6),
    # Copperfield cliff day 21–55
    ("copperfield-warehousing", 21, 55,   0.3),
    # Cedar Valley wobble day 5–30
    ("cedar-valley",           5,   30,   0.7),
    # Copperfield recovery day 55–170
    ("copperfield-warehousing", 55, 170,  0.8),
    # Driftwood churns day 50
    ("driftwood-warehousing",  50,  None, 0.0),
    # Summer dip day 100–150 for fleet accounts
    ("trailhead-logistics",    100, 150,  0.8),
    ("bison-transport",        100, 150,  0.7),
    ("redwood-fleet",          100, 150,  0.8),
    ("stonebridge-fleet",      100, 150,  0.85),
    # Bison recovery day 160–230
    ("bison-transport",        160, 230,  1.2),
    # Blueridge champion departs day 180
    ("blueridge-transport",    180, 250,  0.5),
    # Hawkstone crisis day 200–260
    ("hawkstone-industries",   200, 260,  0.7),
    # Quarrystone churns day 220
    ("quarrystone-logistics",  220, None, 0.0),
    # Year-end uptick day 270–330
    ("trailhead-logistics",    270, 330,  1.15),
    ("bison-transport",        270, 330,  1.1),
    ("meridian-fleet",         270, 330,  1.1),
    # Blueridge recovery day 290+
    ("blueridge-transport",    290, 365,  1.1),
    # Falcon growth day 320+
    ("falcon-delivery",        320, 365,  1.2),
]


def _login_multiplier(slug: str, day: int) -> float:
    """Compute the effective login probability multiplier for a given day."""
    mult = 1.0
    for s, start, end, m in _LOGIN_MODIFIERS:
        if s != slug:
            continue
        if day < start:
            continue
        if end is not None and day >= end:
            continue
        mult = m  # last matching modifier wins
    return mult


# ---------------------------------------------------------------------------
# Champion identification
# ---------------------------------------------------------------------------

# First contact listed for each account is treated as the champion.
_CHAMPION_CONTACT: dict[str, str] = {}
for _slug, _contact_rows in _CONTACTS.items():
    if _contact_rows:
        _name = _contact_rows[0][0]
        _email = _contact_rows[0][3]
        _aid = _id[_slug]
        _CHAMPION_CONTACT[_slug] = det_id("contact", _aid, _email)

# Days when the champion goes quiet (from SCENARIO_TIMELINE)
_CHAMPION_QUIET_DAYS: dict[str, int] = {
    "pinnacle-supply": 3,
    "blueridge-transport": 180,
}

# Days when a new contact appears (slug → list of (day, name, role, title, email))
_NEW_CONTACTS: dict[str, list[tuple[int, str, str, str, str]]] = {
    "meridian-fleet": [(10, "Sarah Chen", "facilities",
                        "Facilities Manager",
                        "sarah.chen@meridian-fleet.example")],
    "pinnacle-supply": [(110, "Monica Reeves", "supply_chain",
                         "VP Supply Chain Operations",
                         "monica.reeves@pinnacle-supply.example")],
    "oakmont-logistics": [(65, "Rachel Torres", "fleet_operations",
                           "Fleet Ops Director",
                           "rachel.torres@oakmont-logistics.example")],
    "blueridge-transport": [(250, "Jessica Huang", "transportation",
                             "Director of Transportation",
                             "jessica.huang@blueridge-transport.example")],
    "prairie-wind": [(340, "Greg Patterson", "operations",
                      "Operations Expansion Lead",
                      "greg.patterson@prairie-wind.example")],
}


# ---------------------------------------------------------------------------
# Role type assignment
# ---------------------------------------------------------------------------

def _infer_role_type(role: str | None, title: str | None, is_first: bool) -> RoleType:
    """Infer a stakeholder role type from CRM role/title fields."""
    t = (title or "").lower()
    r = (role or "").lower()
    if is_first:
        return "champion"
    if any(k in t for k in ("vp", "cto", "coo", "cfo", "director", "owner")):
        return "executive_sponsor"
    if any(k in t for k in ("it ", "tech", "engineer", "analyst")):
        return "technical_lead"
    if "admin" in t or "admin" in r:
        return "admin"
    return "end_user"


# ---------------------------------------------------------------------------
# Feature catalogue and adoption timeline
# ---------------------------------------------------------------------------

# All possible features in the product.  Order reflects typical adoption
# sequence (basic first, advanced later).
_FEATURE_CATALOGUE: tuple[str, ...] = (
    "core_telematics",
    "route_optimization",
    "maintenance_alerts",
    "fuel_analytics",
    "driver_coaching",
    "advanced_reporting",
    "compliance_dashboard",
    "dispatch_automation",
)

# Base days-to-reach-stage for a "normal" account per feature tier.
# (exploring_day, adopted_day, power_user_day) — relative to contract start.
_FEATURE_TIMELINES: dict[str, tuple[int, int, int]] = {
    "core_telematics":      (5,   30,  90),
    "route_optimization":   (20,  60,  150),
    "maintenance_alerts":   (15,  45,  120),
    "fuel_analytics":       (30,  90,  200),
    "driver_coaching":      (25,  75,  180),
    "advanced_reporting":   (40,  120, 270),
    "compliance_dashboard": (50,  150, 300),
    "dispatch_automation":  (60,  180, 365),
}


def _feature_status_at_day(
    tenure: int,
    feature: str,
    speed: float,
    account_seed: str,
) -> FeatureStatus:
    """Compute feature adoption status given total *tenure* days since contract.

    *tenure* is the number of days since the account's original contract date,
    NOT the simulation day offset.  This ensures long-tenured accounts show
    mature feature adoption even at simulation day 0.
    """
    timeline = _FEATURE_TIMELINES.get(feature)
    if timeline is None or speed <= 0:
        return "not_started"

    explore_day, adopt_day, power_day = timeline
    # Apply speed multiplier (faster = lower day thresholds)
    # Add per-account jitter so not all accounts adopt at the same day
    jitter = _det_float(f"{account_seed}:feat:{feature}") * 15 - 7.5
    explore_day = max(1, int(explore_day / speed + jitter))
    adopt_day = max(explore_day + 5, int(adopt_day / speed + jitter))
    power_day = max(adopt_day + 10, int(power_day / speed + jitter))

    if tenure >= power_day:
        return "power_user"
    if tenure >= adopt_day:
        return "adopted"
    if tenure >= explore_day:
        return "exploring"
    return "not_started"


# ---------------------------------------------------------------------------
# Case generation schedule
#
# Cases are deterministically placed at specific days for each account,
# aligned with the SCENARIO_TIMELINE narrative arcs.
# ---------------------------------------------------------------------------

# (slug, day, subject, priority, topic, resolve_after_days|None, csat|None)
_CASE_SCHEDULE: list[tuple[str, int, str, str, str, int | None, float | None]] = [
    # Ironhorse — GPS hardware issue during onboarding
    ("ironhorse-freight",    0,  "GPS hardware compatibility issue with older vehicles",
     "Medium", "hardware_compat", 25, 3.5),
    ("ironhorse-freight",    18, "Driver mobile app not syncing telemetry",
     "Low", "mobile_sync", 12, 4.0),

    # Pinehill — integration issues drag onboarding
    ("pinehill-transport",   0,  "Integration with legacy dispatch system failing",
     "High", "integration", 45, 2.5),
    ("pinehill-transport",   30, "Integration timeout errors persist",
     "High", "integration", 30, 2.0),
    ("pinehill-transport",   80, "Legacy dispatch connector still dropping events",
     "Medium", "integration", 20, 3.0),

    # Clearwater — basic questions
    ("clearwater-field-ops", 0,  "Question about mobile app setup for technicians",
     "Low", "setup_question", 8, 4.5),

    # Trailhead — rare, low-priority feature requests
    ("trailhead-logistics",  0,  "Feature request: custom compliance report template",
     "Low", "feature_request", 35, 5.0),
    ("trailhead-logistics",  120, "Request for API webhook for new asset alerts",
     "Low", "feature_request", 20, 4.5),

    # Sagebrush — frustration before churn
    ("sagebrush-transport",  0,  "Frustrated with slow reporting performance",
     "High", "performance", 40, 1.5),
    ("sagebrush-transport",  25, "Dashboard load times unacceptable",
     "High", "performance", None, None),  # never resolved

    # Cypress — repeated support escalations
    ("cypress-field",        0,  "Repeated GPS accuracy issues in rural areas",
     "High", "gps_accuracy", 50, 2.5),
    ("cypress-field",        7,  "GPS accuracy: 3rd report this month",
     "High", "gps_accuracy", 45, 2.0),
    ("cypress-field",        7,  "API timeouts affecting dispatch workflow",
     "Medium", "api_timeout", 40, 3.0),
    ("cypress-field",        14, "GPS accuracy in Zone 4 still problematic",
     "High", "gps_accuracy", 35, 2.5),

    # Quarrystone — admin access transfer
    ("quarrystone-logistics", 0, "Need to transfer admin access to new contact",
     "Medium", "admin_transfer", None, None),

    # Harborview — integration and billing issues
    ("harborview-fleet",     0,  "Integration with new ERP system not working as expected",
     "High", "erp_integration", 60, 2.0),
    ("harborview-fleet",     10, "ERP sync dropping line items intermittently",
     "High", "erp_integration", 50, 2.5),

    # Hawkstone crisis — ticket spike at day 205
    ("hawkstone-industries", 205, "Reporting discrepancy after platform update",
     "High", "reporting_bug", 30, 3.0),
    ("hawkstone-industries", 205, "Dashboard widgets showing stale data",
     "High", "reporting_bug", 25, 3.5),
    ("hawkstone-industries", 205, "Compliance report export failing",
     "Medium", "export_bug", 20, 3.5),

    # Copperfield cliff — case during disengagement
    ("copperfield-warehousing", 30, "Users unable to access mobile view after update",
     "Medium", "mobile_access", 20, 3.0),

    # Bison — routine case during slow bleed
    ("bison-transport",      50, "Route optimization suggesting inefficient paths",
     "Medium", "routing_quality", 35, 3.5),

    # Stonebridge — moderate priority
    ("stonebridge-fleet",    60, "Fleet dashboard not showing real-time positions",
     "Medium", "dashboard_display", 15, 4.0),

    # Cascade — adoption question
    ("cascade-field",        40, "How to set up maintenance alert thresholds",
     "Low", "config_question", 5, 4.5),

    # Mesa — steady account, rare case
    ("mesa-industrial",      150, "Quarterly compliance report format change request",
     "Low", "feature_request", 30, 4.0),

    # Prairie Wind — expansion signal case
    ("prairie-wind",         340, "New operations team needs onboarding access",
     "Low", "access_request", 10, 4.5),
]


# ---------------------------------------------------------------------------
# Opportunity stage progression
# ---------------------------------------------------------------------------

_OPP_STAGES = ("Prospecting", "Qualification", "Proposal", "Negotiation",
               "Closed Won", "Closed Lost")


def _opportunity_stages_at_day(
    slug: str,
    opp_type: str,
    base_stage: str,
    day: int,
) -> tuple[tuple[tuple[str, int], ...], str]:
    """Compute opportunity stage history and current stage at *day*.

    Returns ``(stage_history, current_stage)``.
    """
    # Find the index of the base stage
    try:
        base_idx = _OPP_STAGES.index(base_stage)
    except ValueError:
        base_idx = 1  # default to Qualification

    stages: list[tuple[str, int]] = [(base_stage, 0)]

    # Stage advancement schedule based on account narrative
    advance_days: dict[str, list[tuple[int, str]]] = {
        # Trailhead expansion — slow advancement
        "trailhead-logistics": [(90, "Proposal"), (200, "Negotiation")],
        # Meridian expansion — closes at day 180
        "meridian-fleet": [(60, "Proposal"), (120, "Negotiation"), (180, "Closed Won")],
        # Oakmont expansion — closes at day 120
        "oakmont-logistics": [(30, "Negotiation"), (120, "Closed Won")],
        # Harborview renewal — save play, closes conditionally
        "harborview-fleet": [(45, "Negotiation"), (280, "Closed Won")],
        # Windmill renewal — smooth
        "windmill-transport": [(30, "Negotiation"), (50, "Closed Won")],
        # Cedar Valley renewal — close with wobble
        "cedar-valley": [(20, "Proposal"), (30, "Negotiation"), (60, "Closed Won")],
    }

    schedule = advance_days.get(slug, [])
    current = base_stage
    for adv_day, adv_stage in schedule:
        if day >= adv_day:
            stages.append((adv_stage, adv_day))
            current = adv_stage

    return tuple(stages), current


# ---------------------------------------------------------------------------
# 1. Per-user activity simulation
# ---------------------------------------------------------------------------

def _simulate_user_logins(
    contact: CRMContact,
    slug: str,
    day: int,
    persona: _Persona,
    is_champion: bool,
    appeared_day: int,
) -> UserLoginHistory:
    """Generate the login history for a single user up to *day*."""
    role_type = _infer_role_type(contact.role, contact.title, is_champion)

    # Per-user activity level modifier based on role
    role_mult: dict[RoleType, float] = {
        "champion": 1.3,
        "executive_sponsor": 0.4,
        "technical_lead": 1.0,
        "end_user": 0.8,
        "admin": 0.9,
    }
    user_mult = role_mult.get(role_type, 0.8)

    # Champion quiet override
    champion_quiet_day = _CHAMPION_QUIET_DAYS.get(slug)
    is_quiet_champion = (
        is_champion
        and champion_quiet_day is not None
    )

    login_days: list[int] = []
    for d in range(max(0, appeared_day), day + 1):
        # Compute effective login probability
        weekday = _is_weekday(d)
        base_p = persona.login_weekday_p if weekday else persona.login_weekend_p
        p = base_p * user_mult * _login_multiplier(slug, d)

        # Champion goes quiet
        if is_quiet_champion and champion_quiet_day is not None and d >= champion_quiet_day:
            if is_champion:
                p *= 0.05  # near-zero but not exactly zero

        p = max(0.0, min(1.0, p))

        # Deterministic coin flip
        if _det_float(f"{contact.contact_id}:login:{d}") < p:
            login_days.append(d)

    return UserLoginHistory(
        contact_id=contact.contact_id,
        account_id=contact.account_id,
        login_days=tuple(login_days),
        role_type=role_type,
        is_champion=is_champion,
    )


# ---------------------------------------------------------------------------
# 2. Feature adoption simulation
# ---------------------------------------------------------------------------

def _simulate_features(
    slug: str,
    day: int,
    persona: _Persona,
    base_contacts: list[CRMContact],
) -> tuple[FeatureAdoptionState, ...]:
    """Compute feature adoption states for an account at *day*.

    Uses total tenure (days since contract start) rather than raw simulation
    day so that long-tenured accounts show mature adoption at day 0.
    Churned accounts freeze adoption at the churn day.
    """
    entitled_features = [cap for cap, _, _ in _ENTITLEMENTS.get(slug, [])]
    if not entitled_features:
        return ()

    account_id = _id[slug]
    n_users = len(base_contacts)

    # Cap the effective day at churn day for mid-simulation churns
    churn_day = _CHURN_DAYS.get(slug)
    effective_day = min(day, churn_day) if churn_day is not None else day
    tenure = _tenure_days(slug, effective_day)

    results: list[FeatureAdoptionState] = []

    for feature in _FEATURE_CATALOGUE:
        if feature not in entitled_features:
            continue

        status = _feature_status_at_day(tenure, feature, persona.feature_speed, slug)

        # After churn, zero out users regardless of feature status
        is_churned = churn_day is not None and day >= churn_day
        if is_churned or persona.feature_speed <= 0:
            users_active = 0
        elif status == "not_started":
            users_active = 0
        elif status == "exploring":
            users_active = max(1, int(n_users * 0.2))
        elif status == "adopted":
            users_active = max(1, int(n_users * 0.6))
        else:  # power_user
            users_active = max(1, int(n_users * 0.85))

        # Find first_used_day (in tenure terms, capped at pre-simulation)
        first_used_day: int | None = None
        if status != "not_started":
            timeline = _FEATURE_TIMELINES.get(feature)
            if timeline:
                jitter = _det_float(f"{slug}:feat:{feature}") * 15 - 7.5
                first_used_day = max(0, int(timeline[0] / max(0.01, persona.feature_speed) + jitter))

        ent_row = next(
            ((cap, qty, unit) for cap, qty, unit in _ENTITLEMENTS.get(slug, [])
             if cap == feature),
            None,
        )
        total_ent = ent_row[1] if ent_row else n_users

        results.append(FeatureAdoptionState(
            account_id=account_id,
            feature=feature,
            status=status,
            first_used_day=first_used_day,
            users_active=min(users_active, total_ent),
            total_entitled_users=total_ent,
        ))

    return tuple(results)


# ---------------------------------------------------------------------------
# 3. Case lifecycle simulation
# ---------------------------------------------------------------------------

def _simulate_cases(
    slug: str,
    day: int,
) -> tuple[CaseLifecycle, ...]:
    """Generate case records for an account up to *day*."""
    account_id = _id[slug]
    cases: list[CaseLifecycle] = []

    for s, open_day, subject, priority, topic, resolve_days, csat in _CASE_SCHEDULE:
        if s != slug:
            continue
        if open_day > day:
            continue

        case_id = det_id("case", account_id, f"deep-d{open_day}-{topic}")

        # Determine current status
        if resolve_days is not None:
            resolve_day = open_day + resolve_days
            if day >= resolve_day:
                status = "Resolved"
                actual_resolve = resolve_day
            elif day >= open_day + max(3, resolve_days // 3):
                # Escalated cases: high priority cases that take > 10 days
                if priority == "High" and resolve_days > 10:
                    status = "Escalated"
                else:
                    status = "In Progress"
                actual_resolve = None
            elif day >= open_day + 2:
                status = "In Progress"
                actual_resolve = None
            else:
                status = "Open"
                actual_resolve = None
        else:
            # Never resolved
            if day >= open_day + 15:
                status = "Escalated" if priority == "High" else "In Progress"
            elif day >= open_day + 2:
                status = "In Progress"
            else:
                status = "Open"
            actual_resolve = None

        cases.append(CaseLifecycle(
            case_id=case_id,
            account_id=account_id,
            open_day=open_day,
            subject=subject,
            priority=priority,
            status=status,
            resolution_day=actual_resolve,
            csat_score=csat if actual_resolve is not None and day >= actual_resolve else None,
            topic=topic,
        ))

    return tuple(cases)


# ---------------------------------------------------------------------------
# 4. Opportunity stage simulation
# ---------------------------------------------------------------------------

def _simulate_opportunities(
    slug: str,
    day: int,
) -> tuple[OpportunityTimeline, ...]:
    """Generate opportunity records with stage progression."""
    results: list[OpportunityTimeline] = []
    account_id = _id[slug]

    for s, opp_type, amount, base_stage, close_date in _OPPS:
        if s != slug:
            continue

        opp_id = det_id("opp", account_id, opp_type.lower())
        stages, current = _opportunity_stages_at_day(slug, opp_type, base_stage, day)

        results.append(OpportunityTimeline(
            opportunity_id=opp_id,
            account_id=account_id,
            opportunity_type=opp_type,
            amount_cents=amount,
            stages=stages,
            current_stage=current,
        ))

    return tuple(results)


# ---------------------------------------------------------------------------
# 5. Contact role/title evolution
# ---------------------------------------------------------------------------

def _simulate_contacts(
    slug: str,
    day: int,
    base_contacts: list[CRMContact],
    login_histories: tuple[UserLoginHistory, ...],
) -> tuple[ContactEvolution, ...]:
    """Compute contact snapshots with role evolution."""
    account_id = _id[slug]
    logins_by_id: dict[str, UserLoginHistory] = {
        lh.contact_id: lh for lh in login_histories
    }
    results: list[ContactEvolution] = []

    champion_id = _CHAMPION_CONTACT.get(slug)

    for i, contact in enumerate(base_contacts):
        is_champion = (contact.contact_id == champion_id)
        role_type = _infer_role_type(contact.role, contact.title, is_champion)

        # Engagement level derived from login history
        lh = logins_by_id.get(contact.contact_id)
        if lh:
            recent_logins = sum(1 for d in lh.login_days if d >= max(0, day - 30))
            if recent_logins >= 15:
                engagement = "high"
            elif recent_logins >= 5:
                engagement = "medium"
            elif recent_logins >= 1:
                engagement = "low"
            else:
                engagement = "inactive"
        else:
            engagement = "inactive"

        # Champion departure check
        champion_quiet = _CHAMPION_QUIET_DAYS.get(slug)
        departed_day: int | None = None
        title_changes: list[tuple[str, int]] = []

        if is_champion and champion_quiet is not None:
            # Champion goes quiet but doesn't formally leave
            # (Quarrystone's champion departed before day 0)
            if slug == "quarrystone-logistics":
                departed_day = 0

        results.append(ContactEvolution(
            contact_id=contact.contact_id,
            account_id=account_id,
            name=contact.name,
            current_title=contact.title or "",
            current_role_type=role_type,
            engagement_level=engagement,  # type: ignore[arg-type]
            appeared_day=0,
            departed_day=departed_day if day >= (departed_day or day + 1) else None,
            title_changes=tuple(title_changes),
        ))

    # Add new contacts that appear during the simulation
    new_contacts = _NEW_CONTACTS.get(slug, [])
    for appear_day, name, role, title, email in new_contacts:
        if day < appear_day:
            continue
        contact_id = det_id("contact", account_id, email)
        lh = logins_by_id.get(contact_id)

        if lh:
            recent_logins = sum(1 for d in lh.login_days if d >= max(0, day - 30))
            engagement: EngagementLevel = (
                "high" if recent_logins >= 15
                else "medium" if recent_logins >= 5
                else "low" if recent_logins >= 1
                else "inactive"
            )
        else:
            engagement = "low"  # just appeared

        # New contacts are often successors or sponsors
        if "vp" in title.lower() or "director" in title.lower():
            rt: RoleType = "executive_sponsor"
        else:
            rt = "end_user"

        results.append(ContactEvolution(
            contact_id=contact_id,
            account_id=account_id,
            name=name,
            current_title=title,
            current_role_type=rt,
            engagement_level=engagement,
            appeared_day=appear_day,
            departed_day=None,
            title_changes=(),
        ))

    return tuple(results)


# ---------------------------------------------------------------------------
# 6. CSM ↔ customer activity records
# ---------------------------------------------------------------------------

def _simulate_activities(
    slug: str,
    day: int,
    persona: _Persona,
    contacts: tuple[ContactEvolution, ...],
) -> tuple[CSMActivityRecord, ...]:
    """Generate CSM activity records (calls, emails, meetings)."""
    account_id = _id[slug]
    if persona.csm_activity_rate <= 0:
        return ()

    # Stop CSM activity after churn
    churn_day = _CHURN_DAYS.get(slug)
    effective_end = min(day, churn_day - 1) if churn_day is not None else day

    activities: list[CSMActivityRecord] = []
    channels = ("call", "email", "email", "meeting")  # weighted toward email

    for d in range(0, effective_end + 1):
        # Probability of any CSM activity on this day
        daily_p = persona.csm_activity_rate / 30.0
        # CSM activity increases when account is at risk
        mult = _login_multiplier(slug, d)
        if mult < 0.7 and mult > 0.0:
            # Account struggling → CSM increases outreach
            daily_p *= 1.8
        elif mult > 1.1:
            # Account healthy → CSM reduces frequency
            daily_p *= 0.7

        daily_p = min(1.0, daily_p)

        if _det_float(f"{slug}:activity:{d}") >= daily_p:
            continue

        # Pick channel deterministically
        ch_idx = _det_int(f"{slug}:channel:{d}", 0, len(channels) - 1)
        channel = channels[ch_idx]

        # Pick a contact (prefer active contacts)
        active_contacts = [
            c for c in contacts
            if c.engagement_level != "inactive"
            and c.appeared_day <= d
            and (c.departed_day is None or d < c.departed_day)
        ]
        if not active_contacts:
            active_contacts = [c for c in contacts if c.appeared_day <= d]
        if not active_contacts:
            continue

        contact_idx = _det_int(f"{slug}:contact_pick:{d}", 0, len(active_contacts) - 1)
        picked = active_contacts[contact_idx]

        # Meeting attendees
        attendees: tuple[str, ...]
        if channel == "meeting" and len(active_contacts) > 1:
            n_attendees = min(len(active_contacts), _det_int(f"{slug}:attendees:{d}", 2, 4))
            attendee_ids = [picked.contact_id]
            for ac in active_contacts:
                if ac.contact_id != picked.contact_id and len(attendee_ids) < n_attendees:
                    attendee_ids.append(ac.contact_id)
            attendees = tuple(attendee_ids)
        else:
            attendees = (picked.contact_id,)

        direction = "outbound" if _det_float(f"{slug}:dir:{d}") < 0.65 else "inbound"

        activities.append(CSMActivityRecord(
            activity_id=det_id("deep-activity", account_id, str(d), channel),
            account_id=account_id,
            contact_id=picked.contact_id,
            channel=channel,
            direction=direction,
            day=d,
            attendees=attendees,
        ))

    return tuple(activities)


# ---------------------------------------------------------------------------
# Metric computation — derived FROM granular data
# ---------------------------------------------------------------------------

def _compute_dau(login_histories: tuple[UserLoginHistory, ...], day: int) -> int:
    """Count distinct users who logged in on exactly *day*."""
    return sum(1 for lh in login_histories if day in lh.login_days)


def _compute_wau(login_histories: tuple[UserLoginHistory, ...], day: int) -> int:
    """Count distinct users who logged in within [day-6, day]."""
    window = set(range(max(0, day - 6), day + 1))
    return sum(1 for lh in login_histories if window & set(lh.login_days))


def _compute_mau(login_histories: tuple[UserLoginHistory, ...], day: int) -> int:
    """Count distinct users who logged in within [day-29, day]."""
    window = set(range(max(0, day - 29), day + 1))
    return sum(1 for lh in login_histories if window & set(lh.login_days))


def _compute_csat(cases: tuple[CaseLifecycle, ...]) -> float | None:
    """Average CSAT from resolved cases with scores."""
    scores = [c.csat_score for c in cases if c.csat_score is not None]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 2)


def _compute_feature_depth(
    features: tuple[FeatureAdoptionState, ...],
) -> float:
    """Feature depth score: fraction of entitled features actively used.

    A feature counts as "adopted" only if it has reached adopted/power_user
    status AND has at least one active user.  Churned accounts with zero
    users will show depth = 0.0.
    """
    if not features:
        return 0.0
    adopted_count = sum(
        1 for f in features
        if f.status in ("adopted", "power_user") and f.users_active > 0
    )
    return round(adopted_count / len(features), 2)


def _compute_active_users(
    login_histories: tuple[UserLoginHistory, ...],
    day: int,
) -> int:
    """Count users active in the last 30 days."""
    return _compute_mau(login_histories, day)


def _compute_champion_active(
    login_histories: tuple[UserLoginHistory, ...],
    day: int,
) -> bool:
    """True if the champion logged in within the last 14 days."""
    window = set(range(max(0, day - 13), day + 1))
    for lh in login_histories:
        if lh.is_champion and (window & set(lh.login_days)):
            return True
    return False


# ---------------------------------------------------------------------------
# Main simulation entry point
# ---------------------------------------------------------------------------

def simulate_data(
    base_book: FixtureCustomerData,
    day: int,
) -> SimulatedDataBundle:
    """Simulate deep data for all 35 accounts at *day* offset from SEED_DATE.

    All simulation is deterministic: the same *day* always produces the same
    data.  The returned ``SimulatedDataBundle`` contains per-account granular
    data and computed aggregate metrics.

    Parameters
    ----------
    base_book:
        The base ``FixtureCustomerData`` from ``build_synthetic_book()``.
    day:
        Days past SEED_DATE.  ``0`` returns the baseline; ``365`` returns the
        full-year simulation.

    Returns
    -------
    SimulatedDataBundle
        Contains an ``AccountDataBundle`` for every account keyed by
        ``account_id``.
    """
    as_of = _day_iso(day)
    account_bundles: dict[str, AccountDataBundle] = {}

    # Build a contact lookup by account slug
    contacts_by_slug: dict[str, list[CRMContact]] = {}
    for contact in base_book.contacts:
        for slug_key, aid in _id.items():
            if contact.account_id == aid:
                contacts_by_slug.setdefault(slug_key, []).append(contact)
                break

    for slug, name, industry, csm in _ACCT_DATA:
        account_id = _id[slug]
        persona_name = _ACCOUNT_PERSONA.get(slug, "stable")
        persona = _PERSONAS[persona_name]
        base_contacts = contacts_by_slug.get(slug, [])

        # --- 1. Per-user login histories ---
        login_histories_list: list[UserLoginHistory] = []
        champion_id = _CHAMPION_CONTACT.get(slug)

        for i, contact in enumerate(base_contacts):
            is_champ = (contact.contact_id == champion_id)
            lh = _simulate_user_logins(contact, slug, day, persona, is_champ, 0)
            login_histories_list.append(lh)

        # New contacts that appear mid-simulation
        for appear_day, nc_name, nc_role, nc_title, nc_email in _NEW_CONTACTS.get(slug, []):
            if day < appear_day:
                continue
            nc_id = det_id("contact", account_id, nc_email)
            nc_contact = CRMContact(
                contact_id=nc_id,
                account_id=account_id,
                email=nc_email,
                name=nc_name,
                role=nc_role,
                title=nc_title,
                consent_to_contact=True,
            )
            lh = _simulate_user_logins(
                nc_contact, slug, day, persona, False, appear_day,
            )
            login_histories_list.append(lh)

        login_histories = tuple(login_histories_list)

        # --- 2. Feature adoption ---
        features = _simulate_features(slug, day, persona, base_contacts)

        # --- 3. Cases ---
        cases = _simulate_cases(slug, day)

        # --- 4. Opportunities ---
        opportunities = _simulate_opportunities(slug, day)

        # --- 5. Contact evolution ---
        contacts_evo = _simulate_contacts(slug, day, base_contacts, login_histories)

        # --- 6. CSM activities ---
        activities = _simulate_activities(slug, day, persona, contacts_evo)

        # --- Computed aggregates ---
        dau = _compute_dau(login_histories, day)
        wau = _compute_wau(login_histories, day)
        mau = _compute_mau(login_histories, day)
        overall_csat = _compute_csat(cases)
        feature_depth = _compute_feature_depth(features)
        active_users = _compute_active_users(login_histories, day)
        champion_active = _compute_champion_active(login_histories, day)

        account_bundles[account_id] = AccountDataBundle(
            account_id=account_id,
            account_slug=slug,
            login_histories=login_histories,
            feature_adoptions=features,
            cases=cases,
            opportunities=opportunities,
            contacts=contacts_evo,
            activities=activities,
            dau=dau,
            wau=wau,
            mau=mau,
            overall_csat=overall_csat,
            feature_depth_score=feature_depth,
            active_user_count=active_users,
            champion_active=champion_active,
        )

    return SimulatedDataBundle(
        day=day,
        as_of_date=as_of,
        accounts=account_bundles,
    )
