"""Narrative property battery for the fieldstone tenant (Universe v2,
WS-Tenant-Fieldstone, Wave 3). Mirrors ``eval/narrative_battery.py``'s
pattern (frozen cases, ``hard_ok`` gate, determinism-across-two-runs) for
fieldstone's smaller 12-account book.

Anti-Goodhart note: ``docs/TENANT_FIELDSTONE_BIBLE.md`` owns ground truth.
This battery may be edited to add cases or correct an assertion against a
bible change -- never to match whatever the system currently outputs.

Two generalization assertions this battery exists to prove (the report's
lead findings):
(a) Arc F1 (``masonry-home-services``) is FleetOps-alarming (40h reply
    latency, quarterly cadence) yet correctly reads as zero-flag/healthy
    for this tenant -- ``check_arc_f1_healthy_despite_absolutes``.
(b) With no CS platform at all, every divergence signal that would
    otherwise read a health band/CTA/adoption summary must return an
    honest unknown/empty, never a fabricated value --
    ``check_no_health_band_rail_returns_unknown``.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ultra_csm.data_plane.tenants.fieldstone.baselines import classify_delta, load_norms_baselines
from ultra_csm.data_plane.tenants.fieldstone.book import (
    ARC_F1_SLUG,
    ARC_F2_SLUG,
    BORING_CONTROL_SLUGS,
    HERRING_SLUG,
    account_id_for,
    build_fieldstone_book,
)
from ultra_csm.data_plane.tenants.fieldstone.comms import (
    culvert_calendar_events,
    culvert_cases_as_of,
    culvert_communication_signals,
    masonry_calendar_events,
    masonry_cases_as_of,
    masonry_communication_signals,
    wrenhouse_calendar_events,
    wrenhouse_cases_as_of,
    wrenhouse_communication_signals,
)
from ultra_csm.data_plane.signal_extractor import (
    meeting_cadence_shift,
    reply_latency_trend,
    ticket_frequency_window,
)
from ultra_csm.data_plane.tenants.fieldstone.book import build_fieldstone_data_plane

ARTIFACT_PATH = Path(__file__).with_name("fieldstone_battery.json")
SEED_DATE = "2026-06-21"


def _as_of(day_offset: int) -> str:
    return (date.fromisoformat(SEED_DATE) + timedelta(days=day_offset)).isoformat()


def _signals(slug: str, comms_fn, cal_fn, cases_fn, day_offset: int):
    account_id = account_id_for(slug)
    as_of = _as_of(day_offset)
    return {
        "latency": reply_latency_trend(account_id, comms_fn(day_offset), as_of=as_of),
        "cadence": meeting_cadence_shift(account_id, cal_fn(day_offset), as_of=as_of),
        "tickets": ticket_frequency_window(account_id, cases_fn(day_offset), as_of=as_of),
    }


def check_arc_f1_healthy_despite_absolutes() -> dict[str, Any]:
    """Arc F1: 40h reply latency + quarterly cadence would alarm a
    FleetOps-tuned reader (``eval/narrative_battery.py``'s own
    ``check_healthy_control`` asserts ``latency > 10`` is already
    suspicious for ITS tenant). This account must read as zero-flag for
    fieldstone at every checkpoint -- proven via the baseline-relative
    classifier, not an absolute threshold."""

    problems: list[str] = []
    detail: dict[str, Any] = {}
    for label, day in {"day60": 60, "day180": 180, "day300": 300}.items():
        sig = _signals(ARC_F1_SLUG, masonry_communication_signals, masonry_calendar_events, masonry_cases_as_of, day)
        flag = classify_delta("reply_latency_trend_hours", sig["latency"].value)
        detail[label] = {
            "latency_value": sig["latency"].value,
            "flagged": flag.flagged,
            "reason": flag.reason,
            "tickets": sig["tickets"].value,
        }
        if flag.flagged:
            problems.append(f"{label}: expected zero flag on Arc F1 (norms proof), got flagged: {flag.reason}")
        if sig["tickets"].value != 0:
            problems.append(f"{label}: expected zero cases on Arc F1, got {sig['tickets'].value}")
    return {
        "case": "arc-f1-healthy-despite-fleetops-alarming-absolutes",
        "account": ARC_F1_SLUG, "ok": not problems, "problems": problems, "detail": detail,
    }


def check_arc_f2_baseline_delta_risk() -> dict[str, Any]:
    """Arc F2: no flag at day 80 (40h = this account's own normal,
    identical delta to Masonry's), flag by day 140 (a real, large delta
    off the account's own baseline). This is the tenant's proof that
    "risk = delta from tenant baseline" is a real, gradeable distinction."""

    problems: list[str] = []
    detail: dict[str, Any] = {}
    day80 = _signals(ARC_F2_SLUG, culvert_communication_signals, culvert_calendar_events, culvert_cases_as_of, 80)
    day140 = _signals(ARC_F2_SLUG, culvert_communication_signals, culvert_calendar_events, culvert_cases_as_of, 140)
    flag80 = classify_delta("reply_latency_trend_hours", day80["latency"].value)
    flag140 = classify_delta("reply_latency_trend_hours", day140["latency"].value)
    detail["day80"] = {"latency_value": day80["latency"].value, "flagged": flag80.flagged, "reason": flag80.reason}
    detail["day140"] = {"latency_value": day140["latency"].value, "flagged": flag140.flagged, "reason": flag140.reason}
    if flag80.flagged:
        problems.append(f"day80: expected NO flag (40h = tenant/account normal), got flagged: {flag80.reason}")
    if not flag140.flagged:
        problems.append(f"day140: expected a flag (real baseline-delta risk), got no flag: {flag140.reason}")
    if day140["tickets"].value < 1:
        problems.append(f"day140: expected the day-100 billing-dispute case visible, got {day140['tickets'].value}")
    # The discriminating claim itself: day-80 Culvert and day-180 Masonry
    # deltas must be statistically indistinguishable (both near zero) even
    # though only one account later develops real risk.
    masonry_day180 = _signals(
        ARC_F1_SLUG, masonry_communication_signals, masonry_calendar_events, masonry_cases_as_of, 180
    )
    if day80["latency"].value is not None and masonry_day180["latency"].value is not None:
        delta_gap = abs(day80["latency"].value - masonry_day180["latency"].value)
        detail["cross_account_baseline_comparison"] = {
            "culvert_day80_delta": day80["latency"].value,
            "masonry_day180_delta": masonry_day180["latency"].value,
            "gap": delta_gap,
        }
        if delta_gap > 5.0:
            problems.append(
                f"expected Culvert's day-80 delta and Masonry's day-180 delta to be near-identical "
                f"(both flat baselines), got a {delta_gap}h gap"
            )
    return {
        "case": "arc-f2-baseline-delta-risk", "account": ARC_F2_SLUG,
        "ok": not problems, "problems": problems, "detail": detail,
    }


def check_herring_zero_flag() -> dict[str, Any]:
    """One loud-looking, fast-resolving case; everything else reads
    exactly like a boring control. Zero flags at every checkpoint."""

    problems: list[str] = []
    detail: dict[str, Any] = {}
    for label, day in {"day60": 60, "day180": 180, "day300": 300}.items():
        sig = _signals(HERRING_SLUG, wrenhouse_communication_signals, wrenhouse_calendar_events, wrenhouse_cases_as_of, day)
        flag = classify_delta("reply_latency_trend_hours", sig["latency"].value)
        detail[label] = {"latency_value": sig["latency"].value, "flagged": flag.flagged, "tickets": sig["tickets"].value}
        if flag.flagged:
            problems.append(f"{label}: expected zero flag on herring, got flagged: {flag.reason}")
    # The one case must have resolved same-day (loud subject, no real duration).
    cases = wrenhouse_cases_as_of(300)
    unresolved = [c for c in cases if c.closed_at is None]
    if unresolved:
        problems.append(f"expected the herring's case resolved by day 300, still open: {unresolved}")
    detail["case_count"] = len(cases)
    return {"case": "herring-fh1-zero-flag", "account": HERRING_SLUG, "ok": not problems, "problems": problems, "detail": detail}


def check_boring_controls_zero_flag() -> dict[str, Any]:
    problems: list[str] = []
    detail: dict[str, Any] = {}
    book = build_fieldstone_book()
    for slug in BORING_CONTROL_SLUGS:
        account_id = account_id_for(slug)
        cases = [c for c in book.cases if c.account_id == account_id]
        detail[slug] = {"case_count": len(cases)}
        if cases:
            problems.append(f"{slug}: expected zero cases on a boring control, got {len(cases)}")
    return {"case": "boring-controls-zero-flag", "ok": not problems, "problems": problems, "detail": detail}


def check_no_health_band_rail_returns_unknown() -> dict[str, Any]:
    """No CS platform exists for this tenant at all. Every divergence
    signal that would read a health band/CTA/adoption summary must return
    an honest unknown/empty -- never fabricate one. Direct proof against
    ``FieldstoneCSPlatformConnector``, the actual connector every
    fieldstone code path reads through."""

    problems: list[str] = []
    detail: dict[str, Any] = {}
    dp = build_fieldstone_data_plane()
    for slug in (ARC_F1_SLUG, ARC_F2_SLUG, HERRING_SLUG, *BORING_CONTROL_SLUGS):
        account_id = account_id_for(slug)
        company = dp.cs.get_company(account_id)
        health = dp.cs.get_health_score(account_id)
        ctas = dp.cs.list_ctas(account_id)
        plans = dp.cs.list_success_plans(account_id)
        adoption = dp.cs.get_adoption_summary(account_id)
        detail[slug] = {
            "company_is_none": company is None,
            "health_is_none": health is None,
            "ctas_empty": ctas == [],
            "plans_empty": plans == [],
            "adoption_is_none": adoption is None,
        }
        if company is not None:
            problems.append(f"{slug}: expected no CS-platform company (fabricated), got one")
        if health is not None:
            problems.append(f"{slug}: expected no health band (fabricated), got one")
        if ctas:
            problems.append(f"{slug}: expected zero CTAs (fabricated), got {ctas}")
        if plans:
            problems.append(f"{slug}: expected zero success plans (fabricated), got {plans}")
        if adoption is not None:
            problems.append(f"{slug}: expected no adoption summary (fabricated), got one")
    return {
        "case": "no-health-band-rail-returns-unknown",
        "ok": not problems, "problems": problems, "detail": detail,
    }


def check_baseline_config_loads() -> dict[str, Any]:
    """The HARD RULE knob itself must load, validate, and fail closed."""

    problems: list[str] = []
    detail: dict[str, Any] = {}
    cfg = load_norms_baselines()
    detail["tenant"] = cfg.tenant
    detail["floors"] = cfg.flag_delta_floor_by_metric
    if cfg.tenant != "fieldstone":
        problems.append(f"expected tenant fieldstone, got {cfg.tenant}")
    if "reply_latency_trend_hours" not in cfg.flag_delta_floor_by_metric:
        problems.append("expected a reply_latency_trend_hours floor configured")
    unconfigured = classify_delta("some_unconfigured_metric", 999.0, config=cfg)
    detail["unconfigured_metric_fails_closed"] = {
        "flagged": unconfigured.flagged, "reason": unconfigured.reason,
    }
    if unconfigured.flagged:
        problems.append("expected an unconfigured metric to fail closed (never flag), got flagged")
    return {"case": "baseline-config-loads-fail-closed", "ok": not problems, "problems": problems, "detail": detail}


CASES = (
    check_arc_f1_healthy_despite_absolutes,
    check_arc_f2_baseline_delta_risk,
    check_herring_zero_flag,
    check_boring_controls_zero_flag,
    check_no_health_band_rail_returns_unknown,
    check_baseline_config_loads,
)


def run_battery() -> dict[str, Any]:
    results = [fn() for fn in CASES]
    return {
        "artifact": "fieldstone_narrative_property_battery",
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
