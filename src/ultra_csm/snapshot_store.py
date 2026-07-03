"""Snapshot persistence and trajectory computation (VM-6, VM-7).

Each time the system evaluates the book, it persists a snapshot of every
account's value model output: health band, scores, factor values, lens
priorities.  Trajectory is a query over stored snapshots: is health
improving, stable, or declining?  How fast?  Over what window?

This activates signals that a single point-in-time read can't produce:

* "Usage declined 15% over the last 30 days"
* "Health has been green for six consecutive evaluations"
* Band transitions with exact dates

Usage::

    store = SnapshotStore()
    store.store_snapshot(day=0, account_id="acct-1", output={...})
    store.store_snapshot(day=30, account_id="acct-1", output={...})

    trajectory = store.get_trajectory("acct-1", window_days=60)
    trend = store.compute_trend("acct-1", window_days=60)
    change = store.detect_band_change("acct-1", from_day=0, to_day=30)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

TrendDirection = Literal["unknown", "improving", "stable", "declining"]

# Ordered from worst to best for numeric comparison.
_BAND_RANK: dict[str, int] = {"red": 0, "yellow": 1, "green": 2}


@dataclass(frozen=True)
class AccountSnapshot:
    """A single point-in-time snapshot of an account's value model output."""

    day: int
    account_id: str
    health_band: str
    health_score: float
    priority_score: int
    priority_factors: tuple[str, ...]
    lifecycle_stage: str
    arr_cents: int
    raw: dict[str, Any]


@dataclass(frozen=True)
class BandChange:
    """A detected health-band transition between two evaluation days."""

    account_id: str
    from_day: int
    to_day: int
    old_band: str
    new_band: str
    direction: TrendDirection


@dataclass(frozen=True)
class TrajectoryPoint:
    """A single data point in a trajectory series."""

    day: int
    health_band: str
    health_score: float
    priority_score: int
    priority_factors: tuple[str, ...]


@dataclass(frozen=True)
class Trajectory:
    """Health trajectory for an account over a time window."""

    account_id: str
    window_days: int
    points: tuple[TrajectoryPoint, ...]
    trend: TrendDirection
    trend_velocity: float
    consecutive_band: str | None
    consecutive_count: int


# ---------------------------------------------------------------------------
# SnapshotStore
# ---------------------------------------------------------------------------


class SnapshotStore:
    """In-memory snapshot store for value model outputs.

    Stores one snapshot per (day, account_id) pair.  Supports trajectory
    queries, trend computation, and band-change detection.

    This is an in-memory implementation suitable for the demo loop and
    timeline commands.  A production implementation would persist to
    Postgres (see ``migrations/`` for the schema pattern).
    """

    def __init__(self) -> None:
        # (day, account_id) -> AccountSnapshot
        self._snapshots: dict[tuple[int, str], AccountSnapshot] = {}
        # account_id -> sorted list of days with snapshots
        self._account_days: dict[str, list[int]] = {}

    # ----- Storage -----

    def store_snapshot(
        self,
        day: int,
        account_id: str,
        value_model_output: dict[str, Any],
    ) -> AccountSnapshot:
        """Persist a value model output snapshot for an account at a given day.

        Parameters
        ----------
        day:
            Simulation day (0, 30, 60, ...).
        account_id:
            The account being scored.
        value_model_output:
            Dict with at least ``health_band``, ``health_score``,
            ``priority_score``, ``priority_factors``, ``lifecycle_stage``,
            ``arr_cents``.
        """
        snapshot = AccountSnapshot(
            day=day,
            account_id=account_id,
            health_band=value_model_output.get("health_band", "unknown"),
            health_score=value_model_output.get("health_score", 0.0),
            priority_score=value_model_output.get("priority_score", 0),
            priority_factors=tuple(value_model_output.get("priority_factors", ())),
            lifecycle_stage=value_model_output.get("lifecycle_stage", "unknown"),
            arr_cents=value_model_output.get("arr_cents", 0),
            raw=value_model_output,
        )

        key = (day, account_id)
        self._snapshots[key] = snapshot

        if account_id not in self._account_days:
            self._account_days[account_id] = []
        days_list = self._account_days[account_id]
        if day not in days_list:
            days_list.append(day)
            days_list.sort()

        return snapshot

    def get_snapshot(self, day: int, account_id: str) -> AccountSnapshot | None:
        """Retrieve a single snapshot, or ``None`` if not stored."""
        return self._snapshots.get((day, account_id))

    # ----- Trajectory queries (VM-7) -----

    def get_trajectory(
        self,
        account_id: str,
        window_days: int,
    ) -> list[AccountSnapshot]:
        """Return all snapshots for *account_id* within the last *window_days*.

        Snapshots are returned in chronological order (ascending day).
        If no snapshots exist, returns an empty list.
        """
        days = self._account_days.get(account_id, [])
        if not days:
            return []

        max_day = days[-1]
        cutoff = max_day - window_days

        return [
            self._snapshots[(d, account_id)]
            for d in days
            if d >= cutoff
        ]

    def compute_trend(
        self,
        account_id: str,
        window_days: int,
    ) -> TrendDirection:
        """Compute the health trend over the given window.

        Uses a combination of health-score slope and band transitions:

        * If fewer than two snapshots exist: **unknown**.
        * If health score increased by more than 5 points over the window:
          **improving**.
        * If health score decreased by more than 5 points: **declining**.
        * Otherwise: **stable**.

        The threshold (5 points) is deliberately conservative — small
        oscillations don't trigger trend changes.
        """
        snapshots = self.get_trajectory(account_id, window_days)
        if len(snapshots) < 2:
            return "unknown"

        first = snapshots[0]
        last = snapshots[-1]
        delta = last.health_score - first.health_score

        if delta > 5.0:
            return "improving"
        if delta < -5.0:
            return "declining"
        return "stable"

    def compute_trend_velocity(
        self,
        account_id: str,
        window_days: int,
    ) -> float:
        """Compute the rate of health-score change (points per day).

        Returns 0.0 if fewer than 2 snapshots exist in the window.
        """
        snapshots = self.get_trajectory(account_id, window_days)
        if len(snapshots) < 2:
            return 0.0

        first = snapshots[0]
        last = snapshots[-1]
        day_span = last.day - first.day
        if day_span == 0:
            return 0.0

        return round((last.health_score - first.health_score) / day_span, 4)

    def detect_band_change(
        self,
        account_id: str,
        from_day: int,
        to_day: int,
    ) -> BandChange | None:
        """Detect a health-band transition between two evaluation days.

        Returns ``None`` if:
        * Either snapshot doesn't exist.
        * The band didn't change.
        """
        old = self.get_snapshot(from_day, account_id)
        new = self.get_snapshot(to_day, account_id)

        if old is None or new is None:
            return None
        if old.health_band == new.health_band:
            return None

        old_rank = _BAND_RANK.get(old.health_band, 1)
        new_rank = _BAND_RANK.get(new.health_band, 1)

        if new_rank > old_rank:
            direction: TrendDirection = "improving"
        elif new_rank < old_rank:
            direction = "declining"
        else:
            direction = "stable"

        return BandChange(
            account_id=account_id,
            from_day=from_day,
            to_day=to_day,
            old_band=old.health_band,
            new_band=new.health_band,
            direction=direction,
        )

    def consecutive_band_count(self, account_id: str) -> tuple[str | None, int]:
        """Count how many consecutive evaluations the account has been in
        its current band.

        Returns ``(band, count)`` or ``(None, 0)`` if no snapshots exist.
        """
        days = self._account_days.get(account_id, [])
        if not days:
            return None, 0

        current_band = self._snapshots[(days[-1], account_id)].health_band
        count = 0
        for d in reversed(days):
            snap = self._snapshots[(d, account_id)]
            if snap.health_band == current_band:
                count += 1
            else:
                break

        return current_band, count

    def build_trajectory(
        self,
        account_id: str,
        window_days: int,
    ) -> Trajectory:
        """Build a complete :class:`Trajectory` object for an account.

        Combines snapshot history, trend computation, velocity, and
        consecutive-band tracking into a single response object suitable
        for the API layer.
        """
        snapshots = self.get_trajectory(account_id, window_days)
        trend = self.compute_trend(account_id, window_days)
        velocity = self.compute_trend_velocity(account_id, window_days)
        band, count = self.consecutive_band_count(account_id)

        points = tuple(
            TrajectoryPoint(
                day=s.day,
                health_band=s.health_band,
                health_score=s.health_score,
                priority_score=s.priority_score,
                priority_factors=s.priority_factors,
            )
            for s in snapshots
        )

        return Trajectory(
            account_id=account_id,
            window_days=window_days,
            points=points,
            trend=trend,
            trend_velocity=velocity,
            consecutive_band=band,
            consecutive_count=count,
        )

    # ----- Bulk queries -----

    def all_account_ids(self) -> list[str]:
        """Return all account IDs that have at least one snapshot."""
        return list(self._account_days.keys())

    def all_days(self) -> list[int]:
        """Return all unique days that have at least one snapshot."""
        days: set[int] = set()
        for d, _ in self._snapshots:
            days.add(d)
        return sorted(days)

    def snapshots_at_day(self, day: int) -> list[AccountSnapshot]:
        """Return all snapshots stored for a given day."""
        return [
            snap for (d, _), snap in self._snapshots.items()
            if d == day
        ]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entire store to a JSON-compatible dict."""
        result: dict[str, Any] = {}
        for account_id in sorted(self._account_days):
            days = self._account_days[account_id]
            result[account_id] = {
                "snapshots": [
                    {
                        "day": self._snapshots[(d, account_id)].day,
                        "health_band": self._snapshots[(d, account_id)].health_band,
                        "health_score": self._snapshots[(d, account_id)].health_score,
                        "priority_score": self._snapshots[(d, account_id)].priority_score,
                        "priority_factors": list(self._snapshots[(d, account_id)].priority_factors),
                        "lifecycle_stage": self._snapshots[(d, account_id)].lifecycle_stage,
                    }
                    for d in days
                ],
                "trajectory": {
                    "trend": self.compute_trend(account_id, 365),
                    "velocity": self.compute_trend_velocity(account_id, 365),
                    "consecutive_band": self.consecutive_band_count(account_id)[0],
                    "consecutive_count": self.consecutive_band_count(account_id)[1],
                },
            }
        return result
