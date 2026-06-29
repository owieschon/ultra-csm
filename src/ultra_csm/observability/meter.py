"""The METER seam — counters + histograms behind an injectable protocol.

The metrics twin of `tracer.py`: the same NoOp-default / lazy-Otel-live split. The
Orchestrator builds its instruments ONCE from the injected meter in `__init__`
(`counter`/`histogram`), then `add`/`record`s them at the terminal points of a turn.

The `enabled` flag is the determinism guard. It is the ONLY thing the orchestrator
consults before reading a monotonic clock for turn latency: `NoOpMeter.enabled is
False`, so the scored path never reads a wall-clock and the latency value never
exists. A live `OtelMeter` (or the in-memory `RecordingMeter` a test injects) reports
`enabled is True`, so timing runs only off the scored path. The instruments
themselves are no-ops under NoOp regardless — `enabled` exists purely so the CALLER
can skip even computing the value to feed them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable


@runtime_checkable
class Counter(Protocol):
    def add(self, amount: int = 1, attributes: Mapping[str, Any] | None = None) -> None: ...


@runtime_checkable
class Histogram(Protocol):
    def record(self, value: float, attributes: Mapping[str, Any] | None = None) -> None: ...


@runtime_checkable
class Meter(Protocol):
    enabled: bool

    def counter(self, name: str, *, unit: str = "1", description: str = "") -> Counter: ...

    def histogram(self, name: str, *, unit: str = "1", description: str = "") -> Histogram: ...


# ---------------------------------------------------------------------------
# NoOp — the default, the scored path.
# ---------------------------------------------------------------------------
class _NoOpCounter:
    __slots__ = ()

    def add(self, amount: int = 1, attributes: Mapping[str, Any] | None = None) -> None:
        pass


class _NoOpHistogram:
    __slots__ = ()

    def record(self, value: float, attributes: Mapping[str, Any] | None = None) -> None:
        pass


_NOOP_COUNTER = _NoOpCounter()
_NOOP_HISTOGRAM = _NoOpHistogram()


class NoOpMeter:
    """The default meter: every instrument is a shared no-op, `enabled` is False, so
    the orchestrator records nothing AND never reads a clock to compute a latency."""

    __slots__ = ()
    enabled = False

    def counter(self, name: str, *, unit: str = "1", description: str = "") -> _NoOpCounter:
        return _NOOP_COUNTER

    def histogram(self, name: str, *, unit: str = "1", description: str = "") -> _NoOpHistogram:
        return _NOOP_HISTOGRAM


@dataclass
class RecordedCounter:
    name: str
    observations: list[tuple[int, dict[str, Any]]] = field(default_factory=list)

    def add(self, amount: int = 1, attributes: Mapping[str, Any] | None = None) -> None:
        self.observations.append((amount, dict(attributes or {})))

    @property
    def total(self) -> int:
        return sum(amount for amount, _ in self.observations)


@dataclass
class RecordedHistogram:
    name: str
    observations: list[tuple[float, dict[str, Any]]] = field(default_factory=list)

    def record(self, value: float, attributes: Mapping[str, Any] | None = None) -> None:
        self.observations.append((value, dict(attributes or {})))

    @property
    def count(self) -> int:
        return len(self.observations)


class RecordingMeter:
    """In-memory meter used by deterministic CSM tests."""

    enabled = True

    def __init__(self) -> None:
        self.counters: dict[str, RecordedCounter] = {}
        self.histograms: dict[str, RecordedHistogram] = {}

    def counter(self, name: str, *, unit: str = "1", description: str = "") -> RecordedCounter:
        return self.counters.setdefault(name, RecordedCounter(name))

    def histogram(
        self, name: str, *, unit: str = "1", description: str = ""
    ) -> RecordedHistogram:
        return self.histograms.setdefault(name, RecordedHistogram(name))
