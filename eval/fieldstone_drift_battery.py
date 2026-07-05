"""Fieldstone drift battery (Harvest 11: robustness-grid extension).

Report 18's drift events (schema field rename, junk contact import) ran
against fleetops only, at fleetops' own day-120/150 anchors. This battery
proves the schema-rename drift event on fieldstone's own onboarding path
(``FieldstoneOnboardingCostResult``'s HubSpot-shaped ``Account``/``Contact``
records, ``ultra_csm.data_plane.tenants.fieldstone.onboarding._hubspot_records_for_onboarding``)
-- the mapping layer must ask a new confirmation question or refuse a
renamed field, never silently keep mapping the old field's meaning.

A junk-contact-import analog is NOT included for this tenant, disclosed
(not silently skipped): fieldstone's checkpoint signals
(``reply_latency_trend``/``meeting_cadence_shift``/``ticket_frequency_window``,
per ``eval/fieldstone_battery.py``) are computed from comms/calendar/case
fixtures, never from the contact roster -- ``thread_participation_width``
(the signal a junk-CONTACT injection actually perturbs in the fleetops
drift battery) is not used for this tenant at all. Injecting junk contacts
into fieldstone's book would perturb a signal family this tenant's bible
never reads.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from eval.perturbation.perturb import schema_rename
from ultra_csm import mcp_server
from ultra_csm.data_plane.tenants.fieldstone.onboarding import _hubspot_records_for_onboarding

ARTIFACT_PATH = Path(__file__).with_name("fieldstone_drift_battery.json")

# Fieldstone's own timeline anchor for this drift event: distinct from
# fleetops' day-120 (report 18) and from every fieldstone bible-graded
# checkpoint (60/80/140/180/300) -- chosen so this synthetic ingest-time
# marker never collides with a graded narrative checkpoint.
_BEFORE_DAY = 100
_AT_DAY = 160
_AFTER_DAY = 250
_SCHEMA_RENAME_MAP = {"Industry": "Vertical", "Title": "JobTitle"}


def check(ok: bool, problems: list[str], label: str, detail: Any = None) -> None:
    if not ok:
        problems.append(f"{label}: {detail}" if detail is not None else label)


def _records_for_day(day: int) -> tuple:
    records = _hubspot_records_for_onboarding()
    if day < _AT_DAY:
        return records
    renamed = []
    for table_name, contract, recs, field_metadata in records:
        renamed_recs = schema_rename(recs, _SCHEMA_RENAME_MAP)
        renamed_metadata = (
            {_SCHEMA_RENAME_MAP.get(k, k): v for k, v in field_metadata.items()}
            if field_metadata
            else field_metadata
        )
        renamed.append((table_name, contract, renamed_recs, renamed_metadata))
    return tuple(renamed)


def check_schema_field_rename_before_at_after() -> dict[str, Any]:
    """Day 100 (before): Industry/Title unrenamed, mapping proceeds
    normally. Day 160/250 (at/after): the two renamed fields must surface
    a new confirmation question or be refused -- never silently kept
    mapped under the pre-rename meaning."""

    problems: list[str] = []
    detail: dict[str, Any] = {}

    for day in (_BEFORE_DAY, _AT_DAY, _AFTER_DAY):
        book_id = f"fieldstone-drift-schema-rename-day{day}"
        mcp_server._relational_books.pop(book_id, None)
        questions: set[str] = set()
        auto_mapped_source_fields: set[str] = set()
        for table_name, contract, records, field_metadata in _records_for_day(day):
            resp = mcp_server.ingest_table(
                book_id=book_id,
                table_name=table_name,
                contract=contract,
                records=records,
                expected_count=len(records),
                field_metadata=field_metadata,
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
        "Vertical" not in str(detail[str(_BEFORE_DAY)]) and "JobTitle" not in str(detail[str(_BEFORE_DAY)]),
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


def check_narrative_battery_still_green_post_drift() -> dict[str, Any]:
    """The onboarding-ingest drift event touches Account/Contact
    HubSpot-shaped records only -- ``eval/fieldstone_battery.py``'s
    checkpoint truths (comms/calendar/case fixtures) must stay unaffected."""

    from eval.fieldstone_battery import run_battery as run_fieldstone_battery

    problems: list[str] = []
    report = run_fieldstone_battery()
    detail = {"hard_ok": report["hard_ok"], "cases": len(report["cases"]), "failed_cases": report["failed_cases"]}
    check(report["hard_ok"] and len(report["cases"]) == 6, problems, "fieldstone battery must stay 6/6 post-drift", detail)
    return {"case": "narrative-battery-still-green-post-drift", "ok": not problems, "problems": problems, "detail": detail}


CASES = (
    check_schema_field_rename_before_at_after,
    check_narrative_battery_still_green_post_drift,
)


def run_battery() -> dict[str, Any]:
    results = [fn() for fn in CASES]
    return {
        "artifact": "fieldstone_drift_battery",
        "cases": results,
        "axes_not_applicable": [
            {
                "axis": "junk-contact-import",
                "applicable": False,
                "reason": (
                    "fieldstone's checkpoint signals never read the contact "
                    "roster (thread_participation_width is not used for this "
                    "tenant); a junk-contact injection would perturb a signal "
                    "family this tenant's bible never reads"
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
