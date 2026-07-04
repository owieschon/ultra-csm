"""The quantity-reconciliation battery must hold for every canon-table row
and be deterministic across two runs (Universe v2, WS-Data-Classes
Phase 1)."""

from __future__ import annotations

from eval.quantity_battery import CASES, run_battery


def test_quantity_battery_holds_for_every_case():
    report = run_battery()
    assert report["hard_ok"], f"failing cases: {report['failed_cases']}"
    assert len(report["cases"]) == len(CASES)


def test_quantity_battery_is_deterministic_across_two_runs():
    first = run_battery()
    second = run_battery()
    assert first == second


def test_pinehill_day8_known_variance_is_recorded_not_silently_fixed():
    report = run_battery()
    case = next(c for c in report["cases"] if c["case"] == "pinehill_day8_known_variance")
    assert case["ok"], case["problems"]
    assert case["detail"]["status"] == "known_variance"
    assert case["detail"]["claimed_active"] == 22
    assert case["detail"]["simulator_active_assets"] == 12
