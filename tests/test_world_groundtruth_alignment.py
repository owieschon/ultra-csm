"""P1 regression tests: world ground-truth integrity (report 75 F1/F2/F7).

These assert the alignment DIRECTLY (recorded latent == the state that
generated the observables) rather than via an oracle false-negative rate,
which report 76 showed is vacuous: F3's noiseless health<->doomed coupling
forces FNR ~0.0 whether or not the F1 bug is fixed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ultra_csm.world import build_context_graph, generate_world, run_knowability_audit
from ultra_csm.world.generator import (
    WorldConfig,
    _latent_tuple,
    build_synthetic_book,
    det_id,
)

# Latent enum/label vocabulary that must never appear in an observable field.
_LATENT_STRINGS = (
    "champion_disengaged",
    "healthy_champion",
    "product_fit_gap",
    "fit_confirmed",
    "doomed",
    "thriving",
    "conflicted",
)

SEEDS = (1, 7, 11)


@pytest.mark.parametrize("seed", SEEDS)
def test_generated_recorded_latent_matches_the_index_that_generated_observables(seed):
    """For every generated account, the recorded doomed/thriving is the tuple
    drawn at its own generation index (recovered from account_id), not a
    sort-position re-roll. This is the direct F1 assertion."""
    config = WorldConfig(seed=seed, scale=200)
    world = generate_world(config)
    base_ids = {a.account_id for a in build_synthetic_book().accounts}
    gen_index_by_id = {
        det_id("world-account", seed, i): i
        for i in range(sum(1 for a in world.data.accounts if a.account_id not in base_ids))
    }
    checked = 0
    for row in world.latent_truth:
        if row.anchor_account:
            continue
        expected = _latent_tuple(config, gen_index_by_id[row.account_id])
        assert row.doomed == expected["doomed"], row.account_id
        assert row.thriving == expected["thriving"], row.account_id
        assert row.champion_engagement == expected["champion_engagement"], row.account_id
        checked += 1
    assert checked > 0


@pytest.mark.parametrize("seed", SEEDS)
def test_observable_band_equals_recorded_doomed_for_generated_accounts(seed):
    """The alignment invariant, observed from the observable side: a generated
    account's health band is red iff recorded doomed, green iff thriving. This
    was false under F1 (up to 16/62 mismatches at seed 11)."""
    world = generate_world(WorldConfig(seed=seed, scale=200))
    band = {h.account_id: h.band for h in world.data.health_scores}
    for row in world.latent_truth:
        if row.anchor_account:
            continue
        assert (band[row.account_id] == "red") == row.doomed, row.account_id
        assert (band[row.account_id] == "green") == row.thriving, row.account_id


@pytest.mark.parametrize("seed", SEEDS)
def test_no_latent_string_appears_in_any_observable_field(seed):
    """F2: health.drivers, CTA reasons, and case subjects carry no latent
    enum/label vocabulary."""
    world = generate_world(WorldConfig(seed=seed, scale=200))
    observable_text: list[str] = []
    for h in world.data.health_scores:
        observable_text.extend(h.drivers)
    observable_text.extend(c.reason for c in world.data.ctas)
    observable_text.extend(c.subject for c in world.data.cases)
    for text in observable_text:
        lowered = text.lower()
        for token in _LATENT_STRINGS:
            assert token not in lowered, f"latent string {token!r} leaked into {text!r}"


def test_knowability_audit_flags_a_planted_observable_leak():
    """F7: the semantic check catches a leak a name/import scan cannot."""
    import dataclasses

    world = generate_world(WorldConfig(seed=7, scale=200))
    graph = build_context_graph(world)
    assert run_knowability_audit(world, graph, repo_root=Path.cwd())["hard_ok"] is True
    assert world.data.ctas, "expected at least one CTA to poison"

    leaked_cta = dataclasses.replace(world.data.ctas[0], reason="Doomed latent trajectory")
    poisoned = dataclasses.replace(
        world, data=dataclasses.replace(world.data, ctas=(leaked_cta, *world.data.ctas[1:]))
    )
    audit = run_knowability_audit(poisoned, graph, repo_root=Path.cwd())
    assert audit["hard_ok"] is False
    assert audit["observable_free_of_latent_strings"] is False
