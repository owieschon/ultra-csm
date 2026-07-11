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

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ultra_csm.world.generator import LatentAccountTruth, _fraction

# Ratified in knowledge/world_response_config.json and
# docs/SYNTHETIC_UNIVERSE_BIBLE.md's "World response" section -- a config
# change is a bible change first. This module reads the config as the
# single source of truth (no hardcoded duplicate of the bands/mapping) so
# the two can never silently drift apart.
CONFIG_PATH = (
    Path(__file__).resolve().parents[3] / "knowledge" / "world_response_config.json"
)


@lru_cache(maxsize=1)
def _config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _reply_probability(champion_engagement: str) -> float:
    cfg = _config()
    bands = cfg["engagement_reply_probability"]
    default_band = cfg["default_reply_probability_band"]
    return bands.get(champion_engagement, bands[default_band])


def _is_customer_facing(action_id: str) -> bool:
    return action_id in _config()["customer_facing_actions"]


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

    Returns None for actions in the internal/no-response class (config:
    knowledge/world_response_config.json) -- a customer never sees them, so
    there is nothing to observe. For customer-facing actions, same
    (seed, account, action, day) always returns the same event; the reply
    probability is conditioned on latent_state.champion_engagement but that
    field, and every other latent field, never appears in the returned
    event.
    """
    if not _is_customer_facing(action_id):
        return None
    probability = _reply_probability(latent_state.champion_engagement)
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
