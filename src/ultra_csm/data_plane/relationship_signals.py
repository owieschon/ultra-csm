"""Job-change fixture rows (Universe v2, WS-Data-Classes Phase 6).

``JobChangeSignal`` (the dataclass) now lives in ``data_plane/contracts.py``
(architecture cleanup, report 42) -- moved out of this module because
``value_model.py`` (the deterministic core) imports it directly via
``_champion_departed_factor`` (Harvest 16's person layer), and a
deterministic-core dependency has no business transitively pulling in this
module's fixture/bible imports (``fixtures.py``, ``narrative_shared.py``,
``pinnacle_comms.py``, ``trailhead_comms.py``). This module now only owns
the actual fixture rows below, importing the type back from ``contracts.py``.

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

Consumed since Harvest 16 (#48): ``value_model._champion_departed_factor``
reads these rows via ``agent1/sweep.py``'s ``_person_layer_inputs`` ->
``data_plane/fixtures.py``'s ``FixtureCRMDataConnector.list_job_changes``.
No longer dormant -- see docs/PROGRAM_REPORT_12.md's original Owner Ask and
docs/PROGRAM_REPORT_42.md for how it was resolved.
"""

from __future__ import annotations

from ultra_csm.data_plane.contracts import JobChangeSignal, JobChangeType
from ultra_csm.data_plane.fixtures import det_id
from ultra_csm.data_plane.narrative_shared import rfc3339
from ultra_csm.data_plane.pinnacle_comms import DEREK_CONTACT_ID, PINNACLE_ACCOUNT_ID
from ultra_csm.data_plane.trailhead_comms import TRAILHEAD_ACCOUNT_ID

__all__ = [
    "JobChangeSignal",
    "JobChangeType",
    "MIKE_LINDGREN_CONTACT_ID",
    "DEREK_VAUGHN_DEPARTURE",
    "MIKE_LINDGREN_PROMOTION",
    "SIGNALS",
    "job_change_signals_as_of",
]

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
