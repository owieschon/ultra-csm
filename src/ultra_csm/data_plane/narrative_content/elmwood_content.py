"""Full email bodies for Elmwood Trucking's routine health check-in.

Keyed by ``(day_offset, hour)`` from ``elmwood_comms.py``'s
``_MESSAGE_SCHEDULE``. Cast: Sam Foster (Dispatch Lead, Elmwood's sole
contact, real synthetic_book.py row), Marcus Webb (senior CSM, csm102 --
the same CSM persona used in comms_fixtures.py/aspenridge_comms.py/
cedarfield_comms.py). Elmwood has no scripted arc: this is a routine,
unremarkable check-in consistent with its single ``health_yellow``
factor -- no invented case, no invented urgency.
"""

from __future__ import annotations

BODIES: dict[tuple[int, int], str] = {
    (67, 9): (
        "Sam,\n\n"
        "Noticed Elmwood's health score has been in the yellow band for a bit -- nothing that's "
        "raised any flags on our end, just wanted to check in and see how things are going day "
        "to day.\n\n"
        "Marcus Webb\n"
        "Customer Success Manager, FleetOps Platform"
    ),
    (68, 13): (
        "Appreciate the check-in. Nothing specific going on -- dispatch has just been busy this "
        "stretch and some of the reporting hasn't gotten looked at as closely as usual.\n\n"
        "Sam Foster\n"
        "Dispatch Lead, Elmwood Trucking"
    ),
}
