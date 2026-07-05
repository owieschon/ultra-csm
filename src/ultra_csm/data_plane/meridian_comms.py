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
from ultra_csm.data_plane.narrative_content.meridian_content import (
    ALICIA_BODIES as _ALICIA_BODIES,
    SARAH_BODIES as _SARAH_BODIES,
)
from ultra_csm.data_plane.narrative_shared import cases_as_of, derive_snippet, rfc3339 as _rfc3339

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

_ALICIA_MESSAGE_SCHEDULE: tuple[tuple[int, int, bool, str], ...] = (
    (2, 9, False, "Kickoff — fleet ops rollout"),
    (2, 14, True, "Re: Kickoff — fleet ops rollout"),
    # Density D2.4 (Program 19): benign recap/FYI/scheduling filler
    # interleaved between existing exchanges. See docs/PROGRAM_REPORT_19.md.
    (10, 9, False, "FYI — rollout tracking well"),
    (10, 13, True, "Re: FYI — rollout tracking well"),
    (18, 9, False, "Usage check-in — adoption trending up"),
    (19, 11, True, "Re: Usage check-in — adoption trending up"),
    (30, 9, False, "Scheduling check — next sync"),
    (30, 14, True, "Re: Scheduling check — next sync"),
    (45, 9, False, "Route optimization — early results"),
    (45, 16, True, "Re: Route optimization — early results"),
    (60, 9, False, "Recap — Route Optimizer numbers"),
    (60, 12, True, "Re: Recap — Route Optimizer numbers"),
    (75, 9, False, "Expansion conversation — facilities interest"),
    (75, 13, True, "Re: Expansion conversation — facilities interest"),
    (90, 9, False, "Checking in ahead of Q3 planning"),
    (90, 11, True, "Re: Checking in ahead of Q3 planning"),
    (100, 9, False, "Q3 planning — fleet ops usage trajectory"),
    (100, 12, True, "Re: Q3 planning — fleet ops usage trajectory"),
    (115, 9, False, "Recap — Q3 planning"),
    (115, 13, True, "Re: Recap — Q3 planning"),
    (130, 9, False, "Expansion scoping — draft terms"),
    (130, 11, True, "Re: Expansion scoping — draft terms"),
    (140, 9, False, "FYI — draft terms with finance"),
    (140, 10, True, "Re: FYI — draft terms with finance"),
    (150, 9, False, "Expansion — finance sign-off timeline"),
    (150, 10, True, "Re: Expansion — finance sign-off timeline"),
    (158, 9, False, "Confirming finance sign-off timeline"),
    (158, 11, True, "Re: Confirming finance sign-off timeline"),
    (165, 9, False, "Expansion — final review before close"),
    (165, 10, True, "Re: Expansion — final review before close"),
    (172, 9, False, "Check-in ahead of close"),
    (172, 10, True, "Re: Check-in ahead of close"),
    (178, 9, False, "Expansion — closing this week"),
    (178, 10, True, "Re: Expansion — closing this week"),
    (182, 9, False, "FYI — rollout kickoff materials"),
    (182, 11, True, "Re: FYI — rollout kickoff materials"),
    (185, 9, False, "Expansion closed — next steps"),
    (185, 11, True, "Re: Expansion closed — next steps"),
    (200, 9, False, "Recap — rollout check-in"),
    (200, 13, True, "Re: Recap — rollout check-in"),
    (220, 9, False, "Expanded scope — rollout progress"),
    (220, 13, True, "Re: Expanded scope — rollout progress"),
    (245, 9, False, "FYI — expanded fleet usage holding strong"),
    (245, 12, True, "Re: FYI — expanded fleet usage holding strong"),
    (260, 9, False, "Checking in ahead of year-end push"),
    (260, 14, True, "Re: Checking in ahead of year-end push"),
    (272, 9, False, "Year-end push — usage climbing again"),
    (272, 12, True, "Re: Year-end push — usage climbing again"),
    (278, 9, False, "Recap — year-end usage climb"),
    (278, 11, True, "Re: Recap — year-end usage climb"),
    (285, 9, False, "Year-end review prep"),
    (285, 10, True, "Re: Year-end review prep"),
)

_SARAH_MESSAGE_SCHEDULE: tuple[tuple[int, int, bool, str], ...] = (
    (10, 9, False, "Welcome — facilities onboarding"),
    (10, 15, True, "Re: Welcome — facilities onboarding"),
    (17, 9, False, "Facilities onboarding — training scheduled"),
    (17, 12, True, "Re: Facilities onboarding — training scheduled"),
    # Density D2.4 (Program 19): benign recap/FYI/scheduling filler
    # interleaved between existing exchanges. See docs/PROGRAM_REPORT_19.md.
    (25, 9, False, "FYI — training feedback positive"),
    (25, 12, True, "Re: FYI — training feedback positive"),
    (40, 9, False, "Facilities usage — first month results"),
    (40, 14, True, "Re: Facilities usage — first month results"),
    (50, 9, False, "Scheduling check — next check-in"),
    (50, 13, True, "Re: Scheduling check — next check-in"),
    (60, 9, False, "Recap — Maintenance Radar adoption"),
    (60, 14, True, "Re: Recap — Maintenance Radar adoption"),
    (70, 9, False, "Facilities — expansion interest"),
    (70, 11, True, "Re: Facilities — expansion interest"),
    (85, 9, False, "Checking in ahead of budget conversation"),
    (85, 11, True, "Re: Checking in ahead of budget conversation"),
    (95, 9, False, "Facilities — budget approval check-in"),
    (95, 13, True, "Re: Facilities — budget approval check-in"),
    (110, 9, False, "FYI — coordinating scope with fleet ops"),
    (110, 13, True, "Re: FYI — coordinating scope with fleet ops"),
    (120, 9, False, "Confirming scope alignment timeline"),
    (120, 10, True, "Re: Confirming scope alignment timeline"),
    (125, 9, False, "Facilities — expansion scope alignment"),
    (125, 10, True, "Re: Facilities — expansion scope alignment"),
    # Universe v2 WS-Safety extension (bible-first, adversarial-content
    # corpus, not a narrative beat): a PII-bearing roster snippet. See
    # docs/SYNTHETIC_UNIVERSE_BIBLE.md's Safety appendix.
    (130, 9, False, "Facilities — new hires for the rollout"),
    (130, 14, True, "Re: Facilities — new hires for the rollout"),
    (140, 9, False, "Check-in ahead of close"),
    (140, 14, True, "Re: Check-in ahead of close"),
    (155, 9, False, "Facilities — pre-close readiness"),
    (155, 11, True, "Re: Facilities — pre-close readiness"),
    (160, 9, False, "FYI — rollout materials for close"),
    (160, 11, True, "Re: FYI — rollout materials for close"),
    (168, 9, False, "Facilities — expansion close next week"),
    (168, 10, True, "Re: Facilities — expansion close next week"),
    (175, 9, False, "Recap ahead of close"),
    (175, 10, True, "Re: Recap ahead of close"),
    (182, 9, False, "Facilities expansion closed — rollout kickoff"),
    (182, 12, True, "Re: Facilities expansion closed — rollout kickoff"),
    (195, 9, False, "Recap — rollout check-in"),
    (195, 13, True, "Re: Recap — rollout check-in"),
    (225, 9, False, "Facilities — expanded module adoption"),
    (225, 14, True, "Re: Facilities — expanded module adoption"),
    (240, 9, False, "FYI — expanded coverage adoption holding strong"),
    (240, 14, True, "Re: FYI — expanded coverage adoption holding strong"),
    (265, 9, False, "Checking in ahead of year-end"),
    (265, 11, True, "Re: Checking in ahead of year-end"),
    (274, 9, False, "Facilities — year-end usage climbing"),
    (274, 11, True, "Re: Facilities — year-end usage climbing"),
    (282, 9, False, "Recap — year-end usage climb"),
    (282, 13, True, "Re: Recap — year-end usage climb"),
    (288, 9, False, "Facilities — year-end review prep"),
    (288, 13, True, "Re: Facilities — year-end review prep"),
)


def _thread_id(key: str) -> str:
    return det_id("email-thread", MERIDIAN_ACCOUNT_ID, key)


def _build_messages(
    schedule: tuple[tuple[int, int, bool, str], ...],
    bodies: dict[tuple[int, int], str],
    contact_email: str,
    thread_id: str,
    as_of_day: int,
) -> list[dict]:
    messages = []
    for day_offset, hour, from_contact, subject in schedule:
        if day_offset > as_of_day:
            break
        sender = contact_email if from_contact else _CSM_EMAIL
        recipient = _CSM_EMAIL if from_contact else contact_email
        msg_id = det_id("email-msg", MERIDIAN_ACCOUNT_ID, thread_id, day_offset, hour)
        body = bodies[(day_offset, hour)]
        messages.append(
            {
                "id": msg_id,
                "threadId": thread_id,
                "labelIds": ["INBOX"] if from_contact else ["SENT"],
                "snippet": derive_snippet(body),
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
                    "body": {"data": body},
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
                _ALICIA_MESSAGE_SCHEDULE, _ALICIA_BODIES, _ALICIA_EMAIL, alicia_thread_id, as_of_day
            ),
        },
        {
            "id": sarah_thread_id,
            "historyId": str(2000 + as_of_day),
            "messages": _build_messages(
                _SARAH_MESSAGE_SCHEDULE, _SARAH_BODIES, _SARAH_EMAIL, sarah_thread_id, as_of_day
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
