"""Phase 3 (MP-W1R): shape heterogeneity (D2), dirty-data rates (D3),
latent outcome derivation (D5). Deterministic, no LLM."""

from __future__ import annotations

from eval.world_diversity_battery import run_battery
from ultra_csm.world.generator import WorldConfig, generate_world


def test_battery_reports_nonzero_shape_variance_and_passes():
    artifact = run_battery()

    assert artifact["hard_ok"] is True
    assert artifact["evidence_count"]["variance_gt_0"] is True
    assert artifact["factor_count"]["variance_gt_0"] is True
    assert artifact["source_mix"]["variance_gt_0"] is True
    assert len(artifact["source_mix"]["distinct_sources"]) > 1


def test_dirty_data_rates_materialize_within_tolerance():
    artifact = run_battery()

    row = artifact["dirty_data_rates"]
    assert row["ok"] is True
    for kind, configured in row["configured"].items():
        assert abs(row["observed"][kind] - configured) <= row["tolerance"]


def test_latent_outcome_is_a_pure_function_of_doomed_thriving():
    world = generate_world(WorldConfig(seed=7, scale=200))

    for row in world.latent_truth:
        if row.doomed:
            assert row.latent_outcome in ("churned", "downgraded")
        elif row.thriving:
            assert row.latent_outcome == "expanded"
        else:
            assert row.latent_outcome == "flat"


def test_dirty_data_flags_are_independent_and_can_co_occur():
    world = generate_world(WorldConfig(seed=7, scale=400))

    # Independence means SOME account combines at least two flags -- if this
    # never happens across 400 accounts, the three rolls are accidentally
    # correlated (e.g. sharing a hash label) rather than independent.
    co_occurrences = sum(1 for row in world.latent_truth if len(row.data_quality_flags) >= 2)
    assert co_occurrences > 0
