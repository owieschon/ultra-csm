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
    ("ironclad-freight", "Ironclad Freight", "logistics", "csm-101"),  # high
    ("sterling-fleet-services", "Sterling Fleet Services", "fleet_management", "csm-101"),  # high
    ("cobalt-fleet-ops", "Cobalt Fleet Ops", "warehousing", "csm-104"),  # high
    ("ridgeline-fleet-services", "Ridgeline Fleet Services", "logistics", "csm-104"),  # high
    ("northbend-haulage", "Northbend Haulage", "field_services", "csm-101"),  # high
    ("fairview-line-haul", "Fairview Line Haul", "transportation", "csm-102"),  # high
    ("amberline-supply-chain", "Amberline Supply Chain", "transportation", "csm-104"),  # high
    ("brookstone-supply-chain", "Brookstone Supply Chain", "field_services", "csm-101"),  # mid
    ("cedarfield-industrial-supply", "Cedarfield Industrial Supply", "transportation", "csm-102"),  # mid
    ("deerpath-carriers", "Deerpath Carriers", "field_services", "csm-102"),  # mid
    ("elmwood-trucking", "Elmwood Trucking", "fleet_management", "csm-102"),  # mid
    ("foxhollow-field-services", "Foxhollow Field Services", "transportation", "csm-101"),  # mid
    ("grovemont-delivery", "Grovemont Delivery", "transportation", "csm-103"),  # mid
    ("hillcrest-haulage", "Hillcrest Haulage", "warehousing", "csm-103"),  # mid
    ("ivywood-haulage", "Ivywood Haulage", "field_services", "csm-102"),  # mid
    ("juniper-trucking", "Juniper Trucking", "fleet_management", "csm-104"),  # mid
    ("kingsford-delivery", "Kingsford Delivery", "transportation", "csm-103"),  # mid
    ("lakeshore-warehousing", "Lakeshore Warehousing", "fleet_management", "csm-104"),  # mid
    ("millbrook-trucking", "Millbrook Trucking", "transportation", "csm-102"),  # mid
    ("northgate-delivery", "Northgate Delivery", "warehousing", "csm-104"),  # mid
    ("oakridge-carriers", "Oakridge Carriers", "field_services", "csm-103"),  # mid
    ("pinebluff-supply-chain", "Pinebluff Supply Chain", "warehousing", "csm-102"),  # mid
    ("quarrymill-fleet-ops", "Quarrymill Fleet Ops", "logistics", "csm-101"),  # mid
    ("redstone-transport-co", "Redstone Transport Co", "fleet_management", "csm-104"),  # mid
    ("silverlake-haulage", "Silverlake Haulage", "field_services", "csm-101"),  # mid
    ("thornwood-fleet-services", "Thornwood Fleet Services", "transportation", "csm-103"),  # mid
    ("underhill-fleet-ops", "Underhill Fleet Ops", "field_services", "csm-104"),  # mid
    ("valleyfield-field-services", "Valleyfield Field Services", "fleet_management", "csm-104"),  # mid
    ("westbrook-logistics", "Westbrook Logistics", "field_services", "csm-101"),  # mid
    ("yellowpine-fleet-services", "Yellowpine Fleet Services", "logistics", "csm-103"),  # mid
    ("ashford-haulage", "Ashford Haulage", "fleet_management", "csm-104"),  # mid
    ("birchwood-line-haul", "Birchwood Line Haul", "field_services", "csm-104"),  # mid
    ("claybourne-transport-co", "Claybourne Transport Co", "warehousing", "csm-104"),  # mid
    ("dunmore-transport-co", "Dunmore Transport Co", "field_services", "csm-104"),  # mid
    ("eastfield-freight", "Eastfield Freight", "warehousing", "csm-104"),  # mid
    ("farrow-fleet-ops", "Farrow Fleet Ops", "logistics", "csm-104"),  # tech
    ("glenbrook-distribution", "Glenbrook Distribution", "field_services", "csm-103"),  # tech
    ("harlow-warehousing", "Harlow Warehousing", "transportation", "csm-101"),  # tech
    ("innisfree-logistics", "Innisfree Logistics", "field_services", "csm-102"),  # tech
    ("kestrel-logistics", "Kestrel Logistics", "transportation", "csm-101"),  # tech
    ("longview-delivery", "Longview Delivery", "warehousing", "csm-103"),  # tech
    ("marrow-trucking", "Marrow Trucking", "logistics", "csm-103"),  # tech
    ("newland-fleet-ops", "Newland Fleet Ops", "field_services", "csm-102"),  # tech
    ("overlook-haulage", "Overlook Haulage", "fleet_management", "csm-102"),  # tech
    ("parkview-fleet-services", "Parkview Fleet Services", "field_services", "csm-102"),  # tech
    ("rockford-line-haul", "Rockford Line Haul", "logistics", "csm-101"),  # tech
    ("sandhill-distribution", "Sandhill Distribution", "transportation", "csm-103"),  # tech
    ("timberline2-fleet-ops", "Timberline2 Fleet Ops", "warehousing", "csm-104"),  # tech
    ("vantage-line-haul", "Vantage Line Haul", "fleet_management", "csm-101"),  # tech
    ("wolfden-warehousing", "Wolfden Warehousing", "logistics", "csm-103"),  # tech
    ("ashgate-industrial-supply", "Ashgate Industrial Supply", "logistics", "csm-102"),  # tech
    ("bramblewood-fleet-ops", "Bramblewood Fleet Ops", "fleet_management", "csm-103"),  # tech
    ("copperfield2-carriers", "Copperfield2 Carriers", "transportation", "csm-102"),  # tech
    ("duskwood-transport-co", "Duskwood Transport Co", "warehousing", "csm-104"),  # tech
    ("evergreen-warehousing", "Evergreen Warehousing", "warehousing", "csm-103"),  # tech
    ("fallcreek-transport-co", "Fallcreek Transport Co", "fleet_management", "csm-103"),  # tech
    ("greystone-haulage", "Greystone Haulage", "fleet_management", "csm-101"),  # tech
    ("hawksmoor-warehousing", "Hawksmoor Warehousing", "field_services", "csm-103"),  # tech
    ("ironbark-fleet-ops", "Ironbark Fleet Ops", "transportation", "csm-103"),  # tech
    ("larkspur-transport-co", "Larkspur Transport Co", "fleet_management", "csm-104"),  # tech
    ("marshfield-supply-chain", "Marshfield Supply Chain", "field_services", "csm-102"),  # tech
    ("nightingale-industrial-supply", "Nightingale Industrial Supply", "fleet_management", "csm-103"),  # tech
    ("ostervale-distribution", "Ostervale Distribution", "field_services", "csm-103"),  # tech
    ("pathfinder-freight", "Pathfinder Freight", "field_services", "csm-102"),  # tech
    ("quailridge-line-haul", "Quailridge Line Haul", "warehousing", "csm-102"),  # tech
    ("ravenswood-logistics", "Ravenswood Logistics", "logistics", "csm-103"),  # tech
    ("stonegate-field-services", "Stonegate Field Services", "logistics", "csm-101"),  # tech
    ("truewind-distribution", "Truewind Distribution", "transportation", "csm-102"),  # tech
    ("underpass-transport-co", "Underpass Transport Co", "warehousing", "csm-103"),  # tech
    ("vernonhall-delivery", "Vernonhall Delivery", "field_services", "csm-103"),  # tech
    ("wrenfield-carriers", "Wrenfield Carriers", "warehousing", "csm-103"),  # tech
    ("yarrow-industrial-supply", "Yarrow Industrial Supply", "fleet_management", "csm-103"),  # tech
    ("ashland-transport-co", "Ashland Transport Co", "transportation", "csm-101"),  # tech
    ("belltower-supply-chain", "Belltower Supply Chain", "fleet_management", "csm-101"),  # tech
    ("crestwood2-field-services", "Crestwood2 Field Services", "fleet_management", "csm-101"),  # tech
    ("driftwood2-haulage", "Driftwood2 Haulage", "field_services", "csm-103"),  # tech
    ("emberfield-delivery", "Emberfield Delivery", "fleet_management", "csm-101"),  # tech
    ("frostmoor-supply-chain", "Frostmoor Supply Chain", "logistics", "csm-102"),  # tech
    ("graywolf-warehousing", "Graywolf Warehousing", "logistics", "csm-101"),  # tech
    ("hartland-fleet-services", "Hartland Fleet Services", "field_services", "csm-101"),  # tech
    ("ivorygate-freight", "Ivorygate Freight", "transportation", "csm-101"),  # tech
    ("juniperfield-logistics", "Juniperfield Logistics", "logistics", "csm-104"),  # tech
    ("knollwood-transport-co", "Knollwood Transport Co", "fleet_management", "csm-103"),  # tech
    ("lonepine-supply-chain", "Lonepine Supply Chain", "logistics", "csm-103"),  # tech
    ("meadowlark-field-services", "Meadowlark Field Services", "field_services", "csm-102"),  # tech
    ("nightfall-warehousing", "Nightfall Warehousing", "fleet_management", "csm-103"),  # tech
    ("oldstone-industrial-supply", "Oldstone Industrial Supply", "transportation", "csm-101"),  # tech
    ("poplarcreek-trucking", "Poplarcreek Trucking", "warehousing", "csm-103"),  # tech
    ("quietbrook-warehousing", "Quietbrook Warehousing", "transportation", "csm-101"),  # tech
    ("rimrock-trucking", "Rimrock Trucking", "warehousing", "csm-102"),  # tech
    ("sagewood-fleet-ops", "Sagewood Fleet Ops", "warehousing", "csm-102"),  # tech
    ("trailrock-trucking", "Trailrock Trucking", "field_services", "csm-102"),  # tech
    ("umberfield-industrial-supply", "Umberfield Industrial Supply", "fleet_management", "csm-102"),  # tech
    ("vinecrest-freight", "Vinecrest Freight", "warehousing", "csm-104"),  # tech
    ("watermill-trucking", "Watermill Trucking", "warehousing", "csm-102"),  # tech
    ("yewbrook-field-services", "Yewbrook Field Services", "transportation", "csm-103"),  # tech
    ("amberfield-fleet-ops", "Amberfield Fleet Ops", "fleet_management", "csm-102"),  # tech
    ("boulderfield-fleet-services", "Boulderfield Fleet Services", "field_services", "csm-104"),  # tech
    ("clearcreek2-industrial-supply", "Clearcreek2 Industrial Supply", "warehousing", "csm-102"),  # tech
    ("duncehall-haulage", "Duncehall Haulage", "warehousing", "csm-101"),  # tech
    ("elderwood-trucking", "Elderwood Trucking", "warehousing", "csm-102"),  # tech
    ("foxglove-delivery", "Foxglove Delivery", "field_services", "csm-104"),  # tech
    ("granitehill-distribution", "Granitehill Distribution", "field_services", "csm-101"),  # tech
    ("hollowbrook-distribution", "Hollowbrook Distribution", "transportation", "csm-104"),  # tech
    ("ironwood2-line-haul", "Ironwood2 Line Haul", "fleet_management", "csm-104"),  # tech
    ("jasperfield-logistics", "Jasperfield Logistics", "field_services", "csm-104"),  # tech
    ("kettlecreek-distribution", "Kettlecreek Distribution", "field_services", "csm-101"),  # tech
    ("lindenfield-supply-chain", "Lindenfield Supply Chain", "warehousing", "csm-101"),  # tech
    ("mossgate-logistics", "Mossgate Logistics", "logistics", "csm-104"),  # tech
    ("northwind-distribution", "Northwind Distribution", "logistics", "csm-101"),  # tech
    ("orchardview-industrial-supply", "Orchardview Industrial Supply", "fleet_management", "csm-103"),  # tech
    ("palewood-field-services", "Palewood Field Services", "field_services", "csm-102"),  # tech
    ("quarrycreek-haulage", "Quarrycreek Haulage", "field_services", "csm-101"),  # tech
    ("roughcut-freight", "Roughcut Freight", "fleet_management", "csm-102"),  # tech
    ("stillwater2-freight", "Stillwater2 Freight", "transportation", "csm-102"),  # tech
    ("thistledown-field-services", "Thistledown Field Services", "warehousing", "csm-102"),  # tech
    ("uplands-distribution", "Uplands Distribution", "fleet_management", "csm-101"),  # tech
    ("verdantfield-logistics", "Verdantfield Logistics", "warehousing", "csm-101"),  # tech
    ("whitfield-transport-co", "Whitfield Transport Co", "warehousing", "csm-104"),  # tech
    ("yarrowfield-delivery", "Yarrowfield Delivery", "transportation", "csm-104"),  # tech
    ("ashwell-supply-chain", "Ashwell Supply Chain", "transportation", "csm-103"),  # tech
    ("bramblecreek-line-haul", "Bramblecreek Line Haul", "logistics", "csm-104"),  # tech
    ("cinderfield-delivery", "Cinderfield Delivery", "logistics", "csm-101"),  # tech
    ("deepwater-haulage", "Deepwater Haulage", "logistics", "csm-104"),  # tech
    ("everfield-transport-co", "Everfield Transport Co", "logistics", "csm-102"),  # tech
    ("flintridge-field-services", "Flintridge Field Services", "fleet_management", "csm-103"),  # tech
    ("goldenfield-trucking", "Goldenfield Trucking", "transportation", "csm-104"),  # tech
    ("hazelwood-transport-co", "Hazelwood Transport Co", "transportation", "csm-103"),  # tech
    ("ironhollow-line-haul", "Ironhollow Line Haul", "logistics", "csm-104"),  # tech
    ("junipergate-line-haul", "Junipergate Line Haul", "fleet_management", "csm-103"),  # tech
    ("kirkfield-line-haul", "Kirkfield Line Haul", "transportation", "csm-102"),  # tech
    ("lowcreek-delivery", "Lowcreek Delivery", "warehousing", "csm-104"),  # tech
    ("mistvale-trucking", "Mistvale Trucking", "warehousing", "csm-102"),  # tech
    ("netherfield-industrial-supply", "Netherfield Industrial Supply", "warehousing", "csm-103"),  # tech
    ("oakhollow-industrial-supply", "Oakhollow Industrial Supply", "fleet_management", "csm-103"),  # tech
    ("plainfield2-transport-co", "Plainfield2 Transport Co", "transportation", "csm-104"),  # tech
    ("quarrystone2-warehousing", "Quarrystone2 Warehousing", "fleet_management", "csm-103"),  # tech
    ("redcreek-distribution", "Redcreek Distribution", "warehousing", "csm-103"),  # tech
    ("slatefield-transport-co", "Slatefield Transport Co", "transportation", "csm-101"),  # tech
    ("timbergate-transport-co", "Timbergate Transport Co", "fleet_management", "csm-104"),  # tech
    ("uppercreek-logistics", "Uppercreek Logistics", "logistics", "csm-101"),  # tech
    ("vandermill-haulage", "Vandermill Haulage", "fleet_management", "csm-101"),  # tech
    ("woodbine-transport-co", "Woodbine Transport Co", "logistics", "csm-103"),  # tech
    ("yorkfield-industrial-supply", "Yorkfield Industrial Supply", "field_services", "csm-104"),  # tech
    ("ironclad-logistics", "Ironclad Logistics", "transportation", "csm-101"),  # tech
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
    "ironclad-freight": (21000000, "steady_state", "Active", "2025-06-01", "2027-06-01", 71.0),
    "sterling-fleet-services": (17000000, "steady_state", "Active", "2025-06-01", "2027-06-01", 63.0),
    "cobalt-fleet-ops": (16500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 62.0),
    "ridgeline-fleet-services": (18500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 86.0),
    "northbend-haulage": (27000000, "steady_state", "Active", "2025-06-01", "2027-06-01", 61.0),
    "fairview-line-haul": (21500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 64.0),
    "amberline-supply-chain": (22500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 70.0),
    "brookstone-supply-chain": (6500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 67.0),
    "cedarfield-industrial-supply": (7600000, "steady_state", "Active", "2025-06-01", "2027-06-01", 72.0),
    "deerpath-carriers": (5200000, "steady_state", "Active", "2025-06-01", "2027-06-01", 76.0),
    "elmwood-trucking": (3500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 78.0),
    "foxhollow-field-services": (4200000, "steady_state", "Active", "2025-06-01", "2027-06-01", 87.0),
    "grovemont-delivery": (6400000, "steady_state", "Active", "2025-06-01", "2027-06-01", 81.0),
    "hillcrest-haulage": (9500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 89.0),
    "ivywood-haulage": (2500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 82.0),
    "juniper-trucking": (6600000, "steady_state", "Active", "2025-06-01", "2027-06-01", 66.0),
    "kingsford-delivery": (7600000, "steady_state", "Active", "2025-06-01", "2027-06-01", 65.0),
    "lakeshore-warehousing": (9800000, "steady_state", "Active", "2025-06-01", "2027-06-01", 80.0),
    "millbrook-trucking": (4600000, "steady_state", "Active", "2025-06-01", "2027-06-01", 72.0),
    "northgate-delivery": (6500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 62.0),
    "oakridge-carriers": (8400000, "steady_state", "Active", "2025-06-01", "2027-06-01", 81.0),
    "pinebluff-supply-chain": (3100000, "steady_state", "Active", "2025-06-01", "2027-06-01", 84.0),
    "quarrymill-fleet-ops": (6300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 69.0),
    "redstone-transport-co": (2700000, "steady_state", "Active", "2025-06-01", "2027-06-01", 80.0),
    "silverlake-haulage": (5200000, "steady_state", "Active", "2025-06-01", "2027-06-01", 63.0),
    "thornwood-fleet-services": (7900000, "steady_state", "Active", "2025-06-01", "2027-06-01", 77.0),
    "underhill-fleet-ops": (3100000, "steady_state", "Active", "2025-06-01", "2027-06-01", 82.0),
    "valleyfield-field-services": (8100000, "steady_state", "Active", "2025-06-01", "2027-06-01", 70.0),
    "westbrook-logistics": (4800000, "steady_state", "Active", "2025-06-01", "2027-06-01", 69.0),
    "yellowpine-fleet-services": (7300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 71.0),
    "ashford-haulage": (9000000, "steady_state", "Active", "2025-06-01", "2027-06-01", 86.0),
    "birchwood-line-haul": (9100000, "steady_state", "Active", "2025-06-01", "2027-06-01", 70.0),
    "claybourne-transport-co": (3400000, "steady_state", "Active", "2025-06-01", "2027-06-01", 66.0),
    "dunmore-transport-co": (4700000, "steady_state", "Active", "2025-06-01", "2027-06-01", 62.0),
    "eastfield-freight": (7300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 84.0),
    "farrow-fleet-ops": (1000000, "steady_state", "Active", "2025-06-01", "2027-06-01", 88.0),
    "glenbrook-distribution": (500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 67.0),
    "harlow-warehousing": (900000, "steady_state", "Active", "2025-06-01", "2027-06-01", 77.0),
    "innisfree-logistics": (600000, "steady_state", "Active", "2025-06-01", "2027-06-01", 72.0),
    "kestrel-logistics": (700000, "steady_state", "Active", "2025-06-01", "2027-06-01", 71.0),
    "longview-delivery": (1100000, "steady_state", "Active", "2025-06-01", "2027-06-01", 87.0),
    "marrow-trucking": (1100000, "steady_state", "Active", "2025-06-01", "2027-06-01", 77.0),
    "newland-fleet-ops": (1200000, "steady_state", "Active", "2025-06-01", "2027-06-01", 80.0),
    "overlook-haulage": (1800000, "steady_state", "Active", "2025-06-01", "2027-06-01", 80.0),
    "parkview-fleet-services": (2000000, "steady_state", "Active", "2025-06-01", "2027-06-01", 70.0),
    "rockford-line-haul": (300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 67.0),
    "sandhill-distribution": (1700000, "steady_state", "Active", "2025-06-01", "2027-06-01", 85.0),
    "timberline2-fleet-ops": (2200000, "steady_state", "Active", "2025-06-01", "2027-06-01", 76.0),
    "vantage-line-haul": (1300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 89.0),
    "wolfden-warehousing": (1900000, "steady_state", "Active", "2025-06-01", "2027-06-01", 71.0),
    "ashgate-industrial-supply": (400000, "steady_state", "Active", "2025-06-01", "2027-06-01", 78.0),
    "bramblewood-fleet-ops": (700000, "steady_state", "Active", "2025-06-01", "2027-06-01", 75.0),
    "copperfield2-carriers": (800000, "steady_state", "Active", "2025-06-01", "2027-06-01", 72.0),
    "duskwood-transport-co": (1400000, "steady_state", "Active", "2025-06-01", "2027-06-01", 82.0),
    "evergreen-warehousing": (900000, "steady_state", "Active", "2025-06-01", "2027-06-01", 79.0),
    "fallcreek-transport-co": (2300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 87.0),
    "greystone-haulage": (1100000, "steady_state", "Active", "2025-06-01", "2027-06-01", 65.0),
    "hawksmoor-warehousing": (900000, "steady_state", "Active", "2025-06-01", "2027-06-01", 73.0),
    "ironbark-fleet-ops": (300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 87.0),
    "larkspur-transport-co": (1600000, "steady_state", "Active", "2025-06-01", "2027-06-01", 60.0),
    "marshfield-supply-chain": (2400000, "steady_state", "Active", "2025-06-01", "2027-06-01", 86.0),
    "nightingale-industrial-supply": (1500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 89.0),
    "ostervale-distribution": (1300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 79.0),
    "pathfinder-freight": (1800000, "steady_state", "Active", "2025-06-01", "2027-06-01", 68.0),
    "quailridge-line-haul": (800000, "steady_state", "Active", "2025-06-01", "2027-06-01", 64.0),
    "ravenswood-logistics": (1500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 65.0),
    "stonegate-field-services": (500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 79.0),
    "truewind-distribution": (1000000, "steady_state", "Active", "2025-06-01", "2027-06-01", 70.0),
    "underpass-transport-co": (1900000, "steady_state", "Active", "2025-06-01", "2027-06-01", 71.0),
    "vernonhall-delivery": (1100000, "steady_state", "Active", "2025-06-01", "2027-06-01", 73.0),
    "wrenfield-carriers": (1100000, "steady_state", "Active", "2025-06-01", "2027-06-01", 69.0),
    "yarrow-industrial-supply": (1300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 83.0),
    "ashland-transport-co": (2100000, "steady_state", "Active", "2025-06-01", "2027-06-01", 61.0),
    "belltower-supply-chain": (1500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 77.0),
    "crestwood2-field-services": (1900000, "steady_state", "Active", "2025-06-01", "2027-06-01", 77.0),
    "driftwood2-haulage": (500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 87.0),
    "emberfield-delivery": (500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 75.0),
    "frostmoor-supply-chain": (1000000, "steady_state", "Active", "2025-06-01", "2027-06-01", 76.0),
    "graywolf-warehousing": (1100000, "steady_state", "Active", "2025-06-01", "2027-06-01", 79.0),
    "hartland-fleet-services": (300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 81.0),
    "ivorygate-freight": (300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 81.0),
    "juniperfield-logistics": (800000, "steady_state", "Active", "2025-06-01", "2027-06-01", 72.0),
    "knollwood-transport-co": (300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 61.0),
    "lonepine-supply-chain": (900000, "steady_state", "Active", "2025-06-01", "2027-06-01", 73.0),
    "meadowlark-field-services": (2000000, "steady_state", "Active", "2025-06-01", "2027-06-01", 84.0),
    "nightfall-warehousing": (300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 85.0),
    "oldstone-industrial-supply": (1300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 61.0),
    "poplarcreek-trucking": (1700000, "steady_state", "Active", "2025-06-01", "2027-06-01", 71.0),
    "quietbrook-warehousing": (500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 67.0),
    "rimrock-trucking": (1000000, "steady_state", "Active", "2025-06-01", "2027-06-01", 86.0),
    "sagewood-fleet-ops": (2400000, "steady_state", "Active", "2025-06-01", "2027-06-01", 78.0),
    "trailrock-trucking": (1000000, "steady_state", "Active", "2025-06-01", "2027-06-01", 64.0),
    "umberfield-industrial-supply": (800000, "steady_state", "Active", "2025-06-01", "2027-06-01", 74.0),
    "vinecrest-freight": (2400000, "steady_state", "Active", "2025-06-01", "2027-06-01", 84.0),
    "watermill-trucking": (1400000, "steady_state", "Active", "2025-06-01", "2027-06-01", 62.0),
    "yewbrook-field-services": (2300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 75.0),
    "amberfield-fleet-ops": (1600000, "steady_state", "Active", "2025-06-01", "2027-06-01", 64.0),
    "boulderfield-fleet-services": (1000000, "steady_state", "Active", "2025-06-01", "2027-06-01", 80.0),
    "clearcreek2-industrial-supply": (2400000, "steady_state", "Active", "2025-06-01", "2027-06-01", 76.0),
    "duncehall-haulage": (1300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 65.0),
    "elderwood-trucking": (2000000, "steady_state", "Active", "2025-06-01", "2027-06-01", 68.0),
    "foxglove-delivery": (2400000, "steady_state", "Active", "2025-06-01", "2027-06-01", 68.0),
    "granitehill-distribution": (1900000, "steady_state", "Active", "2025-06-01", "2027-06-01", 73.0),
    "hollowbrook-distribution": (1400000, "steady_state", "Active", "2025-06-01", "2027-06-01", 64.0),
    "ironwood2-line-haul": (1800000, "steady_state", "Active", "2025-06-01", "2027-06-01", 88.0),
    "jasperfield-logistics": (600000, "steady_state", "Active", "2025-06-01", "2027-06-01", 78.0),
    "kettlecreek-distribution": (1700000, "steady_state", "Active", "2025-06-01", "2027-06-01", 89.0),
    "lindenfield-supply-chain": (1500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 63.0),
    "mossgate-logistics": (600000, "steady_state", "Active", "2025-06-01", "2027-06-01", 84.0),
    "northwind-distribution": (1500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 83.0),
    "orchardview-industrial-supply": (1300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 65.0),
    "palewood-field-services": (2200000, "steady_state", "Active", "2025-06-01", "2027-06-01", 76.0),
    "quarrycreek-haulage": (2100000, "steady_state", "Active", "2025-06-01", "2027-06-01", 85.0),
    "roughcut-freight": (600000, "steady_state", "Active", "2025-06-01", "2027-06-01", 72.0),
    "stillwater2-freight": (1000000, "steady_state", "Active", "2025-06-01", "2027-06-01", 88.0),
    "thistledown-field-services": (1400000, "steady_state", "Active", "2025-06-01", "2027-06-01", 86.0),
    "uplands-distribution": (300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 65.0),
    "verdantfield-logistics": (900000, "steady_state", "Active", "2025-06-01", "2027-06-01", 83.0),
    "whitfield-transport-co": (2000000, "steady_state", "Active", "2025-06-01", "2027-06-01", 82.0),
    "yarrowfield-delivery": (600000, "steady_state", "Active", "2025-06-01", "2027-06-01", 84.0),
    "ashwell-supply-chain": (2300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 89.0),
    "bramblecreek-line-haul": (2400000, "steady_state", "Active", "2025-06-01", "2027-06-01", 86.0),
    "cinderfield-delivery": (1300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 67.0),
    "deepwater-haulage": (2000000, "steady_state", "Active", "2025-06-01", "2027-06-01", 78.0),
    "everfield-transport-co": (1600000, "steady_state", "Active", "2025-06-01", "2027-06-01", 72.0),
    "flintridge-field-services": (1300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 61.0),
    "goldenfield-trucking": (1600000, "steady_state", "Active", "2025-06-01", "2027-06-01", 74.0),
    "hazelwood-transport-co": (1100000, "steady_state", "Active", "2025-06-01", "2027-06-01", 67.0),
    "ironhollow-line-haul": (800000, "steady_state", "Active", "2025-06-01", "2027-06-01", 76.0),
    "junipergate-line-haul": (2100000, "steady_state", "Active", "2025-06-01", "2027-06-01", 83.0),
    "kirkfield-line-haul": (1400000, "steady_state", "Active", "2025-06-01", "2027-06-01", 62.0),
    "lowcreek-delivery": (1000000, "steady_state", "Active", "2025-06-01", "2027-06-01", 84.0),
    "mistvale-trucking": (800000, "steady_state", "Active", "2025-06-01", "2027-06-01", 80.0),
    "netherfield-industrial-supply": (1300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 89.0),
    "oakhollow-industrial-supply": (1300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 75.0),
    "plainfield2-transport-co": (1600000, "steady_state", "Active", "2025-06-01", "2027-06-01", 70.0),
    "quarrystone2-warehousing": (1100000, "steady_state", "Active", "2025-06-01", "2027-06-01", 77.0),
    "redcreek-distribution": (1900000, "steady_state", "Active", "2025-06-01", "2027-06-01", 89.0),
    "slatefield-transport-co": (500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 75.0),
    "timbergate-transport-co": (1200000, "steady_state", "Active", "2025-06-01", "2027-06-01", 82.0),
    "uppercreek-logistics": (2300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 89.0),
    "vandermill-haulage": (1700000, "steady_state", "Active", "2025-06-01", "2027-06-01", 63.0),
    "woodbine-transport-co": (500000, "steady_state", "Active", "2025-06-01", "2027-06-01", 83.0),
    "yorkfield-industrial-supply": (800000, "steady_state", "Active", "2025-06-01", "2027-06-01", 78.0),
    "ironclad-logistics": (1300000, "steady_state", "Active", "2025-06-01", "2027-06-01", 85.0),
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
    "ironclad-freight": (71.0, "yellow", ("moderate_adoption",)),
    "sterling-fleet-services": (63.0, "green", ("stable_usage",)),
    "cobalt-fleet-ops": (62.0, "yellow", ("moderate_adoption",)),
    "ridgeline-fleet-services": (86.0, "green", ("stable_usage",)),
    "northbend-haulage": (61.0, "yellow", ("moderate_adoption",)),
    "fairview-line-haul": (64.0, "green", ("stable_usage",)),
    "amberline-supply-chain": (70.0, "green", ("stable_usage",)),
    "brookstone-supply-chain": (67.0, "green", ("stable_usage",)),
    "cedarfield-industrial-supply": (72.0, "yellow", ("moderate_adoption",)),
    "deerpath-carriers": (76.0, "green", ("stable_usage",)),
    "elmwood-trucking": (78.0, "yellow", ("moderate_adoption",)),
    "foxhollow-field-services": (87.0, "yellow", ("moderate_adoption",)),
    "grovemont-delivery": (81.0, "green", ("stable_usage",)),
    "hillcrest-haulage": (89.0, "green", ("stable_usage",)),
    "ivywood-haulage": (82.0, "green", ("stable_usage",)),
    "juniper-trucking": (66.0, "green", ("stable_usage",)),
    "kingsford-delivery": (65.0, "green", ("stable_usage",)),
    "lakeshore-warehousing": (80.0, "green", ("stable_usage",)),
    "millbrook-trucking": (72.0, "yellow", ("moderate_adoption",)),
    "northgate-delivery": (62.0, "yellow", ("moderate_adoption",)),
    "oakridge-carriers": (81.0, "green", ("stable_usage",)),
    "pinebluff-supply-chain": (84.0, "green", ("stable_usage",)),
    "quarrymill-fleet-ops": (69.0, "yellow", ("moderate_adoption",)),
    "redstone-transport-co": (80.0, "green", ("stable_usage",)),
    "silverlake-haulage": (63.0, "green", ("stable_usage",)),
    "thornwood-fleet-services": (77.0, "green", ("stable_usage",)),
    "underhill-fleet-ops": (82.0, "yellow", ("moderate_adoption",)),
    "valleyfield-field-services": (70.0, "yellow", ("moderate_adoption",)),
    "westbrook-logistics": (69.0, "green", ("stable_usage",)),
    "yellowpine-fleet-services": (71.0, "yellow", ("moderate_adoption",)),
    "ashford-haulage": (86.0, "yellow", ("moderate_adoption",)),
    "birchwood-line-haul": (70.0, "yellow", ("moderate_adoption",)),
    "claybourne-transport-co": (66.0, "green", ("stable_usage",)),
    "dunmore-transport-co": (62.0, "yellow", ("moderate_adoption",)),
    "eastfield-freight": (84.0, "yellow", ("moderate_adoption",)),
    "farrow-fleet-ops": (88.0, "green", ("stable_usage",)),
    "glenbrook-distribution": (67.0, "yellow", ("moderate_adoption",)),
    "harlow-warehousing": (77.0, "yellow", ("moderate_adoption",)),
    "innisfree-logistics": (72.0, "yellow", ("moderate_adoption",)),
    "kestrel-logistics": (71.0, "green", ("stable_usage",)),
    "longview-delivery": (87.0, "green", ("stable_usage",)),
    "marrow-trucking": (77.0, "green", ("stable_usage",)),
    "newland-fleet-ops": (80.0, "yellow", ("moderate_adoption",)),
    "overlook-haulage": (80.0, "green", ("stable_usage",)),
    "parkview-fleet-services": (70.0, "yellow", ("moderate_adoption",)),
    "rockford-line-haul": (67.0, "green", ("stable_usage",)),
    "sandhill-distribution": (85.0, "green", ("stable_usage",)),
    "timberline2-fleet-ops": (76.0, "yellow", ("moderate_adoption",)),
    "vantage-line-haul": (89.0, "green", ("stable_usage",)),
    "wolfden-warehousing": (71.0, "green", ("stable_usage",)),
    "ashgate-industrial-supply": (78.0, "yellow", ("moderate_adoption",)),
    "bramblewood-fleet-ops": (75.0, "green", ("stable_usage",)),
    "copperfield2-carriers": (72.0, "green", ("stable_usage",)),
    "duskwood-transport-co": (82.0, "green", ("stable_usage",)),
    "evergreen-warehousing": (79.0, "green", ("stable_usage",)),
    "fallcreek-transport-co": (87.0, "green", ("stable_usage",)),
    "greystone-haulage": (65.0, "green", ("stable_usage",)),
    "hawksmoor-warehousing": (73.0, "yellow", ("moderate_adoption",)),
    "ironbark-fleet-ops": (87.0, "green", ("stable_usage",)),
    "larkspur-transport-co": (60.0, "green", ("stable_usage",)),
    "marshfield-supply-chain": (86.0, "green", ("stable_usage",)),
    "nightingale-industrial-supply": (89.0, "green", ("stable_usage",)),
    "ostervale-distribution": (79.0, "green", ("stable_usage",)),
    "pathfinder-freight": (68.0, "green", ("stable_usage",)),
    "quailridge-line-haul": (64.0, "green", ("stable_usage",)),
    "ravenswood-logistics": (65.0, "green", ("stable_usage",)),
    "stonegate-field-services": (79.0, "green", ("stable_usage",)),
    "truewind-distribution": (70.0, "green", ("stable_usage",)),
    "underpass-transport-co": (71.0, "green", ("stable_usage",)),
    "vernonhall-delivery": (73.0, "green", ("stable_usage",)),
    "wrenfield-carriers": (69.0, "green", ("stable_usage",)),
    "yarrow-industrial-supply": (83.0, "green", ("stable_usage",)),
    "ashland-transport-co": (61.0, "green", ("stable_usage",)),
    "belltower-supply-chain": (77.0, "yellow", ("moderate_adoption",)),
    "crestwood2-field-services": (77.0, "green", ("stable_usage",)),
    "driftwood2-haulage": (87.0, "green", ("stable_usage",)),
    "emberfield-delivery": (75.0, "green", ("stable_usage",)),
    "frostmoor-supply-chain": (76.0, "green", ("stable_usage",)),
    "graywolf-warehousing": (79.0, "green", ("stable_usage",)),
    "hartland-fleet-services": (81.0, "green", ("stable_usage",)),
    "ivorygate-freight": (81.0, "green", ("stable_usage",)),
    "juniperfield-logistics": (72.0, "green", ("stable_usage",)),
    "knollwood-transport-co": (61.0, "green", ("stable_usage",)),
    "lonepine-supply-chain": (73.0, "green", ("stable_usage",)),
    "meadowlark-field-services": (84.0, "yellow", ("moderate_adoption",)),
    "nightfall-warehousing": (85.0, "green", ("stable_usage",)),
    "oldstone-industrial-supply": (61.0, "green", ("stable_usage",)),
    "poplarcreek-trucking": (71.0, "green", ("stable_usage",)),
    "quietbrook-warehousing": (67.0, "green", ("stable_usage",)),
    "rimrock-trucking": (86.0, "green", ("stable_usage",)),
    "sagewood-fleet-ops": (78.0, "green", ("stable_usage",)),
    "trailrock-trucking": (64.0, "yellow", ("moderate_adoption",)),
    "umberfield-industrial-supply": (74.0, "yellow", ("moderate_adoption",)),
    "vinecrest-freight": (84.0, "green", ("stable_usage",)),
    "watermill-trucking": (62.0, "yellow", ("moderate_adoption",)),
    "yewbrook-field-services": (75.0, "green", ("stable_usage",)),
    "amberfield-fleet-ops": (64.0, "green", ("stable_usage",)),
    "boulderfield-fleet-services": (80.0, "yellow", ("moderate_adoption",)),
    "clearcreek2-industrial-supply": (76.0, "green", ("stable_usage",)),
    "duncehall-haulage": (65.0, "yellow", ("moderate_adoption",)),
    "elderwood-trucking": (68.0, "yellow", ("moderate_adoption",)),
    "foxglove-delivery": (68.0, "green", ("stable_usage",)),
    "granitehill-distribution": (73.0, "green", ("stable_usage",)),
    "hollowbrook-distribution": (64.0, "yellow", ("moderate_adoption",)),
    "ironwood2-line-haul": (88.0, "yellow", ("moderate_adoption",)),
    "jasperfield-logistics": (78.0, "yellow", ("moderate_adoption",)),
    "kettlecreek-distribution": (89.0, "yellow", ("moderate_adoption",)),
    "lindenfield-supply-chain": (63.0, "green", ("stable_usage",)),
    "mossgate-logistics": (84.0, "green", ("stable_usage",)),
    "northwind-distribution": (83.0, "yellow", ("moderate_adoption",)),
    "orchardview-industrial-supply": (65.0, "yellow", ("moderate_adoption",)),
    "palewood-field-services": (76.0, "yellow", ("moderate_adoption",)),
    "quarrycreek-haulage": (85.0, "green", ("stable_usage",)),
    "roughcut-freight": (72.0, "green", ("stable_usage",)),
    "stillwater2-freight": (88.0, "yellow", ("moderate_adoption",)),
    "thistledown-field-services": (86.0, "green", ("stable_usage",)),
    "uplands-distribution": (65.0, "green", ("stable_usage",)),
    "verdantfield-logistics": (83.0, "green", ("stable_usage",)),
    "whitfield-transport-co": (82.0, "yellow", ("moderate_adoption",)),
    "yarrowfield-delivery": (84.0, "green", ("stable_usage",)),
    "ashwell-supply-chain": (89.0, "green", ("stable_usage",)),
    "bramblecreek-line-haul": (86.0, "yellow", ("moderate_adoption",)),
    "cinderfield-delivery": (67.0, "green", ("stable_usage",)),
    "deepwater-haulage": (78.0, "yellow", ("moderate_adoption",)),
    "everfield-transport-co": (72.0, "green", ("stable_usage",)),
    "flintridge-field-services": (61.0, "green", ("stable_usage",)),
    "goldenfield-trucking": (74.0, "green", ("stable_usage",)),
    "hazelwood-transport-co": (67.0, "yellow", ("moderate_adoption",)),
    "ironhollow-line-haul": (76.0, "green", ("stable_usage",)),
    "junipergate-line-haul": (83.0, "yellow", ("moderate_adoption",)),
    "kirkfield-line-haul": (62.0, "green", ("stable_usage",)),
    "lowcreek-delivery": (84.0, "yellow", ("moderate_adoption",)),
    "mistvale-trucking": (80.0, "yellow", ("moderate_adoption",)),
    "netherfield-industrial-supply": (89.0, "green", ("stable_usage",)),
    "oakhollow-industrial-supply": (75.0, "yellow", ("moderate_adoption",)),
    "plainfield2-transport-co": (70.0, "green", ("stable_usage",)),
    "quarrystone2-warehousing": (77.0, "green", ("stable_usage",)),
    "redcreek-distribution": (89.0, "green", ("stable_usage",)),
    "slatefield-transport-co": (75.0, "green", ("stable_usage",)),
    "timbergate-transport-co": (82.0, "yellow", ("moderate_adoption",)),
    "uppercreek-logistics": (89.0, "green", ("stable_usage",)),
    "vandermill-haulage": (63.0, "green", ("stable_usage",)),
    "woodbine-transport-co": (83.0, "green", ("stable_usage",)),
    "yorkfield-industrial-supply": (78.0, "green", ("stable_usage",)),
    "ironclad-logistics": (85.0, "green", ("stable_usage",)),
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
    "ironclad-freight": (55, 68, 71, 101, 0.7, ()),
    "sterling-fleet-services": (60, 76, 47, 69, 0.68, ()),
    "cobalt-fleet-ops": (33, 49, 87, 112, 0.78, ()),
    "ridgeline-fleet-services": (41, 61, 68, 80, 0.85, ()),
    "northbend-haulage": (26, 40, 54, 73, 0.74, ()),
    "fairview-line-haul": (30, 47, 81, 110, 0.74, ()),
    "amberline-supply-chain": (56, 77, 38, 60, 0.63, ()),
    "brookstone-supply-chain": (12, 14, 24, 32, 0.75, ()),
    "cedarfield-industrial-supply": (18, 25, 27, 41, 0.66, ()),
    "deerpath-carriers": (11, 13, 20, 27, 0.74, ()),
    "elmwood-trucking": (17, 25, 16, 23, 0.7, ()),
    "foxhollow-field-services": (15, 18, 24, 32, 0.75, ()),
    "grovemont-delivery": (17, 24, 22, 32, 0.69, ()),
    "hillcrest-haulage": (13, 16, 13, 22, 0.59, ()),
    "ivywood-haulage": (24, 29, 26, 41, 0.63, ()),
    "juniper-trucking": (11, 15, 12, 15, 0.8, ()),
    "kingsford-delivery": (19, 28, 31, 40, 0.78, ()),
    "lakeshore-warehousing": (15, 19, 16, 23, 0.7, ()),
    "millbrook-trucking": (17, 29, 21, 31, 0.68, ()),
    "northgate-delivery": (19, 23, 19, 27, 0.7, ()),
    "oakridge-carriers": (15, 20, 12, 18, 0.67, ()),
    "pinebluff-supply-chain": (16, 21, 12, 17, 0.71, ()),
    "quarrymill-fleet-ops": (12, 14, 13, 20, 0.65, ()),
    "redstone-transport-co": (17, 23, 10, 17, 0.59, ()),
    "silverlake-haulage": (8, 14, 30, 38, 0.79, ()),
    "thornwood-fleet-services": (16, 20, 17, 24, 0.71, ()),
    "underhill-fleet-ops": (7, 11, 35, 43, 0.81, ()),
    "valleyfield-field-services": (17, 27, 26, 35, 0.74, ()),
    "westbrook-logistics": (17, 22, 22, 26, 0.85, ()),
    "yellowpine-fleet-services": (12, 20, 11, 16, 0.69, ()),
    "ashford-haulage": (16, 23, 34, 39, 0.87, ()),
    "birchwood-line-haul": (7, 11, 28, 37, 0.76, ()),
    "claybourne-transport-co": (9, 15, 27, 33, 0.82, ()),
    "dunmore-transport-co": (10, 15, 18, 25, 0.72, ()),
    "eastfield-freight": (16, 23, 33, 41, 0.8, ()),
    "farrow-fleet-ops": (1, 3, 2, 3, 0.67, ()),
    "glenbrook-distribution": (5, 8, 6, 10, 0.6, ()),
    "harlow-warehousing": (3, 6, 9, 12, 0.75, ()),
    "innisfree-logistics": (7, 9, 3, 5, 0.6, ()),
    "kestrel-logistics": (4, 6, 2, 4, 0.5, ()),
    "longview-delivery": (6, 8, 7, 10, 0.7, ()),
    "marrow-trucking": (6, 8, 10, 14, 0.71, ()),
    "newland-fleet-ops": (3, 5, 7, 9, 0.78, ()),
    "overlook-haulage": (3, 5, 5, 9, 0.56, ()),
    "parkview-fleet-services": (3, 5, 5, 9, 0.56, ()),
    "rockford-line-haul": (1, 2, 3, 4, 0.75, ()),
    "sandhill-distribution": (6, 8, 8, 14, 0.57, ()),
    "timberline2-fleet-ops": (4, 7, 2, 3, 0.67, ()),
    "vantage-line-haul": (1, 2, 2, 4, 0.5, ()),
    "wolfden-warehousing": (2, 4, 7, 10, 0.7, ()),
    "ashgate-industrial-supply": (7, 9, 8, 13, 0.62, ()),
    "bramblewood-fleet-ops": (3, 4, 8, 10, 0.8, ()),
    "copperfield2-carriers": (3, 5, 5, 9, 0.56, ()),
    "duskwood-transport-co": (4, 7, 2, 3, 0.67, ()),
    "evergreen-warehousing": (4, 8, 11, 14, 0.79, ()),
    "fallcreek-transport-co": (2, 4, 11, 14, 0.79, ()),
    "greystone-haulage": (4, 6, 7, 8, 0.88, ()),
    "hawksmoor-warehousing": (6, 8, 7, 10, 0.7, ()),
    "ironbark-fleet-ops": (2, 4, 11, 14, 0.79, ()),
    "larkspur-transport-co": (2, 3, 4, 7, 0.57, ()),
    "marshfield-supply-chain": (6, 9, 4, 5, 0.8, ()),
    "nightingale-industrial-supply": (7, 8, 10, 14, 0.71, ()),
    "ostervale-distribution": (2, 4, 4, 6, 0.67, ()),
    "pathfinder-freight": (5, 9, 9, 13, 0.69, ()),
    "quailridge-line-haul": (4, 5, 3, 5, 0.6, ()),
    "ravenswood-logistics": (3, 4, 8, 10, 0.8, ()),
    "stonegate-field-services": (4, 6, 8, 12, 0.67, ()),
    "truewind-distribution": (7, 9, 3, 5, 0.6, ()),
    "underpass-transport-co": (2, 4, 4, 6, 0.67, ()),
    "vernonhall-delivery": (2, 4, 7, 10, 0.7, ()),
    "wrenfield-carriers": (5, 8, 11, 14, 0.79, ()),
    "yarrow-industrial-supply": (6, 8, 10, 14, 0.71, ()),
    "ashland-transport-co": (4, 6, 10, 12, 0.83, ()),
    "belltower-supply-chain": (4, 6, 6, 8, 0.75, ()),
    "crestwood2-field-services": (5, 6, 5, 8, 0.62, ()),
    "driftwood2-haulage": (5, 8, 3, 6, 0.5, ()),
    "emberfield-delivery": (4, 6, 5, 8, 0.62, ()),
    "frostmoor-supply-chain": (6, 9, 4, 5, 0.8, ()),
    "graywolf-warehousing": (1, 2, 8, 12, 0.67, ()),
    "hartland-fleet-services": (1, 2, 8, 12, 0.67, ()),
    "ivorygate-freight": (5, 6, 6, 8, 0.75, ()),
    "juniperfield-logistics": (2, 3, 4, 7, 0.57, ()),
    "knollwood-transport-co": (6, 8, 4, 6, 0.67, ()),
    "lonepine-supply-chain": (6, 8, 6, 10, 0.6, ()),
    "meadowlark-field-services": (4, 5, 9, 13, 0.69, ()),
    "nightfall-warehousing": (4, 8, 11, 14, 0.79, ()),
    "oldstone-industrial-supply": (5, 6, 6, 8, 0.75, ()),
    "poplarcreek-trucking": (5, 8, 7, 10, 0.7, ()),
    "quietbrook-warehousing": (5, 6, 9, 12, 0.75, ()),
    "rimrock-trucking": (4, 5, 9, 13, 0.69, ()),
    "sagewood-fleet-ops": (3, 5, 7, 9, 0.78, ()),
    "trailrock-trucking": (3, 5, 4, 5, 0.8, ()),
    "umberfield-industrial-supply": (6, 9, 7, 9, 0.78, ()),
    "vinecrest-freight": (1, 3, 2, 3, 0.67, ()),
    "watermill-trucking": (4, 5, 9, 13, 0.69, ()),
    "yewbrook-field-services": (3, 4, 3, 6, 0.5, ()),
    "amberfield-fleet-ops": (7, 9, 10, 13, 0.77, ()),
    "boulderfield-fleet-services": (1, 3, 5, 7, 0.71, ()),
    "clearcreek2-industrial-supply": (7, 9, 8, 13, 0.62, ()),
    "duncehall-haulage": (3, 6, 6, 8, 0.75, ()),
    "elderwood-trucking": (7, 9, 6, 9, 0.67, ()),
    "foxglove-delivery": (2, 3, 6, 11, 0.55, ()),
    "granitehill-distribution": (5, 6, 7, 12, 0.58, ()),
    "hollowbrook-distribution": (1, 3, 4, 7, 0.57, ()),
    "ironwood2-line-haul": (5, 7, 7, 11, 0.64, ()),
    "jasperfield-logistics": (5, 7, 8, 11, 0.73, ()),
    "kettlecreek-distribution": (1, 2, 8, 12, 0.67, ()),
    "lindenfield-supply-chain": (1, 2, 6, 8, 0.75, ()),
    "mossgate-logistics": (2, 3, 2, 3, 0.67, ()),
    "northwind-distribution": (1, 2, 2, 4, 0.5, ()),
    "orchardview-industrial-supply": (6, 8, 4, 6, 0.67, ()),
    "palewood-field-services": (6, 9, 4, 5, 0.8, ()),
    "quarrycreek-haulage": (3, 6, 3, 4, 0.75, ()),
    "roughcut-freight": (3, 5, 8, 13, 0.62, ()),
    "stillwater2-freight": (7, 9, 6, 9, 0.67, ()),
    "thistledown-field-services": (6, 9, 7, 9, 0.78, ()),
    "uplands-distribution": (1, 2, 10, 12, 0.83, ()),
    "verdantfield-logistics": (1, 2, 6, 8, 0.75, ()),
    "whitfield-transport-co": (1, 3, 5, 7, 0.71, ()),
    "yarrowfield-delivery": (2, 3, 4, 7, 0.57, ()),
    "ashwell-supply-chain": (5, 8, 8, 14, 0.57, ()),
    "bramblecreek-line-haul": (5, 7, 4, 7, 0.57, ()),
    "cinderfield-delivery": (1, 2, 3, 4, 0.75, ()),
    "deepwater-haulage": (2, 3, 2, 3, 0.67, ()),
    "everfield-transport-co": (7, 9, 5, 9, 0.56, ()),
    "flintridge-field-services": (6, 8, 10, 14, 0.71, ()),
    "goldenfield-trucking": (2, 3, 7, 11, 0.64, ()),
    "hazelwood-transport-co": (6, 8, 7, 10, 0.7, ()),
    "ironhollow-line-haul": (4, 7, 9, 11, 0.82, ()),
    "junipergate-line-haul": (5, 8, 3, 6, 0.5, ()),
    "kirkfield-line-haul": (3, 5, 8, 13, 0.62, ()),
    "lowcreek-delivery": (4, 7, 5, 7, 0.71, ()),
    "mistvale-trucking": (4, 5, 9, 13, 0.69, ()),
    "netherfield-industrial-supply": (3, 4, 12, 14, 0.86, ()),
    "oakhollow-industrial-supply": (3, 4, 9, 14, 0.64, ()),
    "plainfield2-transport-co": (1, 3, 5, 7, 0.71, ()),
    "quarrystone2-warehousing": (5, 8, 8, 10, 0.8, ()),
    "redcreek-distribution": (2, 4, 9, 14, 0.64, ()),
    "slatefield-transport-co": (4, 6, 3, 4, 0.75, ()),
    "timbergate-transport-co": (4, 7, 5, 7, 0.71, ()),
    "uppercreek-logistics": (4, 6, 7, 12, 0.58, ()),
    "vandermill-haulage": (3, 6, 6, 8, 0.75, ()),
    "woodbine-transport-co": (6, 8, 4, 6, 0.67, ()),
    "yorkfield-industrial-supply": (2, 3, 7, 11, 0.64, ()),
    "ironclad-logistics": (4, 6, 7, 8, 0.88, ()),
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
    "ironclad-freight": [("Riley Brooks", "operations", "Operations Manager", "riley.brooks@ironclad-freight.example", True)],
    "sterling-fleet-services": [("Morgan Reyes", "operations", "Logistics Coordinator", "morgan.reyes@sterling-fleet-services.example", True)],
    "cobalt-fleet-ops": [("Sam Turner", "operations", "Operations Manager", "sam.turner@cobalt-fleet-ops.example", True)],
    "ridgeline-fleet-services": [("Alex Turner", "operations", "Dispatch Lead", "alex.turner@ridgeline-fleet-services.example", True)],
    "northbend-haulage": [("Jordan Cole", "operations", "Fleet Manager", "jordan.cole@northbend-haulage.example", True)],
    "fairview-line-haul": [("Alex Hayes", "operations", "Fleet Manager", "alex.hayes@fairview-line-haul.example", True)],
    "amberline-supply-chain": [("Casey Sharp", "operations", "Facilities Manager", "casey.sharp@amberline-supply-chain.example", True)],
    "brookstone-supply-chain": [("Jordan Doyle", "operations", "Fleet Manager", "jordan.doyle@brookstone-supply-chain.example", True)],
    "cedarfield-industrial-supply": [("Alex Foster", "operations", "Facilities Manager", "alex.foster@cedarfield-industrial-supply.example", True)],
    "deerpath-carriers": [("Alex Sharp", "operations", "Operations Manager", "alex.sharp@deerpath-carriers.example", True)],
    "elmwood-trucking": [("Sam Foster", "operations", "Dispatch Lead", "sam.foster@elmwood-trucking.example", True)],
    "foxhollow-field-services": [("Jamie Bennett", "operations", "Logistics Coordinator", "jamie.bennett@foxhollow-field-services.example", True)],
    "grovemont-delivery": [("Cameron Cole", "operations", "Operations Manager", "cameron.cole@grovemont-delivery.example", True)],
    "hillcrest-haulage": [("Morgan Cole", "operations", "Facilities Manager", "morgan.cole@hillcrest-haulage.example", True)],
    "ivywood-haulage": [("Taylor Hayes", "operations", "Fleet Manager", "taylor.hayes@ivywood-haulage.example", True)],
    "juniper-trucking": [("Taylor Ward", "operations", "Dispatch Lead", "taylor.ward@juniper-trucking.example", True)],
    "kingsford-delivery": [("Riley Reyes", "operations", "Dispatch Lead", "riley.reyes@kingsford-delivery.example", True)],
    "lakeshore-warehousing": [("Drew Ward", "operations", "Logistics Coordinator", "drew.ward@lakeshore-warehousing.example", True)],
    "millbrook-trucking": [("Taylor Turner", "operations", "Fleet Manager", "taylor.turner@millbrook-trucking.example", True)],
    "northgate-delivery": [("Taylor Turner", "operations", "Facilities Manager", "taylor.turner@northgate-delivery.example", True)],
    "oakridge-carriers": [("Jordan Cole", "operations", "Fleet Manager", "jordan.cole@oakridge-carriers.example", True)],
    "pinebluff-supply-chain": [("Taylor Ward", "operations", "Logistics Coordinator", "taylor.ward@pinebluff-supply-chain.example", True)],
    "quarrymill-fleet-ops": [("Jamie Bennett", "operations", "Operations Manager", "jamie.bennett@quarrymill-fleet-ops.example", True)],
    "redstone-transport-co": [("Taylor Sharp", "operations", "Facilities Manager", "taylor.sharp@redstone-transport-co.example", True)],
    "silverlake-haulage": [("Morgan Brooks", "operations", "Fleet Manager", "morgan.brooks@silverlake-haulage.example", True)],
    "thornwood-fleet-services": [("Jordan Bennett", "operations", "Operations Manager", "jordan.bennett@thornwood-fleet-services.example", True)],
    "underhill-fleet-ops": [("Alex Turner", "operations", "Dispatch Lead", "alex.turner@underhill-fleet-ops.example", True)],
    "valleyfield-field-services": [("Casey Sharp", "operations", "Dispatch Lead", "casey.sharp@valleyfield-field-services.example", True)],
    "westbrook-logistics": [("Jamie Reyes", "operations", "Operations Manager", "jamie.reyes@westbrook-logistics.example", True)],
    "yellowpine-fleet-services": [("Morgan Brooks", "operations", "Facilities Manager", "morgan.brooks@yellowpine-fleet-services.example", True)],
    "ashford-haulage": [("Taylor Foster", "operations", "Logistics Coordinator", "taylor.foster@ashford-haulage.example", True)],
    "birchwood-line-haul": [("Drew Sharp", "operations", "Operations Manager", "drew.sharp@birchwood-line-haul.example", True)],
    "claybourne-transport-co": [("Casey Ward", "operations", "Facilities Manager", "casey.ward@claybourne-transport-co.example", True)],
    "dunmore-transport-co": [("Casey Sharp", "operations", "Dispatch Lead", "casey.sharp@dunmore-transport-co.example", True)],
    "eastfield-freight": [("Alex Hayes", "operations", "Logistics Coordinator", "alex.hayes@eastfield-freight.example", True)],
    "farrow-fleet-ops": [("Alex Hayes", "operations", "Dispatch Lead", "alex.hayes@farrow-fleet-ops.example", True)],
    "glenbrook-distribution": [("Cameron Doyle", "operations", "Logistics Coordinator", "cameron.doyle@glenbrook-distribution.example", True)],
    "harlow-warehousing": [("Cameron Doyle", "operations", "Facilities Manager", "cameron.doyle@harlow-warehousing.example", True)],
    "innisfree-logistics": [("Drew Sharp", "operations", "Facilities Manager", "drew.sharp@innisfree-logistics.example", True)],
    "kestrel-logistics": [("Jamie Brooks", "operations", "Facilities Manager", "jamie.brooks@kestrel-logistics.example", True)],
    "longview-delivery": [("Cameron Brooks", "operations", "Operations Manager", "cameron.brooks@longview-delivery.example", True)],
    "marrow-trucking": [("Cameron Brooks", "operations", "Logistics Coordinator", "cameron.brooks@marrow-trucking.example", True)],
    "newland-fleet-ops": [("Casey Sharp", "operations", "Operations Manager", "casey.sharp@newland-fleet-ops.example", True)],
    "overlook-haulage": [("Alex Turner", "operations", "Dispatch Lead", "alex.turner@overlook-haulage.example", True)],
    "parkview-fleet-services": [("Alex Turner", "operations", "Facilities Manager", "alex.turner@parkview-fleet-services.example", True)],
    "rockford-line-haul": [("Riley Cole", "operations", "Operations Manager", "riley.cole@rockford-line-haul.example", True)],
    "sandhill-distribution": [("Jordan Reyes", "operations", "Operations Manager", "jordan.reyes@sandhill-distribution.example", True)],
    "timberline2-fleet-ops": [("Casey Sharp", "operations", "Fleet Manager", "casey.sharp@timberline2-fleet-ops.example", True)],
    "vantage-line-haul": [("Jordan Brooks", "operations", "Operations Manager", "jordan.brooks@vantage-line-haul.example", True)],
    "wolfden-warehousing": [("Morgan Bennett", "operations", "Logistics Coordinator", "morgan.bennett@wolfden-warehousing.example", True)],
    "ashgate-industrial-supply": [("Drew Hayes", "operations", "Logistics Coordinator", "drew.hayes@ashgate-industrial-supply.example", True)],
    "bramblewood-fleet-ops": [("Jordan Reyes", "operations", "Facilities Manager", "jordan.reyes@bramblewood-fleet-ops.example", True)],
    "copperfield2-carriers": [("Alex Foster", "operations", "Fleet Manager", "alex.foster@copperfield2-carriers.example", True)],
    "duskwood-transport-co": [("Drew Sharp", "operations", "Facilities Manager", "drew.sharp@duskwood-transport-co.example", True)],
    "evergreen-warehousing": [("Riley Doyle", "operations", "Operations Manager", "riley.doyle@evergreen-warehousing.example", True)],
    "fallcreek-transport-co": [("Riley Bennett", "operations", "Facilities Manager", "riley.bennett@fallcreek-transport-co.example", True)],
    "greystone-haulage": [("Jordan Cole", "operations", "Operations Manager", "jordan.cole@greystone-haulage.example", True)],
    "hawksmoor-warehousing": [("Jamie Doyle", "operations", "Operations Manager", "jamie.doyle@hawksmoor-warehousing.example", True)],
    "ironbark-fleet-ops": [("Morgan Doyle", "operations", "Fleet Manager", "morgan.doyle@ironbark-fleet-ops.example", True)],
    "larkspur-transport-co": [("Drew Ward", "operations", "Dispatch Lead", "drew.ward@larkspur-transport-co.example", True)],
    "marshfield-supply-chain": [("Drew Ward", "operations", "Facilities Manager", "drew.ward@marshfield-supply-chain.example", True)],
    "nightingale-industrial-supply": [("Riley Cole", "operations", "Facilities Manager", "riley.cole@nightingale-industrial-supply.example", True)],
    "ostervale-distribution": [("Riley Doyle", "operations", "Facilities Manager", "riley.doyle@ostervale-distribution.example", True)],
    "pathfinder-freight": [("Sam Foster", "operations", "Facilities Manager", "sam.foster@pathfinder-freight.example", True)],
    "quailridge-line-haul": [("Drew Sharp", "operations", "Fleet Manager", "drew.sharp@quailridge-line-haul.example", True)],
    "ravenswood-logistics": [("Riley Doyle", "operations", "Logistics Coordinator", "riley.doyle@ravenswood-logistics.example", True)],
    "stonegate-field-services": [("Jamie Brooks", "operations", "Operations Manager", "jamie.brooks@stonegate-field-services.example", True)],
    "truewind-distribution": [("Drew Sharp", "operations", "Logistics Coordinator", "drew.sharp@truewind-distribution.example", True)],
    "underpass-transport-co": [("Morgan Brooks", "operations", "Facilities Manager", "morgan.brooks@underpass-transport-co.example", True)],
    "vernonhall-delivery": [("Riley Reyes", "operations", "Fleet Manager", "riley.reyes@vernonhall-delivery.example", True)],
    "wrenfield-carriers": [("Cameron Brooks", "operations", "Logistics Coordinator", "cameron.brooks@wrenfield-carriers.example", True)],
    "yarrow-industrial-supply": [("Morgan Doyle", "operations", "Fleet Manager", "morgan.doyle@yarrow-industrial-supply.example", True)],
    "ashland-transport-co": [("Morgan Reyes", "operations", "Fleet Manager", "morgan.reyes@ashland-transport-co.example", True)],
    "belltower-supply-chain": [("Jamie Doyle", "operations", "Logistics Coordinator", "jamie.doyle@belltower-supply-chain.example", True)],
    "crestwood2-field-services": [("Cameron Cole", "operations", "Logistics Coordinator", "cameron.cole@crestwood2-field-services.example", True)],
    "driftwood2-haulage": [("Riley Doyle", "operations", "Logistics Coordinator", "riley.doyle@driftwood2-haulage.example", True)],
    "emberfield-delivery": [("Riley Cole", "operations", "Operations Manager", "riley.cole@emberfield-delivery.example", True)],
    "frostmoor-supply-chain": [("Casey Turner", "operations", "Dispatch Lead", "casey.turner@frostmoor-supply-chain.example", True)],
    "graywolf-warehousing": [("Morgan Reyes", "operations", "Operations Manager", "morgan.reyes@graywolf-warehousing.example", True)],
    "hartland-fleet-services": [("Jamie Reyes", "operations", "Logistics Coordinator", "jamie.reyes@hartland-fleet-services.example", True)],
    "ivorygate-freight": [("Jordan Doyle", "operations", "Operations Manager", "jordan.doyle@ivorygate-freight.example", True)],
    "juniperfield-logistics": [("Taylor Ward", "operations", "Fleet Manager", "taylor.ward@juniperfield-logistics.example", True)],
    "knollwood-transport-co": [("Jordan Reyes", "operations", "Dispatch Lead", "jordan.reyes@knollwood-transport-co.example", True)],
    "lonepine-supply-chain": [("Jordan Bennett", "operations", "Dispatch Lead", "jordan.bennett@lonepine-supply-chain.example", True)],
    "meadowlark-field-services": [("Casey Sharp", "operations", "Dispatch Lead", "casey.sharp@meadowlark-field-services.example", True)],
    "nightfall-warehousing": [("Cameron Bennett", "operations", "Facilities Manager", "cameron.bennett@nightfall-warehousing.example", True)],
    "oldstone-industrial-supply": [("Morgan Doyle", "operations", "Fleet Manager", "morgan.doyle@oldstone-industrial-supply.example", True)],
    "poplarcreek-trucking": [("Morgan Doyle", "operations", "Dispatch Lead", "morgan.doyle@poplarcreek-trucking.example", True)],
    "quietbrook-warehousing": [("Jordan Bennett", "operations", "Logistics Coordinator", "jordan.bennett@quietbrook-warehousing.example", True)],
    "rimrock-trucking": [("Sam Turner", "operations", "Logistics Coordinator", "sam.turner@rimrock-trucking.example", True)],
    "sagewood-fleet-ops": [("Taylor Hayes", "operations", "Operations Manager", "taylor.hayes@sagewood-fleet-ops.example", True)],
    "trailrock-trucking": [("Casey Hayes", "operations", "Dispatch Lead", "casey.hayes@trailrock-trucking.example", True)],
    "umberfield-industrial-supply": [("Casey Hayes", "operations", "Logistics Coordinator", "casey.hayes@umberfield-industrial-supply.example", True)],
    "vinecrest-freight": [("Casey Hayes", "operations", "Operations Manager", "casey.hayes@vinecrest-freight.example", True)],
    "watermill-trucking": [("Casey Turner", "operations", "Logistics Coordinator", "casey.turner@watermill-trucking.example", True)],
    "yewbrook-field-services": [("Jamie Reyes", "operations", "Operations Manager", "jamie.reyes@yewbrook-field-services.example", True)],
    "amberfield-fleet-ops": [("Alex Ward", "operations", "Fleet Manager", "alex.ward@amberfield-fleet-ops.example", True)],
    "boulderfield-fleet-services": [("Casey Hayes", "operations", "Operations Manager", "casey.hayes@boulderfield-fleet-services.example", True)],
    "clearcreek2-industrial-supply": [("Casey Hayes", "operations", "Facilities Manager", "casey.hayes@clearcreek2-industrial-supply.example", True)],
    "duncehall-haulage": [("Riley Doyle", "operations", "Dispatch Lead", "riley.doyle@duncehall-haulage.example", True)],
    "elderwood-trucking": [("Alex Turner", "operations", "Operations Manager", "alex.turner@elderwood-trucking.example", True)],
    "foxglove-delivery": [("Alex Hayes", "operations", "Dispatch Lead", "alex.hayes@foxglove-delivery.example", True)],
    "granitehill-distribution": [("Jamie Reyes", "operations", "Dispatch Lead", "jamie.reyes@granitehill-distribution.example", True)],
    "hollowbrook-distribution": [("Drew Foster", "operations", "Dispatch Lead", "drew.foster@hollowbrook-distribution.example", True)],
    "ironwood2-line-haul": [("Taylor Turner", "operations", "Fleet Manager", "taylor.turner@ironwood2-line-haul.example", True)],
    "jasperfield-logistics": [("Alex Ward", "operations", "Fleet Manager", "alex.ward@jasperfield-logistics.example", True)],
    "kettlecreek-distribution": [("Riley Doyle", "operations", "Facilities Manager", "riley.doyle@kettlecreek-distribution.example", True)],
    "lindenfield-supply-chain": [("Jamie Brooks", "operations", "Logistics Coordinator", "jamie.brooks@lindenfield-supply-chain.example", True)],
    "mossgate-logistics": [("Taylor Sharp", "operations", "Operations Manager", "taylor.sharp@mossgate-logistics.example", True)],
    "northwind-distribution": [("Riley Doyle", "operations", "Facilities Manager", "riley.doyle@northwind-distribution.example", True)],
    "orchardview-industrial-supply": [("Riley Cole", "operations", "Operations Manager", "riley.cole@orchardview-industrial-supply.example", True)],
    "palewood-field-services": [("Casey Ward", "operations", "Fleet Manager", "casey.ward@palewood-field-services.example", True)],
    "quarrycreek-haulage": [("Riley Brooks", "operations", "Operations Manager", "riley.brooks@quarrycreek-haulage.example", True)],
    "roughcut-freight": [("Sam Ward", "operations", "Fleet Manager", "sam.ward@roughcut-freight.example", True)],
    "stillwater2-freight": [("Alex Turner", "operations", "Facilities Manager", "alex.turner@stillwater2-freight.example", True)],
    "thistledown-field-services": [("Drew Hayes", "operations", "Fleet Manager", "drew.hayes@thistledown-field-services.example", True)],
    "uplands-distribution": [("Morgan Doyle", "operations", "Facilities Manager", "morgan.doyle@uplands-distribution.example", True)],
    "verdantfield-logistics": [("Jordan Cole", "operations", "Dispatch Lead", "jordan.cole@verdantfield-logistics.example", True)],
    "whitfield-transport-co": [("Drew Foster", "operations", "Fleet Manager", "drew.foster@whitfield-transport-co.example", True)],
    "yarrowfield-delivery": [("Taylor Foster", "operations", "Operations Manager", "taylor.foster@yarrowfield-delivery.example", True)],
    "ashwell-supply-chain": [("Morgan Doyle", "operations", "Fleet Manager", "morgan.doyle@ashwell-supply-chain.example", True)],
    "bramblecreek-line-haul": [("Sam Foster", "operations", "Dispatch Lead", "sam.foster@bramblecreek-line-haul.example", True)],
    "cinderfield-delivery": [("Cameron Bennett", "operations", "Operations Manager", "cameron.bennett@cinderfield-delivery.example", True)],
    "deepwater-haulage": [("Sam Ward", "operations", "Facilities Manager", "sam.ward@deepwater-haulage.example", True)],
    "everfield-transport-co": [("Alex Turner", "operations", "Fleet Manager", "alex.turner@everfield-transport-co.example", True)],
    "flintridge-field-services": [("Riley Reyes", "operations", "Facilities Manager", "riley.reyes@flintridge-field-services.example", True)],
    "goldenfield-trucking": [("Drew Hayes", "operations", "Fleet Manager", "drew.hayes@goldenfield-trucking.example", True)],
    "hazelwood-transport-co": [("Jamie Doyle", "operations", "Dispatch Lead", "jamie.doyle@hazelwood-transport-co.example", True)],
    "ironhollow-line-haul": [("Drew Sharp", "operations", "Fleet Manager", "drew.sharp@ironhollow-line-haul.example", True)],
    "junipergate-line-haul": [("Cameron Bennett", "operations", "Dispatch Lead", "cameron.bennett@junipergate-line-haul.example", True)],
    "kirkfield-line-haul": [("Taylor Ward", "operations", "Operations Manager", "taylor.ward@kirkfield-line-haul.example", True)],
    "lowcreek-delivery": [("Taylor Turner", "operations", "Logistics Coordinator", "taylor.turner@lowcreek-delivery.example", True)],
    "mistvale-trucking": [("Drew Turner", "operations", "Fleet Manager", "drew.turner@mistvale-trucking.example", True)],
    "netherfield-industrial-supply": [("Riley Bennett", "operations", "Logistics Coordinator", "riley.bennett@netherfield-industrial-supply.example", True)],
    "oakhollow-industrial-supply": [("Cameron Reyes", "operations", "Dispatch Lead", "cameron.reyes@oakhollow-industrial-supply.example", True)],
    "plainfield2-transport-co": [("Casey Hayes", "operations", "Operations Manager", "casey.hayes@plainfield2-transport-co.example", True)],
    "quarrystone2-warehousing": [("Morgan Brooks", "operations", "Operations Manager", "morgan.brooks@quarrystone2-warehousing.example", True)],
    "redcreek-distribution": [("Morgan Brooks", "operations", "Logistics Coordinator", "morgan.brooks@redcreek-distribution.example", True)],
    "slatefield-transport-co": [("Jordan Reyes", "operations", "Dispatch Lead", "jordan.reyes@slatefield-transport-co.example", True)],
    "timbergate-transport-co": [("Taylor Turner", "operations", "Operations Manager", "taylor.turner@timbergate-transport-co.example", True)],
    "uppercreek-logistics": [("Jamie Doyle", "operations", "Operations Manager", "jamie.doyle@uppercreek-logistics.example", True)],
    "vandermill-haulage": [("Cameron Cole", "operations", "Facilities Manager", "cameron.cole@vandermill-haulage.example", True)],
    "woodbine-transport-co": [("Jordan Bennett", "operations", "Fleet Manager", "jordan.bennett@woodbine-transport-co.example", True)],
    "yorkfield-industrial-supply": [("Sam Turner", "operations", "Operations Manager", "sam.turner@yorkfield-industrial-supply.example", True)],
    "ironclad-logistics": [("Jordan Cole", "operations", "Logistics Coordinator", "jordan.cole@ironclad-logistics.example", True)],
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
    "ironclad-freight": [("core_telematics", 77, "assets"), ("route_optimization", 77, "assets"), ("advanced_reporting", 77, "assets"), ("fuel_analytics", 77, "assets"), ("driver_coaching", 77, "assets")],
    "sterling-fleet-services": [("core_telematics", 125, "assets"), ("route_optimization", 125, "assets"), ("advanced_reporting", 125, "assets"), ("fuel_analytics", 125, "assets"), ("driver_coaching", 125, "assets")],
    "cobalt-fleet-ops": [("core_telematics", 88, "assets"), ("route_optimization", 88, "assets"), ("advanced_reporting", 88, "assets"), ("fuel_analytics", 88, "assets")],
    "ridgeline-fleet-services": [("core_telematics", 136, "assets"), ("route_optimization", 136, "assets"), ("advanced_reporting", 136, "assets"), ("fuel_analytics", 136, "assets")],
    "northbend-haulage": [("core_telematics", 157, "assets"), ("route_optimization", 157, "assets"), ("advanced_reporting", 157, "assets"), ("fuel_analytics", 157, "assets"), ("driver_coaching", 157, "assets")],
    "fairview-line-haul": [("core_telematics", 74, "assets"), ("route_optimization", 74, "assets"), ("advanced_reporting", 74, "assets"), ("fuel_analytics", 74, "assets")],
    "amberline-supply-chain": [("core_telematics", 84, "assets"), ("route_optimization", 84, "assets"), ("advanced_reporting", 84, "assets"), ("fuel_analytics", 84, "assets")],
    "brookstone-supply-chain": [("core_telematics", 18, "assets"), ("route_optimization", 18, "assets"), ("maintenance_alerts", 18, "assets")],
    "cedarfield-industrial-supply": [("core_telematics", 25, "assets"), ("route_optimization", 25, "assets")],
    "deerpath-carriers": [("core_telematics", 41, "assets"), ("route_optimization", 41, "assets")],
    "elmwood-trucking": [("core_telematics", 39, "assets"), ("route_optimization", 39, "assets")],
    "foxhollow-field-services": [("core_telematics", 18, "assets"), ("route_optimization", 18, "assets"), ("maintenance_alerts", 18, "assets")],
    "grovemont-delivery": [("core_telematics", 16, "assets"), ("route_optimization", 16, "assets"), ("maintenance_alerts", 16, "assets")],
    "hillcrest-haulage": [("core_telematics", 36, "assets"), ("route_optimization", 36, "assets"), ("maintenance_alerts", 36, "assets")],
    "ivywood-haulage": [("core_telematics", 27, "assets"), ("route_optimization", 27, "assets")],
    "juniper-trucking": [("core_telematics", 31, "assets"), ("route_optimization", 31, "assets")],
    "kingsford-delivery": [("core_telematics", 26, "assets"), ("route_optimization", 26, "assets"), ("maintenance_alerts", 26, "assets")],
    "lakeshore-warehousing": [("core_telematics", 37, "assets"), ("route_optimization", 37, "assets")],
    "millbrook-trucking": [("core_telematics", 17, "assets"), ("route_optimization", 17, "assets")],
    "northgate-delivery": [("core_telematics", 41, "assets"), ("route_optimization", 41, "assets")],
    "oakridge-carriers": [("core_telematics", 34, "assets"), ("route_optimization", 34, "assets"), ("maintenance_alerts", 34, "assets")],
    "pinebluff-supply-chain": [("core_telematics", 33, "assets"), ("route_optimization", 33, "assets")],
    "quarrymill-fleet-ops": [("core_telematics", 36, "assets"), ("route_optimization", 36, "assets"), ("maintenance_alerts", 36, "assets")],
    "redstone-transport-co": [("core_telematics", 33, "assets"), ("route_optimization", 33, "assets")],
    "silverlake-haulage": [("core_telematics", 24, "assets"), ("route_optimization", 24, "assets"), ("maintenance_alerts", 24, "assets")],
    "thornwood-fleet-services": [("core_telematics", 38, "assets"), ("route_optimization", 38, "assets"), ("maintenance_alerts", 38, "assets")],
    "underhill-fleet-ops": [("core_telematics", 27, "assets"), ("route_optimization", 27, "assets")],
    "valleyfield-field-services": [("core_telematics", 21, "assets"), ("route_optimization", 21, "assets")],
    "westbrook-logistics": [("core_telematics", 42, "assets"), ("route_optimization", 42, "assets"), ("maintenance_alerts", 42, "assets")],
    "yellowpine-fleet-services": [("core_telematics", 32, "assets"), ("route_optimization", 32, "assets"), ("maintenance_alerts", 32, "assets")],
    "ashford-haulage": [("core_telematics", 25, "assets"), ("route_optimization", 25, "assets")],
    "birchwood-line-haul": [("core_telematics", 21, "assets"), ("route_optimization", 21, "assets")],
    "claybourne-transport-co": [("core_telematics", 17, "assets"), ("route_optimization", 17, "assets")],
    "dunmore-transport-co": [("core_telematics", 41, "assets"), ("route_optimization", 41, "assets")],
    "eastfield-freight": [("core_telematics", 27, "assets"), ("route_optimization", 27, "assets")],
    "farrow-fleet-ops": [("core_telematics", 7, "assets"), ("route_optimization", 7, "assets")],
    "glenbrook-distribution": [("core_telematics", 14, "assets"), ("route_optimization", 14, "assets")],
    "harlow-warehousing": [("core_telematics", 4, "assets")],
    "innisfree-logistics": [("core_telematics", 13, "assets")],
    "kestrel-logistics": [("core_telematics", 8, "assets"), ("route_optimization", 8, "assets")],
    "longview-delivery": [("core_telematics", 6, "assets")],
    "marrow-trucking": [("core_telematics", 6, "assets")],
    "newland-fleet-ops": [("core_telematics", 13, "assets")],
    "overlook-haulage": [("core_telematics", 13, "assets")],
    "parkview-fleet-services": [("core_telematics", 13, "assets")],
    "rockford-line-haul": [("core_telematics", 8, "assets")],
    "sandhill-distribution": [("core_telematics", 6, "assets")],
    "timberline2-fleet-ops": [("core_telematics", 11, "assets")],
    "vantage-line-haul": [("core_telematics", 12, "assets")],
    "wolfden-warehousing": [("core_telematics", 14, "assets"), ("route_optimization", 14, "assets")],
    "ashgate-industrial-supply": [("core_telematics", 5, "assets")],
    "bramblewood-fleet-ops": [("core_telematics", 14, "assets")],
    "copperfield2-carriers": [("core_telematics", 13, "assets"), ("route_optimization", 13, "assets")],
    "duskwood-transport-co": [("core_telematics", 7, "assets"), ("route_optimization", 7, "assets")],
    "evergreen-warehousing": [("core_telematics", 6, "assets"), ("route_optimization", 6, "assets")],
    "fallcreek-transport-co": [("core_telematics", 10, "assets")],
    "greystone-haulage": [("core_telematics", 4, "assets")],
    "hawksmoor-warehousing": [("core_telematics", 14, "assets")],
    "ironbark-fleet-ops": [("core_telematics", 10, "assets")],
    "larkspur-transport-co": [("core_telematics", 3, "assets")],
    "marshfield-supply-chain": [("core_telematics", 9, "assets")],
    "nightingale-industrial-supply": [("core_telematics", 6, "assets")],
    "ostervale-distribution": [("core_telematics", 10, "assets")],
    "pathfinder-freight": [("core_telematics", 9, "assets"), ("route_optimization", 9, "assets")],
    "quailridge-line-haul": [("core_telematics", 9, "assets")],
    "ravenswood-logistics": [("core_telematics", 14, "assets")],
    "stonegate-field-services": [("core_telematics", 8, "assets")],
    "truewind-distribution": [("core_telematics", 13, "assets"), ("route_optimization", 13, "assets")],
    "underpass-transport-co": [("core_telematics", 14, "assets"), ("route_optimization", 14, "assets")],
    "vernonhall-delivery": [("core_telematics", 14, "assets"), ("route_optimization", 14, "assets")],
    "wrenfield-carriers": [("core_telematics", 10, "assets")],
    "yarrow-industrial-supply": [("core_telematics", 10, "assets")],
    "ashland-transport-co": [("core_telematics", 8, "assets")],
    "belltower-supply-chain": [("core_telematics", 4, "assets")],
    "crestwood2-field-services": [("core_telematics", 4, "assets")],
    "driftwood2-haulage": [("core_telematics", 10, "assets")],
    "emberfield-delivery": [("core_telematics", 12, "assets"), ("route_optimization", 12, "assets")],
    "frostmoor-supply-chain": [("core_telematics", 9, "assets")],
    "graywolf-warehousing": [("core_telematics", 8, "assets")],
    "hartland-fleet-services": [("core_telematics", 8, "assets")],
    "ivorygate-freight": [("core_telematics", 12, "assets"), ("route_optimization", 12, "assets")],
    "juniperfield-logistics": [("core_telematics", 11, "assets"), ("route_optimization", 11, "assets")],
    "knollwood-transport-co": [("core_telematics", 10, "assets")],
    "lonepine-supply-chain": [("core_telematics", 6, "assets")],
    "meadowlark-field-services": [("core_telematics", 5, "assets")],
    "nightfall-warehousing": [("core_telematics", 10, "assets")],
    "oldstone-industrial-supply": [("core_telematics", 4, "assets"), ("route_optimization", 4, "assets")],
    "poplarcreek-trucking": [("core_telematics", 6, "assets"), ("route_optimization", 6, "assets")],
    "quietbrook-warehousing": [("core_telematics", 8, "assets"), ("route_optimization", 8, "assets")],
    "rimrock-trucking": [("core_telematics", 5, "assets")],
    "sagewood-fleet-ops": [("core_telematics", 5, "assets")],
    "trailrock-trucking": [("core_telematics", 9, "assets")],
    "umberfield-industrial-supply": [("core_telematics", 5, "assets")],
    "vinecrest-freight": [("core_telematics", 11, "assets"), ("route_optimization", 11, "assets")],
    "watermill-trucking": [("core_telematics", 9, "assets"), ("route_optimization", 9, "assets")],
    "yewbrook-field-services": [("core_telematics", 10, "assets")],
    "amberfield-fleet-ops": [("core_telematics", 9, "assets"), ("route_optimization", 9, "assets")],
    "boulderfield-fleet-services": [("core_telematics", 3, "assets")],
    "clearcreek2-industrial-supply": [("core_telematics", 9, "assets")],
    "duncehall-haulage": [("core_telematics", 4, "assets")],
    "elderwood-trucking": [("core_telematics", 13, "assets")],
    "foxglove-delivery": [("core_telematics", 3, "assets")],
    "granitehill-distribution": [("core_telematics", 4, "assets")],
    "hollowbrook-distribution": [("core_telematics", 11, "assets")],
    "ironwood2-line-haul": [("core_telematics", 3, "assets"), ("route_optimization", 3, "assets")],
    "jasperfield-logistics": [("core_telematics", 3, "assets")],
    "kettlecreek-distribution": [("core_telematics", 8, "assets"), ("route_optimization", 8, "assets")],
    "lindenfield-supply-chain": [("core_telematics", 4, "assets")],
    "mossgate-logistics": [("core_telematics", 11, "assets"), ("route_optimization", 11, "assets")],
    "northwind-distribution": [("core_telematics", 12, "assets")],
    "orchardview-industrial-supply": [("core_telematics", 10, "assets")],
    "palewood-field-services": [("core_telematics", 9, "assets"), ("route_optimization", 9, "assets")],
    "quarrycreek-haulage": [("core_telematics", 12, "assets"), ("route_optimization", 12, "assets")],
    "roughcut-freight": [("core_telematics", 5, "assets"), ("route_optimization", 5, "assets")],
    "stillwater2-freight": [("core_telematics", 13, "assets")],
    "thistledown-field-services": [("core_telematics", 13, "assets"), ("route_optimization", 13, "assets")],
    "uplands-distribution": [("core_telematics", 8, "assets")],
    "verdantfield-logistics": [("core_telematics", 4, "assets")],
    "whitfield-transport-co": [("core_telematics", 11, "assets"), ("route_optimization", 11, "assets")],
    "yarrowfield-delivery": [("core_telematics", 3, "assets"), ("route_optimization", 3, "assets")],
    "ashwell-supply-chain": [("core_telematics", 10, "assets")],
    "bramblecreek-line-haul": [("core_telematics", 3, "assets"), ("route_optimization", 3, "assets")],
    "cinderfield-delivery": [("core_telematics", 12, "assets"), ("route_optimization", 12, "assets")],
    "deepwater-haulage": [("core_telematics", 11, "assets")],
    "everfield-transport-co": [("core_telematics", 5, "assets"), ("route_optimization", 5, "assets")],
    "flintridge-field-services": [("core_telematics", 10, "assets")],
    "goldenfield-trucking": [("core_telematics", 3, "assets")],
    "hazelwood-transport-co": [("core_telematics", 14, "assets"), ("route_optimization", 14, "assets")],
    "ironhollow-line-haul": [("core_telematics", 3, "assets")],
    "junipergate-line-haul": [("core_telematics", 14, "assets"), ("route_optimization", 14, "assets")],
    "kirkfield-line-haul": [("core_telematics", 5, "assets")],
    "lowcreek-delivery": [("core_telematics", 3, "assets")],
    "mistvale-trucking": [("core_telematics", 9, "assets")],
    "netherfield-industrial-supply": [("core_telematics", 6, "assets")],
    "oakhollow-industrial-supply": [("core_telematics", 6, "assets")],
    "plainfield2-transport-co": [("core_telematics", 3, "assets")],
    "quarrystone2-warehousing": [("core_telematics", 14, "assets")],
    "redcreek-distribution": [("core_telematics", 10, "assets"), ("route_optimization", 10, "assets")],
    "slatefield-transport-co": [("core_telematics", 8, "assets")],
    "timbergate-transport-co": [("core_telematics", 11, "assets")],
    "uppercreek-logistics": [("core_telematics", 8, "assets")],
    "vandermill-haulage": [("core_telematics", 4, "assets")],
    "woodbine-transport-co": [("core_telematics", 14, "assets")],
    "yorkfield-industrial-supply": [("core_telematics", 3, "assets")],
    "ironclad-logistics": [("core_telematics", 4, "assets")],
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
