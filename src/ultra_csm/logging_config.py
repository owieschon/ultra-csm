"""Structured JSON logging for the Ultra CSM system."""

from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any


_REDACTED = "[redacted]"
_REDACTED_CONTENT = "[redacted-content]"
_REDACTED_EMAIL = "[redacted-email]"
_REDACTED_SECRET = "[redacted-secret]"

_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}\b")
_TOKEN_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|"
    r"authorization|password|secret)\s*[:=]\s*['\"]?[^'\"\s,;]+"
)

_SENSITIVE_KEY_NAMES = {
    "authorization",
    "accesskey",
    "api-key",
    "api_key",
    "password",
    "token",
}
_SENSITIVE_KEY_SUFFIXES = ("_token", "_secret", "_api_key", "_password")
_CONTENT_KEY_NAMES = {
    "body",
    "content",
    "customer_draft",
    "email_body",
    "raw_message",
    "text",
    "transcript",
}


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in _SENSITIVE_KEY_NAMES or normalized.endswith(_SENSITIVE_KEY_SUFFIXES)


def _is_content_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in _CONTENT_KEY_NAMES or normalized.endswith(("_body", "_content"))


def scrub_log_value(value: Any, *, key: str | None = None) -> Any:
    """Return *value* with PII, customer content, and secrets removed for logs."""

    if key is not None:
        if _is_sensitive_key(key):
            return _REDACTED_SECRET
        if _is_content_key(key):
            return _REDACTED_CONTENT

    if isinstance(value, str):
        scrubbed = _BEARER_RE.sub(f"Bearer {_REDACTED_SECRET}", value)
        scrubbed = _TOKEN_ASSIGNMENT_RE.sub(
            lambda match: f"{match.group(1)}={_REDACTED_SECRET}", scrubbed
        )
        return _EMAIL_RE.sub(_REDACTED_EMAIL, scrubbed)

    if isinstance(value, Mapping):
        return {str(k): scrub_log_value(v, key=str(k)) for k, v in value.items()}

    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return [scrub_log_value(item) for item in value]

    return value


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": scrub_log_value(record.getMessage()),
        }

        # Merge any extra fields the caller passed via `extra={}`.
        # Exclude standard LogRecord attributes so only user-supplied
        # extras appear.
        standard = set(logging.LogRecord("", 0, "", 0, None, None, None).__dict__)
        for key, value in record.__dict__.items():
            if key not in standard and key not in entry:
                entry[key] = scrub_log_value(value, key=key)

        if record.exc_info and record.exc_info[0] is not None:
            entry["exception"] = scrub_log_value(self.formatException(record.exc_info))

        return json.dumps(entry, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger with structured JSON output to stderr.

    Idempotent on repeated calls (returns early if our JSON handler is
    already installed), and also reclaims the root logger from any
    pre-existing plain `StreamHandler`s -- e.g. the MCP SDK's own
    `logging.basicConfig()`, which installs a handler on import before this
    repo gets a chance to run. Left alone, both handlers fire on every
    record and each log line is emitted twice (once plain, once JSON).
    Non-StreamHandler handlers (e.g. a test's custom handler) are left
    untouched.
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers on repeated calls.
    if any(
        isinstance(h, logging.StreamHandler) and isinstance(h.formatter, JSONFormatter)
        for h in root.handlers
    ):
        return

    # Remove any other pre-existing StreamHandler (plain-text, no JSONFormatter)
    # so its output doesn't duplicate ours once we install our own below.
    for existing in list(root.handlers):
        if isinstance(existing, logging.StreamHandler) and not isinstance(
            existing.formatter, JSONFormatter
        ):
            root.removeHandler(existing)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
