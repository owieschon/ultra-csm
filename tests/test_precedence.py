"""Pure precedence and hold-state tests for Lane E2."""

from __future__ import annotations

import pytest

from ultra_csm.agent1.precedence import (
    ActionPacket,
    FindingPacket,
    OverrideRequest,
    PrecedenceConfigError,
    PrecedenceStateError,
    approval_decision,
    classify_action,
    classify_finding,
    commit_decision,
    conflict_context_refs,
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

AS_OF = "2026-07-02T10:00:00Z"


def test_default_config_contains_ratified_risk_and_ttv_gap_matrix():
    config = load_precedence_config()

    assert {
        (rule.blocker, rule.blocked, rule.scope)
        for rule in config.precedence
    } == {
        ("risk", "expansion", "customer_facing"),
        ("ttv_gap", "expansion", "customer_facing"),
    }


@pytest.mark.parametrize(
    "raw",
    [
        {"authority": "tier-3"},
        {"precedence": [{"blocker": "risk", "blocked": "expansion", "scope": "customer_facing", "tier": 3}]},
        {
            "precedence": [{
                "blocker": "risk",
                "blocked": "expansion",
                "scope": "customer_facing",
                "release_condition": "auto",
            }],
        },
        {
            "precedence": [{
                "blocker": "risk",
                "blocked": "expansion",
                "scope": "customer_facing",
                "recipient": "customer",
            }],
        },
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
        {"precedence": [{"blocker": "unknown", "blocked": "expansion", "scope": "customer_facing"}]},
        {"precedence": [{"blocker": "risk", "blocked": "expansion", "scope": "internal"}]},
        {"precedence": [{"blocker": "risk", "blocked": "risk", "scope": "customer_facing"}]},
    ],
)
def test_precedence_config_unsafe_foils_fail_closed(raw):
    candidate = {"config_version": "precedence-v1", **raw}

    with pytest.raises(PrecedenceConfigError):
        parse_precedence_config(candidate)


def test_findings_stay_visible_while_customer_facing_expansion_action_is_held():
    config = load_precedence_config()
    risk = _finding("risk", "risk-1", "risk-ci-1")
    expansion_finding = _finding("expansion", "expansion-1", "expansion-ci-1")
    customer_action = _action("expansion-customer-t0", scope="customer_facing", tier=3)
    internal_flag = _action(
        "expansion-internal-flag",
        scope="internal",
        action_type="expansion_ready_flag",
        tier=1,
    )
    risk_action = _action(
        "risk-internal",
        lens="risk",
        scope="internal",
        action_type="recommend_next_best_action",
        tier=1,
    )

    result = evaluate_precedence(
        (risk, expansion_finding),
        (customer_action, internal_flag, risk_action),
        config,
        as_of=AS_OF,
    )

    assert classify_finding(risk, config) == "blocking"
    assert classify_action(customer_action, config) == "precedence_gated"
    assert {finding.finding_id for finding in result.visible_findings} == {
        "risk-1",
        "expansion-1",
    }
    assert [held.action.action_id for held in result.held_actions] == ["expansion-customer-t0"]
    assert result.held_actions[0].blocking_refs == ("risk-1",)
    assert {active.action.action_id for active in result.active_actions} == {
        "expansion-internal-flag",
        "risk-internal",
    }
    internal = next(
        item for item in result.active_actions if item.action.action_id == "expansion-internal-flag"
    )
    assert internal.conflict_context_refs == ("risk-1",)
    assert [event.event_type for event in result.ledger_events] == ["hold_created"]


def test_approve_refused_while_held_and_commit_rechecks_current_blockers():
    config = load_precedence_config()
    action = _action("expansion-customer-t0")
    risk = _finding("risk", "risk-1", "risk-ci-1")

    refused = approval_decision(action, (risk,), config, as_of=AS_OF)
    assert refused.allowed is False
    assert refused.reason == "held_current_blocker"
    assert refused.blocking_refs == ("risk-1",)
    assert refused.ledger_events[0].event_type == "approval_refused"

    approved_before_new_blocker = approval_decision(action, (), config, as_of=AS_OF)
    assert approved_before_new_blocker.allowed is True

    blocked_at_commit = commit_decision(action, (risk,), config, as_of=AS_OF)
    assert blocked_at_commit.allowed is False
    assert blocked_at_commit.reason == "blocked_current_state"
    assert blocked_at_commit.ledger_events[0].event_type == "commit_blocked"


def test_release_rederives_fresh_item_and_rejects_stale_payload_replay():
    held = create_held_action(
        _action("expansion-customer-t0", payload={"draft": "t0", "evidence": "old"}),
        ("risk-1",),
        as_of=AS_OF,
    )
    fresh = _action("expansion-customer-t1", payload={"draft": "t1", "evidence": "current"})

    result = rederive_hold_release(
        held,
        current_blocking_refs=(),
        current_candidate=fresh,
        as_of="2026-07-02T10:05:00Z",
    )

    assert result.outcome == "fresh"
    assert result.active_action == fresh
    assert result.closed_hold is not None
    assert result.closed_hold.reason == "superseded"
    assert result.closed_hold.old_payload_sha256 == held.action.payload_sha256
    assert result.closed_hold.replacement_payload_sha256 == fresh.payload_sha256
    assert [event.event_type for event in result.ledger_events] == [
        "hold_released",
        "superseded",
    ]

    validate_rederived_payload(fresh, fresh.payload)
    with pytest.raises(PrecedenceStateError):
        validate_rederived_payload(fresh, held.action.payload)


def test_release_with_new_or_partial_blockers_stays_held_without_active_flash():
    held = create_held_action(
        _action("expansion-customer-t0"),
        ("risk-1", "ttv-1"),
        as_of=AS_OF,
    )
    candidate = _action("expansion-customer-t1", payload={"draft": "fresh"})

    partial_clear = rederive_hold_release(
        held,
        current_blocking_refs=("ttv-1",),
        current_candidate=candidate,
        as_of="2026-07-02T10:05:00Z",
    )

    assert partial_clear.outcome == "held"
    assert partial_clear.active_action is None
    assert partial_clear.held_action is not None
    assert partial_clear.held_action.blocking_refs == ("ttv-1",)
    assert partial_clear.held_action.held_since == AS_OF
    assert partial_clear.ledger_events[0].event_type == "held_to_held"
    assert partial_clear.ledger_events[0].detail["active_flash"] is False


def test_release_with_opportunity_gone_expires_loudly_with_history_visible():
    held = create_held_action(_action("expansion-customer-t0"), ("risk-1",), as_of=AS_OF)

    result = rederive_hold_release(
        held,
        current_blocking_refs=(),
        current_candidate=None,
        as_of="2026-07-02T10:05:00Z",
    )

    assert result.outcome == "expired"
    assert result.active_action is None
    assert result.closed_hold is not None
    assert result.closed_hold.reason == "expired"
    assert result.closed_hold.history_visible is True
    assert result.ledger_events[0].event_type == "expired"


def test_dismissal_release_is_synchronous_and_sticky_per_condition_instance():
    config = load_precedence_config()
    action = _action("expansion-customer-t0")
    risk = _finding("risk", "risk-1", "risk-ci-1")
    held = create_held_action(action, ("risk-1",), as_of=AS_OF)

    event = finding_disposition_event(
        risk,
        disposition="dismiss",
        actor_id="human-1",
        as_of="2026-07-02T10:01:00Z",
        note="factor no longer applies",
    )
    dismissed = dismissed_condition_instances((event,))

    assert current_blocking_refs(action, (risk,), config, dismissed_condition_instances=dismissed) == ()
    fresh = _action("expansion-customer-t1", payload={"draft": "current"})
    released = rederive_hold_release(
        held,
        current_blocking_refs=(),
        current_candidate=fresh,
        as_of="2026-07-02T10:02:00Z",
    )
    assert released.outcome == "fresh"

    same_instance = _finding("risk", "risk-2", "risk-ci-1")
    new_instance = _finding("risk", "risk-3", "risk-ci-2")
    assert current_blocking_refs(
        action,
        (same_instance,),
        config,
        dismissed_condition_instances=dismissed,
    ) == ()
    assert current_blocking_refs(
        action,
        (new_instance,),
        config,
        dismissed_condition_instances=dismissed,
    ) == ("risk-3",)


def test_override_requires_blocked_action_tier_current_refs_and_justification():
    held = create_held_action(_action("expansion-customer-t0", tier=3), ("risk-1",), as_of=AS_OF)
    current_refs = ("risk-1", "ttv-1")

    good = validate_override(
        held,
        OverrideRequest(
            actor_id="leader-1",
            authorized_tiers=(3,),
            named_refs=("ttv-1", "risk-1"),
            justification="Customer exec has approved the consult despite active blockers.",
        ),
        current_blocking_refs=current_refs,
        as_of="2026-07-02T10:06:00Z",
    )
    assert good.allowed is True
    assert good.ledger_events[0].event_type == "override_released"

    wrong_tier = validate_override(
        held,
        OverrideRequest("leader-1", (2,), current_refs, "reviewed"),
        current_blocking_refs=current_refs,
        as_of="2026-07-02T10:06:00Z",
    )
    assert wrong_tier.allowed is False
    assert wrong_tier.reason == "wrong_tier"

    stale_refs = validate_override(
        held,
        OverrideRequest("leader-1", (3,), ("risk-1",), "reviewed"),
        current_blocking_refs=current_refs,
        as_of="2026-07-02T10:06:00Z",
    )
    assert stale_refs.allowed is False
    assert stale_refs.reason == "stale_refs"

    missing_justification = validate_override(
        held,
        OverrideRequest("leader-1", (3,), current_refs, "  "),
        current_blocking_refs=current_refs,
        as_of="2026-07-02T10:06:00Z",
    )
    assert missing_justification.allowed is False
    assert missing_justification.reason == "missing_justification"


def test_flap_notification_dedupe_uses_hold_event_idempotency_key():
    config = load_precedence_config()
    result = evaluate_precedence(
        (_finding("risk", "risk-1", "risk-ci-1"),),
        (_action("expansion-customer-t0"),),
        config,
        as_of=AS_OF,
    )
    event = result.ledger_events[0]

    first = hold_notification_decision(event, frozenset())
    second = hold_notification_decision(event, frozenset({event.idempotency_key}))

    assert first.should_notify is True
    assert first.reason == "new"
    assert second.should_notify is False
    assert second.reason == "deduped"


def test_conflict_context_reports_blockers_without_suppressing_internal_actions():
    config = load_precedence_config()
    internal = _action("expansion-internal-flag", scope="internal", tier=1)
    risk = _finding("risk", "risk-1", "risk-ci-1")

    assert current_blocking_refs(internal, (risk,), config) == ()
    assert conflict_context_refs(internal, (risk,), config) == ("risk-1",)


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
