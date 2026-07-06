"""ingest_slack_internal_notes: composes confirmed mappings + slack_reader
+ internal_note persistence. The live HTTP call (live_channel_messages) is
mocked -- the Owner Ask boundary for the actual Slack call is already
covered by test_slack_reader.py's fail-closed test; this test proves the
ingest/persistence wiring around it, including idempotency across re-runs.
"""

from __future__ import annotations

from unittest.mock import patch

from ultra_csm.comms_mapping import confirm_comms_mapping, ingest_slack_internal_notes
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
    channel_id="C0123456",
    channel_name="C0123456",
    messages=(
        SlackMessage(author_display_name="Marcus Webb", text="renewal risk flagged", timestamp="2026-06-01T00:00:00.0000Z"),
        SlackMessage(author_display_name="Grace Okafor", text="champion went quiet", timestamp="2026-06-02T00:00:00.0000Z"),
    ),
    candidates=(),
)


def _seed_account(conn, *, account_id, name):
    with session(conn, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK) as cur:
        cur.execute(
            "INSERT INTO account (account_id, tenant_id, name) VALUES (%s, %s, %s) "
            "ON CONFLICT (account_id) DO NOTHING",
            (account_id, T1, name),
        )


def _note_count(conn, account_id):
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, true)", (T1,))
        cur.execute("SELECT count(*) FROM internal_note WHERE account_id = %s", (account_id,))
        return cur.fetchone()[0]


def test_ingest_writes_notes_for_confirmed_mapping(gov_conn):
    orch, _ = setup_roster(gov_conn)
    account_id = "88888888-8888-8888-8888-888888888888"
    _seed_account(gov_conn, account_id=account_id, name="Meridian Fleet")
    confirm_comms_mapping(
        gov_conn, tenant_id=T1, actor_id=T1_AGENT, source_type="slack_channel",
        external_id="C0123456", account_id=account_id, confirmed_by=orch, now=CLOCK,
    )

    with patch("ultra_csm.comms_mapping.live_channel_messages", return_value=_FAKE_PENDING):
        written = ingest_slack_internal_notes(gov_conn, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK)

    assert written == 2
    assert _note_count(gov_conn, account_id) == 2


def test_ingest_is_idempotent_across_reruns(gov_conn):
    orch, _ = setup_roster(gov_conn)
    account_id = "99999999-9999-9999-9999-999999999999"
    _seed_account(gov_conn, account_id=account_id, name="Pinnacle Supply")
    confirm_comms_mapping(
        gov_conn, tenant_id=T1, actor_id=T1_AGENT, source_type="slack_channel",
        external_id="C0123456", account_id=account_id, confirmed_by=orch, now=CLOCK,
    )

    with patch("ultra_csm.comms_mapping.live_channel_messages", return_value=_FAKE_PENDING):
        ingest_slack_internal_notes(gov_conn, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK)
        second_run_written = ingest_slack_internal_notes(gov_conn, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK)

    assert second_run_written == 0  # same messages, same deterministic ids -- nothing new
    assert _note_count(gov_conn, account_id) == 2  # still exactly 2, not 4


def test_ingest_with_no_confirmed_mappings_writes_nothing(gov_conn):
    setup_roster(gov_conn)
    with patch("ultra_csm.comms_mapping.live_channel_messages") as mock_fetch:
        written = ingest_slack_internal_notes(gov_conn, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK)

    assert written == 0
    mock_fetch.assert_not_called()
