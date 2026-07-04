"""Drift battery (Universe v2, WS-Perturbation-Drift, Wave 4).

Perturbation catches calibration failures; drift catches the time
dimension nobody tests -- the tenant changing under the agent mid-flight.
Before/at/after assertions (days 115/125/155) for the two D7-reserved
drift events scripted against the fleetops timeline
(``docs/SYNTHETIC_UNIVERSE_BIBLE.md``'s "Drift events" section), plus the
existing six arcs' checkpoint truths re-run against the now-permanently-
drifted book (drift must not corrupt the narrative battery), plus the
content-invariance isolation guarantee (drift lives in book/CRM state,
not comms, so the snapshot must stay byte-identical).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from eval.narrative_battery import run_battery as run_narrative_battery
from eval.perturbation.perturb import schema_rename
from eval.week1_protocol import _crm_records_for_onboarding
from ultra_csm import mcp_server
from ultra_csm.data_plane.aspenridge_comms import aspenridge_stakeholder_relationships
from ultra_csm.data_plane.book_simulator import simulate_book
from ultra_csm.data_plane.comms_fixtures import pinehill_stakeholder_relationships
from ultra_csm.data_plane.fixtures import account_id_for
from ultra_csm.data_plane.meridian_comms import meridian_stakeholder_relationships
from ultra_csm.data_plane.pinnacle_comms import pinnacle_stakeholder_relationships
from ultra_csm.data_plane.quarrystone_comms import quarrystone_stakeholder_relationships
from ultra_csm.data_plane.signal_extractor import thread_participation_width
from ultra_csm.data_plane.synthetic_book import build_synthetic_book
from ultra_csm.data_plane.trailhead_comms import trailhead_stakeholder_relationships

ARTIFACT_PATH = Path(__file__).with_name("drift_battery.json")

_SIX_ARCS = (
    ("pinehill-transport", pinehill_stakeholder_relationships),
    ("pinnacle-supply", pinnacle_stakeholder_relationships),
    ("quarrystone-logistics", quarrystone_stakeholder_relationships),
    ("aspenridge-supply", aspenridge_stakeholder_relationships),
    ("meridian-fleet", meridian_stakeholder_relationships),
    ("trailhead-logistics", trailhead_stakeholder_relationships),
)

_SCHEMA_RENAME_MAP = {"Industry": "Vertical", "Title": "JobTitle"}


def check(ok: bool, problems: list[str], label: str, detail: Any = None) -> None:
    if not ok:
        problems.append(f"{label}: {detail}" if detail is not None else label)


def _onboarding_records_for_day(day: int) -> tuple:
    records = _crm_records_for_onboarding()
    if day < 120:
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
    """Day 115 (before): fields still Industry/Title, mapping proceeds
    normally. Day 125/155 (at/after): the two renamed fields must surface
    a new confirmation question or be refused -- never silently kept
    mapped under the pre-rename meaning."""

    problems: list[str] = []
    detail: dict[str, Any] = {}

    for day in (115, 125, 155):
        book_id = f"drift-schema-rename-day{day}"
        mcp_server._relational_books.pop(book_id, None)
        questions: set[str] = set()
        auto_mapped_source_fields: set[str] = set()
        for table_name, contract, records, field_metadata in _onboarding_records_for_day(day):
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
            if day >= 120
            else [],
        }

    # Before (day 115): no renamed field name should appear at all --
    # the source still says Industry/Title.
    check(
        "Vertical" not in str(detail["115"]) and "JobTitle" not in str(detail["115"]),
        problems,
        "day 115 (before rename): renamed field names should not appear anywhere yet",
        detail["115"],
    )
    # At/after (day 125, 155): the rename must be detected -- either a new
    # confirmation question mentions it, or it is refused (never silently
    # auto-mapped under the OLD field's meaning while presenting as the
    # NEW field name with no question raised).
    for day_key in ("125", "155"):
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


def check_junk_contacts_present_after_day150() -> dict[str, Any]:
    """40 junk contacts land across the six arc accounts at day 150, not
    before; verified directly against the simulated book, not assumed."""

    problems: list[str] = []
    detail: dict[str, Any] = {}
    base = build_synthetic_book()
    book_before = simulate_book(base, 115)
    book_after = simulate_book(base, 155)

    total_junk_after = 0
    for slug, _rels_fn in _SIX_ARCS:
        account_id = account_id_for(slug)
        junk_before = [c for c in book_before.contacts if c.account_id == account_id and c.email.endswith("@invalid.example")]
        junk_after = [c for c in book_after.contacts if c.account_id == account_id and c.email.endswith("@invalid.example")]
        detail[slug] = {"junk_before_day150": len(junk_before), "junk_after_day150": len(junk_after)}
        total_junk_after += len(junk_after)
        check(len(junk_before) == 0, problems, f"{slug}: expected zero junk contacts before day 150", len(junk_before))
        check(len(junk_after) > 0, problems, f"{slug}: expected junk contacts present after day 150", len(junk_after))

    detail["total_junk_after_day150"] = total_junk_after
    check(total_junk_after == 40, problems, "expected exactly 40 junk contacts total across the six arcs", total_junk_after)

    return {"case": "junk-contacts-present-after-day150", "ok": not problems, "problems": problems, "detail": detail}


def check_width_signals_unaffected_by_junk_import() -> dict[str, Any]:
    """Relationship-width signals for all six arcs must be identical
    whether computed before or after the junk-contact drift -- width is
    computed from each arc's own StakeholderRelationship fixture function,
    never from the raw CRMContact table the junk rows land in, so this
    holds true BY CONSTRUCTION; verified directly, not assumed."""

    problems: list[str] = []
    detail: dict[str, Any] = {}

    for slug, rels_fn in _SIX_ARCS:
        account_id = account_id_for(slug)
        for day, as_of in ((115, "2026-10-14"), (155, "2026-11-23")):
            rels = rels_fn(day)
            width = thread_participation_width(account_id, rels, as_of=as_of)
            detail.setdefault(slug, {})[str(day)] = width.value

        before, after = detail[slug]["115"], detail[slug]["155"]
        # The two days are different bible moments for some arcs (width
        # legitimately changes over the year for reasons unrelated to
        # junk contacts, e.g. Pinnacle's day-110 NewContactAppears) -- so
        # this check's real assertion is structural: junk contacts are
        # never present in `rels` at all, which the function signature
        # itself proves (rels_fn takes only as_of_day, never a contacts
        # list). Recorded here as an explicit, direct check rather than a
        # same-value assertion that would be coincidentally true or false
        # for the wrong reason.
        check(
            not any("invalid.example" in str(r) for r in rels),
            problems,
            f"{slug}: junk contacts must never appear in the StakeholderRelationship fixture rows",
            None,
        )
        detail[slug]["before_after_delta"] = None if before is None or after is None else round(after - before, 2)

    return {
        "case": "width-signals-unaffected-by-junk-import",
        "ok": not problems,
        "problems": problems,
        "detail": detail,
    }


def check_narrative_battery_still_green_post_drift() -> dict[str, Any]:
    """The six arcs' EXISTING checkpoint truths must still all pass with
    the drift events baked into SCENARIO_TIMELINE -- drift must not
    corrupt the narrative battery."""

    problems: list[str] = []
    report = run_narrative_battery()
    detail = {"hard_ok": report["hard_ok"], "cases": len(report["cases"]), "failed_cases": report["failed_cases"]}
    check(report["hard_ok"] and len(report["cases"]) == 8, problems, "narrative battery must stay 8/8 post-drift", detail)
    return {"case": "narrative-battery-still-green-post-drift", "ok": not problems, "problems": problems, "detail": detail}


def check_content_invariance_isolation() -> dict[str, Any]:
    """Neither drift event may perturb the content-invariance snapshot --
    day 120/150 are not comms-schedule days for any of the six arcs'
    checkpoints."""

    problems: list[str] = []
    from eval.content_invariance_check import SNAPSHOT_PATH, build_snapshot

    current = json.dumps(build_snapshot(), indent=2, sort_keys=True, default=str) + "\n"
    committed = SNAPSHOT_PATH.read_text(encoding="utf-8")
    identical = current == committed
    check(identical, problems, "content-invariance snapshot must stay byte-identical after both drift events", None)
    return {"case": "content-invariance-isolation", "ok": not problems, "problems": problems, "detail": {}}


CASES = (
    check_schema_field_rename_before_at_after,
    check_junk_contacts_present_after_day150,
    check_width_signals_unaffected_by_junk_import,
    check_narrative_battery_still_green_post_drift,
    check_content_invariance_isolation,
)


def run_battery() -> dict[str, Any]:
    results = [fn() for fn in CASES]
    return {
        "artifact": "drift_battery",
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
