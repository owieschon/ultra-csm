"""Ambient temporal awareness (amendment 20) — distributed agents coordinate off
one canonical UTC clock; the clock is injectable so the eval stays deterministic."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ultra_csm.agent_context import AgentContext, current

# A fixed logical instant — the eval would inject one like this; no wall clock.
_T = datetime(2026, 6, 25, 16, 30, 0, tzinfo=timezone.utc)


def test_distributed_agents_share_one_instant():
    """Two agents on different continents read the SAME canonical instant in their
    own local time — coherent collaboration across IP addresses / time zones."""
    ny = current(now=_T, tz="America/New_York", locale="en_US")
    tokyo = current(now=_T, tz="Asia/Tokyo", locale="ja_JP")

    # Same canonical UTC underneath — no drift between participants.
    assert ny.now_utc == tokyo.now_utc == _T

    # Each renders the SAME post instant in its own zone, correctly.
    assert ny.render(_T).startswith("2026-06-25T12:30:00")   # UTC-4 (EDT)
    assert tokyo.render(_T).startswith("2026-06-26T01:30:00")  # UTC+9, next day

    # Tokyo can render NY's local wall time and vice-versa off the one instant.
    assert ny.render(_T, tz="Asia/Tokyo") == tokyo.render(_T)


def test_injected_clock_is_deterministic():
    """Same injected now → identical context (the eval-determinism contract)."""
    a = current(now=_T, tz="UTC")
    b = current(now=_T, tz="UTC")
    assert a.header() == b.header()
    assert "utc=2026-06-25T16:30:00+00:00" in a.header()
    assert "tz=UTC" in a.header() and "locale=en_US" in a.header()


def test_header_includes_location_when_present():
    ctx = current(now=_T, tz="Europe/London", locale="en_GB", location="London, UK")
    assert "location=London, UK" in ctx.header()
    assert "tz=Europe/London" in ctx.header()


def test_live_default_is_real_utc():
    """With no injected clock, the context is real UTC (the live lane)."""
    ctx = current(tz="UTC")
    assert ctx.now_utc.tzinfo is timezone.utc
    # Within a wide sanity window of 'now' — proves it read the real clock.
    assert ctx.now_utc.year >= 2026


def test_naive_now_is_read_as_utc():
    ctx = current(now=datetime(2026, 6, 25, 16, 30, 0))  # naive
    assert ctx.now_utc == _T


def test_naive_instant_is_constructor_guarded():
    with pytest.raises(ValueError):
        AgentContext(now_utc=datetime(2026, 6, 25, 16, 30, 0))  # naive → reject
