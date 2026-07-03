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
    """Configure the root logger with structured JSON output to stderr."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers on repeated calls.
    if any(
        isinstance(h, logging.StreamHandler) and isinstance(h.formatter, JSONFormatter)
        for h in root.handlers
    ):
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
