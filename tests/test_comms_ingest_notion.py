"""ingest_notion_call_transcripts: composes confirmed notion_meeting
mappings + notion_call_transcripts.py + communication_signal persistence.
Mirrors test_comms_ingest.py's Slack test pattern; the live HTTP call
(live_single_meeting_transcript) is mocked -- the Owner Ask boundary for
the actual Notion call is already covered by test_notion_call_transcripts.py's
fail-closed test.
"""

from __future__ import annotations

from unittest.mock import patch

from ultra_csm.comms_mapping import confirm_comms_mapping, ingest_notion_call_transcripts
from ultra_csm.data_plane.notion_call_transcripts import PendingCallTranscript
from ultra_csm.platform.db import session

from tests._govhelpers import (  # noqa: F401 - gov_conn is a pytest fixture used by injection
    CLOCK,
    T1,
    T1_AGENT,
    gov_conn,
    setup_roster,
)

_FAKE_PENDING = PendingCallTranscript(
    meeting_note_id="meeting-note-1",
    title="FleetOps <> Meridian Fleet - Weekly Sync",
    occurred_at="2026-06-15T14:00:00.000Z",
    transcript_text="renewal risk flagged, need a plan",
    candidates=(),
)


def _seed_account_and_contact(conn, *, account_id, contact_id, name):
    with session(conn, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK) as cur:
        cur.execute(
            "INSERT INTO account (account_id, tenant_id, name) VALUES (%s, %s, %s) "
            "ON CONFLICT (account_id) DO NOTHING",
            (account_id, T1, name),
        )
        cur.execute(
            "INSERT INTO contact (contact_id, tenant_id, account_id, email, name) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (contact_id) DO NOTHING",
            (contact_id, T1, account_id, f"{contact_id}@example.com", "Alicia Fernandez"),
        )


def _signal_count(conn, account_id):
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, true)", (T1,))
        cur.execute("SELECT count(*) FROM communication_signal WHERE account_id = %s", (account_id,))
        return cur.fetchone()[0]


def test_ingest_writes_a_signal_for_confirmed_mapping_with_a_contact(gov_conn):
    orch, _ = setup_roster(gov_conn)
    account_id = "aaaaaaaa-1111-1111-1111-111111111111"
    contact_id = "bbbbbbbb-1111-1111-1111-111111111111"
    _seed_account_and_contact(gov_conn, account_id=account_id, contact_id=contact_id, name="Meridian Fleet")
    confirm_comms_mapping(
        gov_conn, tenant_id=T1, actor_id=T1_AGENT, source_type="notion_meeting",
        external_id="meeting-note-1", account_id=account_id, contact_id=contact_id,
        confirmed_by=orch, now=CLOCK,
    )

    with patch("ultra_csm.comms_mapping.live_single_meeting_transcript", return_value=_FAKE_PENDING):
        written = ingest_notion_call_transcripts(gov_conn, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK)

    assert written == 1
    assert _signal_count(gov_conn, account_id) == 1


def test_ingest_is_idempotent_across_reruns(gov_conn):
    orch, _ = setup_roster(gov_conn)
    account_id = "aaaaaaaa-2222-2222-2222-222222222222"
    contact_id = "bbbbbbbb-2222-2222-2222-222222222222"
    _seed_account_and_contact(gov_conn, account_id=account_id, contact_id=contact_id, name="Pinnacle Supply")
    confirm_comms_mapping(
        gov_conn, tenant_id=T1, actor_id=T1_AGENT, source_type="notion_meeting",
        external_id="meeting-note-1", account_id=account_id, contact_id=contact_id,
        confirmed_by=orch, now=CLOCK,
    )

    with patch("ultra_csm.comms_mapping.live_single_meeting_transcript", return_value=_FAKE_PENDING):
        ingest_notion_call_transcripts(gov_conn, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK)
        second_written = ingest_notion_call_transcripts(gov_conn, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK)

    assert second_written == 0
    assert _signal_count(gov_conn, account_id) == 1


def test_ingest_skips_mapping_with_no_confirmed_contact(gov_conn):
    orch, _ = setup_roster(gov_conn)
    account_id = "aaaaaaaa-3333-3333-3333-333333333333"
    with session(gov_conn, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK) as cur:
        cur.execute(
            "INSERT INTO account (account_id, tenant_id, name) VALUES (%s, %s, %s) "
            "ON CONFLICT (account_id) DO NOTHING",
            (account_id, T1, "Crateworks"),
        )
    confirm_comms_mapping(
        gov_conn, tenant_id=T1, actor_id=T1_AGENT, source_type="notion_meeting",
        external_id="meeting-note-2", account_id=account_id, contact_id=None,
        confirmed_by=orch, now=CLOCK,
    )

    with patch("ultra_csm.comms_mapping.live_single_meeting_transcript") as mock_fetch:
        written = ingest_notion_call_transcripts(gov_conn, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK)

    assert written == 0
    mock_fetch.assert_not_called()  # never even attempted the live call -- skipped before fetching
