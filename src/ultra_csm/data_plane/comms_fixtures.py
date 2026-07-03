"""Email and calendar fixtures in real connector API shape, day-offset aware.

Companion to :mod:`ultra_csm.data_plane.rocketlane_fixtures`'s narrative
section: this module is the email/calendar half of the causal exhaust for
the story arcs in docs/SYNTHETIC_UNIVERSE_BIBLE.md, starting with the
onboarding-stall pilot (Pinehill Transport).

Two layers, mirroring how a real connector works:

* Raw wire shape -- ``pinehill_email_thread()`` / ``pinehill_calendar_events()``
  return dicts shaped exactly like the Gmail ``users.threads.get`` and
  Google Calendar ``events.list`` responses (``payload.headers``,
  ``attendees``, ``recurrence``, ``status``). These are what a live
  connector would hand back.
* Normalized contract shape -- ``pinehill_communication_signals()`` /
  ``pinehill_stakeholder_relationships()`` adapt the raw wire shape into the
  existing (currently unused, "reserved for live connector integration")
  :class:`~ultra_csm.data_plane.contracts.CommunicationSignal` and
  :class:`~ultra_csm.data_plane.contracts.StakeholderRelationship` contracts
  -- no new evidence contract invented.

All content is fictional; the account domain is ``*.example`` per
docs/LIVE_INTEGRATION_FINDINGS.md-adjacent hygiene conventions.
"""

from __future__ import annotations

from datetime import datetime

from ultra_csm.data_plane.contracts import CommunicationSignal, CRMCase, StakeholderRelationship
from ultra_csm.data_plane.fixtures import account_id_for, det_id
from ultra_csm.data_plane.narrative_shared import cases_as_of, rfc3339 as _rfc3339

PINEHILL_ACCOUNT_ID = account_id_for("pinehill-transport")
PINEHILL_CHAMPION_CONTACT_ID = det_id(
    "contact", PINEHILL_ACCOUNT_ID, "dennis.gruber@pinehill-transport.example"
)
_CSM_EMAIL = "csm102@fleetops-platform.example"
_CHAMPION_EMAIL = "dennis.gruber@pinehill-transport.example"


# ---------------------------------------------------------------------------
# Message schedule: (day_offset, hour, from_champion, subject, body_snippet)
#
# Reply-latency trend (hours between the CSM's message and the champion's
# reply): ~5h, ~6h through day 9 (before) -> stretching to 30h, 50h, 70h,
# 60h across the stall (day 24-88) -> back to ~3h once the connector is
# stable (day 306, after). One thread, one contact throughout -- Pinehill's
# signal is latency stretch, not thread narrowing (contrast Pinnacle's
# single-threaded-risk arc, which is a width story).
# ---------------------------------------------------------------------------

_MESSAGE_SCHEDULE: tuple[tuple[int, int, bool, str, str], ...] = (
    (1, 9, False, "Kickoff — legacy dispatch integration timeline",
     "Looking forward to getting the legacy dispatch connector live this month."),
    (1, 14, True, "Re: Kickoff — legacy dispatch integration timeline",
     "Sounds good, our team is ready to start whenever you are."),
    (8, 9, False, "Checking in ahead of the 50% activation milestone",
     "Quick check-in before Friday's milestone review."),
    (8, 15, True, "Re: Checking in ahead of the 50% activation milestone",
     "All set on our end, talk Friday."),
    (22, 9, False, "Legacy dispatch integration — timeout errors",
     "Seeing timeout errors on the legacy dispatch connector, need your IT team's help."),
    (23, 15, True, "Re: Legacy dispatch integration — timeout errors",
     "Will loop in IT, bit swamped this week, give us a few days."),
    (32, 9, False, "Following up — integration timeout case still open",
     "Following up on the timeout case, any movement from IT?"),
    (34, 11, True, "Re: Following up — integration timeout case still open",
     "Sorry for the delay, IT is still looking into it."),
    (60, 9, False, "Third integration issue this month — can we get time this week?",
     "This is the third dispatch connector issue this month, can we find 30 minutes?"),
    (63, 15, True, "Re: Third integration issue this month — can we get time this week?",
     "Apologies, been heads down on our end, let's find time next week."),
    (85, 9, False, "Dispatch connector still dropping events — need to escalate",
     "The connector is still dropping events, we should escalate this internally."),
    (87, 21, True, "Re: Dispatch connector still dropping events — need to escalate",
     "Understood, escalating on our side too."),
    (275, 9, False, "Quarterly check-in — integration holding steady",
     "Wanted to check in now that things have settled down on the connector."),
    (275, 15, True, "Re: Quarterly check-in — integration holding steady",
     "Yes, quiet on our end too, appreciate the follow-through."),
    (295, 9, False, "Steady-state review prep",
     "Sending over the steady-state review agenda for next week."),
    (295, 14, True, "Re: Steady-state review prep",
     "Looks good, see you then."),
    (305, 9, False, "Great news — integration fully stable",
     "Wanted to flag that the legacy dispatch integration has been fully stable for two weeks."),
    (306, 12, True, "Re: Great news — integration fully stable",
     "Fantastic, thank you for sticking with this one."),
)


def pinehill_email_thread(as_of_day: int) -> dict:
    """Gmail ``users.threads.get`` shape for the Pinehill/Dennis Gruber thread,
    truncated to messages sent on or before *as_of_day*."""

    thread_id = det_id("email-thread", PINEHILL_ACCOUNT_ID, "legacy-dispatch-integration")
    messages = []
    for day_offset, hour, from_champion, subject, snippet in _MESSAGE_SCHEDULE:
        if day_offset > as_of_day:
            break
        sender = _CHAMPION_EMAIL if from_champion else _CSM_EMAIL
        recipient = _CSM_EMAIL if from_champion else _CHAMPION_EMAIL
        msg_id = det_id("email-msg", PINEHILL_ACCOUNT_ID, day_offset, hour)
        messages.append(
            {
                "id": msg_id,
                "threadId": thread_id,
                "labelIds": ["INBOX"] if from_champion else ["SENT"],
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


def pinehill_communication_signals(as_of_day: int) -> list[CommunicationSignal]:
    """Adapt the raw Gmail-shaped thread into ``CommunicationSignal`` rows,
    one per champion reply, with ``response_time_hours`` computed from the
    preceding outbound message. This is the reply-latency-trend raw input.
    """

    thread = pinehill_email_thread(as_of_day)
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
                    signal_id=det_id("comm-signal", PINEHILL_ACCOUNT_ID, msg["id"]),
                    account_id=PINEHILL_ACCOUNT_ID,
                    contact_id=PINEHILL_CHAMPION_CONTACT_ID,
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
                signal_id=det_id("comm-signal", PINEHILL_ACCOUNT_ID, msg["id"]),
                account_id=PINEHILL_ACCOUNT_ID,
                contact_id=PINEHILL_CHAMPION_CONTACT_ID,
                channel="email",
                direction="inbound",
                timestamp=headers["Date"],
                response_time_hours=response_time_hours,
            )
        )
    return signals


def pinehill_stakeholder_relationships(as_of_day: int) -> list[StakeholderRelationship]:
    """One champion relationship throughout -- width never broadens in this
    arc (the stall is a latency story, not a single-threaded-risk story)."""

    thread = pinehill_email_thread(as_of_day)
    last_inbound = None
    for msg in thread["messages"]:
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        if headers["From"] == _CHAMPION_EMAIL:
            last_inbound = headers["Date"]
    if last_inbound is None:
        return []
    return [
        StakeholderRelationship(
            account_id=PINEHILL_ACCOUNT_ID,
            contact_id=PINEHILL_CHAMPION_CONTACT_ID,
            relationship_type="champion",
            strength="strong",
            last_interaction=last_inbound,
            multi_thread_depth=1,
        )
    ]


# ---------------------------------------------------------------------------
# Calendar: weekly sync cadence that stretches to biweekly across the
# stall and recovers to weekly after the connector stabilizes.
# ---------------------------------------------------------------------------

_CALENDAR_SCHEDULE: tuple[tuple[int, str], ...] = (
    (1, "confirmed"),
    (8, "confirmed"),
    (15, "confirmed"),
    (22, "confirmed"),
    (29, "confirmed"),
    (36, "confirmed"),
    (43, "cancelled"),   # cadence starts slipping once the stall bites
    (57, "confirmed"),   # biweekly through the stall
    (71, "cancelled"),
    (85, "confirmed"),
    (99, "confirmed"),
    (130, "confirmed"),  # monthly cadence through mid-onboarding
    (160, "confirmed"),
    (190, "confirmed"),
    (220, "confirmed"),
    (250, "confirmed"),  # cadence starts tightening toward steady-state
    (270, "confirmed"),
    (289, "confirmed"),  # weekly again, post-recovery (day 300 graduation)
    (296, "confirmed"),
    (303, "confirmed"),
    (310, "confirmed"),
)


def pinehill_calendar_events(as_of_day: int) -> dict:
    """Google Calendar ``events.list`` shape for the Pinehill/CSM sync,
    truncated to events scheduled on or before *as_of_day*."""

    items = []
    for day_offset, status in _CALENDAR_SCHEDULE:
        if day_offset > as_of_day:
            break
        event_id = det_id("calendar-event", PINEHILL_ACCOUNT_ID, day_offset)
        start = _rfc3339(day_offset, 10)
        end = _rfc3339(day_offset, 10, minute=30)
        items.append(
            {
                "id": event_id,
                "summary": "Pinehill Transport <> CSM Sync",
                "start": {"dateTime": start},
                "end": {"dateTime": end},
                "attendees": [
                    {"email": _CSM_EMAIL, "responseStatus": "accepted"},
                    {
                        "email": _CHAMPION_EMAIL,
                        "responseStatus": "accepted" if status == "confirmed" else "declined",
                    },
                ],
                "recurrence": ["RRULE:FREQ=WEEKLY"],
                "status": status,
            }
        )
    return {"items": items}


# ---------------------------------------------------------------------------
# CRMCase adapter -- see narrative_shared.cases_as_of for why this reuses
# the existing ``_CASE_SCHEDULE`` timeline instead of authoring a second,
# competing case schedule.
# ---------------------------------------------------------------------------


def pinehill_cases_as_of(as_of_day: int) -> list[CRMCase]:
    """Pinehill's three legacy-dispatch-integration cases (day 0/30/80,
    ``_CASE_SCHEDULE`` in data_simulator.py), as ``CRMCase`` rows visible as
    of *as_of_day*."""

    return cases_as_of(PINEHILL_ACCOUNT_ID, as_of_day)
