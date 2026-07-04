"""Meeting-transcript consistency battery (Universe v2, WS-Data-Classes
Phase 2).

Extends ``content_battery.py``'s pattern to the new
``narrative_content.transcripts`` module: the error-string cross-reference
now spans email + case-verbatim + transcript (previously email + case-
verbatim only); a tier/module vocabulary check (no transcript may mention
a module the account isn't entitled to); and an attendee-consistency check
(every transcript's attendee list must be a subset of the underlying
calendar event's actual attendee emails -- the transcript cannot invent a
participant the calendar fixture doesn't have).

Same ``hard_ok`` / two-identical-consecutive-runs pattern as its siblings.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ultra_csm.data_plane.comms_fixtures import pinehill_calendar_events
from ultra_csm.data_plane.meridian_comms import meridian_calendar_events
from ultra_csm.data_plane.narrative_content import transcripts as transcripts_mod
from ultra_csm.data_plane.pinnacle_comms import pinnacle_calendar_events
from ultra_csm.data_plane.trailhead_comms import trailhead_calendar_events

ARTIFACT_PATH = Path(__file__).with_name("transcript_battery.json")

# Pinehill's three canon error strings (docs/SYNTHETIC_UNIVERSE_BIBLE.md's
# error-string canon table) -- the day-57 and day-99 transcripts quote the
# ones relevant to that checkpoint verbatim.
_PINEHILL_ERROR_STRINGS = {
    0: "DISPATCH_BRIDGE_CONNECT_FAILURE: RouteLedger 5.2 SOAP endpoint refused connection "
       "(fault code AUTH-401, host dispatch.pinehill-transport.internal:8443)",
    30: "DISPATCH_BRIDGE_TIMEOUT: upstream RouteLedger socket closed after 30000ms "
        "(job batch 4417, retry_count=3)",
    80: "DISPATCH_BRIDGE_EVENT_LOSS: 214 of 1,880 dispatch events unacknowledged in trailing "
        "24h window (RouteLedger ack timeout, queue=pinehill-dispatch-out)",
}

_ALL_MODULES = (
    "Live Map", "Route Optimizer", "Driver Scorecards", "Maintenance Radar",
    "Insights Hub", "Compliance Center", "Fuel Analytics", "Dispatch Automation",
)

# Actual entitlements per account (synthetic_book.py, cross-checked against
# content_battery.py's _ARC_ENTITLEMENTS table -- not re-derived here, kept
# identical so the two batteries can never silently diverge on canon).
_ACCOUNT_ENTITLEMENTS: dict[str, tuple[str, ...]] = {
    "pinehill-transport": ("Live Map", "Route Optimizer"),
    "meridian-fleet": ("Live Map", "Route Optimizer", "Driver Scorecards", "Maintenance Radar"),
    "trailhead-logistics": ("Live Map", "Route Optimizer", "Insights Hub", "Compliance Center", "Fuel Analytics"),
    "pinnacle-supply": ("Live Map", "Route Optimizer", "Insights Hub", "Fuel Analytics", "Dispatch Automation"),
}

# Maps a transcript's account_id back to its account slug for the
# entitlement lookup above (module-private account ids aren't slug-keyed).
_ACCOUNT_ID_TO_SLUG: dict[str, str] = {}
for _slug in _ACCOUNT_ENTITLEMENTS:
    from ultra_csm.data_plane.fixtures import account_id_for as _account_id_for

    _ACCOUNT_ID_TO_SLUG[_account_id_for(_slug)] = _slug

# Calendar-fixture lookup functions, one per account with a transcript.
_CALENDAR_FNS = {
    "pinehill-transport": pinehill_calendar_events,
    "meridian-fleet": meridian_calendar_events,
    "trailhead-logistics": trailhead_calendar_events,
    "pinnacle-supply": pinnacle_calendar_events,
}


def check(ok: bool, problems: list[str], label: str, detail: Any = None) -> None:
    if not ok:
        problems.append(f"{label}: {detail}" if detail is not None else label)


def check_error_string_cross_reference_spans_transcripts() -> dict[str, Any]:
    """Pinehill's day-57 transcript quotes the day-0/day-30 error strings;
    the day-99 transcript quotes the day-80 one -- extending
    content_battery.py's email+verbatim cross-reference to now also cover
    transcripts."""

    problems: list[str] = []
    detail: dict[str, Any] = {}
    from ultra_csm.data_plane.comms_fixtures import PINEHILL_ACCOUNT_ID
    from ultra_csm.data_plane.fixtures import det_id

    day57_id = det_id("calendar-event", PINEHILL_ACCOUNT_ID, 57)
    day99_id = det_id("calendar-event", PINEHILL_ACCOUNT_ID, 99)
    day57 = transcripts_mod.TRANSCRIPTS[day57_id]
    day99 = transcripts_mod.TRANSCRIPTS[day99_id]

    for day in (0, 30):
        present = _PINEHILL_ERROR_STRINGS[day] in day57.summary
        check(present, problems, f"day57 transcript missing day{day} error string")
        detail[f"day57_has_day{day}"] = present

    present_80 = _PINEHILL_ERROR_STRINGS[80] in day99.summary
    check(present_80, problems, "day99 transcript missing day80 error string")
    detail["day99_has_day80"] = present_80

    return {
        "case": "error_string_cross_reference_spans_transcripts",
        "ok": not problems, "problems": problems, "detail": detail,
    }


def check_transcript_tier_vocabulary() -> dict[str, Any]:
    """No transcript may mention a module the account isn't entitled to."""

    problems: list[str] = []
    detail: dict[str, Any] = {}
    for event_id, t in transcripts_mod.TRANSCRIPTS.items():
        slug = _ACCOUNT_ID_TO_SLUG.get(t.account_id)
        if slug is None:
            continue
        entitled = set(_ACCOUNT_ENTITLEMENTS[slug])
        forbidden = [m for m in _ALL_MODULES if m not in entitled]
        text = t.summary + " ".join(t.decisions) + " ".join(t.actions)
        found_forbidden = sorted({m for m in forbidden if m in text})
        check(not found_forbidden, problems, f"{t.title}: mentions un-entitled module(s)", found_forbidden)
        detail[t.title] = {"entitled": sorted(entitled), "found_forbidden": found_forbidden}
    return {"case": "transcript_tier_vocabulary", "ok": not problems, "problems": problems, "detail": detail}


def check_attendee_consistency_vs_calendar_fixture() -> dict[str, Any]:
    """Every transcript's attendees must be a subset of that event's actual
    calendar-fixture attendee emails -- a transcript cannot invent a
    participant the calendar fixture never scheduled."""

    problems: list[str] = []
    detail: dict[str, Any] = {}
    for event_id, t in transcripts_mod.TRANSCRIPTS.items():
        slug = _ACCOUNT_ID_TO_SLUG.get(t.account_id)
        if slug is None:
            check(False, problems, f"{t.title}: unknown account slug for calendar lookup")
            continue
        cal_fn = _CALENDAR_FNS[slug]
        items = cal_fn(t.day_offset)["items"]
        matching = [it for it in items if it["id"] == event_id]
        if not matching:
            check(False, problems, f"{t.title}: event_det_id not found in calendar fixture as of its own day", event_id)
            continue
        actual_attendees = {a["email"] for a in matching[0]["attendees"]}
        extra = sorted(set(t.attendees) - actual_attendees)
        check(not extra, problems, f"{t.title}: transcript attendees not in calendar fixture", extra)
        detail[t.title] = {"transcript_attendees": sorted(t.attendees), "calendar_attendees": sorted(actual_attendees), "extra": extra}
    return {"case": "attendee_consistency_vs_calendar_fixture", "ok": not problems, "problems": problems, "detail": detail}


def check_every_transcript_keyed_to_a_real_calendar_event() -> dict[str, Any]:
    """Every TRANSCRIPTS key must resolve to a real, existing calendar
    event -- no invented day/event."""

    problems: list[str] = []
    detail: dict[str, Any] = {}
    for event_id, t in transcripts_mod.TRANSCRIPTS.items():
        slug = _ACCOUNT_ID_TO_SLUG.get(t.account_id)
        cal_fn = _CALENDAR_FNS.get(slug) if slug else None
        found = False
        if cal_fn is not None:
            items = cal_fn(t.day_offset)["items"]
            found = any(it["id"] == event_id for it in items)
        check(found, problems, f"{t.title}: transcript key does not resolve to a real calendar event")
        detail[t.title] = found
    return {"case": "every_transcript_keyed_to_a_real_calendar_event", "ok": not problems, "problems": problems, "detail": detail}


CASES = (
    check_error_string_cross_reference_spans_transcripts,
    check_transcript_tier_vocabulary,
    check_attendee_consistency_vs_calendar_fixture,
    check_every_transcript_keyed_to_a_real_calendar_event,
)


def run_battery() -> dict[str, Any]:
    results = [fn() for fn in CASES]
    return {
        "artifact": "transcript_consistency_battery",
        "cases": results,
        "hard_ok": all(r["ok"] for r in results),
        "failed_cases": [r["case"] for r in results if not r["ok"]],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ARTIFACT_PATH)
    args = parser.parse_args(argv)
    report = run_battery()
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "artifact": str(args.output),
        "cases": len(report["cases"]),
        "hard_ok": report["hard_ok"],
        "failed_cases": report["failed_cases"],
    }, indent=2, sort_keys=True))
    return 0 if report["hard_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
