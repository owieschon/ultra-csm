"""OOO auto-reply guard for the live Gmail reader.

Real out-of-office auto-replies typically quote the original subject line
and come from the original recipient's real email domain -- so they'd
match ``live_email_thread``'s subject-tag/participant-domain IMAP search
and be misread as a genuine, fast customer reply, artificially deflating
``reply_latency_trend`` (data_plane/signal_extractor.py) and hiding a real
risk signal. RFC 3834's ``Auto-Submitted`` header (present, value other
than ``no``) distinguishes an auto-reply from a real inbound reply, which
never carries the header (or carries ``Auto-Submitted: no``).

No real IMAP/network: this constructs fake ``email.message.Message``
objects (the same raw object type ``live_email_thread`` gets back from
``email.message_from_bytes``) and feeds them through
``_message_dict_from_raw``, the internal parsing function extracted from
``live_email_thread`` for exactly this purpose.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime

from ultra_csm.data_plane.contracts import CommunicationSignal
from ultra_csm.data_plane.live_gmail_reader import _message_dict_from_raw
from ultra_csm.data_plane.signal_extractor import reply_latency_trend

_TAG = "pinehill-live-reseed"
_DOMAIN = "pinehill-transport.example"
_CSM_EMAIL = "csm102@fleetops-platform.example"
_CHAMPION_EMAIL = "dennis.gruber@pinehill-transport.example"
_ACCOUNT_ID = "acct-pinehill-live-reseed"
_CONTACT_ID = "contact-dennis-gruber"


def _raw_message(
    *,
    from_addr: str,
    to_addr: str,
    date: str,
    subject: str,
    body: str = "body text",
    auto_submitted: str | None = None,
) -> bytes:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Date"] = date
    msg["Subject"] = subject
    msg["Message-ID"] = f"<{hash((from_addr, date, subject))}@example>"
    if auto_submitted is not None:
        msg["Auto-Submitted"] = auto_submitted
    msg.set_content(body)
    return bytes(msg)


def _parse(raw_bytes: bytes, uid: bytes = b"1") -> dict | None:
    return _message_dict_from_raw(raw_bytes, uid, tag=_TAG, participant_domain=_DOMAIN)


# ---------------------------------------------------------------------------
# (b) normal replies (no header, or "no") are not filtered.
# ---------------------------------------------------------------------------


def test_message_with_no_auto_submitted_header_is_not_filtered():
    raw = _raw_message(
        from_addr=_CHAMPION_EMAIL,
        to_addr=_CSM_EMAIL,
        date="Mon, 01 Jun 2026 15:00:00 +0000",
        subject=f"Re: Checking in [{_TAG}]",
        body="Thanks, all good here.",
    )

    parsed = _parse(raw)

    assert parsed is not None
    headers = {h["name"]: h["value"] for h in parsed["payload"]["headers"]}
    assert headers["From"] == _CHAMPION_EMAIL
    assert headers["Subject"] == f"Re: Checking in [{_TAG}]"


def test_message_with_auto_submitted_no_is_not_filtered():
    raw = _raw_message(
        from_addr=_CHAMPION_EMAIL,
        to_addr=_CSM_EMAIL,
        date="Mon, 01 Jun 2026 15:00:00 +0000",
        subject=f"Re: Checking in [{_TAG}]",
        auto_submitted="no",
    )

    parsed = _parse(raw)

    assert parsed is not None


# ---------------------------------------------------------------------------
# (a) an OOO auto-reply (Auto-Submitted: auto-replied) is excluded.
# ---------------------------------------------------------------------------


def test_message_with_auto_submitted_auto_replied_is_filtered_out():
    raw = _raw_message(
        from_addr=_CHAMPION_EMAIL,
        to_addr=_CSM_EMAIL,
        date="Mon, 01 Jun 2026 09:05:00 +0000",
        subject=f"Automatic reply: Checking in [{_TAG}]",
        body="I am out of the office and will respond when I return.",
        auto_submitted="auto-replied",
    )

    assert _parse(raw) is None


def test_auto_submitted_header_match_is_case_insensitive():
    raw = _raw_message(
        from_addr=_CHAMPION_EMAIL,
        to_addr=_CSM_EMAIL,
        date="Mon, 01 Jun 2026 09:05:00 +0000",
        subject=f"Automatic reply: Checking in [{_TAG}]",
        auto_submitted="Auto-Replied",
    )

    assert _parse(raw) is None


# ---------------------------------------------------------------------------
# Thread-level: an OOO auto-reply spliced between the outbound message and
# the real customer reply must not move reply_latency_trend at all -- the
# thread built with the OOO message present (and filtered) must match, in
# every message and in the resulting signal, a thread built without the
# OOO message ever having existed.
# ---------------------------------------------------------------------------


def _build_thread_messages(raw_triples: list[tuple[bytes, bytes]]) -> list[dict]:
    """Mimic live_email_thread's per-uid parse-and-filter loop, then sort
    the same way live_email_thread does."""

    messages = []
    for raw_bytes, uid in raw_triples:
        parsed = _parse(raw_bytes, uid)
        if parsed is not None:
            messages.append(parsed)
    messages.sort(key=lambda m: m["payload"]["headers"][2]["value"])
    return messages


def _communication_signals_from_thread(messages: list[dict]) -> list[CommunicationSignal]:
    """Adapt a raw thread's messages into CommunicationSignal rows the same
    way comms_fixtures.py's pinehill_communication_signals() does: one row
    per message, response_time_hours on inbound rows computed from the
    preceding outbound message."""

    signals: list[CommunicationSignal] = []
    prev_outbound_at = None
    for i, msg in enumerate(messages):
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        sent_at = datetime.fromisoformat(headers["Date"].replace("Z", "+00:00"))
        from_champion = headers["From"] == _CHAMPION_EMAIL
        if not from_champion:
            prev_outbound_at = sent_at
            signals.append(
                CommunicationSignal(
                    signal_id=f"sig-{i}",
                    account_id=_ACCOUNT_ID,
                    contact_id=_CONTACT_ID,
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
                signal_id=f"sig-{i}",
                account_id=_ACCOUNT_ID,
                contact_id=_CONTACT_ID,
                channel="email",
                direction="inbound",
                timestamp=headers["Date"],
                response_time_hours=response_time_hours,
            )
        )
    return signals


_BASE_DATE = datetime(2026, 6, 1, 9, 0, 0, tzinfo=timezone.utc)


def _windowed_schedule(fast_hours: float) -> list[tuple[bytes, bytes]]:
    """Two windows' worth of outbound/reply pairs (so reply_latency_trend
    has both a recent and a prior window), all replying in ``fast_hours``."""

    raws = []
    uid = 0
    for day in (5, 12, 26, 33):
        out_at = _BASE_DATE + timedelta(days=day)
        uid += 1
        raws.append(
            (
                _raw_message(
                    from_addr=_CSM_EMAIL,
                    to_addr=_CHAMPION_EMAIL,
                    date=format_datetime(out_at),
                    subject=f"Checking in [{_TAG}] #{day}",
                ),
                str(uid).encode(),
            )
        )
        uid += 1
        reply_at = out_at + timedelta(hours=fast_hours)
        raws.append(
            (
                _raw_message(
                    from_addr=_CHAMPION_EMAIL,
                    to_addr=_CSM_EMAIL,
                    date=format_datetime(reply_at),
                    subject=f"Re: Checking in [{_TAG}] #{day}",
                ),
                str(uid).encode(),
            )
        )
    return raws


def test_ooo_auto_reply_does_not_change_reply_latency_trend():
    as_of = "2026-07-10"

    base_schedule = _windowed_schedule(fast_hours=4.0)

    # Thread A: outbound, then an OOO auto-reply immediately after, then the
    # real (fast) customer reply -- as would happen once OOO noise is
    # seeded into the live mailbox.
    ooo_at = _BASE_DATE + timedelta(days=5, minutes=1)
    ooo_raw = _raw_message(
        from_addr=_CHAMPION_EMAIL,
        to_addr=_CSM_EMAIL,
        date=format_datetime(ooo_at),
        subject=f"Automatic reply: Checking in [{_TAG}] #5",
        body="Out of office, will respond later.",
        auto_submitted="auto-replied",
    )
    schedule_with_ooo = list(base_schedule) + [(ooo_raw, b"999")]

    messages_with_ooo = _build_thread_messages(schedule_with_ooo)
    messages_without_ooo = _build_thread_messages(base_schedule)

    # The OOO message must be entirely absent from the built thread.
    assert all(
        "Automatic reply" not in dict(
            (h["name"], h["value"]) for h in m["payload"]["headers"]
        ).get("Subject", "")
        for m in messages_with_ooo
    )
    assert len(messages_with_ooo) == len(messages_without_ooo)

    signals_with_ooo = _communication_signals_from_thread(messages_with_ooo)
    signals_without_ooo = _communication_signals_from_thread(messages_without_ooo)

    trend_with_ooo = reply_latency_trend(_ACCOUNT_ID, signals_with_ooo, as_of=as_of)
    trend_without_ooo = reply_latency_trend(_ACCOUNT_ID, signals_without_ooo, as_of=as_of)

    assert trend_with_ooo.value == trend_without_ooo.value
    assert trend_with_ooo.value is not None


def test_ooo_auto_reply_excluded_would_otherwise_have_deflated_latency():
    """Sanity check on the scenario itself: the customer is consistently
    slow (30h) in both the prior and recent trend windows -- a flat,
    genuinely-no-improvement risk signal. If an OOO auto-reply seeded only
    in the recent window were NOT filtered (i.e. its ~1-minute turnaround
    were treated as the customer's real reply), the recent-window mean
    would drop sharply, manufacturing a fake "reply latency improving"
    reading and hiding the real (flat/risk) signal. This is the exact
    deflation the guard prevents."""

    as_of = "2026-07-10"

    # Prior window (days 5, 12) and recent window (days 26, 33): customer
    # always replies in 30h. Only the recent-window pairs also get an OOO
    # auto-reply landing 1 minute after the outbound message.
    slow_schedule: list[tuple[bytes, bytes]] = []
    unguarded_schedule: list[tuple[bytes, bytes]] = []
    uid = 0
    for day in (5, 12, 26, 33):
        out_at = _BASE_DATE + timedelta(days=day)
        uid += 1
        outbound_raw = _raw_message(
            from_addr=_CSM_EMAIL,
            to_addr=_CHAMPION_EMAIL,
            date=format_datetime(out_at),
            subject=f"Checking in [{_TAG}] #{day}",
        )
        outbound_entry = (outbound_raw, str(uid).encode())
        slow_schedule.append(outbound_entry)
        unguarded_schedule.append(outbound_entry)

        slow_reply_raw = _raw_message(
            from_addr=_CHAMPION_EMAIL,
            to_addr=_CSM_EMAIL,
            date=format_datetime(out_at + timedelta(hours=30)),
            subject=f"Re: Checking in [{_TAG}] #{day}",
        )
        uid += 1
        slow_reply_entry = (slow_reply_raw, str(uid).encode())
        slow_schedule.append(slow_reply_entry)
        unguarded_schedule.append(slow_reply_entry)

        if day in (26, 33):  # recent window only
            ooo_at = out_at + timedelta(minutes=1)
            uid += 1
            # Guarded schedule: real OOO message, carries Auto-Submitted
            # and gets filtered by _message_dict_from_raw. Unguarded
            # schedule: same timing/content but no Auto-Submitted header,
            # standing in for "the guard doesn't exist" so it's treated
            # as the reply.
            slow_schedule.append(
                (
                    _raw_message(
                        from_addr=_CHAMPION_EMAIL,
                        to_addr=_CSM_EMAIL,
                        date=format_datetime(ooo_at),
                        subject=f"Automatic reply: Checking in [{_TAG}] #{day}",
                        auto_submitted="auto-replied",
                    ),
                    str(uid).encode(),
                )
            )
            unguarded_schedule.append(
                (
                    _raw_message(
                        from_addr=_CHAMPION_EMAIL,
                        to_addr=_CSM_EMAIL,
                        date=format_datetime(ooo_at),
                        subject=f"Automatic reply: Checking in [{_TAG}] #{day}",
                    ),
                    str(uid).encode(),
                )
            )

    messages_filtered = _build_thread_messages(slow_schedule)
    signals_filtered = _communication_signals_from_thread(messages_filtered)
    trend_filtered = reply_latency_trend(_ACCOUNT_ID, signals_filtered, as_of=as_of)

    messages_unguarded = _build_thread_messages(unguarded_schedule)
    signals_unguarded = _communication_signals_from_thread(messages_unguarded)
    trend_unguarded = reply_latency_trend(_ACCOUNT_ID, signals_unguarded, as_of=as_of)

    assert trend_filtered.value is not None
    assert trend_unguarded.value is not None
    # Guarded: flat 30h in both windows -> zero trend (correctly flags no
    # improvement, i.e. sustained risk). Unguarded: the fast OOO replies
    # pull the recent-window mean down, manufacturing a negative
    # ("improving") delta that hides the real, unchanged slow latency.
    assert trend_filtered.value == 0.0
    assert trend_unguarded.value < trend_filtered.value
