"""Crateworks drift battery (Harvest 11: robustness-grid extension).

Report 18's schema-rename drift event ran against fleetops only, at
fleetops' own day-120 anchor. This battery proves the same event kind on
crateworks's own conversational-onboarding path
(``eval/crateworks_onboarding.py``'s ``_tables_for_onboarding``, the exact
flat-record shape ``mcp_server.ingest_table`` already drives for this
tenant) -- the mapping layer must ask a new confirmation question or
refuse a renamed field, never silently keep mapping the old field's
meaning under the header-casing mess this tenant's bible already bakes
into every ingest run.

A junk-contact-import analog is NOT included for this tenant, disclosed
(not silently skipped): every crateworks account ALREADY carries an
authored duplicate-contact pair and one stale record as a permanent,
fixed-quota property of the book (bible section 3) -- there is no
"before/after" timeline to script a NEW junk-contact event against; the
mess is a standing fixture property, not a dated world change. The
identity-collision axis this would otherwise probe is already covered by
``eval/crateworks_perturbation_battery.py``'s
``check_identity_collision_width_isolated_from_comms_noise``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from eval.crateworks_onboarding import _tables_for_onboarding
from eval.perturbation.perturb import schema_rename
from ultra_csm import mcp_server

ARTIFACT_PATH = Path(__file__).with_name("crateworks_drift_battery.json")

# Crateworks's own timeline anchor for this drift event: distinct from
# fleetops' day-120 (report 18) and from every crateworks bible-graded
# checkpoint (60/100/200).
_BEFORE_DAY = 50
_AT_DAY = 120
_AFTER_DAY = 180
_SCHEMA_RENAME_MAP = {"industry": "vertical", "title": "job_title"}


def check(ok: bool, problems: list[str], label: str, detail: Any = None) -> None:
    if not ok:
        problems.append(f"{label}: {detail}" if detail is not None else label)


def _tables_for_day(day: int) -> tuple:
    tables = _tables_for_onboarding()
    if day < _AT_DAY:
        return tables
    return tuple(
        (table_name, contract, schema_rename(records, _SCHEMA_RENAME_MAP))
        for table_name, contract, records in tables
    )


def check_schema_field_rename_before_at_after() -> dict[str, Any]:
    """Day 50 (before): industry/title unrenamed, mapping proceeds
    normally. Day 120/180 (at/after): the two renamed fields must surface
    a new confirmation question or be refused -- never silently kept
    mapped under the pre-rename meaning."""

    problems: list[str] = []
    detail: dict[str, Any] = {}

    for day in (_BEFORE_DAY, _AT_DAY, _AFTER_DAY):
        book_id = f"crateworks-drift-schema-rename-day{day}"
        mcp_server._relational_books.pop(book_id, None)
        questions: set[str] = set()
        auto_mapped_source_fields: set[str] = set()
        for table_name, contract, records in _tables_for_day(day):
            resp = mcp_server.ingest_table(
                book_id=book_id,
                table_name=table_name,
                contract=contract,
                records=records,
                expected_count=len(records),
            )
            for q in resp.get("confirmation_questions", []):
                questions.add(q["key"])
            for a in resp.get("auto_mapped", []):
                if a.get("source_field"):
                    auto_mapped_source_fields.add(a["source_field"])
        detail[str(day)] = {
            "confirmation_questions": sorted(questions),
            "renamed_fields_still_auto_mapped": sorted(
                set(_SCHEMA_RENAME_MAP.values()) & auto_mapped_source_fields
            )
            if day >= _AT_DAY
            else [],
        }

    check(
        "vertical" not in str(detail[str(_BEFORE_DAY)]) and "job_title" not in str(detail[str(_BEFORE_DAY)]),
        problems,
        f"day {_BEFORE_DAY} (before rename): renamed field names should not appear anywhere yet",
        detail[str(_BEFORE_DAY)],
    )
    for day_key in (str(_AT_DAY), str(_AFTER_DAY)):
        d = detail[day_key]
        detected = bool(d["confirmation_questions"]) or not d["renamed_fields_still_auto_mapped"]
        check(
            detected,
            problems,
            f"day {day_key}: renamed fields must surface a question or be refused, not silently mis-mapped",
            d,
        )

    return {
        "case": "schema-field-rename-before-at-after",
        "ok": not problems,
        "problems": problems,
        "detail": detail,
    }


def check_crateworks_battery_still_green_post_drift() -> dict[str, Any]:
    """The onboarding-ingest drift event touches Account/Contact flat
    records only, driven under separate book ids -- ``eval/crateworks_battery.py``'s
    checkpoint truths (comms/relationship fixtures, mess-quota checks)
    must stay unaffected."""

    from eval.crateworks_battery import run_battery as run_crateworks_battery

    problems: list[str] = []
    report = run_crateworks_battery()
    detail = {"hard_ok": report["hard_ok"], "cases": len(report["cases"]), "failed_cases": report["failed_cases"]}
    check(report["hard_ok"] and len(report["cases"]) == 6, problems, "crateworks battery must stay 6/6 post-drift", detail)
    return {"case": "crateworks-battery-still-green-post-drift", "ok": not problems, "problems": problems, "detail": detail}


CASES = (
    check_schema_field_rename_before_at_after,
    check_crateworks_battery_still_green_post_drift,
)


def run_battery() -> dict[str, Any]:
    results = [fn() for fn in CASES]
    return {
        "artifact": "crateworks_drift_battery",
        "cases": results,
        "axes_not_applicable": [
            {
                "axis": "junk-contact-import",
                "applicable": False,
                "reason": (
                    "every crateworks account already carries a permanent, "
                    "fixed-quota duplicate-contact pair and stale record "
                    "(bible section 3) -- there is no before/after timeline "
                    "to script a NEW junk-contact event against; the "
                    "identity-collision axis this would probe is already "
                    "covered by the perturbation grid's width-isolation cell"
                ),
            }
        ],
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
