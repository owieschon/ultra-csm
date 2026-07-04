"""Full email bodies for the Pinnacle Supply Chain single-threaded-risk arc.

Keyed by ``(day_offset, hour)`` from ``pinnacle_comms.py``'s
``_MESSAGE_SCHEDULE``. Canon: docs/SYNTHETIC_UNIVERSE_BIBLE.md. Cast: Derek
Vaughn (Director of Operations, original champion, goes quiet day 3 per the
existing ``ChampionGoesQuiet`` mutation), Monica Reeves (VP Supply Chain
Operations, the replacement champion who appears day 110 per the existing
``NewContactAppears`` event -- methodical, always restates next steps), and
Priya Nandan (senior CSM, csm101). This account's risk is relational, not
technical -- no legacy-integration story is referenced here, unlike
Pinehill.
"""

from __future__ import annotations

BODIES: dict[tuple[int, int], str] = {
    (1, 9): (
        "Derek,\n\n"
        "Looking forward to our quarterly ops review next week -- excited to get Pinnacle fully "
        "ramped across Live Map, Route Optimizer, Insights Hub, Fuel Analytics, and Dispatch "
        "Automation.\n\n"
        "Priya Nandan\n"
        "Customer Success Manager, FleetOps Platform"
    ),
    (1, 13): (
        "Sounds good, see you then.\n\n"
        "Derek Vaughn\n"
        "Director of Operations, Pinnacle Supply Chain"
    ),
    (110, 9): (
        "Monica,\n\n"
        "Introducing myself as your CSM contact going forward -- I understand Derek has moved on "
        "from the account, so wanted to make sure you have a direct line to me and full context "
        "on where things stand across Pinnacle's FleetOps modules.\n\n"
        "Priya Nandan\n"
        "Customer Success Manager, FleetOps Platform"
    ),
    (112, 20): (
        "Thanks for reaching out, still getting oriented on my end -- appreciate you being "
        "patient while I get up to speed on what Pinnacle actually has running today.\n\n"
        "Monica Reeves\n"
        "VP Supply Chain Operations, Pinnacle Supply Chain"
    ),
    (135, 9): (
        "Monica,\n\n"
        "Sending over the activation review agenda for this week -- we'll walk through current "
        "usage across all five entitled modules and flag anything that's lapsed since the "
        "transition.\n\n"
        "Priya"
    ),
    (136, 15): (
        "Looks good, appreciate you putting this together. Next steps on my end: confirm who on "
        "my team owns day-to-day Dispatch Automation usage, and come prepared with questions on "
        "Insights Hub reporting.\n\n"
        "Monica"
    ),
    (170, 9): (
        "Monica,\n\n"
        "Wanted to check in on how the rollout is progressing on your side since the activation "
        "review.\n\n"
        "Priya"
    ),
    (170, 13): (
        "Going well, team's fully ramped now across all the modules we walked through. Next step "
        "on my end: keep an eye on Fuel Analytics adoption specifically, that was the one lagging "
        "behind.\n\n"
        "Monica"
    ),
    (210, 9): (
        "Monica,\n\n"
        "Starting renewal prep conversations a bit early this cycle, given the leadership change "
        "earlier in the year -- want to make sure the renewal reflects where the account actually "
        "stands today.\n\n"
        "Priya"
    ),
    (210, 12): (
        "Great, let's get time on the calendar. Next step on my end: pull together our own usage "
        "read before we talk, so I'm not just reacting to your numbers.\n\n"
        "Monica"
    ),
    (245, 9): (
        "Monica,\n\n"
        "Recap from today's QBR -- great momentum across the board since you took over the "
        "account, all five modules showing healthy usage.\n\n"
        "Priya"
    ),
    (245, 12): (
        "Agreed, really pleased with where things stand. Next step on my end: loop my team in on "
        "the Insights Hub dashboard changes we discussed before next quarter's review.\n\n"
        "Monica"
    ),
}
