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
}
