"""Loopway drift battery (Harvest 11: robustness-grid extension).

Report 18's schema-rename drift event ran against fleetops only, at
fleetops' own day-120 anchor. This battery proves the same event KIND on
loopway's own Attio-shaped mapping layer, at loopway's own timeline
anchor -- distinct from ``eval/loopway_perturbation_battery.py``'s
schema-rename cell (report 18's own precedent, kept genuinely separate:
the perturbation cell stress-tests the mapping layer in isolation with no
narrative attached; this battery scripts a DATED, before/at/after event
against the tenant's real timeline, reusing the same rename mechanism
intentionally -- the two are not the same test).

A junk-contact-import analog is NOT included for this tenant, disclosed
(not silently skipped): loopway's tail is generated, frozen, literal data
(bible: "zero runtime generation... exactly as if a human had typed 376
rows by hand"), and its cohort/trigger logic (``eval/loopway_battery.py``'s
``_account_triggers``) reads static bible-membership tuples, never a
live contact count or roster size. Injecting junk contacts would perturb
a signal family this tenant's cohort logic never reads at all.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from eval.loopway_perturbation_battery import _rename_attio_person_field
from ultra_csm.data_plane.explorer import run_explorer
from ultra_csm.data_plane.tenants.loopway.attio_transport import (
    FakeLoopwayAttioClient,
    build_loopway_attio_fixture_payloads,
)
from ultra_csm.data_plane.tenants.loopway.narrative_shared import base_synthetic_book

ARTIFACT_PATH = Path(__file__).with_name("loopway_drift_battery.json")
_RUNTIME_BUDGET_SECONDS = 90.0

# Loopway's own timeline anchor for this drift event: distinct from
# fleetops' day-120 (report 18) and from every loopway bible-graded
# checkpoint (75/105/120/200).
_BEFORE_DAY = 50
_AT_DAY = 90
_AFTER_DAY = 160
_OLD_SLUG = "email_addresses"
_NEW_SLUG = "email_address_list"


def check(ok: bool, problems: list[str], label: str, detail: Any = None) -> None:
    if not ok:
        problems.append(f"{label}: {detail}" if detail is not None else label)


def _discover(payloads: dict[str, Any]):
    client = FakeLoopwayAttioClient(payloads)
    return run_explorer(
        "attio_crm", env={"ULTRA_CSM_ATTIO_ACCESS_TOKEN": "simulated-attio-token-loopway"}, client=client
    )


def check_schema_field_rename_before_at_after() -> dict[str, Any]:
    """Day 50 (before): email_addresses unrenamed, CRMContact.email maps
    cleanly. Day 90/160 (at/after): the renamed field must surface as no
    longer a clean mapping -- never silently kept mapped under the
    pre-rename source field name."""

    problems: list[str] = []
    detail: dict[str, Any] = {}
    book = base_synthetic_book()
    payloads = build_loopway_attio_fixture_payloads(book)
    renamed_payloads = _rename_attio_person_field(payloads, _OLD_SLUG, _NEW_SLUG)

    for day, day_payloads in ((_BEFORE_DAY, payloads), (_AT_DAY, renamed_payloads), (_AFTER_DAY, renamed_payloads)):
        result = _discover(day_payloads)
        assert result.ok and result.mapping_proposal is not None, result.errors
        entry = next(e for e in result.mapping_proposal.entries if e.key == "CRMContact.email")
        detail[str(day)] = {"state": entry.state, "source_field": entry.source_field}

    check(
        detail[str(_BEFORE_DAY)]["state"] == "mapped" and detail[str(_BEFORE_DAY)]["source_field"] == _OLD_SLUG,
        problems,
        f"day {_BEFORE_DAY} (before rename): CRMContact.email should map cleanly to {_OLD_SLUG!r}",
        detail[str(_BEFORE_DAY)],
    )
    for day_key in (str(_AT_DAY), str(_AFTER_DAY)):
        d = detail[day_key]
        still_silently_mapped = d["state"] == "mapped" and d["source_field"] == _OLD_SLUG
        check(
            not still_silently_mapped,
            problems,
            f"day {day_key}: renamed field must not still silently map under the pre-rename source field name",
            d,
        )

    return {
        "case": "schema-field-rename-before-at-after",
        "ok": not problems,
        "problems": problems,
        "detail": detail,
    }


def check_loopway_battery_still_green_post_drift() -> dict[str, Any]:
    """The Attio mapping drift event touches the discovery/proposal layer
    only -- ``eval/loopway_battery.py``'s cohort/trigger checkpoint truths
    (resolved from static bible-membership tuples, never from the Attio
    mapping layer) must stay unaffected."""

    from eval.loopway_battery import run_battery as run_loopway_battery

    problems: list[str] = []
    report = run_loopway_battery()
    detail = {
        "hard_ok": report["hard_ok"], "cases": len(report["cases"]), "failed_cases": report["failed_cases"],
    }
    check(report["hard_ok"] and len(report["cases"]) == 9, problems, "loopway battery must stay 9/9 post-drift", detail)
    return {"case": "loopway-battery-still-green-post-drift", "ok": not problems, "problems": problems, "detail": detail}


CASES = (
    check_schema_field_rename_before_at_after,
    check_loopway_battery_still_green_post_drift,
)


def run_battery() -> dict[str, Any]:
    start = time.perf_counter()
    results = [fn() for fn in CASES]
    elapsed = time.perf_counter() - start
    return {
        "artifact": "loopway_drift_battery",
        "cases": results,
        "runtime_seconds": round(elapsed, 3),
        "runtime_budget_seconds": _RUNTIME_BUDGET_SECONDS,
        "within_runtime_budget": elapsed <= _RUNTIME_BUDGET_SECONDS,
        "axes_not_applicable": [
            {
                "axis": "junk-contact-import",
                "applicable": False,
                "reason": (
                    "loopway's tail is generated, frozen, literal data; its "
                    "cohort/trigger logic reads static bible-membership "
                    "tuples, never a live contact count or roster size -- a "
                    "junk-contact injection would perturb a signal family "
                    "this tenant's cohort logic never reads"
                ),
            }
        ],
        "hard_ok": all(r["ok"] for r in results) and elapsed <= _RUNTIME_BUDGET_SECONDS,
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
        "runtime_seconds": report["runtime_seconds"],
        "failed_cases": report["failed_cases"],
    }, indent=2, sort_keys=True))
    return 0 if report["hard_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
