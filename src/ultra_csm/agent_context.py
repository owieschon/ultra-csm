"""Ambient temporal + location awareness (REQUIREMENTS amendment 20).

Every agent carries an `AgentContext`: a canonical UTC clock plus its timezone and
locale, so agents collaborating from different IP addresses around the world share
one clock and can render each other's timestamps coherently. The Commons stamps
posts in UTC; each recipient renders them in its own zone off this one instant.

The clock is INJECTABLE — live agents use real UTC; the deterministic eval injects
a fixed logical clock (the same offline/live split as ``platform`` ``app.clock()``
and the seed's ``now``), so the scored battery is never wall-clock dependent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class AgentContext:
    """The ambient context every agent carries. ``now_utc`` is timezone-aware UTC;
    ``tz`` is the agent's IANA zone; ``locale`` and the optional ``location`` hint
    (e.g. IP-derived) let a globally-distributed roster coordinate coherently."""

    now_utc: datetime
    tz: str = "UTC"
    locale: str = "en_US"
    location: str | None = None

    def __post_init__(self) -> None:
        if self.now_utc.tzinfo is None:
            raise ValueError("now_utc must be timezone-aware (UTC)")

    def local_now(self) -> datetime:
        """This agent's wall-clock now, in its own zone."""
        return self.now_utc.astimezone(ZoneInfo(self.tz))

    def render(self, ts: datetime, *, tz: str | None = None) -> str:
        """Render a UTC instant in a recipient's zone (default this agent's). A
        naive timestamp is read as UTC. This is how one canonical instant reads
        correctly for every participant regardless of where they sit."""
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(ZoneInfo(tz or self.tz)).isoformat()

    def header(self) -> str:
        """The one-line ambient header every agent carries into its context."""
        head = (f"utc={self.now_utc.astimezone(timezone.utc).isoformat()} "
                f"tz={self.tz} locale={self.locale}")
        return head + (f" location={self.location}" if self.location else "")


def current(
    *,
    now: datetime | None = None,
    tz: str = "UTC",
    locale: str = "en_US",
    location: str | None = None,
) -> AgentContext:
    """Construct the ambient context. ``now`` defaults to real UTC (the live
    lane); the eval injects a fixed logical clock so the scored path stays
    byte-deterministic. A naive ``now`` is read as UTC."""
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return AgentContext(
        now_utc=now.astimezone(timezone.utc), tz=tz, locale=locale, location=location
    )
