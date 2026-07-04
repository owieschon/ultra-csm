"""Universe v2 WS-Safety: eval.canary_battery structural checks."""

from __future__ import annotations

from eval.canary_battery import run_battery


def test_canary_battery_hard_ok():
    report = run_battery()
    assert report["hard_ok"], report["failed_cases"]
    assert len(report["cases"]) == 5


def test_canary_battery_two_runs_byte_identical():
    import json

    first = run_battery()
    second = run_battery()
    assert json.dumps(first, sort_keys=True, default=str) == json.dumps(
        second, sort_keys=True, default=str
    )
