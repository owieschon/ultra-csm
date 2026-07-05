"""Harvest 11 robustness-grid extension: eval.loopway_drift_battery structural checks.

One test, two calls -- the post-drift check re-runs the full
``eval/loopway_battery.py`` suite, mirroring ``tests/test_drift_battery.py``'s
runtime discipline.
"""

from __future__ import annotations

import json

from eval.loopway_drift_battery import run_battery


def test_loopway_drift_battery_hard_ok_and_repeatable_within_budget():
    first = run_battery()
    assert first["hard_ok"], first["failed_cases"]
    assert len(first["cases"]) == 2
    assert first["within_runtime_budget"]
    assert len(first["axes_not_applicable"]) == 1

    second = run_battery()
    for report in (first, second):
        del report["runtime_seconds"]
    assert json.dumps(first, sort_keys=True, default=str) == json.dumps(
        second, sort_keys=True, default=str
    )
