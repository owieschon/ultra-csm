"""Full email bodies for Cobalt Fleet Ops's routine health check-in.

Keyed by ``(day_offset, hour)`` from ``cobalt_comms.py``'s
``_MESSAGE_SCHEDULE``. Cast: Sam Turner (Operations Manager, Cobalt's sole
contact, real synthetic_book.py row), Devon Ellis (senior CSM, csm104 --
the same CSM persona used in quarrystone_comms.py). Cobalt has no scripted
arc: this is a routine, unremarkable check-in consistent with its single
``health_yellow`` factor -- no invented case, no invented urgency.
"""

from __future__ import annotations

BODIES: dict[tuple[int, int], str] = {
    (60, 9): (
        "Sam,\n\n"
        "Wanted to check in -- noticed Cobalt's health score has been sitting in the yellow band "
        "the last little while. Nothing urgent on our end, just want to make sure everything's "
        "working the way you need it to. Anything we should be looking at together?\n\n"
        "Devon Ellis\n"
        "Customer Success Manager, FleetOps Platform"
    ),
    (61, 14): (
        "Thanks for reaching out. Nothing major -- dispatch has been a bit slower to adopt some "
        "of the newer routing suggestions, but the core stuff is working fine day to day.\n\n"
        "Sam Turner\n"
        "Operations Manager, Cobalt Fleet Ops"
    ),
    (62, 10): (
        "Good to know, appreciate the update. Happy to set up a short walkthrough on the routing "
        "suggestions whenever it's useful -- no rush, just say the word.\n\n"
        "Devon Ellis\n"
        "Customer Success Manager, FleetOps Platform"
    ),
}
