"""Deterministic quality circuit breaker for customer-facing drafts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal


BreakerState = Literal["closed", "open", "disabled", "missing_artifact"]


@dataclass(frozen=True)
class QualityBreakerConfig:
    artifact_path: Path
    operator_events_path: Path
    enabled: bool = True


@dataclass(frozen=True)
class QualityBreakerDecision:
    state: BreakerState
    triggered: bool
    reason: str
    artifact_path: str | None = None
    artifact_sha256: str | None = None
    cleared_by_event: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_quality_breaker(config: QualityBreakerConfig) -> QualityBreakerDecision:
    """Return the deterministic breaker state for the configured quality artifact."""

    if not config.enabled:
        return QualityBreakerDecision(
            state="disabled",
            triggered=False,
            reason="breaker disabled by config",
        )
    if not config.artifact_path.exists():
        return QualityBreakerDecision(
            state="missing_artifact",
            triggered=True,
            reason="configured quality artifact is missing",
            artifact_path=str(config.artifact_path),
        )

    raw = config.artifact_path.read_bytes()
    artifact_sha256 = hashlib.sha256(raw).hexdigest()
    artifact = json.loads(raw.decode("utf-8"))
    red_reason = _red_reason(artifact)
    if red_reason is None:
        return QualityBreakerDecision(
            state="closed",
            triggered=False,
            reason="quality artifact is green",
            artifact_path=str(config.artifact_path),
            artifact_sha256=artifact_sha256,
        )

    reset_event = _matching_reset_event(config.operator_events_path, artifact_sha256)
    if reset_event is not None:
        return QualityBreakerDecision(
            state="closed",
            triggered=False,
            reason="quality breaker cleared by operator event",
            artifact_path=str(config.artifact_path),
            artifact_sha256=artifact_sha256,
            cleared_by_event=str(reset_event.get("event_id") or ""),
        )

    return QualityBreakerDecision(
        state="open",
        triggered=True,
        reason=red_reason,
        artifact_path=str(config.artifact_path),
        artifact_sha256=artifact_sha256,
    )


def record_quality_breaker_reset(
    config: QualityBreakerConfig,
    *,
    operator_id: str,
    rationale: str,
    recorded_at: str,
) -> dict[str, Any]:
    """Record the operator event that clears the current artifact fingerprint."""

    if not config.artifact_path.exists():
        raise FileNotFoundError(config.artifact_path)
    artifact_sha256 = hashlib.sha256(config.artifact_path.read_bytes()).hexdigest()
    event = {
        "event_id": hashlib.sha256(
            json.dumps(
                {
                    "artifact_sha256": artifact_sha256,
                    "operator_id": operator_id,
                    "recorded_at": recorded_at,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:24],
        "event_type": "quality_breaker_reset",
        "artifact_sha256": artifact_sha256,
        "operator_id": operator_id,
        "rationale": rationale,
        "recorded_at": recorded_at,
    }
    config.operator_events_path.parent.mkdir(parents=True, exist_ok=True)
    with config.operator_events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return event


def _red_reason(artifact: dict[str, Any]) -> str | None:
    if artifact.get("hard_ok") is False:
        return "quality artifact hard_ok=false"
    if artifact.get("quality_gate_passed") is False:
        return "quality artifact quality_gate_passed=false"
    if artifact.get("semantic_quality_passed") is False:
        return "quality artifact semantic_quality_passed=false"
    failures = artifact.get("hard_failures")
    if isinstance(failures, list) and failures:
        return "quality artifact has hard_failures"
    return None


def _matching_reset_event(path: Path, artifact_sha256: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    match: dict[str, Any] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if (
            event.get("event_type") == "quality_breaker_reset"
            and event.get("artifact_sha256") == artifact_sha256
        ):
            match = event
    return match
