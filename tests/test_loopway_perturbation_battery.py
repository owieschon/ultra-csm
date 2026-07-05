"""Harvest 11 robustness-grid extension: eval.loopway_perturbation_battery structural checks."""

from __future__ import annotations

import json

from eval.loopway_perturbation_battery import run_battery


def test_loopway_perturbation_battery_hard_ok_within_budget():
    report = run_battery()
    assert report["hard_ok"], report["failed_cases"]
    assert len(report["cases"]) == 3
    assert report["within_runtime_budget"]


def test_loopway_perturbation_battery_two_runs_byte_identical():
    first = run_battery()
    second = run_battery()
    for report in (first, second):
        del report["runtime_seconds"]
    assert json.dumps(first, sort_keys=True, default=str) == json.dumps(
        second, sort_keys=True, default=str
    )
