"""Pinnacle Supply Chain's single-threaded-risk arc, day-offset aware.

Companion to comms_fixtures.py (same pattern, different arc -- see
docs/SYNTHETIC_UNIVERSE_BIBLE.md's "Single-threaded-risk" section). The
sole champion, Derek Vaughn, goes quiet day 3 (SCENARIO_TIMELINE) and never
replies again. A second contact, Monica Reeves, appears day 110 (already
scripted via NewContactAppears) and becomes the new champion by day 240 --
this module's job is to make that width-1-inactive -> width-2-weak ->
width-1-strong (Monica) story visible in raw email/calendar artifacts.
"""

from __future__ import annotations

from datetime import datetime

from ultra_csm.data_plane.contracts import CommunicationSignal, CRMCase, StakeholderRelationship
from ultra_csm.data_plane.fixtures import account_id_for, det_id
from ultra_csm.data_plane.narrative_shared import cases_as_of, rfc3339 as _rfc3339

PINNACLE_ACCOUNT_ID = account_id_for("pinnacle-supply")
_CSM_EMAIL = "csm101@fleetops-platform.example"
_DEREK_EMAIL = "derek.vaughn@pinnacle-supply.example"
_MONICA_EMAIL = "monica.reeves@pinnacle-supply.example"
DEREK_CONTACT_ID = det_id("contact", PINNACLE_ACCOUNT_ID, _DEREK_EMAIL)
MONICA_CONTACT_ID = det_id("contact", PINNACLE_ACCOUNT_ID, _MONICA_EMAIL)

# (day_offset, hour, contact_email, from_contact, subject, snippet)
_MESSAGE_SCHEDULE: tuple[tuple[int, int, str, bool, str, str], ...] = (
    (1, 9, _DEREK_EMAIL, False, "Kickoff — quarterly ops review",
     "Looking forward to our quarterly review next week."),
    (1, 13, _DEREK_EMAIL, True, "Re: Kickoff — quarterly ops review",
     "Sounds good, see you then."),
    # Derek goes quiet day 3 (ChampionGoesQuiet) -- no further messages from him, ever.
    (110, 9, _MONICA_EMAIL, False, "Introduction — Pinnacle Supply Chain account",
     "Hi Monica, introducing myself as your CSM contact going forward."),
    (112, 20, _MONICA_EMAIL, True, "Re: Introduction — Pinnacle Supply Chain account",
     "Thanks for reaching out, still getting oriented on my end."),
    (135, 9, _MONICA_EMAIL, False, "Recovery plan — activation review",
     "Sending over the activation review agenda for this week."),
    (136, 15, _MONICA_EMAIL, True, "Re: Recovery plan — activation review",
     "Looks good, appreciate you putting this together."),
    (170, 9, _MONICA_EMAIL, False, "Check-in — how's adoption looking",
     "Wanted to check in on how the rollout is progressing."),
    (170, 13, _MONICA_EMAIL, True, "Re: Check-in — how's adoption looking",
     "Going well, team's fully ramped now."),
    (210, 9, _MONICA_EMAIL, False, "Renewal prep kickoff",
     "Starting renewal prep conversations a bit early this cycle."),
    (210, 12, _MONICA_EMAIL, True, "Re: Renewal prep kickoff",
     "Great, let's get time on the calendar."),
    (245, 9, _MONICA_EMAIL, False, "Quarterly business review — recap",
     "Recap from today's QBR, great momentum across the board."),
    (245, 12, _MONICA_EMAIL, True, "Re: Quarterly business review — recap",
     "Agreed, really pleased with where things stand."),
)


def pinnacle_email_thread(as_of_day: int) -> dict:
    """Gmail ``users.threads.get`` shape. One thread per contact (Derek's
    dies after day 3; Monica's starts day 110), truncated to *as_of_day*."""

    threads: dict[str, dict] = {}
    for day_offset, hour, contact_email, from_contact, subject, snippet in _MESSAGE_SCHEDULE:
        if day_offset > as_of_day:
            break
        thread_key = "derek" if contact_email == _DEREK_EMAIL else "monica"
        thread_id = det_id("email-thread", PINNACLE_ACCOUNT_ID, thread_key)
        sender = contact_email if from_contact else _CSM_EMAIL
        recipient = _CSM_EMAIL if from_contact else contact_email
        msg_id = det_id("email-msg", PINNACLE_ACCOUNT_ID, day_offset, hour)
        threads.setdefault(
            thread_id, {"id": thread_id, "historyId": str(1000 + as_of_day), "messages": []}
        )
        threads[thread_id]["messages"].append(
            {
                "id": msg_id,
                "threadId": thread_id,
                "labelIds": ["INBOX"] if from_contact else ["SENT"],
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
    return {"threads": list(threads.values())}


def pinnacle_communication_signals(as_of_day: int) -> list[CommunicationSignal]:
    """Adapt the raw threads into ``CommunicationSignal`` rows for both
    contacts, with reply latency computed per-contact."""

    signals: list[CommunicationSignal] = []
    for thread in pinnacle_email_thread(as_of_day)["threads"]:
        prev_outbound_at = None
        for msg in thread["messages"]:
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            sent_at = datetime.fromisoformat(headers["Date"].replace("Z", "+00:00"))
            from_derek = headers["From"] == _DEREK_EMAIL
            from_monica = headers["From"] == _MONICA_EMAIL
            contact_id = DEREK_CONTACT_ID if from_derek else MONICA_CONTACT_ID if from_monica else None
            if contact_id is None:
                # outbound from CSM -- attribute to whichever contact this thread is for.
                contact_id = DEREK_CONTACT_ID if _DEREK_EMAIL in (headers["To"],) else MONICA_CONTACT_ID
                prev_outbound_at = sent_at
                signals.append(
                    CommunicationSignal(
                        signal_id=det_id("comm-signal", PINNACLE_ACCOUNT_ID, msg["id"]),
                        account_id=PINNACLE_ACCOUNT_ID,
                        contact_id=contact_id,
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
                    signal_id=det_id("comm-signal", PINNACLE_ACCOUNT_ID, msg["id"]),
                    account_id=PINNACLE_ACCOUNT_ID,
                    contact_id=contact_id,
                    channel="email",
                    direction="inbound",
                    timestamp=headers["Date"],
                    response_time_hours=response_time_hours,
                )
            )
    return signals


def pinnacle_stakeholder_relationships(as_of_day: int) -> list[StakeholderRelationship]:
    """Derek's relationship exists from day 1 but never updates past his
    last reply (day 1); Monica's appears day 110 and strengthens over time
    -- width reads as 1 (Derek, inactive) before day 110, 2 (both, Monica
    weak) from day 110, and Monica reads ``strength="strong"`` by day 245.
    """

    relationships: list[StakeholderRelationship] = []
    if as_of_day >= 1:
        relationships.append(
            StakeholderRelationship(
                account_id=PINNACLE_ACCOUNT_ID,
                contact_id=DEREK_CONTACT_ID,
                relationship_type="champion",
                strength="weak",
                last_interaction=_rfc3339(1, 13),
                multi_thread_depth=1,
            )
        )
    if as_of_day >= 110:
        strength = "strong" if as_of_day >= 240 else "moderate" if as_of_day >= 135 else "weak"
        last_interaction = _rfc3339(1, 13)
        for day_offset, hour, contact_email, from_contact, _subject, _snippet in _MESSAGE_SCHEDULE:
            if day_offset > as_of_day or contact_email != _MONICA_EMAIL or not from_contact:
                continue
            last_interaction = _rfc3339(day_offset, hour)
        relationships.append(
            StakeholderRelationship(
                account_id=PINNACLE_ACCOUNT_ID,
                contact_id=MONICA_CONTACT_ID,
                relationship_type="champion",
                strength=strength,
                last_interaction=last_interaction,
                multi_thread_depth=2,
            )
        )
    return relationships


# ---------------------------------------------------------------------------
# Calendar: Derek's weekly sync stops after day 1; Monica's cadence starts
# thin (monthly) from day 110 and tightens toward a strong quarterly-plus
# cadence by day 245.
# ---------------------------------------------------------------------------

_CALENDAR_SCHEDULE: tuple[tuple[int, str], ...] = (
    (1, "confirmed"),
    # silence -- Derek's sync never recurs after day 3
    (112, "confirmed"),
    (140, "confirmed"),
    (170, "confirmed"),
    (200, "confirmed"),
    (215, "confirmed"),
    (230, "confirmed"),
    (245, "confirmed"),
)


def pinnacle_calendar_events(as_of_day: int) -> dict:
    items = []
    for day_offset, status in _CALENDAR_SCHEDULE:
        if day_offset > as_of_day:
            break
        attendee_email = _DEREK_EMAIL if day_offset == 1 else _MONICA_EMAIL
        event_id = det_id("calendar-event", PINNACLE_ACCOUNT_ID, day_offset)
        items.append(
            {
                "id": event_id,
                "summary": "Pinnacle Supply Chain <> CSM Sync",
                "start": {"dateTime": _rfc3339(day_offset, 10)},
                "end": {"dateTime": _rfc3339(day_offset, 10, minute=30)},
                "attendees": [
                    {"email": _CSM_EMAIL, "responseStatus": "accepted"},
                    {"email": attendee_email, "responseStatus": "accepted"},
                ],
                "recurrence": ["RRULE:FREQ=WEEKLY"] if day_offset == 1 else ["RRULE:FREQ=MONTHLY"],
                "status": status,
            }
        )
    return {"items": items}


def pinnacle_cases_as_of(as_of_day: int) -> list[CRMCase]:
    return cases_as_of(PINNACLE_ACCOUNT_ID, as_of_day)
