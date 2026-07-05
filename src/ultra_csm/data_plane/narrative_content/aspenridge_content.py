"""Full email bodies for the Aspenridge Supply Chain silent-decline arc.

Keyed by ``(day_offset, hour)`` from ``aspenridge_comms.py``'s
``_MESSAGE_SCHEDULE``. Canon: docs/SYNTHETIC_UNIVERSE_BIBLE.md. Cast:
Christine Yoder (Fleet Administrator, calm, always replies same-day) and
Marcus Webb (CSM). This account's entitlements are Live Map + Route
Optimizer only (`synthetic_book.py`) -- content here deliberately never
mentions a module this account hasn't purchased. The point of this arc is
that every artifact reads calm; usage decline is real but lives only in
telemetry this module never touches.
"""

from __future__ import annotations

BODIES: dict[tuple[int, int], str] = {
    (1, 9): (
        "Christine,\n\n"
        "Sending over the agenda ahead of our Q1 business review next week: Live Map asset "
        "coverage, Route Optimizer usage, and anything on your side for the rest of the quarter. "
        "Nothing unusual to flag from our end going in.\n\n"
        "Marcus Webb\n"
        "Customer Success Manager, FleetOps Platform"
    ),
    (1, 13): (
        "Looks good, see you then.\n\n"
        "Christine Yoder\n"
        "Fleet Administrator, Aspenridge Supply Chain"
    ),
    (91, 9): (
        "Christine,\n\n"
        "Sending over the agenda ahead of our Q2 business review next week -- same format as "
        "last quarter, Live Map coverage and Route Optimizer usage. Let me know if anything on "
        "your end needs a slot on the agenda.\n\n"
        "Marcus"
    ),
    (91, 12): (
        "Thanks, agenda works fine for our team, nothing to add this quarter.\n\n"
        "Christine"
    ),
    (181, 9): (
        "Christine,\n\n"
        "Sending over the agenda ahead of our Q3 business review next week -- same format, "
        "Live Map and Route Optimizer.\n\n"
        "Marcus"
    ),
    (181, 14): (
        "Sounds good, nothing new to flag on our end this quarter either.\n\n"
        "Christine"
    ),
    (271, 9): (
        "Christine,\n\n"
        "Sending over the agenda ahead of our Q4 business review next week -- same format as the "
        "year so far.\n\n"
        "Marcus"
    ),
    (271, 11): (
        "Works for us, talk then.\n\n"
        "Christine"
    ),
    (361, 9): (
        "Christine,\n\n"
        "Sending over the agenda ahead of our year-end review next week -- we'll cover the full "
        "year of Live Map and Route Optimizer usage plus anything you'd like on the agenda for "
        "next year's planning.\n\n"
        "Marcus"
    ),
    (361, 15): (
        "Appreciate the heads up, see you at the review.\n\n"
        "Christine Yoder\n"
        "Fleet Administrator, Aspenridge Supply Chain"
    ),
    # Density D2.1 (Program 19): benign recap/FYI/scheduling filler, same
    # "calm, prompt, one contact" cadence as the existing QBR pairs -- no
    # new plot beat, no new participant. See docs/PROGRAM_REPORT_19.md and
    # docs/SYNTHETIC_UNIVERSE_BIBLE.md's density subsection for placement.
    (5, 10): (
        "Christine,\n\n"
        "Quick recap from Tuesday's Q1 review -- Live Map coverage and Route Optimizer usage both "
        "holding steady, nothing on our end needs follow-up. Thanks for the time.\n\n"
        "Marcus"
    ),
    (5, 14): (
        "Thanks for the recap, matches what we discussed.\n\n"
        "Christine"
    ),
    (45, 9): (
        "Christine,\n\n"
        "No urgent items, just checking in on scheduling -- want to keep the Q2 review on the "
        "calendar for the usual week, or is there a better slot with your team's spring routing "
        "changes?\n\n"
        "Marcus"
    ),
    (45, 13): (
        "Usual week works fine, no changes needed on our end.\n\n"
        "Christine"
    ),
    (95, 10): (
        "Christine,\n\n"
        "Quick recap from the Q2 review -- same steady picture as last quarter, no open items on "
        "either side.\n\n"
        "Marcus"
    ),
    (95, 15): (
        "Agreed, appreciate the recap.\n\n"
        "Christine"
    ),
    (135, 9): (
        "Christine,\n\n"
        "Just confirming the Q3 review slot is still good for you -- no agenda changes on our end.\n\n"
        "Marcus"
    ),
    (135, 12): (
        "Still good, thanks for confirming.\n\n"
        "Christine"
    ),
    (185, 9): (
        "Christine,\n\n"
        "Recap from Tuesday's Q3 review -- steady quarter, Live Map and Route Optimizer usage both "
        "in line with prior quarters, nothing flagged on either side.\n\n"
        "Marcus"
    ),
    (185, 13): (
        "Thanks Marcus, all good from our end too.\n\n"
        "Christine"
    ),
    (275, 10): (
        "Christine,\n\n"
        "Recap from the Q4 review -- another steady quarter, no open items. Appreciate the "
        "consistency on your team's side.\n\n"
        "Marcus"
    ),
    (275, 14): (
        "Likewise, appreciate you keeping these efficient.\n\n"
        "Christine"
    ),
    (363, 9): (
        "Christine,\n\n"
        "Quick recap from the year-end review -- thanks again for the time, and for a genuinely "
        "low-drama year on the account side. Looking forward to next year's planning.\n\n"
        "Marcus"
    ),
    (363, 12): (
        "Likewise, thanks for a smooth year, Marcus.\n\n"
        "Christine Yoder\n"
        "Fleet Administrator, Aspenridge Supply Chain"
    ),
}
