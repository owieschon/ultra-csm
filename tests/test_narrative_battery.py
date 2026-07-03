"""The narrative property battery must hold for every arc/herring/control
case, and hold identically across two runs (fully deterministic, no
randomness anywhere in the Synthetic Tenant Universe)."""

from __future__ import annotations

from eval.narrative_battery import CASES, run_battery


def test_narrative_battery_holds_for_every_case():
    report = run_battery()
    assert report["hard_ok"], f"failing cases: {report['failed_cases']}"
    assert len(report["cases"]) == len(CASES)


def test_narrative_battery_is_deterministic_across_two_runs():
    first = run_battery()
    second = run_battery()
    assert first == second


def test_onboarding_stall_pilot_shows_the_stall_and_the_recovery():
    report = run_battery()
    case = next(c for c in report["cases"] if c["case"] == "onboarding-stall")
    assert case["ok"], case["problems"]
    assert case["detail"]["during"]["latency"] > 15
    assert not any(case["detail"]["after"]["gaps"].values())


def test_boring_controls_and_red_herrings_are_never_contaminated():
    report = run_battery()
    controls = next(c for c in report["cases"] if c["case"] == "boring-controls")
    herrings = next(c for c in report["cases"] if c["case"] == "red-herrings")
    assert controls["ok"], controls["problems"]
    assert herrings["ok"], herrings["problems"]
