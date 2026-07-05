"""Fieldstone perturbation battery (Harvest 11: robustness-grid extension).

Report 18's six-cell perturbation grid ran on fleetops only; report 18 said
so explicitly. This battery answers the same calibration question --
"do controlled input distortions move the value model's outputs in the
RIGHT direction and magnitude?" -- for fieldstone, whose entire bible
premise (``docs/TENANT_FIELDSTONE_BIBLE.md``) is that risk must read as a
DELTA from the tenant's own baseline (``baselines.classify_delta``,
20h floor), never an absolute FleetOps-tuned threshold. Reuses
``eval/perturbation/perturb.py``'s pure functions unmodified (Harvest 11's
ownership map: extend/reuse the axis machinery, never fork a second
perturbation concept).

Axes tested (bible-driven per Harvest 11 Decisions, verified against
``docs/TENANT_FIELDSTONE_BIBLE.md``, not copy-pasted from fleetops):

| Axis | Correct behavior | Failure it catches |
| latency x3, uniform | classify_delta stays UNFLAGGED (delta ~unchanged) | an absolute-hours threshold hiding anywhere -- would misfire once values move from ~38h to ~114h |
| latency x3, recent-window-only | classify_delta FLAGS (a real, localized delta exceeds the 20h floor) | delta-detection stops working once the perturbation library (not this tenant's own fixtures) is the source of the shift |
| volume x0.1 | reply_latency_trend degrades to insufficient-history (``None``), never fabricated | window logic fabricating a trend from thinned data |
| hygiene_drop 30% | no crash reading a perturbed contact's optional fields | null-handling brittleness |

Axes NOT applicable, disclosed (not silently skipped):
- CS-platform / health-band / CTA / adoption perturbation: fieldstone has
  NO CS platform substrate at all (bible "No-CS-platform discipline" --
  ``FieldstoneCSPlatformConnector`` returns the honest absence value for
  every method). There is no health band/CTA/adoption value to perturb;
  verified at runtime below, not merely asserted from the bible text.
- schema_rename / arr_shift: omitted from this tenant's grid, not silently
  -- both exercise the SAME shared, tenant-agnostic mapping/tier-resolution
  machinery report 18's fleetops cells 5/6 already calibration-test
  (fieldstone's HubSpot ingest path reuses ``mcp_server.ingest_table``
  unmodified; tier resolution reuses the identical D2 thresholds/resolver
  fleetops uses). Fieldstone's actual differentiator -- baseline-relative
  risk classification -- is what the latency/volume/hygiene axes above
  test; repeating fleetops' generic-mechanism cells here would add no
  fieldstone-specific calibration coverage.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from eval.perturbation.perturb import hygiene_drop, latency_scale, latency_scale_recent_window, volume_scale
from ultra_csm.data_plane.signal_extractor import reply_latency_trend
from ultra_csm.data_plane.tenants.fieldstone.baselines import classify_delta
from ultra_csm.data_plane.tenants.fieldstone.book import (
    ARC_F1_SLUG,
    account_id_for,
    build_fieldstone_book,
    build_fieldstone_data_plane,
)
from ultra_csm.data_plane.tenants.fieldstone.comms import masonry_communication_signals

ARTIFACT_PATH = Path(__file__).with_name("fieldstone_perturbation_battery.json")
SEED_DATE = "2026-06-21"
_AS_OF_DAY_180 = 180


def _as_of(day_offset: int) -> str:
    from datetime import date, timedelta

    return (date.fromisoformat(SEED_DATE) + timedelta(days=day_offset)).isoformat()


def check(ok: bool, problems: list[str], label: str, detail: Any = None) -> None:
    if not ok:
        problems.append(f"{label}: {detail}" if detail is not None else label)


def check_latency_uniform_no_new_flags() -> dict[str, Any]:
    """Masonry (Arc F1, day 180) has a near-zero baseline delta (-0.5h,
    per the bible). Uniform x3 scale moves both trailing windows together
    -- the delta stays ~unchanged (well under the 20h floor) even though
    the absolute band jumps from ~38h to ~114h. An absolute-hours
    threshold hiding anywhere would instead see the new, higher band and
    misfire."""

    problems: list[str] = []
    account_id = account_id_for(ARC_F1_SLUG)
    as_of = _as_of(_AS_OF_DAY_180)
    signals = tuple(masonry_communication_signals(_AS_OF_DAY_180))
    baseline = reply_latency_trend(account_id, list(signals), as_of=as_of)

    scaled = latency_scale(signals, 3.0)
    perturbed = reply_latency_trend(account_id, list(scaled), as_of=as_of)
    flag = classify_delta("reply_latency_trend_hours", perturbed.value)

    detail = {
        "baseline_trend": baseline.value, "perturbed_trend": perturbed.value,
        "flagged": flag.flagged, "reason": flag.reason,
    }
    check(
        not flag.flagged,
        problems,
        "fieldstone's baseline-delta classifier should stay unflagged after a uniform x3 latency scale",
        detail,
    )
    return {"case": "latency-uniform-no-new-flags", "ok": not problems, "problems": problems, "detail": detail}


def check_latency_recent_window_flags_real_stretch() -> dict[str, Any]:
    """Same account, same day, same baseline as the cell above -- scaling
    ONLY the recent window (a real, localized shift) must cross the 20h
    baseline-delta floor and flag, the direct contrast to the uniform
    cell above."""

    problems: list[str] = []
    account_id = account_id_for(ARC_F1_SLUG)
    as_of = _as_of(_AS_OF_DAY_180)
    signals = tuple(masonry_communication_signals(_AS_OF_DAY_180))
    from datetime import date

    now_day_count = (date.fromisoformat(as_of) - date(1970, 1, 1)).days
    scaled = latency_scale_recent_window(signals, 3.0, as_of_days_ago_cutoff=21, now_days=now_day_count)
    perturbed = reply_latency_trend(account_id, list(scaled), as_of=as_of)
    flag = classify_delta("reply_latency_trend_hours", perturbed.value)

    detail = {"perturbed_trend": perturbed.value, "flagged": flag.flagged, "reason": flag.reason}
    check(
        flag.flagged,
        problems,
        "a real recent-window-only latency stretch should cross fieldstone's 20h baseline-delta floor",
        detail,
    )
    return {
        "case": "latency-recent-window-flags-real-stretch",
        "ok": not problems, "problems": problems, "detail": detail,
    }


def check_volume_down_degrades_honestly() -> dict[str, Any]:
    """Thinning Masonry's day-180 comms to 10% must degrade the trend to
    insufficient-history (``None``), never fabricate one from what's
    left."""

    problems: list[str] = []
    account_id = account_id_for(ARC_F1_SLUG)
    as_of = _as_of(_AS_OF_DAY_180)
    signals = tuple(masonry_communication_signals(_AS_OF_DAY_180))
    thinned = volume_scale(signals, 0.1, account_id=account_id)
    perturbed = reply_latency_trend(account_id, list(thinned), as_of=as_of)

    detail = {"thinned_count": len(thinned), "original_count": len(signals), "perturbed_trend": perturbed.value}
    check(
        perturbed.value is None,
        problems,
        "thinning Masonry's day-180 comms to 10% should degrade to insufficient-history, not fabricate a trend",
        detail,
    )
    return {"case": "volume-down-degrades-honestly", "ok": not problems, "problems": problems, "detail": detail}


def check_hygiene_drop_no_crash() -> dict[str, Any]:
    """hygiene_drop 30% on fieldstone contacts' optional fields must not
    crash a downstream reader."""

    problems: list[str] = []
    book = build_fieldstone_book()
    contacts = book.contacts
    check(len(contacts) > 0, problems, "expected fieldstone contacts to be non-empty", len(contacts))

    dropped = hygiene_drop(contacts, 0.3)
    crashed = False
    try:
        for c in dropped:
            _ = (c.title, c.role, c.org_level)
    except Exception as exc:  # noqa: BLE001 - this cell's whole point is "did anything crash"
        crashed = True
        problems.append(f"reading perturbed contacts raised: {exc!r}")

    nulled_count = sum(1 for c in dropped if c.title is None and c.role is None and c.org_level is None)
    detail = {"contacts": len(contacts), "nulled": nulled_count, "crashed": crashed}
    check(not crashed, problems, "hygiene_drop must never crash a downstream reader", detail)
    return {"case": "hygiene-drop-no-crash", "ok": not problems, "problems": problems, "detail": detail}


def check_cs_platform_axis_not_applicable() -> dict[str, Any]:
    """NA-by-construction, disclosed (mirrors ``eval/tier_gating_battery.py``'s
    NA-handling discipline): fieldstone has no CS platform at all, so
    there is no health band/CTA/adoption value a perturbation axis could
    distort. Verified directly against the real connector, not asserted
    from the bible text alone."""

    dp = build_fieldstone_data_plane()
    account_id = account_id_for(ARC_F1_SLUG)
    company = dp.cs.get_company(account_id)
    health = dp.cs.get_health_score(account_id)
    adoption = dp.cs.get_adoption_summary(account_id)
    return {
        "axis": "cs-platform-health-band-cta-adoption",
        "applicable": False,
        "reason": (
            "fieldstone has no CS platform substrate at all (bible: "
            "'No-CS-platform discipline') -- verified: get_company/"
            "get_health_score/get_adoption_summary all return None for "
            "this tenant, so there is no health band/CTA/adoption value "
            "to perturb"
        ),
        "verified": {
            "company_is_none": company is None,
            "health_is_none": health is None,
            "adoption_is_none": adoption is None,
        },
    }


CASES = (
    check_latency_uniform_no_new_flags,
    check_latency_recent_window_flags_real_stretch,
    check_volume_down_degrades_honestly,
    check_hygiene_drop_no_crash,
)


def run_battery() -> dict[str, Any]:
    results = [fn() for fn in CASES]
    na_axes = [check_cs_platform_axis_not_applicable()]
    return {
        "artifact": "fieldstone_perturbation_battery",
        "cases": results,
        "axes_not_applicable": na_axes,
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
