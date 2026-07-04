"""Email and calendar fixtures for the expansion-ready arc (Meridian Fleet
Group), in real connector API shape, day-offset aware.

Companion to ``comms_fixtures.py`` (Pinehill) and its narrative siblings --
see docs/SYNTHETIC_UNIVERSE_BIBLE.md section 5. This is the multi-threaded
growth story: Alicia Fernandez (VP Fleet Ops, established champion from day
1) and Sarah Chen (Facilities Manager, a new department stakeholder who
appears day 10 via the scripted ``NewContactAppears`` event in
book_simulator.py) both engage with increasing cadence in the run-up to the
day-180 ARR expansion ($28M -> $36M), continuing strong through the day-270
year-end usage uptick.

Same two-layer shape as comms_fixtures.py:

* Raw wire shape -- ``meridian_email_thread()`` / ``meridian_calendar_events()``
  return dicts shaped like the Gmail ``users.threads.get`` and Google
  Calendar ``events.list`` responses.
* Normalized contract shape -- ``meridian_communication_signals()`` /
  ``meridian_stakeholder_relationships()`` adapt the raw wire shape into the
  existing :class:`~ultra_csm.data_plane.contracts.CommunicationSignal` and
  :class:`~ultra_csm.data_plane.contracts.StakeholderRelationship` contracts.

All content is fictional; contact/CSM email domains are ``*.example``.
"""

from __future__ import annotations

from datetime import datetime

from ultra_csm.data_plane.contracts import CommunicationSignal, CRMCase, StakeholderRelationship
from ultra_csm.data_plane.fixtures import account_id_for, det_id
from ultra_csm.data_plane.narrative_shared import cases_as_of, rfc3339 as _rfc3339

MERIDIAN_ACCOUNT_ID = account_id_for("meridian-fleet")
MERIDIAN_ALICIA_CONTACT_ID = det_id(
    "contact", MERIDIAN_ACCOUNT_ID, "alicia.fernandez@meridian-fleet.example"
)
MERIDIAN_SARAH_CONTACT_ID = det_id(
    "contact", MERIDIAN_ACCOUNT_ID, "sarah.chen@meridian-fleet.example"
)
_CSM_EMAIL = "csm101@fleetops-platform.example"
_ALICIA_EMAIL = "alicia.fernandez@meridian-fleet.example"
_SARAH_EMAIL = "sarah.chen@meridian-fleet.example"

_ALICIA_THREAD_KEY = "fleet-ops-expansion"
_SARAH_THREAD_KEY = "facilities-onboarding"


# ---------------------------------------------------------------------------
# Message schedule: (day_offset, hour, contact_email, from_contact, subject,
# body_snippet). Two logical threads (Alicia's fleet-ops thread runs the
# whole simulation; Sarah's facilities thread starts day 10 once she
# appears). Both threads tighten in cadence and reply speed as day 180
# approaches, and stay active through the day-270 year-end uptick.
# ---------------------------------------------------------------------------

_ALICIA_MESSAGE_SCHEDULE: tuple[tuple[int, int, bool, str, str], ...] = (
    (2, 9, False, "Kickoff — fleet ops rollout",
     "Excited to get the telematics rollout underway across your fleet."),
    (2, 14, True, "Re: Kickoff — fleet ops rollout",
     "Great, our dispatch team is ready whenever you are."),
    (18, 9, False, "Usage check-in — adoption trending up",
     "Adoption numbers are looking strong this month, wanted to flag it."),
    (19, 11, True, "Re: Usage check-in — adoption trending up",
     "Yep, our drivers have taken to it faster than expected."),
    (45, 9, False, "Route optimization — early results",
     "Early route optimization numbers are in, worth a look before next sync."),
    (45, 16, True, "Re: Route optimization — early results",
     "These are great, sharing with the regional managers."),
    (75, 9, False, "Expansion conversation — facilities interest",
     "Heard facilities is interested in the platform too, happy to loop in."),
    (75, 13, True, "Re: Expansion conversation — facilities interest",
     "Yes, I've already connected Sarah Chen with your team."),
    (100, 9, False, "Q3 planning — fleet ops usage trajectory",
     "Usage trajectory looks strong heading into Q3, let's talk expansion scope."),
    (100, 12, True, "Re: Q3 planning — fleet ops usage trajectory",
     "Agreed, let's put expansion on the agenda for our next sync."),
    (130, 9, False, "Expansion scoping — draft terms",
     "Sending over draft terms for the fleet ops + facilities expansion."),
    (130, 11, True, "Re: Expansion scoping — draft terms",
     "Reviewed, this looks right, routing to finance for sign-off."),
    (150, 9, False, "Expansion — finance sign-off timeline",
     "Checking in on finance sign-off timeline ahead of the close."),
    (150, 10, True, "Re: Expansion — finance sign-off timeline",
     "On track, expect sign-off this week."),
    (165, 9, False, "Expansion — final review before close",
     "Final review doc attached ahead of closing the expansion."),
    (165, 10, True, "Re: Expansion — final review before close",
     "Approved on our end, ready to close."),
    (178, 9, False, "Expansion — closing this week",
     "Everything's set to close the expansion this week, thank you for driving this."),
    (178, 10, True, "Re: Expansion — closing this week",
     "Thrilled to expand the partnership, talk soon."),
    (185, 9, False, "Expansion closed — next steps",
     "Expansion is officially closed, sending over the rollout plan for the new scope."),
    (185, 11, True, "Re: Expansion closed — next steps",
     "Fantastic, let's get the new modules rolled out quickly."),
    (220, 9, False, "Expanded scope — rollout progress",
     "Rollout on the expanded scope is going smoothly, adoption climbing fast."),
    (220, 13, True, "Re: Expanded scope — rollout progress",
     "Great to hear, drivers are picking it up quickly."),
    (272, 9, False, "Year-end push — usage climbing again",
     "Seeing another usage climb heading into year-end, great trajectory."),
    (272, 12, True, "Re: Year-end push — usage climbing again",
     "Yes, we're leaning in hard before year-end close."),
    (285, 9, False, "Year-end review prep",
     "Sending the year-end review agenda, usage trend looks excellent."),
    (285, 10, True, "Re: Year-end review prep",
     "Looks good, see you at the review."),
)

_SARAH_MESSAGE_SCHEDULE: tuple[tuple[int, int, bool, str, str], ...] = (
    (10, 9, False, "Welcome — facilities onboarding",
     "Welcome aboard, looking forward to getting facilities set up on the platform."),
    (10, 15, True, "Re: Welcome — facilities onboarding",
     "Thanks, excited to get started, when can we schedule training?"),
    (17, 9, False, "Facilities onboarding — training scheduled",
     "Training is scheduled for this week, sending the agenda now."),
    (17, 12, True, "Re: Facilities onboarding — training scheduled",
     "Perfect, my team is ready."),
    (40, 9, False, "Facilities usage — first month results",
     "First month of facilities usage data is in, adoption is strong."),
    (40, 14, True, "Re: Facilities usage — first month results",
     "Great to see, our maintenance team loves the alerts."),
    (70, 9, False, "Facilities — expansion interest",
     "Wanted to check whether facilities would want to formalize the expanded scope."),
    (70, 11, True, "Re: Facilities — expansion interest",
     "Yes, very interested, let's get budget approval moving."),
    (95, 9, False, "Facilities — budget approval check-in",
     "Checking in on budget approval for the facilities expansion."),
    (95, 13, True, "Re: Facilities — budget approval check-in",
     "Approved on our side, coordinating with Alicia's team on terms."),
    (125, 9, False, "Facilities — expansion scope alignment",
     "Aligning facilities scope with the broader fleet ops expansion terms."),
    (125, 10, True, "Re: Facilities — expansion scope alignment",
     "Looks aligned, ready to sign off with fleet ops."),
    (155, 9, False, "Facilities — pre-close readiness",
     "Getting facilities ready for the expansion close next month."),
    (155, 11, True, "Re: Facilities — pre-close readiness",
     "All set, my team is ready to onboard the new modules."),
    (168, 9, False, "Facilities — expansion close next week",
     "Expansion closes next week, sending final facilities rollout plan."),
    (168, 10, True, "Re: Facilities — expansion close next week",
     "Reviewed, looks great, excited to get going."),
    (182, 9, False, "Facilities expansion closed — rollout kickoff",
     "Facilities expansion is closed, kicking off the new module rollout."),
    (182, 12, True, "Re: Facilities expansion closed — rollout kickoff",
     "Team is ready, let's get started this week."),
    (225, 9, False, "Facilities — expanded module adoption",
     "Adoption on the new facilities modules is climbing quickly."),
    (225, 14, True, "Re: Facilities — expanded module adoption",
     "Yes, maintenance alerts have cut response time significantly."),
    (274, 9, False, "Facilities — year-end usage climbing",
     "Facilities usage is climbing again heading into year-end, strong trend."),
    (274, 11, True, "Re: Facilities — year-end usage climbing",
     "Agreed, we're pushing hard to close out the year strong."),
    (288, 9, False, "Facilities — year-end review prep",
     "Sending the facilities year-end review agenda ahead of next week."),
    (288, 13, True, "Re: Facilities — year-end review prep",
     "Looks good, see you then."),
)


def _thread_id(key: str) -> str:
    return det_id("email-thread", MERIDIAN_ACCOUNT_ID, key)


def _build_messages(
    schedule: tuple[tuple[int, int, bool, str, str], ...],
    contact_email: str,
    thread_id: str,
    as_of_day: int,
) -> list[dict]:
    messages = []
    for day_offset, hour, from_contact, subject, snippet in schedule:
        if day_offset > as_of_day:
            break
        sender = contact_email if from_contact else _CSM_EMAIL
        recipient = _CSM_EMAIL if from_contact else contact_email
        msg_id = det_id("email-msg", MERIDIAN_ACCOUNT_ID, thread_id, day_offset, hour)
        messages.append(
            {
                "id": msg_id,
                "threadId": thread_id,
                "labelIds": ["INBOX"] if from_contact else ["SENT"],
                "snippet": snippet,
                "internalDate": str(
                    int(
                        datetime.fromisoformat(
                            _rfc3339(day_offset, hour).replace("Z", "+00:00")
                        ).timestamp()
                        * 1000
                    )
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
    return messages


def meridian_email_thread(as_of_day: int) -> dict:
    """Gmail-shaped threads for both Meridian contacts, truncated to
    messages sent on or before *as_of_day*. Returns both the Alicia
    fleet-ops thread (active from day 1) and the Sarah facilities thread
    (active from day 10, once she appears) as a single ``threads`` list
    keyed by thread id -- mirrors ``users.threads.list`` shape, since this
    account has more than one active thread."""

    alicia_thread_id = _thread_id(_ALICIA_THREAD_KEY)
    sarah_thread_id = _thread_id(_SARAH_THREAD_KEY)
    threads = [
        {
            "id": alicia_thread_id,
            "historyId": str(1000 + as_of_day),
            "messages": _build_messages(
                _ALICIA_MESSAGE_SCHEDULE, _ALICIA_EMAIL, alicia_thread_id, as_of_day
            ),
        },
        {
            "id": sarah_thread_id,
            "historyId": str(2000 + as_of_day),
            "messages": _build_messages(
                _SARAH_MESSAGE_SCHEDULE, _SARAH_EMAIL, sarah_thread_id, as_of_day
            ),
        },
    ]
    return {"threads": threads}


def meridian_communication_signals(
    as_of_day: int, threads: list[dict] | None = None
) -> list[CommunicationSignal]:
    """Adapt both raw Gmail-shaped threads into ``CommunicationSignal``
    rows, one per contact reply, with ``response_time_hours`` computed from
    the preceding outbound message -- per thread, since Alicia's and
    Sarah's reply-latency histories are independent.

    ``threads`` defaults to the fixture's ``["threads"]`` list (Alicia's
    thread first, then Sarah's); pass a live-read equivalent
    (``live_gmail_reader.live_email_thread``, one call per contact) in the
    same order to drive this same extraction from real mailbox data."""

    signals: list[CommunicationSignal] = []
    threads = threads if threads is not None else meridian_email_thread(as_of_day)["threads"]
    for thread, contact_email, contact_id in (
        (threads[0], _ALICIA_EMAIL, MERIDIAN_ALICIA_CONTACT_ID),
        (threads[1], _SARAH_EMAIL, MERIDIAN_SARAH_CONTACT_ID),
    ):
        prev_outbound_at: datetime | None = None
        for msg in thread["messages"]:
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            sent_at = datetime.fromisoformat(headers["Date"].replace("Z", "+00:00"))
            from_contact = headers["From"] == contact_email
            if not from_contact:
                prev_outbound_at = sent_at
                signals.append(
                    CommunicationSignal(
                        signal_id=det_id("comm-signal", MERIDIAN_ACCOUNT_ID, msg["id"]),
                        account_id=MERIDIAN_ACCOUNT_ID,
                        contact_id=contact_id,
                        channel="email",
                        direction="outbound",
                        timestamp=headers["Date"],
                    )
                )
                continue
            response_time_hours = None
            if prev_outbound_at is not None:
                response_time_hours = round(
                    (sent_at - prev_outbound_at).total_seconds() / 3600.0, 1
                )
            signals.append(
                CommunicationSignal(
                    signal_id=det_id("comm-signal", MERIDIAN_ACCOUNT_ID, msg["id"]),
                    account_id=MERIDIAN_ACCOUNT_ID,
                    contact_id=contact_id,
                    channel="email",
                    direction="inbound",
                    timestamp=headers["Date"],
                    response_time_hours=response_time_hours,
                )
            )
    return signals


def meridian_stakeholder_relationships(as_of_day: int) -> list[StakeholderRelationship]:
    """Width reads as 1 before Sarah appears (day 10), 2 from day 10
    onward -- both ``strength="strong"`` by day 170/280, reflecting the
    multi-threaded growth story."""

    threads = meridian_email_thread(as_of_day)["threads"]
    relationships: list[StakeholderRelationship] = []
    for thread, contact_id, relationship_type in (
        (threads[0], MERIDIAN_ALICIA_CONTACT_ID, "champion"),
        (threads[1], MERIDIAN_SARAH_CONTACT_ID, "champion"),
    ):
        last_inbound = None
        contact_email = _ALICIA_EMAIL if contact_id == MERIDIAN_ALICIA_CONTACT_ID else _SARAH_EMAIL
        for msg in thread["messages"]:
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            if headers["From"] == contact_email:
                last_inbound = headers["Date"]
        if last_inbound is None:
            continue
        relationships.append(
            StakeholderRelationship(
                account_id=MERIDIAN_ACCOUNT_ID,
                contact_id=contact_id,
                relationship_type=relationship_type,
                strength="strong",
                last_interaction=last_inbound,
                multi_thread_depth=2 if contact_id == MERIDIAN_SARAH_CONTACT_ID else 1,
            )
        )
    return relationships


# ---------------------------------------------------------------------------
# Calendar: weekly sync cadence for both contacts that tightens to 2x/week
# as day 180 approaches, holding through the day-270 year-end uptick.
# ---------------------------------------------------------------------------

_ALICIA_CALENDAR_SCHEDULE: tuple[int, ...] = (
    3, 10, 17, 24, 31, 38, 45, 52, 59, 66, 73, 80, 87, 94, 101, 108, 115, 122, 129,
    # cadence tightens to 2x/week from ~day 135 through the day-180 close
    136, 140, 143, 147, 150, 154, 157, 161, 164, 168, 171, 175, 178,
    # holds 2x/week through the post-close rollout and year-end uptick
    182, 185, 189, 192, 196, 199, 220, 227, 234, 241, 248, 255, 262, 269,
    272, 276, 279, 283, 286, 290,
)

_SARAH_CALENDAR_SCHEDULE: tuple[int, ...] = (
    # weekly starting shortly after she appears day 10
    12, 19, 26, 33, 40, 47, 54, 61, 68, 75, 82, 89, 96, 103, 110, 117, 124, 131,
    # 2x/week from ~day 137 through the day-180 close
    137, 141, 144, 148, 151, 155, 158, 162, 165, 169, 172, 176, 179,
    # holds 2x/week through rollout and year-end uptick
    183, 186, 190, 193, 197, 200, 221, 228, 235, 242, 249, 256, 263, 270,
    273, 277, 280, 284, 287, 291,
)


def _calendar_items(
    schedule: tuple[int, ...],
    contact_email: str,
    summary: str,
    key: str,
    as_of_day: int,
) -> list[dict]:
    items = []
    for day_offset in schedule:
        if day_offset > as_of_day:
            break
        event_id = det_id("calendar-event", MERIDIAN_ACCOUNT_ID, key, day_offset)
        start = _rfc3339(day_offset, 10)
        end = _rfc3339(day_offset, 10, minute=30)
        items.append(
            {
                "id": event_id,
                "summary": summary,
                "start": {"dateTime": start},
                "end": {"dateTime": end},
                "attendees": [
                    {"email": _CSM_EMAIL, "responseStatus": "accepted"},
                    {"email": contact_email, "responseStatus": "accepted"},
                ],
                "recurrence": ["RRULE:FREQ=WEEKLY"],
                "status": "confirmed",
            }
        )
    return items


def meridian_calendar_events(as_of_day: int) -> dict:
    """Google Calendar ``events.list`` shape covering both the Alicia
    fleet-ops sync (from day 3) and the Sarah facilities sync (from day
    12, shortly after she appears), truncated to *as_of_day*. Merged into
    one ``items`` list, sorted by start time, since ``meeting_cadence_shift``
    reads cadence across the whole account regardless of attendee."""

    items = _calendar_items(
        _ALICIA_CALENDAR_SCHEDULE, _ALICIA_EMAIL, "Meridian Fleet Ops <> CSM Sync",
        "fleet-ops-sync", as_of_day,
    ) + _calendar_items(
        _SARAH_CALENDAR_SCHEDULE, _SARAH_EMAIL, "Meridian Facilities <> CSM Sync",
        "facilities-sync", as_of_day,
    )
    items.sort(key=lambda item: item["start"]["dateTime"])
    return {"items": items}


# ---------------------------------------------------------------------------
# CRMCase adapter -- see narrative_shared.cases_as_of for why this reuses
# the existing ``_CASE_SCHEDULE`` timeline instead of authoring a second,
# competing case schedule.
# ---------------------------------------------------------------------------


def meridian_cases_as_of(as_of_day: int) -> list[CRMCase]:
    """Meridian's cases (``_CASE_SCHEDULE`` in data_simulator.py), as
    ``CRMCase`` rows visible as of *as_of_day*."""

    return cases_as_of(MERIDIAN_ACCOUNT_ID, as_of_day)
