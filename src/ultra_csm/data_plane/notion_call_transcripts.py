"""Live Notion read adapter for customer call-transcript evidence.

Distinct from ``notion_reader.py``, which is an AUTHORING front door only
(``knowledge/`` org-pack/playbook/content-catalog authoring, never imported
by the runtime -- see that module's own docstring). This module reads
CUSTOMER EVIDENCE at request time -- call/meeting transcripts -- the same
runtime-facing role as ``live_gmail_reader.py``, and is imported by the API
layer, not the authoring render pipeline. Deliberately does not share code
with notion_reader.py (even though both talk to the Notion API) to keep
that module's "authoring only" boundary literal, not just documented.

Two-step live fetch (Notion's query-meeting-notes response carries pointers
to related blocks, not transcript text directly -- verified against
https://developers.notion.com/reference/query-meeting-notes, 2026-07-05):
1. POST /v1/blocks/meeting_notes/query -- title/attendee/date filters,
   returns meeting_notes blocks with a nested
   ``children: {summary_block_id, notes_block_id, transcript_block_id}``
   object (each an optional UUID string; NOT a flat list of IDs).
2. GET /v1/blocks/{transcript_block_id}/children -- the transcript's own
   content. (verify-at-runtime) The block type(s) returned here are NOT
   documented by Notion's public reference -- only that "transcript" was
   renamed to "meeting_notes" in API version 2026-03-11, with no schema
   given for the transcript block's own children. Parsed generically below
   (any block type carrying a ``rich_text`` field), not assumed to be
   ``paragraph`` specifically.

Auth: ``ULTRA_CSM_NOTION_TOKEN`` in ~/ultra-csm-live-creds.env (same
credential as the authoring edge -- one Notion integration, two
capabilities; read inline here rather than imported from notion_reader.py,
for the same "keep the authoring boundary literal" reason as above).
Requires "AI meeting notes" enabled for the integration's user (a
workspace/plan capability, not just the integration token) -- Owner Ask,
verify-at-runtime.

query-meeting-notes needs Notion-Version 2026-03-11, one version newer
than notion_reader.py's 2025-09-03 -- passed per-call, never a global
version bump, so the already-tested org_pack/playbooks/content_catalog
calls are untouched.

Account identity resolution (verify-at-runtime, owner-ratified 2026-07-05):
verified against the full documented response schema that NO field --
not ``calendar_event.attendees`` (internal Notion user UUIDs only), not
``recording``, not ``created_by``/``last_edited_by`` -- carries an external
attendee's email or name. So this module never claims a structured email
match; it produces CANDIDATE account attributions from two signals of
different reliability, both requiring human confirmation before a
CommunicationSignal is minted (mirrors source_mapping.py's propose-then-
confirm discipline for identity-ambiguous external data, without reusing
its field-mapping-specific dataclasses -- this is record-level identity
attribution, a different problem from source_mapping's field-level schema
mapping):
  - "title_match": the meeting title contains a known account's name.
    Documented, verified capability (title filter supports
    string_contains).
  - "transcript_text_match": the fetched transcript text contains a known
    contact's email or name. Unverified reliability -- whether Notion's
    transcription inherits speaker-email/name attribution from the
    underlying call platform is not documented; attempted best-effort,
    never assumed to work.

Read-only: this module only ever issues query/read requests, never a
page/block write endpoint.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import request as urllib_request

from ultra_csm.data_plane.contracts import AccountAttributionCandidate, CommunicationSignal, CRMContact

_CREDS_PATH = "~/ultra-csm-live-creds.env"
_TOKEN_KEY = "ULTRA_CSM_NOTION_TOKEN"
_NOTION_API_BASE = "https://api.notion.com/v1"
_MEETING_NOTES_VERSION = "2026-03-11"

# No prior art for channel="call"/"meeting" CommunicationSignal.direction
# anywhere in this codebase (grepped 2026-07-05: zero existing usages). A
# call has no natural inbound/outbound sense the way an email reply does;
# "inbound" is a convention this module sets, not a meaningful distinction
# recovered from Notion data. Not widening the Literal type to add a
# neutral third value without the sanctioning process contracts.py's own
# docstring requires (docs/UNIVERSE_V2_CONVENTIONS.md §7) for such a small,
# cosmetic-only need.
_CALL_SIGNAL_DIRECTION = "inbound"


class NotionTranscriptReadError(RuntimeError):
    """Raised when a live transcript read cannot proceed (missing creds, bad shape)."""


@dataclass(frozen=True)
class KnownAccount:
    """The minimal slice of account identity this module needs to propose
    candidates against -- supplied by the caller (the API layer already
    has this data); this connector does no DB access of its own, matching
    the rest of the data_plane's pure-transform connector style."""

    account_id: str
    account_name: str
    contacts: tuple[CRMContact, ...] = ()


@dataclass(frozen=True)
class PendingCallTranscript:
    """A live-pulled transcript awaiting human confirmation of which
    account it belongs to. Never a CommunicationSignal until confirmed --
    see module docstring."""

    meeting_note_id: str
    title: str
    occurred_at: str | None
    transcript_text: str
    candidates: tuple[AccountAttributionCandidate, ...]


def _unwrap_placeholder_brackets(value: str) -> str:
    """Strip one enclosing ``<...>`` pair -- a real, observed convention in
    this creds file (the Rocketlane key carries the same wrapping),
    sometimes left in place around the real pasted value. Only strips a
    genuinely matching pair."""

    if len(value) >= 2 and value.startswith("<") and value.endswith(">"):
        return value[1:-1]
    return value


def _read_token(creds_path: str | None = None) -> str:
    path = os.path.expanduser(creds_path or _CREDS_PATH)
    if not os.path.exists(path):
        raise NotionTranscriptReadError(f"missing credentials file: {path}")
    for line in open(path):
        line = line.strip()
        if line.startswith(f"{_TOKEN_KEY}="):
            value = _unwrap_placeholder_brackets(line.split("=", 1)[1].strip())
            if value:
                return value
    raise NotionTranscriptReadError(f"missing {_TOKEN_KEY} in {path}")


def _notion_request(
    url: str, *, token: str, method: str, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": _MEETING_NOTES_VERSION,
        "accept": "application/json",
    }
    if data is not None:
        headers["content-type"] = "application/json"
    req = urllib_request.Request(url, data=data, headers=headers, method=method)
    with urllib_request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https host, read-only.
        return json.loads(resp.read().decode("utf-8"))


def _rich_text_plain(rich_text: list[dict[str, Any]]) -> str:
    return "".join(fragment.get("plain_text", "") for fragment in rich_text)


def _query_meeting_notes(*, token: str, title_contains: str | None = None) -> list[dict[str, Any]]:
    body: dict[str, Any] = {}
    if title_contains:
        body["filter"] = {
            "property": "title",
            "filter": {"operator": "string_contains", "value": {"type": "exact", "value": title_contains}},
        }
    response = _notion_request(
        f"{_NOTION_API_BASE}/blocks/meeting_notes/query", token=token, method="POST", body=body
    )
    return response.get("results", [])


def _transcript_block_id(meeting_note: dict[str, Any]) -> str | None:
    children = meeting_note.get("meeting_notes", {}).get("children", {})
    return children.get("transcript_block_id")


def _fetch_transcript_text(*, token: str, transcript_block_id: str) -> str:
    """Generic block-text extraction: pulls ``rich_text`` from whatever
    block type(s) come back, rather than assuming ``paragraph`` -- see
    module docstring's verify-at-runtime note on the undocumented
    transcript block shape."""

    response = _notion_request(
        f"{_NOTION_API_BASE}/blocks/{transcript_block_id}/children", token=token, method="GET"
    )
    lines: list[str] = []
    for block in response.get("results", []):
        block_type = block.get("type")
        payload = block.get(block_type, {}) if block_type else {}
        rich_text = payload.get("rich_text")
        if rich_text:
            text = _rich_text_plain(rich_text)
            if text:
                lines.append(text)
    return "\n\n".join(lines)


def _title_match_candidates(
    title: str, known_accounts: tuple[KnownAccount, ...]
) -> tuple[AccountAttributionCandidate, ...]:
    title_lower = title.lower()
    return tuple(
        AccountAttributionCandidate(
            account_id=account.account_id,
            confidence=0.7,
            reason=f"meeting title contains account name {account.account_name!r}",
            signal="title_match",
        )
        for account in known_accounts
        if account.account_name.lower() in title_lower
    )


def _transcript_text_match_candidates(
    transcript_text: str, known_accounts: tuple[KnownAccount, ...]
) -> tuple[AccountAttributionCandidate, ...]:
    """Best-effort scan for a known contact's email or name in the
    transcript text. Lower confidence than a title match: whether Notion's
    transcription carries speaker email/name attribution at all is
    unverified (see module docstring)."""

    text_lower = transcript_text.lower()
    candidates: list[AccountAttributionCandidate] = []
    for account in known_accounts:
        for contact in account.contacts:
            if contact.email and contact.email.lower() in text_lower:
                candidates.append(
                    AccountAttributionCandidate(
                        account_id=account.account_id,
                        confidence=0.5,
                        reason=f"transcript text contains contact email {contact.email!r}",
                        signal="transcript_text_match",
                    )
                )
            elif contact.name and contact.name.lower() in text_lower:
                candidates.append(
                    AccountAttributionCandidate(
                        account_id=account.account_id,
                        confidence=0.3,
                        reason=f"transcript text contains contact name {contact.name!r}",
                        signal="transcript_text_match",
                    )
                )
    return tuple(candidates)


def parse_meeting_note(
    meeting_note: dict[str, Any],
    *,
    transcript_text: str,
    known_accounts: tuple[KnownAccount, ...],
) -> PendingCallTranscript:
    """Pure transform: a raw meeting_notes block + its already-fetched
    transcript text -> a PendingCallTranscript with candidate account
    attributions. Split from the live fetch so this is independently
    offline-testable against a captured fixture."""

    title = _rich_text_plain(meeting_note.get("meeting_notes", {}).get("title", []))
    calendar_event = meeting_note.get("meeting_notes", {}).get("calendar_event") or {}
    occurred_at = calendar_event.get("start_time")
    candidates = _title_match_candidates(title, known_accounts) + _transcript_text_match_candidates(
        transcript_text, known_accounts
    )
    return PendingCallTranscript(
        meeting_note_id=meeting_note["id"],
        title=title,
        occurred_at=occurred_at,
        transcript_text=transcript_text,
        candidates=candidates,
    )


def live_call_transcripts(
    *,
    known_accounts: tuple[KnownAccount, ...],
    title_contains: str | None = None,
    creds_path: str | None = None,
) -> tuple[PendingCallTranscript, ...]:
    """Live, read-only pull: query meeting notes, fetch each one's
    transcript, and propose (never auto-confirm) account candidates.
    Raises NotionTranscriptReadError if ULTRA_CSM_NOTION_TOKEN is absent --
    no live pull is attempted without a real credential (same discipline
    as notion_reader.py's live_authoring_payload)."""

    token = _read_token(creds_path)
    meeting_notes = _query_meeting_notes(token=token, title_contains=title_contains)
    pending: list[PendingCallTranscript] = []
    for meeting_note in meeting_notes:
        transcript_block_id = _transcript_block_id(meeting_note)
        transcript_text = (
            _fetch_transcript_text(token=token, transcript_block_id=transcript_block_id)
            if transcript_block_id
            else ""
        )
        pending.append(
            parse_meeting_note(meeting_note, transcript_text=transcript_text, known_accounts=known_accounts)
        )
    return tuple(pending)


def live_single_meeting_transcript(
    *, meeting_note_id: str, creds_path: str | None = None
) -> PendingCallTranscript:
    """Live, read-only pull for ONE already-confirmed meeting note -- the
    ingest path's entry point (comms_mapping.py): given a
    comms_source_mapping row, fetch that specific meeting note directly
    via GET /v1/blocks/{id} (verified identical shape to a query-
    meeting-notes result item, 2026-07-05), skipping the broad query +
    candidate-matching steps in live_call_transcripts (unnecessary once a
    human has already confirmed the account). known_accounts is empty by
    construction -- the caller already has the confirmed account_id."""

    token = _read_token(creds_path)
    meeting_note = _notion_request(f"{_NOTION_API_BASE}/blocks/{meeting_note_id}", token=token, method="GET")
    transcript_block_id = _transcript_block_id(meeting_note)
    transcript_text = (
        _fetch_transcript_text(token=token, transcript_block_id=transcript_block_id)
        if transcript_block_id
        else ""
    )
    return parse_meeting_note(meeting_note, transcript_text=transcript_text, known_accounts=())


def confirm_call_transcript(
    pending: PendingCallTranscript, *, account_id: str, contact_id: str, signal_id: str
) -> CommunicationSignal:
    """Human-confirmed: mint the actual CommunicationSignal only after a
    CSM has picked (or overridden) the account -- this connector never
    does so on its own (see module docstring's identity-resolution note).
    ``contact_id`` is supplied by the caller (informed by the confirm
    action), not guessed by this module."""

    return CommunicationSignal(
        signal_id=signal_id,
        account_id=account_id,
        contact_id=contact_id,
        channel="call",
        direction=_CALL_SIGNAL_DIRECTION,
        timestamp=pending.occurred_at or "",
    )
