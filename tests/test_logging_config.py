"""Structured logging redaction tests."""

from __future__ import annotations

import json
import logging

from ultra_csm.logging_config import JSONFormatter


def _formatted_record(message: str, *, extra: dict) -> dict:
    record = logging.LogRecord(
        name="ultra_csm.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return json.loads(JSONFormatter().format(record))


def test_json_formatter_scrubs_pii_content_and_secret_tokens():
    email = "pat.owner@example.com"
    body = "Hi Pat, your renewal risk note belongs only in storage."
    token = "sk-live-SECRET-TOKEN-123456"

    entry = _formatted_record(
        f"relay failed for {email} authorization={token}",
        extra={
            "contact_email": email,
            "body": body,
            "nested": {
                "access_token": token,
                "transcript": "private call transcript",
                "safe_count": 2,
            },
            "events": [{"text": "private Slack message"}, {"owner": email}],
        },
    )
    rendered = json.dumps(entry, sort_keys=True)

    assert email not in rendered
    assert body not in rendered
    assert token not in rendered
    assert "private call transcript" not in rendered
    assert "private Slack message" not in rendered
    assert "[redacted-email]" in rendered
    assert "[redacted-content]" in rendered
    assert "[redacted-secret]" in rendered
    assert entry["nested"]["safe_count"] == 2
