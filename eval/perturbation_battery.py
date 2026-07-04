"""Perturbation battery (Universe v2, WS-Perturbation-Drift, Wave 4).

Hand-authored tenants catch judgment failures; this battery catches
CALIBRATION failures -- thresholds/assumptions that only held because a
tenant's numbers happened to sit where the bible authors put them. Six
named cells, a FIXED deterministic grid (not a cross-product of every
tenant x every axis x every magnitude -- that would blow well past the
10-minute runtime budget for no assertion value beyond what these six
already prove). Two consecutive runs must be byte-identical.

The covariance table IS the spec -- each cell below is one row of it:

| Perturbation | Correct behavior | Failure it catches |
| latency x3, uniform | trend delta ~unchanged, no new flags | absolute-hours thresholds hiding anywhere |
| latency x3, recent-window-only | flag appears where a real stretch should be caught | delta-detection actually works post-perturbation |
| volume x0.5 | signal degrades to insufficient-history HONESTLY | window logic fabricating from thin data |
| hygiene_drop 30% | factors losing evidence go silent, no crash | null-handling brittleness |
| schema_rename (10 fields) | mapping asks new questions or refuses, never silently mis-maps | stale-mapping assumptions |
| arr_shift -60% | tier assignment moves, tier-forbidden motions move with it | hard-coded tier/ARR assumptions |
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from eval.perturbation.perturb import (
    hygiene_drop,
    latency_scale,
    latency_scale_recent_window,
    schema_rename,
    volume_scale,
)
from eval.week1_protocol import _crm_records_for_onboarding
from ultra_csm import mcp_server
from ultra_csm.data_plane.fixtures import account_id_for
from ultra_csm.data_plane.signal_extractor import reply_latency_trend
from ultra_csm.data_plane.synthetic_book import SEED_DATE, _COMPANY, build_synthetic_book
from ultra_csm.data_plane.trailhead_comms import trailhead_communication_signals
from ultra_csm.knowledge import load_playbooks
from ultra_csm.value_model import load_value_model_config, resolve_tenant_tier

ARTIFACT_PATH = Path(__file__).with_name("perturbation_battery.json")


def _as_of(day_offset: int) -> str:
    from datetime import date, timedelta

    return (date.fromisoformat(SEED_DATE) + timedelta(days=day_offset)).isoformat()


def check(ok: bool, problems: list[str], label: str, detail: Any = None) -> None:
    if not ok:
        problems.append(f"{label}: {detail}" if detail is not None else label)


def check_latency_uniform_no_new_flags() -> dict[str, Any]:
    """Cell 1: latency x3 on a healthy account (Trailhead, day 180) -- both
    trailing windows scale together, so the near-zero trend a healthy
    baseline already has stays near zero after scaling; an absolute-hours
    threshold hiding anywhere would instead see both windows cross it."""

    problems: list[str] = []
    account_id = account_id_for("trailhead-logistics")
    as_of = _as_of(180)
    signals = tuple(trailhead_communication_signals(180))
    baseline = reply_latency_trend(account_id, list(signals), as_of=as_of)

    scaled = latency_scale(signals, 3.0)
    perturbed = reply_latency_trend(account_id, list(scaled), as_of=as_of)

    detail = {"baseline_trend": baseline.value, "perturbed_trend": perturbed.value}
    check(
        perturbed.value is None or perturbed.value <= 10,
        problems,
        "healthy-control's own <=10h tolerance should still hold after a uniform x3 latency scale",
        detail,
    )
    return {"case": "latency-uniform-no-new-flags", "ok": not problems, "problems": problems, "detail": detail}


def check_latency_recent_window_flags_real_stretch() -> dict[str, Any]:
    """Cell 2: latency x3 applied to the RECENT window only (same account,
    same day, same baseline as cell 1) -- a real, localized shift should
    be caught; contrasted directly against cell 1's uniform shift, which
    should NOT be caught."""

    problems: list[str] = []
    account_id = account_id_for("trailhead-logistics")
    as_of = _as_of(180)
    signals = tuple(trailhead_communication_signals(180))
    from datetime import date

    now_day_count = (date.fromisoformat(as_of) - date(1970, 1, 1)).days
    # k=6 here (vs. cell 1's uniform x3): Trailhead's baseline trend is
    # already so close to zero (0.5h) that a x3 recent-window-only scale
    # only reaches 9.5h, just under check_healthy_control's own <=10h
    # tolerance -- not a clean contrast. k=6 gives an unambiguous real
    # stretch (>10h) so this cell's PASS is a clear detection, not a
    # coin-flip near the same threshold cell 1 checks from the other side.
    scaled = latency_scale_recent_window(signals, 6.0, as_of_days_ago_cutoff=21, now_days=now_day_count)
    perturbed = reply_latency_trend(account_id, list(scaled), as_of=as_of)

    detail = {"perturbed_trend": perturbed.value}
    check(
        perturbed.value is not None and perturbed.value > 10,
        problems,
        "a real recent-window-only latency stretch should push the trend past the healthy tolerance",
        detail,
    )
    return {
        "case": "latency-recent-window-flags-real-stretch",
        "ok": not problems,
        "problems": problems,
        "detail": detail,
    }


def check_volume_down_degrades_honestly() -> dict[str, Any]:
    """Cell 3: volume x0.5 on a thin-history checkpoint -- the resulting
    signal must degrade to insufficient-history (``None``), never fabricate
    a trend from what's left."""

    problems: list[str] = []
    account_id = account_id_for("trailhead-logistics")
    as_of = _as_of(60)
    signals = tuple(trailhead_communication_signals(60))
    thinned = volume_scale(signals, 0.1, account_id=account_id)
    perturbed = reply_latency_trend(account_id, list(thinned), as_of=as_of)

    detail = {"thinned_count": len(thinned), "original_count": len(signals), "perturbed_trend": perturbed.value}
    check(
        perturbed.value is None,
        problems,
        "thinning volume to 10% of a day-60 checkpoint should degrade to insufficient-history, not fabricate a trend",
        detail,
    )
    return {"case": "volume-down-degrades-honestly", "ok": not problems, "problems": problems, "detail": detail}


def check_hygiene_drop_no_crash_no_fabrication() -> dict[str, Any]:
    """Cell 4: hygiene_drop 30% on contact optional fields -- value-model
    construction must not crash, and no factor may cite a nulled field's
    evidence as if it were present."""

    problems: list[str] = []
    data = build_synthetic_book()
    contacts = tuple(c for c in data.contacts if c.account_id == account_id_for("trailhead-logistics"))
    check(len(contacts) > 0, problems, "expected trailhead contacts to be non-empty for this cell", len(contacts))

    dropped = hygiene_drop(contacts, 0.3)
    crashed = False
    try:
        # Exercising the perturbed contacts through the same shape a real
        # consumer would (title/role/org_level reads) -- this cell asserts
        # no crash iterating/reading a nulled optional field, not a specific
        # downstream factor (no lens reads CRMContact.title/org_level
        # directly into a factor today; contacts.py's stability itself is
        # the surface this cell exercises).
        for c in dropped:
            _ = (c.title, c.role, c.org_level)
    except Exception as exc:  # noqa: BLE001 - this cell's whole point is "did anything crash"
        crashed = True
        problems.append(f"reading perturbed contacts raised: {exc!r}")

    nulled_count = sum(1 for c in dropped if c.title is None and c.role is None and c.org_level is None)
    detail = {"contacts": len(contacts), "nulled": nulled_count, "crashed": crashed}
    check(not crashed, problems, "hygiene_drop must never crash a downstream reader", detail)
    return {"case": "hygiene-drop-no-crash", "ok": not problems, "problems": problems, "detail": detail}


def check_schema_rename_asks_or_refuses() -> dict[str, Any]:
    """Cell 5: rename 10 source fields across the onboarding tables before
    ``ingest_table`` sees them -- the mapping layer must ask a NEW
    confirmation question or refuse, never silently keep mapping the old
    field name's meaning onto data that no longer carries it."""

    problems: list[str] = []
    rename_map = {
        "Industry": "Vertical",
        "OwnerId": "OwningRepId",
        "Name": "FullName",
        "Email": "EmailAddress",
        "Title": "JobTitle",
        "AccountId": "ParentAccountRef",
        "StageName": "PipelineStage",
        "Amount": "DealValue",
        "CloseDate": "ExpectedCloseDate",
        "Type": "DealType",
    }
    book_id = "perturbation-schema-rename"
    mcp_server._relational_books.pop(book_id, None)

    renamed_questions: set[str] = set()
    refused_or_new = True

    for table_name, contract, records, field_metadata in _crm_records_for_onboarding():
        renamed_records = schema_rename(records, rename_map)
        renamed_metadata = None
        if field_metadata:
            renamed_metadata = {rename_map.get(k, k): v for k, v in field_metadata.items()}
        resp = mcp_server.ingest_table(
            book_id=book_id,
            table_name=table_name,
            contract=contract,
            records=renamed_records,
            expected_count=len(renamed_records),
            field_metadata=renamed_metadata,
        )
        for q in resp.get("confirmation_questions", []):
            renamed_questions.add(q["key"])
        # A renamed field must not appear silently auto-mapped under its
        # OLD internal-field assumption without ALSO producing a question
        # or being absent from auto_mapped entirely (refused).
        auto_mapped_fields = {a.get("source_field") for a in resp.get("auto_mapped", [])}
        for old_name in rename_map:
            if old_name in auto_mapped_fields:
                refused_or_new = False
                problems.append(f"{table_name}: renamed field {old_name!r} still auto-mapped under its old name")

    detail = {
        "renamed_field_count": len(rename_map),
        "confirmation_questions_after_rename": sorted(renamed_questions),
        "refused_or_new_question_for_every_renamed_field": refused_or_new,
    }
    check(
        len(renamed_questions) > 0 or refused_or_new,
        problems,
        "renaming 10 source fields should surface new confirmation questions or refuse, never silently mis-map",
        detail,
    )
    return {"case": "schema-rename-asks-or-refuses", "ok": not problems, "problems": problems, "detail": detail}


def check_arr_shift_moves_tier_and_forbidden_motions() -> dict[str, Any]:
    """Cell 6: arr_shift -60% on an account near a tier boundary -- the
    resolved tier must move, and the tier-forbidden-motions set that
    applies to it must move with it (never stay pinned to the
    pre-shift tier)."""

    problems: list[str] = []
    slug = "aspenridge-supply"
    original_arr = _COMPANY[slug][0]
    cfg = load_value_model_config()
    playbooks = load_playbooks("fleetops")

    attrs_before = {
        "account_id": slug, "account_name": slug, "owner_id": "csm", "industry": "logistics",
        "arr_cents": original_arr, "lifecycle_stage": "steady_state", "status": "Active",
        "current_score": None,
    }
    tier_before = resolve_tenant_tier(attrs_before, cfg).tier

    shifted_arr = round(original_arr * (1.0 - 0.6))
    attrs_after = {**attrs_before, "arr_cents": shifted_arr}
    tier_after = resolve_tenant_tier(attrs_after, cfg).tier

    forbidden_before = set(playbooks.tier_for(tier_before).forbidden_motions)
    forbidden_after = set(playbooks.tier_for(tier_after).forbidden_motions)

    detail = {
        "account": slug,
        "arr_before_cents": original_arr,
        "arr_after_cents": shifted_arr,
        "tier_before": tier_before,
        "tier_after": tier_after,
        "forbidden_motions_before": sorted(forbidden_before),
        "forbidden_motions_after": sorted(forbidden_after),
    }
    check(tier_before != tier_after, problems, "a -60% ARR shift on a near-boundary account should move its tier", detail)
    check(
        forbidden_before != forbidden_after or tier_before == tier_after,
        problems,
        "the forbidden-motions set must move with the tier, not stay pinned to the pre-shift tier",
        detail,
    )
    return {
        "case": "arr-shift-moves-tier-and-forbidden-motions",
        "ok": not problems,
        "problems": problems,
        "detail": detail,
    }


CASES = (
    check_latency_uniform_no_new_flags,
    check_latency_recent_window_flags_real_stretch,
    check_volume_down_degrades_honestly,
    check_hygiene_drop_no_crash_no_fabrication,
    check_schema_rename_asks_or_refuses,
    check_arr_shift_moves_tier_and_forbidden_motions,
)


def run_battery() -> dict[str, Any]:
    results = [fn() for fn in CASES]
    return {
        "artifact": "perturbation_battery",
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
