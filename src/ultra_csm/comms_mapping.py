"""Confirmed account-attribution for identity-ambiguous comms evidence.

Persists the "confirm" half of notion_call_transcripts.py's / slack_reader.py's
propose-then-confirm discipline (migrations/0006_comms_source_mappings.sql).
A human confirms an external identifier (a Notion meeting note, a Slack
channel) maps to an account once; a later ingest run reads the confirmed
mapping instead of re-proposing candidates for something already resolved.

No review UI exists yet for browsing pending candidates (Owner Ask,
2026-07-05) -- this module is the persistence + confirm/lookup primitives a
future UI action would call, mirroring how governance/gate.py's functions
predate any UI that drives them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from ultra_csm.data_plane.notion_call_transcripts import (
    confirm_call_transcript,
    live_single_meeting_transcript,
)
from ultra_csm.data_plane.slack_reader import confirm_slack_channel, live_channel_messages
from ultra_csm.platform.db import session

SourceType = Literal["notion_meeting", "slack_channel"]


def _deterministic_id(*parts: str) -> str:
    """Stable across repeat ingest runs (same identifying parts -> same
    id), so a re-run's INSERT ... ON CONFLICT DO NOTHING is genuinely
    idempotent rather than relying on fetch-order-dependent indices."""

    return str(uuid5(NAMESPACE_URL, "ultra-csm:" + ":".join(parts)))


@dataclass(frozen=True)
class ConfirmedMapping:
    source_type: SourceType
    external_id: str
    account_id: str
    contact_id: str | None
    confirmed_by: str
    confirmed_at: str


def confirm_comms_mapping(
    conn,
    *,
    tenant_id: str,
    actor_id: str,
    source_type: SourceType,
    external_id: str,
    account_id: str,
    confirmed_by: str,
    contact_id: str | None = None,
    now=None,
) -> str:
    """Persist a human-confirmed external-id -> account attribution.

    Idempotent on (tenant_id, source_type, external_id): re-confirming
    updates the existing row (a CSM correcting an earlier confirm needs no
    delete first) rather than erroring on the UNIQUE constraint."""

    with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=now) as cur:
        cur.execute(
            "INSERT INTO comms_source_mapping "
            "(mapping_id, tenant_id, source_type, external_id, account_id, contact_id, confirmed_by) "
            "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (tenant_id, source_type, external_id) DO UPDATE SET "
            "account_id = EXCLUDED.account_id, contact_id = EXCLUDED.contact_id, "
            "confirmed_by = EXCLUDED.confirmed_by, confirmed_at = app.clock(), "
            "row_version = comms_source_mapping.row_version + 1 "
            "RETURNING mapping_id",
            (tenant_id, source_type, external_id, account_id, contact_id, confirmed_by),
        )
        return str(cur.fetchone()[0])


def ingest_slack_internal_notes(
    conn, *, tenant_id: str, actor_id: str, creds_path: str | None = None, now=None
) -> int:
    """Pull messages for every confirmed slack_channel mapping and persist
    them into internal_note. This is the standalone ingest half of the
    seed-then-read pattern every other connector in this app already uses
    (FixtureCommsConnector is the read half) -- mirrors 'Program 7' live
    narrative seeding's shape, NOT wired into the live API request path
    (nothing in this app reads live at request time; see api.py survey).

    Deliberately NOT scheduled here: a recurring job (launchd/cron) is an
    Owner Ask per this repo's own risk posture (AGENT_PROFILE.md: 'Always
    owner-gated regardless of anything: standing jobs'). Callable directly
    or from a future scheduled invocation the owner sets up.

    Returns the count of notes written (new + updated). Idempotent: each
    note's id is deterministic from (channel_id, message timestamp), so a
    re-run against unchanged messages writes nothing new.
    """

    written = 0
    for mapping in list_confirmed_mappings(conn, tenant_id=tenant_id, source_type="slack_channel"):
        pending = live_channel_messages(channel_id=mapping.external_id, creds_path=creds_path)
        notes = confirm_slack_channel(
            pending, account_id=mapping.account_id, note_id_prefix=f"slack-{mapping.external_id}"
        )
        with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=now) as cur:
            for note in notes:
                stable_id = _deterministic_id("slack-note", mapping.external_id, note.timestamp)
                cur.execute(
                    "INSERT INTO internal_note "
                    "(note_id, tenant_id, account_id, author, content, source, message_ts) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (note_id) DO NOTHING",
                    (stable_id, tenant_id, note.account_id, note.author, note.content, note.source, note.timestamp),
                )
                written += cur.rowcount
    return written


def ingest_notion_call_transcripts(
    conn, *, tenant_id: str, actor_id: str, creds_path: str | None = None, now=None
) -> int:
    """Pull the transcript for every confirmed notion_meeting mapping and
    persist it into communication_signal -- the Notion-transcript sibling
    of ingest_slack_internal_notes, same seed-then-read discipline (not
    wired into the live API request path; see that function's docstring).

    Mappings with no confirmed contact_id are skipped, not defaulted:
    communication_signal.contact_id is NOT NULL (CommunicationSignal.
    contact_id is a required field), and fabricating a contact would be
    exactly the kind of unevidenced claim this system never makes.
    Skipped mappings are counted separately so a caller can tell "nothing
    to do" apart from "something needs a contact confirmed."

    Returns the count of signals written (new; ON CONFLICT DO NOTHING
    makes re-running against an unchanged transcript a no-op)."""

    written = 0
    for mapping in list_confirmed_mappings(conn, tenant_id=tenant_id, source_type="notion_meeting"):
        if mapping.contact_id is None:
            continue
        pending = live_single_meeting_transcript(meeting_note_id=mapping.external_id, creds_path=creds_path)
        signal = confirm_call_transcript(
            pending,
            account_id=mapping.account_id,
            contact_id=mapping.contact_id,
            signal_id=_deterministic_id("notion-signal", mapping.external_id),
        )
        with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=now) as cur:
            cur.execute(
                "INSERT INTO communication_signal "
                "(signal_id, tenant_id, account_id, contact_id, channel, direction, "
                "message_ts, response_time_hours, attendees) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (signal_id) DO NOTHING",
                (
                    signal.signal_id, tenant_id, signal.account_id, signal.contact_id,
                    signal.channel, signal.direction, signal.timestamp or None,
                    signal.response_time_hours, list(signal.attendees),
                ),
            )
            written += cur.rowcount
    return written


def list_confirmed_mappings(
    conn, *, tenant_id: str, source_type: SourceType
) -> list[ConfirmedMapping]:
    """Every confirmed mapping of one source type for this tenant -- the
    ingest path's starting point: only fetch/attribute what's already
    confirmed, never re-propose."""

    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_id,))
        cur.execute(
            "SELECT source_type, external_id, account_id, contact_id, confirmed_by, confirmed_at "
            "FROM comms_source_mapping WHERE tenant_id = %s AND source_type = %s "
            "ORDER BY confirmed_at",
            (tenant_id, source_type),
        )
        rows = cur.fetchall()
    return [
        ConfirmedMapping(
            source_type=row[0],
            external_id=row[1],
            account_id=str(row[2]),
            contact_id=str(row[3]) if row[3] else None,
            confirmed_by=str(row[4]),
            confirmed_at=row[5].isoformat() if hasattr(row[5], "isoformat") else str(row[5]),
        )
        for row in rows
    ]
