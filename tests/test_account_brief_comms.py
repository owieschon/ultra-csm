"""_build_account_brief's comms wiring, isolated from the full API/Postgres
lifespan (see tests/test_api.py for the degrade-to-empty integration test).
"""

from __future__ import annotations

import dataclasses

from ultra_csm._api_helpers import _build_account_brief
from ultra_csm.data_plane.contracts import CommunicationSignal, InternalCommsNote
from ultra_csm.data_plane.fixtures import ACME_LOGISTICS, build_fixture_data_plane

_AS_OF = "2026-06-27"


class _StubCommsConnector:
    def list_gmail_signals(self, account_id: str) -> list[CommunicationSignal]:
        return [
            CommunicationSignal(
                signal_id="sig-1", account_id=account_id, contact_id="contact-1",
                channel="email", direction="inbound", timestamp="2026-06-01T00:00:00Z",
            )
        ]

    def list_call_transcript_signals(self, account_id: str) -> list[CommunicationSignal]:
        return [
            CommunicationSignal(
                signal_id="sig-2", account_id=account_id, contact_id="contact-2",
                channel="call", direction="inbound", timestamp="2026-06-02T00:00:00Z",
            )
        ]

    def list_internal_notes(self, account_id: str) -> list[InternalCommsNote]:
        return [
            InternalCommsNote(
                note_id="note-1", account_id=account_id, author="Marcus Webb",
                timestamp="2026-06-03T00:00:00Z", content="renewal risk flagged", source="csm_note",
            )
        ]


def test_brief_populates_comms_fields_when_a_comms_source_is_configured():
    data_plane = dataclasses.replace(build_fixture_data_plane(), comms=_StubCommsConnector())

    brief = _build_account_brief(ACME_LOGISTICS, data_plane=data_plane, as_of=_AS_OF)

    assert brief["comms_gmail"] == [
        {
            "signal_id": "sig-1", "account_id": ACME_LOGISTICS, "contact_id": "contact-1",
            "channel": "email", "direction": "inbound", "timestamp": "2026-06-01T00:00:00Z",
            "response_time_hours": None, "attendees": (),
        }
    ]
    assert brief["comms_call_transcripts"][0]["channel"] == "call"
    assert brief["comms_internal"] == [
        {
            "note_id": "note-1", "account_id": ACME_LOGISTICS, "author": "Marcus Webb",
            "timestamp": "2026-06-03T00:00:00Z", "content": "renewal risk flagged", "source": "csm_note",
        }
    ]
