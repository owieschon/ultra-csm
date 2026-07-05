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
    # Density D2.2 (Program 19): benign scheduling/recap/FYI filler, Monica
    # thread only (Derek never replies again -- no Derek message added). See
    # docs/PROGRAM_REPORT_19.md and the bible's density subsection.
    (118, 9): (
        "Monica,\n\n"
        "No action needed, just confirming the activation review slot is still good for next "
        "week on your calendar.\n\n"
        "Priya"
    ),
    (118, 14): (
        "Still good on my end, see you then.\n\n"
        "Monica"
    ),
    (145, 9): (
        "Monica,\n\n"
        "Quick recap from last week's activation review -- appreciate you and your team getting "
        "up to speed so fast on the entitled modules.\n\n"
        "Priya"
    ),
    (145, 13): (
        "Thanks, appreciate the recap. Next step on my end: still confirming the Dispatch "
        "Automation owner, will follow up once I have a name.\n\n"
        "Monica"
    ),
    (160, 9): (
        "Monica,\n\n"
        "Checking in ahead of our next sync -- anything you want added to the agenda on the "
        "Fuel Analytics adoption front?\n\n"
        "Priya"
    ),
    (160, 12): (
        "Nothing to add yet, still tracking it internally. Next step on my end: bring numbers to "
        "the next sync.\n\n"
        "Monica"
    ),
    (185, 9): (
        "Monica,\n\n"
        "Recap from today's sync -- Fuel Analytics adoption is trending the right direction, "
        "nothing else to flag.\n\n"
        "Priya"
    ),
    (185, 11): (
        "Good to hear. Next step on my end: keep monitoring and report back at the renewal-prep "
        "conversation.\n\n"
        "Monica"
    ),
    (200, 9): (
        "Monica,\n\n"
        "No urgent items, just a quick FYI that we're starting to pull together renewal-prep "
        "materials ahead of the conversation we scheduled.\n\n"
        "Priya"
    ),
    (200, 13): (
        "Appreciate the heads up, will do the same on my side.\n\n"
        "Monica"
    ),
    (225, 9): (
        "Monica,\n\n"
        "Quick recap from the renewal-prep conversation -- usage read looked strong across the "
        "board, nothing that changes our approach heading into the QBR.\n\n"
        "Priya"
    ),
    (225, 12): (
        "Agreed, matches what I saw on my end too. Next step on my end: finalize the usage numbers "
        "before the QBR.\n\n"
        "Monica"
    ),
    (238, 9): (
        "Monica,\n\n"
        "Sending over the QBR agenda for next week -- same format as last quarter, all five "
        "modules.\n\n"
        "Priya"
    ),
    (238, 14): (
        "Looks good, see you then. Next step on my end: loop in my team lead for the Insights Hub "
        "portion.\n\n"
        "Monica"
    ),
}
