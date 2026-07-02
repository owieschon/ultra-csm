"""Deterministic trigger evaluation for Ultra CSM ticks.

Triggers decide what work should be considered. They do not wake the process,
open sockets, run LLMs, or mint authority. Webhooks, cron, CI, or a manual
operator can all wake the same external beat: ``ucsm tick``. Live webhooks later
should only cause an early re-observation through tick, not a second trigger
mechanism.
"""

from __future__ import annotations

import hashlib
import json
import operator
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from ultra_csm.snapshot_store import SnapshotStore

REPO = Path(__file__).resolve().parents[2]
DEFAULT_TRIGGER_CONFIG_PATH = REPO / "config" / "trigger_config.json"

TriggerKind = Literal["schedule", "deadline", "event"]
TriggerScope = Literal["book", "account"]
SuppressionReason = Literal[
    "schedule",
    "cooldown",
    "idempotent_fired_ledger",
    "pending_proposal",
]

KNOWN_LENSES = frozenset({"ttv"})
KNOWN_KINDS = frozenset({"schedule", "deadline", "event"})
KNOWN_SCOPES = frozenset({"book", "account"})
KNOWN_FIELDS = frozenset({
    "account_id",
    "account_name",
    "arr_cents",
    "health_band",
    "health_score",
    "lifecycle_stage",
    "renewal_date",
    "status",
})
DATE_FIELDS = frozenset({"renewal_date"})
TRANSITION_FIELDS = frozenset({"health_band"})
KNOWN_BANDS = frozenset({"green", "yellow", "red", "unknown"})
FORBIDDEN_AUTHORITY_KEYS = frozenset({
    "authority",
    "autonomy_tier",
    "permission",
    "recipient",
    "recipients",
    "release",
    "release_condition",
    "required_permission",
    "tier",
})

_VALUE_OPS = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}
KNOWN_OPS = frozenset((*_VALUE_OPS.keys(), "in", "within_days", "transition"))
_BOOK_ACCOUNT = "__book__"


class TriggerConfigError(ValueError):
    """Raised when trigger config is not fail-closed valid."""


@dataclass(frozen=True)
class TriggerAction:
    lens: str
    scope: TriggerScope

    def to_dict(self) -> dict[str, str]:
        return {"lens": self.lens, "scope": self.scope}


@dataclass(frozen=True)
class TriggerPredicate:
    field: str
    op: str
    value: Any

    def to_dict(self) -> dict[str, Any]:
        return {"field": self.field, "op": self.op, "value": self.value}


@dataclass(frozen=True)
class TriggerRule:
    name: str
    kind: TriggerKind
    action: TriggerAction
    when: tuple[TriggerPredicate, ...] = ()
    every_days: int | None = None
    cooldown_days: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "kind": self.kind,
            "action": self.action.to_dict(),
            "cooldown_days": self.cooldown_days,
        }
        if self.every_days is not None:
            payload["every"] = f"{self.every_days}d"
        if self.when:
            payload["when"] = [predicate.to_dict() for predicate in self.when]
        return payload


@dataclass(frozen=True)
class TriggerRuntime:
    """Immutable ledger/gate observations supplied by the tick runner."""

    last_fire_at: tuple[tuple[str, str, str], ...] = ()
    fired_idempotency_keys: frozenset[str] = frozenset()
    pending_trigger_accounts: frozenset[tuple[str, str]] = frozenset()

    def last_fire_date(self, trigger_name: str, account_id: str | None) -> date | None:
        key = _runtime_account_key(account_id)
        matches = [
            _parse_date(as_of)
            for name, account, as_of in self.last_fire_at
            if name == trigger_name and account == key
        ]
        return max(matches) if matches else None

    def has_pending(self, trigger_name: str, account_id: str | None) -> bool:
        key = _runtime_account_key(account_id)
        return (trigger_name, key) in self.pending_trigger_accounts


@dataclass(frozen=True)
class TriggerConfig:
    config_version: str
    triggers: tuple[TriggerRule, ...]
    runtime: TriggerRuntime = TriggerRuntime()

    def with_runtime(self, runtime: TriggerRuntime) -> "TriggerConfig":
        return replace(self, runtime=runtime)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_version": self.config_version,
            "triggers": [trigger.to_dict() for trigger in self.triggers],
        }


@dataclass(frozen=True)
class AccountTriggerState:
    account_id: str
    account_name: str
    health_band: str | None = None
    health_score: float | None = None
    renewal_date: str | None = None
    lifecycle_stage: str | None = None
    arr_cents: int | None = None
    status: str | None = None

    def attrs(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "account_name": self.account_name,
            "health_band": self.health_band,
            "health_score": self.health_score,
            "renewal_date": self.renewal_date,
            "lifecycle_stage": self.lifecycle_stage,
            "arr_cents": self.arr_cents,
            "status": self.status,
        }

    def to_snapshot_payload(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "account_name": self.account_name,
            "health_band": self.health_band or "unknown",
            "health_score": self.health_score if self.health_score is not None else 0.0,
            "priority_score": 0,
            "priority_factors": [],
            "lifecycle_stage": self.lifecycle_stage or "unknown",
            "arr_cents": self.arr_cents or 0,
            "renewal_date": self.renewal_date,
            "status": self.status,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.attrs()


@dataclass(frozen=True)
class TriggerState:
    day: int | None
    accounts: tuple[AccountTriggerState, ...]

    def by_account(self) -> dict[str, AccountTriggerState]:
        return {account.account_id: account for account in self.accounts}

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "accounts": [account.to_dict() for account in self.accounts],
        }


@dataclass(frozen=True)
class FiredTrigger:
    trigger_name: str
    config_version: str
    kind: TriggerKind
    action: TriggerAction
    as_of: str
    evidence: dict[str, Any]
    condition_instance: str
    idempotency_key: str
    account_id: str | None = None
    account_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger_name": self.trigger_name,
            "config_version": self.config_version,
            "kind": self.kind,
            "action": self.action.to_dict(),
            "as_of": self.as_of,
            "account_id": self.account_id,
            "account_name": self.account_name,
            "condition_instance": self.condition_instance,
            "idempotency_key": self.idempotency_key,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class TriggerSuppression:
    trigger_name: str
    reason: SuppressionReason
    as_of: str
    condition_instance: str
    evidence: dict[str, Any]
    account_id: str | None = None
    account_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger_name": self.trigger_name,
            "reason": self.reason,
            "as_of": self.as_of,
            "account_id": self.account_id,
            "account_name": self.account_name,
            "condition_instance": self.condition_instance,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class TriggerEvaluation:
    fired: tuple[FiredTrigger, ...]
    suppressions: tuple[TriggerSuppression, ...]


def load_trigger_config(path: Path = DEFAULT_TRIGGER_CONFIG_PATH) -> TriggerConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return parse_trigger_config(raw)


def parse_trigger_config(raw: dict[str, Any]) -> TriggerConfig:
    _reject_forbidden_authority(raw)
    allowed_top = {"config_version", "triggers"}
    extras = set(raw) - allowed_top
    if extras:
        raise TriggerConfigError(f"unknown trigger config keys: {sorted(extras)}")
    version = raw.get("config_version")
    if not isinstance(version, str) or not version:
        raise TriggerConfigError("trigger config requires config_version")
    triggers_raw = raw.get("triggers")
    if not isinstance(triggers_raw, list):
        raise TriggerConfigError("trigger config requires triggers list")
    triggers = tuple(_parse_trigger(item) for item in triggers_raw)
    seen: set[str] = set()
    for trigger in triggers:
        if trigger.name in seen:
            raise TriggerConfigError(f"duplicate trigger name: {trigger.name}")
        seen.add(trigger.name)
    return TriggerConfig(config_version=version, triggers=triggers)


def evaluate_triggers(
    state: TriggerState,
    prev_snapshot: TriggerState | None,
    as_of: str | datetime | date,
    config: TriggerConfig,
) -> tuple[FiredTrigger, ...]:
    """Return the deterministic fired-trigger tuple for the supplied inputs."""

    return evaluate_trigger_decisions(state, prev_snapshot, as_of, config).fired


def evaluate_trigger_decisions(
    state: TriggerState,
    prev_snapshot: TriggerState | None,
    as_of: str | datetime | date,
    config: TriggerConfig,
) -> TriggerEvaluation:
    as_of_date = _parse_date(as_of)
    fired: list[FiredTrigger] = []
    suppressions: list[TriggerSuppression] = []

    for trigger in config.triggers:
        candidates, blocked = _candidate_triggers(trigger, state, prev_snapshot, as_of_date, config)
        suppressions.extend(blocked)
        for candidate in candidates:
            suppression = _noise_suppression(trigger, candidate, as_of_date, config.runtime)
            if suppression is not None:
                suppressions.append(suppression)
            else:
                fired.append(candidate)

    return TriggerEvaluation(
        fired=tuple(sorted(
            fired,
            key=lambda item: (
                item.trigger_name,
                item.account_id or "",
                item.condition_instance,
            ),
        )),
        suppressions=tuple(sorted(
            suppressions,
            key=lambda item: (
                item.trigger_name,
                item.account_id or "",
                item.reason,
                item.condition_instance,
            ),
        )),
    )


def trigger_runtime_from_fired(
    fired_rows: tuple[dict[str, Any], ...],
    *,
    pending_trigger_accounts: frozenset[tuple[str, str]] = frozenset(),
) -> TriggerRuntime:
    last_fire_at: list[tuple[str, str, str]] = []
    idempotency_keys: set[str] = set()
    for row in fired_rows:
        trigger_name = str(row["trigger_name"])
        account = _runtime_account_key(row.get("account_id"))
        as_of = str(row["as_of"])
        last_fire_at.append((trigger_name, account, as_of))
        key = row.get("idempotency_key")
        if isinstance(key, str) and key:
            idempotency_keys.add(key)
    return TriggerRuntime(
        last_fire_at=tuple(sorted(last_fire_at)),
        fired_idempotency_keys=frozenset(idempotency_keys),
        pending_trigger_accounts=pending_trigger_accounts,
    )


def idempotency_key_for(
    trigger_name: str,
    account_id: str | None,
    condition_instance: str,
) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {
                "trigger": trigger_name,
                "account_id": _runtime_account_key(account_id),
                "condition_instance": condition_instance,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:24]
    return f"trigger:{digest}"


def _parse_trigger(raw: Any) -> TriggerRule:
    if not isinstance(raw, dict):
        raise TriggerConfigError("each trigger must be an object")
    _reject_forbidden_authority(raw)
    allowed = {"action", "cooldown_days", "every", "kind", "name", "when"}
    extras = set(raw) - allowed
    if extras:
        raise TriggerConfigError(f"unknown trigger keys: {sorted(extras)}")
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise TriggerConfigError("trigger requires non-empty name")
    kind = raw.get("kind")
    if kind not in KNOWN_KINDS:
        raise TriggerConfigError(f"unknown trigger kind: {kind}")
    action = _parse_action(raw.get("action"))
    cooldown_days = int(raw.get("cooldown_days", 0))
    if cooldown_days < 0:
        raise TriggerConfigError("cooldown_days must be >= 0")

    if kind == "schedule":
        if "when" in raw:
            raise TriggerConfigError("schedule trigger cannot define when")
        every_days = _parse_every(raw.get("every"))
        return TriggerRule(
            name=name,
            kind="schedule",
            action=action,
            every_days=every_days,
            cooldown_days=cooldown_days,
        )

    if "every" in raw:
        raise TriggerConfigError(f"{kind} trigger cannot define every")
    when_raw = raw.get("when")
    if not isinstance(when_raw, list) or not when_raw:
        raise TriggerConfigError(f"{kind} trigger requires non-empty when")
    predicates = tuple(_parse_predicate(item, kind=kind) for item in when_raw)
    return TriggerRule(
        name=name,
        kind=kind,  # type: ignore[arg-type]
        action=action,
        when=predicates,
        cooldown_days=cooldown_days,
    )


def _parse_action(raw: Any) -> TriggerAction:
    if not isinstance(raw, dict):
        raise TriggerConfigError("trigger action must be an object")
    _reject_forbidden_authority(raw)
    extras = set(raw) - {"lens", "scope"}
    if extras:
        raise TriggerConfigError(f"unknown action keys: {sorted(extras)}")
    lens = raw.get("lens")
    if lens not in KNOWN_LENSES:
        raise TriggerConfigError(f"unknown action lens: {lens}")
    scope = raw.get("scope")
    if scope not in KNOWN_SCOPES:
        raise TriggerConfigError(f"unknown action scope: {scope}")
    return TriggerAction(lens=lens, scope=scope)  # type: ignore[arg-type]


def _parse_predicate(raw: Any, *, kind: str) -> TriggerPredicate:
    if not isinstance(raw, dict):
        raise TriggerConfigError("trigger predicate must be an object")
    _reject_forbidden_authority(raw)
    extras = set(raw) - {"field", "op", "value"}
    if extras:
        raise TriggerConfigError(f"unknown predicate keys: {sorted(extras)}")
    field = raw.get("field")
    op = raw.get("op")
    value = raw.get("value")
    if field not in KNOWN_FIELDS:
        raise TriggerConfigError(f"unknown trigger field: {field}")
    if op not in KNOWN_OPS:
        raise TriggerConfigError(f"unknown trigger op: {op}")
    if kind == "deadline":
        if op != "within_days":
            raise TriggerConfigError("deadline trigger requires within_days")
        if field not in DATE_FIELDS:
            raise TriggerConfigError(f"within_days requires a date field: {field}")
        if not isinstance(value, int) or value < 0:
            raise TriggerConfigError("within_days value must be a non-negative integer")
    elif kind == "event":
        if op != "transition":
            raise TriggerConfigError("event trigger requires transition")
        if field not in TRANSITION_FIELDS:
            raise TriggerConfigError(f"transition requires a transition field: {field}")
        if not isinstance(value, list) or len(value) != 2:
            raise TriggerConfigError("transition value must be [from, to]")
        for side in value:
            if side != "*" and side not in KNOWN_BANDS:
                raise TriggerConfigError(f"unknown transition band: {side}")
        value = tuple(value)
    return TriggerPredicate(field=str(field), op=str(op), value=value)


def _parse_every(raw: Any) -> int:
    if not isinstance(raw, str) or not raw.endswith("d"):
        raise TriggerConfigError("schedule every must be in Nd form")
    try:
        days = int(raw[:-1])
    except ValueError as exc:
        raise TriggerConfigError("schedule every must be in Nd form") from exc
    if days <= 0:
        raise TriggerConfigError("schedule every must be positive")
    return days


def _reject_forbidden_authority(raw: Any, *, path: str = "$") -> None:
    if isinstance(raw, dict):
        for key, value in raw.items():
            if str(key) in FORBIDDEN_AUTHORITY_KEYS:
                raise TriggerConfigError(
                    f"trigger config cannot name authority key {path}.{key}"
                )
            _reject_forbidden_authority(value, path=f"{path}.{key}")
    elif isinstance(raw, list):
        for index, item in enumerate(raw):
            _reject_forbidden_authority(item, path=f"{path}[{index}]")


def _candidate_triggers(
    trigger: TriggerRule,
    state: TriggerState,
    prev_snapshot: TriggerState | None,
    as_of: date,
    config: TriggerConfig,
) -> tuple[tuple[FiredTrigger, ...], tuple[TriggerSuppression, ...]]:
    if trigger.kind == "schedule":
        return _schedule_candidates(trigger, as_of, config)
    if trigger.kind == "deadline":
        return _deadline_candidates(trigger, state, as_of, config), ()
    if trigger.kind == "event":
        return _event_candidates(trigger, state, prev_snapshot, as_of, config), ()
    raise AssertionError(f"unreachable trigger kind: {trigger.kind}")


def _schedule_candidates(
    trigger: TriggerRule,
    as_of: date,
    config: TriggerConfig,
) -> tuple[tuple[FiredTrigger, ...], tuple[TriggerSuppression, ...]]:
    assert trigger.every_days is not None
    last_fire = config.runtime.last_fire_date(trigger.name, None)
    evidence: dict[str, Any] = {
        "type": "schedule",
        "every_days": trigger.every_days,
        "last_fire_at": last_fire.isoformat() if last_fire else None,
        "as_of": as_of.isoformat(),
    }
    condition_instance = (
        f"schedule:{trigger.name}:period:{as_of.toordinal() // trigger.every_days}"
    )
    if last_fire is not None and (as_of - last_fire).days < trigger.every_days:
        suppression = TriggerSuppression(
            trigger_name=trigger.name,
            reason="schedule",
            as_of=as_of.isoformat(),
            account_id=None,
            account_name=None,
            condition_instance=condition_instance,
            evidence=evidence,
        )
        return (), (suppression,)
    return (_build_fired(trigger, as_of, None, None, condition_instance, evidence, config),), ()


def _deadline_candidates(
    trigger: TriggerRule,
    state: TriggerState,
    as_of: date,
    config: TriggerConfig,
) -> tuple[FiredTrigger, ...]:
    candidates: list[FiredTrigger] = []
    for account in sorted(state.accounts, key=lambda item: item.account_id):
        if all(_deadline_predicate_matches(predicate, account, as_of) for predicate in trigger.when):
            evidence = {
                "type": "deadline",
                "predicates": [
                    _deadline_evidence(predicate, account, as_of)
                    for predicate in trigger.when
                ],
            }
            condition_instance = (
                f"deadline:{trigger.name}:{account.account_id}:"
                f"{_condition_payload(evidence)}:{as_of.isoformat()}"
            )
            candidates.append(_build_fired(
                trigger,
                as_of,
                account.account_id,
                account.account_name,
                condition_instance,
                evidence,
                config,
            ))
    return tuple(candidates)


def _event_candidates(
    trigger: TriggerRule,
    state: TriggerState,
    prev_snapshot: TriggerState | None,
    as_of: date,
    config: TriggerConfig,
) -> tuple[FiredTrigger, ...]:
    if prev_snapshot is None or prev_snapshot.day is None or state.day is None:
        return ()
    prev_by_account = prev_snapshot.by_account()
    candidates: list[FiredTrigger] = []
    for account in sorted(state.accounts, key=lambda item: item.account_id):
        previous = prev_by_account.get(account.account_id)
        if previous is None:
            continue
        evidence_parts: list[dict[str, Any]] = []
        matched = True
        for predicate in trigger.when:
            event_evidence = _transition_evidence(predicate, previous, account, prev_snapshot.day, state.day)
            if event_evidence is None:
                matched = False
                break
            evidence_parts.append(event_evidence)
        if not matched:
            continue
        evidence = {"type": "event", "transitions": evidence_parts}
        condition_instance = (
            f"event:{trigger.name}:{account.account_id}:"
            f"{_condition_payload(evidence)}"
        )
        candidates.append(_build_fired(
            trigger,
            as_of,
            account.account_id,
            account.account_name,
            condition_instance,
            evidence,
            config,
        ))
    return tuple(candidates)


def _deadline_predicate_matches(
    predicate: TriggerPredicate,
    account: AccountTriggerState,
    as_of: date,
) -> bool:
    value = account.attrs().get(predicate.field)
    if value in (None, ""):
        return False
    target = _parse_date(value)
    days_until = (target - as_of).days
    return 0 <= days_until <= int(predicate.value)


def _deadline_evidence(
    predicate: TriggerPredicate,
    account: AccountTriggerState,
    as_of: date,
) -> dict[str, Any]:
    value = account.attrs()[predicate.field]
    target = _parse_date(value)
    return {
        "field": predicate.field,
        "op": predicate.op,
        "value": predicate.value,
        "field_value": target.isoformat(),
        "days_until": (target - as_of).days,
    }


def _transition_evidence(
    predicate: TriggerPredicate,
    previous: AccountTriggerState,
    current: AccountTriggerState,
    from_day: int,
    to_day: int,
) -> dict[str, Any] | None:
    prev_value = previous.attrs().get(predicate.field)
    new_value = current.attrs().get(predicate.field)
    if prev_value in (None, "", "unknown") or new_value in (None, "", "unknown"):
        return None

    store = SnapshotStore()
    store.store_snapshot(from_day, current.account_id, previous.to_snapshot_payload())
    store.store_snapshot(to_day, current.account_id, current.to_snapshot_payload())
    change = store.detect_band_change(current.account_id, from_day, to_day)
    if change is None:
        return None

    from_expected, to_expected = predicate.value
    if from_expected != "*" and change.old_band != from_expected:
        return None
    if to_expected != "*" and change.new_band != to_expected:
        return None
    return {
        "field": predicate.field,
        "op": predicate.op,
        "value": list(predicate.value),
        "from": change.old_band,
        "to": change.new_band,
        "from_day": change.from_day,
        "to_day": change.to_day,
        "direction": change.direction,
    }


def _noise_suppression(
    trigger: TriggerRule,
    fired: FiredTrigger,
    as_of: date,
    runtime: TriggerRuntime,
) -> TriggerSuppression | None:
    if trigger.cooldown_days > 0:
        last_fire = runtime.last_fire_date(trigger.name, fired.account_id)
        if last_fire is not None and (as_of - last_fire).days <= trigger.cooldown_days:
            return TriggerSuppression(
                trigger_name=trigger.name,
                reason="cooldown",
                as_of=as_of.isoformat(),
                account_id=fired.account_id,
                account_name=fired.account_name,
                condition_instance=fired.condition_instance,
                evidence={
                    **fired.evidence,
                    "last_fire_at": last_fire.isoformat(),
                    "cooldown_days": trigger.cooldown_days,
                    "days_since_fire": (as_of - last_fire).days,
                },
            )

    if runtime.has_pending(trigger.name, fired.account_id):
        return TriggerSuppression(
            trigger_name=trigger.name,
            reason="pending_proposal",
            as_of=as_of.isoformat(),
            account_id=fired.account_id,
            account_name=fired.account_name,
            condition_instance=fired.condition_instance,
            evidence={
                **fired.evidence,
                "pending_trigger_account": _runtime_account_key(fired.account_id),
            },
        )

    if fired.idempotency_key in runtime.fired_idempotency_keys:
        return TriggerSuppression(
            trigger_name=trigger.name,
            reason="idempotent_fired_ledger",
            as_of=as_of.isoformat(),
            account_id=fired.account_id,
            account_name=fired.account_name,
            condition_instance=fired.condition_instance,
            evidence={**fired.evidence, "idempotency_key": fired.idempotency_key},
        )

    return None


def _build_fired(
    trigger: TriggerRule,
    as_of: date,
    account_id: str | None,
    account_name: str | None,
    condition_instance: str,
    evidence: dict[str, Any],
    config: TriggerConfig,
) -> FiredTrigger:
    return FiredTrigger(
        trigger_name=trigger.name,
        config_version=config.config_version,
        kind=trigger.kind,
        action=trigger.action,
        account_id=account_id,
        account_name=account_name,
        as_of=as_of.isoformat(),
        evidence=evidence,
        condition_instance=condition_instance,
        idempotency_key=idempotency_key_for(
            trigger.name,
            account_id,
            condition_instance,
        ),
    )


def _condition_payload(evidence: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    return digest


def _parse_date(value: str | datetime | date) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value)
    if "T" in text:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    return date.fromisoformat(text)


def _runtime_account_key(account_id: str | None) -> str:
    return account_id or _BOOK_ACCOUNT
