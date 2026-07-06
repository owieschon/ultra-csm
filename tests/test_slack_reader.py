"""Offline tests for the Slack internal-comms connector.

Same pattern as tests/test_notion_call_transcripts.py: pure-transform
parse function tested directly, live HTTP path only exercised for the
fail-closed-without-credentials path (Owner Ask boundary).
"""

from __future__ import annotations

import pytest

from ultra_csm.data_plane.contracts import InternalCommsNote
from ultra_csm.data_plane.slack_reader import (
    KnownAccount,
    SlackReadError,
    confirm_slack_channel,
    live_slack_channels,
    parse_channel,
)

_MERIDIAN = KnownAccount(account_id="acct-meridian-fleet", account_name="Meridian Fleet")
_PINNACLE = KnownAccount(account_id="acct-pinnacle-supply", account_name="Pinnacle Supply")

_RAW_MESSAGES = [
    {"type": "message", "user": "U123", "text": "renewal risk flagged, need a plan", "ts": "1750000000.000100"},
    {"type": "message", "user": "U456", "text": "champion went quiet for 2 weeks", "ts": "1750000100.000200"},
    {"type": "channel_join", "user": "U123", "ts": "1749999999.000000"},  # non-message event, must be skipped
]

_DISPLAY_NAMES = {"U123": "Marcus Webb", "U456": "Grace Okafor"}


def test_channel_name_match_proposes_a_candidate():
    pending = parse_channel(
        channel_id="C1",
        channel_name="acct-meridian-fleet-internal",
        raw_messages=_RAW_MESSAGES,
        display_names=_DISPLAY_NAMES,
        known_accounts=(_MERIDIAN, _PINNACLE),
    )
    signals = {c.signal for c in pending.candidates}
    account_ids = {c.account_id for c in pending.candidates}
    assert "channel_name_match" in signals
    assert "acct-meridian-fleet" in account_ids
    assert "acct-pinnacle-supply" not in account_ids


def test_no_channel_name_match_yields_no_candidates():
    pending = parse_channel(
        channel_id="C2",
        channel_name="general",
        raw_messages=_RAW_MESSAGES,
        display_names=_DISPLAY_NAMES,
        known_accounts=(_MERIDIAN, _PINNACLE),
    )
    assert pending.candidates == ()


def test_non_message_events_are_skipped():
    pending = parse_channel(
        channel_id="C1",
        channel_name="acct-meridian-fleet-internal",
        raw_messages=_RAW_MESSAGES,
        display_names=_DISPLAY_NAMES,
        known_accounts=(_MERIDIAN,),
    )
    assert len(pending.messages) == 2  # the channel_join event is excluded
    assert all(m.text for m in pending.messages)


def test_display_names_resolved_and_timestamps_converted():
    pending = parse_channel(
        channel_id="C1",
        channel_name="acct-meridian-fleet-internal",
        raw_messages=_RAW_MESSAGES,
        display_names=_DISPLAY_NAMES,
        known_accounts=(_MERIDIAN,),
    )
    authors = {m.author_display_name for m in pending.messages}
    assert authors == {"Marcus Webb", "Grace Okafor"}
    assert all(m.timestamp.endswith("Z") for m in pending.messages)


def test_confirm_mints_one_internal_comms_note_per_message_only_after_human_pick():
    pending = parse_channel(
        channel_id="C1",
        channel_name="acct-meridian-fleet-internal",
        raw_messages=_RAW_MESSAGES,
        display_names=_DISPLAY_NAMES,
        known_accounts=(_MERIDIAN,),
    )

    notes = confirm_slack_channel(pending, account_id="acct-meridian-fleet", note_id_prefix="slack-C1")

    assert len(notes) == 2
    assert all(isinstance(n, InternalCommsNote) for n in notes)
    assert all(n.source == "slack" for n in notes)
    assert all(n.account_id == "acct-meridian-fleet" for n in notes)
    assert {n.note_id for n in notes} == {"slack-C1-0", "slack-C1-1"}


def test_live_reader_fails_closed_without_credentials(tmp_path):
    empty_creds = tmp_path / "empty-creds.env"
    empty_creds.write_text("", encoding="utf-8")

    with pytest.raises(SlackReadError, match="ULTRA_CSM_SLACK_BOT_TOKEN"):
        live_slack_channels(known_accounts=(_MERIDIAN,), creds_path=str(empty_creds))
