"""Full email bodies for the Pinehill Transport onboarding-stall arc.

Keyed by the ``(day_offset, hour)`` pair from ``comms_fixtures.py``'s
``_MESSAGE_SCHEDULE`` -- the same key that already uniquely identifies each
scheduled message. Content here is prose only; it must never be read by
``signal_extractor.py`` (headers/ids/status only) or change a single
checkpoint value in ``eval/content_invariance_snapshot.json``.

Canon: docs/SYNTHETIC_UNIVERSE_BIBLE.md's "Canon -- the FleetOps universe"
section. Cast: Dennis Gruber (Operations Director, terse, replies from his
phone between dock shifts) and Marcus Webb (CSM, restates open action items
every message -- a documentation habit from owning the two hardest books).
Error strings quoted below match the bible's error-string canon table
exactly, for Phase E's cross-channel check to verify against.
"""

from __future__ import annotations

BODIES: dict[tuple[int, int], str] = {
    (1, 9): (
        "Dennis,\n\n"
        "Kicking off the Legacy Dispatch Integration phase of your Launch Plan today. "
        "The one blocker we need to scope up front is RouteLedger 5.2 -- your team's "
        "existing dispatch system. We'll need read/write API access to it before "
        "Dispatch Bridge configuration can start.\n\n"
        "Action items:\n"
        "- Pinehill: confirm a named IT contact with RouteLedger admin access -- owner Dennis, needed by June 24.\n"
        "- FleetOps: Grace Okafor (our Dispatch Bridge specialist) will join the first working "
        "session once we have that contact -- owner Grace, no date yet, pending the above.\n\n"
        "Target: 50% of your 50 licensed assets reporting through Live Map by June 28, per the "
        "Launch Plan milestones we agreed at signing.\n\n"
        "Marcus Webb\n"
        "Customer Success Manager, FleetOps Platform"
    ),
    (1, 14): (
        "hey marcus\n\n"
        "sounds good. our it guy is a contractor, name's Raul, i'll get you his email "
        "by end of week. he's the one with the RouteLedger admin login.\n\n"
        "-dennis"
    ),
    (8, 9): (
        "Dennis,\n\n"
        "Quick check-in ahead of Friday's 50%-activation milestone review. As of this morning "
        "we're at 22 of 50 assets reporting through Live Map -- on pace, but I want to flag it "
        "now rather than surprise you Friday.\n\n"
        "Open item from last week: still waiting on Raul's contact info for RouteLedger access "
        "(owner Dennis, was due June 24 -- no pressure, just keeping the thread current).\n\n"
        "Marcus"
    ),
    (8, 15): (
        "yep sent raul's email over separately, sorry that slipped\n\n"
        "we're good for friday\n\n"
        "-d"
    ),
    (22, 9): (
        "Dennis,\n\n"
        "The Dispatch Bridge connection to RouteLedger is failing on the initial handshake. "
        "Grace pulled the connector logs this morning:\n\n"
        "  DISPATCH_BRIDGE_CONNECT_FAILURE: RouteLedger 5.2 SOAP endpoint refused connection "
        "(fault code AUTH-401, host dispatch.pinehill-transport.internal:8443)\n\n"
        "This reads like the service account credentials Raul provisioned don't have the SOAP "
        "endpoint permission enabled on RouteLedger's side -- can your IT team check the account's "
        "role assignment? We're blocked on Dispatch Bridge configuration until this clears.\n\n"
        "Action items:\n"
        "- Pinehill: have Raul check the service account's RouteLedger role -- owner Dennis, needed this week.\n"
        "- FleetOps: Grace standing by to retest as soon as the role is updated -- owner Grace, no date, pending above.\n\n"
        "Marcus"
    ),
    (23, 15): (
        "will loop in raul, he's swamped this week (contractor, splits time with two other "
        "clients) but i'll push him\n\n"
        "-dennis"
    ),
    (32, 9): (
        "Dennis,\n\n"
        "Following up on the AUTH-401 case -- it's now been open since June 21 with no movement "
        "from Raul's side. I know he's stretched thin, but this is the one thing blocking the "
        "entire Integration & Data Setup phase.\n\n"
        "Would it help if Grace got on a short call directly with Raul, rather than routing "
        "through you? Sometimes it's faster contractor-to-contractor on the specifics.\n\n"
        "Action items (unchanged from last week, restating since they're still open):\n"
        "- Pinehill: Raul to check/update the service account's RouteLedger role.\n"
        "- FleetOps: Grace standing by to retest.\n\n"
        "Marcus"
    ),
    (34, 11): (
        "sorry for the delay. yes let's do grace + raul directly, i'll set it up. "
        "it people are still looking into it on our end too\n\n"
        "-d"
    ),
    (60, 9): (
        "Dennis,\n\n"
        "This is the third distinct Dispatch Bridge flare-up this month -- the original AUTH-401 "
        "handshake issue never fully resolved, and now we're also seeing intermittent timeouts on "
        "top of it:\n\n"
        "  DISPATCH_BRIDGE_TIMEOUT: upstream RouteLedger socket closed after 30000ms "
        "(job batch 4417, retry_count=3)\n\n"
        "I'd rather get 30 minutes with you and Raul together than keep going back and forth over "
        "email on each new symptom. Can we find time this week?\n\n"
        "Action items:\n"
        "- Pinehill: confirm a 30-minute slot this week with Raul -- owner Dennis.\n"
        "- FleetOps: Grace to bring a full timeline of both the AUTH-401 and timeout symptoms to that call.\n\n"
        "Marcus"
    ),
    (63, 15): (
        "apologies, been heads down on our end (peak shipping week). let's find time next week, "
        "i'll send a couple slots\n\n"
        "-dennis"
    ),
    (85, 9): (
        "Dennis,\n\n"
        "The Dispatch Bridge connector is still dropping events even after last week's retry-timeout "
        "fix -- this is worse than the earlier symptoms, not better, and I think we need to escalate "
        "on both sides rather than keep iterating over email:\n\n"
        "  DISPATCH_BRIDGE_EVENT_LOSS: 214 of 1,880 dispatch events unacknowledged in trailing 24h "
        "window (RouteLedger ack timeout, queue=pinehill-dispatch-out)\n\n"
        "That's about 11% of your dispatch events not making it through, which is well past the "
        "point where I'm comfortable calling this an intermittent issue. I'm escalating internally "
        "to get a senior engineer on this alongside Grace.\n\n"
        "Action items:\n"
        "- Pinehill: escalating to Raul's manager on your end too, per your last note.\n"
        "- FleetOps: Grace + senior engineer to isolate the ack-timeout root cause -- owner Grace, target this week.\n\n"
        "Marcus"
    ),
    (87, 21): (
        "understood, escalating on our side too. raul's manager is looping in a "
        "second contractor who actually built the original routeledger integration "
        "years ago, might know something we don't\n\n"
        "-dennis"
    ),
    (275, 9): (
        "Dennis,\n\n"
        "Wanted to check in now that the Dispatch Bridge connection has been steady for a while -- "
        "no event-loss, no timeouts, no open cases on the integration side since the September fix. "
        "Nice change from where we were over the summer.\n\n"
        "How's the team finding day-to-day usage now that it's not fighting the connector?\n\n"
        "Marcus"
    ),
    (275, 15): (
        "yeah quiet on our end too, appreciate you guys sticking with it through the summer, "
        "that was a rough stretch\n\n"
        "-d"
    ),
    (295, 9): (
        "Dennis,\n\n"
        "Sending over the agenda for next week's steady-state review -- this is the call where we "
        "formally move Pinehill from onboarding into steady-state, since Live Map and Route "
        "Optimizer are both fully activated and the Dispatch Bridge connection has held for months.\n\n"
        "Agenda: (1) final activation numbers, (2) handoff of day-to-day ownership from the "
        "onboarding team to my ongoing CSM coverage, (3) anything on your roadmap for next year.\n\n"
        "Marcus"
    ),
    (295, 14): (
        "looks good, see you then\n\n"
        "-dennis"
    ),
    (305, 9): (
        "Dennis,\n\n"
        "Wanted to flag directly: the Legacy Dispatch Integration has now been fully stable for two "
        "weeks straight, zero dropped events. After everything it took to get here -- the AUTH-401 "
        "handshake issue, the timeouts, the event loss -- I wanted to say it before the steady-state "
        "review makes it official: nice work getting through that with us.\n\n"
        "Marcus"
    ),
    (306, 12): (
        "fantastic. genuinely appreciate you and grace sticking with this one, know it "
        "dragged on longer than either of us wanted\n\n"
        "-dennis"
    ),
}
