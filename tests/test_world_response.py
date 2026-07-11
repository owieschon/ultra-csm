"""Phase 1 (MP-W1R): latent-conditioned, deterministic world response."""

from __future__ import annotations

from dataclasses import fields

from ultra_csm.world.generator import LatentAccountTruth
from ultra_csm.world.response import ObservableEvent, respond

ACTION_ID = "draft_customer_outreach"


def _latent(account_id: str, champion_engagement: str) -> LatentAccountTruth:
    return LatentAccountTruth(
        account_id=account_id,
        account_slug=account_id,
        anchor_account=False,
        doomed=False,
        thriving=False,
        champion_engagement=champion_engagement,
        product_fit="adequate",
        org_state="stable",
        latent_label="test",
        corruption_flags=(),
        causal_chain=(),
        observed_day=1,
    )


def test_response_distribution_differs_by_latent_champion_engagement():
    engaged = _latent("acct-engaged", "engaged")
    quiet = _latent("acct-quiet", "quiet")

    engaged_replies = sum(
        1 for day in range(1, 201) if respond(ACTION_ID, engaged, world_seed=7, day=day).replied
    )
    quiet_replies = sum(
        1 for day in range(1, 201) if respond(ACTION_ID, quiet, world_seed=7, day=day).replied
    )

    # engaged (0.8) vs quiet (0.1) bands over 200 trials -- must diverge far
    # beyond any plausible sampling noise, or the response isn't actually
    # conditioned on latent state.
    assert engaged_replies > quiet_replies + 100


def test_response_is_deterministic_for_identical_inputs():
    latent = _latent("acct-1", "high")

    first = respond(ACTION_ID, latent, world_seed=42, day=10)
    second = respond(ACTION_ID, latent, world_seed=42, day=10)

    assert first == second


def test_response_never_carries_a_latent_field_verbatim():
    latent = _latent("acct-1", "engaged")
    event = respond(ACTION_ID, latent, world_seed=7, day=1)

    event_field_names = {f.name for f in fields(ObservableEvent)}
    latent_only_field_names = {f.name for f in fields(LatentAccountTruth)} - {"account_id"}
    assert not (event_field_names & latent_only_field_names)

    # Belt and suspenders: the CATEGORICAL latent labels (the actual signal
    # a leak would expose) must never appear verbatim in the event's string
    # fields. Boolean/int fields are excluded from this comparison -- a
    # coincidental match like day=1 == observed_day=1 is not a leak, it's
    # two unrelated small integers.
    categorical_latent_values = {
        latent.champion_engagement,
        latent.product_fit,
        latent.org_state,
        latent.latent_label,
    }
    event_string_values = {event.kind, event.action_id}
    assert not (event_string_values & categorical_latent_values)
