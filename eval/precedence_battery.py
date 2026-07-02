"""Deterministic precedence battery for Lane E2."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ultra_csm.agent1.precedence import (
    ActionPacket,
    FindingPacket,
    OverrideRequest,
    PrecedenceConfigError,
    PrecedenceStateError,
    approval_decision,
    commit_decision,
    create_held_action,
    current_blocking_refs,
    dismissed_condition_instances,
    evaluate_precedence,
    finding_disposition_event,
    hold_notification_decision,
    load_precedence_config,
    parse_precedence_config,
    rederive_hold_release,
    validate_override,
    validate_rederived_payload,
)

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO / "eval" / "precedence_battery.json"
AS_OF = "2026-07-02T10:00:00Z"


@dataclass(frozen=True)
class BatteryCase:
    case_id: str
    passed: bool
    hard_gate: bool
    detail: str


def build_precedence_battery_artifact(output_path: Path = DEFAULT_OUTPUT) -> dict:
    cases = [_run_case(case) for case in CASES]
    hard_failures = [case.case_id for case in cases if case.hard_gate and not case.passed]
    artifact = {
        "artifact": "precedence_battery",
        "claim_boundary": {"sim": True, "fixture": True, "live": False},
        "measurement_scope": (
            "Pure precedence packet evaluation and release re-derivation. "
            "No database, live claims, connector calls, queue renderer, or LLM."
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


def creation_into_held() -> None:
    result = evaluate_precedence((_finding("risk", "risk-1", "risk-ci-1"),), (_action("a0"),), _config(), as_of=AS_OF)
    assert len(result.held_actions) == 1
    assert result.held_actions[0].blocking_refs == ("risk-1",)
    assert result.ledger_events[0].event_type == "hold_created"


def approve_refused_while_held() -> None:
    decision = approval_decision(
        _action("a0"),
        (_finding("risk", "risk-1", "risk-ci-1"),),
        _config(),
        as_of=AS_OF,
    )
    assert decision.allowed is False
    assert decision.ledger_events[0].event_type == "approval_refused"


def commit_blocked_post_approval() -> None:
    action = _action("a0")
    assert approval_decision(action, (), _config(), as_of=AS_OF).allowed is True
    blocked = commit_decision(
        action,
        (_finding("risk", "risk-1", "risk-ci-1"),),
        _config(),
        as_of=AS_OF,
    )
    assert blocked.allowed is False
    assert blocked.ledger_events[0].event_type == "commit_blocked"


def organic_release_rederives_fresh_item() -> None:
    held = create_held_action(_action("a0"), ("risk-1",), as_of=AS_OF)
    fresh = _action("a1", payload={"draft": "fresh", "evidence": "t1"})
    result = rederive_hold_release(
        held,
        current_blocking_refs=(),
        current_candidate=fresh,
        as_of="2026-07-02T10:05:00Z",
    )
    assert result.outcome == "fresh"
    assert result.active_action == fresh
    assert result.closed_hold is not None and result.closed_hold.reason == "superseded"


def synchronous_dismissal_release() -> None:
    action = _action("a0")
    risk = _finding("risk", "risk-1", "risk-ci-1")
    dismiss = finding_disposition_event(
        risk,
        disposition="dismiss",
        actor_id="human-1",
        as_of="2026-07-02T10:01:00Z",
    )
    dismissed = dismissed_condition_instances((dismiss,))
    assert current_blocking_refs(action, (risk,), _config(), dismissed_condition_instances=dismissed) == ()
    held = create_held_action(action, ("risk-1",), as_of=AS_OF)
    result = rederive_hold_release(
        held,
        current_blocking_refs=(),
        current_candidate=_action("a1"),
        as_of="2026-07-02T10:01:00Z",
    )
    assert result.outcome == "fresh"


def sticky_dismissal_no_rehold() -> None:
    action = _action("a0")
    risk = _finding("risk", "risk-1", "risk-ci-1")
    dismiss = finding_disposition_event(
        risk,
        disposition="dismiss",
        actor_id="human-1",
        as_of="2026-07-02T10:01:00Z",
    )
    same_instance = _finding("risk", "risk-2", "risk-ci-1")
    dismissed = dismissed_condition_instances((dismiss,))
    assert current_blocking_refs(
        action,
        (same_instance,),
        _config(),
        dismissed_condition_instances=dismissed,
    ) == ()


def new_instance_rehold() -> None:
    action = _action("a0")
    dismiss = finding_disposition_event(
        _finding("risk", "risk-1", "risk-ci-1"),
        disposition="dismiss",
        actor_id="human-1",
        as_of="2026-07-02T10:01:00Z",
    )
    dismissed = dismissed_condition_instances((dismiss,))
    assert current_blocking_refs(
        action,
        (_finding("risk", "risk-2", "risk-ci-2"),),
        _config(),
        dismissed_condition_instances=dismissed,
    ) == ("risk-2",)


def release_with_new_blocker_without_active_flash() -> None:
    held = create_held_action(_action("a0"), ("risk-1",), as_of=AS_OF)
    result = rederive_hold_release(
        held,
        current_blocking_refs=("ttv-1",),
        current_candidate=_action("a1"),
        as_of="2026-07-02T10:05:00Z",
    )
    assert result.outcome == "held"
    assert result.active_action is None
    assert result.held_action is not None and result.held_action.held_since == AS_OF
    assert result.ledger_events[0].detail["active_flash"] is False


def release_with_stale_evidence_supersedes_old_payload() -> None:
    held = create_held_action(
        _action("a0", payload={"draft": "old", "evidence": "t0"}),
        ("risk-1",),
        as_of=AS_OF,
    )
    fresh = _action("a1", payload={"draft": "fresh", "evidence": "t1"})
    result = rederive_hold_release(
        held,
        current_blocking_refs=(),
        current_candidate=fresh,
        as_of="2026-07-02T10:05:00Z",
    )
    assert result.closed_hold is not None
    assert result.closed_hold.old_payload_sha256 != result.closed_hold.replacement_payload_sha256
    assert [event.event_type for event in result.ledger_events] == ["hold_released", "superseded"]


def opportunity_gone_expires_loudly() -> None:
    result = rederive_hold_release(
        create_held_action(_action("a0"), ("risk-1",), as_of=AS_OF),
        current_blocking_refs=(),
        current_candidate=None,
        as_of="2026-07-02T10:05:00Z",
    )
    assert result.outcome == "expired"
    assert result.closed_hold is not None and result.closed_hold.history_visible is True
    assert result.ledger_events[0].event_type == "expired"


def multi_blocker_partial_clear_stays_held() -> None:
    held = create_held_action(_action("a0"), ("risk-1", "ttv-1"), as_of=AS_OF)
    result = rederive_hold_release(
        held,
        current_blocking_refs=("ttv-1",),
        current_candidate=_action("a1"),
        as_of="2026-07-02T10:05:00Z",
    )
    assert result.outcome == "held"
    assert result.held_action is not None and result.held_action.blocking_refs == ("ttv-1",)


def override_with_justification_and_wrong_tier_refused() -> None:
    held = create_held_action(_action("a0", tier=3), ("risk-1",), as_of=AS_OF)
    good = validate_override(
        held,
        OverrideRequest("leader-1", (3,), ("risk-1",), "approved against current refs"),
        current_blocking_refs=("risk-1",),
        as_of="2026-07-02T10:06:00Z",
    )
    wrong = validate_override(
        held,
        OverrideRequest("leader-1", (2,), ("risk-1",), "approved against current refs"),
        current_blocking_refs=("risk-1",),
        as_of="2026-07-02T10:06:00Z",
    )
    stale = validate_override(
        held,
        OverrideRequest("leader-1", (3,), ("risk-1",), "approved against current refs"),
        current_blocking_refs=("risk-1", "ttv-1"),
        as_of="2026-07-02T10:06:00Z",
    )
    assert good.allowed is True
    assert wrong.allowed is False and wrong.reason == "wrong_tier"
    assert stale.allowed is False and stale.reason == "stale_refs"


def flap_notification_dedupe() -> None:
    event = evaluate_precedence(
        (_finding("risk", "risk-1", "risk-ci-1"),),
        (_action("a0"),),
        _config(),
        as_of=AS_OF,
    ).ledger_events[0]
    assert hold_notification_decision(event, frozenset()).should_notify is True
    assert hold_notification_decision(event, frozenset({event.idempotency_key})).should_notify is False


def held_item_visible_hard_gate() -> None:
    result = evaluate_precedence(
        (
            _finding("risk", "risk-1", "risk-ci-1"),
            _finding("expansion", "expansion-1", "expansion-ci-1"),
        ),
        (_action("a0"),),
        _config(),
        as_of=AS_OF,
    )
    assert result.held_actions
    assert {finding.finding_id for finding in result.visible_findings} == {
        "risk-1",
        "expansion-1",
    }


def replay_falsification_rejects_t0_payload_after_evidence_moves() -> None:
    held = create_held_action(
        _action("a0", payload={"draft": "old", "evidence": "t0"}),
        ("risk-1",),
        as_of=AS_OF,
    )
    fresh = _action("a1", payload={"draft": "fresh", "evidence": "t1"})
    result = rederive_hold_release(
        held,
        current_blocking_refs=(),
        current_candidate=fresh,
        as_of="2026-07-02T10:05:00Z",
    )
    assert result.active_action == fresh
    try:
        validate_rederived_payload(fresh, held.action.payload)
    except PrecedenceStateError:
        return
    raise AssertionError("stale T0 payload replay was accepted")


def config_unsafe_foils_rejected() -> None:
    foils = (
        {"precedence": [{"blocker": "risk", "blocked": "expansion", "scope": "customer_facing", "authority": "x"}]},
        {"precedence": [{"blocker": "risk", "blocked": "expansion", "scope": "customer_facing", "recipient": "customer"}]},
        {
            "precedence": [{
                "blocker": "risk",
                "blocked": "expansion",
                "scope": "customer_facing",
                "awareness_suppression": True,
            }],
        },
        {
            "precedence": [{
                "blocker": "risk",
                "blocked": "expansion",
                "scope": "customer_facing",
                "internal_suppression": True,
            }],
        },
        {"precedence": [{"blocker": "sentiment", "blocked": "expansion", "scope": "customer_facing"}]},
        {"precedence": [{"blocker": "risk", "blocked": "expansion", "scope": "internal"}]},
    )
    for raw in foils:
        try:
            parse_precedence_config({"config_version": "precedence-v1", **raw})
        except PrecedenceConfigError:
            continue
        raise AssertionError(f"unsafe foil loaded: {raw}")


def cross_lens_fixture() -> None:
    result = evaluate_precedence(
        (
            _finding("risk", "risk-1", "risk-ci-1"),
            _finding("expansion", "expansion-1", "expansion-ci-1"),
        ),
        (
            _action("expansion-customer", scope="customer_facing", tier=3),
            _action("expansion-internal", scope="internal", tier=1),
        ),
        _config(),
        as_of=AS_OF,
    )
    assert {finding.lens for finding in result.visible_findings} == {"risk", "expansion"}
    assert [held.action.action_id for held in result.held_actions] == ["expansion-customer"]
    internal = next(item for item in result.active_actions if item.action.action_id == "expansion-internal")
    assert internal.conflict_context_refs == ("risk-1",)


CASES: tuple[Callable[[], None], ...] = (
    creation_into_held,
    approve_refused_while_held,
    commit_blocked_post_approval,
    organic_release_rederives_fresh_item,
    synchronous_dismissal_release,
    sticky_dismissal_no_rehold,
    new_instance_rehold,
    release_with_new_blocker_without_active_flash,
    release_with_stale_evidence_supersedes_old_payload,
    opportunity_gone_expires_loudly,
    multi_blocker_partial_clear_stays_held,
    override_with_justification_and_wrong_tier_refused,
    flap_notification_dedupe,
    held_item_visible_hard_gate,
    replay_falsification_rejects_t0_payload_after_evidence_moves,
    config_unsafe_foils_rejected,
    cross_lens_fixture,
)


def _run_case(fn: Callable[[], None]) -> BatteryCase:
    print(f"precedence_battery: {fn.__name__}")
    try:
        fn()
    except AssertionError as exc:
        return BatteryCase(fn.__name__, False, True, str(exc) or "assertion failed")
    except Exception as exc:
        return BatteryCase(fn.__name__, False, True, f"{type(exc).__name__}: {exc}")
    return BatteryCase(fn.__name__, True, True, "passed")


def _config():
    return load_precedence_config()


def _finding(lens: str, finding_id: str, condition_instance: str) -> FindingPacket:
    return FindingPacket(
        finding_id=finding_id,
        account_id="acct-1",
        lens=lens,  # type: ignore[arg-type]
        condition_instance=condition_instance,
        evidence_refs=(f"ev:{finding_id}",),
        payload={"summary": finding_id},
    )


def _action(
    action_id: str,
    *,
    lens: str = "expansion",
    scope: str = "customer_facing",
    action_type: str = "initiate_customer_call",
    tier: int = 3,
    payload: dict | None = None,
) -> ActionPacket:
    return ActionPacket(
        action_id=action_id,
        account_id="acct-1",
        lens=lens,  # type: ignore[arg-type]
        scope=scope,  # type: ignore[arg-type]
        action_type=action_type,
        autonomy_tier=tier,
        payload=payload or {"draft": action_id, "evidence": "current"},
        finding_id="expansion-1",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    artifact = build_precedence_battery_artifact(output_path=args.output)
    score = artifact["score"]
    print(
        "Precedence battery: "
        f"{score['passed']}/{score['total']} hard_ok={artifact['hard_ok']}"
    )
    print(f"battery JSON -> {args.output}")
    return 0 if artifact["hard_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
