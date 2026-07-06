"""End-to-end: confirm a mapping, ingest, then prove FixtureCommsConnector
(with a real conn) reads exactly what was written -- the actual closing
move of the seed-then-read gap (2026-07-05 follow-up)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from ultra_csm.comms_mapping import confirm_comms_mapping, ingest_slack_internal_notes
from ultra_csm.data_plane.fixtures import FixtureCommsConnector
from ultra_csm.data_plane.slack_reader import PendingSlackChannel, SlackMessage
from ultra_csm.platform.db import session

from tests._govhelpers import (  # noqa: F401 - gov_conn is a pytest fixture used by injection
    CLOCK,
    T1,
    T1_AGENT,
    gov_conn,
    setup_roster,
)

_FAKE_PENDING = PendingSlackChannel(
    channel_id="C9999",
    channel_name="C9999",
    messages=(
        SlackMessage(author_display_name="Marcus Webb", text="renewal risk flagged", timestamp="2026-06-01T00:00:00.0000Z"),
    ),
    candidates=(),
)


def test_connector_reads_back_exactly_what_ingest_wrote(gov_conn):
    orch, _ = setup_roster(gov_conn)
    account_id = "cccccccc-0000-0000-0000-000000000001"
    with session(gov_conn, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK) as cur:
        cur.execute(
            "INSERT INTO account (account_id, tenant_id, name) VALUES (%s, %s, %s) "
            "ON CONFLICT (account_id) DO NOTHING",
            (account_id, T1, "Meridian Fleet"),
        )
    confirm_comms_mapping(
        gov_conn, tenant_id=T1, actor_id=T1_AGENT, source_type="slack_channel",
        external_id="C9999", account_id=account_id, confirmed_by=orch, now=CLOCK,
    )
    with patch("ultra_csm.comms_mapping.live_channel_messages", return_value=_FAKE_PENDING):
        ingest_slack_internal_notes(gov_conn, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK)

    connector = FixtureCommsConnector(conn=gov_conn, tenant_id=T1)
    notes = connector.list_internal_notes(account_id)

    assert len(notes) == 1
    assert notes[0].author == "Marcus Webb"
    assert notes[0].content == "renewal risk flagged"
    assert notes[0].source == "slack"
    # message_ts round-tripped, not created_at -- compare the instant, not
    # the literal string: psycopg renders timestamptz in the session's
    # local offset, not necessarily "+00:00", for an equal UTC instant.
    assert datetime.fromisoformat(notes[0].timestamp) == datetime.fromisoformat("2026-06-01T00:00:00+00:00")


def test_connector_returns_empty_for_an_account_with_no_ingested_comms(gov_conn):
    setup_roster(gov_conn)
    account_id = "cccccccc-0000-0000-0000-000000000002"
    with session(gov_conn, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK) as cur:
        cur.execute(
            "INSERT INTO account (account_id, tenant_id, name) VALUES (%s, %s, %s) "
            "ON CONFLICT (account_id) DO NOTHING",
            (account_id, T1, "Pinnacle Supply"),
        )

    connector = FixtureCommsConnector(conn=gov_conn, tenant_id=T1)

    assert connector.list_internal_notes(account_id) == []
    assert connector.list_gmail_signals(account_id) == []
    assert connector.list_call_transcript_signals(account_id) == []
