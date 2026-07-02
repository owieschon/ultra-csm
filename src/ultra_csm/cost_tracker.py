"""In-memory cost tracking and budget enforcement for LLM calls.

Provides a thread-safe cumulative tracker that the API ``/metrics``
endpoint queries, plus a lightweight budget gate the sweep checks
before each Slot B call.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model pricing — USD per million tokens
# ---------------------------------------------------------------------------

MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (input_cost_per_mtok, output_cost_per_mtok)
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (0.80, 4.00),
    # Fixture / test models — zero cost.
    "fixture-agent1-slot-b-v1": (0.0, 0.0),
    "unsafe-agent1-slot-b": (0.0, 0.0),
}

# Conservative upper-bound estimates for budget checks (tokens).
_ESTIMATED_INPUT_TOKENS = 2000
_ESTIMATED_OUTPUT_TOKENS = 700


def compute_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Compute estimated cost in USD for a given model and token counts."""
    input_rate, output_rate = MODEL_PRICING.get(model_id, (5.00, 25.00))
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


def estimate_call_cost(model_id: str) -> float:
    """Conservative upper-bound estimate for one Slot B call."""
    return compute_cost(model_id, _ESTIMATED_INPUT_TOKENS, _ESTIMATED_OUTPUT_TOKENS)


# ---------------------------------------------------------------------------
# Call record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CallRecord:
    """Record of a single Slot B call."""

    model_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: float
    account_id: str | None = None
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# CostTracker — thread-safe cumulative counter
# ---------------------------------------------------------------------------


class CostTracker:
    """Thread-safe cumulative cost tracker for Slot B LLM calls.

    The sweep calls :meth:`reset_sweep` at the start, and
    :attr:`current_sweep_cost` before each Slot B call to check the budget.
    The API queries :meth:`stats` for the ``/metrics`` endpoint.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: list[CallRecord] = []
        self._total_cost_usd: float = 0.0
        self._total_tokens: int = 0
        self._total_latency_ms: float = 0.0
        self._daily_cost: dict[str, float] = {}  # date_str → cost
        self._sweep_cost: float = 0.0

    # -- recording ----------------------------------------------------------

    def record(
        self,
        *,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        account_id: str | None = None,
    ) -> CallRecord:
        """Record a Slot B call and return the call record."""
        total_tokens = input_tokens + output_tokens
        cost_usd = compute_cost(model_id, input_tokens, output_tokens)
        rec = CallRecord(
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            account_id=account_id,
        )

        with self._lock:
            self._calls.append(rec)
            self._total_cost_usd += cost_usd
            self._total_tokens += total_tokens
            self._total_latency_ms += latency_ms
            self._sweep_cost += cost_usd

            date_str = time.strftime("%Y-%m-%d", time.gmtime(rec.timestamp))
            self._daily_cost[date_str] = (
                self._daily_cost.get(date_str, 0.0) + cost_usd
            )

        log.info(
            "slot_b_call",
            extra={
                "model_id": model_id,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cost_usd": round(cost_usd, 6),
                "latency_ms": round(latency_ms, 2),
                "account_id": account_id,
            },
        )

        return rec

    # -- sweep lifecycle ----------------------------------------------------

    def reset_sweep(self) -> None:
        """Reset the per-sweep cost counter (called at sweep start)."""
        with self._lock:
            self._sweep_cost = 0.0

    @property
    def current_sweep_cost(self) -> float:
        """Accumulated cost for the current sweep."""
        with self._lock:
            return self._sweep_cost

    # -- queries ------------------------------------------------------------

    def today_cost_usd(self) -> float:
        """Total cost for today (UTC)."""
        with self._lock:
            today = time.strftime("%Y-%m-%d", time.gmtime())
            return self._daily_cost.get(today, 0.0)

    def stats(self) -> dict[str, Any]:
        """Cumulative stats for the ``/metrics`` endpoint."""
        with self._lock:
            n = len(self._calls)
            return {
                "total_calls": n,
                "total_tokens": self._total_tokens,
                "total_cost_usd": round(self._total_cost_usd, 6),
                "avg_latency_ms": (
                    round(self._total_latency_ms / n, 2) if n > 0 else 0.0
                ),
            }

    def cost_per_account(self) -> dict[str, float]:
        """Cost breakdown by account_id."""
        with self._lock:
            per: dict[str, float] = {}
            for call in self._calls:
                key = call.account_id or "unknown"
                per[key] = per.get(key, 0.0) + call.cost_usd
            return {k: round(v, 6) for k, v in per.items()}


# ---------------------------------------------------------------------------
# CostBudget — simple budget gate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CostBudget:
    """Cost budget configuration checked by the sweep before each Slot B call."""

    max_cost_per_sweep_usd: float = 1.00
    max_cost_per_day_usd: float = 10.00

    def would_exceed_sweep(
        self, current_sweep_cost: float, estimated_next: float
    ) -> bool:
        return (current_sweep_cost + estimated_next) > self.max_cost_per_sweep_usd

    def would_exceed_daily(
        self, current_daily_cost: float, estimated_next: float
    ) -> bool:
        return (current_daily_cost + estimated_next) > self.max_cost_per_day_usd

    def to_dict(self) -> dict[str, float]:
        return {
            "max_cost_per_sweep_usd": self.max_cost_per_sweep_usd,
            "max_cost_per_day_usd": self.max_cost_per_day_usd,
        }
