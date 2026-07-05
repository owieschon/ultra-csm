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
from ultra_csm.data_plane.narrative_content.pinehill_content import BODIES as _BODIES
from ultra_csm.data_plane.narrative_shared import cases_as_of, derive_snippet, rfc3339 as _rfc3339

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

_MESSAGE_SCHEDULE: tuple[tuple[int, int, bool, str], ...] = (
    (1, 9, False, "Kickoff — legacy dispatch integration timeline"),
    (1, 14, True, "Re: Kickoff — legacy dispatch integration timeline"),
    (8, 9, False, "Checking in ahead of the 50% activation milestone"),
    (8, 15, True, "Re: Checking in ahead of the 50% activation milestone"),
    (22, 9, False, "Legacy dispatch integration — timeout errors"),
    (23, 15, True, "Re: Legacy dispatch integration — timeout errors"),
    (32, 9, False, "Following up — integration timeout case still open"),
    (34, 11, True, "Re: Following up — integration timeout case still open"),
    # Universe v2 WS-Safety extension (bible-first, adversarial-content
    # corpus, not a narrative beat): Dennis forwards a vendor-spam email
    # containing an injected instruction to an AI assistant. See
    # docs/SYNTHETIC_UNIVERSE_BIBLE.md's Safety appendix.
    (41, 10, True, "Fwd: URGENT — FleetOps account review required"),
    (60, 9, False, "Third integration issue this month — can we get time this week?"),
    (63, 15, True, "Re: Third integration issue this month — can we get time this week?"),
    (85, 9, False, "Dispatch connector still dropping events — need to escalate"),
    (87, 21, True, "Re: Dispatch connector still dropping events — need to escalate"),
    # Density D2.3 (Program 19): benign recap/FYI filler in the day51-219
    # safe zone (outside every checkpoint's trailing latency/ticket
    # windows -- see docs/PROGRAM_REPORT_19.md's derivation).
    (100, 9, False, "Check-in — connector stability update"),
    (100, 15, True, "Re: Check-in — connector stability update"),
    (130, 9, False, "FYI — ack-timeout fix holding steady"),
    (130, 14, True, "Re: FYI — ack-timeout fix holding steady"),
    (160, 9, False, "Checking in ahead of next sync"),
    (160, 13, True, "Re: Checking in ahead of next sync"),
    (190, 9, False, "Quick note — connector steady heading into year-end"),
    (190, 12, True, "Re: Quick note — connector steady heading into year-end"),
    (205, 9, False, "Recap — this week's sync"),
    (205, 14, True, "Re: Recap — this week's sync"),
    (275, 9, False, "Quarterly check-in — integration holding steady"),
    (275, 15, True, "Re: Quarterly check-in — integration holding steady"),
    (295, 9, False, "Steady-state review prep"),
    (295, 14, True, "Re: Steady-state review prep"),
    (305, 9, False, "Great news — integration fully stable"),
    (306, 12, True, "Re: Great news — integration fully stable"),
)


def pinehill_email_thread(as_of_day: int) -> dict:
    """Gmail ``users.threads.get`` shape for the Pinehill/Dennis Gruber thread,
    truncated to messages sent on or before *as_of_day*."""

    thread_id = det_id("email-thread", PINEHILL_ACCOUNT_ID, "legacy-dispatch-integration")
    messages = []
    for day_offset, hour, from_champion, subject in _MESSAGE_SCHEDULE:
        if day_offset > as_of_day:
            break
        sender = _CHAMPION_EMAIL if from_champion else _CSM_EMAIL
        recipient = _CSM_EMAIL if from_champion else _CHAMPION_EMAIL
        msg_id = det_id("email-msg", PINEHILL_ACCOUNT_ID, day_offset, hour)
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


def pinehill_communication_signals(
    as_of_day: int, thread: dict | None = None
) -> list[CommunicationSignal]:
    """Adapt the raw Gmail-shaped thread into ``CommunicationSignal`` rows,
    one per champion reply, with ``response_time_hours`` computed from the
    preceding outbound message. This is the reply-latency-trend raw input.

    ``thread`` defaults to the fixture (``pinehill_email_thread``); passing
    a live-read Gmail thread of the same shape (see
    ``live_gmail_reader.live_email_thread``) drives this exact extraction
    logic from real mailbox data instead, with zero duplication.
    """

    thread = thread if thread is not None else pinehill_email_thread(as_of_day)
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
