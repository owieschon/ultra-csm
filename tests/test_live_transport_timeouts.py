"""Regression coverage for the writer-path timeout fix (R2 finding #1)."""

from __future__ import annotations

from ultra_csm.agent1.slot_a import AnthropicCaseNoteClassifier
from ultra_csm.agent1.slot_b import AnthropicReasonDraftWriter
from ultra_csm.llm_transport import (
    CLAUDE_CODE_DEFAULT_TIMEOUT_S,
    TIMEOUT_ENV_VAR,
    TRANSPORT_ENV_VAR,
)


def test_writer_resolves_claude_code_timeout(monkeypatch):
    # Reproduces R2 finding #1: the writer previously passed the flat 30s
    # LIVE_TIMEOUT_S to the claude_code transport and aborted on draw 1.
    monkeypatch.setenv(TRANSPORT_ENV_VAR, "claude_code")
    monkeypatch.delenv(TIMEOUT_ENV_VAR, raising=False)

    writer = AnthropicReasonDraftWriter(model_id="claude-haiku-4-5")

    assert writer._transport._timeout_s == CLAUDE_CODE_DEFAULT_TIMEOUT_S


def test_slot_a_classifier_resolves_claude_code_timeout(monkeypatch):
    monkeypatch.setenv(TRANSPORT_ENV_VAR, "claude_code")
    monkeypatch.delenv(TIMEOUT_ENV_VAR, raising=False)

    classifier = AnthropicCaseNoteClassifier(model_id="claude-haiku-4-5")

    assert classifier._transport._timeout_s == CLAUDE_CODE_DEFAULT_TIMEOUT_S


def test_writer_honors_timeout_env_override(monkeypatch):
    monkeypatch.setenv(TRANSPORT_ENV_VAR, "claude_code")
    monkeypatch.setenv(TIMEOUT_ENV_VAR, "45")

    writer = AnthropicReasonDraftWriter(model_id="claude-haiku-4-5")

    assert writer._transport._timeout_s == 45.0
