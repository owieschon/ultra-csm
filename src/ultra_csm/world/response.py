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


def _in_shock_window(day: int) -> bool:
    shock = _config()["shock"]
    start = shock["shock_day"]
    return start <= day < start + shock["shock_duration_days"]


def _reply_probability(champion_engagement: str, *, day: int) -> float:
    cfg = _config()
    bands = cfg["engagement_reply_probability"]
    default_band = cfg["default_reply_probability_band"]
    probability = bands.get(champion_engagement, bands[default_band])
    if _in_shock_window(day):
        # D6: one config-scheduled nonstationary shock -- shifts the reply
        # rate for a fixed window, same mechanism regardless of shock_kind
        # (the kind is descriptive metadata for the flight recorder /
        # improvement-loop reporting, not a second branch of logic here).
        probability *= cfg["shock"]["shock_reply_probability_multiplier"]
    return probability


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
    probability is conditioned on latent_state.champion_engagement (and,
    during the D6 shock window, shifted by the configured multiplier) but
    that field, and every other latent field, never appears in the returned
    event.
    """
    if not _is_customer_facing(action_id):
        return None
    probability = _reply_probability(latent_state.champion_engagement, day=day)
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


@dataclass(frozen=True)
class InjectionEvent:
    """A live, world-stream untrusted-text event -- arrives the same way a
    CRM note or ingested email would. Carries no latent fields. Category
    strings and paraphrase content live entirely in
    knowledge/world_response_config.json's ``injection_categories`` (reusing
    the CATEGORIES eval.gold_slot_b_hard's A6_*_INJECTION constants define,
    never their exact frozen strings -- new paraphrases, same adversarial
    intent per category)."""

    account_id: str
    day: int
    category: str
    text: str


def injection_event(account_id: str, world_seed: int, day: int) -> InjectionEvent | None:
    """Seeded-deterministic: ~injection_event_rate of (account, day) pairs
    fire an event, uniformly distributed across the configured categories."""
    cfg = _config()
    roll = _fraction(world_seed, 0, f"{account_id}:{day}:injection")
    if roll >= cfg["injection_event_rate"]:
        return None
    categories = cfg["injection_categories"]
    category = sorted(categories)[
        int(_fraction(world_seed, 0, f"{account_id}:{day}:injection-category") * len(categories))
        % len(categories)
    ]
    paraphrases = categories[category]["paraphrases"]
    text = paraphrases[
        int(_fraction(world_seed, 0, f"{account_id}:{day}:injection-text") * len(paraphrases))
        % len(paraphrases)
    ]
    return InjectionEvent(account_id=account_id, day=day, category=category, text=text)
