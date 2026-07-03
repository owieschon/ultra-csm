"""Narrative property battery for the Synthetic Tenant Universe (Phase U3).

Modeled on eval/relational_battery.py's pattern: frozen cases (here, the
six arcs' bible-specified checkpoints plus the two red herrings and the 27
boring controls from docs/SYNTHETIC_UNIVERSE_BIBLE.md, rather than random
seeds -- this system is deterministic by construction, not seeded), a
``hard_ok`` gate, and a determinism-across-two-runs assertion.

Anti-Goodhart note: docs/SYNTHETIC_UNIVERSE_BIBLE.md owns ground truth. This
battery may be edited to add cases or to correct an assertion against a
bible change (a new beat, a corrected date) -- it may NEVER be edited to
match whatever the system currently outputs without a bible change
explaining why the WORLD changed. If a case starts failing, the fix is
either a bug in the fixture/extractor code, or a bible correction with a
stated reason -- never a quiet edit to this file to make red turn green.

Three checks per arc case:
(a) the extractor surfaces the scripted signals with the right values;
(b) for the one account with a Rocketlane rail (Pinehill), the activation-
    gap function surfaces the arc's truth at each checkpoint;
(c) red herrings and boring controls: zero flags -- specificity is a hard
    assertion, not a nice-to-have.
"""

from __future__ import annotations

import argparse
import json
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
from ultra_csm.data_plane.narrative_shared import cases_as_of
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
from ultra_csm.data_plane.synthetic_book import SEED_DATE, build_synthetic_book
from ultra_csm.data_plane.book_simulator import simulate_book
from ultra_csm.data_plane.trailhead_comms import (
    trailhead_calendar_events,
    trailhead_cases_as_of,
    trailhead_communication_signals,
    trailhead_stakeholder_relationships,
)

ARTIFACT_PATH = Path(__file__).with_name("narrative_battery.json")

RED_HERRINGS = ("cedar-valley", "ironridge-fleet")

BORING_CONTROLS = (
    "ironhorse-freight", "ridgeline-warehousing", "northstar-couriers",
    "clearwater-field-ops", "summit-industrial",
    "crestline-distribution", "redwood-fleet", "bison-transport",
    "copperfield-warehousing", "cascade-field", "timberline-logistics",
    "falcon-delivery", "mesa-industrial", "stonebridge-fleet",
    "prairie-wind", "granite-peak", "hawkstone-industries",
    "oakmont-logistics", "blueridge-transport", "westfield-industrial",
    "sagebrush-transport", "driftwood-warehousing", "cypress-field",
    "harborview-fleet", "windmill-transport",
    "riverstone-logistics", "dustbowl-freight",
)


def _as_of(day_offset: int) -> str:
    return (date.fromisoformat(SEED_DATE) + timedelta(days=day_offset)).isoformat()


def _signals(account_id, comms_fn, rels_fn, cal_fn, cases_fn, day_offset):
    as_of = _as_of(day_offset)
    signals = comms_fn(day_offset)
    rels = rels_fn(day_offset)
    calendar = cal_fn(day_offset)
    cases = cases_fn(day_offset)
    return {
        "latency": reply_latency_trend(account_id, signals, as_of=as_of),
        "width": thread_participation_width(account_id, rels, as_of=as_of),
        "cadence": meeting_cadence_shift(account_id, calendar, as_of=as_of),
        "tickets": ticket_frequency_window(account_id, cases, as_of=as_of),
    }


def check_onboarding_stall() -> dict[str, Any]:
    account_id = account_id_for("pinehill-transport")
    problems: list[str] = []
    checkpoints = {"before": 20, "during": 50, "after": 310}
    detail: dict[str, Any] = {}
    for label, day in checkpoints.items():
        sig = _signals(
            account_id, pinehill_communication_signals, pinehill_stakeholder_relationships,
            pinehill_calendar_events, pinehill_cases_as_of, day,
        )
        onboarding = pinehill_onboarding_fixture_data(day)
        as_of = _as_of(day)
        gaps = {
            phase.name: has_activation_gap(phase, onboarding.projects[0], onboarding.tasks, as_of=as_of)
            for phase in onboarding.phases
        }
        detail[label] = {
            "latency": sig["latency"].value,
            "tickets": sig["tickets"].value,
            "gaps": gaps,
        }
        if label == "during":
            if not (sig["latency"].value is not None and sig["latency"].value > 15):
                problems.append(f"during: expected reply-latency stretch, got {sig['latency'].value}")
            if not any(gaps.values()):
                problems.append(f"during: expected at least one Rocketlane activation gap, got {gaps}")
            if sig["tickets"].value < 2:
                problems.append(f"during: expected >=2 open cases, got {sig['tickets'].value}")
        if label == "after":
            if any(gaps.values()):
                problems.append(f"after: expected zero activation gaps, got {gaps}")
    return {"case": "onboarding-stall", "account": "pinehill-transport", "ok": not problems,
            "problems": problems, "detail": detail}


def check_single_threaded_risk() -> dict[str, Any]:
    account_id = account_id_for("pinnacle-supply")
    problems: list[str] = []
    checkpoints = {"day10": 10, "day120": 120, "day250": 250}
    detail: dict[str, Any] = {}
    for label, day in checkpoints.items():
        sig = _signals(
            account_id, pinnacle_communication_signals, pinnacle_stakeholder_relationships,
            pinnacle_calendar_events, pinnacle_cases_as_of, day,
        )
        rels = pinnacle_stakeholder_relationships(day)
        strengths = {r.contact_id: r.strength for r in rels}
        detail[label] = {"width": sig["width"].value, "strengths": strengths}
        if label == "day10" and sig["width"].value != 1:
            problems.append(f"day10: expected width 1, got {sig['width'].value}")
        if label == "day120" and sig["width"].value != 2:
            problems.append(f"day120: expected width 2, got {sig['width'].value}")
        if label == "day250":
            if sig["width"].value != 2:
                problems.append(f"day250: expected width 2, got {sig['width'].value}")
            if "strong" not in strengths.values():
                problems.append(f"day250: expected a strong relationship, got {strengths}")
    return {"case": "single-threaded-risk", "account": "pinnacle-supply", "ok": not problems,
            "problems": problems, "detail": detail}


def check_churn_brewing() -> dict[str, Any]:
    account_id = account_id_for("quarrystone-logistics")
    problems: list[str] = []
    checkpoints = {"day30": 30, "day190": 190, "day225": 225}
    detail: dict[str, Any] = {}
    for label, day in checkpoints.items():
        sig = _signals(
            account_id, quarrystone_communication_signals, quarrystone_stakeholder_relationships,
            quarrystone_calendar_events, quarrystone_cases_as_of, day,
        )
        detail[label] = {"width": sig["width"].value, "cadence": sig["cadence"].value, "tickets": sig["tickets"].value}
        if sig["width"].value != 1:
            problems.append(f"{label}: expected flat width 1 (no replacement ever), got {sig['width'].value}")
        if sig["cadence"].value is not None:
            problems.append(f"{label}: expected no computable cadence (near-zero calendar activity), got {sig['cadence'].value}")
        if label == "day190" and sig["tickets"].value < 1:
            problems.append(f"day190: expected the day-160 renewal case visible, got {sig['tickets'].value}")
    return {"case": "churn-brewing", "account": "quarrystone-logistics", "ok": not problems,
            "problems": problems, "detail": detail}


def check_silent_decline() -> dict[str, Any]:
    account_id = account_id_for("aspenridge-supply")
    base = build_synthetic_book()
    problems: list[str] = []
    checkpoints = {"day90": 90, "day200": 200, "day340": 340}
    detail: dict[str, Any] = {}
    for label, day in checkpoints.items():
        sig = _signals(
            account_id, aspenridge_communication_signals, aspenridge_stakeholder_relationships,
            _aspenridge_calendar_events, aspenridge_cases_as_of, day,
        )
        book = simulate_book(base, day)
        health = next(h for h in book.health_scores if h.account_id == account_id)
        adoption = next(a for a in book.adoption_summaries if a.account_id == account_id)
        detail[label] = {"band": health.band, "adoption_rate": adoption.adoption_rate, "tickets": sig["tickets"].value}
        if health.band != "green":
            problems.append(f"{label}: expected band green (engine's own >20% threshold not tripped), got {health.band}")
        if sig["tickets"].value != 0:
            problems.append(f"{label}: expected zero cases, got {sig['tickets'].value}")
    # the real signal: usage genuinely declines even though band stays green
    first = next(a for a in simulate_book(base, 90).adoption_summaries if a.account_id == account_id)
    last = next(a for a in simulate_book(base, 340).adoption_summaries if a.account_id == account_id)
    if not (last.adoption_rate < first.adoption_rate):
        problems.append(f"expected adoption_rate to decline day90->day340, got {first.adoption_rate} -> {last.adoption_rate}")
    detail["adoption_decline"] = {"day90": first.adoption_rate, "day340": last.adoption_rate}
    return {"case": "silent-decline", "account": "aspenridge-supply", "ok": not problems,
            "problems": problems, "detail": detail}


def check_expansion_ready() -> dict[str, Any]:
    account_id = account_id_for("meridian-fleet")
    problems: list[str] = []
    checkpoints = {"day20": 20, "day170": 170, "day280": 280}
    detail: dict[str, Any] = {}
    for label, day in checkpoints.items():
        sig = _signals(
            account_id, meridian_communication_signals, meridian_stakeholder_relationships,
            meridian_calendar_events, meridian_cases_as_of, day,
        )
        detail[label] = {"width": sig["width"].value, "cadence": sig["cadence"].value}
        if label in ("day170", "day280") and sig["width"].value != 2:
            problems.append(f"{label}: expected multi-threaded width 2, got {sig['width'].value}")
        if label == "day170" and not (sig["cadence"].value is not None and sig["cadence"].value <= 0):
            problems.append(f"day170: expected cadence tightening (<=0 delta) into the expansion, got {sig['cadence'].value}")
    return {"case": "expansion-ready", "account": "meridian-fleet", "ok": not problems,
            "problems": problems, "detail": detail}


def check_healthy_control() -> dict[str, Any]:
    account_id = account_id_for("trailhead-logistics")
    problems: list[str] = []
    checkpoints = {"day60": 60, "day180": 180, "day300": 300}
    detail: dict[str, Any] = {}
    for label, day in checkpoints.items():
        sig = _signals(
            account_id, trailhead_communication_signals, trailhead_stakeholder_relationships,
            trailhead_calendar_events, trailhead_cases_as_of, day,
        )
        detail[label] = {"latency": sig["latency"].value, "cadence": sig["cadence"].value, "tickets": sig["tickets"].value}
        if sig["latency"].value is not None and sig["latency"].value > 10:
            problems.append(f"{label}: unexpected latency stretch on the control account: {sig['latency'].value}")
        if sig["cadence"].value is not None and sig["cadence"].value > 5:
            problems.append(f"{label}: unexpected cadence widening on the control account: {sig['cadence'].value}")
        if sig["tickets"].value > 1:
            problems.append(f"{label}: unexpected ticket volume on the control account: {sig['tickets'].value}")
    return {"case": "healthy-control", "account": "trailhead-logistics", "ok": not problems,
            "problems": problems, "detail": detail}


def check_red_herrings() -> dict[str, Any]:
    base = build_synthetic_book()
    problems: list[str] = []
    detail: dict[str, Any] = {}
    for slug in RED_HERRINGS:
        account_id = account_id_for(slug)
        late_day = 340
        cases = cases_as_of(account_id, late_day)
        book = simulate_book(base, late_day)
        health = next((h for h in book.health_scores if h.account_id == account_id), None)
        band = health.band if health else None
        all_resolved = all(c.closed_at is not None for c in cases)
        detail[slug] = {"case_count": len(cases), "all_resolved": all_resolved, "band": band}
        if len(cases) < 1:
            problems.append(f"{slug}: expected at least one case (the herring signal), got {len(cases)}")
        if not all_resolved:
            problems.append(f"{slug}: expected the herring case(s) resolved by day {late_day}")
        if band not in ("green", None):
            problems.append(f"{slug}: expected green/unset health band (world truth: never at risk), got {band}")
    return {"case": "red-herrings", "ok": not problems, "problems": problems, "detail": detail}


# Case subjects authored specifically for this program's arcs/herrings --
# none of these should ever appear on a boring-control account. A raw case
# *count* threshold isn't meaningful here: several controls (e.g.
# cypress-field, an at_risk_support persona) legitimately carry real,
# pre-existing case volume that has nothing to do with this program. The
# real specificity question is contamination, not volume.
_AUTHORED_CASE_SUBJECTS = (
    "Requesting updated MSA redline for renewal paperwork",
    "Integration webhook returning 500 errors intermittently",
    "Renewal terms discussion — no response",
)


def check_boring_controls() -> dict[str, Any]:
    problems: list[str] = []
    detail: dict[str, Any] = {}
    spot_day = 340
    for slug in BORING_CONTROLS:
        account_id = account_id_for(slug)
        cases = cases_as_of(account_id, spot_day)
        contaminated = [c.subject for c in cases if c.subject in _AUTHORED_CASE_SUBJECTS]
        detail[slug] = {"case_count": len(cases), "contaminated": contaminated}
        if contaminated:
            problems.append(f"{slug}: program-authored case content leaked onto a boring control: {contaminated}")
    return {"case": "boring-controls", "ok": not problems, "problems": problems, "detail": detail}


CASES = (
    check_onboarding_stall,
    check_single_threaded_risk,
    check_churn_brewing,
    check_silent_decline,
    check_expansion_ready,
    check_healthy_control,
    check_red_herrings,
    check_boring_controls,
)


def run_battery() -> dict[str, Any]:
    results = [fn() for fn in CASES]
    return {
        "artifact": "narrative_property_battery",
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
