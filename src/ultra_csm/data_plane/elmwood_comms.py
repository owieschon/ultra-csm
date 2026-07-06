"""Elmwood Trucking -- routine health check-in, day-offset aware.

Elmwood is a mid-touch, steady_state account with a single scored factor
(``health_yellow``, no case/milestone/success-plan signal of any kind) --
not one of docs/SYNTHETIC_UNIVERSE_BIBLE.md's six arcs, red herrings, 27
boring controls, tier-mirror/proof accounts, or 25-account cohort-truth
set (verified absent from all of those before authoring this file, per
dispatch 28's Phase 2 re-ground note). Content here is proportionate to
the account's actual data: a short, benign check-in exchange
acknowledging the yellow health band, not a dramatic arc.

Companion to pinnacle_comms.py/comms_fixtures.py (same CommunicationSignal
construction pattern, smaller schedule).
"""

from __future__ import annotations

from datetime import datetime

from ultra_csm.data_plane.contracts import CommunicationSignal
from ultra_csm.data_plane.fixtures import account_id_for, det_id
from ultra_csm.data_plane.narrative_content.elmwood_content import BODIES as _BODIES
from ultra_csm.data_plane.narrative_shared import derive_snippet, rfc3339 as _rfc3339

ELMWOOD_ACCOUNT_ID = account_id_for("elmwood-trucking")
_CSM_EMAIL = "csm102@fleetops-platform.example"
_SAM_EMAIL = "sam.foster@elmwood-trucking.example"
SAM_CONTACT_ID = det_id("contact", ELMWOOD_ACCOUNT_ID, _SAM_EMAIL)

# (day_offset, hour, from_contact, subject)
_MESSAGE_SCHEDULE: tuple[tuple[int, int, bool, str], ...] = (
    (67, 9, False, "Checking in on Elmwood's account health"),
    (68, 13, True, "Re: Checking in on Elmwood's account health"),
)


def elmwood_email_thread(as_of_day: int) -> dict:
    """Gmail ``users.threads.get`` shape, one thread, truncated to *as_of_day*."""

    thread_id = det_id("email-thread", ELMWOOD_ACCOUNT_ID, "sam")
    messages = []
    for day_offset, hour, from_contact, subject in _MESSAGE_SCHEDULE:
        if day_offset > as_of_day:
            break
        sender = _SAM_EMAIL if from_contact else _CSM_EMAIL
        recipient = _CSM_EMAIL if from_contact else _SAM_EMAIL
        msg_id = det_id("email-msg", ELMWOOD_ACCOUNT_ID, day_offset, hour)
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


def elmwood_communication_signals(
    as_of_day: int, threads: list[dict] | None = None
) -> list[CommunicationSignal]:
    """Adapt the raw thread into ``CommunicationSignal`` rows, with reply
    latency computed from the prior outbound message."""

    signals: list[CommunicationSignal] = []
    threads = threads if threads is not None else elmwood_email_thread(as_of_day)["threads"]
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
                        signal_id=det_id("comm-signal", ELMWOOD_ACCOUNT_ID, msg["id"]),
                        account_id=ELMWOOD_ACCOUNT_ID,
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
                    signal_id=det_id("comm-signal", ELMWOOD_ACCOUNT_ID, msg["id"]),
                    account_id=ELMWOOD_ACCOUNT_ID,
                    contact_id=SAM_CONTACT_ID,
                    channel="email",
                    direction="inbound",
                    timestamp=headers["Date"],
                    response_time_hours=response_time_hours,
                )
            )
    return signals
