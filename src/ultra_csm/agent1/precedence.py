"""Pure cross-lens precedence and hold state for Agent 1.

The hard invariant is that precedence suppresses customer-facing actions only.
Findings remain visible while a related action is held.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

from ultra_csm.governance import canonical_payload_sha256

REPO = Path(__file__).resolve().parents[3]
DEFAULT_PRECEDENCE_CONFIG_PATH = REPO / "config" / "precedence_config.json"

LensId = Literal["risk", "expansion", "ttv_gap"]
ActionScope = Literal["customer_facing", "internal"]
MatrixScope = Literal["customer_facing"]
FindingClass = Literal["blocking", "visible", "inactive"]
ActionClass = Literal["precedence_gated", "customer_facing_active", "internal_active"]
ReleaseOutcomeKind = Literal["fresh", "held", "expired"]

KNOWN_LENSES = frozenset({"risk", "expansion", "ttv_gap"})
KNOWN_MATRIX_SCOPES = frozenset({"customer_facing"})
KNOWN_ACTION_SCOPES = frozenset({"customer_facing", "internal"})
KNOWN_CONFIG_VERSIONS = frozenset({"precedence-v1"})
PRECEDENCE_BLOCKER_LENSES = frozenset({"risk", "ttv_gap"})
PRECEDENCE_BLOCKED_LENSES = frozenset({"expansion"})

FORBIDDEN_CONFIG_KEYS = frozenset({
    "authority",
    "autonomy_tier",
    "permission",
    "required_permission",
    "tier",
    "release",
    "release_condition",
    "recipient",
    "recipients",
    "awareness",
    "awareness_suppression",
    "finding_suppression",
    "hide_findings",
    "suppress_awareness",
    "suppress_findings",
    "internal",
    "internal_suppression",
    "suppress_internal",
})


class PrecedenceConfigError(ValueError):
    """Raised when precedence config is not fail-closed valid."""


class PrecedenceStateError(ValueError):
    """Raised when a pure state-machine input is unsafe or stale."""


@dataclass(frozen=True)
class PrecedenceRule:
    blocker: LensId
    blocked: LensId
    scope: MatrixScope

    def to_dict(self) -> dict[str, str]:
        return {
            "blocker": self.blocker,
            "blocked": self.blocked,
            "scope": self.scope,
        }


@dataclass(frozen=True)
class PrecedenceConfig:
    config_version: str
    precedence: tuple[PrecedenceRule, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_version": self.config_version,
            "precedence": [rule.to_dict() for rule in self.precedence],
        }


@dataclass(frozen=True)
class FindingPacket:
    finding_id: str
    account_id: str
    lens: LensId
    condition_instance: str
    evidence_refs: tuple[str, ...] = ()
    active: bool = True
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "account_id": self.account_id,
            "lens": self.lens,
            "condition_instance": self.condition_instance,
            "evidence_refs": list(self.evidence_refs),
            "active": self.active,
            "payload": self.payload,
        }


@dataclass(frozen=True)
class ActionPacket:
    action_id: str
    account_id: str
    lens: LensId
    scope: ActionScope
    action_type: str
    autonomy_tier: int
    payload: dict[str, Any]
    finding_id: str | None = None
    payload_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.payload_sha256:
            object.__setattr__(self, "payload_sha256", canonical_payload_sha256(self.payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "account_id": self.account_id,
            "lens": self.lens,
            "scope": self.scope,
            "action_type": self.action_type,
            "autonomy_tier": self.autonomy_tier,
            "finding_id": self.finding_id,
            "payload_sha256": self.payload_sha256,
            "payload": self.payload,
        }


@dataclass(frozen=True)
class ActiveActionPacket:
    action: ActionPacket
    conflict_context_refs: tuple[str, ...] = ()
    status: Literal["active"] = "active"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "action": self.action.to_dict(),
            "conflict_context_refs": list(self.conflict_context_refs),
        }


@dataclass(frozen=True)
class HeldActionPacket:
    held_item_id: str
    action: ActionPacket
    blocking_refs: tuple[str, ...]
    held_since: str
    release_conditions: tuple[str, ...] = (
        "all_blocking_refs_clear_or_dismissed",
        "authorized_override",
    )
    status: Literal["held"] = "held"

    def to_dict(self) -> dict[str, Any]:
        return {
            "held_item_id": self.held_item_id,
            "status": self.status,
            "action": self.action.to_dict(),
            "blocking_refs": list(self.blocking_refs),
            "held_since": self.held_since,
            "release_conditions": list(self.release_conditions),
        }


@dataclass(frozen=True)
class ClosedHoldPacket:
    held_item_id: str
    action_id: str
    account_id: str
    reason: Literal["expired", "superseded"]
    closed_at: str
    history_visible: bool
    old_payload_sha256: str
    replacement_action_id: str | None = None
    replacement_payload_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "held_item_id": self.held_item_id,
            "action_id": self.action_id,
            "account_id": self.account_id,
            "reason": self.reason,
            "closed_at": self.closed_at,
            "history_visible": self.history_visible,
            "old_payload_sha256": self.old_payload_sha256,
            "replacement_action_id": self.replacement_action_id,
            "replacement_payload_sha256": self.replacement_payload_sha256,
        }


@dataclass(frozen=True)
class LedgerEvent:
    event_type: str
    account_id: str
    target_id: str
    at: str
    refs: tuple[str, ...] = ()
    actor_id: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""

    def __post_init__(self) -> None:
        if not self.idempotency_key:
            object.__setattr__(
                self,
                "idempotency_key",
                _stable_id(
                    "precedence-event",
                    {
                        "event_type": self.event_type,
                        "target_id": self.target_id,
                        "refs": list(self.refs),
                    },
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "account_id": self.account_id,
            "target_id": self.target_id,
            "at": self.at,
            "refs": list(self.refs),
            "actor_id": self.actor_id,
            "detail": self.detail,
            "idempotency_key": self.idempotency_key,
        }


@dataclass(frozen=True)
class PrecedenceEvaluation:
    visible_findings: tuple[FindingPacket, ...]
    active_actions: tuple[ActiveActionPacket, ...]
    held_actions: tuple[HeldActionPacket, ...]
    ledger_events: tuple[LedgerEvent, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "visible_findings": [finding.to_dict() for finding in self.visible_findings],
            "active_actions": [action.to_dict() for action in self.active_actions],
            "held_actions": [action.to_dict() for action in self.held_actions],
            "ledger_events": [event.to_dict() for event in self.ledger_events],
        }


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str
    blocking_refs: tuple[str, ...]
    ledger_events: tuple[LedgerEvent, ...] = ()


@dataclass(frozen=True)
class HoldReleaseResult:
    outcome: ReleaseOutcomeKind
    active_action: ActionPacket | None
    held_action: HeldActionPacket | None
    closed_hold: ClosedHoldPacket | None
    ledger_events: tuple[LedgerEvent, ...]


@dataclass(frozen=True)
class OverrideRequest:
    actor_id: str
    authorized_tiers: tuple[int, ...]
    named_refs: tuple[str, ...]
    justification: str


@dataclass(frozen=True)
class OverrideDecision:
    allowed: bool
    reason: str
    ledger_events: tuple[LedgerEvent, ...] = ()


@dataclass(frozen=True)
class NotificationDecision:
    should_notify: bool
    idempotency_key: str
    reason: Literal["new", "deduped"]


def load_precedence_config(path: Path = DEFAULT_PRECEDENCE_CONFIG_PATH) -> PrecedenceConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PrecedenceConfigError(f"could not load precedence config: {path}") from exc
    return parse_precedence_config(raw)


def parse_precedence_config(raw: dict[str, Any]) -> PrecedenceConfig:
    _reject_forbidden_config_keys(raw)
    allowed_top = {"config_version", "precedence"}
    extras = set(raw) - allowed_top
    if extras:
        raise PrecedenceConfigError(f"unknown precedence config keys: {sorted(extras)}")
    version = raw.get("config_version")
    if version not in KNOWN_CONFIG_VERSIONS:
        raise PrecedenceConfigError(f"unknown precedence config_version: {version}")
    precedence_raw = raw.get("precedence")
    if not isinstance(precedence_raw, list) or not precedence_raw:
        raise PrecedenceConfigError("precedence config requires non-empty precedence list")
    rules = tuple(_parse_rule(item) for item in precedence_raw)
    seen: set[tuple[str, str, str]] = set()
    for rule in rules:
        key = (rule.blocker, rule.blocked, rule.scope)
        if key in seen:
            raise PrecedenceConfigError(f"duplicate precedence rule: {key}")
        seen.add(key)
    return PrecedenceConfig(config_version=version, precedence=rules)


def classify_finding(
    finding: FindingPacket,
    config: PrecedenceConfig,
    *,
    dismissed_condition_instances: frozenset[str] = frozenset(),
) -> FindingClass:
    _validate_lens(finding.lens)
    if not finding.active:
        return "inactive"
    if finding.condition_instance in dismissed_condition_instances:
        return "visible"
    if any(rule.blocker == finding.lens for rule in config.precedence):
        return "blocking"
    return "visible"


def classify_action(action: ActionPacket, config: PrecedenceConfig) -> ActionClass:
    _validate_lens(action.lens)
    _validate_action_scope(action.scope)
    if action.scope == "internal":
        return "internal_active"
    if any(rule.blocked == action.lens and rule.scope == action.scope for rule in config.precedence):
        return "precedence_gated"
    return "customer_facing_active"


def visible_finding_packets(findings: tuple[FindingPacket, ...]) -> tuple[FindingPacket, ...]:
    return tuple(sorted(
        (finding for finding in findings if finding.active),
        key=lambda item: (item.account_id, item.lens, item.finding_id),
    ))


def current_blocking_refs(
    action: ActionPacket,
    findings: tuple[FindingPacket, ...],
    config: PrecedenceConfig,
    *,
    dismissed_condition_instances: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    _validate_lens(action.lens)
    _validate_action_scope(action.scope)
    if action.scope != "customer_facing":
        return ()
    blocker_lenses = {
        rule.blocker
        for rule in config.precedence
        if rule.blocked == action.lens and rule.scope == action.scope
    }
    refs = [
        finding.finding_id
        for finding in findings
        if (
            finding.active
            and finding.account_id == action.account_id
            and finding.lens in blocker_lenses
            and finding.condition_instance not in dismissed_condition_instances
        )
    ]
    return _normalize_refs(refs)


def conflict_context_refs(
    action: ActionPacket,
    findings: tuple[FindingPacket, ...],
    config: PrecedenceConfig,
    *,
    dismissed_condition_instances: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    _validate_lens(action.lens)
    blocker_lenses = {
        rule.blocker
        for rule in config.precedence
        if rule.blocked == action.lens
    }
    refs = [
        finding.finding_id
        for finding in findings
        if (
            finding.active
            and finding.account_id == action.account_id
            and finding.lens in blocker_lenses
            and finding.condition_instance not in dismissed_condition_instances
        )
    ]
    return _normalize_refs(refs)


def evaluate_precedence(
    findings: tuple[FindingPacket, ...],
    actions: tuple[ActionPacket, ...],
    config: PrecedenceConfig,
    *,
    as_of: str,
    dismissed_condition_instances: frozenset[str] = frozenset(),
) -> PrecedenceEvaluation:
    active_actions: list[ActiveActionPacket] = []
    held_actions: list[HeldActionPacket] = []
    ledger: list[LedgerEvent] = []

    for action in sorted(actions, key=lambda item: item.action_id):
        classification = classify_action(action, config)
        refs = current_blocking_refs(
            action,
            findings,
            config,
            dismissed_condition_instances=dismissed_condition_instances,
        )
        context_refs = conflict_context_refs(
            action,
            findings,
            config,
            dismissed_condition_instances=dismissed_condition_instances,
        )
        if classification == "precedence_gated" and refs:
            hold = create_held_action(action, refs, as_of=as_of)
            held_actions.append(hold)
            ledger.append(_ledger_event(
                "hold_created",
                hold.action.account_id,
                hold.held_item_id,
                as_of,
                refs=hold.blocking_refs,
                detail={
                    "action_id": hold.action.action_id,
                    "payload_sha256": hold.action.payload_sha256,
                },
            ))
        else:
            active_actions.append(ActiveActionPacket(
                action=action,
                conflict_context_refs=context_refs,
            ))

    return PrecedenceEvaluation(
        visible_findings=visible_finding_packets(findings),
        active_actions=tuple(active_actions),
        held_actions=tuple(held_actions),
        ledger_events=tuple(ledger),
    )


def create_held_action(
    action: ActionPacket,
    blocking_refs: tuple[str, ...],
    *,
    as_of: str,
) -> HeldActionPacket:
    refs = _normalize_refs(blocking_refs)
    if not refs:
        raise PrecedenceStateError("held action requires at least one blocking ref")
    return HeldActionPacket(
        held_item_id=_stable_id(
            "hold",
            {
                "action_id": action.action_id,
                "payload_sha256": action.payload_sha256,
                "refs": list(refs),
            },
        ),
        action=action,
        blocking_refs=refs,
        held_since=as_of,
    )


def approval_decision(
    action: ActionPacket,
    current_findings: tuple[FindingPacket, ...],
    config: PrecedenceConfig,
    *,
    as_of: str,
    dismissed_condition_instances: frozenset[str] = frozenset(),
) -> GateDecision:
    refs = current_blocking_refs(
        action,
        current_findings,
        config,
        dismissed_condition_instances=dismissed_condition_instances,
    )
    if not refs:
        return GateDecision(True, "unblocked", ())
    event = _ledger_event(
        "approval_refused",
        action.account_id,
        action.action_id,
        as_of,
        refs=refs,
        detail={"payload_sha256": action.payload_sha256},
    )
    return GateDecision(False, "held_current_blocker", refs, (event,))


def commit_decision(
    action: ActionPacket,
    current_findings: tuple[FindingPacket, ...],
    config: PrecedenceConfig,
    *,
    as_of: str,
    payload: dict[str, Any] | None = None,
    dismissed_condition_instances: frozenset[str] = frozenset(),
) -> GateDecision:
    refs = current_blocking_refs(
        action,
        current_findings,
        config,
        dismissed_condition_instances=dismissed_condition_instances,
    )
    if refs:
        event = _ledger_event(
            "commit_blocked",
            action.account_id,
            action.action_id,
            as_of,
            refs=refs,
            detail={"payload_sha256": action.payload_sha256},
        )
        return GateDecision(False, "blocked_current_state", refs, (event,))
    if payload is not None and canonical_payload_sha256(payload) != action.payload_sha256:
        event = _ledger_event(
            "commit_refused",
            action.account_id,
            action.action_id,
            as_of,
            detail={"reason": "payload_hash_mismatch"},
        )
        return GateDecision(False, "payload_hash_mismatch", (), (event,))
    return GateDecision(True, "unblocked", ())


def rederive_hold_release(
    held: HeldActionPacket,
    *,
    current_blocking_refs: tuple[str, ...],
    current_candidate: ActionPacket | None,
    as_of: str,
) -> HoldReleaseResult:
    refs = _normalize_refs(current_blocking_refs)
    if refs:
        updated = replace(held, blocking_refs=refs)
        event = _ledger_event(
            "held_to_held",
            held.action.account_id,
            held.held_item_id,
            as_of,
            refs=refs,
            detail={
                "previous_refs": list(held.blocking_refs),
                "held_since": held.held_since,
                "active_flash": False,
            },
        )
        return HoldReleaseResult("held", None, updated, None, (event,))

    if current_candidate is None:
        closed = ClosedHoldPacket(
            held_item_id=held.held_item_id,
            action_id=held.action.action_id,
            account_id=held.action.account_id,
            reason="expired",
            closed_at=as_of,
            history_visible=True,
            old_payload_sha256=held.action.payload_sha256,
        )
        event = _ledger_event(
            "expired",
            held.action.account_id,
            held.held_item_id,
            as_of,
            detail=closed.to_dict(),
        )
        return HoldReleaseResult("expired", None, None, closed, (event,))

    _validate_rederived_candidate(held, current_candidate)
    closed = ClosedHoldPacket(
        held_item_id=held.held_item_id,
        action_id=held.action.action_id,
        account_id=held.action.account_id,
        reason="superseded",
        closed_at=as_of,
        history_visible=True,
        old_payload_sha256=held.action.payload_sha256,
        replacement_action_id=current_candidate.action_id,
        replacement_payload_sha256=current_candidate.payload_sha256,
    )
    events = (
        _ledger_event(
            "hold_released",
            held.action.account_id,
            held.held_item_id,
            as_of,
            detail={"release_source": "rederived"},
        ),
        _ledger_event(
            "superseded",
            held.action.account_id,
            held.held_item_id,
            as_of,
            detail=closed.to_dict(),
        ),
    )
    return HoldReleaseResult("fresh", current_candidate, None, closed, events)


def validate_rederived_payload(current_candidate: ActionPacket, presented_payload: dict[str, Any]) -> None:
    if canonical_payload_sha256(presented_payload) != current_candidate.payload_sha256:
        raise PrecedenceStateError("release payload must match current re-derived candidate")


def finding_disposition_event(
    finding: FindingPacket,
    *,
    disposition: Literal["acknowledge", "dismiss", "deny"],
    actor_id: str,
    as_of: str,
    note: str | None = None,
) -> LedgerEvent:
    if disposition not in {"acknowledge", "dismiss", "deny"}:
        raise PrecedenceStateError(f"unknown finding disposition: {disposition}")
    if not actor_id:
        raise PrecedenceStateError("finding disposition requires actor_id")
    detail: dict[str, Any] = {"condition_instance": finding.condition_instance}
    if note:
        detail["note"] = note
    return _ledger_event(
        disposition,
        finding.account_id,
        finding.finding_id,
        as_of,
        refs=(finding.finding_id,),
        actor_id=actor_id,
        detail=detail,
    )


def dismissed_condition_instances(events: tuple[LedgerEvent, ...]) -> frozenset[str]:
    return frozenset(
        str(event.detail["condition_instance"])
        for event in events
        if event.event_type in {"dismiss", "deny"} and "condition_instance" in event.detail
    )


def validate_override(
    held: HeldActionPacket,
    request: OverrideRequest,
    *,
    current_blocking_refs: tuple[str, ...],
    as_of: str,
) -> OverrideDecision:
    refs = _normalize_refs(current_blocking_refs)
    named_refs = _normalize_refs(request.named_refs)
    if not request.actor_id:
        return OverrideDecision(False, "missing_actor")
    if not request.justification.strip():
        return OverrideDecision(False, "missing_justification")
    if not refs:
        return OverrideDecision(False, "no_current_blocker")
    if named_refs != refs:
        return OverrideDecision(False, "stale_refs")
    if held.action.autonomy_tier not in set(request.authorized_tiers):
        return OverrideDecision(False, "wrong_tier")
    event = _ledger_event(
        "override_released",
        held.action.account_id,
        held.held_item_id,
        as_of,
        refs=refs,
        actor_id=request.actor_id,
        detail={
            "action_id": held.action.action_id,
            "blocked_action_tier": held.action.autonomy_tier,
            "justification": request.justification,
        },
    )
    return OverrideDecision(True, "override_valid", (event,))


def hold_notification_decision(
    event: LedgerEvent,
    emitted_idempotency_keys: frozenset[str],
) -> NotificationDecision:
    if event.idempotency_key in emitted_idempotency_keys:
        return NotificationDecision(False, event.idempotency_key, "deduped")
    return NotificationDecision(True, event.idempotency_key, "new")


def _parse_rule(raw: Any) -> PrecedenceRule:
    if not isinstance(raw, dict):
        raise PrecedenceConfigError("each precedence rule must be an object")
    _reject_forbidden_config_keys(raw)
    allowed = {"blocker", "blocked", "scope"}
    extras = set(raw) - allowed
    if extras:
        raise PrecedenceConfigError(f"unknown precedence rule keys: {sorted(extras)}")
    blocker = raw.get("blocker")
    blocked = raw.get("blocked")
    scope = raw.get("scope")
    if blocker not in KNOWN_LENSES:
        raise PrecedenceConfigError(f"unknown blocker lens: {blocker}")
    if blocked not in KNOWN_LENSES:
        raise PrecedenceConfigError(f"unknown blocked lens: {blocked}")
    if blocker not in PRECEDENCE_BLOCKER_LENSES:
        raise PrecedenceConfigError(f"lens cannot act as precedence blocker: {blocker}")
    if blocked not in PRECEDENCE_BLOCKED_LENSES:
        raise PrecedenceConfigError(f"lens cannot be precedence-blocked: {blocked}")
    if scope not in KNOWN_MATRIX_SCOPES:
        raise PrecedenceConfigError(f"unknown precedence scope: {scope}")
    return PrecedenceRule(
        blocker=blocker,  # type: ignore[arg-type]
        blocked=blocked,  # type: ignore[arg-type]
        scope=scope,  # type: ignore[arg-type]
    )


def _reject_forbidden_config_keys(raw: Any, *, path: str = "$") -> None:
    if isinstance(raw, dict):
        for key, value in raw.items():
            if str(key) in FORBIDDEN_CONFIG_KEYS:
                raise PrecedenceConfigError(
                    f"precedence config cannot name unsafe key {path}.{key}"
                )
            _reject_forbidden_config_keys(value, path=f"{path}.{key}")
    elif isinstance(raw, list):
        for index, item in enumerate(raw):
            _reject_forbidden_config_keys(item, path=f"{path}[{index}]")


def _validate_lens(lens: str) -> None:
    if lens not in KNOWN_LENSES:
        raise PrecedenceStateError(f"unknown lens: {lens}")


def _validate_action_scope(scope: str) -> None:
    if scope not in KNOWN_ACTION_SCOPES:
        raise PrecedenceStateError(f"unknown action scope: {scope}")


def _validate_rederived_candidate(held: HeldActionPacket, candidate: ActionPacket) -> None:
    if candidate.account_id != held.action.account_id:
        raise PrecedenceStateError("re-derived candidate account does not match held item")
    if candidate.lens != held.action.lens:
        raise PrecedenceStateError("re-derived candidate lens does not match held item")
    if candidate.scope != held.action.scope:
        raise PrecedenceStateError("re-derived candidate scope does not match held item")


def _normalize_refs(refs: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    normalized = []
    for ref in refs:
        if not isinstance(ref, str) or not ref:
            raise PrecedenceStateError("refs must be non-empty strings")
        normalized.append(ref)
    return tuple(sorted(set(normalized)))


def _ledger_event(
    event_type: str,
    account_id: str,
    target_id: str,
    at: str,
    *,
    refs: tuple[str, ...] = (),
    actor_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> LedgerEvent:
    return LedgerEvent(
        event_type=event_type,
        account_id=account_id,
        target_id=target_id,
        at=at,
        refs=_normalize_refs(refs) if refs else (),
        actor_id=actor_id,
        detail=detail or {},
    )


def _stable_id(prefix: str, payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"{prefix}:{canonical_payload_sha256({'payload': blob})[:24]}"
