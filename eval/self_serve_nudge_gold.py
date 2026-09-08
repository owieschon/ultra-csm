"""Validator for MP-E self-serve nudge blind-label candidates.

The rows in ``eval/gold/self_serve_nudge_candidates.json`` are not final gold:
``owner_label`` must remain null until OA-E3 blind labeling is complete.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ultra_csm.data_plane.contracts import NudgeDeliveryChannel, ResolutionState
from ultra_csm.knowledge import PLAYBOOK_MOTIONS

GOLD_DIR = Path(__file__).resolve().parent / "gold"
DEFAULT_CANDIDATE_PATH = GOLD_DIR / "self_serve_nudge_candidates.json"
VALID_IDENTITY_STATES: tuple[ResolutionState, ...] = ("exactly_one", "ambiguous", "none")
VALID_CHANNELS: tuple[NudgeDeliveryChannel, ...] = ("lifecycle_email", "sales_engagement")
VALID_MODES = ("nudge", "none", "abstain")


class SelfServeNudgeGoldError(ValueError):
    """Raised when the blind-label candidate packet is malformed."""


@dataclass(frozen=True)
class CandidateAction:
    motion: str
    content_id: str | None
    channel: NudgeDeliveryChannel | None


@dataclass(frozen=True)
class SelfServeNudgeCandidate:
    candidate_id: str
    tenant: str
    product_user_id: str
    checkpoint_day: int
    identity_state: ResolutionState
    candidate_action: CandidateAction
    owner_label: dict[str, Any] | None


def load_self_serve_nudge_candidates(
    path: Path | str = DEFAULT_CANDIDATE_PATH,
) -> tuple[SelfServeNudgeCandidate, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise SelfServeNudgeGoldError("self-serve candidate packet must be a non-empty array")
    rows = tuple(_row(item) for item in raw)
    _validate_coverage(rows)
    return rows


def _row(raw: Any) -> SelfServeNudgeCandidate:
    if not isinstance(raw, dict):
        raise SelfServeNudgeGoldError("candidate row must be an object")
    candidate_id = _required_str(raw, "candidate_id")
    tenant = _required_str(raw, "tenant")
    product_user_id = _required_str(raw, "product_user_id")
    checkpoint_day = raw.get("checkpoint_day")
    if not isinstance(checkpoint_day, int):
        raise SelfServeNudgeGoldError(f"{candidate_id}: checkpoint_day must be an integer")
    identity_state = raw.get("identity_state")
    if identity_state not in VALID_IDENTITY_STATES:
        raise SelfServeNudgeGoldError(f"{candidate_id}: invalid identity_state")

    action = raw.get("candidate_action")
    if not isinstance(action, dict):
        raise SelfServeNudgeGoldError(f"{candidate_id}: candidate_action must be an object")
    motion = _required_str(action, "motion")
    if motion not in PLAYBOOK_MOTIONS and motion != "none":
        raise SelfServeNudgeGoldError(f"{candidate_id}: unknown motion {motion!r}")
    channel = action.get("channel")
    if channel is not None and channel not in VALID_CHANNELS:
        raise SelfServeNudgeGoldError(f"{candidate_id}: invalid channel {channel!r}")
    content_id = action.get("content_id")
    if content_id is not None and not isinstance(content_id, str):
        raise SelfServeNudgeGoldError(f"{candidate_id}: content_id must be string or null")
    if motion == "none" and (channel is not None or content_id is not None):
        raise SelfServeNudgeGoldError(f"{candidate_id}: none action cannot carry channel/content")

    owner_label = raw.get("owner_label")
    if owner_label is not None:
        _validate_owner_label(candidate_id, owner_label)
    return SelfServeNudgeCandidate(
        candidate_id=candidate_id,
        tenant=tenant,
        product_user_id=product_user_id,
        checkpoint_day=checkpoint_day,
        identity_state=identity_state,
        candidate_action=CandidateAction(
            motion=motion,
            content_id=content_id,
            channel=channel,
        ),
        owner_label=owner_label,
    )


def _validate_coverage(rows: tuple[SelfServeNudgeCandidate, ...]) -> None:
    if len(rows) < 10:
        raise SelfServeNudgeGoldError("candidate packet must contain at least 10 rows")
    states = {row.identity_state for row in rows}
    if not {"exactly_one", "ambiguous", "none"} <= states:
        raise SelfServeNudgeGoldError("candidate packet must cover all identity states")
    motions = {row.candidate_action.motion for row in rows}
    if not {"content_route", "campaign_enroll", "none"} <= motions:
        raise SelfServeNudgeGoldError("candidate packet must cover route, sequence, and no-action")
    channels = {
        row.candidate_action.channel
        for row in rows
        if row.candidate_action.channel is not None
    }
    if channels != set(VALID_CHANNELS):
        raise SelfServeNudgeGoldError("candidate packet must cover both delivery channels")
    if any(row.owner_label is not None for row in rows):
        raise SelfServeNudgeGoldError("OA-E3 owner_label values must stay null until blind labeling")


def _validate_owner_label(candidate_id: str, owner_label: Any) -> None:
    if not isinstance(owner_label, dict):
        raise SelfServeNudgeGoldError(f"{candidate_id}: owner_label must be null or object")
    mode = owner_label.get("mode")
    if mode not in VALID_MODES:
        raise SelfServeNudgeGoldError(f"{candidate_id}: owner_label mode is invalid")


def _required_str(raw: dict[str, Any], field: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value:
        raise SelfServeNudgeGoldError(f"row missing {field}")
    return value


if __name__ == "__main__":
    rows = load_self_serve_nudge_candidates()
    print(f"validated {len(rows)} self-serve nudge blind-label candidates")
