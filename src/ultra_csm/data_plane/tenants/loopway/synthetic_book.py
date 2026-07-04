"""Loopway 400-account synthetic book (Universe v2, WS-Tenant-Loopway, Wave 3).

Frozen literal data -- generated once by a non-shipped authoring script
(deterministic hash/index-derived names, no `random`, no runtime
generation), exactly the discipline docs/PROGRAM_REPORT_14.md's
Segmented-Book generator established. See docs/TENANT_LOOPWAY_BIBLE.md
for the canon this data implements: 4 high-touch, 20 mid-touch, 376
tech-touch (of which 98 carry named-arc weight: Arc L1's 60, Arc L2's 3,
Arc L3's 20, Herring L-H1's 15; the remaining 278 are plain, boring
tail accounts).
"""

from __future__ import annotations

from ultra_csm.data_plane.contracts import (
    AdoptionSummary,
    CRMAccount,
    CRMContact,
    CSCompany,
    Entitlement,
    HealthScore,
    TimeToValueMilestone,
    UsageSignal,
)
from ultra_csm.data_plane.fixtures import FixtureCustomerData, account_id_for, det_id

SEED_CLOCK = "2026-06-21T00:00:00Z"
SEED_DATE = "2026-06-21"
TENANT = "loopway"

# ---------------------------------------------------------------------------
# Account master list: (slug, name, industry, arr_cents, signup_date)
# ---------------------------------------------------------------------------

HIGH_TOUCH: tuple[tuple[str, str, str, int, str], ...] = (
    ("meridian-routeworks", "Meridian RouteWorks", "ecommerce_delivery", 18500000, "2025-09-01"),
    ("harborlight-logistics", "Harborlight Logistics", "last_mile_delivery", 14200000, "2025-11-15"),
    ("crestpoint-delivery-group", "Crestpoint Delivery Group", "courier", 12800000, "2026-01-10"),
    ("summitline-delivery-co", "Summitline Delivery Co", "food_delivery", 11000000, "2025-07-20"),
)

MID_TOUCH: tuple[tuple[str, str, str, int, str], ...] = (
    ("ashgrove-logistics", "Ashgrove Logistics", "last_mile_delivery", 2600000, "2025-01-01"),
    ("bellcrest-delivery", "Bellcrest Delivery", "courier", 2950000, "2025-02-04"),
    ("cinderpath-dispatch", "Cinderpath Dispatch", "food_delivery", 3300000, "2025-03-07"),
    ("dunmoor-routing", "Dunmoor Routing", "field_service_logistics", 3650000, "2025-04-10"),
    ("everfield-freight", "Everfield Freight", "ecommerce_delivery", 4000000, "2025-05-13"),
    ("foxglen-express", "Foxglen Express", "last_mile_delivery", 4350000, "2025-06-16"),
    ("graywick-transit", "Graywick Transit", "courier", 4700000, "2025-07-19"),
    ("hollowmere-movers", "Hollowmere Movers", "food_delivery", 5050000, "2025-08-22"),
    ("ironvale-logistics", "Ironvale Logistics", "field_service_logistics", 5400000, "2025-09-25"),
    ("junipeak-delivery", "Junipeak Delivery", "ecommerce_delivery", 5750000, "2025-10-01"),
    ("kestrelford-dispatch", "Kestrelford Dispatch", "last_mile_delivery", 6100000, "2025-11-04"),
    ("larkwood-routing", "Larkwood Routing", "courier", 6450000, "2025-12-07"),
    ("millhaven-freight", "Millhaven Freight", "food_delivery", 6800000, "2025-01-10"),
    ("norwick-express", "Norwick Express", "field_service_logistics", 7150000, "2025-02-13"),
    ("oakspire-transit", "Oakspire Transit", "ecommerce_delivery", 7500000, "2025-03-16"),
    ("pemberton-movers", "Pemberton Movers", "last_mile_delivery", 7850000, "2025-04-19"),
    ("quillfield-logistics", "Quillfield Logistics", "courier", 8200000, "2025-05-22"),
    ("rosemere-delivery", "Rosemere Delivery", "food_delivery", 8550000, "2025-06-25"),
    ("stonewick-dispatch", "Stonewick Dispatch", "field_service_logistics", 8900000, "2025-07-01"),
    ("thistledown-routing", "Thistledown Routing", "ecommerce_delivery", 9250000, "2025-08-04"),
)

# Arc L1 -- stalled 35 (signup wave day 30-45)
L1_STALLED_ROWS: tuple[tuple[str, str, str, int, str], ...] = (
    ("northline-logistics", "Northline Logistics", "last_mile_delivery", 180000, "2026-02-03"),
    ("fastlane-delivery", "Fastlane Delivery", "courier", 180000, "2026-02-04"),
    ("swiftpath-dispatch", "Swiftpath Dispatch", "food_delivery", 180000, "2026-02-05"),
    ("corebridge-routing", "Corebridge Routing", "field_service_logistics", 180000, "2026-02-06"),
    ("vector-freight", "Vector Freight", "ecommerce_delivery", 180000, "2026-02-07"),
    ("trueroute-express", "Trueroute Express", "last_mile_delivery", 180000, "2026-02-08"),
    ("openlane-transit", "Openlane Transit", "courier", 180000, "2026-02-09"),
    ("brightpath-movers", "Brightpath Movers", "food_delivery", 180000, "2026-02-10"),
    ("clearroute-logistics", "Clearroute Logistics", "field_service_logistics", 180000, "2026-02-11"),
    ("fleetwire-delivery", "Fleetwire Delivery", "ecommerce_delivery", 180000, "2026-02-12"),
    ("dashline-dispatch", "Dashline Dispatch", "last_mile_delivery", 180000, "2026-02-13"),
    ("rapidcore-routing", "Rapidcore Routing", "courier", 180000, "2026-02-14"),
    ("pathfynd-freight", "Pathfynd Freight", "food_delivery", 180000, "2026-02-15"),
    ("routewise-express", "Routewise Express", "field_service_logistics", 180000, "2026-02-16"),
    ("loadline-transit", "Loadline Transit", "ecommerce_delivery", 180000, "2026-02-17"),
    ("dispatchly-movers", "Dispatchly Movers", "last_mile_delivery", 180000, "2026-02-18"),
    ("trackwell-logistics", "Trackwell Logistics", "courier", 180000, "2026-02-03"),
    ("wayfare-delivery", "Wayfare Delivery", "food_delivery", 180000, "2026-02-04"),
    ("nimbleroute-dispatch", "Nimbleroute Dispatch", "field_service_logistics", 180000, "2026-02-05"),
    ("sprintline-routing", "Sprintline Routing", "ecommerce_delivery", 180000, "2026-02-06"),
    ("corepath-freight", "Corepath Freight", "last_mile_delivery", 180000, "2026-02-07"),
    ("ridgewire-express", "Ridgewire Express", "courier", 180000, "2026-02-08"),
    ("freshtrack-transit", "Freshtrack Transit", "food_delivery", 180000, "2026-02-09"),
    ("nextroute-movers", "Nextroute Movers", "field_service_logistics", 180000, "2026-02-10"),
    ("basecamp-logistics", "Basecamp Logistics", "ecommerce_delivery", 180000, "2026-02-11"),
    ("signalcore-delivery", "Signalcore Delivery", "last_mile_delivery", 180000, "2026-02-12"),
    ("pivotroute-dispatch", "Pivotroute Dispatch", "courier", 180000, "2026-02-13"),
    ("driftline-routing", "Driftline Routing", "food_delivery", 180000, "2026-02-14"),
    ("focalpath-freight", "Focalpath Freight", "field_service_logistics", 180000, "2026-02-15"),
    ("uplinehq-express", "Uplinehq Express", "ecommerce_delivery", 180000, "2026-02-16"),
    ("greenlane-transit", "Greenlane Transit", "last_mile_delivery", 180000, "2026-02-17"),
    ("steadyroute-movers", "Steadyroute Movers", "courier", 180000, "2026-02-18"),
    ("fastcore-logistics", "Fastcore Logistics", "food_delivery", 180000, "2026-02-03"),
    ("truepath-delivery", "Truepath Delivery", "field_service_logistics", 180000, "2026-02-04"),
    ("openroute-dispatch", "Openroute Dispatch", "ecommerce_delivery", 180000, "2026-02-05"),
)

# Arc L1 -- activated 25 (contrast group, same wave)
L1_ACTIVATED_ROWS: tuple[tuple[str, str, str, int, str], ...] = (
    ("brightline-routing", "Brightline Routing", "last_mile_delivery", 180000, "2026-02-03"),
    ("clearcore-freight", "Clearcore Freight", "courier", 180000, "2026-02-04"),
    ("fleetline-express", "Fleetline Express", "food_delivery", 180000, "2026-02-05"),
    ("dashcore-transit", "Dashcore Transit", "field_service_logistics", 180000, "2026-02-06"),
    ("rapidpath-movers", "Rapidpath Movers", "ecommerce_delivery", 180000, "2026-02-07"),
    ("pathwire-logistics", "Pathwire Logistics", "last_mile_delivery", 180000, "2026-02-08"),
    ("routecore-delivery", "Routecore Delivery", "courier", 180000, "2026-02-09"),
    ("loadcore-dispatch", "Loadcore Dispatch", "food_delivery", 180000, "2026-02-10"),
    ("dispatchwire-routing", "Dispatchwire Routing", "field_service_logistics", 180000, "2026-02-11"),
    ("trackline-freight", "Trackline Freight", "ecommerce_delivery", 180000, "2026-02-12"),
    ("wayline-express", "Wayline Express", "last_mile_delivery", 180000, "2026-02-13"),
    ("nimblecore-transit", "Nimblecore Transit", "courier", 180000, "2026-02-14"),
    ("sprintpath-movers", "Sprintpath Movers", "food_delivery", 180000, "2026-02-15"),
    ("northline-delivery2", "Northline Delivery", "field_service_logistics", 180000, "2026-02-16"),
    ("fastlane-dispatch2", "Fastlane Dispatch", "ecommerce_delivery", 180000, "2026-02-17"),
    ("swiftpath-routing2", "Swiftpath Routing", "last_mile_delivery", 180000, "2026-02-18"),
    ("corebridge-freight2", "Corebridge Freight", "courier", 180000, "2026-02-03"),
    ("vector-express2", "Vector Express", "food_delivery", 180000, "2026-02-04"),
    ("trueroute-transit2", "Trueroute Transit", "field_service_logistics", 180000, "2026-02-05"),
    ("openlane-movers2", "Openlane Movers", "ecommerce_delivery", 180000, "2026-02-06"),
    ("brightpath-logistics2", "Brightpath Logistics", "last_mile_delivery", 180000, "2026-02-07"),
    ("clearroute-delivery2", "Clearroute Delivery", "courier", 180000, "2026-02-08"),
    ("fleetwire-dispatch2", "Fleetwire Dispatch", "food_delivery", 180000, "2026-02-09"),
    ("dashline-routing2", "Dashline Routing", "field_service_logistics", 180000, "2026-02-10"),
    ("rapidcore-freight2", "Rapidcore Freight", "ecommerce_delivery", 180000, "2026-02-11"),
)

# Arc L2 -- PQL surfacing (3 accounts)
L2_ROWS: tuple[tuple[str, str, str, int, str], ...] = (
    ("pathfynd-express2", "Pathfynd Express", "last_mile_delivery", 240000, "2025-01-01"),
    ("routewise-transit2", "Routewise Transit", "courier", 240000, "2025-01-01"),
    ("loadline-movers2", "Loadline Movers", "food_delivery", 240000, "2025-01-01"),
)

# Arc L3 -- silent mass churn-risk (20 accounts)
L3_ROWS: tuple[tuple[str, str, str, int, str], ...] = (
    ("dispatchly-logistics2", "Dispatchly Logistics", "field_service_logistics", 150000, "2025-01-01"),
    ("trackwell-delivery2", "Trackwell Delivery", "ecommerce_delivery", 150000, "2025-01-01"),
    ("wayfare-dispatch2", "Wayfare Dispatch", "last_mile_delivery", 150000, "2025-01-01"),
    ("nimbleroute-routing2", "Nimbleroute Routing", "courier", 150000, "2025-01-01"),
    ("sprintline-freight2", "Sprintline Freight", "food_delivery", 150000, "2025-01-01"),
    ("corepath-express2", "Corepath Express", "field_service_logistics", 150000, "2025-01-01"),
    ("ridgewire-transit2", "Ridgewire Transit", "ecommerce_delivery", 150000, "2025-01-01"),
    ("freshtrack-movers2", "Freshtrack Movers", "last_mile_delivery", 150000, "2025-01-01"),
    ("nextroute-logistics2", "Nextroute Logistics", "courier", 150000, "2025-01-01"),
    ("basecamp-delivery2", "Basecamp Delivery", "food_delivery", 150000, "2025-01-01"),
    ("signalcore-dispatch2", "Signalcore Dispatch", "field_service_logistics", 150000, "2025-01-01"),
    ("pivotroute-routing2", "Pivotroute Routing", "ecommerce_delivery", 150000, "2025-01-01"),
    ("driftline-freight2", "Driftline Freight", "last_mile_delivery", 150000, "2025-01-01"),
    ("focalpath-express2", "Focalpath Express", "courier", 150000, "2025-01-01"),
    ("uplinehq-transit2", "Uplinehq Transit", "food_delivery", 150000, "2025-01-01"),
    ("greenlane-movers2", "Greenlane Movers", "field_service_logistics", 150000, "2025-01-01"),
    ("steadyroute-logistics2", "Steadyroute Logistics", "ecommerce_delivery", 150000, "2025-01-01"),
    ("fastcore-delivery2", "Fastcore Delivery", "last_mile_delivery", 150000, "2025-01-01"),
    ("truepath-dispatch2", "Truepath Dispatch", "courier", 150000, "2025-01-01"),
    ("openroute-routing2", "Openroute Routing", "food_delivery", 150000, "2025-01-01"),
)

# Herring L-H1 -- seasonal dip, self-recovers (15 accounts)
HERRING_ROWS: tuple[tuple[str, str, str, int, str], ...] = (
    ("brightline-freight2", "Brightline Freight", "field_service_logistics", 160000, "2025-01-01"),
    ("clearcore-express2", "Clearcore Express", "ecommerce_delivery", 160000, "2025-01-01"),
    ("fleetline-transit2", "Fleetline Transit", "last_mile_delivery", 160000, "2025-01-01"),
    ("dashcore-movers2", "Dashcore Movers", "courier", 160000, "2025-01-01"),
    ("rapidpath-logistics2", "Rapidpath Logistics", "food_delivery", 160000, "2025-01-01"),
    ("pathwire-delivery2", "Pathwire Delivery", "field_service_logistics", 160000, "2025-01-01"),
    ("routecore-dispatch2", "Routecore Dispatch", "ecommerce_delivery", 160000, "2025-01-01"),
    ("loadcore-routing2", "Loadcore Routing", "last_mile_delivery", 160000, "2025-01-01"),
    ("dispatchwire-freight2", "Dispatchwire Freight", "courier", 160000, "2025-01-01"),
    ("trackline-express2", "Trackline Express", "food_delivery", 160000, "2025-01-01"),
    ("wayline-transit2", "Wayline Transit", "field_service_logistics", 160000, "2025-01-01"),
    ("nimblecore-movers2", "Nimblecore Movers", "ecommerce_delivery", 160000, "2025-01-01"),
    ("sprintpath-logistics2", "Sprintpath Logistics", "last_mile_delivery", 160000, "2025-01-01"),
    ("northline-dispatch3", "Northline Dispatch", "courier", 160000, "2025-01-01"),
    ("fastlane-routing3", "Fastlane Routing", "food_delivery", 160000, "2025-01-01"),
)

# Plain tech-touch tail: 278 ordinary, boring accounts -- no arc, no story.
PLAIN_ROWS: tuple[tuple[str, str, str, int, str], ...] = (
    ("swiftpath-freight3", "Swiftpath Freight", "field_service_logistics", 194000, "2025-06-01"),
    ("corebridge-express3", "Corebridge Express", "ecommerce_delivery", 202000, "2025-06-01"),
    ("vector-transit3", "Vector Transit", "last_mile_delivery", 50000, "2025-06-01"),
    ("trueroute-movers3", "Trueroute Movers", "courier", 58000, "2025-06-01"),
    ("openlane-logistics3", "Openlane Logistics", "food_delivery", 66000, "2025-06-01"),
    ("brightpath-delivery3", "Brightpath Delivery", "field_service_logistics", 74000, "2025-06-01"),
    ("clearroute-dispatch3", "Clearroute Dispatch", "ecommerce_delivery", 82000, "2025-06-01"),
    ("fleetwire-routing3", "Fleetwire Routing", "last_mile_delivery", 90000, "2025-06-01"),
    ("dashline-freight3", "Dashline Freight", "courier", 98000, "2025-06-01"),
    ("rapidcore-express3", "Rapidcore Express", "food_delivery", 106000, "2025-06-01"),
    ("pathfynd-transit3", "Pathfynd Transit", "field_service_logistics", 114000, "2025-06-01"),
    ("routewise-movers3", "Routewise Movers", "ecommerce_delivery", 122000, "2025-06-01"),
    ("loadline-logistics3", "Loadline Logistics", "last_mile_delivery", 130000, "2025-06-01"),
    ("dispatchly-delivery3", "Dispatchly Delivery", "courier", 138000, "2025-06-01"),
    ("trackwell-dispatch3", "Trackwell Dispatch", "food_delivery", 146000, "2025-06-01"),
    ("wayfare-routing3", "Wayfare Routing", "field_service_logistics", 154000, "2025-06-01"),
    ("nimbleroute-freight3", "Nimbleroute Freight", "ecommerce_delivery", 162000, "2025-06-01"),
    ("sprintline-express3", "Sprintline Express", "last_mile_delivery", 170000, "2025-06-01"),
    ("corepath-transit3", "Corepath Transit", "courier", 178000, "2025-06-01"),
    ("ridgewire-movers3", "Ridgewire Movers", "food_delivery", 186000, "2025-06-01"),
    ("freshtrack-logistics3", "Freshtrack Logistics", "field_service_logistics", 194000, "2025-06-01"),
    ("nextroute-delivery3", "Nextroute Delivery", "ecommerce_delivery", 202000, "2025-06-01"),
    ("basecamp-dispatch3", "Basecamp Dispatch", "last_mile_delivery", 50000, "2025-06-01"),
    ("signalcore-routing3", "Signalcore Routing", "courier", 58000, "2025-06-01"),
    ("pivotroute-freight3", "Pivotroute Freight", "food_delivery", 66000, "2025-06-01"),
    ("driftline-express3", "Driftline Express", "field_service_logistics", 74000, "2025-06-01"),
    ("focalpath-transit3", "Focalpath Transit", "ecommerce_delivery", 82000, "2025-06-01"),
    ("uplinehq-movers3", "Uplinehq Movers", "last_mile_delivery", 90000, "2025-06-01"),
    ("greenlane-logistics3", "Greenlane Logistics", "courier", 98000, "2025-06-01"),
    ("steadyroute-delivery3", "Steadyroute Delivery", "food_delivery", 106000, "2025-06-01"),
    ("fastcore-dispatch3", "Fastcore Dispatch", "field_service_logistics", 114000, "2025-06-01"),
    ("truepath-routing3", "Truepath Routing", "ecommerce_delivery", 122000, "2025-06-01"),
    ("openroute-freight3", "Openroute Freight", "last_mile_delivery", 130000, "2025-06-01"),
    ("brightline-express3", "Brightline Express", "courier", 138000, "2025-06-01"),
    ("clearcore-transit3", "Clearcore Transit", "food_delivery", 146000, "2025-06-01"),
    ("fleetline-movers3", "Fleetline Movers", "field_service_logistics", 154000, "2025-06-01"),
    ("dashcore-logistics3", "Dashcore Logistics", "ecommerce_delivery", 162000, "2025-06-01"),
    ("rapidpath-delivery3", "Rapidpath Delivery", "last_mile_delivery", 170000, "2025-06-01"),
    ("pathwire-dispatch3", "Pathwire Dispatch", "courier", 178000, "2025-06-01"),
    ("routecore-routing3", "Routecore Routing", "food_delivery", 186000, "2025-06-01"),
    ("loadcore-freight3", "Loadcore Freight", "field_service_logistics", 194000, "2025-06-01"),
    ("dispatchwire-express3", "Dispatchwire Express", "ecommerce_delivery", 202000, "2025-06-01"),
    ("trackline-transit3", "Trackline Transit", "last_mile_delivery", 50000, "2025-06-01"),
    ("wayline-movers3", "Wayline Movers", "courier", 58000, "2025-06-01"),
    ("nimblecore-logistics3", "Nimblecore Logistics", "food_delivery", 66000, "2025-06-01"),
    ("sprintpath-delivery3", "Sprintpath Delivery", "field_service_logistics", 74000, "2025-06-01"),
    ("northline-routing4", "Northline Routing", "ecommerce_delivery", 82000, "2025-06-01"),
    ("fastlane-freight4", "Fastlane Freight", "last_mile_delivery", 90000, "2025-06-01"),
    ("swiftpath-express4", "Swiftpath Express", "courier", 98000, "2025-06-01"),
    ("corebridge-transit4", "Corebridge Transit", "food_delivery", 106000, "2025-06-01"),
    ("vector-movers4", "Vector Movers", "field_service_logistics", 114000, "2025-06-01"),
    ("trueroute-logistics4", "Trueroute Logistics", "ecommerce_delivery", 122000, "2025-06-01"),
    ("openlane-delivery4", "Openlane Delivery", "last_mile_delivery", 130000, "2025-06-01"),
    ("brightpath-dispatch4", "Brightpath Dispatch", "courier", 138000, "2025-06-01"),
    ("clearroute-routing4", "Clearroute Routing", "food_delivery", 146000, "2025-06-01"),
    ("fleetwire-freight4", "Fleetwire Freight", "field_service_logistics", 154000, "2025-06-01"),
    ("dashline-express4", "Dashline Express", "ecommerce_delivery", 162000, "2025-06-01"),
    ("rapidcore-transit4", "Rapidcore Transit", "last_mile_delivery", 170000, "2025-06-01"),
    ("pathfynd-movers4", "Pathfynd Movers", "courier", 178000, "2025-06-01"),
    ("routewise-logistics4", "Routewise Logistics", "food_delivery", 186000, "2025-06-01"),
    ("loadline-delivery4", "Loadline Delivery", "field_service_logistics", 194000, "2025-06-01"),
    ("dispatchly-dispatch4", "Dispatchly Dispatch", "ecommerce_delivery", 202000, "2025-06-01"),
    ("trackwell-routing4", "Trackwell Routing", "last_mile_delivery", 50000, "2025-06-01"),
    ("wayfare-freight4", "Wayfare Freight", "courier", 58000, "2025-06-01"),
    ("nimbleroute-express4", "Nimbleroute Express", "food_delivery", 66000, "2025-06-01"),
    ("sprintline-transit4", "Sprintline Transit", "field_service_logistics", 74000, "2025-06-01"),
    ("corepath-movers4", "Corepath Movers", "ecommerce_delivery", 82000, "2025-06-01"),
    ("ridgewire-logistics4", "Ridgewire Logistics", "last_mile_delivery", 90000, "2025-06-01"),
    ("freshtrack-delivery4", "Freshtrack Delivery", "courier", 98000, "2025-06-01"),
    ("nextroute-dispatch4", "Nextroute Dispatch", "food_delivery", 106000, "2025-06-01"),
    ("basecamp-routing4", "Basecamp Routing", "field_service_logistics", 114000, "2025-06-01"),
    ("signalcore-freight4", "Signalcore Freight", "ecommerce_delivery", 122000, "2025-06-01"),
    ("pivotroute-express4", "Pivotroute Express", "last_mile_delivery", 130000, "2025-06-01"),
    ("driftline-transit4", "Driftline Transit", "courier", 138000, "2025-06-01"),
    ("focalpath-movers4", "Focalpath Movers", "food_delivery", 146000, "2025-06-01"),
    ("uplinehq-logistics4", "Uplinehq Logistics", "field_service_logistics", 154000, "2025-06-01"),
    ("greenlane-delivery4", "Greenlane Delivery", "ecommerce_delivery", 162000, "2025-06-01"),
    ("steadyroute-dispatch4", "Steadyroute Dispatch", "last_mile_delivery", 170000, "2025-06-01"),
    ("fastcore-routing4", "Fastcore Routing", "courier", 178000, "2025-06-01"),
    ("truepath-freight4", "Truepath Freight", "food_delivery", 186000, "2025-06-01"),
    ("openroute-express4", "Openroute Express", "field_service_logistics", 194000, "2025-06-01"),
    ("brightline-transit4", "Brightline Transit", "ecommerce_delivery", 202000, "2025-06-01"),
    ("clearcore-movers4", "Clearcore Movers", "last_mile_delivery", 50000, "2025-06-01"),
    ("fleetline-logistics4", "Fleetline Logistics", "courier", 58000, "2025-06-01"),
    ("dashcore-delivery4", "Dashcore Delivery", "food_delivery", 66000, "2025-06-01"),
    ("rapidpath-dispatch4", "Rapidpath Dispatch", "field_service_logistics", 74000, "2025-06-01"),
    ("pathwire-routing4", "Pathwire Routing", "ecommerce_delivery", 82000, "2025-06-01"),
    ("routecore-freight4", "Routecore Freight", "last_mile_delivery", 90000, "2025-06-01"),
    ("loadcore-express4", "Loadcore Express", "courier", 98000, "2025-06-01"),
    ("dispatchwire-transit4", "Dispatchwire Transit", "food_delivery", 106000, "2025-06-01"),
    ("trackline-movers4", "Trackline Movers", "field_service_logistics", 114000, "2025-06-01"),
    ("wayline-logistics4", "Wayline Logistics", "ecommerce_delivery", 122000, "2025-06-01"),
    ("nimblecore-delivery4", "Nimblecore Delivery", "last_mile_delivery", 130000, "2025-06-01"),
    ("sprintpath-dispatch4", "Sprintpath Dispatch", "courier", 138000, "2025-06-01"),
    ("northline-freight5", "Northline Freight", "food_delivery", 146000, "2025-06-01"),
    ("fastlane-express5", "Fastlane Express", "field_service_logistics", 154000, "2025-06-01"),
    ("swiftpath-transit5", "Swiftpath Transit", "ecommerce_delivery", 162000, "2025-06-01"),
    ("corebridge-movers5", "Corebridge Movers", "last_mile_delivery", 170000, "2025-06-01"),
    ("vector-logistics5", "Vector Logistics", "courier", 178000, "2025-06-01"),
    ("trueroute-delivery5", "Trueroute Delivery", "food_delivery", 186000, "2025-06-01"),
    ("openlane-dispatch5", "Openlane Dispatch", "field_service_logistics", 194000, "2025-06-01"),
    ("brightpath-routing5", "Brightpath Routing", "ecommerce_delivery", 202000, "2025-06-01"),
    ("clearroute-freight5", "Clearroute Freight", "last_mile_delivery", 50000, "2025-06-01"),
    ("fleetwire-express5", "Fleetwire Express", "courier", 58000, "2025-06-01"),
    ("dashline-transit5", "Dashline Transit", "food_delivery", 66000, "2025-06-01"),
    ("rapidcore-movers5", "Rapidcore Movers", "field_service_logistics", 74000, "2025-06-01"),
    ("pathfynd-logistics5", "Pathfynd Logistics", "ecommerce_delivery", 82000, "2025-06-01"),
    ("routewise-delivery5", "Routewise Delivery", "last_mile_delivery", 90000, "2025-06-01"),
    ("loadline-dispatch5", "Loadline Dispatch", "courier", 98000, "2025-06-01"),
    ("dispatchly-routing5", "Dispatchly Routing", "food_delivery", 106000, "2025-06-01"),
    ("trackwell-freight5", "Trackwell Freight", "field_service_logistics", 114000, "2025-06-01"),
    ("wayfare-express5", "Wayfare Express", "ecommerce_delivery", 122000, "2025-06-01"),
    ("nimbleroute-transit5", "Nimbleroute Transit", "last_mile_delivery", 130000, "2025-06-01"),
    ("sprintline-movers5", "Sprintline Movers", "courier", 138000, "2025-06-01"),
    ("corepath-logistics5", "Corepath Logistics", "food_delivery", 146000, "2025-06-01"),
    ("ridgewire-delivery5", "Ridgewire Delivery", "field_service_logistics", 154000, "2025-06-01"),
    ("freshtrack-dispatch5", "Freshtrack Dispatch", "ecommerce_delivery", 162000, "2025-06-01"),
    ("nextroute-routing5", "Nextroute Routing", "last_mile_delivery", 170000, "2025-06-01"),
    ("basecamp-freight5", "Basecamp Freight", "courier", 178000, "2025-06-01"),
    ("signalcore-express5", "Signalcore Express", "food_delivery", 186000, "2025-06-01"),
    ("pivotroute-transit5", "Pivotroute Transit", "field_service_logistics", 194000, "2025-06-01"),
    ("driftline-movers5", "Driftline Movers", "ecommerce_delivery", 202000, "2025-06-01"),
    ("focalpath-logistics5", "Focalpath Logistics", "last_mile_delivery", 50000, "2025-06-01"),
    ("uplinehq-delivery5", "Uplinehq Delivery", "courier", 58000, "2025-06-01"),
    ("greenlane-dispatch5", "Greenlane Dispatch", "food_delivery", 66000, "2025-06-01"),
    ("steadyroute-routing5", "Steadyroute Routing", "field_service_logistics", 74000, "2025-06-01"),
    ("fastcore-freight5", "Fastcore Freight", "ecommerce_delivery", 82000, "2025-06-01"),
    ("truepath-express5", "Truepath Express", "last_mile_delivery", 90000, "2025-06-01"),
    ("openroute-transit5", "Openroute Transit", "courier", 98000, "2025-06-01"),
    ("brightline-movers5", "Brightline Movers", "food_delivery", 106000, "2025-06-01"),
    ("clearcore-logistics5", "Clearcore Logistics", "field_service_logistics", 114000, "2025-06-01"),
    ("fleetline-delivery5", "Fleetline Delivery", "ecommerce_delivery", 122000, "2025-06-01"),
    ("dashcore-dispatch5", "Dashcore Dispatch", "last_mile_delivery", 130000, "2025-06-01"),
    ("rapidpath-routing5", "Rapidpath Routing", "courier", 138000, "2025-06-01"),
    ("pathwire-freight5", "Pathwire Freight", "food_delivery", 146000, "2025-06-01"),
    ("routecore-express5", "Routecore Express", "field_service_logistics", 154000, "2025-06-01"),
    ("loadcore-transit5", "Loadcore Transit", "ecommerce_delivery", 162000, "2025-06-01"),
    ("dispatchwire-movers5", "Dispatchwire Movers", "last_mile_delivery", 170000, "2025-06-01"),
    ("trackline-logistics5", "Trackline Logistics", "courier", 178000, "2025-06-01"),
    ("wayline-delivery5", "Wayline Delivery", "food_delivery", 186000, "2025-06-01"),
    ("nimblecore-dispatch5", "Nimblecore Dispatch", "field_service_logistics", 194000, "2025-06-01"),
    ("sprintpath-routing5", "Sprintpath Routing", "ecommerce_delivery", 202000, "2025-06-01"),
    ("northline-express6", "Northline Express", "last_mile_delivery", 50000, "2025-06-01"),
    ("fastlane-transit6", "Fastlane Transit", "courier", 58000, "2025-06-01"),
    ("swiftpath-movers6", "Swiftpath Movers", "food_delivery", 66000, "2025-06-01"),
    ("corebridge-logistics6", "Corebridge Logistics", "field_service_logistics", 74000, "2025-06-01"),
    ("vector-delivery6", "Vector Delivery", "ecommerce_delivery", 82000, "2025-06-01"),
    ("trueroute-dispatch6", "Trueroute Dispatch", "last_mile_delivery", 90000, "2025-06-01"),
    ("openlane-routing6", "Openlane Routing", "courier", 98000, "2025-06-01"),
    ("brightpath-freight6", "Brightpath Freight", "food_delivery", 106000, "2025-06-01"),
    ("clearroute-express6", "Clearroute Express", "field_service_logistics", 114000, "2025-06-01"),
    ("fleetwire-transit6", "Fleetwire Transit", "ecommerce_delivery", 122000, "2025-06-01"),
    ("dashline-movers6", "Dashline Movers", "last_mile_delivery", 130000, "2025-06-01"),
    ("rapidcore-logistics6", "Rapidcore Logistics", "courier", 138000, "2025-06-01"),
    ("pathfynd-delivery6", "Pathfynd Delivery", "food_delivery", 146000, "2025-06-01"),
    ("routewise-dispatch6", "Routewise Dispatch", "field_service_logistics", 154000, "2025-06-01"),
    ("loadline-routing6", "Loadline Routing", "ecommerce_delivery", 162000, "2025-06-01"),
    ("dispatchly-freight6", "Dispatchly Freight", "last_mile_delivery", 170000, "2025-06-01"),
    ("trackwell-express6", "Trackwell Express", "courier", 178000, "2025-06-01"),
    ("wayfare-transit6", "Wayfare Transit", "food_delivery", 186000, "2025-06-01"),
    ("nimbleroute-movers6", "Nimbleroute Movers", "field_service_logistics", 194000, "2025-06-01"),
    ("sprintline-logistics6", "Sprintline Logistics", "ecommerce_delivery", 202000, "2025-06-01"),
    ("corepath-delivery6", "Corepath Delivery", "last_mile_delivery", 50000, "2025-06-01"),
    ("ridgewire-dispatch6", "Ridgewire Dispatch", "courier", 58000, "2025-06-01"),
    ("freshtrack-routing6", "Freshtrack Routing", "food_delivery", 66000, "2025-06-01"),
    ("nextroute-freight6", "Nextroute Freight", "field_service_logistics", 74000, "2025-06-01"),
    ("basecamp-express6", "Basecamp Express", "ecommerce_delivery", 82000, "2025-06-01"),
    ("signalcore-transit6", "Signalcore Transit", "last_mile_delivery", 90000, "2025-06-01"),
    ("pivotroute-movers6", "Pivotroute Movers", "courier", 98000, "2025-06-01"),
    ("driftline-logistics6", "Driftline Logistics", "food_delivery", 106000, "2025-06-01"),
    ("focalpath-delivery6", "Focalpath Delivery", "field_service_logistics", 114000, "2025-06-01"),
    ("uplinehq-dispatch6", "Uplinehq Dispatch", "ecommerce_delivery", 122000, "2025-06-01"),
    ("greenlane-routing6", "Greenlane Routing", "last_mile_delivery", 130000, "2025-06-01"),
    ("steadyroute-freight6", "Steadyroute Freight", "courier", 138000, "2025-06-01"),
    ("fastcore-express6", "Fastcore Express", "food_delivery", 146000, "2025-06-01"),
    ("truepath-transit6", "Truepath Transit", "field_service_logistics", 154000, "2025-06-01"),
    ("openroute-movers6", "Openroute Movers", "ecommerce_delivery", 162000, "2025-06-01"),
    ("brightline-logistics6", "Brightline Logistics", "last_mile_delivery", 170000, "2025-06-01"),
    ("clearcore-delivery6", "Clearcore Delivery", "courier", 178000, "2025-06-01"),
    ("fleetline-dispatch6", "Fleetline Dispatch", "food_delivery", 186000, "2025-06-01"),
    ("dashcore-routing6", "Dashcore Routing", "field_service_logistics", 194000, "2025-06-01"),
    ("rapidpath-freight6", "Rapidpath Freight", "ecommerce_delivery", 202000, "2025-06-01"),
    ("pathwire-express6", "Pathwire Express", "last_mile_delivery", 50000, "2025-06-01"),
    ("routecore-transit6", "Routecore Transit", "courier", 58000, "2025-06-01"),
    ("loadcore-movers6", "Loadcore Movers", "food_delivery", 66000, "2025-06-01"),
    ("dispatchwire-logistics6", "Dispatchwire Logistics", "field_service_logistics", 74000, "2025-06-01"),
    ("trackline-delivery6", "Trackline Delivery", "ecommerce_delivery", 82000, "2025-06-01"),
    ("wayline-dispatch6", "Wayline Dispatch", "last_mile_delivery", 90000, "2025-06-01"),
    ("nimblecore-routing6", "Nimblecore Routing", "courier", 98000, "2025-06-01"),
    ("sprintpath-freight6", "Sprintpath Freight", "food_delivery", 106000, "2025-06-01"),
    ("northline-transit7", "Northline Transit", "field_service_logistics", 114000, "2025-06-01"),
    ("fastlane-movers7", "Fastlane Movers", "ecommerce_delivery", 122000, "2025-06-01"),
    ("swiftpath-logistics7", "Swiftpath Logistics", "last_mile_delivery", 130000, "2025-06-01"),
    ("corebridge-delivery7", "Corebridge Delivery", "courier", 138000, "2025-06-01"),
    ("vector-dispatch7", "Vector Dispatch", "food_delivery", 146000, "2025-06-01"),
    ("trueroute-routing7", "Trueroute Routing", "field_service_logistics", 154000, "2025-06-01"),
    ("openlane-freight7", "Openlane Freight", "ecommerce_delivery", 162000, "2025-06-01"),
    ("brightpath-express7", "Brightpath Express", "last_mile_delivery", 170000, "2025-06-01"),
    ("clearroute-transit7", "Clearroute Transit", "courier", 178000, "2025-06-01"),
    ("fleetwire-movers7", "Fleetwire Movers", "food_delivery", 186000, "2025-06-01"),
    ("dashline-logistics7", "Dashline Logistics", "field_service_logistics", 194000, "2025-06-01"),
    ("rapidcore-delivery7", "Rapidcore Delivery", "ecommerce_delivery", 202000, "2025-06-01"),
    ("pathfynd-dispatch7", "Pathfynd Dispatch", "last_mile_delivery", 50000, "2025-06-01"),
    ("routewise-routing7", "Routewise Routing", "courier", 58000, "2025-06-01"),
    ("loadline-freight7", "Loadline Freight", "food_delivery", 66000, "2025-06-01"),
    ("dispatchly-express7", "Dispatchly Express", "field_service_logistics", 74000, "2025-06-01"),
    ("trackwell-transit7", "Trackwell Transit", "ecommerce_delivery", 82000, "2025-06-01"),
    ("wayfare-movers7", "Wayfare Movers", "last_mile_delivery", 90000, "2025-06-01"),
    ("nimbleroute-logistics7", "Nimbleroute Logistics", "courier", 98000, "2025-06-01"),
    ("sprintline-delivery7", "Sprintline Delivery", "food_delivery", 106000, "2025-06-01"),
    ("corepath-dispatch7", "Corepath Dispatch", "field_service_logistics", 114000, "2025-06-01"),
    ("ridgewire-routing7", "Ridgewire Routing", "ecommerce_delivery", 122000, "2025-06-01"),
    ("freshtrack-freight7", "Freshtrack Freight", "last_mile_delivery", 130000, "2025-06-01"),
    ("nextroute-express7", "Nextroute Express", "courier", 138000, "2025-06-01"),
    ("basecamp-transit7", "Basecamp Transit", "food_delivery", 146000, "2025-06-01"),
    ("signalcore-movers7", "Signalcore Movers", "field_service_logistics", 154000, "2025-06-01"),
    ("pivotroute-logistics7", "Pivotroute Logistics", "ecommerce_delivery", 162000, "2025-06-01"),
    ("driftline-delivery7", "Driftline Delivery", "last_mile_delivery", 170000, "2025-06-01"),
    ("focalpath-dispatch7", "Focalpath Dispatch", "courier", 178000, "2025-06-01"),
    ("uplinehq-routing7", "Uplinehq Routing", "food_delivery", 186000, "2025-06-01"),
    ("greenlane-freight7", "Greenlane Freight", "field_service_logistics", 194000, "2025-06-01"),
    ("steadyroute-express7", "Steadyroute Express", "ecommerce_delivery", 202000, "2025-06-01"),
    ("fastcore-transit7", "Fastcore Transit", "last_mile_delivery", 50000, "2025-06-01"),
    ("truepath-movers7", "Truepath Movers", "courier", 58000, "2025-06-01"),
    ("openroute-logistics7", "Openroute Logistics", "food_delivery", 66000, "2025-06-01"),
    ("brightline-delivery7", "Brightline Delivery", "field_service_logistics", 74000, "2025-06-01"),
    ("clearcore-dispatch7", "Clearcore Dispatch", "ecommerce_delivery", 82000, "2025-06-01"),
    ("fleetline-routing7", "Fleetline Routing", "last_mile_delivery", 90000, "2025-06-01"),
    ("dashcore-freight7", "Dashcore Freight", "courier", 98000, "2025-06-01"),
    ("rapidpath-express7", "Rapidpath Express", "food_delivery", 106000, "2025-06-01"),
    ("pathwire-transit7", "Pathwire Transit", "field_service_logistics", 114000, "2025-06-01"),
    ("routecore-movers7", "Routecore Movers", "ecommerce_delivery", 122000, "2025-06-01"),
    ("loadcore-logistics7", "Loadcore Logistics", "last_mile_delivery", 130000, "2025-06-01"),
    ("dispatchwire-delivery7", "Dispatchwire Delivery", "courier", 138000, "2025-06-01"),
    ("trackline-dispatch7", "Trackline Dispatch", "food_delivery", 146000, "2025-06-01"),
    ("wayline-routing7", "Wayline Routing", "field_service_logistics", 154000, "2025-06-01"),
    ("nimblecore-freight7", "Nimblecore Freight", "ecommerce_delivery", 162000, "2025-06-01"),
    ("sprintpath-express7", "Sprintpath Express", "last_mile_delivery", 170000, "2025-06-01"),
    ("northline-movers8", "Northline Movers", "courier", 178000, "2025-06-01"),
    ("fastlane-logistics8", "Fastlane Logistics", "food_delivery", 186000, "2025-06-01"),
    ("swiftpath-delivery8", "Swiftpath Delivery", "field_service_logistics", 194000, "2025-06-01"),
    ("corebridge-dispatch8", "Corebridge Dispatch", "ecommerce_delivery", 202000, "2025-06-01"),
    ("vector-routing8", "Vector Routing", "last_mile_delivery", 50000, "2025-06-01"),
    ("trueroute-freight8", "Trueroute Freight", "courier", 58000, "2025-06-01"),
    ("openlane-express8", "Openlane Express", "food_delivery", 66000, "2025-06-01"),
    ("brightpath-transit8", "Brightpath Transit", "field_service_logistics", 74000, "2025-06-01"),
    ("clearroute-movers8", "Clearroute Movers", "ecommerce_delivery", 82000, "2025-06-01"),
    ("fleetwire-logistics8", "Fleetwire Logistics", "last_mile_delivery", 90000, "2025-06-01"),
    ("dashline-delivery8", "Dashline Delivery", "courier", 98000, "2025-06-01"),
    ("rapidcore-dispatch8", "Rapidcore Dispatch", "food_delivery", 106000, "2025-06-01"),
    ("pathfynd-routing8", "Pathfynd Routing", "field_service_logistics", 114000, "2025-06-01"),
    ("routewise-freight8", "Routewise Freight", "ecommerce_delivery", 122000, "2025-06-01"),
    ("loadline-express8", "Loadline Express", "last_mile_delivery", 130000, "2025-06-01"),
    ("dispatchly-transit8", "Dispatchly Transit", "courier", 138000, "2025-06-01"),
    ("trackwell-movers8", "Trackwell Movers", "food_delivery", 146000, "2025-06-01"),
    ("wayfare-logistics8", "Wayfare Logistics", "field_service_logistics", 154000, "2025-06-01"),
    ("nimbleroute-delivery8", "Nimbleroute Delivery", "ecommerce_delivery", 162000, "2025-06-01"),
    ("sprintline-dispatch8", "Sprintline Dispatch", "last_mile_delivery", 170000, "2025-06-01"),
    ("corepath-routing8", "Corepath Routing", "courier", 178000, "2025-06-01"),
    ("ridgewire-freight8", "Ridgewire Freight", "food_delivery", 186000, "2025-06-01"),
    ("freshtrack-express8", "Freshtrack Express", "field_service_logistics", 194000, "2025-06-01"),
    ("nextroute-transit8", "Nextroute Transit", "ecommerce_delivery", 202000, "2025-06-01"),
    ("basecamp-movers8", "Basecamp Movers", "last_mile_delivery", 50000, "2025-06-01"),
    ("signalcore-logistics8", "Signalcore Logistics", "courier", 58000, "2025-06-01"),
    ("pivotroute-delivery8", "Pivotroute Delivery", "food_delivery", 66000, "2025-06-01"),
    ("driftline-dispatch8", "Driftline Dispatch", "field_service_logistics", 74000, "2025-06-01"),
    ("focalpath-routing8", "Focalpath Routing", "ecommerce_delivery", 82000, "2025-06-01"),
    ("uplinehq-freight8", "Uplinehq Freight", "last_mile_delivery", 90000, "2025-06-01"),
    ("greenlane-express8", "Greenlane Express", "courier", 98000, "2025-06-01"),
    ("steadyroute-transit8", "Steadyroute Transit", "food_delivery", 106000, "2025-06-01"),
    ("fastcore-movers8", "Fastcore Movers", "field_service_logistics", 114000, "2025-06-01"),
    ("truepath-logistics8", "Truepath Logistics", "ecommerce_delivery", 122000, "2025-06-01"),
    ("openroute-delivery8", "Openroute Delivery", "last_mile_delivery", 130000, "2025-06-01"),
    ("brightline-dispatch8", "Brightline Dispatch", "courier", 138000, "2025-06-01"),
    ("clearcore-routing8", "Clearcore Routing", "food_delivery", 146000, "2025-06-01"),
    ("fleetline-freight8", "Fleetline Freight", "field_service_logistics", 154000, "2025-06-01"),
    ("dashcore-express8", "Dashcore Express", "ecommerce_delivery", 162000, "2025-06-01"),
    ("rapidpath-transit8", "Rapidpath Transit", "last_mile_delivery", 170000, "2025-06-01"),
)

L1_STALLED: tuple[str, ...] = tuple(r[0] for r in L1_STALLED_ROWS)
L1_ACTIVATED: tuple[str, ...] = tuple(r[0] for r in L1_ACTIVATED_ROWS)
L2_COHORT: tuple[str, ...] = tuple(r[0] for r in L2_ROWS)
L3_COHORT: tuple[str, ...] = tuple(r[0] for r in L3_ROWS)
HERRING_COHORT: tuple[str, ...] = tuple(r[0] for r in HERRING_ROWS)

ALL_ROWS: tuple[tuple[str, str, str, int, str], ...] = (
    HIGH_TOUCH + MID_TOUCH + L1_STALLED_ROWS + L1_ACTIVATED_ROWS + L2_ROWS
    + L3_ROWS + HERRING_ROWS + PLAIN_ROWS
)

NAMED_ACCOUNTS: tuple[str, ...] = tuple(
    r[0] for r in (HIGH_TOUCH + MID_TOUCH + L1_STALLED_ROWS + L1_ACTIVATED_ROWS + L2_ROWS + L3_ROWS + HERRING_ROWS)
)

# Fixed, deterministic 40-account sample of the 278 plain-tail accounts --
# the first 40 by generated index (never `random.sample`), stated per the
# bible's runtime-discipline section. Reused by every battery/eval that
# needs a bounded but representative tail sample.
PLAIN_TAIL_SAMPLE_40: tuple[str, ...] = tuple(r[0] for r in PLAIN_ROWS[:40])

# The battery/eval-facing account-list scope this tenant's runtime
# discipline commits to (bible: "Runtime + sampling discipline"): every
# named account plus the fixed 40-tail-account sample -- never a random
# sample, never all 400 for a check that constructs comms/telemetry
# fixtures per account.
BATTERY_SAMPLE: tuple[str, ...] = NAMED_ACCOUNTS + PLAIN_TAIL_SAMPLE_40


def _group_for(slug: str) -> str:
    if slug in {r[0] for r in HIGH_TOUCH}:
        return "high"
    if slug in {r[0] for r in MID_TOUCH}:
        return "mid"
    if slug in L1_STALLED:
        return "l1_stalled"
    if slug in L1_ACTIVATED:
        return "l1_activated"
    if slug in L2_COHORT:
        return "l2"
    if slug in L3_COHORT:
        return "l3"
    if slug in HERRING_COHORT:
        return "herring"
    return "plain"


# ---------------------------------------------------------------------------
# Deterministic per-account derived facts (health / adoption / entitlements /
# usage / milestones). No `random` module anywhere below -- every value is a
# pure function of the account's slug and static group membership, matching
# every other tenant's "no runtime randomness" discipline.
# ---------------------------------------------------------------------------


def _stable_unit_interval(*parts: object) -> float:
    """Deterministic value in [0, 1) derived from det_id's UUID5 -- used the
    same way campaigns.py's ``_det_unit_interval`` is, for a stable
    per-account pseudo-variation that is not randomness (same inputs
    always produce the same output, forever)."""

    from uuid import UUID

    return (UUID(det_id(*parts)).int % 10_000) / 10_000


def _health_for(slug: str, group: str) -> tuple[float, str, tuple[str, ...]]:
    """(score, band, drivers) -- static baseline snapshot (day 0)."""

    jitter = _stable_unit_interval("health", slug)
    if group == "high":
        return (88.0 + jitter * 8, "green", ("stable_usage",))
    if group == "mid":
        return (78.0 + jitter * 10, "green", ("stable_usage",))
    if group == "l1_stalled":
        return (42.0 + jitter * 8, "yellow", ("activation_stalled",))
    if group == "l1_activated":
        return (80.0 + jitter * 10, "green", ("fast_activation",))
    if group == "l2":
        return (90.0 + jitter * 6, "green", ("product_qualified_lead", "champion_active"))
    if group == "l3":
        return (35.0 + jitter * 8, "yellow", ("usage_decay_silent",))
    if group == "herring":
        return (68.0 + jitter * 8, "yellow", ("seasonal_dip",))
    return (72.0 + jitter * 15, "green", ("stable_usage",))


def _adoption_for(slug: str, group: str) -> tuple[int, int, int, int, float, tuple[str, ...]]:
    """(active_users, licensed_users, active_assets, entitled_assets,
    adoption_rate, underused_capabilities)."""

    jitter = _stable_unit_interval("adoption", slug)
    if group == "high":
        return (18 + int(jitter * 12), 25, 40 + int(jitter * 20), 60, 0.80, ())
    if group == "mid":
        return (6 + int(jitter * 6), 10, 12 + int(jitter * 8), 20, 0.65, ("proof_of_delivery",))
    if group == "l1_stalled":
        return (0, 3, 0, 5, 0.0, ("driver_app",))
    if group == "l1_activated":
        return (3 + int(jitter * 2), 3, 5 + int(jitter * 3), 5, 0.85, ())
    if group == "l2":
        # 5x the tech-touch tail median (median ~2 active users, ~2 route
        # plans/week for a plain tech-touch account) -- see usage signals.
        return (12 + int(jitter * 4), 15, 20 + int(jitter * 5), 20, 0.95, ())
    if group == "l3":
        return (0, 2, 0, 5, 0.0, ("route_planning_core",))
    if group == "herring":
        return (2 + int(jitter * 2), 3, 3 + int(jitter * 2), 5, 0.55, ())
    return (1 + int(jitter * 3), 2, 2 + int(jitter * 3), 5, 0.45, ())


def _entitlements_for(slug: str, group: str) -> list[tuple[str, int, str]]:
    if group in ("high", "mid"):
        return [
            ("route_planning_core", 30, "drivers"),
            ("driver_app", 30, "drivers"),
            ("proof_of_delivery", 30, "drivers"),
            ("analytics", 30, "users"),
        ]
    if group == "l2":
        return [
            ("route_planning_core", 15, "drivers"),
            ("driver_app", 15, "drivers"),
            ("analytics", 15, "users"),
        ]
    return [
        ("route_planning_core", 5, "drivers"),
        ("driver_app", 5, "drivers"),
    ]


def _usage_signals_for(account_id: str, slug: str, group: str) -> list[UsageSignal]:
    """Aggregate-level usage baselines (bible: "full event exhaust ONLY for
    L1/L2/L3 named accounts" -- these are the aggregate-level signals every
    account gets; per-event exhaust for arc accounts lives in
    ``event_telemetry.py``, not here)."""

    active_users, _, active_assets, _, _, _ = _adoption_for(slug, group)
    route_plans_per_week = float(active_users * 3)
    return [
        UsageSignal(
            signal_id=det_id("signal", account_id, "active_users", SEED_DATE),
            account_id=account_id,
            grain="company",
            subject_id=None,
            metric_name="active_users",
            value=float(active_users),
            unit="drivers",
            observed_at=SEED_CLOCK,
            source_ref="loopway_product_telemetry",
        ),
        UsageSignal(
            signal_id=det_id("signal", account_id, "route_plans_per_week", SEED_DATE),
            account_id=account_id,
            grain="company",
            subject_id=None,
            metric_name="route_plans_per_week",
            value=route_plans_per_week,
            unit="plans",
            observed_at=SEED_CLOCK,
            source_ref="loopway_product_telemetry",
        ),
    ]


def _milestone_for(account_id: str, slug: str, group: str, signup_date: str) -> TimeToValueMilestone:
    """The core PLG activation milestone: at least one driver logging a
    completed stop in the driver app."""

    from datetime import date, timedelta

    expected_by = (date.fromisoformat(signup_date) + timedelta(days=45)).isoformat()
    if group == "l1_stalled" or group == "l3":
        achieved_at = None
    else:
        achieved_at = signup_date
    evidence = () if achieved_at is None else (det_id("signal", account_id, "active_users", SEED_DATE),)
    return TimeToValueMilestone(
        account_id=account_id,
        milestone="driver_app_activated",
        expected_by=expected_by,
        achieved_at=achieved_at,
        evidence_signal_ids=evidence,
    )


def build_synthetic_book() -> FixtureCustomerData:
    """Build the 400-account Loopway synthetic book."""

    accounts = []
    companies = []
    contacts_list = []
    health_scores = []
    adoption_summaries = []
    entitlements_list = []
    usage_signals_list = []
    milestones_list = []

    for slug, name, industry, arr_cents, signup_date in ALL_ROWS:
        account_id = account_id_for(slug)
        group = _group_for(slug)

        accounts.append(
            CRMAccount(account_id=account_id, name=name, owner_id="growth-team", industry=industry)
        )
        companies.append(
            CSCompany(
                company_id=account_id,
                name=name,
                industry=industry,
                arr_cents=arr_cents,
                lifecycle_stage="steady_state" if group not in ("l1_stalled", "l1_activated") else "onboarding",
                status="Active",
                original_contract_date=signup_date,
                renewal_date=signup_date,
                csm_owner_id="growth-team",
                current_score=_health_for(slug, group)[0],
            )
        )

        # Named accounts (high/mid touch) get a real contact; the 376-account
        # tail gets one lightweight signup contact each (self-serve signup --
        # no CSM-managed contact roster for a PLG tail, per the bible's "no
        # named CSMs" canon).
        contact_email = f"admin@{slug.replace('-', '')}.example"
        contacts_list.append(
            CRMContact(
                contact_id=det_id("contact", account_id, contact_email),
                account_id=account_id,
                email=contact_email,
                name=f"{name} Admin",
                role="operations",
                title="Operations Lead" if group in ("high", "mid") else None,
                consent_to_contact=True,
            )
        )

        score, band, drivers = _health_for(slug, group)
        health_scores.append(
            HealthScore(account_id=account_id, score=score, band=band, drivers=drivers, measured_at=SEED_CLOCK)
        )

        active_users, licensed_users, active_assets, entitled_assets, adoption_rate, underused = _adoption_for(slug, group)
        adoption_summaries.append(
            AdoptionSummary(
                account_id=account_id,
                active_users=active_users,
                licensed_users=licensed_users,
                active_assets=active_assets,
                entitled_assets=entitled_assets,
                adoption_rate=adoption_rate,
                underused_capabilities=underused,
                measured_at=SEED_CLOCK,
            )
        )

        for capability, qty, unit in _entitlements_for(slug, group):
            entitlements_list.append(
                Entitlement(
                    account_id=account_id,
                    capability=capability,
                    entitled_quantity=qty,
                    unit=unit,
                    starts_at=signup_date,
                )
            )

        usage_signals_list.extend(_usage_signals_for(account_id, slug, group))
        milestones_list.append(_milestone_for(account_id, slug, group, signup_date))

    return FixtureCustomerData(
        accounts=tuple(accounts),
        companies=tuple(companies),
        contacts=tuple(contacts_list),
        cases=(),
        opportunities=(),
        health_scores=tuple(health_scores),
        ctas=(),
        success_plans=(),
        adoption_summaries=tuple(adoption_summaries),
        entitlements=tuple(entitlements_list),
        usage_signals=tuple(usage_signals_list),
        milestones=tuple(milestones_list),
    )

