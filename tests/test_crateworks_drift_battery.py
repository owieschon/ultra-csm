"""Harvest 11 robustness-grid extension: eval.crateworks_drift_battery structural checks.

One test, two calls (not four across separate tests) -- the schema-rename
check boots an ephemeral Postgres cluster per call, mirroring
``tests/test_drift_battery.py``'s runtime discipline.
"""

from __future__ import annotations

import json

from eval.crateworks_drift_battery import run_battery


def test_crateworks_drift_battery_hard_ok_and_repeatable():
    first = run_battery()
    assert first["hard_ok"], first["failed_cases"]
    assert len(first["cases"]) == 2
    assert len(first["axes_not_applicable"]) == 1

    second = run_battery()
    assert json.dumps(first, sort_keys=True, default=str) == json.dumps(
        second, sort_keys=True, default=str
    )
