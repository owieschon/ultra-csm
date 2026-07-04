"""Universe v2 WS-Perturbation-Drift: eval.drift_battery structural checks.

One test, two calls (not four across separate tests) -- this battery
boots an ephemeral Postgres cluster per call (~10-20s each), so keeping
pytest's own call count minimal matters for `make eval`'s overall runtime.
"""

from __future__ import annotations

import json

from eval.drift_battery import run_battery


def test_drift_battery_hard_ok_and_repeatable():
    first = run_battery()
    assert first["hard_ok"], first["failed_cases"]
    assert len(first["cases"]) == 5

    second = run_battery()
    assert json.dumps(first, sort_keys=True, default=str) == json.dumps(
        second, sort_keys=True, default=str
    )
