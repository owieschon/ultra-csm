"""Deterministic trigger evaluation tests."""

from __future__ import annotations

import pytest

from ultra_csm.triggers import (
    AccountTriggerState,
    DEFAULT_TRIGGER_CONFIG_PATH,
    TriggerConfigError,
    TriggerRuntime,
    TriggerState,
    evaluate_trigger_decisions,
    evaluate_triggers,
    load_trigger_config,
    parse_trigger_config,
)


def test_default_trigger_config_promotes_live_book_lenses():
    config = load_trigger_config(DEFAULT_TRIGGER_CONFIG_PATH)

    assert config.config_version == "triggers-v1"
    triggers_by_name = {trigger.name: trigger for trigger in config.triggers}
    assert set(triggers_by_name) == {
        "daily_ttv",
        "weekly_risk_sweep",
        "weekly_expansion_sweep",
    }
    assert {trigger.action.lens for trigger in config.triggers} == {
        "ttv",
        "risk",
        "expansion",
    }
    assert triggers_by_name["daily_ttv"].action.scope == "book"
    assert triggers_by_name["weekly_risk_sweep"].every_days == 7
    assert triggers_by_name["weekly_expansion_sweep"].every_days == 7


def test_schedule_trigger_is_deterministic_and_respects_boundary():
    config = parse_trigger_config({
        "config_version": "test-triggers",
        "triggers": [{
            "name": "daily_ttv",
            "kind": "schedule",
            "every": "1d",
            "action": {"lens": "ttv", "scope": "book"},
        }],
    })
    state = TriggerState(day=0, accounts=())

    first = evaluate_triggers(state, None, "2026-06-21", config)
    second = evaluate_triggers(state, None, "2026-06-21", config)

    assert first == second
    assert first[0].trigger_name == "daily_ttv"
    assert first[0].account_id is None

    blocked = evaluate_trigger_decisions(
        state,
        None,
        "2026-06-21",
        config.with_runtime(TriggerRuntime(
            last_fire_at=(("daily_ttv", "__book__", "2026-06-21"),),
        )),
    )
    assert blocked.fired == ()
    assert [item.reason for item in blocked.suppressions] == ["schedule"]


def test_deadline_trigger_fires_only_with_positive_date_evidence():
    config = _deadline_config()
    state = TriggerState(day=0, accounts=(
        _account("acct-1", renewal_date="2026-08-01"),
        _account("acct-2", renewal_date=None),
        _account("acct-3", renewal_date="2027-08-01"),
    ))

    fired = evaluate_triggers(state, None, "2026-06-21", config)

    assert [item.account_id for item in fired] == ["acct-1"]
    assert fired[0].evidence["predicates"][0]["days_until"] == 41


def test_event_trigger_uses_previous_snapshot_transition():
    config = _event_config()
    prev = TriggerState(day=0, accounts=(_account("acct-1", band="green"),))
    current = TriggerState(day=10, accounts=(_account("acct-1", band="red"),))

    fired = evaluate_triggers(current, prev, "2026-07-01", config)

    assert len(fired) == 1
    transition = fired[0].evidence["transitions"][0]
    assert transition["from"] == "green"
    assert transition["to"] == "red"
    assert transition["direction"] == "declining"


def test_event_trigger_does_not_fire_without_previous_or_transition():
    config = _event_config()
    current = TriggerState(day=10, accounts=(_account("acct-1", band="green"),))
    stable_prev = TriggerState(day=0, accounts=(_account("acct-1", band="green"),))

    assert evaluate_triggers(current, None, "2026-07-01", config) == ()
    assert evaluate_triggers(current, stable_prev, "2026-07-01", config) == ()


def test_noise_controls_are_deterministic_not_fires():
    config = _deadline_config(cooldown_days=30)
    state = TriggerState(day=0, accounts=(_account("acct-1", renewal_date="2026-08-01"),))
    first = evaluate_triggers(state, None, "2026-06-21", config)[0]

    cooldown = evaluate_trigger_decisions(
        state,
        None,
        "2026-06-30",
        config.with_runtime(TriggerRuntime(
            last_fire_at=(("renewal_window", "acct-1", "2026-06-21"),),
        )),
    )
    assert cooldown.fired == ()
    assert [item.reason for item in cooldown.suppressions] == ["cooldown"]

    idempotent = evaluate_trigger_decisions(
        state,
        None,
        "2026-06-21",
        config.with_runtime(TriggerRuntime(
            fired_idempotency_keys=frozenset({first.idempotency_key}),
        )),
    )
    assert idempotent.fired == ()
    assert [item.reason for item in idempotent.suppressions] == ["idempotent_fired_ledger"]

    pending = evaluate_trigger_decisions(
        state,
        None,
        "2026-06-21",
        config.with_runtime(TriggerRuntime(
            pending_trigger_accounts=frozenset({("renewal_window", "acct-1")}),
        )),
    )
    assert pending.fired == ()
    assert [item.reason for item in pending.suppressions] == ["pending_proposal"]


@pytest.mark.parametrize("key", ["tier", "release_condition", "recipient"])
def test_trigger_config_rejects_authority_keys(key: str):
    raw = {
        "config_version": "test-triggers",
        "triggers": [{
            "name": "unsafe",
            "kind": "schedule",
            "every": "1d",
            "action": {"lens": "ttv", "scope": "book", key: "forbidden"},
        }],
    }

    with pytest.raises(TriggerConfigError):
        parse_trigger_config(raw)


@pytest.mark.parametrize(
    "patch",
    [
        {"kind": "unknown"},
        {"when": [{"field": "unknown", "op": "within_days", "value": 90}]},
        {"when": [{"field": "renewal_date", "op": "unknown", "value": 90}]},
        {"action": {"lens": "not_a_real_lens", "scope": "account"}},
    ],
)
def test_trigger_config_fails_closed_for_unknowns(patch: dict):
    trigger = {
        "name": "renewal_window",
        "kind": "deadline",
        "when": [{"field": "renewal_date", "op": "within_days", "value": 90}],
        "action": {"lens": "ttv", "scope": "account"},
    }
    trigger.update(patch)

    with pytest.raises(TriggerConfigError):
        parse_trigger_config({"config_version": "test-triggers", "triggers": [trigger]})


def _deadline_config(*, cooldown_days: int = 0):
    trigger = {
        "name": "renewal_window",
        "kind": "deadline",
        "when": [{"field": "renewal_date", "op": "within_days", "value": 90}],
        "action": {"lens": "ttv", "scope": "account"},
    }
    if cooldown_days:
        trigger["cooldown_days"] = cooldown_days
    return parse_trigger_config({"config_version": "test-triggers", "triggers": [trigger]})


def _event_config():
    return parse_trigger_config({
        "config_version": "test-triggers",
        "triggers": [{
            "name": "band_drop",
            "kind": "event",
            "when": [{"field": "health_band", "op": "transition", "value": ["green", "*"]}],
            "action": {"lens": "ttv", "scope": "account"},
        }],
    })


def _account(
    account_id: str,
    *,
    band: str = "green",
    renewal_date: str | None = "2026-08-01",
) -> AccountTriggerState:
    return AccountTriggerState(
        account_id=account_id,
        account_name=f"Account {account_id}",
        health_band=band,
        health_score=90.0 if band == "green" else 30.0,
        renewal_date=renewal_date,
        lifecycle_stage="renewal",
        arr_cents=1000000,
        status="Active",
    )
