"""Harvest 12 runtime-chaos: eval.resilience_battery structural checks.

Each case boots/kills its own throwaway EphemeralCluster -- real wall-clock
cost, so this is one test with one call, not a repeatability check
(the point of this battery is that a kill mid-operation is a genuine,
non-deterministic-in-timing fault injection, not a pure function).
"""

from __future__ import annotations

from eval.resilience_battery import run_battery


def test_resilience_battery_hard_ok_within_budget():
    report = run_battery()
    assert report["hard_ok"], report["failed_cases"]
    assert len(report["cases"]) == 4
    assert report["within_runtime_budget"]
