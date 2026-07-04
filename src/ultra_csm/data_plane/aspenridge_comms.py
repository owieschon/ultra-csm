"""Email and calendar fixtures for the silent-decline (green-but-quiet) arc,
`aspenridge-supply` -- see docs/SYNTHETIC_UNIVERSE_BIBLE.md, arc 4.

This account's risk is *not* a communications story: usage is genuinely,
slowly declining (`UsageDecline("aspenridge-supply", 90, ...)` in
book_simulator.py, calibrated to stay under the engine's 20%
auto-health-adjustment threshold so the health band never moves off green),
but the CSM relationship itself stays completely normal throughout --
quarterly business reviews on schedule, prompt champion replies, one steady
contact. The point of this module is to be boring: every fixture here should
make the extractor read calm/unremarkable, so the only place this account's
risk is visible is the usage/adoption telemetry that already exists
elsewhere (`AdoptionSummary` / `UsageSignal`), not here.

Same two-layer shape as `comms_fixtures.py` (Pinehill's onboarding-stall
module, the template this mirrors):

* Raw wire shape -- ``aspenridge_email_thread()`` /
  ``aspenridge_calendar_events()`` return dicts shaped like the Gmail
  ``users.threads.get`` and Google Calendar ``events.list`` responses.
* Normalized contract shape -- ``aspenridge_communication_signals()`` /
  ``aspenridge_stakeholder_relationships()`` adapt the raw wire shape into
  the existing ``CommunicationSignal`` / ``StakeholderRelationship``
  contracts.

All content is fictional; the account domain is ``*.example``.
"""

from __future__ import annotations

from datetime import datetime

from ultra_csm.data_plane.contracts import CommunicationSignal, CRMCase, StakeholderRelationship
from ultra_csm.data_plane.fixtures import account_id_for, det_id
from ultra_csm.data_plane.narrative_content.aspenridge_content import BODIES as _BODIES
from ultra_csm.data_plane.narrative_shared import cases_as_of, derive_snippet, rfc3339 as _rfc3339

ASPENRIDGE_ACCOUNT_ID = account_id_for("aspenridge-supply")
ASPENRIDGE_CHAMPION_CONTACT_ID = det_id(
    "contact", ASPENRIDGE_ACCOUNT_ID, "christine.yoder@aspenridge-sc.example"
)
_CSM_EMAIL = "csm102@fleetops-platform.example"
_CHAMPION_EMAIL = "christine.yoder@aspenridge-sc.example"


# ---------------------------------------------------------------------------
# Message schedule: (day_offset, hour, from_champion, subject, body_snippet)
#
# Calm quarterly-cadence check-ins paired with each QBR (day ~1, ~91, ~181,
# ~271, ~361). Every reply lands same-day, a few hours after the CSM's
# message -- reply latency never stretches, unlike Pinehill's stall. One
# thread, one contact throughout: this account doesn't need width to read
# as fine, it just needs to stay calm.
# ---------------------------------------------------------------------------

_MESSAGE_SCHEDULE: tuple[tuple[int, int, bool, str], ...] = (
    (1, 9, False, "Q1 business review — agenda attached"),
    (1, 13, True, "Re: Q1 business review — agenda attached"),
    (91, 9, False, "Q2 business review — agenda attached"),
    (91, 12, True, "Re: Q2 business review — agenda attached"),
    (181, 9, False, "Q3 business review — agenda attached"),
    (181, 14, True, "Re: Q3 business review — agenda attached"),
    (271, 9, False, "Q4 business review — agenda attached"),
    (271, 11, True, "Re: Q4 business review — agenda attached"),
    (361, 9, False, "Year-end check-in — agenda attached"),
    (361, 15, True, "Re: Year-end check-in — agenda attached"),
)


def aspenridge_email_thread(as_of_day: int) -> dict:
    """Gmail ``users.threads.get`` shape for the Aspenridge/Christine Yoder
    thread, truncated to messages sent on or before *as_of_day*."""

    thread_id = det_id("email-thread", ASPENRIDGE_ACCOUNT_ID, "quarterly-check-in")
    messages = []
    for day_offset, hour, from_champion, subject in _MESSAGE_SCHEDULE:
        if day_offset > as_of_day:
            break
        sender = _CHAMPION_EMAIL if from_champion else _CSM_EMAIL
        recipient = _CSM_EMAIL if from_champion else _CHAMPION_EMAIL
        msg_id = det_id("email-msg", ASPENRIDGE_ACCOUNT_ID, day_offset, hour)
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


def aspenridge_communication_signals(
    as_of_day: int, thread: dict | None = None
) -> list[CommunicationSignal]:
    """Adapt the raw Gmail-shaped thread into ``CommunicationSignal`` rows,
    one per champion reply, with ``response_time_hours`` computed from the
    preceding outbound message. Reply latency here should stay flat and
    low (a few hours) at every checkpoint -- this is the "nothing wrong
    with the relationship" half of the arc.

    ``thread`` defaults to the fixture; pass a live-read Gmail thread of
    the same shape (``live_gmail_reader.live_email_thread``) to drive this
    same extraction from real mailbox data."""

    thread = thread if thread is not None else aspenridge_email_thread(as_of_day)
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
                    signal_id=det_id("comm-signal", ASPENRIDGE_ACCOUNT_ID, msg["id"]),
                    account_id=ASPENRIDGE_ACCOUNT_ID,
                    contact_id=ASPENRIDGE_CHAMPION_CONTACT_ID,
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
                signal_id=det_id("comm-signal", ASPENRIDGE_ACCOUNT_ID, msg["id"]),
                account_id=ASPENRIDGE_ACCOUNT_ID,
                contact_id=ASPENRIDGE_CHAMPION_CONTACT_ID,
                channel="email",
                direction="inbound",
                timestamp=headers["Date"],
                response_time_hours=response_time_hours,
            )
        )
    return signals


def aspenridge_stakeholder_relationships(as_of_day: int) -> list[StakeholderRelationship]:
    """One champion relationship throughout, ``strength="strong"`` the whole
    way -- nothing wrong with the relationship graph in this arc; the risk
    is purely in product usage, which lives in `UsageSignal`/
    `AdoptionSummary`, not here."""

    thread = aspenridge_email_thread(as_of_day)
    last_inbound = None
    for msg in thread["messages"]:
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        if headers["From"] == _CHAMPION_EMAIL:
            last_inbound = headers["Date"]
    if last_inbound is None:
        return []
    return [
        StakeholderRelationship(
            account_id=ASPENRIDGE_ACCOUNT_ID,
            contact_id=ASPENRIDGE_CHAMPION_CONTACT_ID,
            relationship_type="champion",
            strength="strong",
            last_interaction=last_inbound,
            multi_thread_depth=1,
        )
    ]


# ---------------------------------------------------------------------------
# Calendar: quarterly business review cadence, roughly every ~90 days,
# every event confirmed -- no cancellations, no widening. Contrast Pinehill
# (weekly -> biweekly stretch) and Pinnacle (single-threaded-risk gaps):
# this account's cadence never moves.
# ---------------------------------------------------------------------------

_CALENDAR_SCHEDULE: tuple[tuple[int, str], ...] = (
    (1, "confirmed"),
    (91, "confirmed"),
    (181, "confirmed"),
    (271, "confirmed"),
    (361, "confirmed"),
)


def aspenridge_calendar_events(as_of_day: int) -> dict:
    """Google Calendar ``events.list`` shape for the Aspenridge/CSM
    quarterly business review, truncated to events scheduled on or before
    *as_of_day*."""

    items = []
    for day_offset, status in _CALENDAR_SCHEDULE:
        if day_offset > as_of_day:
            break
        event_id = det_id("calendar-event", ASPENRIDGE_ACCOUNT_ID, day_offset)
        start = _rfc3339(day_offset, 10)
        end = _rfc3339(day_offset, 10, minute=30)
        items.append(
            {
                "id": event_id,
                "summary": "Aspenridge Supply Chain <> CSM Quarterly Business Review",
                "start": {"dateTime": start},
                "end": {"dateTime": end},
                "attendees": [
                    {"email": _CSM_EMAIL, "responseStatus": "accepted"},
                    {"email": _CHAMPION_EMAIL, "responseStatus": "accepted"},
                ],
                "recurrence": ["RRULE:FREQ=MONTHLY;INTERVAL=3"],
                "status": status,
            }
        )
    return {"items": items}


# ---------------------------------------------------------------------------
# CRMCase adapter -- see narrative_shared.cases_as_of. Aspenridge has no
# entries in `_CASE_SCHEDULE`, so this correctly returns an empty list at
# every checkpoint: zero cases is itself part of the "nothing looks wrong"
# story, not a gap in this module.
# ---------------------------------------------------------------------------


def aspenridge_cases_as_of(as_of_day: int) -> list[CRMCase]:
    """Aspenridge has no scripted cases -- zero CTAs is part of the arc's
    point (a briefing that only reads CRM/CTA state will call this account
    fine)."""

    return cases_as_of(ASPENRIDGE_ACCOUNT_ID, as_of_day)
