"""Universe v2 WS-Perturbation-Drift: eval.perturbation_battery structural checks."""

from __future__ import annotations

import json

from eval.perturbation_battery import run_battery


def test_perturbation_battery_hard_ok():
    report = run_battery()
    assert report["hard_ok"], report["failed_cases"]
    assert len(report["cases"]) == 6


def test_perturbation_battery_two_runs_byte_identical():
    first = run_battery()
    second = run_battery()
    assert json.dumps(first, sort_keys=True, default=str) == json.dumps(
        second, sort_keys=True, default=str
    )
