"""Live Slack read adapter for internal account comms.

Runtime-facing (imported by the API layer, like live_gmail_reader.py and
notion_call_transcripts.py), not an authoring surface. Read-only: this
module only ever calls Slack's read (GET) Web API methods, never a
chat.postMessage or other write endpoint.

Endpoints (verified against docs.slack.dev, 2026-07-05 -- api.slack.com's
/methods/* URLs 302-redirect there now):
- GET /api/users.conversations -- channels the bot token is a member of
  (scopes: channels:read, groups:read). Membership is the curation
  mechanism: an account's channel only appears here once a human has
  `/invite`d the bot to it -- see docs/ (Owner setup), not something this
  module decides.
- GET /api/conversations.history -- messages in one channel (scopes:
  channels:history, groups:history). Each message: {type, user, text, ts}.
- GET /api/users.info -- resolve a Slack user ID to real_name/display_name
  (scope: users:read). Email requires the ADDITIONAL users:read.email
  scope, not required here: account attribution comes from channel name
  (see below), not from matching a message author's identity, so a
  display name is sufficient for InternalCommsNote.author.

Slack's Web API returns HTTP 200 with an ``"ok": false`` body on logical
errors (not just HTTP error codes) -- checked explicitly below, not
inferred from status code alone.

Account identity resolution: unlike a Notion meeting title (arbitrary,
per-meeting), a Slack channel is a stable, human-curated unit -- a human
already decided this channel is relevant by inviting the bot to it. So
matching is coarser-grained than the transcript case: propose an account
match ONCE per channel (by channel name, same title-match style as
notion_call_transcripts.py, sharing AccountAttributionCandidate), and once
a human confirms that one mapping, every message in the channel resolves
to that account -- not a per-message confirmation.

Auth: ``ULTRA_CSM_SLACK_BOT_TOKEN`` in ~/ultra-csm-live-creds.env.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib import request as urllib_request
from urllib.parse import urlencode

from ultra_csm.data_plane.contracts import AccountAttributionCandidate, InternalCommsNote

_CREDS_PATH = "~/ultra-csm-live-creds.env"
_TOKEN_KEY = "ULTRA_CSM_SLACK_BOT_TOKEN"
_SLACK_API_BASE = "https://slack.com/api"


class SlackReadError(RuntimeError):
    """Raised when a live Slack read cannot proceed (missing creds, API error)."""


@dataclass(frozen=True)
class KnownAccount:
    """Same minimal shape as notion_call_transcripts.KnownAccount -- not
    shared directly to avoid coupling two independent connectors to each
    other, only to the common contracts.py types they both mint."""

    account_id: str
    account_name: str


@dataclass(frozen=True)
class SlackMessage:
    author_display_name: str
    text: str
    timestamp: str  # ISO-8601, converted from Slack's "ts" epoch-seconds string


@dataclass(frozen=True)
class PendingSlackChannel:
    """A live-pulled channel's messages awaiting human confirmation of
    which account they belong to. One confirmation covers every message
    in the channel -- see module docstring."""

    channel_id: str
    channel_name: str
    messages: tuple[SlackMessage, ...]
    candidates: tuple[AccountAttributionCandidate, ...]


def _read_token(creds_path: str | None = None) -> str:
    path = os.path.expanduser(creds_path or _CREDS_PATH)
    if not os.path.exists(path):
        raise SlackReadError(f"missing credentials file: {path}")
    for line in open(path):
        line = line.strip()
        if line.startswith(f"{_TOKEN_KEY}="):
            value = line.split("=", 1)[1].strip()
            if value:
                return value
    raise SlackReadError(f"missing {_TOKEN_KEY} in {path}")


def _slack_get(method: str, *, token: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    url = f"{_SLACK_API_BASE}/{method}"
    if params:
        url = f"{url}?{urlencode(params)}"
    req = urllib_request.Request(
        url, headers={"Authorization": f"Bearer {token}", "accept": "application/json"}, method="GET"
    )
    with urllib_request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https host, read-only GET.
        body = json.loads(resp.read().decode("utf-8"))
    # Slack returns HTTP 200 even on logical failure; "ok" is the real signal.
    if not body.get("ok", False):
        raise SlackReadError(f"Slack API {method} failed: {body.get('error', 'unknown error')}")
    return body


def _ts_to_iso(ts: str) -> str:
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z"


def _list_member_channels(*, token: str) -> list[dict[str, Any]]:
    body = _slack_get(
        "users.conversations", token=token, params={"types": "public_channel,private_channel"}
    )
    return body.get("channels", [])


def _channel_history(*, token: str, channel_id: str) -> list[dict[str, Any]]:
    body = _slack_get("conversations.history", token=token, params={"channel": channel_id})
    return body.get("messages", [])


def _resolve_display_name(*, token: str, user_id: str) -> str:
    body = _slack_get("users.info", token=token, params={"user": user_id})
    profile = body.get("user", {}).get("profile", {})
    return profile.get("real_name") or profile.get("display_name") or user_id


def _channel_name_match_candidates(
    channel_name: str, known_accounts: tuple[KnownAccount, ...]
) -> tuple[AccountAttributionCandidate, ...]:
    name_lower = channel_name.lower().replace("-", " ").replace("_", " ")
    return tuple(
        AccountAttributionCandidate(
            account_id=account.account_id,
            confidence=0.7,
            reason=f"channel name {channel_name!r} contains account name {account.account_name!r}",
            signal="channel_name_match",
        )
        for account in known_accounts
        if account.account_name.lower() in name_lower
    )


def parse_channel(
    *,
    channel_id: str,
    channel_name: str,
    raw_messages: list[dict[str, Any]],
    display_names: dict[str, str],
    known_accounts: tuple[KnownAccount, ...],
) -> PendingSlackChannel:
    """Pure transform: raw channel metadata + already-fetched messages +
    already-resolved user display names -> a PendingSlackChannel with
    candidate account attributions. Split from the live fetch so this is
    independently offline-testable against a captured fixture."""

    messages = tuple(
        SlackMessage(
            author_display_name=display_names.get(msg.get("user", ""), msg.get("user", "unknown")),
            text=msg.get("text", ""),
            timestamp=_ts_to_iso(msg["ts"]),
        )
        for msg in raw_messages
        if msg.get("type") == "message" and "ts" in msg
    )
    candidates = _channel_name_match_candidates(channel_name, known_accounts)
    return PendingSlackChannel(
        channel_id=channel_id, channel_name=channel_name, messages=messages, candidates=candidates
    )


def live_slack_channels(
    *, known_accounts: tuple[KnownAccount, ...], creds_path: str | None = None
) -> tuple[PendingSlackChannel, ...]:
    """Live, read-only pull: every channel the bot is a member of, with its
    message history and proposed (never auto-confirmed) account
    candidates. Raises SlackReadError if ULTRA_CSM_SLACK_BOT_TOKEN is
    absent -- no live pull without a real credential."""

    token = _read_token(creds_path)
    channels = _list_member_channels(token=token)
    pending: list[PendingSlackChannel] = []
    for channel in channels:
        channel_id = channel["id"]
        raw_messages = _channel_history(token=token, channel_id=channel_id)
        user_ids = {msg["user"] for msg in raw_messages if msg.get("type") == "message" and "user" in msg}
        display_names = {uid: _resolve_display_name(token=token, user_id=uid) for uid in user_ids}
        pending.append(
            parse_channel(
                channel_id=channel_id,
                channel_name=channel.get("name", channel_id),
                raw_messages=raw_messages,
                display_names=display_names,
                known_accounts=known_accounts,
            )
        )
    return tuple(pending)


def live_channel_messages(*, channel_id: str, creds_path: str | None = None) -> PendingSlackChannel:
    """Live, read-only pull for ONE already-confirmed channel -- the
    ingest path's entry point (comms_mapping.py): given a
    comms_source_mapping row, fetch that specific channel's messages
    directly, skipping the membership-list + candidate-matching steps in
    live_slack_channels (unnecessary once a human has already confirmed
    the account). channel_name is not independently known here (no
    users.conversations call), so candidates is always empty by
    construction -- the caller already has the confirmed account_id."""

    token = _read_token(creds_path)
    raw_messages = _channel_history(token=token, channel_id=channel_id)
    user_ids = {msg["user"] for msg in raw_messages if msg.get("type") == "message" and "user" in msg}
    display_names = {uid: _resolve_display_name(token=token, user_id=uid) for uid in user_ids}
    return parse_channel(
        channel_id=channel_id,
        channel_name=channel_id,
        raw_messages=raw_messages,
        display_names=display_names,
        known_accounts=(),
    )


def confirm_slack_channel(
    pending: PendingSlackChannel, *, account_id: str, note_id_prefix: str
) -> tuple[InternalCommsNote, ...]:
    """Human-confirmed: mint an InternalCommsNote per message only after a
    CSM has picked (or overridden) the account for this channel -- this
    connector never does so on its own (see module docstring). One
    confirmation covers every message already fetched for the channel."""

    return tuple(
        InternalCommsNote(
            note_id=f"{note_id_prefix}-{i}",
            account_id=account_id,
            author=message.author_display_name,
            timestamp=message.timestamp,
            content=message.text,
            source="slack",
        )
        for i, message in enumerate(pending.messages)
    )
