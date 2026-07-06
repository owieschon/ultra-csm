"""Offline tests for the Notion call-transcript connector.

Mirrors tests/test_notion_render.py's fail-closed-without-credentials
pattern and tests/test_live_gmail_reader_ooo_guard.py's synthetic-payload
construction style. The live HTTP path (query_meeting_notes/transcript
fetch) is not exercised here -- same Owner Ask boundary as the Notion
authoring edge and Gmail live readers.
"""

from __future__ import annotations

import pytest

from ultra_csm.data_plane.contracts import CommunicationSignal, CRMContact
from ultra_csm.data_plane.notion_call_transcripts import (
    KnownAccount,
    NotionTranscriptReadError,
    confirm_call_transcript,
    live_call_transcripts,
    parse_meeting_note,
)

_MERIDIAN = KnownAccount(
    account_id="acct-meridian-fleet",
    account_name="Meridian Fleet",
    contacts=(
        CRMContact(
            contact_id="contact-alicia",
            account_id="acct-meridian-fleet",
            email="alicia.fernandez@meridianfleet.example",
            name="Alicia Fernandez",
            role="champion",
            title="VP Fleet Ops",
            consent_to_contact=True,
        ),
    ),
)
_PINNACLE = KnownAccount(account_id="acct-pinnacle-supply", account_name="Pinnacle Supply")


def _raw_meeting_note(title: str, *, start_time: str | None = "2026-06-15T14:00:00.000Z") -> dict:
    return {
        "object": "block",
        "id": "meeting-note-1",
        "type": "meeting_notes",
        "meeting_notes": {
            "title": [{"type": "text", "text": {"content": title}, "plain_text": title}],
            "status": "notes_ready",
            "children": {
                "summary_block_id": "sum-1",
                "notes_block_id": "notes-1",
                "transcript_block_id": "transcript-1",
            },
            "calendar_event": {"start_time": start_time, "end_time": None, "attendees": []},
        },
    }


def test_title_match_proposes_a_candidate():
    note = _raw_meeting_note("FleetOps <> Meridian Fleet - Weekly Sync")
    pending = parse_meeting_note(
        note, transcript_text="general discussion, nothing account-specific", known_accounts=(_MERIDIAN, _PINNACLE)
    )
    assert pending.title == "FleetOps <> Meridian Fleet - Weekly Sync"
    signals = {c.signal for c in pending.candidates}
    account_ids = {c.account_id for c in pending.candidates}
    assert "title_match" in signals
    assert "acct-meridian-fleet" in account_ids
    assert "acct-pinnacle-supply" not in account_ids


def test_transcript_text_match_proposes_a_lower_confidence_candidate():
    note = _raw_meeting_note("Weekly Sync")  # title carries no account signal
    pending = parse_meeting_note(
        note,
        transcript_text="...following up, alicia.fernandez@meridianfleet.example will confirm...",
        known_accounts=(_MERIDIAN, _PINNACLE),
    )
    assert len(pending.candidates) == 1
    candidate = pending.candidates[0]
    assert candidate.signal == "transcript_text_match"
    assert candidate.account_id == "acct-meridian-fleet"
    title_candidates = [c for c in pending.candidates if c.signal == "title_match"]
    assert not title_candidates


def test_no_match_yields_no_candidates():
    note = _raw_meeting_note("Internal standup")
    pending = parse_meeting_note(note, transcript_text="unrelated content", known_accounts=(_MERIDIAN, _PINNACLE))
    assert pending.candidates == ()


def test_confirm_mints_a_call_communication_signal_only_after_human_pick():
    note = _raw_meeting_note("FleetOps <> Meridian Fleet - Weekly Sync")
    pending = parse_meeting_note(note, transcript_text="", known_accounts=(_MERIDIAN,))

    signal = confirm_call_transcript(
        pending, account_id="acct-meridian-fleet", contact_id="contact-alicia", signal_id="sig-call-1"
    )

    assert isinstance(signal, CommunicationSignal)
    assert signal.channel == "call"
    assert signal.account_id == "acct-meridian-fleet"
    assert signal.contact_id == "contact-alicia"
    assert signal.timestamp == "2026-06-15T14:00:00.000Z"


def test_live_reader_fails_closed_without_credentials(tmp_path):
    """Decision 4 / K8 discipline, same as the authoring edge: absent a
    NOTION_* credential entry, the live pull raises rather than silently
    no-op or fabricate a payload."""

    empty_creds = tmp_path / "empty-creds.env"
    empty_creds.write_text("", encoding="utf-8")

    with pytest.raises(NotionTranscriptReadError, match="ULTRA_CSM_NOTION_TOKEN"):
        live_call_transcripts(known_accounts=(_MERIDIAN,), creds_path=str(empty_creds))
