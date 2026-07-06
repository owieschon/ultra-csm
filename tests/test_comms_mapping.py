"""comms_source_mapping: confirm/list + RLS + idempotent re-confirm, same
discipline as test_internal_notes.py (migrations/0006_comms_source_mappings.sql)."""

from __future__ import annotations

from ultra_csm.comms_mapping import confirm_comms_mapping, list_confirmed_mappings
from ultra_csm.platform.db import session

from tests._govhelpers import (  # noqa: F401 - gov_conn is a pytest fixture used by injection
    CLOCK,
    T1,
    T1_AGENT,
    T2,
    T2_AGENT,
    change_log_count,
    gov_conn,
    setup_roster,
)


def _seed_account(conn, *, tenant, actor, account_id, name):
    with session(conn, tenant_id=tenant, actor_id=actor, now=CLOCK) as cur:
        cur.execute(
            "INSERT INTO account (account_id, tenant_id, name) VALUES (%s, %s, %s) "
            "ON CONFLICT (account_id) DO NOTHING",
            (account_id, tenant, name),
        )


def test_confirm_and_list_slack_channel_mapping(gov_conn):
    orch, _ = setup_roster(gov_conn)
    account_id = "44444444-4444-4444-4444-444444444444"
    _seed_account(gov_conn, tenant=T1, actor=T1_AGENT, account_id=account_id, name="Meridian Fleet")

    mapping_id = confirm_comms_mapping(
        gov_conn,
        tenant_id=T1,
        actor_id=T1_AGENT,
        source_type="slack_channel",
        external_id="C0123456",
        account_id=account_id,
        confirmed_by=orch,
        now=CLOCK,
    )
    assert mapping_id

    mappings = list_confirmed_mappings(gov_conn, tenant_id=T1, source_type="slack_channel")
    assert len(mappings) == 1
    assert mappings[0].external_id == "C0123456"
    assert mappings[0].account_id == account_id
    assert mappings[0].contact_id is None  # channel-level, no specific contact

    assert change_log_count(gov_conn, "comms_source_mapping", "mapping_id", mapping_id, tenant=T1) == 1


def test_reconfirm_updates_rather_than_errors(gov_conn):
    orch, _ = setup_roster(gov_conn)
    account_a = "55555555-5555-5555-5555-555555555555"
    account_b = "66666666-6666-6666-6666-666666666666"
    _seed_account(gov_conn, tenant=T1, actor=T1_AGENT, account_id=account_a, name="Pinnacle Supply")
    _seed_account(gov_conn, tenant=T1, actor=T1_AGENT, account_id=account_b, name="Crateworks")

    first_id = confirm_comms_mapping(
        gov_conn, tenant_id=T1, actor_id=T1_AGENT, source_type="notion_meeting",
        external_id="meeting-note-1", account_id=account_a, confirmed_by=orch, now=CLOCK,
    )
    second_id = confirm_comms_mapping(
        gov_conn, tenant_id=T1, actor_id=T1_AGENT, source_type="notion_meeting",
        external_id="meeting-note-1", account_id=account_b, confirmed_by=orch, now=CLOCK,
    )

    assert first_id == second_id  # same row, updated -- not a duplicate
    mappings = list_confirmed_mappings(gov_conn, tenant_id=T1, source_type="notion_meeting")
    assert len(mappings) == 1
    assert mappings[0].account_id == account_b  # the correction won


def test_mappings_are_tenant_isolated(gov_conn):
    orch1, _ = setup_roster(gov_conn, tenant=T1, seed_actor=T1_AGENT)
    setup_roster(gov_conn, tenant=T2, seed_actor=T2_AGENT)
    account_id = "77777777-7777-7777-7777-777777777777"
    _seed_account(gov_conn, tenant=T1, actor=T1_AGENT, account_id=account_id, name="Loopway")

    confirm_comms_mapping(
        gov_conn, tenant_id=T1, actor_id=T1_AGENT, source_type="slack_channel",
        external_id="C-t1-only", account_id=account_id, confirmed_by=orch1, now=CLOCK,
    )

    t2_mappings = list_confirmed_mappings(gov_conn, tenant_id=T2, source_type="slack_channel")
    assert t2_mappings == []
