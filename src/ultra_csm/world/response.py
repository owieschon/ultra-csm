"""Latent-conditioned observable world response to agent actions.

F1's closed-loop hooks were, per docs/WORLD.md, "deterministic placeholders":
agent actions never fed back into the world's observable state. This module
is that feedback path. ``respond()`` is seeded-deterministic per
``(seed, account_id, action_id, day)`` -- never ``random.random()`` at call
time -- and its probability bands are conditioned on the account's LATENT
``champion_engagement`` state, which the returned ``ObservableEvent`` never
exposes directly (only a derived ``replied`` boolean). This is what makes
the world answer back with information about the hidden truth, rather than
producing uniform noise dressed up as a response.
"""

from __future__ import annotations

from dataclasses import dataclass

from ultra_csm.world.generator import LatentAccountTruth, _fraction

# D1: reply-probability bands keyed to the champion_engagement values
# generator.py actually emits (bible section for this lands in Phase 2)
# -- {engaged, quiet} on the anchor path, {quiet, high, medium} on the
# generated path. An unrecognized value falls back to the "quiet" band
# (0.1) rather than raising, since new latent states should degrade to the
# most conservative response rather than crash a live sweep.
ENGAGEMENT_REPLY_PROBABILITY = {
    "engaged": 0.8,
    "high": 0.6,
    "medium": 0.4,
    "quiet": 0.1,
}
_DEFAULT_REPLY_PROBABILITY = ENGAGEMENT_REPLY_PROBABILITY["quiet"]


@dataclass(frozen=True)
class ObservableEvent:
    """The agent-visible outcome of an action. Carries no latent fields --
    only a derived, boolean-observable outcome."""

    kind: str
    account_id: str
    action_id: str
    day: int
    replied: bool


def respond(
    action_id: str,
    latent_state: LatentAccountTruth,
    world_seed: int,
    day: int,
) -> ObservableEvent | None:
    """Seeded-deterministic observable response to one agent action.

    Same (seed, account, action, day) always returns the same event. The
    reply probability is conditioned on latent_state.champion_engagement but
    that field, and every other latent field, never appears in the returned
    event.
    """
    probability = ENGAGEMENT_REPLY_PROBABILITY.get(
        latent_state.champion_engagement, _DEFAULT_REPLY_PROBABILITY
    )
    roll = _fraction(
        world_seed,
        0,
        f"{latent_state.account_id}:{action_id}:{day}:reply",
    )
    return ObservableEvent(
        kind="customer_reply",
        account_id=latent_state.account_id,
        action_id=action_id,
        day=day,
        replied=roll < probability,
    )
