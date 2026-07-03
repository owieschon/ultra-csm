"""Deterministic trigger battery for Lane F."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ultra_csm.governance import proposal_fields_for
from ultra_csm.triggers import (
    AccountTriggerState,
    FiredTrigger,
    TriggerConfigError,
    TriggerRuntime,
    TriggerState,
    evaluate_trigger_decisions,
    evaluate_triggers,
    parse_trigger_config,
)

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO / "eval" / "trigger_battery.json"


@dataclass(frozen=True)
class BatteryCase:
    case_id: str
    passed: bool
    hard_gate: bool
    detail: str


def build_trigger_battery_artifact(output_path: Path = DEFAULT_OUTPUT) -> dict:
    cases = [_run_case(case) for case in CASES]
    hard_failures = [case.case_id for case in cases if case.hard_gate and not case.passed]
    artifact = {
        "artifact": "trigger_battery",
        "claim_boundary": {"sim": True, "fixture": True, "live": False},
        "measurement_scope": (
            "Pure trigger evaluation over fixture state plus action taxonomy "
            "authority guard; no daemon, webhook server, queue, network, or LLM."
        ),
        "score": {
            "passed": sum(1 for case in cases if case.passed),
            "total": len(cases),
        },
        "hard_ok": not hard_failures,
        "hard_failures": hard_failures,
        "cases": [case.__dict__ for case in cases],
    }
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def fires_schedule_boundary() -> None:
    config = _schedule_config()
    fired = evaluate_triggers(TriggerState(day=0, accounts=()), None, "2026-06-21", config)
    assert len(fired) == 1
    assert fired[0].trigger_name == "daily_ttv"
    assert fired[0].evidence["type"] == "schedule"


def fires_deadline_horizon() -> None:
    config = _deadline_config()
    state = TriggerState(day=0, accounts=(_account("acct-1", renewal_date="2026-08-01"),))
    fired = evaluate_triggers(state, None, "2026-06-21", config)
    assert len(fired) == 1
    assert fired[0].account_id == "acct-1"
    assert fired[0].evidence["predicates"][0]["days_until"] == 41


def fires_band_transition() -> None:
    config = _event_config()
    prev = TriggerState(day=0, accounts=(_account("acct-1", band="green"),))
    current = TriggerState(day=1, accounts=(_account("acct-1", band="red"),))
    fired = evaluate_triggers(current, prev, "2026-06-22", config)
    assert len(fired) == 1
    assert fired[0].evidence["transitions"][0]["from"] == "green"
    assert fired[0].evidence["transitions"][0]["to"] == "red"


def not_fire_cooldown() -> None:
    config = _deadline_config(cooldown_days=30)
    state = TriggerState(day=0, accounts=(_account("acct-1", renewal_date="2026-08-01"),))
    decision = evaluate_trigger_decisions(
        state,
        None,
        "2026-06-30",
        config.with_runtime(TriggerRuntime(
            last_fire_at=(("renewal_window", "acct-1", "2026-06-21"),),
        )),
    )
    assert decision.fired == ()
    assert [item.reason for item in decision.suppressions] == ["cooldown"]


def not_fire_stable_band() -> None:
    config = _event_config()
    prev = TriggerState(day=0, accounts=(_account("acct-1", band="green"),))
    current = TriggerState(day=1, accounts=(_account("acct-1", band="green"),))
    assert evaluate_triggers(current, prev, "2026-06-22", config) == ()


def not_fire_missing_snapshot() -> None:
    config = _event_config()
    current = TriggerState(day=1, accounts=(_account("acct-1", band="red"),))
    assert evaluate_triggers(current, None, "2026-06-22", config) == ()


def not_fire_absent_date_field() -> None:
    config = _deadline_config()
    state = TriggerState(day=0, accounts=(_account("acct-1", renewal_date=None),))
    assert evaluate_triggers(state, None, "2026-06-21", config) == ()


def not_fire_pending_proposal() -> None:
    config = _deadline_config()
    state = TriggerState(day=0, accounts=(_account("acct-1", renewal_date="2026-08-01"),))
    decision = evaluate_trigger_decisions(
        state,
        None,
        "2026-06-21",
        config.with_runtime(TriggerRuntime(
            pending_trigger_accounts=frozenset({("renewal_window", "acct-1")}),
        )),
    )
    assert decision.fired == ()
    assert [item.reason for item in decision.suppressions] == ["pending_proposal"]


def reproducible_fired_tuple_and_ledger_entry() -> None:
    config = _deadline_config()
    state = TriggerState(day=0, accounts=(_account("acct-1", renewal_date="2026-08-01"),))
    first = evaluate_trigger_decisions(state, None, "2026-06-21", config)
    second = evaluate_trigger_decisions(state, None, "2026-06-21", config)
    assert first == second
    assert _ledger_entry(first.fired) == _ledger_entry(second.fired)


def fired_provenance_complete() -> None:
    config = _deadline_config()
    state = TriggerState(day=0, accounts=(_account("acct-1", renewal_date="2026-08-01"),))
    fired = evaluate_triggers(state, None, "2026-06-21", config)[0]
    payload = fired.to_dict()
    assert payload["trigger_name"]
    assert payload["config_version"] == "test-triggers"
    assert payload["as_of"] == "2026-06-21"
    assert payload["evidence"]["predicates"][0]["field_value"] == "2026-08-01"
    assert payload["idempotency_key"].startswith("trigger:")


def unsafe_foil_rejected() -> None:
    for bad_action in (
        {"lens": "ttv", "scope": "book", "tier": 1},
        {"lens": "ttv", "scope": "book", "release_condition": "auto"},
        {"lens": "ttv", "scope": "book", "recipient": "customer"},
        {"lens": "risk", "scope": "account"},
    ):
        try:
            parse_trigger_config({
                "config_version": "test-triggers",
                "triggers": [{
                    "name": "unsafe",
                    "kind": "schedule",
                    "every": "1d",
                    "action": bad_action,
                }],
            })
        except TriggerConfigError:
            continue
        raise AssertionError(f"unsafe config loaded: {bad_action}")


def downstream_action_taxonomy_tier_preserved() -> None:
    config = _deadline_config()
    state = TriggerState(day=0, accounts=(_account("acct-1", renewal_date="2026-08-01"),))
    fired = evaluate_triggers(state, None, "2026-06-21", config)[0]
    assert "tier" not in fired.action.to_dict()
    assert proposal_fields_for("draft_customer_outreach") == {
        "action": "draft_customer_outreach",
        "autonomy_tier": 2,
        "required_permission": "customer.outreach.draft",
    }


CASES: tuple[Callable[[], None], ...] = (
    fires_schedule_boundary,
    fires_deadline_horizon,
    fires_band_transition,
    not_fire_cooldown,
    not_fire_stable_band,
    not_fire_missing_snapshot,
    not_fire_absent_date_field,
    not_fire_pending_proposal,
    reproducible_fired_tuple_and_ledger_entry,
    fired_provenance_complete,
    unsafe_foil_rejected,
    downstream_action_taxonomy_tier_preserved,
)


def _run_case(fn: Callable[[], None]) -> BatteryCase:
    print(f"trigger_battery: {fn.__name__}")
    try:
        fn()
    except AssertionError as exc:
        return BatteryCase(fn.__name__, False, True, str(exc) or "assertion failed")
    except Exception as exc:
        return BatteryCase(fn.__name__, False, True, f"{type(exc).__name__}: {exc}")
    return BatteryCase(fn.__name__, True, True, "passed")


def _schedule_config():
    return parse_trigger_config({
        "config_version": "test-triggers",
        "triggers": [{
            "name": "daily_ttv",
            "kind": "schedule",
            "every": "1d",
            "action": {"lens": "ttv", "scope": "book"},
        }],
    })


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


def _ledger_entry(fired: tuple[FiredTrigger, ...]) -> dict:
    return {
        "as_of": "2026-06-21",
        "fired_triggers": [item.to_dict() for item in fired],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    artifact = build_trigger_battery_artifact(args.output)
    print(json.dumps({
        "artifact": str(args.output),
        "hard_ok": artifact["hard_ok"],
        "passed": artifact["score"]["passed"],
        "total": artifact["score"]["total"],
    }, indent=2, sort_keys=True))
    return 0 if artifact["hard_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
