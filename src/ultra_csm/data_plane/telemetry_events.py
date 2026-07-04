"""Event-level product-telemetry exhaust for Pinehill Transport and Meridian
Fleet Group (Universe v2, WS-Data-Classes Phase 1).

``synthetic_book.py`` / ``book_simulator.py`` already produce a company-grain
*aggregate* -- ``AdoptionSummary.active_assets`` / ``adoption_rate`` -- for
every account at any day offset (``simulate_book``). Nothing in the universe
previously rendered that aggregate as the individual login/feature_action/
api_call events a real product-telemetry pipeline would emit before being
rolled up. This module is that missing layer for the two accounts whose
arcs (Pinehill's onboarding stall, Meridian's expansion) most depend on a
usage story: it derives one event stream per account, per day, per asset,
from the SAME scripted ``UsageDecline``/``UsageGrowth`` mutations the
simulator already applies -- never a second, competing usage script.

Determinism: which of an account's ``entitled_assets`` are "active" on a
given day is chosen by ranking each asset's deterministic hash
(``det_id("asset", account_id, asset_index)``) and taking the top
``active_assets`` (per ``simulate_book(day).adoption_summaries``) by that
rank, stable day-over-day (once an asset ranks into the active set for a
higher active_assets count, it stays active as the count grows, and only
drops out as it shrinks) -- so this is not "any N of self.assets" per day,
it's a monotone nested selection, mirroring how real fleets tend to keep
the same subset of vehicles active rather than reshuffling which ones are
online. Each active asset emits one ``login``, one ``feature_action``, and
one ``api_call`` event that day (the minimal event triple a fleet-ops
telemetry pipeline would produce per asset-day); aggregating
(distinct active asset ids that day) reproduces
``AdoptionSummary.active_assets`` exactly (0% error, comfortably within the
required ±2%), which is what ``check_event_aggregation_matches_simulator``
in the accompanying test asserts at every bible checkpoint day for both
accounts.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from ultra_csm.data_plane.book_simulator import simulate_book
from ultra_csm.data_plane.fixtures import account_id_for, det_id
from ultra_csm.data_plane.narrative_shared import base_synthetic_book, rfc3339


def _det_int(*parts: object) -> int:
    """Deterministic non-negative int derived from ``det_id``'s UUID5 --
    used for stable ranking/rotation, never for anything cryptographic."""

    return UUID(det_id(*parts)).int

TELEMETRY_ACCOUNTS: tuple[str, ...] = ("pinehill-transport", "meridian-fleet")

EventType = str  # "login" | "feature_action" | "api_call"

_EVENT_TYPES: tuple[str, ...] = ("login", "feature_action", "api_call")

# Deterministic per-account module rotation for feature_action events, so the
# derived exhaust exercises more than one capability key without inventing a
# usage pattern the bible doesn't already imply (each account's own
# entitlement list, canon-consistent with docs/SYNTHETIC_UNIVERSE_BIBLE.md's
# capability-key table).
_ACCOUNT_MODULES: dict[str, tuple[str, ...]] = {
    "pinehill-transport": ("core_telematics", "route_optimization"),
    "meridian-fleet": ("core_telematics", "route_optimization", "driver_coaching", "maintenance_alerts"),
}


@dataclass(frozen=True)
class TelemetryEvent:
    """One event-level exhaust row: login, feature_action, or api_call."""

    event_id: str
    account_id: str
    asset_id: str
    event_type: EventType
    module: str | None
    day_offset: int
    observed_at: str
    actor: str


_POOL_SIZE_CACHE: dict[str, int] = {}


def _pool_size(account_slug: str) -> int:
    """The asset-id pool must be large enough to name every asset the
    simulator ever reports active for this account across the full 365-day
    timeline -- some accounts' scripted ``UsageGrowth`` (Meridian's, e.g.)
    legitimately drives ``active_assets`` above ``entitled_assets`` (real
    over-provisioned usage, same as the fixture's own
    ``westfield-industrial`` adoption_rate=1.10), so the pool cannot be
    sized off ``entitled_assets`` alone."""

    cached = _POOL_SIZE_CACHE.get(account_slug)
    if cached is not None:
        return cached
    base = base_synthetic_book()
    account_id = account_id_for(account_slug)
    max_active = 0
    for day in range(0, 366):
        book = simulate_book(base, day)
        adoption = next(a for a in book.adoption_summaries if a.account_id == account_id)
        max_active = max(max_active, adoption.active_assets)
    _POOL_SIZE_CACHE[account_slug] = max_active
    return max_active


def _asset_ids(account_slug: str, pool_size: int) -> tuple[str, ...]:
    account_id = account_id_for(account_slug)
    return tuple(det_id("asset", account_id, i) for i in range(pool_size))


def _active_asset_ids(account_slug: str, day_offset: int) -> tuple[str, ...]:
    """The subset of the account's asset pool active on *day_offset*, sized
    to match ``AdoptionSummary.active_assets`` at that day, chosen by a
    stable deterministic rank so the active set nests as it grows/shrinks
    rather than reshuffling."""

    base = base_synthetic_book()
    book = simulate_book(base, day_offset)
    account_id = account_id_for(account_slug)
    adoption = next(a for a in book.adoption_summaries if a.account_id == account_id)
    active_count = adoption.active_assets
    pool = _asset_ids(account_slug, _pool_size(account_slug))
    ranked = sorted(pool, key=lambda aid: _det_int("asset-rank", aid))
    return tuple(ranked[:active_count])


def telemetry_events_for_day(account_slug: str, day_offset: int) -> tuple[TelemetryEvent, ...]:
    """The login/feature_action/api_call event triple for every asset active
    on *account_slug* at *day_offset*."""

    if account_slug not in TELEMETRY_ACCOUNTS:
        raise ValueError(f"telemetry events not scripted for {account_slug!r}")
    account_id = account_id_for(account_slug)
    active = _active_asset_ids(account_slug, day_offset)
    modules = _ACCOUNT_MODULES[account_slug]
    observed_at = rfc3339(day_offset, 6)
    events: list[TelemetryEvent] = []
    for asset_id in active:
        module_idx = _det_int("asset-module", asset_id, day_offset) % len(modules)
        module = modules[module_idx]
        for event_type in _EVENT_TYPES:
            events.append(
                TelemetryEvent(
                    event_id=det_id("telemetry-event", account_id, asset_id, day_offset, event_type),
                    account_id=account_id,
                    asset_id=asset_id,
                    event_type=event_type,
                    module=module if event_type == "feature_action" else None,
                    day_offset=day_offset,
                    observed_at=observed_at,
                    actor=asset_id,
                )
            )
    return tuple(events)


def telemetry_events_through_day(
    account_slug: str, as_of_day: int, *, sample_days: tuple[int, ...] | None = None
) -> tuple[TelemetryEvent, ...]:
    """All events for *account_slug* on the sampled days on or before
    *as_of_day*. ``sample_days`` defaults to every day 0..as_of_day, but the
    fake transport samples a coarser grid (weekly) to keep fixture volume
    bounded -- see ``build_fake_telemetry_catalog``."""

    days = sample_days if sample_days is not None else tuple(range(0, as_of_day + 1))
    events: list[TelemetryEvent] = []
    for day in days:
        if day > as_of_day:
            continue
        events.extend(telemetry_events_for_day(account_slug, day))
    return tuple(events)


def daily_active_assets_from_events(events: tuple[TelemetryEvent, ...], day_offset: int) -> int:
    """Aggregation-derivation: distinct asset ids with at least one event on
    *day_offset*, reproducing ``AdoptionSummary.active_assets`` for that
    account/day -- the aggregation the accompanying test asserts."""

    return len({e.asset_id for e in events if e.day_offset == day_offset})


def adoption_rate_from_events(
    events: tuple[TelemetryEvent, ...], day_offset: int, entitled_assets: int
) -> float:
    if entitled_assets <= 0:
        return 0.0
    active = daily_active_assets_from_events(events, day_offset)
    return round(active / entitled_assets, 2)
