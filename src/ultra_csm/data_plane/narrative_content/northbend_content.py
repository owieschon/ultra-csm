"""Full email bodies for Northbend Haulage's routine health check-in.

Keyed by ``(day_offset, hour)`` from ``northbend_comms.py``'s
``_MESSAGE_SCHEDULE``. Cast: Jordan Cole (Fleet Manager, Northbend's sole
contact, real synthetic_book.py row), Priya Nandan (senior CSM, csm101 --
the same CSM persona used in pinnacle_comms.py/meridian_comms.py/
trailhead_comms.py). Northbend has no scripted arc: this is a routine,
unremarkable check-in consistent with its single ``health_yellow``
factor -- no invented case, no invented urgency.
"""

from __future__ import annotations

BODIES: dict[tuple[int, int], str] = {
    (58, 9): (
        "Jordan,\n\n"
        "Following up on Northbend's health score -- it's been sitting in the yellow band for a "
        "bit. Nothing that's raised a flag on our end, just wanted to check in and see if there's "
        "anything on your side we should know about.\n\n"
        "Priya Nandan\n"
        "Customer Success Manager, FleetOps Platform"
    ),
    (59, 11): (
        "Appreciate you flagging it. Nothing specific -- we've had a couple of drivers out and "
        "usage has dipped a little as a result, should even back out soon.\n\n"
        "Jordan Cole\n"
        "Fleet Manager, Northbend Haulage"
    ),
}
