"""The relational property battery must hold across all frozen seeds, and the
metadata-first path (source-declared foreign keys) must wire correctly."""

from __future__ import annotations

from eval.relational_battery import SEEDS, check_seed, run_battery


def test_property_battery_holds_for_every_seed():
    report = run_battery()
    assert report["hard_ok"], f"failing seeds: {report['failed_seeds']}"
    assert len(report["cases"]) == len(SEEDS)


def test_battery_is_deterministic_across_two_runs():
    first = run_battery(SEEDS[:5])
    second = run_battery(SEEDS[:5])
    assert first == second


def test_every_seed_wires_source_declared_foreign_keys():
    # The metadata-first invariant: with a source that declares its FKs (as a
    # schema API does), every generated shape ingests with exact ground-truth
    # counts, no fabrication, and the declared FK surfaced as source-declared.
    for seed in SEEDS:
        result = check_seed(seed)
        assert result["ok"], f"seed {seed}: {result['problems']}"
