"""Transport abstraction for live LLM calls.

The repo defaults to direct API use for public portability, but selected lanes
can route through the local Claude Code CLI by setting
``ULTRA_CSM_LLM_TRANSPORT=claude_code``. Both transports preserve the caller's
system prompt verbatim.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Protocol

TRANSPORT_ENV_VAR = "ULTRA_CSM_LLM_TRANSPORT"
DEFAULT_LLM_TRANSPORT = "anthropic_api"
CLAUDE_CODE_TRANSPORT = "claude_code"


@dataclass(frozen=True)
class TransportResponse:
    text: str
    transport: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw: Any | None = None


class MessageTransport(Protocol):
    name: str

    def complete(
        self,
        *,
        model_id: str,
        system_prompt: str,
        user_text: str,
        max_tokens: int,
    ) -> TransportResponse: ...


def configured_transport_name() -> str:
    return os.environ.get(TRANSPORT_ENV_VAR, DEFAULT_LLM_TRANSPORT).strip() or DEFAULT_LLM_TRANSPORT


def resolve_message_transport(
    *,
    client: Any | None = None,
    timeout_s: float | None = None,
    max_retries: int | None = None,
    transport_name: str | None = None,
    runner: Any | None = None,
) -> MessageTransport:
    name = transport_name or configured_transport_name()
    if name == DEFAULT_LLM_TRANSPORT:
        return AnthropicMessagesTransport(
            client=client,
            timeout_s=timeout_s,
            max_retries=max_retries,
        )
    if name == CLAUDE_CODE_TRANSPORT:
        return ClaudeCodeMessagesTransport(
            timeout_s=timeout_s,
            runner=runner,
        )
    raise ValueError(
        f"unsupported {TRANSPORT_ENV_VAR}={name!r}; expected "
        f"{DEFAULT_LLM_TRANSPORT!r} or {CLAUDE_CODE_TRANSPORT!r}"
    )


class AnthropicMessagesTransport:
    name = DEFAULT_LLM_TRANSPORT

    def __init__(
        self,
        *,
        client: Any | None = None,
        timeout_s: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        if client is None:  # pragma: no cover - live lane
            from anthropic import Anthropic

            kwargs: dict[str, Any] = {}
            if timeout_s is not None:
                kwargs["timeout"] = timeout_s
            if max_retries is not None:
                kwargs["max_retries"] = max_retries
            client = Anthropic(**kwargs)
        self._client = client

    def complete(
        self,
        *,
        model_id: str,
        system_prompt: str,
        user_text: str,
        max_tokens: int,
    ) -> TransportResponse:
        msg = self._client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_text}],
        )
        usage = getattr(msg, "usage", None)
        return TransportResponse(
            text=_anthropic_text(msg),
            transport=self.name,
            input_tokens=_coerce_optional_int(getattr(usage, "input_tokens", None)),
            output_tokens=_coerce_optional_int(getattr(usage, "output_tokens", None)),
            raw=msg,
        )


class ClaudeCodeMessagesTransport:
    name = CLAUDE_CODE_TRANSPORT

    def __init__(
        self,
        *,
        timeout_s: float | None = None,
        runner: Any | None = None,
    ) -> None:
        self._timeout_s = timeout_s
        self._runner = runner or subprocess.run

    def complete(
        self,
        *,
        model_id: str,
        system_prompt: str,
        user_text: str,
        max_tokens: int,
    ) -> TransportResponse:
        # --safe-mode, not --bare: both isolate CLAUDE.md/hooks/plugins from the
        # prompt, but --bare forces ANTHROPIC_API_KEY-only auth (never reads
        # OAuth/keychain), which defeats this transport's entire purpose of
        # running on the caller's subscription instead of the metered API.
        cmd = [
            "claude",
            "--safe-mode",
            "--print",
            "--output-format",
            "json",
            "--permission-mode",
            "dontAsk",
            "--tools",
            "",
            "--no-session-persistence",
            "--model",
            model_id,
            "--system-prompt",
            system_prompt,
            user_text,
        ]
        completed = self._runner(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=self._timeout_s,
        )
        payload = json.loads(completed.stdout)
        usage = _extract_usage_dict(payload)
        return TransportResponse(
            text=_extract_claude_code_text(payload),
            transport=self.name,
            input_tokens=_coerce_optional_int(usage.get("input_tokens")),
            output_tokens=_coerce_optional_int(usage.get("output_tokens")),
            raw=payload,
        )


def _anthropic_text(msg: Any) -> str:
    return "".join(
        block.text
        for block in getattr(msg, "content", ())
        if getattr(block, "type", None) == "text"
    ).strip()


def _extract_claude_code_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, list):
        texts = [_extract_claude_code_text(item) for item in payload]
        return "\n".join(text for text in texts if text).strip()
    if not isinstance(payload, dict):
        return str(payload).strip()

    for key in ("result", "output", "text", "completion"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    content = payload.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        texts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())
            elif isinstance(item, str) and item.strip():
                texts.append(item.strip())
        if texts:
            return "\n".join(texts)
    message = payload.get("message")
    if message is not None:
        text = _extract_claude_code_text(message)
        if text:
            return text
    messages = payload.get("messages")
    if isinstance(messages, list):
        for item in reversed(messages):
            text = _extract_claude_code_text(item)
            if text:
                return text
    raise ValueError("claude_code transport returned no assistant text")


def _extract_usage_dict(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    usage = payload.get("usage")
    if isinstance(usage, dict):
        return usage
    result = payload.get("result")
    if isinstance(result, dict):
        usage = result.get("usage")
        if isinstance(usage, dict):
            return usage
    message = payload.get("message")
    if isinstance(message, dict):
        usage = message.get("usage")
        if isinstance(usage, dict):
            return usage
    return {}


def _coerce_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
