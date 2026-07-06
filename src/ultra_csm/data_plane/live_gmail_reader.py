"""Live Gmail read adapter for narrative-arc email evidence.

Reads real IMAP messages back into the exact same Gmail ``users.threads.get``
-shaped dict the fixture comms modules (``comms_fixtures.py`` and its arc
siblings) already produce, so the existing, already-tested extraction
functions (``pinehill_communication_signals`` etc.) consume live data through
an unmodified code path -- pass the live thread dict as their optional
``thread=`` argument instead of letting them default to the fixture.

Auth: IMAP with an app password (``ULTRA_CSM_GMAIL_APP_PASSWORD`` /
``ULTRA_CSM_GMAIL_SENDER`` in the credentials env file, parsed via the shared
``connector_catalog.load_live_creds_file`` loader -- architecture cleanup,
report 42). Read-only: this module only ever opens the mailbox with
``readonly=True``.
"""

from __future__ import annotations

import email.header
import email.utils
import imaplib
from email import message_from_bytes
from email.message import Message

from ultra_csm.data_plane.connector_catalog import (
    load_live_creds_file,
    resolve_live_creds_path,
)


def _imap_connect(readonly: bool = True) -> imaplib.IMAP4_SSL:
    env = load_live_creds_file()
    addr = env.get("ULTRA_CSM_GMAIL_SENDER", "")
    pw = env.get("ULTRA_CSM_GMAIL_APP_PASSWORD", "")
    if not addr or not pw:
        raise RuntimeError(
            "ULTRA_CSM_GMAIL_SENDER/ULTRA_CSM_GMAIL_APP_PASSWORD missing from "
            f"{resolve_live_creds_path()}"
        )
    imap = imaplib.IMAP4_SSL("imap.gmail.com", timeout=30)
    imap.login(addr, pw)
    imap.select("INBOX", readonly=readonly)
    return imap


def _decode_part(part: bytes, encoding: str | None) -> str:
    # Some servers label re-encoded headers with placeholder charsets
    # ("unknown-8bit" etc.) that Python's codec registry doesn't recognize.
    # Fall back to utf-8/replace rather than raising on those.
    for candidate in (encoding, "utf-8"):
        if not candidate:
            continue
        try:
            return part.decode(candidate, errors="replace")
        except LookupError:
            continue
    return part.decode("utf-8", errors="replace")


def _decode_header(raw: str | None) -> str:
    if raw is None:
        return ""
    parts = email.header.decode_header(raw)
    return "".join(
        _decode_part(part, enc) if isinstance(part, bytes) else part for part, enc in parts
    )


def _payload_text(msg: Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                charset = part.get_content_charset() or "utf-8"
                return part.get_payload(decode=True).decode(charset, errors="replace")
        return ""
    charset = msg.get_content_charset() or "utf-8"
    payload = msg.get_payload(decode=True)
    return payload.decode(charset, errors="replace") if payload else ""


def _is_auto_submitted(msg: Message) -> bool:
    """RFC 3834: an ``Auto-Submitted`` header present with any value other
    than ``no`` (case-insensitive) marks an automatic response -- e.g. an
    out-of-office auto-reply. Real inbound customer replies never carry
    this header, or carry ``Auto-Submitted: no``. Auto-replies typically
    quote the original subject and come from the original recipient's real
    domain, so without this guard they'd be misread by
    ``live_email_thread`` as a genuine, fast customer reply and silently
    deflate ``reply_latency_trend``."""

    value = msg.get("Auto-Submitted")
    if value is None:
        return False
    return value.strip().lower() != "no"


def _message_dict_from_raw(raw_bytes: bytes, uid: bytes, *, tag: str, participant_domain: str) -> dict | None:
    """Parse one raw ``RFC822`` message into the thread's message-dict
    shape, or return ``None`` if it's an auto-submitted (e.g. OOO
    auto-reply) message that must be excluded from the thread entirely."""

    msg = message_from_bytes(raw_bytes)
    if _is_auto_submitted(msg):
        return None
    from_addr = _decode_header(msg.get("From"))
    to_addr = _decode_header(msg.get("To"))
    subject = _decode_header(msg.get("Subject"))
    date_hdr = msg.get("Date")
    parsed_date = email.utils.parsedate_to_datetime(date_hdr)
    iso_date = parsed_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    message_id = msg.get("Message-ID", uid.decode())
    return {
        "id": message_id,
        "threadId": f"live-{tag}-{participant_domain}",
        "labelIds": ["SENT"] if "fleetops-platform.example" in from_addr else ["INBOX"],
        "snippet": _payload_text(msg).strip()[:200],
        "payload": {
            "headers": [
                {"name": "From", "value": from_addr},
                {"name": "To", "value": to_addr},
                {"name": "Date", "value": iso_date},
                {"name": "Subject", "value": subject},
            ],
            "body": {"data": _payload_text(msg).strip()},
        },
    }


def live_email_thread(*, tag: str, participant_domain: str) -> dict:
    """Fetch every live INBOX message tagged ``tag`` involving
    ``participant_domain`` (e.g. ``pinehill-transport.example``), return it
    shaped exactly like the fixture modules' ``*_email_thread()`` output:
    ``{"id": ..., "historyId": ..., "messages": [...]}`` with each message
    carrying ``payload.headers`` (From/To/Date/Subject) and
    ``payload.body.data`` -- the same fields the existing
    ``*_communication_signals`` extraction functions already read.

    Messages carrying an ``Auto-Submitted`` header valued anything other
    than ``no`` (RFC 3834 -- e.g. out-of-office auto-replies) are excluded
    from ``messages`` entirely, as if they never existed; see
    ``_is_auto_submitted``.

    Read-only. Does not modify the mailbox (opens with readonly=True).

    Reference implementation: not called by any production sweep/tick path
    directly -- eight ``data_plane`` comms-fixture modules (``aspenridge_comms``,
    ``quarrystone_comms``, ``meridian_comms``, ``comms_fixtures``,
    ``trailhead_comms``, ``pinnacle_comms``, plus ``notion_reader``) cite this
    function BY NAME in their own docstrings as "the live-read equivalent
    pattern" a live connector would follow to reshape a real fetch into the
    same thread-dict shape their fixture ``*_email_thread()`` functions
    already produce. It is exercised directly by
    ``tests/test_live_gmail_reader_ooo_guard.py``. Keep this docstring's
    contract accurate for those readers even though nothing currently calls
    the function itself.
    """

    imap = _imap_connect(readonly=True)
    try:
        status, data = imap.search(
            None, f'(SUBJECT "{tag}") (TEXT "{participant_domain}")'
        )
        uids = data[0].split()
        messages = []
        for uid in uids:
            status, fetched = imap.fetch(uid, "(RFC822)")
            raw_bytes = fetched[0][1]
            message_dict = _message_dict_from_raw(
                raw_bytes, uid, tag=tag, participant_domain=participant_domain
            )
            if message_dict is not None:
                messages.append(message_dict)
        messages.sort(key=lambda m: m["payload"]["headers"][2]["value"])
        return {
            "id": f"live-{tag}-{participant_domain}",
            "historyId": "live",
            "messages": messages,
        }
    finally:
        imap.logout()
