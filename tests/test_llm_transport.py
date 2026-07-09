from __future__ import annotations

import json

from ultra_csm.llm_transport import (
    CLAUDE_CODE_TRANSPORT,
    AnthropicMessagesTransport,
    ClaudeCodeMessagesTransport,
    resolve_message_transport,
)


class _FakeAnthropicClient:
    def __init__(self) -> None:
        self.messages = self
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        usage = type("Usage", (), {"input_tokens": 11, "output_tokens": 7})()
        block = type("Block", (), {"type": "text", "text": "{\"ok\":true}"})()
        return type("Msg", (), {"usage": usage, "content": [block]})()


def test_resolve_message_transport_defaults_to_anthropic_for_injected_client():
    client = _FakeAnthropicClient()

    transport = resolve_message_transport(client=client, transport_name="anthropic_api")

    assert isinstance(transport, AnthropicMessagesTransport)
    response = transport.complete(
        model_id="claude-sonnet-5",
        system_prompt="system prompt",
        user_text="user payload",
        max_tokens=123,
    )
    assert response.transport == "anthropic_api"
    assert response.text == "{\"ok\":true}"
    assert response.input_tokens == 11
    assert response.output_tokens == 7
    assert client.calls[0]["system"] == "system prompt"
    assert client.calls[0]["messages"] == [{"role": "user", "content": "user payload"}]


def test_claude_code_transport_builds_expected_command_and_parses_usage():
    calls: list[dict] = []

    def _runner(cmd, **kwargs):
        calls.append({"cmd": cmd, "kwargs": kwargs})
        payload = {
            "result": "{\"reason\":\"ok\",\"cited_evidence_ids\":[\"sig-1\"],\"customer_draft\":\"Hi\"}",
            "usage": {"input_tokens": 101, "output_tokens": 33},
        }
        return type("Completed", (), {"stdout": json.dumps(payload)})()

    transport = ClaudeCodeMessagesTransport(timeout_s=17.5, runner=_runner)
    response = transport.complete(
        model_id="claude-sonnet-5",
        system_prompt="BYTE IDENTICAL SYSTEM",
        user_text='{"request":"payload"}',
        max_tokens=700,
    )

    assert response.transport == CLAUDE_CODE_TRANSPORT
    assert response.input_tokens == 101
    assert response.output_tokens == 33
    assert "\"customer_draft\":\"Hi\"" in response.text
    cmd = calls[0]["cmd"]
    assert cmd[:6] == ["claude", "--safe-mode", "--print", "--output-format", "json", "--permission-mode"]
    assert "--bare" not in cmd  # forces ANTHROPIC_API_KEY-only auth; breaks subscription transport
    assert "--system-prompt" in cmd
    assert "BYTE IDENTICAL SYSTEM" in cmd
    assert cmd[-1] == '{"request":"payload"}'
    assert calls[0]["kwargs"]["timeout"] == 17.5
    assert calls[0]["kwargs"]["check"] is True


def test_claude_code_transport_extracts_text_from_message_shape():
    def _runner(cmd, **kwargs):
        payload = {
            "message": {
                "content": [
                    {"type": "text", "text": "{\"answer\":1}"},
                ],
                "usage": {"input_tokens": 9, "output_tokens": 4},
            }
        }
        return type("Completed", (), {"stdout": json.dumps(payload)})()

    response = ClaudeCodeMessagesTransport(runner=_runner).complete(
        model_id="claude-sonnet-5",
        system_prompt="system",
        user_text="user",
        max_tokens=50,
    )

    assert response.text == "{\"answer\":1}"
    assert response.input_tokens == 9
    assert response.output_tokens == 4
