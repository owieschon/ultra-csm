"""Person-factor battery (Harvest 16).

Modeled on eval/narrative_battery.py's pattern: frozen cases against
docs/SYNTHETIC_UNIVERSE_BIBLE.md's arcs (here, the four person-derived
value-model factors this dispatch wires in), a ``hard_ok`` gate, and a
determinism-across-two-runs assertion. No governance gate/Postgres cluster
is needed -- unlike eval/tier_policy_battery.py, this battery asserts
directly against ``CustomerValueModel.divergences``, the same level
eval/narrative_battery.py's checks operate at.

Anti-Goodhart note: this battery may be edited to add cases or correct an
assertion against a bible change -- never edited to match whatever the
system currently outputs without a bible change explaining why the WORLD
changed. Four checks, one per factor:

1. ``champion_departed`` fires on pinnacle-supply (Derek Vaughn's day-5
   departure, within the config window) with evidence citing both the
   JobChangeSignal and the StakeholderRelationship role.
2. ``single_threaded_risk`` (real-graph branch) fires on
   quarrystone-logistics (a single frozen champion row that never gains a
   second) with evidence citing StakeholderRelationship rows, not
   UsageSignal ids.
3. ``new_stakeholder_unengaged`` fires on oakmont-logistics inside its
   authored window (day 70-100) and is silent outside it.
4. ``usage_concentration`` fires on pinnacle-supply's existing person-grain
   UsageSignal, via the promoted ``person_factors.top_user_share`` helper.

A fifth check confirms the proxy-fallback zero-drift property directly:
building the value model with no stakeholders passed reproduces the
pre-existing telemetry-proxy evidence exactly (belt-and-suspenders on top
of ``make eval``'s tests/test_value_model.py assertions).
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ultra_csm.data_plane.book_simulator import simulate_book
from ultra_csm.data_plane.contracts import CustomerDataPlane
from ultra_csm.data_plane.fixtures import (
    FixtureCRMDataConnector,
    FixtureCSPlatformConnector,
    FixtureProductTelemetryConnector,
    account_id_for,
)
from ultra_csm.data_plane.synthetic_book import SEED_DATE, build_synthetic_book
from ultra_csm.value_model import build_customer_value_model, load_value_model_config

ARTIFACT_PATH = Path(__file__).with_name("person_factor_battery.json")


def _as_of(day_offset: int) -> str:
    return (date.fromisoformat(SEED_DATE) + timedelta(days=day_offset)).isoformat()


def _model_at(slug: str, day: int):
    base = build_synthetic_book()
    book = simulate_book(base, day)
    data_plane = CustomerDataPlane(
        crm=FixtureCRMDataConnector(data=book),
        cs=FixtureCSPlatformConnector(data=book),
        telemetry=FixtureProductTelemetryConnector(data=book),
    )
    account_id = account_id_for(slug)
    account = data_plane.crm.get_account(account_id)
    company = data_plane.cs.get_company(account_id)
    health = data_plane.cs.get_health_score(account_id)
    adoption = data_plane.cs.get_adoption_summary(account_id)
    entitlements = tuple(data_plane.telemetry.list_entitlements(account_id))
    usage_signals = tuple(data_plane.telemetry.list_usage_signals(account_id))
    success_plans = tuple(data_plane.cs.list_success_plans(account_id))
    stakeholders = tuple(data_plane.crm.list_stakeholders(account_id))
    job_changes = tuple(data_plane.crm.list_job_changes(account_id))
    as_of = _as_of(day)
    model = build_customer_value_model(
        account=account,
        company=company,
        health=health,
        adoption=adoption,
        entitlements=entitlements,
        usage_signals=usage_signals,
        success_plans=success_plans,
        stakeholders=stakeholders,
        job_changes=job_changes,
        as_of=as_of,
        config=load_value_model_config(),
    )
    return model


def _factor(model, name: str):
    return next((f for f in model.divergences if f.name == name), None)


def check_champion_departed() -> dict[str, Any]:
    problems: list[str] = []
    model = _model_at("pinnacle-supply", 10)
    factor = _factor(model, "champion_departed")
    detail: dict[str, Any] = {"factors": [f.name for f in model.divergences]}
    if factor is None:
        problems.append("champion_departed did not fire on pinnacle-supply day 10")
    else:
        detail["value"] = factor.value
        detail["evidence"] = [str(e) for e in factor.evidence]
        if len(factor.evidence) != 2:
            problems.append(f"expected 2 evidence refs (job-change + role), got {len(factor.evidence)}")
        elif not any(e.field == "change_type" for e in factor.evidence):
            problems.append("no evidence ref cites the JobChangeSignal (field='change_type')")
        elif not any(e.field == "relationship_type" for e in factor.evidence):
            problems.append("no evidence ref cites the StakeholderRelationship role")
    # Silent outside the config window (21 days): day 40 is 35 days after
    # the day-5 departure.
    late_model = _model_at("pinnacle-supply", 40)
    if _factor(late_model, "champion_departed") is not None:
        problems.append("champion_departed still firing at day 40 (outside the 21-day window)")
    return {"case": "champion-departed", "account": "pinnacle-supply", "ok": not problems,
            "problems": problems, "detail": detail}


def check_single_threaded_real_graph() -> dict[str, Any]:
    problems: list[str] = []
    model = _model_at("quarrystone-logistics", 30)
    factor = _factor(model, "single_threaded_risk")
    detail: dict[str, Any] = {"factors": [f.name for f in model.divergences]}
    if factor is None:
        problems.append("single_threaded_risk did not fire on quarrystone-logistics day 30")
    else:
        detail["value"] = factor.value
        detail["threshold_name"] = factor.threshold_name
        detail["evidence"] = [str(e) for e in factor.evidence]
        if factor.threshold_name != "min_threaded_persons":
            problems.append(
                f"expected the real-graph branch (threshold_name=min_threaded_persons), "
                f"got {factor.threshold_name!r} -- may have fallen back to the telemetry proxy"
            )
        if any(e.source == "telemetry" for e in factor.evidence):
            problems.append("evidence cites telemetry (proxy), expected crm (real graph) only")
    return {"case": "single-threaded-real-graph", "account": "quarrystone-logistics", "ok": not problems,
            "problems": problems, "detail": detail}


def check_new_stakeholder_unengaged() -> dict[str, Any]:
    problems: list[str] = []
    detail: dict[str, Any] = {}
    boundary = {"day69": (69, False), "day70": (70, True), "day100": (100, True), "day101": (101, False)}
    for label, (day, expect_fire) in boundary.items():
        model = _model_at("oakmont-logistics", day)
        factor = _factor(model, "new_stakeholder_unengaged")
        fired = factor is not None
        detail[label] = {"fired": fired, "value": factor.value if factor else None}
        if fired != expect_fire:
            problems.append(f"{label}: expected fired={expect_fire}, got {fired}")
        if fired and any(e.source == "cs_platform" for e in factor.evidence):
            problems.append(f"{label}: evidence should cite the stakeholder row (crm), not cs_platform")
    return {"case": "new-stakeholder-unengaged", "account": "oakmont-logistics", "ok": not problems,
            "problems": problems, "detail": detail}


def check_usage_concentration() -> dict[str, Any]:
    problems: list[str] = []
    model = _model_at("pinnacle-supply", 10)
    factor = _factor(model, "usage_concentration")
    detail: dict[str, Any] = {"factors": [f.name for f in model.divergences]}
    if factor is None:
        problems.append("usage_concentration did not fire on pinnacle-supply day 10")
    else:
        detail["value"] = factor.value
        detail["evidence"] = [str(e) for e in factor.evidence]
        if not (0.0 <= factor.value <= 1.0):
            problems.append(f"expected a share in [0, 1], got {factor.value}")
        if not all(e.source == "telemetry" for e in factor.evidence):
            problems.append("evidence should cite telemetry (per-user usage signals)")
    return {"case": "usage-concentration", "account": "pinnacle-supply", "ok": not problems,
            "problems": problems, "detail": detail}


def check_proxy_fallback_zero_drift() -> dict[str, Any]:
    """Direct proof of the zero-drift design: with no stakeholders/job_changes
    passed (every pre-existing caller's behavior), single_threaded_risk must
    reproduce the exact pre-Harvest-16 telemetry-proxy evidence -- belt-and-
    suspenders on top of tests/test_value_model.py's own assertion of this.
    Uses ``sweep_fixture_data()`` (the small ACME/Nova book), the same
    fixture source that unit test exercises."""

    from ultra_csm.data_plane.contracts import UsageSignal
    from ultra_csm.data_plane.fixtures import ACME_LOGISTICS, sweep_fixture_data

    problems: list[str] = []
    data = sweep_fixture_data()
    account = next(a for a in data.accounts if a.account_id == ACME_LOGISTICS)
    company = next(c for c in data.companies if c.company_id == ACME_LOGISTICS)
    health = next(h for h in data.health_scores if h.account_id == ACME_LOGISTICS)
    adoption = next(a for a in data.adoption_summaries if a.account_id == ACME_LOGISTICS)
    plans = tuple(p for p in data.success_plans if p.account_id == ACME_LOGISTICS)
    signal = UsageSignal(
        "person-signal-1", ACME_LOGISTICS, "person", "person-1",
        "sessions", 10.0, "count", "2026-06-21T00:00:00Z", "product-telemetry:sessions",
    )
    model = build_customer_value_model(
        account=account,
        company=company,
        health=health,
        adoption=adoption,
        entitlements=(),
        usage_signals=(signal,),
        success_plans=plans,
        config=load_value_model_config(),
    )
    factor = next((f for f in model.divergences if f.name == "single_threaded_risk"), None)
    detail: dict[str, Any] = {}
    if factor is None:
        problems.append("single_threaded_risk did not fire on the proxy path")
    else:
        detail = {"value": factor.value, "threshold_name": factor.threshold_name,
                  "evidence_source_id": factor.evidence[0].source_id}
        if factor.value != 1.0:
            problems.append(f"expected value 1.0 (proxy path), got {factor.value}")
        if factor.threshold_name != "concentration_ceiling":
            problems.append(f"expected threshold_name=concentration_ceiling (proxy), got {factor.threshold_name}")
        if factor.evidence[0].source_id != "person-signal-1":
            problems.append(f"expected evidence[0].source_id=person-signal-1, got {factor.evidence[0].source_id}")
    return {"case": "proxy-fallback-zero-drift", "account": "acme-logistics", "ok": not problems,
            "problems": problems, "detail": detail}


def check_repeatability() -> dict[str, Any]:
    problems: list[str] = []
    for slug, day in (("pinnacle-supply", 10), ("quarrystone-logistics", 30), ("oakmont-logistics", 90)):
        first = [(f.name, f.value) for f in _model_at(slug, day).divergences]
        second = [(f.name, f.value) for f in _model_at(slug, day).divergences]
        if first != second:
            problems.append(f"{slug} day{day}: non-deterministic divergences ({first} != {second})")
    return {"case": "repeatability", "ok": not problems, "problems": problems}


CASES = (
    check_champion_departed,
    check_single_threaded_real_graph,
    check_new_stakeholder_unengaged,
    check_usage_concentration,
    check_proxy_fallback_zero_drift,
    check_repeatability,
)


def run_battery() -> dict[str, Any]:
    results = [fn() for fn in CASES]
    return {
        "artifact": "person_factor_battery",
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
