"""Event-level product-telemetry exhaust for Loopway's named arc accounts
(Universe v2, WS-Tenant-Loopway, Wave 3). Mirrors
``ultra_csm.data_plane.telemetry_events``'s pattern (event-level exhaust
derived from the SAME scripted usage facts the aggregate fixture already
encodes, never a second competing usage script) but scoped to this
tenant's own arcs: full event exhaust ONLY for the 98 L1/L2/L3/herring
named accounts (bible: "full event exhaust ONLY for L1/L2/L3 named
accounts, ~120 accounts max" -- 98 here, comfortably under that ceiling);
the other 302 accounts (24 named high/mid + 278 plain tail) get the
aggregate-level ``UsageSignal`` rows from ``synthetic_book.py`` only.

Day-driven views (``active_users_as_of``) implement each arc's own
time-evolution directly (no shared ``book_simulator.py`` mutation engine
is reused here -- that engine is keyed to fleetops' own module-level
``_ADOPTION``/`_id` tables and is out of this tenant's ownership map; this
is a self-contained, equally-deterministic day function per arc, per the
autonomy rule's "additive + conformant + smallest" test).
"""

from __future__ import annotations

from dataclasses import dataclass

from ultra_csm.data_plane.fixtures import account_id_for
from ultra_csm.data_plane.tenants.loopway.synthetic_book import (
    HERRING_COHORT,
    L1_ACTIVATED,
    L1_STALLED,
    L2_COHORT,
    L3_COHORT,
)


@dataclass(frozen=True)
class DailyUsagePoint:
    account_id: str
    day_offset: int
    active_users: float
    route_plans_per_week: float


def _l1_stalled_curve(day: int) -> tuple[float, float]:
    """Never activates: flat zero from signup through day 75 and beyond."""

    return (0.0, 0.0)


def _l1_activated_curve(day: int) -> tuple[float, float]:
    """Ramps to steady usage within the 45-day activation window."""

    if day < 30:
        return (0.0, 0.0)
    ramp_day = min(day - 30, 15)
    active_users = 1.0 + ramp_day * 0.15
    return (active_users, active_users * 3)


def _l2_curve(day: int) -> tuple[float, float]:
    """Sustained growth to 5x+ the tail median by day 120."""

    if day < 30:
        return (2.0, 6.0)
    growth_days = min(day - 30, 90)
    active_users = 2.0 + growth_days * (11.0 / 90.0)  # 2 -> 13 by day 120
    return (active_users, active_users * 3)


def _l3_curve(day: int) -> tuple[float, float]:
    """Healthy through day 150, then decays to zero by day 210."""

    if day < 150:
        return (4.0, 12.0)
    if day >= 210:
        return (0.0, 0.0)
    decay_frac = (day - 150) / 60.0
    active_users = 4.0 * (1.0 - decay_frac)
    return (max(active_users, 0.0), max(active_users, 0.0) * 3)


def _herring_curve(day: int) -> tuple[float, float]:
    """Seasonal dip days 90-105, then self-recovers to baseline by day 130."""

    baseline = 3.0
    if day < 90 or day >= 130:
        return (baseline, baseline * 3)
    if day < 105:
        dip_frac = (day - 90) / 15.0
        active_users = baseline * (1.0 - 0.8 * dip_frac)
        return (active_users, active_users * 3)
    recover_frac = (day - 105) / 25.0
    active_users = baseline * (0.2 + 0.8 * recover_frac)
    return (active_users, active_users * 3)


_CURVE_BY_GROUP = {
    "l1_stalled": _l1_stalled_curve,
    "l1_activated": _l1_activated_curve,
    "l2": _l2_curve,
    "l3": _l3_curve,
    "herring": _herring_curve,
}


def _group_for(slug: str) -> str | None:
    if slug in L1_STALLED:
        return "l1_stalled"
    if slug in L1_ACTIVATED:
        return "l1_activated"
    if slug in L2_COHORT:
        return "l2"
    if slug in L3_COHORT:
        return "l3"
    if slug in HERRING_COHORT:
        return "herring"
    return None


def usage_as_of(slug: str, day_offset: int) -> DailyUsagePoint:
    """The account's (active_users, route_plans_per_week) at *day_offset*,
    per its arc's scripted curve. Raises for a slug outside the named-arc
    scope this module covers (302 non-arc accounts use the static
    aggregate ``UsageSignal`` from ``synthetic_book.py`` instead)."""

    group = _group_for(slug)
    if group is None:
        raise KeyError(f"{slug} is not a named L1/L2/L3/herring arc account")
    active_users, route_plans = _CURVE_BY_GROUP[group](day_offset)
    return DailyUsagePoint(
        account_id=account_id_for(slug),
        day_offset=day_offset,
        active_users=active_users,
        route_plans_per_week=route_plans,
    )


def milestone_achieved_as_of(slug: str, day_offset: int) -> bool:
    """Whether the driver_app_activated milestone is achieved by
    *day_offset*, per the L1 arc (stalled accounts never activate; the
    contrast group activates within the 45-day window)."""

    group = _group_for(slug)
    if group == "l1_stalled":
        return False
    if group == "l1_activated":
        return day_offset >= 30
    # non-L1 named accounts: activated from day 0 (they are not part of
    # the activation-stall story).
    return True
