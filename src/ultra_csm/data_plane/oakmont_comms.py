"""Oakmont Logistics -- new-stakeholder-unengaged arc (Harvest 16).

Companion to docs/SYNTHETIC_UNIVERSE_BIBLE.md's "New-stakeholder-unengaged"
section. Oakmont is one of the 27 "boring controls" (steady_state, green,
high_usage) -- ``check_boring_controls`` (eval/narrative_battery.py) only
asserts no *case* content leaks onto boring controls, so adding a
``StakeholderRelationship`` row here does not perturb any existing
assertion. No email/calendar module is authored for this arc deliberately:
the story IS the absence of engagement, so there is no comms exhaust to
model -- only the stakeholder-role row a real CRM sync would produce when
an admin is added to the account.

Deterministic, no randomness: a single frozen row, present from
``ADMIN_APPEARS_DAY`` onward, that never gains a matching
``CommunicationSignal`` at any checkpoint (there is no
``oakmont_communication_signals`` reader -- the comms list this factor
checks against is always empty for this account, by construction).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ultra_csm.data_plane.contracts import StakeholderRelationship
from ultra_csm.data_plane.fixtures import account_id_for, det_id

OAKMONT_ACCOUNT_ID = account_id_for("oakmont-logistics")
OAKMONT_NEW_ADMIN_CONTACT_ID = det_id(
    "contact", OAKMONT_ACCOUNT_ID, "priya.subramaniam@oakmont-logistics.example"
)

# Day the admin stakeholder first appears in the CRM sync -- inside the
# new_stakeholder_window_days config default (30) at every checkpoint this
# arc is read at, per docs/SYNTHETIC_UNIVERSE_BIBLE.md.
ADMIN_APPEARS_DAY = 70


def _rfc3339(day_offset: int, hour: int = 9) -> str:
    dt = datetime(2026, 6, 21, tzinfo=timezone.utc) + timedelta(days=day_offset, hours=hour - 9)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def oakmont_stakeholder_relationships(as_of_day: int) -> list[StakeholderRelationship]:
    """Priya Subramaniam (Admin) is added to the CRM at day 70 -- a
    system-of-record sync, not a real engagement -- and her
    ``last_interaction`` is frozen at that add date for the rest of the
    simulation (no meeting, no reply, ever). Width alone reads as a control
    (Oakmont has no comms module to move it); this row exists purely to
    exercise ``new_stakeholder_unengaged``.
    """

    if as_of_day < ADMIN_APPEARS_DAY:
        return []
    return [
        StakeholderRelationship(
            account_id=OAKMONT_ACCOUNT_ID,
            contact_id=OAKMONT_NEW_ADMIN_CONTACT_ID,
            relationship_type="admin",
            strength="weak",
            last_interaction=_rfc3339(ADMIN_APPEARS_DAY),
            multi_thread_depth=1,
        )
    ]
