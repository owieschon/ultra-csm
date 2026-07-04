"""Job-change signal class (Universe v2, WS-Data-Classes Phase 6).

``JobChangeSignal`` is a new dataclass -- NOT added to ``contracts.py`` --
representing an enrichment-feed event that would beat silence-detection to
the punch: a contact's departure, promotion, or lateral move surfaced by an
external enrichment source before the CS platform's own comm-cadence
signals would notice anything changed.

Two fixture rows, both hanging on EXISTING bible beats:

* Derek Vaughn's departure at Pinnacle Supply Chain, day 5 -- two days
  after the already-scripted ``ChampionGoesQuiet("pinnacle-supply", 3)``
  mutation. This is the enrichment signal that, if consumed, would have
  flagged the single-threaded-risk arc's root cause on day 5 rather than
  waiting for the health band to move on day 14 or for Monica Reeves to
  appear on day 110 -- exactly the "beats silence-detection to the punch"
  framing the phase spec calls for.
* A benign red-herring signal: Mike Lindgren (Trailhead's secondary
  fleet-utilization contact) gets a same-company promotion at day 200 --
  a title change with no risk, consistent with Trailhead's healthy-control
  arc never having a real signal to surface.

Dormant until a lens/enrichment consumer reads it -- no code path does yet
(see docs/PROGRAM_REPORT_12.md's Owner Ask).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ultra_csm.data_plane.fixtures import det_id
from ultra_csm.data_plane.narrative_shared import rfc3339
from ultra_csm.data_plane.pinnacle_comms import DEREK_CONTACT_ID, PINNACLE_ACCOUNT_ID
from ultra_csm.data_plane.trailhead_comms import TRAILHEAD_ACCOUNT_ID

JobChangeType = Literal["departure", "promotion", "lateral_move"]


@dataclass(frozen=True)
class JobChangeSignal:
    """An enrichment-feed event reporting a contact's job change."""

    signal_id: str
    account_id: str
    contact_id: str
    contact_name: str
    change_type: JobChangeType
    day_offset: int
    observed_at: str
    old_title: str
    new_title: str | None  # None for a departure (no successor title to report)
    same_company: bool
    detail: str


MIKE_LINDGREN_CONTACT_ID = det_id(
    "contact", TRAILHEAD_ACCOUNT_ID, "mike.lindgren@trailhead-logistics.example"
)

DEREK_VAUGHN_DEPARTURE = JobChangeSignal(
    signal_id=det_id("job-change", PINNACLE_ACCOUNT_ID, DEREK_CONTACT_ID, 5),
    account_id=PINNACLE_ACCOUNT_ID,
    contact_id=DEREK_CONTACT_ID,
    contact_name="Derek Vaughn",
    change_type="departure",
    day_offset=5,
    observed_at=rfc3339(5, 8),
    old_title="Director of Operations, Pinnacle Supply Chain",
    new_title=None,
    same_company=False,
    detail=(
        "Enrichment feed reports Derek Vaughn is no longer listed as an employee of "
        "Pinnacle Supply Chain. Two days after his last reply (day 3) -- this signal "
        "would have surfaced the single-threaded-risk arc's root cause on day 5, well "
        "before the day-14 health-band move or the day-110 replacement contact."
    ),
)

MIKE_LINDGREN_PROMOTION = JobChangeSignal(
    signal_id=det_id("job-change", TRAILHEAD_ACCOUNT_ID, MIKE_LINDGREN_CONTACT_ID, 200),
    account_id=TRAILHEAD_ACCOUNT_ID,
    contact_id=MIKE_LINDGREN_CONTACT_ID,
    contact_name="Mike Lindgren",
    change_type="promotion",
    day_offset=200,
    observed_at=rfc3339(200, 8),
    old_title="Fleet Director",
    new_title="Senior Fleet Director",
    same_company=True,
    detail=(
        "Enrichment feed reports a same-company title change for Mike Lindgren -- a "
        "promotion, not a departure. Benign: no risk, consistent with Trailhead's "
        "healthy-control arc never surfacing a real signal at any checkpoint."
    ),
)

# Fixture exhaust, both accounts.
SIGNALS: tuple[JobChangeSignal, ...] = (DEREK_VAUGHN_DEPARTURE, MIKE_LINDGREN_PROMOTION)


def job_change_signals_as_of(account_id: str, as_of_day: int) -> list[JobChangeSignal]:
    """Reader: signals for *account_id* visible on or before *as_of_day*."""

    return [s for s in SIGNALS if s.account_id == account_id and s.day_offset <= as_of_day]
