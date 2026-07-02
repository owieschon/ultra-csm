"""In-memory API metrics tracking.

Collects request-level response times, per-endpoint counts, percentile
latencies, and sweep-phase timing breakdowns for the ``/metrics`` endpoint.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Sweep timing
# ---------------------------------------------------------------------------


@dataclass
class SweepTiming:
    """Timing breakdown for a single sweep run."""

    total_ms: float = 0.0
    value_model_ms: float = 0.0
    slot_b_total_ms: float = 0.0
    slot_b_avg_per_account_ms: float = 0.0
    slot_b_call_count: int = 0
    governance_ms: float = 0.0
    accounts_swept: int = 0
    budget_skipped: int = 0
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# API metrics
# ---------------------------------------------------------------------------


class APIMetrics:
    """Thread-safe in-memory API metrics tracker."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_requests: int = 0
        self._requests_by_endpoint: dict[str, int] = {}
        self._response_times: list[float] = []
        self._response_times_by_endpoint: dict[str, list[float]] = {}
        self._sweep_timings: list[SweepTiming] = []

    # -- recording ----------------------------------------------------------

    def record_request(self, endpoint: str, response_time_ms: float) -> None:
        """Record a single API request."""
        with self._lock:
            self._total_requests += 1
            self._requests_by_endpoint[endpoint] = (
                self._requests_by_endpoint.get(endpoint, 0) + 1
            )
            self._response_times.append(response_time_ms)
            self._response_times_by_endpoint.setdefault(endpoint, []).append(
                response_time_ms
            )

    def record_sweep(self, timing: SweepTiming) -> None:
        """Record timing for a completed sweep."""
        with self._lock:
            self._sweep_timings.append(timing)

    # -- queries ------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """API request metrics for the ``/metrics`` endpoint."""
        with self._lock:
            return {
                "total_requests": self._total_requests,
                "requests_by_endpoint": dict(self._requests_by_endpoint),
                "avg_response_time_ms": _avg(self._response_times),
                "p50_response_time_ms": _percentile(self._response_times, 50),
                "p95_response_time_ms": _percentile(self._response_times, 95),
                "p99_response_time_ms": _percentile(self._response_times, 99),
            }

    def sweep_snapshot(self) -> dict[str, Any]:
        """Sweep metrics for the ``/metrics`` endpoint."""
        with self._lock:
            total = len(self._sweep_timings)
            if total == 0:
                return {
                    "total_sweeps": 0,
                    "avg_sweep_duration_ms": 0.0,
                    "avg_accounts_per_sweep": 0.0,
                }
            durations = [t.total_ms for t in self._sweep_timings]
            accounts = [float(t.accounts_swept) for t in self._sweep_timings]
            last = self._sweep_timings[-1]
            return {
                "total_sweeps": total,
                "avg_sweep_duration_ms": _avg(durations),
                "avg_accounts_per_sweep": _avg(accounts),
                "last_sweep": {
                    "total_ms": round(last.total_ms, 2),
                    "value_model_ms": round(last.value_model_ms, 2),
                    "slot_b_total_ms": round(last.slot_b_total_ms, 2),
                    "slot_b_avg_per_account_ms": round(
                        last.slot_b_avg_per_account_ms, 2
                    ),
                    "governance_ms": round(last.governance_ms, 2),
                    "accounts_swept": last.accounts_swept,
                    "budget_skipped": last.budget_skipped,
                },
            }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _percentile(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = int(len(s) * p / 100)
    idx = min(idx, len(s) - 1)
    return round(s[idx], 2)
