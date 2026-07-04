"""Content-invariance gate for Program 8 (Universe Deepening).

Every extractor in ``signal_extractor.py`` reads only headers (From/To/
Date/Subject), message/event ids, and status fields -- never email body
text or calendar descriptions (verified by inspection of
``signal_extractor.py`` and every ``*_comms.py`` module before this script
was written). This script serializes the full set of extracted signals the
narrative battery depends on, at every bible checkpoint day, for all six
narrative arcs plus Pinehill's Rocketlane TTV bridge. Content authored in
Program 8 (Phases C-E) must not change a single byte of this snapshot;
``--check`` fails loudly if it does.

Phase F (density expansion) is the one sanctioned exception: it may
regenerate this snapshot exactly once, in the same commit as a bible change
explaining why the world changed, per docs/SYNTHETIC_UNIVERSE_BIBLE.md's
anti-Goodhart rule.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ultra_csm.data_plane.aspenridge_comms import (
    aspenridge_cases_as_of,
    aspenridge_communication_signals,
    aspenridge_stakeholder_relationships,
)
from ultra_csm.data_plane.aspenridge_comms import (
    aspenridge_calendar_events as _aspenridge_calendar_events,
)
from ultra_csm.data_plane.comms_fixtures import (
    pinehill_calendar_events,
    pinehill_cases_as_of,
    pinehill_communication_signals,
    pinehill_stakeholder_relationships,
)
from ultra_csm.data_plane.fixtures import account_id_for
from ultra_csm.data_plane.meridian_comms import (
    meridian_calendar_events,
    meridian_cases_as_of,
    meridian_communication_signals,
    meridian_stakeholder_relationships,
)
from ultra_csm.data_plane.pinnacle_comms import (
    pinnacle_calendar_events,
    pinnacle_cases_as_of,
    pinnacle_communication_signals,
    pinnacle_stakeholder_relationships,
)
from ultra_csm.data_plane.quarrystone_comms import (
    quarrystone_calendar_events,
    quarrystone_cases_as_of,
    quarrystone_communication_signals,
    quarrystone_stakeholder_relationships,
)
from ultra_csm.data_plane.rocketlane_fixtures import has_activation_gap, pinehill_onboarding_fixture_data
from ultra_csm.data_plane.signal_extractor import (
    meeting_cadence_shift,
    reply_latency_trend,
    thread_participation_width,
    ticket_frequency_window,
)
from ultra_csm.data_plane.synthetic_book import SEED_DATE
from ultra_csm.data_plane.trailhead_comms import (
    trailhead_calendar_events,
    trailhead_cases_as_of,
    trailhead_communication_signals,
    trailhead_stakeholder_relationships,
)

SNAPSHOT_PATH = Path(__file__).with_name("content_invariance_snapshot.json")

# (slug, comms_fn, relationships_fn, calendar_fn, cases_fn, checkpoint_days)
# Checkpoint days are docs/SYNTHETIC_UNIVERSE_BIBLE.md's own named
# checkpoints per arc -- the same days narrative_battery.py asserts against.
ARCS: tuple[tuple[str, Any, Any, Any, Any, tuple[int, ...]], ...] = (
    ("pinehill-transport", pinehill_communication_signals, pinehill_stakeholder_relationships,
     pinehill_calendar_events, pinehill_cases_as_of, (20, 50, 310)),
    ("pinnacle-supply", pinnacle_communication_signals, pinnacle_stakeholder_relationships,
     pinnacle_calendar_events, pinnacle_cases_as_of, (10, 120, 250)),
    ("quarrystone-logistics", quarrystone_communication_signals, quarrystone_stakeholder_relationships,
     quarrystone_calendar_events, quarrystone_cases_as_of, (30, 190, 225)),
    ("aspenridge-supply", aspenridge_communication_signals, aspenridge_stakeholder_relationships,
     _aspenridge_calendar_events, aspenridge_cases_as_of, (90, 200, 340)),
    ("meridian-fleet", meridian_communication_signals, meridian_stakeholder_relationships,
     meridian_calendar_events, meridian_cases_as_of, (20, 170, 280)),
    ("trailhead-logistics", trailhead_communication_signals, trailhead_stakeholder_relationships,
     trailhead_calendar_events, trailhead_cases_as_of, (60, 180, 300)),
)


def _as_of(day_offset: int) -> str:
    return (date.fromisoformat(SEED_DATE) + timedelta(days=day_offset)).isoformat()


def _signal_dict(account_id: str, comms_fn, rels_fn, cal_fn, cases_fn, day_offset: int) -> dict[str, Any]:
    as_of = _as_of(day_offset)
    signals = comms_fn(day_offset)
    rels = rels_fn(day_offset)
    calendar = cal_fn(day_offset)
    cases = cases_fn(day_offset)
    return {
        "latency": asdict(reply_latency_trend(account_id, signals, as_of=as_of)),
        "width": asdict(thread_participation_width(account_id, rels, as_of=as_of)),
        "cadence": asdict(meeting_cadence_shift(account_id, calendar, as_of=as_of)),
        "tickets": asdict(ticket_frequency_window(account_id, cases, as_of=as_of)),
        "relationship_strengths": sorted(
            [{"contact_id": r.contact_id, "strength": r.strength, "multi_thread_depth": r.multi_thread_depth}
             for r in rels],
            key=lambda r: r["contact_id"],
        ),
        "case_count": len(cases),
        "case_subjects": sorted(c.subject for c in cases),
    }


def _pinehill_rocketlane(day_offset: int) -> dict[str, Any]:
    as_of = _as_of(day_offset)
    onboarding = pinehill_onboarding_fixture_data(day_offset)
    gaps = {
        phase.name: has_activation_gap(phase, onboarding.projects[0], onboarding.tasks, as_of=as_of)
        for phase in onboarding.phases
    }
    return {"activation_gaps": gaps}


def build_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {"arcs": {}}
    for slug, comms_fn, rels_fn, cal_fn, cases_fn, checkpoints in ARCS:
        account_id = account_id_for(slug)
        arc_snapshot: dict[str, Any] = {}
        for day in checkpoints:
            entry = _signal_dict(account_id, comms_fn, rels_fn, cal_fn, cases_fn, day)
            if slug == "pinehill-transport":
                entry["rocketlane"] = _pinehill_rocketlane(day)
            arc_snapshot[str(day)] = entry
        snapshot["arcs"][slug] = arc_snapshot
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="compare against the committed snapshot instead of writing it")
    args = parser.parse_args(argv)

    current = build_snapshot()
    current_text = json.dumps(current, indent=2, sort_keys=True, default=str) + "\n"

    if args.check:
        if not SNAPSHOT_PATH.exists():
            print(f"FAIL: no snapshot at {SNAPSHOT_PATH}")
            return 1
        committed_text = SNAPSHOT_PATH.read_text(encoding="utf-8")
        if current_text != committed_text:
            print(f"FAIL: content_invariance_snapshot.json does not match current extractor output.")
            print("A content change altered a scored signal. Revert the content change --")
            print("do NOT regenerate this snapshot except in Phase F, in the same commit as a")
            print("bible change explaining why the world changed.")
            return 1
        print("PASS: extractor output is byte-identical to the committed snapshot.")
        return 0

    SNAPSHOT_PATH.write_text(current_text, encoding="utf-8")
    print(f"wrote {SNAPSHOT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
