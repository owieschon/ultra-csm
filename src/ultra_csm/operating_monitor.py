"""Monitoring helpers for the unattended operating job.

The runtime path is deliberately stdlib-only. If ``SENTRY_DSN`` is absent, the
monitoring calls become explicit no-ops so a missing external credential cannot
break the daily job. Tests inject a fake transport and assert the exact payloads
that would be sent.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import sys
from typing import Any, Protocol
from urllib import error, parse, request
import uuid

SENTRY_DSN_ENV = "SENTRY_DSN"
SENTRY_MONITOR_SLUG_ENV = "SENTRY_MONITOR_SLUG"
OPERATING_DAILY_COST_BUDGET_ENV = "ULTRA_CSM_DAILY_COST_BUDGET_USD"
DEFAULT_MONITOR_SLUG = "ultra-csm-operating-daily"
DEFAULT_DAILY_COST_BUDGET_USD = 10.0


class SentryTransport(Protocol):
    def send_envelope(self, *, url: str, body: bytes, auth_header: str) -> None: ...


@dataclass(frozen=True)
class SentryDsn:
    public_key: str
    scheme: str
    host: str
    project_id: str

    @classmethod
    def parse(cls, raw: str) -> "SentryDsn":
        parsed = parse.urlparse(raw)
        public_key = parsed.username or ""
        project_id = parsed.path.strip("/").split("/")[-1] if parsed.path else ""
        if not parsed.scheme or not parsed.hostname or not public_key or not project_id:
            raise ValueError("SENTRY_DSN is malformed")
        return cls(
            public_key=public_key,
            scheme=parsed.scheme,
            host=parsed.netloc.rsplit("@", 1)[-1],
            project_id=project_id,
        )

    @property
    def envelope_url(self) -> str:
        return f"{self.scheme}://{self.host}/api/{self.project_id}/envelope/"

    @property
    def auth_header(self) -> str:
        return (
            "Sentry sentry_version=7, "
            f"sentry_key={self.public_key}, sentry_client=ultra-csm/phase9"
        )


class HttpSentryTransport:
    def send_envelope(self, *, url: str, body: bytes, auth_header: str) -> None:
        req = request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/x-sentry-envelope",
                "X-Sentry-Auth": auth_header,
            },
        )
        with request.urlopen(req, timeout=10) as response:
            response.read()


@dataclass(frozen=True)
class MonitorResult:
    sent: bool
    check_in_id: str | None = None
    reason: str | None = None


class SentryMonitor:
    def __init__(
        self,
        *,
        dsn: str | None,
        environment: str = "live",
        release: str | None = None,
        transport: SentryTransport | None = None,
    ) -> None:
        self._raw_dsn = dsn
        self._environment = environment
        self._release = release
        self._transport = transport or HttpSentryTransport()

    @property
    def configured(self) -> bool:
        return bool(self._raw_dsn)

    def capture_event(
        self,
        *,
        message: str,
        level: str = "error",
        tags: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> MonitorResult:
        if not self._raw_dsn:
            return MonitorResult(sent=False, reason=f"{SENTRY_DSN_ENV} not set")
        event_id = uuid.uuid4().hex
        payload = {
            "event_id": event_id,
            "timestamp": _utc_now_iso(),
            "platform": "python",
            "level": level,
            "message": message,
            "environment": self._environment,
            "release": self._release,
            "tags": tags or {},
            "extra": extra or {},
        }
        self._send_envelope(event_id=event_id, item_type="event", payload=payload)
        return MonitorResult(sent=True)

    def capture_check_in(
        self,
        *,
        monitor_slug: str,
        status: str,
        check_in_id: str | None = None,
        duration: float | None = None,
        schedule: str | None = None,
    ) -> MonitorResult:
        check_id = check_in_id or str(uuid.uuid4())
        if not self._raw_dsn:
            return MonitorResult(
                sent=False,
                check_in_id=check_id,
                reason=f"{SENTRY_DSN_ENV} not set",
            )
        payload: dict[str, Any] = {
            "check_in_id": check_id,
            "monitor_slug": monitor_slug,
            "status": status,
            "environment": self._environment,
        }
        if duration is not None:
            payload["duration"] = duration
        if schedule is not None:
            payload["monitor_config"] = {
                "schedule": {"type": "crontab", "value": schedule},
                "checkin_margin": 60,
                "max_runtime": 120,
                "timezone": "America/New_York",
            }
        self._send_envelope(
            event_id=uuid.uuid4().hex,
            item_type="check_in",
            payload=payload,
        )
        return MonitorResult(sent=True, check_in_id=check_id)

    def _send_envelope(self, *, event_id: str, item_type: str, payload: dict[str, Any]) -> None:
        dsn = SentryDsn.parse(self._raw_dsn or "")
        envelope = "\n".join(
            (
                json.dumps({"event_id": event_id, "dsn": self._raw_dsn}, sort_keys=True),
                json.dumps({"type": item_type}, sort_keys=True),
                json.dumps(payload, sort_keys=True),
                "",
            )
        ).encode("utf-8")
        self._transport.send_envelope(
            url=dsn.envelope_url,
            body=envelope,
            auth_header=dsn.auth_header,
        )


@dataclass(frozen=True)
class Alarm:
    kind: str
    message: str
    payload: dict[str, Any]


def load_operating_log(path: Path) -> tuple[dict[str, Any], ...]:
    if not path.exists():
        return ()
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entries.append(json.loads(line))
    return tuple(entries)


def evaluate_operating_alarms(
    entries: tuple[dict[str, Any], ...],
    *,
    now: datetime,
    daily_cost_budget_usd: float,
    max_run_age: timedelta = timedelta(hours=30),
) -> tuple[Alarm, ...]:
    alarms: list[Alarm] = []
    if not entries:
        alarms.append(
            Alarm(
                kind="missed_run",
                message="Ultra CSM daily job has no operating log entries",
                payload={"max_run_age_hours": max_run_age.total_seconds() / 3600},
            )
        )
    else:
        latest = entries[-1]
        latest_day = datetime.fromisoformat(str(latest["date"])).date()
        latest_date = datetime.combine(latest_day, datetime.min.time(), tzinfo=UTC)
        age = now - latest_date
        if latest_day != now.date() and age > max_run_age:
            alarms.append(
                Alarm(
                    kind="missed_run",
                    message="Ultra CSM daily job missed its expected run window",
                    payload={
                        "latest_date": latest["date"],
                        "age_hours": round(age.total_seconds() / 3600, 2),
                        "max_run_age_hours": max_run_age.total_seconds() / 3600,
                    },
                )
            )
    today = now.date().isoformat()
    today_cost = sum(float(item.get("cost_usd") or 0.0) for item in entries if item.get("date") == today)
    if today_cost > daily_cost_budget_usd:
        alarms.append(
            Alarm(
                kind="cost_budget",
                message="Ultra CSM daily cost budget exceeded",
                payload={
                    "date": today,
                    "cost_usd": round(today_cost, 6),
                    "budget_usd": daily_cost_budget_usd,
                },
            )
        )
    return tuple(alarms)


def send_alarms(monitor: SentryMonitor, alarms: tuple[Alarm, ...]) -> int:
    sent = 0
    for alarm in alarms:
        result = monitor.capture_event(
            message=alarm.message,
            level="error",
            tags={"alarm": alarm.kind, "component": "operating-daily"},
            extra=alarm.payload,
        )
        if result.sent:
            sent += 1
    return sent


def monitor_from_env(env: dict[str, str] | None = None) -> SentryMonitor:
    values = os.environ if env is None else env
    return SentryMonitor(
        dsn=values.get(SENTRY_DSN_ENV),
        environment=values.get("SENTRY_ENVIRONMENT", "live"),
        release=values.get("ULTRA_CSM_RELEASE"),
    )


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _cmd_check_in(args: argparse.Namespace) -> int:
    monitor = monitor_from_env()
    result = monitor.capture_check_in(
        monitor_slug=args.monitor,
        status=args.status,
        check_in_id=args.check_in_id,
        duration=args.duration,
        schedule=args.schedule,
    )
    if result.check_in_id:
        print(result.check_in_id)
    if not result.sent and args.verbose:
        print(result.reason or "not sent", file=sys.stderr)
    return 0


def _cmd_event(args: argparse.Namespace) -> int:
    monitor = monitor_from_env()
    try:
        result = monitor.capture_event(
            message=args.message,
            level=args.level,
            tags={"component": "operating-daily"},
            extra={"detail": args.detail} if args.detail else {},
        )
    except (OSError, error.URLError, ValueError) as exc:
        print(f"sentry_event_failed={type(exc).__name__}", file=sys.stderr)
        return 2
    if not result.sent and args.verbose:
        print(result.reason or "not sent", file=sys.stderr)
    return 0


def _cmd_alarms(args: argparse.Namespace) -> int:
    entries = load_operating_log(Path(args.operating_log))
    budget = float(os.environ.get(OPERATING_DAILY_COST_BUDGET_ENV, args.daily_budget_usd))
    alarms = evaluate_operating_alarms(
        entries,
        now=datetime.now(UTC),
        daily_cost_budget_usd=budget,
    )
    sent = send_alarms(monitor_from_env(), alarms)
    payload = {
        "alarms": [alarm.kind for alarm in alarms],
        "sent": sent,
        "sentry_configured": monitor_from_env().configured,
    }
    print(json.dumps(payload, sort_keys=True))
    return 1 if alarms else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ultra_csm.operating_monitor")
    sub = parser.add_subparsers(dest="command", required=True)

    check_in = sub.add_parser("check-in")
    check_in.add_argument("--monitor", default=os.environ.get(SENTRY_MONITOR_SLUG_ENV, DEFAULT_MONITOR_SLUG))
    check_in.add_argument("--status", required=True, choices=("in_progress", "ok", "error"))
    check_in.add_argument("--check-in-id")
    check_in.add_argument("--duration", type=float)
    check_in.add_argument("--schedule")
    check_in.add_argument("--verbose", action="store_true")
    check_in.set_defaults(func=_cmd_check_in)

    event = sub.add_parser("event")
    event.add_argument("--message", required=True)
    event.add_argument("--level", default="error")
    event.add_argument("--detail")
    event.add_argument("--verbose", action="store_true")
    event.set_defaults(func=_cmd_event)

    alarms = sub.add_parser("alarms")
    alarms.add_argument("--operating-log", required=True)
    alarms.add_argument("--daily-budget-usd", type=float, default=DEFAULT_DAILY_COST_BUDGET_USD)
    alarms.set_defaults(func=_cmd_alarms)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
