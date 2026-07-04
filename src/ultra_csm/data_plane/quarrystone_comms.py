"""Email and calendar fixtures in real connector API shape, day-offset aware.

Companion to :mod:`ultra_csm.data_plane.comms_fixtures` (Pinehill): this
module is the email/calendar half of the causal exhaust for the
churn-brewing arc in docs/SYNTHETIC_UNIVERSE_BIBLE.md (section 3,
``quarrystone-logistics``).

Unlike Pinehill (a latency story) or Pinnacle (a thread-width-recovers
story), Quarrystone's "brewing" signal is entirely **absence**: the sole
contact, Tim Kowalczyk, has already gone quiet by day 0
(``ChampionGoesQuiet("quarrystone-logistics", 0)`` in book_simulator.py's
``SCENARIO_TIMELINE``), no replacement contact ever surfaces, and no
calendar event is ever scheduled after day 0. The account is ``red`` from
day 0 through the day-220 churn -- there is no health-band arc to hang
artifacts on, only the absence of activity a still-open, still-flagged
account should have.

Two layers, mirroring comms_fixtures.py:

* Raw wire shape -- ``quarrystone_email_thread()`` /
  ``quarrystone_calendar_events()`` return dicts shaped exactly like the
  Gmail ``users.threads.get`` and Google Calendar ``events.list``
  responses.
* Normalized contract shape -- ``quarrystone_communication_signals()`` /
  ``quarrystone_stakeholder_relationships()`` adapt the raw wire shape into
  the existing :class:`~ultra_csm.data_plane.contracts.CommunicationSignal`
  and :class:`~ultra_csm.data_plane.contracts.StakeholderRelationship`
  contracts -- no new evidence contract invented.

All content is fictional; the account domain is ``*.example``.
"""

from __future__ import annotations

from datetime import datetime

from ultra_csm.data_plane.contracts import CommunicationSignal, CRMCase, StakeholderRelationship
from ultra_csm.data_plane.fixtures import account_id_for, det_id
from ultra_csm.data_plane.narrative_content.quarrystone_content import BODIES as _BODIES
from ultra_csm.data_plane.narrative_shared import cases_as_of, derive_snippet, rfc3339 as _rfc3339

QUARRYSTONE_ACCOUNT_ID = account_id_for("quarrystone-logistics")
QUARRYSTONE_CHAMPION_CONTACT_ID = det_id(
    "contact", QUARRYSTONE_ACCOUNT_ID, "tim.kowalczyk@quarrystone.example"
)
_CSM_EMAIL = "csm104@fleetops-platform.example"
_CHAMPION_EMAIL = "tim.kowalczyk@quarrystone.example"


# ---------------------------------------------------------------------------
# Message schedule: (day_offset, hour, from_champion, subject, body_snippet)
#
# A single handoff exchange right at day 0 -- the last live contact from Tim
# Kowalczyk before he goes quiet (``ChampionGoesQuiet`` fires at day 0 in
# the spine). Nothing after: no reply-latency stretch to script, because
# there is no further reply at all. This is the contrast with Pinehill
# (latency stretch) and Pinnacle (thread narrows then widens again) -- here
# the thread simply stops.
# ---------------------------------------------------------------------------

_MESSAGE_SCHEDULE: tuple[tuple[int, int, bool, str], ...] = (
    (0, 9, False, "Admin access transfer — please confirm new point of contact"),
    (0, 16, True, "Re: Admin access transfer — please confirm new point of contact"),
)


def quarrystone_email_thread(as_of_day: int) -> dict:
    """Gmail ``users.threads.get`` shape for the Quarrystone/Tim Kowalczyk
    thread, truncated to messages sent on or before *as_of_day*. The
    schedule ends at day 0 -- there is nothing to truncate past that."""

    thread_id = det_id("email-thread", QUARRYSTONE_ACCOUNT_ID, "admin-access-transfer")
    messages = []
    for day_offset, hour, from_champion, subject in _MESSAGE_SCHEDULE:
        if day_offset > as_of_day:
            break
        sender = _CHAMPION_EMAIL if from_champion else _CSM_EMAIL
        recipient = _CSM_EMAIL if from_champion else _CHAMPION_EMAIL
        msg_id = det_id("email-msg", QUARRYSTONE_ACCOUNT_ID, day_offset, hour)
        body = _BODIES[(day_offset, hour)]
        messages.append(
            {
                "id": msg_id,
                "threadId": thread_id,
                "labelIds": ["INBOX"] if from_champion else ["SENT"],
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
    return {"id": thread_id, "historyId": str(1000 + as_of_day), "messages": messages}


def quarrystone_communication_signals(
    as_of_day: int, thread: dict | None = None
) -> list[CommunicationSignal]:
    """Adapt the raw Gmail-shaped thread into ``CommunicationSignal`` rows.
    At most two rows ever exist (the day-0 handoff exchange) -- this is the
    flat, near-zero raw input behind the low ``thread_participation_width``
    reading at every checkpoint.

    ``thread`` defaults to the fixture; pass a live-read Gmail thread of
    the same shape (``live_gmail_reader.live_email_thread``) to drive this
    same extraction from real mailbox data."""

    thread = thread if thread is not None else quarrystone_email_thread(as_of_day)
    signals: list[CommunicationSignal] = []
    prev_outbound_at: datetime | None = None
    for msg in thread["messages"]:
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        sent_at = datetime.fromisoformat(headers["Date"].replace("Z", "+00:00"))
        from_champion = headers["From"] == _CHAMPION_EMAIL
        if not from_champion:
            prev_outbound_at = sent_at
            signals.append(
                CommunicationSignal(
                    signal_id=det_id("comm-signal", QUARRYSTONE_ACCOUNT_ID, msg["id"]),
                    account_id=QUARRYSTONE_ACCOUNT_ID,
                    contact_id=QUARRYSTONE_CHAMPION_CONTACT_ID,
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
                signal_id=det_id("comm-signal", QUARRYSTONE_ACCOUNT_ID, msg["id"]),
                account_id=QUARRYSTONE_ACCOUNT_ID,
                contact_id=QUARRYSTONE_CHAMPION_CONTACT_ID,
                channel="email",
                direction="inbound",
                timestamp=headers["Date"],
                response_time_hours=response_time_hours,
            )
        )
    return signals


def quarrystone_stakeholder_relationships(as_of_day: int) -> list[StakeholderRelationship]:
    """Tim Kowalczyk's relationship row, frozen at his last real reply
    (day 0). He is a real prior contact, not a nonexistent one -- the arc's
    signal is that this single row never updates and no second row ever
    appears (contrast Pinnacle's arc, where a replacement contact does
    surface). ``strength`` is downgraded to ``weak`` from day 0 onward
    since the relationship has already gone stale by the time any
    checkpoint reads it."""

    thread = quarrystone_email_thread(as_of_day)
    last_inbound = None
    for msg in thread["messages"]:
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        if headers["From"] == _CHAMPION_EMAIL:
            last_inbound = headers["Date"]
    if last_inbound is None:
        return []
    return [
        StakeholderRelationship(
            account_id=QUARRYSTONE_ACCOUNT_ID,
            contact_id=QUARRYSTONE_CHAMPION_CONTACT_ID,
            relationship_type="champion",
            strength="weak",
            last_interaction=last_inbound,
            multi_thread_depth=1,
        )
    ]


# ---------------------------------------------------------------------------
# Calendar: no recurring sync ever existed for this account, and no event
# is ever scheduled after day 0 -- the "brewing" signal is the total
# absence of calendar activity through the day-220 churn, not a cadence
# that stretches (contrast Pinehill's weekly-to-biweekly drift).
# ---------------------------------------------------------------------------

_CALENDAR_SCHEDULE: tuple[tuple[int, str], ...] = (
    (0, "confirmed"),
)


def quarrystone_calendar_events(as_of_day: int) -> dict:
    """Google Calendar ``events.list`` shape for the single Quarrystone
    handoff meeting at day 0, truncated to events scheduled on or before
    *as_of_day*. No event is ever scheduled past day 0."""

    items = []
    for day_offset, status in _CALENDAR_SCHEDULE:
        if day_offset > as_of_day:
            break
        event_id = det_id("calendar-event", QUARRYSTONE_ACCOUNT_ID, day_offset)
        start = _rfc3339(day_offset, 10)
        end = _rfc3339(day_offset, 10, minute=30)
        items.append(
            {
                "id": event_id,
                "summary": "Quarrystone Logistics <> CSM Handoff",
                "start": {"dateTime": start},
                "end": {"dateTime": end},
                "attendees": [
                    {"email": _CSM_EMAIL, "responseStatus": "accepted"},
                    {
                        "email": _CHAMPION_EMAIL,
                        "responseStatus": "accepted" if status == "confirmed" else "declined",
                    },
                ],
                "recurrence": [],
                "status": status,
            }
        )
    return {"items": items}


# ---------------------------------------------------------------------------
# CRMCase adapter -- see narrative_shared.cases_as_of for why this reuses
# the existing ``_CASE_SCHEDULE`` timeline instead of authoring a second,
# competing case schedule.
# ---------------------------------------------------------------------------


def quarrystone_cases_as_of(as_of_day: int) -> list[CRMCase]:
    """Quarrystone's cases (``_CASE_SCHEDULE`` in data_simulator.py), as
    ``CRMCase`` rows visible as of *as_of_day*. As of this writing only the
    day-0 "Need to transfer admin access to new contact" case is scripted
    there; the bible's day-160 "Renewal terms discussion — no response"
    case is not yet present in ``_CASE_SCHEDULE`` (out of scope for this
    module -- that file is not authored here)."""

    return cases_as_of(QUARRYSTONE_ACCOUNT_ID, as_of_day)
