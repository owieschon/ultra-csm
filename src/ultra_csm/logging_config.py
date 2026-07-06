"""Structured JSON logging for the Ultra CSM system."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Merge any extra fields the caller passed via `extra={}`.
        # Exclude standard LogRecord attributes so only user-supplied
        # extras appear.
        standard = set(logging.LogRecord("", 0, "", 0, None, None, None).__dict__)
        for key, value in record.__dict__.items():
            if key not in standard and key not in entry:
                entry[key] = value

        if record.exc_info and record.exc_info[0] is not None:
            entry["exception"] = self.formatException(record.exc_info)

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
