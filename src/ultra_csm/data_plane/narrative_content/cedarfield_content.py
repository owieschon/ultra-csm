"""Full email bodies for Cedarfield Industrial Supply's routine health
check-in.

Keyed by ``(day_offset, hour)`` from ``cedarfield_comms.py``'s
``_MESSAGE_SCHEDULE``. Cast: Alex Foster (Facilities Manager, Cedarfield's
sole contact, real synthetic_book.py row), Marcus Webb (senior CSM, csm102
-- the same CSM persona used in comms_fixtures.py/aspenridge_comms.py).
Cedarfield has no scripted arc: this is a routine, unremarkable check-in
consistent with its single ``health_yellow`` factor -- no invented case,
no invented urgency.
"""

from __future__ import annotations

BODIES: dict[tuple[int, int], str] = {
    (64, 9): (
        "Alex,\n\n"
        "Wanted to touch base -- Cedarfield's health score has drifted into the yellow band "
        "recently. Nothing alarming from our side, just want to make sure things are still "
        "working the way your team needs.\n\n"
        "Marcus Webb\n"
        "Customer Success Manager, FleetOps Platform"
    ),
    (65, 15): (
        "Thanks for checking in. Honestly nothing new on our end -- a couple of the newer "
        "features just haven't made it onto anyone's radar yet, that's probably most of it.\n\n"
        "Alex Foster\n"
        "Facilities Manager, Cedarfield Industrial Supply"
    ),
    (66, 9): (
        "Makes sense, thanks for the context. I'll put together a short rundown of what's "
        "available and send it over -- no pressure to act on it, just so it's visible.\n\n"
        "Marcus Webb\n"
        "Customer Success Manager, FleetOps Platform"
    ),
}
