"""Harvest 11 robustness-grid extension: eval.fieldstone_perturbation_battery structural checks."""

from __future__ import annotations

import json

from eval.fieldstone_perturbation_battery import run_battery


def test_fieldstone_perturbation_battery_hard_ok():
    report = run_battery()
    assert report["hard_ok"], report["failed_cases"]
    assert len(report["cases"]) == 4
    assert len(report["axes_not_applicable"]) == 1


def test_fieldstone_perturbation_battery_two_runs_byte_identical():
    first = run_battery()
    second = run_battery()
    assert json.dumps(first, sort_keys=True, default=str) == json.dumps(
        second, sort_keys=True, default=str
    )
