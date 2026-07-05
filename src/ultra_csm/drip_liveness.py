"""Drip liveness detector (Harvest 12: runtime chaos).

No liveness check for the daily drip existed before this dispatch
(verified: zero matches for ``drip`` anywhere in ``scripts/``/``src/``) --
the drip has stopped/failed silently before, a real past incident, and
nothing noticed. This module is a minimal, PURE detector: it reads a
drip log's last timestamp and compares it against a staleness threshold.
It never touches the drip's actual launchd job -- detection only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class DripLivenessResult:
    flagged: bool
    reason: str
    last_timestamp: str | None


def _last_timestamp(log_path: Path) -> str | None:
    """The leading ISO-8601 timestamp of the log's last non-blank line
    (e.g. ``"2026-06-21T00:00:00+00:00 drip ok"``), or ``None`` if the
    file is empty or no line parses."""

    if not log_path.exists():
        return None
    for line in reversed(log_path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        token = line.split(maxsplit=1)[0]
        try:
            datetime.fromisoformat(token)
        except ValueError:
            continue
        return token
    return None


def check_drip_liveness(
    log_path: Path, *, now: str, staleness_threshold_hours: float
) -> DripLivenessResult:
    """Flag loudly (never silently) when the drip log's last entry is
    older than *staleness_threshold_hours* relative to *now*, or when the
    log is missing/unparseable -- a missing signal is itself a liveness
    failure, never treated as healthy by omission."""

    if not log_path.exists():
        return DripLivenessResult(flagged=True, reason=f"drip log missing: {log_path}", last_timestamp=None)

    last = _last_timestamp(log_path)
    if last is None:
        return DripLivenessResult(
            flagged=True, reason=f"drip log has no parseable timestamp: {log_path}", last_timestamp=None
        )

    elapsed_hours = (datetime.fromisoformat(now) - datetime.fromisoformat(last)).total_seconds() / 3600.0
    if elapsed_hours > staleness_threshold_hours:
        return DripLivenessResult(
            flagged=True,
            reason=f"drip log stale: last entry {elapsed_hours:.1f}h ago, threshold {staleness_threshold_hours}h",
            last_timestamp=last,
        )
    return DripLivenessResult(
        flagged=False,
        reason=f"drip log fresh: last entry {elapsed_hours:.1f}h ago",
        last_timestamp=last,
    )
