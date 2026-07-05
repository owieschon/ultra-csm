"""Harvest 11 robustness-grid extension: eval.crateworks_perturbation_battery structural checks."""

from __future__ import annotations

import json

from eval.crateworks_perturbation_battery import run_battery


def test_crateworks_perturbation_battery_hard_ok():
    report = run_battery()
    assert report["hard_ok"], report["failed_cases"]
    assert len(report["cases"]) == 3
    assert len(report["axes_not_applicable"]) == 2


def test_crateworks_perturbation_battery_two_runs_byte_identical():
    first = run_battery()
    second = run_battery()
    assert json.dumps(first, sort_keys=True, default=str) == json.dumps(
        second, sort_keys=True, default=str
    )
