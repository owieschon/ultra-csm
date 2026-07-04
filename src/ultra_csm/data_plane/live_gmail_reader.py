"""Live Gmail read adapter for narrative-arc email evidence.

Reads real IMAP messages back into the exact same Gmail ``users.threads.get``
-shaped dict the fixture comms modules (``comms_fixtures.py`` and its arc
siblings) already produce, so the existing, already-tested extraction
functions (``pinehill_communication_signals`` etc.) consume live data through
an unmodified code path -- pass the live thread dict as their optional
``thread=`` argument instead of letting them default to the fixture.

Auth: IMAP with an app password (``ULTRA_CSM_GMAIL_APP_PASSWORD`` /
``ULTRA_CSM_GMAIL_SENDER`` in the credentials env file). Read-only: this
module only ever opens the mailbox with ``readonly=True``.
"""

from __future__ import annotations

import email.header
import email.utils
import imaplib
import os
from email import message_from_bytes
from email.message import Message


def _imap_connect(readonly: bool = True) -> imaplib.IMAP4_SSL:
    addr, pw = "", ""
    creds_path = os.path.expanduser("~/ultra-csm-live-creds.env")
    for line in open(creds_path):
        line = line.strip()
        if line.startswith("ULTRA_CSM_GMAIL_SENDER="):
            addr = line.split("=", 1)[1].strip()
        if line.startswith("ULTRA_CSM_GMAIL_APP_PASSWORD="):
            pw = line.split("=", 1)[1].strip()
    if not addr or not pw:
        raise RuntimeError(
            "ULTRA_CSM_GMAIL_SENDER/ULTRA_CSM_GMAIL_APP_PASSWORD missing from "
            f"{creds_path}"
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


def live_email_thread(*, tag: str, participant_domain: str) -> dict:
    """Fetch every live INBOX message tagged ``tag`` involving
    ``participant_domain`` (e.g. ``pinehill-transport.example``), return it
    shaped exactly like the fixture modules' ``*_email_thread()`` output:
    ``{"id": ..., "historyId": ..., "messages": [...]}`` with each message
    carrying ``payload.headers`` (From/To/Date/Subject) and
    ``payload.body.data`` -- the same fields the existing
    ``*_communication_signals`` extraction functions already read.

    Read-only. Does not modify the mailbox (opens with readonly=True).
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
            msg = message_from_bytes(raw_bytes)
            from_addr = _decode_header(msg.get("From"))
            to_addr = _decode_header(msg.get("To"))
            subject = _decode_header(msg.get("Subject"))
            date_hdr = msg.get("Date")
            parsed_date = email.utils.parsedate_to_datetime(date_hdr)
            iso_date = parsed_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            message_id = msg.get("Message-ID", uid.decode())
            messages.append({
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
            })
        messages.sort(key=lambda m: m["payload"]["headers"][2]["value"])
        return {
            "id": f"live-{tag}-{participant_domain}",
            "historyId": "live",
            "messages": messages,
        }
    finally:
        imap.logout()
