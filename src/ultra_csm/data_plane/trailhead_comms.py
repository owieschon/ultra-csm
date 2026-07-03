"""Email and calendar fixtures for the healthy-control arc — Trailhead
Logistics.

Companion to :mod:`ultra_csm.data_plane.comms_fixtures` (Pinehill) and its
other arc-specific siblings: this module is the email/calendar causal
exhaust for the "6. Healthy-control" arc in
docs/SYNTHETIC_UNIVERSE_BIBLE.md. Trailhead is the exemplary-adoption
baseline every other arc's briefing is judged against, so unlike the other
arcs there is no stall, no narrowing, no latency stretch to script here —
just a calm, steady, multi-threaded cadence that should read as
unambiguously fine at every checkpoint (day 60, 180, 300 — deliberately
off-beat from the account's mild scripted day 100-150 summer usage dip, see
the bible).

Same two-layer shape as comms_fixtures.py:

* Raw wire shape -- ``trailhead_email_thread()`` / ``trailhead_calendar_events()``
  return dicts shaped exactly like the Gmail ``users.threads.get`` and
  Google Calendar ``events.list`` responses.
* Normalized contract shape -- ``trailhead_communication_signals()`` /
  ``trailhead_stakeholder_relationships()`` adapt the raw wire shape into
  the existing :class:`~ultra_csm.data_plane.contracts.CommunicationSignal`
  and :class:`~ultra_csm.data_plane.contracts.StakeholderRelationship`
  contracts.

All content is fictional; the account domain is ``*.example``.
"""

from __future__ import annotations

from datetime import datetime

from ultra_csm.data_plane.contracts import CommunicationSignal, CRMCase, StakeholderRelationship
from ultra_csm.data_plane.fixtures import account_id_for, det_id
from ultra_csm.data_plane.narrative_shared import cases_as_of, rfc3339 as _rfc3339

TRAILHEAD_ACCOUNT_ID = account_id_for("trailhead-logistics")
TRAILHEAD_CHAMPION_CONTACT_ID = det_id(
    "contact", TRAILHEAD_ACCOUNT_ID, "vanessa.torres@trailhead-logistics.example"
)
TRAILHEAD_SECONDARY_CONTACT_ID = det_id(
    "contact", TRAILHEAD_ACCOUNT_ID, "mike.lindgren@trailhead-logistics.example"
)
_CSM_EMAIL = "csm101@fleetops-platform.example"
_CHAMPION_EMAIL = "vanessa.torres@trailhead-logistics.example"
_SECONDARY_EMAIL = "mike.lindgren@trailhead-logistics.example"


# ---------------------------------------------------------------------------
# Message schedule: (day_offset, hour, from_champion, from_secondary,
# subject, body_snippet)
#
# Calm periodic check-ins, prompt replies throughout (a few hours, never
# stretching) -- both Vanessa (VP Operations, champion) and Mike (Fleet
# Director) show up on the thread, giving genuine multi-threaded width
# without ever looking like drama. No escalation language, no open
# questions left hanging.
# ---------------------------------------------------------------------------

_MESSAGE_SCHEDULE: tuple[tuple[int, int, bool, bool, str, str], ...] = (
    (10, 9, False, False, "Quarterly check-in — Q3 planning",
     "Hope things are going well, wanted to grab time for our regular check-in."),
    (10, 13, True, False, "Re: Quarterly check-in — Q3 planning",
     "Works for us, adoption's been steady on our end, see you at the sync."),
    (45, 9, False, False, "Compliance reporting — any feedback on the new template?",
     "Curious how the new compliance report template is landing with your team."),
    (45, 12, True, False, "Re: Compliance reporting — any feedback on the new template?",
     "Team likes it, saved us real time on the monthly filing, thanks for shipping it."),
    (55, 10, False, False, "Ahead of next week's sync",
     "Sending a quick agenda for next week's sync, nothing pressing on our side."),
    (55, 13, False, True, "Re: Ahead of next week's sync",
     "Agenda looks good, I'll cover the fleet-side usage numbers."),
    (95, 9, False, False, "Case study — quote check",
     "Circulating the draft case study quote for sign-off before we publish."),
    (95, 11, True, False, "Re: Case study — quote check",
     "Quote looks great, approved to publish as-is."),
    (140, 9, False, False, "Mid-year usage recap",
     "Sharing the mid-year usage recap ahead of our sync — nothing unusual, seasonal dip as expected."),
    (140, 13, True, False, "Re: Mid-year usage recap",
     "Matches what we're seeing, expect it to pick back up after peak season."),
    (175, 9, False, False, "Ahead of the quarterly business review",
     "Sending the QBR deck ahead of Thursday, let me know if you want anything added."),
    (175, 12, True, False, "Re: Ahead of the quarterly business review",
     "Deck looks thorough, nothing to add, see you Thursday."),
    (175, 15, False, True, "Re: Ahead of the quarterly business review",
     "Adding one fleet-utilization slide on my end, will send over tonight."),
    (210, 9, False, False, "Webhook rollout — how's it working for your team?",
     "Checking in on the new asset-alert webhook now that it's live."),
    (210, 12, True, False, "Re: Webhook rollout — how's it working for your team?",
     "Working great, exactly what the fleet team asked for."),
    (250, 9, False, False, "Year-end planning check-in",
     "Starting to think about year-end planning, want to sync on priorities for next year."),
    (250, 13, True, False, "Re: Year-end planning check-in",
     "Happy to sync, we're in good shape and excited to keep expanding usage."),
    (285, 9, False, False, "Ahead of the year-end review",
     "Sending the year-end review agenda, looking forward to it."),
    (285, 13, False, True, "Re: Ahead of the year-end review",
     "Agenda's good, I'll bring the year-end fleet metrics."),
    (295, 9, False, False, "Great year — thank you",
     "Wanted to say thanks for another strong year, usage numbers look great heading into next quarter."),
    (295, 12, True, False, "Re: Great year — thank you",
     "Likewise, this has been a smooth partnership all year, appreciate the support."),
)


def trailhead_email_thread(as_of_day: int) -> dict:
    """Gmail ``users.threads.get`` shape for the Trailhead/CSM thread,
    truncated to messages sent on or before *as_of_day*."""

    thread_id = det_id("email-thread", TRAILHEAD_ACCOUNT_ID, "quarterly-check-ins")
    messages = []
    for day_offset, hour, from_champion, from_secondary, subject, snippet in _MESSAGE_SCHEDULE:
        if day_offset > as_of_day:
            break
        if from_champion:
            sender = _CHAMPION_EMAIL
        elif from_secondary:
            sender = _SECONDARY_EMAIL
        else:
            sender = _CSM_EMAIL
        recipient = _CSM_EMAIL if (from_champion or from_secondary) else _CHAMPION_EMAIL
        msg_id = det_id("email-msg", TRAILHEAD_ACCOUNT_ID, day_offset, hour)
        messages.append(
            {
                "id": msg_id,
                "threadId": thread_id,
                "labelIds": ["INBOX"] if (from_champion or from_secondary) else ["SENT"],
                "snippet": snippet,
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
                    "body": {"data": snippet},
                },
            }
        )
    return {"id": thread_id, "historyId": str(1000 + as_of_day), "messages": messages}


def trailhead_communication_signals(as_of_day: int) -> list[CommunicationSignal]:
    """Adapt the raw Gmail-shaped thread into ``CommunicationSignal`` rows,
    one per inbound reply (Vanessa or Mike), with ``response_time_hours``
    computed from the preceding outbound message. Latencies stay in the
    few-hours range throughout -- no stretch, matching the "boringly fine"
    control."""

    thread = trailhead_email_thread(as_of_day)
    signals: list[CommunicationSignal] = []
    prev_outbound_at: datetime | None = None
    for msg in thread["messages"]:
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        sent_at = datetime.fromisoformat(headers["Date"].replace("Z", "+00:00"))
        sender = headers["From"]
        if sender == _CSM_EMAIL:
            prev_outbound_at = sent_at
            signals.append(
                CommunicationSignal(
                    signal_id=det_id("comm-signal", TRAILHEAD_ACCOUNT_ID, msg["id"]),
                    account_id=TRAILHEAD_ACCOUNT_ID,
                    contact_id=TRAILHEAD_CHAMPION_CONTACT_ID,
                    channel="email",
                    direction="outbound",
                    timestamp=headers["Date"],
                )
            )
            continue
        contact_id = (
            TRAILHEAD_CHAMPION_CONTACT_ID if sender == _CHAMPION_EMAIL else TRAILHEAD_SECONDARY_CONTACT_ID
        )
        response_time_hours = None
        if prev_outbound_at is not None:
            response_time_hours = round((sent_at - prev_outbound_at).total_seconds() / 3600.0, 1)
        signals.append(
            CommunicationSignal(
                signal_id=det_id("comm-signal", TRAILHEAD_ACCOUNT_ID, msg["id"]),
                account_id=TRAILHEAD_ACCOUNT_ID,
                contact_id=contact_id,
                channel="email",
                direction="inbound",
                timestamp=headers["Date"],
                response_time_hours=response_time_hours,
            )
        )
    return signals


def trailhead_stakeholder_relationships(as_of_day: int) -> list[StakeholderRelationship]:
    """Two active relationships throughout -- Vanessa (champion) and Mike
    (secondary) -- genuine multi-threaded width for an exemplary account,
    both ``strength="strong"``."""

    thread = trailhead_email_thread(as_of_day)
    last_champion_inbound: str | None = None
    last_secondary_inbound: str | None = None
    for msg in thread["messages"]:
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        if headers["From"] == _CHAMPION_EMAIL:
            last_champion_inbound = headers["Date"]
        elif headers["From"] == _SECONDARY_EMAIL:
            last_secondary_inbound = headers["Date"]

    relationships: list[StakeholderRelationship] = []
    if last_champion_inbound is not None:
        relationships.append(
            StakeholderRelationship(
                account_id=TRAILHEAD_ACCOUNT_ID,
                contact_id=TRAILHEAD_CHAMPION_CONTACT_ID,
                relationship_type="champion",
                strength="strong",
                last_interaction=last_champion_inbound,
                multi_thread_depth=2,
            )
        )
    if last_secondary_inbound is not None:
        relationships.append(
            StakeholderRelationship(
                account_id=TRAILHEAD_ACCOUNT_ID,
                contact_id=TRAILHEAD_SECONDARY_CONTACT_ID,
                relationship_type="stakeholder",
                strength="strong",
                last_interaction=last_secondary_inbound,
                multi_thread_depth=2,
            )
        )
    return relationships


# ---------------------------------------------------------------------------
# Calendar: steady biweekly-ish cadence throughout, all events confirmed --
# no cancellations, no cadence drift, matching the "boringly fine" control.
# ---------------------------------------------------------------------------

_CALENDAR_SCHEDULE: tuple[int, ...] = (
    10, 24, 38, 52, 66, 80, 94, 108, 122, 136, 150, 164, 178, 192, 206, 220,
    234, 248, 262, 276, 290, 304, 318,
)


def trailhead_calendar_events(as_of_day: int) -> dict:
    """Google Calendar ``events.list`` shape for the Trailhead/CSM sync,
    truncated to events scheduled on or before *as_of_day*. All events are
    ``confirmed`` -- no cancellations at any point in this arc."""

    items = []
    for day_offset in _CALENDAR_SCHEDULE:
        if day_offset > as_of_day:
            break
        event_id = det_id("calendar-event", TRAILHEAD_ACCOUNT_ID, day_offset)
        start = _rfc3339(day_offset, 10)
        end = _rfc3339(day_offset, 10, minute=30)
        items.append(
            {
                "id": event_id,
                "summary": "Trailhead Logistics <> CSM Sync",
                "start": {"dateTime": start},
                "end": {"dateTime": end},
                "attendees": [
                    {"email": _CSM_EMAIL, "responseStatus": "accepted"},
                    {"email": _CHAMPION_EMAIL, "responseStatus": "accepted"},
                    {"email": _SECONDARY_EMAIL, "responseStatus": "accepted"},
                ],
                "recurrence": ["RRULE:FREQ=WEEKLY;INTERVAL=2"],
                "status": "confirmed",
            }
        )
    return {"items": items}


# ---------------------------------------------------------------------------
# CRMCase adapter -- see narrative_shared.cases_as_of for why this reuses
# the existing ``_CASE_SCHEDULE`` timeline instead of authoring a second,
# competing case schedule.
# ---------------------------------------------------------------------------


def trailhead_cases_as_of(as_of_day: int) -> list[CRMCase]:
    """Trailhead's rare, low-priority feature-request cases (day 0/120,
    ``_CASE_SCHEDULE`` in data_simulator.py), as ``CRMCase`` rows visible as
    of *as_of_day*. Both resolve cleanly well within a few weeks and never
    contradict the "healthy" read."""

    return cases_as_of(TRAILHEAD_ACCOUNT_ID, as_of_day)
