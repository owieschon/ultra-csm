"""Shared helpers for the bible-driven narrative fixture modules.

Every per-account comms module (``comms_fixtures.py`` for Pinehill, and its
siblings for the other five arcs -- see docs/SYNTHETIC_UNIVERSE_BIBLE.md)
needs the same two things: a cached base synthetic book (rebuilding the
35-account book per call is wasteful), and a ``CaseLifecycle`` ->
``CRMCase`` adapter so each module reuses the existing ``_CASE_SCHEDULE``
causal exhaust instead of authoring a second, competing case timeline.
Centralized here so five modules don't duplicate (and risk diverging on)
this plumbing.
"""

from __future__ import annotations

from datetime import date, timedelta

from ultra_csm.data_plane.contracts import CRMCase
from ultra_csm.data_plane.data_simulator import CaseLifecycle, simulate_data
from ultra_csm.data_plane.fixtures import FixtureCustomerData
from ultra_csm.data_plane.synthetic_book import build_synthetic_book

_SEED = date(2026, 6, 21)

_BASE_BOOK: FixtureCustomerData | None = None


def base_synthetic_book() -> FixtureCustomerData:
    global _BASE_BOOK
    if _BASE_BOOK is None:
        _BASE_BOOK = build_synthetic_book()
    return _BASE_BOOK


def rfc3339(day_offset: int, hour: int = 9, minute: int = 0) -> str:
    from datetime import datetime, timezone

    dt = datetime(2026, 6, 21, tzinfo=timezone.utc) + timedelta(
        days=day_offset, hours=hour - 9, minutes=minute
    )
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_date(day_offset: int) -> str:
    return (_SEED + timedelta(days=day_offset)).isoformat()


def case_lifecycle_to_crmcase(cl: CaseLifecycle) -> CRMCase:
    created_at = rfc3339(cl.open_day)
    closed_at = rfc3339(cl.resolution_day) if cl.resolution_day is not None else None
    return CRMCase(
        case_id=cl.case_id,
        account_id=cl.account_id,
        status=cl.status,
        priority=cl.priority,
        origin="Email",
        subject=cl.subject,
        created_at=created_at,
        closed_at=closed_at,
    )


def cases_as_of(account_id: str, as_of_day: int) -> list[CRMCase]:
    """``CRMCase`` rows for *account_id* visible as of *as_of_day*, adapted
    from data_simulator.py's ``_CASE_SCHEDULE`` -- a case not yet opened on
    that day is not returned; an unresolved case has ``closed_at=None``,
    never a fabricated close date."""

    bundle = simulate_data(base_synthetic_book(), as_of_day)
    account = bundle.accounts[account_id]
    return [
        case_lifecycle_to_crmcase(cl) for cl in account.cases if cl.open_day <= as_of_day
    ]
