"""Cobalt Fleet Ops -- routine health check-in, day-offset aware.

Cobalt is a high-touch, steady_state account with a single scored factor
(``health_yellow``, no case/milestone/success-plan signal of any kind) --
not one of docs/SYNTHETIC_UNIVERSE_BIBLE.md's six arcs, red herrings,
27 boring controls, tier-mirror/proof accounts, or 25-account cohort-truth
set (verified absent from all of those before authoring this file, per
dispatch 28's Phase 2 re-ground note -- seeding a calibrated account would
risk corrupting the assertion it exists for). Content here is proportionate
to the account's actual data: a short, benign check-in exchange
acknowledging the yellow health band, not a dramatic arc -- matching the
bible's own register for this class of account ("2-4 short, boring, benign
message exchanges").

Companion to pinnacle_comms.py/comms_fixtures.py (same CommunicationSignal
construction pattern, smaller schedule).
"""

from __future__ import annotations

from datetime import datetime

from ultra_csm.data_plane.contracts import CommunicationSignal
from ultra_csm.data_plane.fixtures import account_id_for, det_id
from ultra_csm.data_plane.narrative_content.cobalt_content import BODIES as _BODIES
from ultra_csm.data_plane.narrative_shared import derive_snippet, rfc3339 as _rfc3339

COBALT_ACCOUNT_ID = account_id_for("cobalt-fleet-ops")
_CSM_EMAIL = "csm104@fleetops-platform.example"
_SAM_EMAIL = "sam.turner@cobalt-fleet-ops.example"
SAM_CONTACT_ID = det_id("contact", COBALT_ACCOUNT_ID, _SAM_EMAIL)

# (day_offset, hour, from_contact, subject)
_MESSAGE_SCHEDULE: tuple[tuple[int, int, bool, str], ...] = (
    (60, 9, False, "Quick check-in -- how's Cobalt finding things lately"),
    (61, 14, True, "Re: Quick check-in -- how's Cobalt finding things lately"),
    (62, 10, False, "Re: Quick check-in -- how's Cobalt finding things lately"),
)


def cobalt_email_thread(as_of_day: int) -> dict:
    """Gmail ``users.threads.get`` shape, one thread, truncated to *as_of_day*."""

    thread_id = det_id("email-thread", COBALT_ACCOUNT_ID, "sam")
    messages = []
    for day_offset, hour, from_contact, subject in _MESSAGE_SCHEDULE:
        if day_offset > as_of_day:
            break
        sender = _SAM_EMAIL if from_contact else _CSM_EMAIL
        recipient = _CSM_EMAIL if from_contact else _SAM_EMAIL
        msg_id = det_id("email-msg", COBALT_ACCOUNT_ID, day_offset, hour)
        body = _BODIES[(day_offset, hour)]
        messages.append(
            {
                "id": msg_id,
                "threadId": thread_id,
                "labelIds": ["INBOX"] if from_contact else ["SENT"],
                "snippet": derive_snippet(body),
                "internalDate": str(
                    int(datetime.fromisoformat(_rfc3339(day_offset, hour).replace("Z", "+00:00")).timestamp() * 1000)
                ),
                "payload": {
                    "headers": [
                        {"name": "From", "value": sender},
                        {"name": "To", "value": recipient},
                        {"name": "Date", "value": _rfc3339(day_offset, hour)},
                        {"name": "Subject", "value": subject},
                    ],
                    "body": {"data": body},
                },
            }
        )
    return {"threads": [{"id": thread_id, "historyId": str(1000 + as_of_day), "messages": messages}]}


def cobalt_communication_signals(
    as_of_day: int, threads: list[dict] | None = None
) -> list[CommunicationSignal]:
    """Adapt the raw thread into ``CommunicationSignal`` rows, with reply
    latency computed from the prior outbound message."""

    signals: list[CommunicationSignal] = []
    threads = threads if threads is not None else cobalt_email_thread(as_of_day)["threads"]
    for thread in threads:
        prev_outbound_at = None
        for msg in thread["messages"]:
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            sent_at = datetime.fromisoformat(headers["Date"].replace("Z", "+00:00"))
            from_contact = headers["From"] == _SAM_EMAIL
            if not from_contact:
                prev_outbound_at = sent_at
                signals.append(
                    CommunicationSignal(
                        signal_id=det_id("comm-signal", COBALT_ACCOUNT_ID, msg["id"]),
                        account_id=COBALT_ACCOUNT_ID,
                        contact_id=SAM_CONTACT_ID,
                        channel="email",
                        direction="outbound",
                        timestamp=headers["Date"],
                    )
                )
                continue
            response_time_hours = None
            if prev_outbound_at is not None:
                response_time_hours = round((sent_at - prev_outbound_at).total_seconds() / 3600.0, 1)
            signals.append(
                CommunicationSignal(
                    signal_id=det_id("comm-signal", COBALT_ACCOUNT_ID, msg["id"]),
                    account_id=COBALT_ACCOUNT_ID,
                    contact_id=SAM_CONTACT_ID,
                    channel="email",
                    direction="inbound",
                    timestamp=headers["Date"],
                    response_time_hours=response_time_hours,
                )
            )
    return signals
