from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import json

from ultra_csm import api
from ultra_csm.operating_monitor import (
    SentryMonitor,
    evaluate_operating_alarms,
    send_alarms,
)


class RecordingTransport:
    def __init__(self) -> None:
        self.envelopes: list[dict[str, object]] = []

    def send_envelope(self, *, url: str, body: bytes, auth_header: str) -> None:
        lines = body.decode("utf-8").splitlines()
        self.envelopes.append({
            "url": url,
            "auth": auth_header,
            "header": json.loads(lines[0]),
            "item": json.loads(lines[1]),
            "payload": json.loads(lines[2]),
        })


def test_sentry_monitor_sends_check_in_envelope():
    transport = RecordingTransport()
    monitor = SentryMonitor(
        dsn="https://public@example.invalid/42",
        transport=transport,
    )

    result = monitor.capture_check_in(
        monitor_slug="ultra-csm-operating-daily",
        status="in_progress",
        schedule="30 7 * * *",
    )

    assert result.sent
    assert result.check_in_id
    envelope = transport.envelopes[0]
    assert envelope["url"] == "https://example.invalid/api/42/envelope/"
    assert envelope["item"] == {"type": "check_in"}
    payload = envelope["payload"]
    assert payload["monitor_slug"] == "ultra-csm-operating-daily"
    assert payload["status"] == "in_progress"
    assert payload["monitor_config"]["schedule"] == {
        "type": "crontab",
        "value": "30 7 * * *",
    }


def test_sentry_monitor_noops_without_dsn():
    transport = RecordingTransport()
    monitor = SentryMonitor(dsn=None, transport=transport)

    result = monitor.capture_event(message="boom")

    assert not result.sent
    assert result.reason == "SENTRY_DSN not set"
    assert transport.envelopes == []


def test_operating_alarms_detect_missed_run_and_cost_budget():
    now = datetime(2026, 7, 6, 15, 0, tzinfo=UTC)
    entries = (
        {"date": "2026-07-04", "cost_usd": 0.1},
        {"date": "2026-07-06", "cost_usd": 11.25},
    )

    alarms = evaluate_operating_alarms(
        entries,
        now=now,
        daily_cost_budget_usd=10.0,
        max_run_age=timedelta(hours=12),
    )

    assert [alarm.kind for alarm in alarms] == ["cost_budget"]
    assert alarms[0].payload["cost_usd"] == 11.25

    missed = evaluate_operating_alarms(
        ({"date": "2026-07-04", "cost_usd": 0.1},),
        now=now,
        daily_cost_budget_usd=10.0,
        max_run_age=timedelta(hours=30),
    )
    assert [alarm.kind for alarm in missed] == ["missed_run"]


def test_send_alarms_captures_sentry_events():
    transport = RecordingTransport()
    monitor = SentryMonitor(
        dsn="https://public@example.invalid/42",
        transport=transport,
    )
    alarms = evaluate_operating_alarms(
        (),
        now=datetime(2026, 7, 6, tzinfo=UTC),
        daily_cost_budget_usd=10.0,
    )

    assert send_alarms(monitor, alarms) == 1
    envelope = transport.envelopes[0]
    assert envelope["item"] == {"type": "event"}
    assert envelope["payload"]["tags"] == {
        "alarm": "missed_run",
        "component": "operating-daily",
    }


def test_api_unhandled_exception_reports_to_monitor(monkeypatch):
    captured: list[dict[str, object]] = []

    class FakeMonitor:
        def capture_event(self, **kwargs):
            captured.append(kwargs)

    class FakeUrl:
        path = "/boom"

    class FakeRequest:
        url = FakeUrl()

    monkeypatch.setattr(api, "monitor_from_env", lambda: FakeMonitor())

    response = asyncio.run(
        api.unhandled_exception_handler(FakeRequest(), RuntimeError("boom"))
    )

    assert response.status_code == 500
    assert captured == [{
        "message": "Ultra CSM API unhandled exception",
        "tags": {"component": "api", "path": "/boom"},
        "extra": {"exception_type": "RuntimeError"},
    }]
