"""The TRACER seam — a distributed-tracing port behind an injectable protocol.

The same seam shape the codebase already uses for the LLM slots, the CRM connector,
the gate's VerdictSource, and the injected clock: a `Protocol` with a deterministic,
zero-side-effect default (`NoOpTracer`) that the scored eval gets, and a live
implementation (`OtelTracer`, see `otel.py`) the runtime wires only when an OTLP
endpoint is configured.

DETERMINISM (the critical property): the scored battery injects NOTHING, so the
Orchestrator defaults to `NoOpTracer`. A NoOp span reads no wall-clock, allocates no
exporter, and records nothing — `make scorecard` is byte-identical whether or not the
observability layer exists. Observability only OBSERVES; it never touches the value
path, the two chokepoints, or any scored output.

This module has ZERO third-party imports — importing it never pulls in OpenTelemetry,
so the offline eval (which imports the Orchestrator, which imports this) stays lean.
The OTel SDK is imported lazily inside `otel.py`, behind the env gate.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping, Protocol, runtime_checkable


@runtime_checkable
class Span(Protocol):
    """A single unit of work in a trace. Attributes describe it (intent, tier, account);
    events mark point-in-time facts inside it (the contain ALLOW/BLOCK chokepoint,
    the seal exit-token mint)."""

    def set_attribute(self, key: str, value: Any) -> None: ...

    def add_event(self, name: str, attributes: Mapping[str, Any] | None = None) -> None: ...


@runtime_checkable
class Tracer(Protocol):
    """Opens spans. `start_span` is a context manager so the caller wraps a block of
    work and the span closes (and, live, exports) on exit — including on an early
    return or an exception, the deterministic-cleanup property the orchestrator's
    early-return escalation paths rely on."""

    def start_span(
        self, name: str, attributes: Mapping[str, Any] | None = None
    ) -> "Iterator[Span]": ...  # a context manager yielding a Span


# ---------------------------------------------------------------------------
# NoOp — the default, the scored path. Zero side-effects, no wall-clock.
# ---------------------------------------------------------------------------
class _NoOpSpan:
    """A span that records nothing. A single shared instance is reused for every
    NoOp span so the default path allocates no per-span object beyond the generator
    the context manager needs."""

    __slots__ = ()

    def set_attribute(self, key: str, value: Any) -> None:  # noqa: D401 - no-op
        pass

    def add_event(self, name: str, attributes: Mapping[str, Any] | None = None) -> None:
        pass


_NOOP_SPAN = _NoOpSpan()


class NoOpTracer:
    """The default tracer: every `start_span` yields the shared no-op span and does
    NOTHING else. No wall-clock read, no exporter, no recorded state — so a turn run
    under it is byte-identical to a turn run with no instrumentation at all."""

    __slots__ = ()

    @contextmanager
    def start_span(
        self, name: str, attributes: Mapping[str, Any] | None = None
    ) -> Iterator[_NoOpSpan]:
        yield _NOOP_SPAN


@dataclass
class RecordedSpan:
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    parent: "RecordedSpan | None" = None
    children: list["RecordedSpan"] = field(default_factory=list)

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Mapping[str, Any] | None = None) -> None:
        self.events.append((name, dict(attributes or {})))

    def descendants(self) -> "list[RecordedSpan]":
        out: list[RecordedSpan] = []
        for child in self.children:
            out.append(child)
            out.extend(child.descendants())
        return out

    def child_names(self) -> list[str]:
        return [child.name for child in self.children]

    def find(self, name: str) -> "RecordedSpan | None":
        for span in [self, *self.descendants()]:
            if span.name == name:
                return span
        return None


class RecordingTracer:
    """In-memory tracer used by deterministic CSM tests."""

    def __init__(self) -> None:
        self.roots: list[RecordedSpan] = []
        self.spans: list[RecordedSpan] = []
        self._stack: list[RecordedSpan] = []

    @contextmanager
    def start_span(
        self, name: str, attributes: Mapping[str, Any] | None = None
    ) -> Iterator[RecordedSpan]:
        parent = self._stack[-1] if self._stack else None
        span = RecordedSpan(name=name, attributes=dict(attributes or {}), parent=parent)
        if parent is not None:
            parent.children.append(span)
        else:
            self.roots.append(span)
        self.spans.append(span)
        self._stack.append(span)
        try:
            yield span
        finally:
            self._stack.pop()

    @property
    def root(self) -> RecordedSpan:
        return self.roots[0]

    def names(self) -> list[str]:
        return [span.name for span in self.spans]
