"""Operational audit ledger gap coverage."""

from __future__ import annotations

from tests._govhelpers import CLOCK, T1, gov_conn, setup_roster  # noqa: F401
from ultra_csm.audit_ledger import (
    EXPECTED_LEDGER_EVENTS,
    audit_event_type_gap,
    record_audit_event,
)


def test_audit_event_type_gap_reports_missing_expected_events(gov_conn):
    orch, _authority = setup_roster(gov_conn)
    record_audit_event(
        gov_conn,
        tenant_id=T1,
        actor_id=orch,
        event_type="value_model",
        source_ref="test:gap:value_model",
        detail="Value model observed",
        now=CLOCK,
    )

    gap = audit_event_type_gap(
        gov_conn,
        tenant_id=T1,
        actor_id=orch,
        expected_events=("value_model", "slot_b.draft"),
        now=CLOCK,
    )

    assert gap == ("slot_b.draft",)


def test_audit_event_type_gap_empty_when_all_expected_events_observed(gov_conn):
    orch, _authority = setup_roster(gov_conn)
    for event_type in EXPECTED_LEDGER_EVENTS:
        record_audit_event(
            gov_conn,
            tenant_id=T1,
            actor_id=orch,
            event_type=event_type,
            source_ref=f"test:gap:{event_type}",
            detail=f"{event_type} observed",
            now=CLOCK,
        )

    gap = audit_event_type_gap(
        gov_conn,
        tenant_id=T1,
        actor_id=orch,
        now=CLOCK,
    )

    assert gap == ()
