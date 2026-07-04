"""Email/calendar comms fixtures for Fieldstone's two arcs + one herring.

Mirrors ``ultra_csm.data_plane.comms_fixtures``'s pattern (raw connector-
wire-shape layer + a normalized-contract adapter layer) but is
self-contained -- no import from any fleetops-specific module -- since
this tenant's whole point is a DIFFERENT communication culture: ~6-10
sparse email messages per arc across the year (vs. fleetops' 15-20+ for a
single pilot arc), meeting-heavy, quarterly cadence.

Per the bible: "meetings carry the relationship, sparse email is normal."
Reply latency for both arc accounts sits in the same 38-44h band in their
"before" state -- Arc F1 (``masonry-home-services``) never leaves that
band; Arc F2 (``culvert-mechanical``) stretches away from it starting day
90. This is the fixture layer that makes "risk = delta from tenant
baseline" a computable, gradeable fact rather than a rhetorical claim.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ultra_csm.data_plane.contracts import CommunicationSignal, CRMCase, StakeholderRelationship
from ultra_csm.data_plane.tenants.fieldstone.book import (
    ARC_F1_SLUG,
    ARC_F2_SLUG,
    HERRING_SLUG,
    account_id_for,
    det_id,
)

SEED_DATE = "2026-06-21"
_CSM_EMAIL_BY_SLUG = {
    ARC_F1_SLUG: "priya.anand@fieldstone-service.example",
    ARC_F2_SLUG: "priya.anand@fieldstone-service.example",
    HERRING_SLUG: "owen.marsh@fieldstone-service.example",
}
_CHAMPION_EMAIL_BY_SLUG = {
    ARC_F1_SLUG: "renata@masonry-home-services.example",
    ARC_F2_SLUG: "marcus@culvert-mechanical.example",
    HERRING_SLUG: "diane@wrenhouse-hvac.example",
}


def rfc3339(day_offset: int, hour: int = 9, minute: int = 0) -> str:
    dt = datetime(2026, 6, 21, tzinfo=timezone.utc) + timedelta(
        days=day_offset, hours=hour - 9, minutes=minute
    )
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def derive_snippet(body: str, limit: int = 100) -> str:
    first_line = next((line.strip() for line in body.splitlines() if line.strip()), "")
    return first_line if len(first_line) <= limit else first_line[: limit - 1].rstrip() + "…"


# ---------------------------------------------------------------------------
# Arc F1 (masonry-home-services) -- latency FLAT at 38-42h all year, never
# trending. Two exchanges clustered near each checkpoint (day 60/180/300)
# so both the trailing-21d and prior-21d windows have 2 replies each at
# every checkpoint, making the "delta near zero" claim a computed fact
# rather than a coincidence of window placement.
# ---------------------------------------------------------------------------
_F1_SCHEDULE: tuple[tuple[int, int, bool, str], ...] = (
    (10, 9, False, "Welcome to Fieldstone Service Cloud"),
    (11, 23, True, "Re: Welcome to Fieldstone Service Cloud"),  # 38h
    (42, 9, False, "Quick check-in"),
    (43, 23, True, "Re: Quick check-in"),  # 38h
    (58, 9, False, "Quarterly check-in ahead of our call"),
    (59, 23, True, "Re: Quarterly check-in ahead of our call"),  # 38h
    (65, 9, False, "Following up after the call"),
    (66, 22, True, "Re: Following up after the call"),  # 37h
    (150, 9, False, "Mid-year check-in"),
    (151, 23, True, "Re: Mid-year check-in"),  # 38h
    (160, 9, False, "Following up after our Q2 review"),
    (161, 23, True, "Re: Following up after our Q2 review"),  # 38h
    (167, 9, False, "One more follow-up"),
    (168, 22, True, "Re: One more follow-up"),  # 37h
    (245, 9, False, "Ahead of renewal season"),
    (246, 23, True, "Re: Ahead of renewal season"),  # 38h
    (250, 9, False, "Anything we can help with before renewal season"),
    (252, 3, True, "Re: Anything we can help with before renewal season"),  # 42h
    (257, 9, False, "Last check-in before the renewal call"),
    (258, 23, True, "Re: Last check-in before the renewal call"),  # 38h
)

_F1_BODIES = {
    (10, 9): "Hi Renata, welcome aboard -- looking forward to supporting Masonry Home Services.",
    (11, 23): "Thanks! Team's using the scheduler already, all good on our end.",
    (42, 9): "Hi Renata, quick check-in -- anything come up this month?",
    (43, 23): "Nothing at all, all running smoothly.",
    (58, 9): "Hi Renata, checking in ahead of our quarterly call next week -- anything on your mind?",
    (59, 23): "Nothing pressing, things are running smoothly. See you on the call.",
    (65, 9): "Hi Renata, good talking with you -- sending the recap notes over.",
    (66, 22): "Got it, thanks -- all accurate.",
    (150, 9): "Hi Renata, mid-year check-in -- anything we can help with?",
    (151, 23): "All good here, thanks for checking in.",
    (160, 9): "Hi Renata, great talking with you last week. Sending the recap notes over.",
    (161, 23): "Got it, thanks -- all looks accurate.",
    (167, 9): "Hi Renata, one more follow-up on the notes from last time.",
    (168, 22): "All good, nothing to add.",
    (245, 9): "Hi Renata, wanted to get ahead of renewal season -- any questions building up?",
    (246, 23): "None so far, appreciate the heads up.",
    (250, 9): "Hi Renata, wanted to check in before your renewal window opens up -- any questions?",
    (252, 3): "None from us -- happy with how things are going, talk soon.",
    (257, 9): "Hi Renata, one last check-in before our renewal call.",
    (258, 23): "Sounds good, see you then.",
}


# ---------------------------------------------------------------------------
# Arc F2 (culvert-mechanical) -- latency flat ~36-40h through day 89
# (statistically indistinguishable from Masonry's baseline: two replies in
# both the trailing-21d and prior-21d windows at day 80, both ~38h), then
# stretches steadily across days 95-149 so the trailing-21d window at day
# 140 (days 119-140: the 130h/128h replies) reads far above the prior-21d
# window (days 98-119: the 65h/70h replies) -- a real, large DELTA from
# this account's own baseline, not merely "high in absolute terms."
# ---------------------------------------------------------------------------
_F2_SCHEDULE: tuple[tuple[int, int, bool, str], ...] = (
    (12, 9, False, "Welcome to Fieldstone Service Cloud"),
    (13, 21, True, "Re: Welcome to Fieldstone Service Cloud"),  # 36h
    (44, 9, False, "Quick check-in"),
    (45, 23, True, "Re: Quick check-in"),  # 38h
    (58, 9, False, "Quarterly check-in ahead of our call"),
    (59, 23, True, "Re: Quarterly check-in ahead of our call"),  # 38h
    (65, 9, False, "Following up on last week's call"),
    (66, 22, True, "Re: Following up on last week's call"),  # 37h
    (92, 9, False, "Following up on the May invoice question"),
    (95, 14, True, "Re: Following up on the May invoice question"),  # 77h
    (100, 9, False, "Checking in on the invoice dispute"),
    (103, 15, True, "Re: Checking in on the invoice dispute"),  # 78h
    (119, 9, False, "Third follow-up on the billing dispute"),
    (123, 15, True, "Re: Third follow-up on the billing dispute"),  # 102h
    (126, 9, False, "Any update on the billing item?"),
    (130, 15, True, "Re: Any update on the billing item?"),  # 102h
    (136, 9, False, "Fourth follow-up -- billing dispute still open"),
    (140, 21, True, "Re: Fourth follow-up -- billing dispute still open"),  # 132h
)

_F2_BODIES = {
    (12, 9): "Hi Marcus, welcome aboard -- looking forward to supporting Culvert Mechanical.",
    (13, 21): "Thanks, appreciate it. Team's getting set up now.",
    (44, 9): "Hi Marcus, quick check-in -- anything come up this month?",
    (45, 23): "Nothing at all, all running smoothly.",
    (58, 9): "Hi Marcus, checking in ahead of our quarterly call -- anything come up?",
    (59, 23): "All good here, see you on the call.",
    (65, 9): "Hi Marcus, good talking with you last week -- sending the recap over.",
    (66, 22): "Got it, thanks -- all accurate.",
    (92, 9): "Hi Marcus, following up on the disputed line item on the May invoice -- can you take a look?",
    (95, 14): "Sorry for the slow reply, been slammed in the field. Looking into it now.",
    (100, 9): "Hi Marcus, just checking in on the invoice dispute -- any update?",
    (103, 15): "Still chasing this down on our end, apologies for the delay.",
    (119, 9): "Hi Marcus, this is now our third follow-up on the billing dispute -- can we find time to resolve it?",
    (123, 15): "Apologies again, still working through it internally.",
    (126, 9): "Hi Marcus, any update on the billing item?",
    (130, 15): "Not yet, still chasing it down -- will follow up.",
    (136, 9): "Hi Marcus, this is our fourth follow-up -- the billing dispute is still open on our side.",
    (140, 21): "Sorry for how long this has dragged on, still working it internally.",
}


# ---------------------------------------------------------------------------
# Herring F-H1 (wrenhouse-hvac) -- flat baseline like every boring control,
# no arc-level story at all beyond the one loud-looking, fast-resolving
# case (see book.py's ``_cases``).
# ---------------------------------------------------------------------------
_HERRING_SCHEDULE: tuple[tuple[int, int, bool, str], ...] = (
    (20, 9, False, "Welcome to Fieldstone Service Cloud"),
    (21, 23, True, "Re: Welcome to Fieldstone Service Cloud"),  # 38h
    (100, 9, False, "Quarterly check-in ahead of our call"),
    (101, 23, True, "Re: Quarterly check-in ahead of our call"),  # 38h
    (190, 9, False, "Following up after the portal incident"),
    (191, 15, True, "Re: Following up after the portal incident"),  # 30h
    (280, 9, False, "Quarterly check-in ahead of our call"),
    (281, 21, True, "Re: Quarterly check-in ahead of our call"),  # 36h
)

_HERRING_BODIES = {
    (20, 9): "Hi Diane, welcome aboard -- looking forward to supporting Wrenhouse HVAC.",
    (21, 23): "Thanks, all set up on our end.",
    (100, 9): "Hi Diane, checking in ahead of our quarterly call -- anything to flag?",
    (101, 23): "Nothing major, see you on the call.",
    (190, 9): "Hi Diane, following up after that portal outage last week -- all resolved on our end?",
    (191, 15): "Yep, was back up within the hour, no lingering issues.",
    (280, 9): "Hi Diane, checking in ahead of our quarterly call.",
    (281, 21): "All good here, talk soon.",
}

_ARC_TABLE = {
    ARC_F1_SLUG: (_F1_SCHEDULE, _F1_BODIES),
    ARC_F2_SLUG: (_F2_SCHEDULE, _F2_BODIES),
    HERRING_SLUG: (_HERRING_SCHEDULE, _HERRING_BODIES),
}


def _email_thread(slug: str, as_of_day: int) -> dict:
    account_id = account_id_for(slug)
    schedule, bodies = _ARC_TABLE[slug]
    csm_email = _CSM_EMAIL_BY_SLUG[slug]
    champion_email = _CHAMPION_EMAIL_BY_SLUG[slug]
    thread_id = det_id("email-thread", account_id, "primary")
    messages = []
    for day_offset, hour, from_champion, subject in schedule:
        if day_offset > as_of_day:
            break
        sender = champion_email if from_champion else csm_email
        recipient = csm_email if from_champion else champion_email
        msg_id = det_id("email-msg", account_id, day_offset, hour)
        body = bodies[(day_offset, hour)]
        messages.append({
            "id": msg_id,
            "threadId": thread_id,
            "labelIds": ["INBOX"] if from_champion else ["SENT"],
            "snippet": derive_snippet(body),
            "internalDate": str(int(
                datetime.fromisoformat(rfc3339(day_offset, hour).replace("Z", "+00:00")).timestamp() * 1000
            )),
            "payload": {
                "headers": [
                    {"name": "From", "value": sender},
                    {"name": "To", "value": recipient},
                    {"name": "Date", "value": rfc3339(day_offset, hour)},
                    {"name": "Subject", "value": subject},
                ],
                "body": {"data": body},
            },
        })
    return {"id": thread_id, "historyId": str(1000 + as_of_day), "messages": messages}


def _communication_signals(slug: str, as_of_day: int) -> list[CommunicationSignal]:
    account_id = account_id_for(slug)
    contact_id = det_id("contact", slug, "champion")
    champion_email = _CHAMPION_EMAIL_BY_SLUG[slug]
    thread = _email_thread(slug, as_of_day)
    signals: list[CommunicationSignal] = []
    prev_outbound_at: datetime | None = None
    for msg in thread["messages"]:
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        sent_at = datetime.fromisoformat(headers["Date"].replace("Z", "+00:00"))
        from_champion = headers["From"] == champion_email
        if not from_champion:
            prev_outbound_at = sent_at
            signals.append(CommunicationSignal(
                signal_id=det_id("comm-signal", account_id, msg["id"]),
                account_id=account_id,
                contact_id=contact_id,
                channel="email",
                direction="outbound",
                timestamp=headers["Date"],
            ))
            continue
        response_time_hours = None
        if prev_outbound_at is not None:
            response_time_hours = round((sent_at - prev_outbound_at).total_seconds() / 3600.0, 1)
        signals.append(CommunicationSignal(
            signal_id=det_id("comm-signal", account_id, msg["id"]),
            account_id=account_id,
            contact_id=contact_id,
            channel="email",
            direction="inbound",
            timestamp=headers["Date"],
            response_time_hours=response_time_hours,
        ))
    return signals


def _stakeholder_relationships(slug: str, as_of_day: int) -> list[StakeholderRelationship]:
    """One owner-operator champion throughout -- Fieldstone's small-business
    customers are single-threaded by nature (an HVAC/plumbing owner-
    operator), which is itself normal for this tenant, not a risk signal
    the way it is in fleetops' Pinnacle single-threaded-risk arc."""

    account_id = account_id_for(slug)
    contact_id = det_id("contact", slug, "champion")
    champion_email = _CHAMPION_EMAIL_BY_SLUG[slug]
    thread = _email_thread(slug, as_of_day)
    last_inbound = None
    for msg in thread["messages"]:
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        if headers["From"] == champion_email:
            last_inbound = headers["Date"]
    if last_inbound is None:
        return []
    return [StakeholderRelationship(
        account_id=account_id,
        contact_id=contact_id,
        relationship_type="champion",
        strength="strong",
        last_interaction=last_inbound,
        multi_thread_depth=1,
    )]


# ---------------------------------------------------------------------------
# Calendar: quarterly cadence (~90 days), the tenant's own healthy norm.
# ---------------------------------------------------------------------------
_F1_CALENDAR: tuple[int, ...] = (15, 105, 195, 285)
_F2_CALENDAR: tuple[int, ...] = (15,)  # day-90 quarterly meeting never happens (the missed beat)
_HERRING_CALENDAR: tuple[int, ...] = (15, 105, 195, 285)

_CALENDAR_TABLE = {
    ARC_F1_SLUG: _F1_CALENDAR,
    ARC_F2_SLUG: _F2_CALENDAR,
    HERRING_SLUG: _HERRING_CALENDAR,
}


def _calendar_events(slug: str, as_of_day: int) -> dict:
    account_id = account_id_for(slug)
    csm_email = _CSM_EMAIL_BY_SLUG[slug]
    champion_email = _CHAMPION_EMAIL_BY_SLUG[slug]
    items = []
    for day_offset in _CALENDAR_TABLE[slug]:
        if day_offset > as_of_day:
            break
        event_id = det_id("calendar-event", account_id, day_offset)
        start = rfc3339(day_offset, 10)
        end = rfc3339(day_offset, 10, minute=30)
        items.append({
            "id": event_id,
            "summary": f"{slug} <> Fieldstone quarterly business review",
            "start": {"dateTime": start},
            "end": {"dateTime": end},
            "attendees": [
                {"email": csm_email, "responseStatus": "accepted"},
                {"email": champion_email, "responseStatus": "accepted"},
            ],
            "recurrence": ["RRULE:FREQ=MONTHLY;INTERVAL=3"],
            "status": "confirmed",
        })
    return {"items": items}


def _cases_as_of(slug: str, as_of_day: int) -> list[CRMCase]:
    from ultra_csm.data_plane.tenants.fieldstone.book import build_fieldstone_book

    account_id = account_id_for(slug)
    day_by_case = {
        det_id("case", ARC_F2_SLUG, "billing-dispute"): 100,
        det_id("case", HERRING_SLUG, "portal-down"): 45,
    }
    book = build_fieldstone_book()
    return [
        c for c in book.cases
        if c.account_id == account_id and day_by_case.get(c.case_id, 0) <= as_of_day
    ]


# ---------------------------------------------------------------------------
# Public per-arc accessors, mirroring comms_fixtures.py's naming pattern.
# ---------------------------------------------------------------------------


def masonry_communication_signals(as_of_day: int) -> list[CommunicationSignal]:
    return _communication_signals(ARC_F1_SLUG, as_of_day)


def masonry_stakeholder_relationships(as_of_day: int) -> list[StakeholderRelationship]:
    return _stakeholder_relationships(ARC_F1_SLUG, as_of_day)


def masonry_calendar_events(as_of_day: int) -> dict:
    return _calendar_events(ARC_F1_SLUG, as_of_day)


def masonry_cases_as_of(as_of_day: int) -> list[CRMCase]:
    return _cases_as_of(ARC_F1_SLUG, as_of_day)


def culvert_communication_signals(as_of_day: int) -> list[CommunicationSignal]:
    return _communication_signals(ARC_F2_SLUG, as_of_day)


def culvert_stakeholder_relationships(as_of_day: int) -> list[StakeholderRelationship]:
    return _stakeholder_relationships(ARC_F2_SLUG, as_of_day)


def culvert_calendar_events(as_of_day: int) -> dict:
    return _calendar_events(ARC_F2_SLUG, as_of_day)


def culvert_cases_as_of(as_of_day: int) -> list[CRMCase]:
    return _cases_as_of(ARC_F2_SLUG, as_of_day)


def wrenhouse_communication_signals(as_of_day: int) -> list[CommunicationSignal]:
    return _communication_signals(HERRING_SLUG, as_of_day)


def wrenhouse_stakeholder_relationships(as_of_day: int) -> list[StakeholderRelationship]:
    return _stakeholder_relationships(HERRING_SLUG, as_of_day)


def wrenhouse_calendar_events(as_of_day: int) -> dict:
    return _calendar_events(HERRING_SLUG, as_of_day)


def wrenhouse_cases_as_of(as_of_day: int) -> list[CRMCase]:
    return _cases_as_of(HERRING_SLUG, as_of_day)
