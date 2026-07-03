"""Synthetic 35-account book for a fictional fleet-management / industrial IoT SaaS.

Every company name, person name, product code, and datum is entirely fictional.
The book exercises a representative spread of lifecycle stages, health bands,
and CS scenarios including onboarding stalls, champion departure, single-
threaded risk, expansion signals, renewal pressure, and churn.
"""

from __future__ import annotations

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
from ultra_csm.data_plane.fixtures import FixtureCustomerData, account_id_for, det_id

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SEED_CLOCK = "2026-06-21T00:00:00Z"
SEED_DATE = "2026-06-21"


def _sig(acct: str, metric: str, day: str = SEED_DATE) -> str:
    return det_id("signal", acct, metric, day)


# ---------------------------------------------------------------------------
# Account master list  (slug, name, industry, csm_id)
# ---------------------------------------------------------------------------
_ACCT_DATA: list[tuple[str, str, str, str]] = [
    # -- ONBOARDING (6) --
    ("ironhorse-freight",      "Ironhorse Freight Co",       "fleet_management",  "csm-101"),
    ("pinehill-transport",     "Pinehill Transport",         "logistics",         "csm-102"),
    ("ridgeline-warehousing",  "Ridgeline Warehousing",      "warehousing",       "csm-104"),
    ("northstar-couriers",     "Northstar Couriers",         "logistics",         "csm-103"),
    ("clearwater-field-ops",   "Clearwater Field Ops",       "field_services",    "csm-104"),
    ("summit-industrial",      "Summit Industrial Supply",   "manufacturing",     "csm-103"),
    # -- STEADY STATE (15) --
    ("trailhead-logistics",    "Trailhead Logistics",        "logistics",         "csm-101"),
    ("crestline-distribution", "Crestline Distribution",     "logistics",         "csm-102"),
    ("redwood-fleet",          "Redwood Fleet Services",     "fleet_management",  "csm-102"),
    ("bison-transport",        "Bison Transport Group",      "transportation",    "csm-101"),
    ("copperfield-warehousing","Copperfield Warehousing",    "warehousing",       "csm-103"),
    ("cascade-field",          "Cascade Field Services",     "field_services",    "csm-104"),
    ("timberline-logistics",   "Timberline Logistics",       "logistics",         "csm-102"),
    ("falcon-delivery",        "Falcon Delivery Systems",    "logistics",         "csm-104"),
    ("mesa-industrial",        "Mesa Industrial Corp",       "manufacturing",     "csm-103"),
    ("stonebridge-fleet",      "Stonebridge Fleet",          "fleet_management",  "csm-104"),
    ("prairie-wind",           "Prairie Wind Transport",     "transportation",    "csm-104"),
    ("aspenridge-supply",      "Aspenridge Supply Chain",    "logistics",         "csm-102"),
    ("granite-peak",           "Granite Peak Logistics",     "logistics",         "csm-104"),
    ("ironridge-fleet",        "Iron Ridge Fleet Ops",       "fleet_management",  "csm-103"),
    ("hawkstone-industries",   "Hawkstone Industries",       "manufacturing",     "csm-103"),
    # -- EXPANDING (4, lifecycle=steady_state) --
    ("meridian-fleet",         "Meridian Fleet Group",       "fleet_management",  "csm-101"),
    ("oakmont-logistics",      "Oakmont Logistics",          "logistics",         "csm-102"),
    ("blueridge-transport",    "Blue Ridge Transport",       "transportation",    "csm-102"),
    ("westfield-industrial",   "Westfield Industrial",       "manufacturing",     "csm-103"),
    # -- AT RISK (5) --
    ("pinnacle-supply",        "Pinnacle Supply Chain",      "logistics",         "csm-101"),
    ("sagebrush-transport",    "Sagebrush Transport",        "transportation",    "csm-103"),
    ("driftwood-warehousing",  "Driftwood Warehousing",      "warehousing",       "csm-104"),
    ("cypress-field",          "Cypress Field Ops",          "field_services",    "csm-103"),
    ("quarrystone-logistics",  "Quarry Stone Logistics",     "logistics",         "csm-104"),
    # -- RENEWAL (3) --
    ("harborview-fleet",       "Harborview Fleet",           "fleet_management",  "csm-102"),
    ("windmill-transport",     "Windmill Transport",         "transportation",    "csm-103"),
    ("cedar-valley",           "Cedar Valley Distribution",  "logistics",         "csm-104"),
    # -- CHURNED (2) --
    ("riverstone-logistics",   "Riverstone Logistics",       "logistics",         "csm-102"),
    ("dustbowl-freight",       "Dustbowl Freight",           "transportation",    "csm-104"),
]

# Pre-compute account IDs
_id = {slug: account_id_for(slug) for slug, *_ in _ACCT_DATA}

# ---------------------------------------------------------------------------
# CSCompany parameters keyed by slug
# (arr_cents, lifecycle_stage, status, original_contract_date, renewal_date, score)
# ---------------------------------------------------------------------------
_COMPANY: dict[str, tuple[int, str, str, str, str, float]] = {
    # ONBOARDING
    "ironhorse-freight":      (14_800_000, "onboarding",    "Active",  "2026-06-01", "2027-06-01", 72.0),
    "pinehill-transport":     ( 8_500_000, "onboarding",    "Active",  "2026-05-17", "2027-05-17", 55.0),
    "ridgeline-warehousing":  ( 2_800_000, "onboarding",    "Active",  "2026-06-14", "2027-06-14", 68.0),
    "northstar-couriers":     ( 3_800_000, "onboarding",    "Active",  "2026-05-24", "2027-05-24", 75.0),
    "clearwater-field-ops":   ( 3_200_000, "onboarding",    "Active",  "2026-06-01", "2027-06-01", 60.0),
    "summit-industrial":      ( 3_800_000, "onboarding",    "Active",  "2026-06-07", "2027-06-07", 78.0),
    # STEADY STATE
    "trailhead-logistics":    (31_000_000, "steady_state",  "Active",  "2025-01-01", "2027-01-01", 94.0),
    "crestline-distribution": (12_000_000, "steady_state",  "Active",  "2025-06-01", "2027-06-01", 82.0),
    "redwood-fleet":          ( 4_000_000, "steady_state",  "Active",  "2025-04-01", "2027-04-01", 79.0),
    "bison-transport":        (14_500_000, "steady_state",  "Active",  "2024-06-01", "2027-06-01", 74.0),
    "copperfield-warehousing":( 3_500_000, "steady_state",  "Active",  "2025-08-01", "2026-08-01", 80.0),
    "cascade-field":          ( 2_800_000, "adopting",      "Active",  "2025-10-01", "2026-10-01", 70.0),
    "timberline-logistics":   (11_000_000, "steady_state",  "Active",  "2025-03-01", "2027-03-01", 85.0),
    "falcon-delivery":        ( 2_200_000, "adopting",      "Active",  "2025-12-01", "2026-12-01", 65.0),
    "mesa-industrial":        ( 3_800_000, "steady_state",  "Active",  "2025-07-01", "2026-07-01", 81.0),
    "stonebridge-fleet":      ( 3_500_000, "steady_state",  "Active",  "2025-11-01", "2026-11-01", 72.0),
    "prairie-wind":           ( 2_900_000, "steady_state",  "Active",  "2025-09-01", "2026-09-01", 68.0),
    "aspenridge-supply":      ( 4_000_000, "steady_state",  "Active",  "2025-02-01", "2027-02-01", 83.0),
    "granite-peak":           ( 1_800_000, "adopting",      "Active",  "2026-01-01", "2027-01-01", 76.0),
    "ironridge-fleet":        ( 3_600_000, "steady_state",  "Active",  "2025-05-01", "2027-05-01", 80.0),
    "hawkstone-industries":   (13_000_000, "steady_state",  "Active",  "2024-10-01", "2026-10-01", 87.0),
    # EXPANDING (lifecycle=steady_state)
    "meridian-fleet":         (28_000_000, "steady_state",  "Active",  "2025-01-01", "2027-01-01", 91.0),
    "oakmont-logistics":      (11_500_000, "steady_state",  "Active",  "2025-04-01", "2027-04-01", 88.0),
    "blueridge-transport":    ( 3_800_000, "steady_state",  "Active",  "2025-06-01", "2027-06-01", 85.0),
    "westfield-industrial":   ( 3_500_000, "steady_state",  "Active",  "2025-10-01", "2026-10-01", 82.0),
    # AT RISK
    "pinnacle-supply":        (35_000_000, "steady_state",  "Active",  "2024-06-01", "2027-06-01", 78.0),
    "sagebrush-transport":    ( 7_500_000, "at_risk",       "Active",  "2025-08-01", "2026-08-01", 45.0),
    "driftwood-warehousing":  ( 3_000_000, "at_risk",       "Active",  "2025-12-01", "2026-12-01", 38.0),
    "cypress-field":          ( 8_800_000, "at_risk",       "Active",  "2025-06-01", "2026-06-01", 52.0),
    "quarrystone-logistics":  ( 2_000_000, "at_risk",       "Active",  "2026-02-01", "2027-02-01", 42.0),
    # RENEWAL
    "harborview-fleet":       (14_000_000, "renewal",       "Active",  "2025-08-01", "2026-08-05", 56.0),
    "windmill-transport":     ( 3_900_000, "renewal",       "Active",  "2025-08-01", "2026-08-20", 80.0),
    "cedar-valley":           ( 3_500_000, "renewal",       "Active",  "2025-07-01", "2026-07-21", 62.0),
    # CHURNED
    "riverstone-logistics":   ( 8_500_000, "at_risk",       "Churned", "2025-05-01", "2026-05-01", 22.0),
    "dustbowl-freight":       ( 2_400_000, "at_risk",       "Churned", "2025-04-01", "2026-04-01", 15.0),
}

# ---------------------------------------------------------------------------
# Health scores  (slug -> score, band, drivers)
# ---------------------------------------------------------------------------
_HEALTH: dict[str, tuple[float, str, tuple[str, ...]]] = {
    "ironhorse-freight":      (72.0, "yellow", ("activation_in_progress",)),
    "pinehill-transport":     (55.0, "yellow", ("activation_stalled",)),
    "ridgeline-warehousing":  (68.0, "yellow", ("early_onboarding",)),
    "northstar-couriers":     (75.0, "yellow", ("onboarding_on_track",)),
    "clearwater-field-ops":   (60.0, "yellow", ("slow_activation",)),
    "summit-industrial":      (78.0, "green",  ("fast_activation",)),
    "trailhead-logistics":    (94.0, "green",  ("exemplary_adoption", "strong_champion")),
    "crestline-distribution": (82.0, "green",  ("stable_usage",)),
    "redwood-fleet":          (79.0, "green",  ("stable_usage",)),
    "bison-transport":        (74.0, "yellow", ("slight_usage_decline",)),
    "copperfield-warehousing":(80.0, "green",  ("stable_usage",)),
    "cascade-field":          (70.0, "yellow", ("moderate_adoption",)),
    "timberline-logistics":   (85.0, "green",  ("healthy_adoption",)),
    "falcon-delivery":        (65.0, "yellow", ("moderate_adoption",)),
    "mesa-industrial":        (81.0, "green",  ("stable_usage",)),
    "stonebridge-fleet":      (72.0, "yellow", ("moderate_adoption",)),
    "prairie-wind":           (68.0, "yellow", ("moderate_adoption",)),
    "aspenridge-supply":      (83.0, "green",  ("healthy_adoption",)),
    "granite-peak":           (76.0, "green",  ("on_track",)),
    "ironridge-fleet":        (80.0, "green",  ("stable_usage",)),
    "hawkstone-industries":   (87.0, "green",  ("exemplary_adoption",)),
    "meridian-fleet":         (91.0, "green",  ("high_usage", "expansion_signal")),
    "oakmont-logistics":      (88.0, "green",  ("high_usage",)),
    "blueridge-transport":    (85.0, "green",  ("growing_usage",)),
    "westfield-industrial":   (82.0, "green",  ("high_usage",)),
    "pinnacle-supply":        (78.0, "green",  ("stable_usage",)),
    "sagebrush-transport":    (45.0, "red",    ("usage_decline", "engagement_drop")),
    "driftwood-warehousing":  (38.0, "red",    ("low_engagement", "no_champion_activity")),
    "cypress-field":          (52.0, "yellow", ("support_escalation", "declining_satisfaction")),
    "quarrystone-logistics":  (42.0, "red",    ("champion_departed", "no_successor")),
    "harborview-fleet":       (56.0, "yellow", ("declining_csat", "renewal_approaching")),
    "windmill-transport":     (80.0, "green",  ("stable_usage", "renewal_on_track")),
    "cedar-valley":           (62.0, "yellow", ("moderate_adoption", "renewal_approaching")),
    "riverstone-logistics":   (22.0, "red",    ("churned", "competitor_loss")),
    "dustbowl-freight":       (15.0, "red",    ("churned", "budget_cut")),
}

# ---------------------------------------------------------------------------
# Adoption summaries
# (slug -> active_users, licensed_users, active_assets, entitled_assets,
#          adoption_rate, underused_capabilities)
# ---------------------------------------------------------------------------
_ADOPTION: dict[str, tuple[int, int, int, int, float, tuple[str, ...]]] = {
    "ironhorse-freight":      (42, 65,  48, 120, 0.40, ("driver_coaching", "maintenance_alerts")),
    "pinehill-transport":     ( 8, 25,  12,  50, 0.24, ("route_optimization",)),
    "ridgeline-warehousing":  ( 3, 10,   5,  25, 0.20, ()),
    "northstar-couriers":     ( 9, 15,  14,  22, 0.64, ()),
    "clearwater-field-ops":   ( 4, 12,   6,  20, 0.30, ("maintenance_alerts",)),
    "summit-industrial":      (12, 18,  10,  25, 0.40, ()),
    "trailhead-logistics":    (85, 90, 175, 200, 0.88, ()),
    "crestline-distribution": (35, 40,  55,  60, 0.92, ()),
    "redwood-fleet":          (12, 15,  18,  22, 0.82, ("fuel_analytics",)),
    "bison-transport":        (55, 70, 130, 180, 0.72, ("driver_coaching",)),
    "copperfield-warehousing":(10, 12,  18,  20, 0.90, ()),
    "cascade-field":          ( 8, 15,  14,  20, 0.70, ("maintenance_alerts",)),
    "timberline-logistics":   (40, 45,  60,  70, 0.86, ()),
    "falcon-delivery":        ( 6, 10,  10,  15, 0.67, ()),
    "mesa-industrial":        (12, 16,  20,  25, 0.80, ()),
    "stonebridge-fleet":      ( 7, 12,  12,  18, 0.67, ("route_optimization",)),
    "prairie-wind":           ( 5,  8,  10,  15, 0.67, ()),
    "aspenridge-supply":      (10, 12,  16,  18, 0.89, ()),
    "granite-peak":           ( 5,  6,   8,  10, 0.80, ()),
    "ironridge-fleet":        ( 9, 12,  14,  16, 0.88, ()),
    "hawkstone-industries":   (42, 48,  70,  75, 0.93, ()),
    "meridian-fleet":         (52, 55,  54,  60, 0.90, ()),
    "oakmont-logistics":      (38, 40,  48,  50, 0.96, ()),
    "blueridge-transport":    (10, 12,  19,  20, 0.95, ()),
    "westfield-industrial":   (14, 15,  22,  20, 1.10, ()),
    "pinnacle-supply":        (58, 70, 200, 250, 0.80, ("dispatch_automation",)),
    "sagebrush-transport":    ( 8, 22,  12,  35, 0.34, ("route_optimization", "driver_coaching")),
    "driftwood-warehousing":  ( 2, 10,   4,  15, 0.27, ("maintenance_alerts",)),
    "cypress-field":          (15, 28,  20,  40, 0.50, ("maintenance_alerts",)),
    "quarrystone-logistics":  ( 3,  8,   5,  12, 0.42, ()),
    "harborview-fleet":       (25, 40,  35,  55, 0.64, ("advanced_reporting", "dispatch_automation")),
    "windmill-transport":     ( 8, 10,  13,  15, 0.87, ()),
    "cedar-valley":           ( 6, 10,   9,  15, 0.60, ("route_optimization",)),
    "riverstone-logistics":   ( 0,  0,   0,   0, 0.00, ()),
    "dustbowl-freight":       ( 0,  0,   0,   0, 0.00, ()),
}

# ---------------------------------------------------------------------------
# Contacts  (slug -> list of (name, role, title_suffix, email, consent))
# ---------------------------------------------------------------------------
_CONTACTS: dict[str, list[tuple[str, str, str, str, bool]]] = {
    "ironhorse-freight": [
        ("Marcus Webb",      "fleet_operations",      "Dir Fleet Ops",        "marcus.webb@ironhorse-freight.example",     True),
        ("Lisa Chang",       "information_technology", "IT Manager",           "lisa.chang@ironhorse-freight.example",      True),
        ("Robert Haines",    "finance",               "CFO",                  "robert.haines@ironhorse-freight.example",   False),
    ],
    "pinehill-transport": [
        ("Dennis Gruber",    "fleet_operations",      "Fleet Manager",        "dennis.gruber@pinehill-transport.example",  True),
        ("Amy Zhao",         "information_technology", "IT Lead",              "amy.zhao@pinehill-transport.example",       True),
    ],
    "ridgeline-warehousing": [
        ("Jared Nolan",      "operations",            "Warehouse Ops Manager","jared.nolan@ridgeline-wh.example",          True),
    ],
    "northstar-couriers": [
        ("Sandra Faulkner",  "logistics",             "VP Logistics",         "sandra.faulkner@northstar-couriers.example",True),
        ("Tom Briggs",       "operations",            "Dispatch Lead",        "tom.briggs@northstar-couriers.example",     True),
    ],
    "clearwater-field-ops": [
        ("Kelly Vance",      "operations",            "Field Ops Manager",    "kelly.vance@clearwater-fo.example",         True),
    ],
    "summit-industrial": [
        ("Diana Kowalski",   "operations",            "Plant Manager",        "diana.kowalski@summit-industrial.example",  True),
        ("Neil Drummond",    "logistics",             "Logistics Coordinator","neil.drummond@summit-industrial.example",   True),
    ],
    "trailhead-logistics": [
        ("Vanessa Torres",   "operations",            "VP Operations",        "vanessa.torres@trailhead-logistics.example",True),
        ("Paul Gerhardt",    "technology",            "CTO",                  "paul.gerhardt@trailhead-logistics.example", True),
        ("Mike Lindgren",    "fleet_operations",      "Fleet Director",       "mike.lindgren@trailhead-logistics.example", True),
        ("Samira Ali",       "safety",                "Safety Manager",       "samira.ali@trailhead-logistics.example",    True),
    ],
    "crestline-distribution": [
        ("Glen Park",        "logistics",             "Logistics Director",   "glen.park@crestline-dist.example",          True),
        ("Carol Mendez",     "administration",        "Admin",                "carol.mendez@crestline-dist.example",       True),
    ],
    "redwood-fleet": [
        ("Brenda Watts",     "fleet_operations",      "Fleet Manager",        "brenda.watts@redwood-fleet.example",        True),
        ("Tony Salazar",     "maintenance",           "Maintenance Supervisor","tony.salazar@redwood-fleet.example",       True),
    ],
    "bison-transport": [
        ("William Chen",     "transportation",        "VP Transportation",    "william.chen@bison-transport.example",      True),
        ("Laura Kimball",    "fleet_operations",      "Fleet Director",       "laura.kimball@bison-transport.example",     True),
        ("Roger Neville",    "information_technology", "IT Director",          "roger.neville@bison-transport.example",     True),
    ],
    "copperfield-warehousing": [
        ("Patrick Duffy",    "operations",            "Operations Manager",   "patrick.duffy@copperfield-wh.example",      True),
        ("Maria Santos",     "operations",            "Shift Lead",           "maria.santos@copperfield-wh.example",       True),
    ],
    "cascade-field": [
        ("Nancy Ortiz",      "operations",            "Service Manager",      "nancy.ortiz@cascade-field.example",         True),
    ],
    "timberline-logistics": [
        ("Ray Blackwell",    "executive",             "COO",                  "ray.blackwell@timberline-logistics.example", True),
        ("Emma Fischer",     "fleet_operations",      "Fleet Manager",        "emma.fischer@timberline-logistics.example",  True),
    ],
    "falcon-delivery": [
        ("Derek Holt",       "operations",            "Owner/Manager",        "derek.holt@falcon-delivery.example",        True),
    ],
    "mesa-industrial": [
        ("Susan Whitfield",  "operations",            "Plant Ops Director",   "susan.whitfield@mesa-industrial.example",   True),
        ("Alan Rossi",       "safety",                "EHS Manager",          "alan.rossi@mesa-industrial.example",        True),
    ],
    "stonebridge-fleet": [
        ("Jake Morrison",    "fleet_operations",      "Fleet Supervisor",     "jake.morrison@stonebridge-fleet.example",   True),
    ],
    "prairie-wind": [
        ("Hank Drummond",    "executive",             "Owner",                "hank.drummond@prairie-wind.example",        True),
        ("Beth Simmons",     "administration",        "Office Manager",       "beth.simmons@prairie-wind.example",         True),
    ],
    "aspenridge-supply": [
        ("Christine Yoder",  "logistics",             "VP Supply Chain",      "christine.yoder@aspenridge-sc.example",     True),
        ("Frank Delgado",    "transportation",        "Transport Manager",    "frank.delgado@aspenridge-sc.example",       True),
    ],
    "granite-peak": [
        ("Olivia Grant",     "operations",            "Operations Lead",      "olivia.grant@granite-peak.example",         True),
    ],
    "ironridge-fleet": [
        ("Walter Benton",    "fleet_operations",      "Fleet Director",       "walter.benton@ironridge-fleet.example",     True),
        ("Shelly Ramos",     "safety",                "Safety Coordinator",   "shelly.ramos@ironridge-fleet.example",      True),
    ],
    "hawkstone-industries": [
        ("Phil Garrett",     "manufacturing",         "VP Manufacturing",     "phil.garrett@hawkstone-ind.example",        True),
        ("Ingrid Solberg",   "quality",               "Quality Manager",      "ingrid.solberg@hawkstone-ind.example",      True),
        ("Carlos Ruiz",      "maintenance",           "Maintenance Director", "carlos.ruiz@hawkstone-ind.example",         True),
    ],
    "meridian-fleet": [
        ("Alicia Fernandez", "fleet_operations",      "VP Fleet Ops",         "alicia.fernandez@meridian-fleet.example",   True),
        ("James Tuttle",     "fleet_operations",      "Regional Fleet Manager","james.tuttle@meridian-fleet.example",      True),
        ("Karen Bright",     "facilities",            "Facilities Director",  "karen.bright@meridian-fleet.example",       True),
        ("Rob McAllister",   "finance",               "CFO",                  "rob.mcallister@meridian-fleet.example",     True),
    ],
    "oakmont-logistics": [
        ("Dave Hollister",   "logistics",             "Logistics Manager",    "dave.hollister@oakmont-logistics.example",  True),
        ("Nina Crawford",    "fleet_operations",      "Fleet Coordinator",    "nina.crawford@oakmont-logistics.example",   True),
    ],
    "blueridge-transport": [
        ("Martin Rhodes",    "transportation",        "Transportation Director","martin.rhodes@blueridge-transport.example",True),
        ("April Lawson",     "analytics",             "Analyst",              "april.lawson@blueridge-transport.example",  True),
    ],
    "westfield-industrial": [
        ("Trevor Nash",      "operations",            "Plant Manager",        "trevor.nash@westfield-industrial.example",  True),
    ],
    "pinnacle-supply": [
        ("Derek Vaughn",     "supply_chain",          "VP Supply Chain",      "derek.vaughn@pinnacle-supply.example",      True),
        ("Natasha Penn",     "administration",        "Admin",                "natasha.penn@pinnacle-supply.example",      True),
        ("Christine Kim",    "procurement",           "Procurement Manager",  "christine.kim@pinnacle-supply.example",     False),
    ],
    "sagebrush-transport": [
        ("Brett Sawyer",     "fleet_operations",      "Fleet Manager",        "brett.sawyer@sagebrush-transport.example",  True),
        ("Janet Lowe",       "administration",        "Admin",                "janet.lowe@sagebrush-transport.example",    True),
    ],
    "driftwood-warehousing": [
        ("Randy Hollis",     "operations",            "Warehouse Supervisor", "randy.hollis@driftwood-wh.example",         True),
    ],
    "cypress-field": [
        ("Irene Chu",        "field_services",        "Field Services Director","irene.chu@cypress-field.example",         True),
        ("Ben Talbot",       "operations",            "Service Dispatch Lead","ben.talbot@cypress-field.example",          True),
    ],
    "quarrystone-logistics": [
        ("Tim Kowalczyk",    "fleet_operations",      "Fleet Manager",        "tim.kowalczyk@quarrystone.example",         False),
    ],
    "harborview-fleet": [
        ("Gregory Foster",   "operations",            "VP Operations",        "gregory.foster@harborview-fleet.example",   True),
        ("Michelle Park",    "fleet_operations",      "Fleet Manager",        "michelle.park@harborview-fleet.example",    True),
        ("David Cross",      "finance",               "CFO",                  "david.cross@harborview-fleet.example",      True),
    ],
    "windmill-transport": [
        ("Catherine Wells",  "logistics",             "Logistics Director",   "catherine.wells@windmill-transport.example",True),
        ("Ed Parsons",       "fleet_operations",      "Fleet Coordinator",    "ed.parsons@windmill-transport.example",     True),
    ],
    "cedar-valley": [
        ("Diane Mercer",     "logistics",             "Distribution Manager", "diane.mercer@cedar-valley-dist.example",    True),
    ],
    "riverstone-logistics": [
        ("Angela Price",     "logistics",             "VP Logistics",         "angela.price@riverstone-logistics.example", False),
    ],
    "dustbowl-freight": [
        ("Lou Garnett",      "executive",             "Owner/Operator",       "lou.garnett@dustbowl-freight.example",      False),
    ],
}

# ---------------------------------------------------------------------------
# Entitlements  (slug -> list of (capability, quantity, unit))
# ---------------------------------------------------------------------------
_ENTITLEMENTS: dict[str, list[tuple[str, int, str]]] = {
    "ironhorse-freight":      [("core_telematics", 120, "assets"), ("route_optimization", 120, "assets"), ("driver_coaching", 120, "assets"), ("maintenance_alerts", 120, "assets")],
    "pinehill-transport":     [("core_telematics", 50, "assets"), ("route_optimization", 50, "assets")],
    "ridgeline-warehousing":  [("core_telematics", 25, "assets")],
    "northstar-couriers":     [("core_telematics", 22, "assets"), ("route_optimization", 22, "assets")],
    "clearwater-field-ops":   [("core_telematics", 20, "assets"), ("maintenance_alerts", 20, "assets")],
    "summit-industrial":      [("core_telematics", 25, "assets"), ("fuel_analytics", 18, "assets")],
    "trailhead-logistics":    [("core_telematics", 200, "assets"), ("route_optimization", 200, "assets"), ("advanced_reporting", 90, "users"), ("fuel_analytics", 200, "assets"), ("compliance_dashboard", 90, "users")],
    "crestline-distribution": [("core_telematics", 60, "assets"), ("route_optimization", 60, "assets"), ("advanced_reporting", 40, "users")],
    "redwood-fleet":          [("core_telematics", 22, "assets"), ("driver_coaching", 22, "assets"), ("fuel_analytics", 15, "assets")],
    "bison-transport":        [("core_telematics", 180, "assets"), ("route_optimization", 180, "assets"), ("driver_coaching", 70, "assets"), ("advanced_reporting", 70, "users")],
    "copperfield-warehousing":[("core_telematics", 20, "assets"), ("maintenance_alerts", 20, "assets")],
    "cascade-field":          [("core_telematics", 20, "assets"), ("maintenance_alerts", 20, "assets")],
    "timberline-logistics":   [("core_telematics", 70, "assets"), ("route_optimization", 70, "assets"), ("fuel_analytics", 45, "assets")],
    "falcon-delivery":        [("core_telematics", 15, "assets")],
    "mesa-industrial":        [("core_telematics", 25, "assets"), ("fuel_analytics", 25, "assets"), ("compliance_dashboard", 16, "users")],
    "stonebridge-fleet":      [("core_telematics", 18, "assets"), ("route_optimization", 18, "assets")],
    "prairie-wind":           [("core_telematics", 15, "assets")],
    "aspenridge-supply":      [("core_telematics", 18, "assets"), ("route_optimization", 18, "assets")],
    "granite-peak":           [("core_telematics", 10, "assets")],
    "ironridge-fleet":        [("core_telematics", 16, "assets"), ("driver_coaching", 16, "assets"), ("maintenance_alerts", 12, "assets")],
    "hawkstone-industries":   [("core_telematics", 75, "assets"), ("fuel_analytics", 75, "assets"), ("compliance_dashboard", 48, "users"), ("maintenance_alerts", 75, "assets")],
    "meridian-fleet":         [("core_telematics", 60, "assets"), ("route_optimization", 60, "assets"), ("driver_coaching", 55, "assets"), ("maintenance_alerts", 60, "assets")],
    "oakmont-logistics":      [("core_telematics", 50, "assets"), ("route_optimization", 50, "assets"), ("fuel_analytics", 40, "assets")],
    "blueridge-transport":    [("core_telematics", 20, "assets"), ("route_optimization", 20, "assets")],
    "westfield-industrial":   [("core_telematics", 20, "assets"), ("fuel_analytics", 15, "assets")],
    "pinnacle-supply":        [("core_telematics", 250, "assets"), ("route_optimization", 250, "assets"), ("advanced_reporting", 70, "users"), ("fuel_analytics", 250, "assets"), ("dispatch_automation", 70, "assets")],
    "sagebrush-transport":    [("core_telematics", 35, "assets"), ("route_optimization", 35, "assets"), ("driver_coaching", 22, "assets")],
    "driftwood-warehousing":  [("core_telematics", 15, "assets"), ("maintenance_alerts", 15, "assets")],
    "cypress-field":          [("core_telematics", 40, "assets"), ("maintenance_alerts", 40, "assets"), ("compliance_dashboard", 28, "users")],
    "quarrystone-logistics":  [("core_telematics", 12, "assets")],
    "harborview-fleet":       [("core_telematics", 55, "assets"), ("route_optimization", 55, "assets"), ("advanced_reporting", 40, "users"), ("dispatch_automation", 40, "assets")],
    "windmill-transport":     [("core_telematics", 15, "assets"), ("route_optimization", 15, "assets"), ("fuel_analytics", 10, "assets")],
    "cedar-valley":           [("core_telematics", 15, "assets"), ("route_optimization", 15, "assets")],
    # churned accounts have no active entitlements
}

# ---------------------------------------------------------------------------
# Cases  (account_slug, status, priority, origin, subject, created_at, closed_at)
# ---------------------------------------------------------------------------
_CASES: list[tuple[str, str, str, str, str, str, str | None]] = [
    ("ironhorse-freight",    "Open",   "Medium", "Email",  "GPS hardware compatibility issue with older vehicles",             "2026-06-15T10:00:00Z", None),
    ("pinehill-transport",   "Open",   "High",   "Email",  "Integration with legacy dispatch system failing",                  "2026-06-10T09:00:00Z", None),
    ("clearwater-field-ops", "Open",   "Low",    "Portal", "Question about mobile app setup for technicians",                  "2026-06-12T14:00:00Z", None),
    ("trailhead-logistics",  "Closed", "Low",    "Portal", "Feature request: custom compliance report template",               "2026-04-10T11:00:00Z", "2026-05-15T16:00:00Z"),
    ("sagebrush-transport",  "Open",   "High",   "Email",  "Frustrated with slow reporting performance",                       "2026-06-15T08:30:00Z", None),
    ("cypress-field",        "Open",   "High",   "Email",  "Repeated GPS accuracy issues in rural areas",                      "2026-06-05T09:00:00Z", None),
    ("cypress-field",        "Open",   "Medium", "Portal", "API timeouts affecting dispatch workflow",                          "2026-06-18T11:00:00Z", None),
    ("quarrystone-logistics", "Open",  "Medium", "Portal", "Need to transfer admin access to new contact",                     "2026-06-10T10:00:00Z", None),
    ("harborview-fleet",     "Open",   "High",   "Email",  "Integration with new ERP system not working as expected",           "2026-06-08T14:00:00Z", None),
    ("harborview-fleet",     "Closed", "Medium", "Portal", "Billing discrepancy on last invoice",                              "2026-05-10T09:00:00Z", "2026-05-18T15:00:00Z"),
    ("riverstone-logistics", "Closed", "High",   "Email",  "Missing native ERP integration is dealbreaker",                    "2026-03-15T10:00:00Z", "2026-04-15T16:00:00Z"),
]

# ---------------------------------------------------------------------------
# Opportunities  (slug, opp_type, amount_cents, stage, close_date)
# ---------------------------------------------------------------------------
_OPPS: list[tuple[str, str, int, str, str]] = [
    ("trailhead-logistics",  "Expansion", 4_500_000,  "Qualification", "2026-10-01"),
    ("meridian-fleet",       "Expansion", 8_500_000,  "Qualification", "2026-10-15"),
    ("oakmont-logistics",    "Expansion", 3_500_000,  "Proposal",      "2026-09-01"),
    ("harborview-fleet",     "Renewal",   14_000_000, "Proposal",      "2026-08-05"),
    ("windmill-transport",   "Renewal",    4_200_000, "Proposal",      "2026-08-20"),
    ("cedar-valley",         "Renewal",    3_500_000, "Qualification", "2026-07-21"),
]

# ---------------------------------------------------------------------------
# CTAs  (slug, reason, priority, status, due_date, owner_id)
# ---------------------------------------------------------------------------
_CTAS: list[tuple[str, str, str, str, str, str]] = [
    ("meridian-fleet",       "Expansion opportunity - facilities department interested",       "High", "open", "2026-07-15", "csm-101"),
    ("westfield-industrial", "Asset overage - usage exceeds entitlement",                      "High", "open", "2026-07-01", "csm-103"),
    ("sagebrush-transport",  "Usage decline - engagement intervention needed",                 "High", "open", "2026-07-01", "csm-103"),
    ("cypress-field",        "Multiple support escalations - review account health",           "High", "open", "2026-06-28", "csm-103"),
    ("quarrystone-logistics","Champion departed - identify new stakeholder",                   "High", "open", "2026-07-01", "csm-104"),
    ("harborview-fleet",     "Renewal risk - address declining satisfaction before renewal",   "High", "open", "2026-07-15", "csm-102"),
]

# ---------------------------------------------------------------------------
# Success plans  (slug, status, objectives_tuple, target_date)
# ---------------------------------------------------------------------------
_PLANS: list[tuple[str, str, tuple[str, ...], str]] = [
    ("ironhorse-freight",   "active", ("activate_core_fleet", "complete_driver_onboarding"),                                 "2026-07-15"),
    ("pinehill-transport",  "active", ("activate_core_fleet", "configure_routing", "api_integration", "driver_training", "go_live"), "2026-06-21"),
    ("ridgeline-warehousing","active",("activate_core_fleet",),                                                              "2026-07-14"),
    ("northstar-couriers",  "active", ("activate_core_fleet", "optimize_routes"),                                            "2026-07-05"),
    ("clearwater-field-ops","active", ("activate_core_fleet", "mobile_rollout"),                                             "2026-07-15"),
    ("summit-industrial",   "active", ("activate_core_fleet", "deploy_fuel_analytics"),                                      "2026-07-20"),
    ("trailhead-logistics", "active", ("maintain_exemplary_adoption", "expand_compliance_reporting"),                         "2026-09-01"),
]

# ---------------------------------------------------------------------------
# Milestones  (slug, milestone, expected_by, achieved_at)
# ---------------------------------------------------------------------------
_MILESTONES: list[tuple[str, str, str, str | None]] = [
    ("ironhorse-freight",   "activate_50pct_assets",     "2026-06-22", None),
    ("ironhorse-freight",   "first_route_optimization",  "2026-07-01", None),
    ("pinehill-transport",  "admin_setup",               "2026-05-31", "2026-05-28T16:00:00Z"),
    ("pinehill-transport",  "first_telematics_report",   "2026-06-03", "2026-06-02T14:00:00Z"),
    ("pinehill-transport",  "api_integration",           "2026-06-10", "2026-06-08T10:00:00Z"),
    ("pinehill-transport",  "activate_50pct_assets",     "2026-06-14", None),
    ("pinehill-transport",  "configure_routing",         "2026-06-17", None),
    ("ridgeline-warehousing","admin_setup",              "2026-06-21", None),
    ("northstar-couriers",  "activate_50pct_assets",     "2026-06-14", "2026-06-12T11:00:00Z"),
    ("clearwater-field-ops","admin_setup",               "2026-06-15", "2026-06-14T09:00:00Z"),
    ("clearwater-field-ops","activate_50pct_assets",     "2026-06-22", None),
    ("summit-industrial",   "admin_setup",               "2026-06-14", "2026-06-10T15:00:00Z"),
    ("summit-industrial",   "activate_50pct_assets",     "2026-06-28", None),
]


# ===================================================================
# Builder
# ===================================================================

def build_synthetic_book() -> FixtureCustomerData:
    """Build a 35-account synthetic book for a fleet-management / industrial IoT SaaS."""

    # -- Accounts --
    accounts = tuple(
        CRMAccount(account_id=_id[slug], name=name, owner_id=csm, industry=ind)
        for slug, name, ind, csm in _ACCT_DATA
    )

    # -- Companies --
    companies = tuple(
        CSCompany(
            company_id=_id[slug],
            name=name,
            industry=ind,
            arr_cents=_COMPANY[slug][0],
            lifecycle_stage=_COMPANY[slug][1],  # type: ignore[arg-type]
            status=_COMPANY[slug][2],
            original_contract_date=_COMPANY[slug][3],
            renewal_date=_COMPANY[slug][4],
            csm_owner_id=csm,
            current_score=_COMPANY[slug][5],
        )
        for slug, name, ind, csm in _ACCT_DATA
    )

    # -- Contacts --
    contacts_list: list[CRMContact] = []
    for slug, contact_rows in _CONTACTS.items():
        aid = _id[slug]
        for name, role, title, email, consent in contact_rows:
            contacts_list.append(CRMContact(
                contact_id=det_id("contact", aid, email),
                account_id=aid,
                email=email,
                name=name,
                role=role,
                title=title,
                consent_to_contact=consent,
            ))
    contacts = tuple(contacts_list)

    # -- Cases --
    cases = tuple(
        CRMCase(
            case_id=det_id("case", _id[slug], subj[:40]),
            account_id=_id[slug],
            status=status,
            priority=pri,
            origin=origin,
            subject=subj,
            created_at=created,
            closed_at=closed,
        )
        for slug, status, pri, origin, subj, created, closed in _CASES
    )

    # -- Opportunities --
    opportunities = tuple(
        CRMOpportunity(
            opportunity_id=det_id("opp", _id[slug], opp_type.lower()),
            account_id=_id[slug],
            stage_name=stage,
            amount_cents=amount,
            close_date=close,
            opportunity_type=opp_type,
        )
        for slug, opp_type, amount, stage, close in _OPPS
    )

    # -- Health scores --
    health_scores = tuple(
        HealthScore(
            account_id=_id[slug],
            score=score,
            band=band,  # type: ignore[arg-type]
            drivers=drivers,
            measured_at=SEED_CLOCK,
        )
        for slug, (score, band, drivers) in _HEALTH.items()
    )

    # -- CTAs --
    ctas = tuple(
        CTA(
            cta_id=det_id("cta", _id[slug], reason[:30]),
            account_id=_id[slug],
            reason=reason,
            priority=pri,
            status=status,  # type: ignore[arg-type]
            due_date=due,
            owner_id=owner,
        )
        for slug, reason, pri, status, due, owner in _CTAS
    )

    # -- Success plans --
    success_plans = tuple(
        SuccessPlan(
            plan_id=det_id("plan", _id[slug], "sp"),
            account_id=_id[slug],
            status=status,
            objectives=objectives,
            target_date=target,
        )
        for slug, status, objectives, target in _PLANS
    )

    # -- Adoption summaries --
    adoption_summaries = tuple(
        AdoptionSummary(
            account_id=_id[slug],
            active_users=au,
            licensed_users=lu,
            active_assets=aa,
            entitled_assets=ea,
            adoption_rate=rate,
            underused_capabilities=underused,
            measured_at=SEED_CLOCK,
        )
        for slug, (au, lu, aa, ea, rate, underused) in _ADOPTION.items()
    )

    # -- Entitlements --
    ent_list: list[Entitlement] = []
    for slug, caps in _ENTITLEMENTS.items():
        aid = _id[slug]
        start = _COMPANY[slug][3]  # original_contract_date
        for cap, qty, unit in caps:
            ent_list.append(Entitlement(aid, cap, qty, unit, start))
    entitlements = tuple(ent_list)

    # -- Usage signals --
    # Company-grain daily_active_assets for every account with active_assets > 0
    signals: list[UsageSignal] = []
    for slug, (_, _, aa, _, _, _) in _ADOPTION.items():
        if aa > 0:
            aid = _id[slug]
            signals.append(UsageSignal(
                signal_id=_sig(aid, "daily_active_assets"),
                account_id=aid,
                grain="company",
                subject_id=None,
                metric_name="daily_active_assets",
                value=float(aa),
                unit="assets",
                observed_at=SEED_CLOCK,
                source_ref="product-telemetry:daily_active_assets",
            ))

    # Person-grain signal for Pinnacle Supply Chain (single-threaded risk)
    pinnacle = _id["pinnacle-supply"]
    signals.append(UsageSignal(
        signal_id=_sig(pinnacle, "person_active_days_derek"),
        account_id=pinnacle,
        grain="person",
        subject_id=det_id("person", pinnacle, "derek-vaughn"),
        metric_name="person_active_days",
        value=28.0,
        unit="days",
        observed_at=SEED_CLOCK,
        source_ref="product-telemetry:person_active_days",
    ))
    usage_signals = tuple(signals)

    # -- Milestones --
    milestones = tuple(
        TimeToValueMilestone(
            account_id=_id[slug],
            milestone=ms,
            expected_by=expected,
            achieved_at=achieved,
            evidence_signal_ids=(_sig(_id[slug], "daily_active_assets"),),
        )
        for slug, ms, expected, achieved in _MILESTONES
    )

    # -- Tenant mapping --
    all_ids = tuple(_id[slug] for slug, *_ in _ACCT_DATA)

    return FixtureCustomerData(
        accounts=accounts,
        companies=companies,
        contacts=contacts,
        cases=cases,
        opportunities=opportunities,
        health_scores=health_scores,
        ctas=ctas,
        success_plans=success_plans,
        adoption_summaries=adoption_summaries,
        entitlements=entitlements,
        usage_signals=usage_signals,
        milestones=milestones,
        tenant_accounts={"ultra-demo": all_ids},
    )


# ===================================================================
# Summary helper
# ===================================================================

def synthetic_book_summary(data: FixtureCustomerData) -> str:
    """Return a formatted summary of the synthetic book."""

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("SYNTHETIC BOOK SUMMARY")
    lines.append("=" * 60)

    # Total accounts
    lines.append(f"\nTotal accounts: {len(data.accounts)}")

    # Lifecycle distribution
    lifecycle_counts: dict[str, int] = {}
    churned_count = 0
    for co in data.companies:
        if co.status == "Churned":
            churned_count += 1
        lifecycle_counts[co.lifecycle_stage] = lifecycle_counts.get(co.lifecycle_stage, 0) + 1
    lines.append("\nLifecycle distribution:")
    for stage in ("onboarding", "adopting", "steady_state", "renewal", "at_risk"):
        cnt = lifecycle_counts.get(stage, 0)
        lines.append(f"  {stage:20s}: {cnt}")
    lines.append(f"  {'(status=Churned)':20s}: {churned_count}")

    # Size distribution
    enterprise, midmarket, smb = [], [], []
    for co in data.companies:
        arr_k = co.arr_cents / 100_000
        if arr_k >= 200:
            enterprise.append(co)
        elif arr_k >= 50:
            midmarket.append(co)
        else:
            smb.append(co)
    lines.append("\nSize distribution:")
    for label, group in [("Enterprise ($200K+)", enterprise), ("Mid-market ($50K-$150K)", midmarket), ("SMB ($15K-$40K)", smb)]:
        total_arr = sum(c.arr_cents for c in group) / 100
        lines.append(f"  {label:25s}: {len(group):2d} accounts, ${total_arr:,.0f} total ARR")

    # Health distribution
    health_by_band: dict[str, int] = {}
    for hs in data.health_scores:
        health_by_band[hs.band] = health_by_band.get(hs.band, 0) + 1
    lines.append("\nHealth distribution:")
    for band in ("green", "yellow", "red", "unknown"):
        lines.append(f"  {band:10s}: {health_by_band.get(band, 0)}")

    # Top 5 risk accounts (lowest health)
    sorted_health = sorted(data.health_scores, key=lambda h: h.score)
    lines.append("\nTop 5 risk accounts (lowest health score):")
    for hs in sorted_health[:5]:
        acct = next((a for a in data.accounts if a.account_id == hs.account_id), None)
        name = acct.name if acct else hs.account_id
        lines.append(f"  {name:35s}  score={hs.score:5.1f}  band={hs.band}")

    # Top 5 expansion candidates
    steady_adoptions = []
    for co in data.companies:
        if co.lifecycle_stage == "steady_state" and co.status == "Active":
            adopt = next((a for a in data.adoption_summaries if a.account_id == co.company_id), None)
            if adopt and adopt.adoption_rate >= 0.85:
                steady_adoptions.append((co, adopt))
    steady_adoptions.sort(key=lambda x: x[1].adoption_rate, reverse=True)
    lines.append("\nTop 5 expansion candidates (steady_state, adoption >= 0.85):")
    for co, adopt in steady_adoptions[:5]:
        lines.append(f"  {co.name:35s}  adoption={adopt.adoption_rate:.2f}  ARR=${co.arr_cents / 100:,.0f}")

    # Key scenarios
    lines.append("\nKey scenarios in this book:")
    scenarios = [
        "Stalled onboarding with overdue success plan (Pinehill Transport)",
        "Single-threaded champion risk - misleading green health (Pinnacle Supply Chain)",
        "Champion departure with no successor (Quarry Stone Logistics)",
        "Renewal at risk with declining CSAT and CFO evaluating alternatives (Harborview Fleet)",
        "Expansion opportunity from new department (Meridian Fleet Group)",
        "Asset overage exceeding entitlement (Westfield Industrial)",
        "Advocacy-ready exemplary adoption (Trailhead Logistics)",
        "Multiple open escalations with overdue renewal (Cypress Field Ops)",
        "Recent churn - competitor loss (Riverstone Logistics)",
        "Recent churn - budget cut (Dustbowl Freight)",
        "Fast-tracking onboarding ahead of schedule (Summit Industrial Supply)",
        "Usage decline with engagement drop (Sagebrush Transport)",
    ]
    for s in scenarios:
        lines.append(f"  - {s}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)
