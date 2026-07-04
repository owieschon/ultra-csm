"""Full email bodies for the Quarrystone Logistics churn-brewing arc.

Keyed by ``(day_offset, hour)`` from ``quarrystone_comms.py``'s
``_MESSAGE_SCHEDULE``. Canon: docs/SYNTHETIC_UNIVERSE_BIBLE.md. Cast: Tim
Kowalczyk (Operations Manager, the account's sole contact, already going
quiet) and Devon Ellis (newer CSM, csm104). Deliberately thin -- this arc's
entire point is absence, so unlike every other arc's content this is NOT
enriched with additional texture beyond a real, complete two-message
handoff exchange. Volume must stay at exactly 2 messages; see the bible's
"brewing... is entirely absence" framing.
"""

from __future__ import annotations

BODIES: dict[tuple[int, int], str] = {
    (0, 9): (
        "Tim,\n\n"
        "Following up on the admin access transfer case -- our records still show you as the "
        "sole account admin on Live Map. Can you confirm who should take over as the point of "
        "contact going forward? I want to make sure whoever it is gets set up correctly rather "
        "than losing continuity on the account.\n\n"
        "Devon Ellis\n"
        "Customer Success Manager, FleetOps Platform"
    ),
    (0, 16): (
        "still sorting out the transition on our end, will follow up soon\n\n"
        "Tim"
    ),
}
