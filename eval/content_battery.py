"""Cross-channel content-consistency battery (Program 8, Phase E).

Separate from ``narrative_battery.py`` on purpose: that battery asserts
signal-level truth (extractor output at bible checkpoints) and must never
change because of Program 8's content enrichment (see
``eval/content_invariance_check.py``). This battery asserts
content-level truth -- the prose itself is internally consistent with the
bible's error-string canon table and each account's actual entitlements --
which narrative_battery.py has no way to check since it never reads body
text. Same ``hard_ok`` pattern; two consecutive runs must be identical
(all assertions here are over static dict content, so this holds trivially
by construction, not by re-running a simulator).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ultra_csm.data_plane.narrative_content import (
    aspenridge_content,
    case_verbatims,
    meridian_content,
    pinehill_content,
    pinnacle_content,
    quarrystone_content,
    trailhead_content,
)

ARTIFACT_PATH = Path(__file__).with_name("content_battery.json")

# Bible's error-string canon table (docs/SYNTHETIC_UNIVERSE_BIBLE.md).
# (case_id_key, expected_substring) -- case_id_key resolved via case_verbatims._case_id.
_PINEHILL_ERROR_STRINGS = {
    0: "DISPATCH_BRIDGE_CONNECT_FAILURE: RouteLedger 5.2 SOAP endpoint refused connection "
       "(fault code AUTH-401, host dispatch.pinehill-transport.internal:8443)",
    30: "DISPATCH_BRIDGE_TIMEOUT: upstream RouteLedger socket closed after 30000ms "
        "(job batch 4417, retry_count=3)",
    80: "DISPATCH_BRIDGE_EVENT_LOSS: 214 of 1,880 dispatch events unacknowledged in trailing "
        "24h window (RouteLedger ack timeout, queue=pinehill-dispatch-out)",
}
_IRONRIDGE_ERROR_STRING = (
    "WEBHOOK_DELIVERY_500: outbound maintenance-alert webhook to Ironridge's ticketing "
    "endpoint returned HTTP 500 on 6 of 140 attempts over 90 minutes "
    "(endpoint https://tickets.ironridge-fleet.example/hooks/fleetops, no retry backoff "
    "configured)"
)

# All eight canon product names (docs/SYNTHETIC_UNIVERSE_BIBLE.md's Canon section).
_ALL_MODULES = (
    "Live Map", "Route Optimizer", "Driver Scorecards", "Maintenance Radar",
    "Insights Hub", "Compliance Center", "Fuel Analytics", "Dispatch Automation",
)

# Each arc's actual entitled modules, read from synthetic_book.py's entitlement
# tables (not invented) -- see the bible's per-account dossiers.
_ARC_ENTITLEMENTS: dict[str, tuple[str, ...]] = {
    "pinehill": ("Live Map", "Route Optimizer"),
    "aspenridge": ("Live Map", "Route Optimizer"),
    "quarrystone": ("Live Map",),
    "trailhead": ("Live Map", "Route Optimizer", "Insights Hub", "Compliance Center", "Fuel Analytics"),
    "pinnacle": ("Live Map", "Route Optimizer", "Insights Hub", "Fuel Analytics", "Dispatch Automation"),
    "meridian": ("Live Map", "Route Optimizer", "Driver Scorecards", "Maintenance Radar"),
}

_ARC_BODIES: dict[str, dict[tuple[int, int], str]] = {
    "pinehill": pinehill_content.BODIES,
    "aspenridge": aspenridge_content.BODIES,
    "quarrystone": quarrystone_content.BODIES,
    "trailhead": trailhead_content.BODIES,
    "pinnacle": pinnacle_content.BODIES,
}

# Meridian has two independent threads -- flatten separately, tagging origin
# for readable failure messages.
_MERIDIAN_BODIES: dict[str, dict[tuple[int, int], str]] = {
    "meridian-alicia": meridian_content.ALICIA_BODIES,
    "meridian-sarah": meridian_content.SARAH_BODIES,
}

# Curated (arc, reply_key, expected_substring) triples verifying a reply
# engages with something specific the prior message said -- not a generic
# templated response. A hard-coded, honest sample (this content was
# authored by hand, not generated, so these are known-true facts about
# it) rather than an automated heuristic that could pass on accident.
_CONTINUITY_CHECKS = (
    ("pinehill", (8, 15), "raul"),
    ("pinehill", (34, 11), "raul"),
    ("pinehill", (87, 21), "escalating"),
    ("pinehill", (306, 12), "grace"),
    ("pinnacle", (136, 15), "dispatch automation"),
    ("pinnacle", (170, 13), "fuel analytics"),
    ("meridian-alicia", (75, 13), "sarah chen"),
    ("meridian-sarah", (40, 14), "predictive alerts"),
    ("trailhead", (175, 15), "fleet-utilization"),
)

_TERSE_LENGTH_CEILING = 250
_FORMAL_LENGTH_FLOOR = 400


def check(ok: bool, problems: list[str], label: str, detail: Any = None) -> None:
    if not ok:
        problems.append(f"{label}: {detail}" if detail is not None else label)


def check_error_string_cross_references() -> dict[str, Any]:
    problems: list[str] = []
    detail: dict[str, Any] = {}
    for day, error_string in _PINEHILL_ERROR_STRINGS.items():
        case_id = case_verbatims._case_id(case_verbatims._PINEHILL, day)
        verbatim = case_verbatims.VERBATIMS.get(case_id)
        in_verbatim = verbatim is not None and any(error_string in c.body for c in verbatim.comments)
        in_email = any(
            error_string in body
            for (d, _hour), body in pinehill_content.BODIES.items()
            if d >= day
        )
        check(in_verbatim, problems, f"pinehill day{day} error string missing from case verbatim")
        check(in_email, problems, f"pinehill day{day} error string missing from any email body on/after case open day")
        detail[f"pinehill_day{day}"] = {"in_verbatim": in_verbatim, "in_email": in_email}

    ironridge_case_id = case_verbatims._case_id(case_verbatims._IRONRIDGE, 40)
    ironridge_verbatim = case_verbatims.VERBATIMS.get(ironridge_case_id)
    in_ironridge_verbatim = ironridge_verbatim is not None and any(
        _IRONRIDGE_ERROR_STRING in c.body for c in ironridge_verbatim.comments
    )
    check(in_ironridge_verbatim, problems, "ironridge error string missing from its own case verbatim")
    detail["ironridge_day40"] = {"in_verbatim": in_ironridge_verbatim}

    return {"case": "error_string_cross_references", "ok": not problems, "problems": problems, "detail": detail}


def check_no_error_string_leakage() -> dict[str, Any]:
    """Specificity: no case's error string appears on an account it doesn't
    belong to -- Pinehill's three strings must never appear outside
    Pinehill's own bodies/verbatim, and Ironridge's must never appear in
    any of the six arcs' email content (Ironridge has no comms fixture at
    all -- this also guards against a future arc's content accidentally
    reusing it)."""

    problems: list[str] = []
    detail: dict[str, Any] = {}
    other_arc_bodies: dict[str, dict[tuple[int, int], str]] = {
        k: v for k, v in _ARC_BODIES.items() if k != "pinehill"
    }
    other_arc_bodies.update(_MERIDIAN_BODIES)

    for day, error_string in _PINEHILL_ERROR_STRINGS.items():
        leaked_into = [arc for arc, bodies in other_arc_bodies.items() if any(error_string in b for b in bodies.values())]
        check(not leaked_into, problems, f"pinehill day{day} error string leaked into other arcs", leaked_into)

    all_arc_bodies = dict(_ARC_BODIES)
    all_arc_bodies.update(_MERIDIAN_BODIES)
    ironridge_leaked_into = [
        arc for arc, bodies in all_arc_bodies.items() if any(_IRONRIDGE_ERROR_STRING in b for b in bodies.values())
    ]
    check(not ironridge_leaked_into, problems, "ironridge error string leaked into arc emails", ironridge_leaked_into)
    detail["ironridge_leaked_into"] = ironridge_leaked_into

    return {"case": "no_error_string_leakage", "ok": not problems, "problems": problems, "detail": detail}


def check_module_tier_consistency() -> dict[str, Any]:
    problems: list[str] = []
    detail: dict[str, Any] = {}
    all_bodies = dict(_ARC_BODIES)
    all_bodies.update(_MERIDIAN_BODIES)
    for arc, bodies in all_bodies.items():
        base_arc = "meridian" if arc.startswith("meridian") else arc
        entitled = set(_ARC_ENTITLEMENTS[base_arc])
        forbidden = [m for m in _ALL_MODULES if m not in entitled]
        found_forbidden = sorted({
            m for m in forbidden for body in bodies.values() if m in body
        })
        check(not found_forbidden, problems, f"{arc} mentions un-entitled module(s)", found_forbidden)
        detail[arc] = {"entitled": sorted(entitled), "found_forbidden": found_forbidden}
    return {"case": "module_tier_consistency", "ok": not problems, "problems": problems, "detail": detail}


def check_reply_continuity() -> dict[str, Any]:
    problems: list[str] = []
    detail: dict[str, Any] = {}
    all_bodies = dict(_ARC_BODIES)
    all_bodies.update(_MERIDIAN_BODIES)
    for arc, key, expected_substring in _CONTINUITY_CHECKS:
        body = all_bodies[arc].get(key, "")
        present = expected_substring.lower() in body.lower()
        check(present, problems, f"{arc}{key} missing continuity reference", expected_substring)
        detail[f"{arc}{key}"] = present
    return {"case": "reply_continuity", "ok": not problems, "problems": problems, "detail": detail}


def check_persona_length_bounds() -> dict[str, Any]:
    problems: list[str] = []
    dennis_keys = [(1, 14), (8, 15), (23, 15), (34, 11), (63, 15), (87, 21), (275, 15), (295, 14), (306, 12)]
    dennis_lengths = [len(pinehill_content.BODIES[k]) for k in dennis_keys]
    marcus_keys = [(1, 9), (22, 9), (32, 9), (60, 9), (85, 9)]
    marcus_lengths = [len(pinehill_content.BODIES[k]) for k in marcus_keys]

    over_ceiling = [n for n in dennis_lengths if n > _TERSE_LENGTH_CEILING]
    under_floor = [n for n in marcus_lengths if n < _FORMAL_LENGTH_FLOOR]
    check(not over_ceiling, problems, "terse persona (Dennis Gruber) body exceeded length ceiling", over_ceiling)
    check(not under_floor, problems, "formal persona (Marcus Webb) body under length floor", under_floor)

    return {
        "case": "persona_length_bounds", "ok": not problems, "problems": problems,
        "detail": {"dennis_lengths": dennis_lengths, "marcus_lengths": marcus_lengths},
    }


CASES = (
    check_error_string_cross_references,
    check_no_error_string_leakage,
    check_module_tier_consistency,
    check_reply_continuity,
    check_persona_length_bounds,
)


def run_battery() -> dict[str, Any]:
    results = [fn() for fn in CASES]
    return {
        "artifact": "content_consistency_battery",
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
