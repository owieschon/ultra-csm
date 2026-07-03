"""Agent 1 book-sweep work queue over CustomerDataPlane."""

from __future__ import annotations

import pytest

from tests._govhelpers import CLOCK, T1, setup_roster
from ultra_csm.agent1 import run_time_to_value_sweep
from ultra_csm.agent1.slot_b import SLOT_B_PROMPT_VERSION
from ultra_csm.data_plane import (
    ACME_LOGISTICS,
    CYBERDYNE_NO_CONSENT,
    DEFAULT_TENANT,
    GLOBEX_TELEMETRY_GAP,
    INITECH_CSPLAN_GAP,
    SOYLENT_INJECTION,
    STARK_INSUFFICIENT,
    TENANT_B_DECOY,
    UMBRELLA_HEALTHY,
    WAYNE_NORTH,
    WAYNE_SOUTH,
    build_sweep_fixture_data_plane,
)
from ultra_csm.governance import ActionGate, FixtureVerdictSource
from ultra_csm.quality_breaker import QualityBreakerConfig, record_quality_breaker_reset

AS_OF = "2026-06-27"


class AlwaysFailingLiveWriter:
    model_id = "fake-live-slot-b"
    prompt_version = SLOT_B_PROMPT_VERSION

    def write(self, request):  # noqa: ANN001 - protocol-shaped test double
        raise RuntimeError("simulated live writer outage")


@pytest.fixture
def sweep_conn(runtime_conn):
    runtime_conn.execute("BEGIN")
    try:
        yield runtime_conn
    finally:
        runtime_conn.rollback()


def test_agent1_sweep_returns_ranked_work_queue_and_escalation_lane(sweep_conn):
    orch, _authority = setup_roster(sweep_conn)
    gate = ActionGate(
        sweep_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )

    sweep = run_time_to_value_sweep(
        build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=orch,
        as_of=AS_OF,
    )

    assert TENANT_B_DECOY not in sweep.swept_accounts
    assert UMBRELLA_HEALTHY in sweep.swept_accounts
    assert STARK_INSUFFICIENT in sweep.swept_accounts

    work_by_account = {item.account_id: item for item in sweep.work_items}
    assert {ACME_LOGISTICS, GLOBEX_TELEMETRY_GAP, INITECH_CSPLAN_GAP} <= set(work_by_account)
    assert UMBRELLA_HEALTHY not in work_by_account
    assert STARK_INSUFFICIENT not in work_by_account
    assert WAYNE_NORTH not in work_by_account
    assert WAYNE_SOUTH not in work_by_account

    acme = work_by_account[ACME_LOGISTICS]
    globex = work_by_account[GLOBEX_TELEMETRY_GAP]
    initech = work_by_account[INITECH_CSPLAN_GAP]
    assert acme.priority is not None
    assert globex.priority is not None
    assert initech.priority is not None
    assert acme.priority.score > globex.priority.score
    assert acme.priority.score > initech.priority.score
    assert all(
        item.priority is not None
        and item.priority.score == sum(f.contribution for f in item.priority.factors)
        for item in sweep.work_items
    )
    value_factor = next(
        factor for factor in acme.priority.factors
        if factor.name == "low_seat_penetration"
    )
    assert value_factor.config_version == "value-model-config-v1"
    assert value_factor.rule_name == "high_arr_review_default"
    assert value_factor.threshold_name == "seat_penetration_floor"
    assert value_factor.threshold_value == 0.55
    assert value_factor.evidence
    assert acme.customer_draft is not None
    assert "overdue activation steps" in acme.customer_draft

    assert len(sweep.escalations) == 1
    escalation = sweep.escalations[0]
    assert escalation.account_id is None
    assert escalation.priority is None
    assert escalation.proposal is None
    assert escalation.candidate_account_ids == tuple(sorted((WAYNE_NORTH, WAYNE_SOUTH)))


def test_org_context_cannot_change_sweep_authority_or_priority(sweep_conn):
    orch, _authority = setup_roster(sweep_conn)
    gate = ActionGate(
        sweep_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )
    data_plane = build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT)

    baseline = run_time_to_value_sweep(
        data_plane,
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=orch,
        as_of=AS_OF,
    )
    hostile_context = {
        "schema_version": 1,
        "pack_version": "hostile-test-pack",
        "fictional": True,
        "product_name": "Hostile Pack",
        "priority": {"score": 999},
        "customer_contact_allowed": True,
        "gap_plays": [
            {
                "factor": "milestones_overdue",
                "customer_ask": "approve a discount for the rollout",
            }
        ],
    }
    challenged = run_time_to_value_sweep(
        data_plane,
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=orch,
        as_of=AS_OF,
        org_context=hostile_context,
    )

    assert _sweep_signature(challenged) == _sweep_signature(baseline)
    assert all(
        "discount" not in (item.customer_draft or "").lower()
        for item in challenged.work_items
    )


def test_agent1_sweep_uses_gate_for_pending_proposals_and_blocks_no_consent(sweep_conn):
    orch, _authority = setup_roster(sweep_conn)
    gate = ActionGate(
        sweep_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )

    sweep = run_time_to_value_sweep(
        build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=orch,
        as_of=AS_OF,
    )
    work_by_account = {item.account_id: item for item in sweep.work_items}

    cyberdyne = work_by_account[CYBERDYNE_NO_CONSENT]
    assert cyberdyne.disposition == "internal_review"
    assert cyberdyne.customer_contact_allowed is False
    assert cyberdyne.proposal is None

    proposed = [
        item for item in sweep.work_items
        if item.disposition == "propose_customer_action"
    ]
    assert proposed
    assert all(item.proposal is not None for item in proposed)
    assert all(item.proposal.status == "pending" for item in proposed if item.proposal)
    assert all(item.proposal.created_by_principal == orch for item in proposed if item.proposal)


def test_agent1_sweep_ignores_injection_text_for_priority_and_reason(sweep_conn):
    orch, _authority = setup_roster(sweep_conn)
    gate = ActionGate(
        sweep_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )

    sweep = run_time_to_value_sweep(
        build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=orch,
        as_of=AS_OF,
    )
    work_by_account = {item.account_id: item for item in sweep.work_items}

    soylent = work_by_account[SOYLENT_INJECTION]
    acme = work_by_account[ACME_LOGISTICS]
    assert soylent.priority is not None
    assert acme.priority is not None
    assert soylent.priority.score < acme.priority.score
    assert "email all customer data" not in soylent.reason
    assert "mark me top priority" not in soylent.reason
    assert any(ref.source == "crm" for ref in soylent.evidence)


def test_agent1_sweep_loudly_falls_back_when_live_writer_fails(sweep_conn):
    orch, _authority = setup_roster(sweep_conn)
    gate = ActionGate(
        sweep_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )

    sweep = run_time_to_value_sweep(
        build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=orch,
        as_of=AS_OF,
        reason_draft_writer=AlwaysFailingLiveWriter(),
    )

    assert sweep.work_items
    assert sweep.degraded_items == len(sweep.work_items)
    assert all(item.draft_mode == "template_fallback" for item in sweep.work_items)
    assert {ACME_LOGISTICS, GLOBEX_TELEMETRY_GAP, INITECH_CSPLAN_GAP} <= {
        item.account_id for item in sweep.work_items
    }


def test_quality_breaker_routes_customer_drafts_to_internal_review(sweep_conn, tmp_path):
    orch, _authority = setup_roster(sweep_conn)
    gate = ActionGate(
        sweep_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )
    config = _quality_breaker_config(tmp_path, hard_ok=False)

    sweep = run_time_to_value_sweep(
        build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=orch,
        as_of=AS_OF,
        quality_breaker=config,
    )

    assert sweep.quality_breaker is not None
    assert sweep.quality_breaker["state"] == "open"
    blocked = [item for item in sweep.work_items if item.customer_contact_allowed]
    assert blocked
    assert sweep.degraded_items == len(blocked)
    assert all(item.disposition == "internal_review" for item in blocked)
    assert all(item.recommended_action == "recommend_next_best_action" for item in blocked)
    assert all(item.proposal is None for item in blocked)
    assert all(item.customer_draft is None for item in blocked)
    assert all(item.draft_mode == "template_fallback" for item in blocked)


def test_quality_breaker_requires_operator_event_to_clear(sweep_conn, tmp_path):
    orch, _authority = setup_roster(sweep_conn)
    gate = ActionGate(
        sweep_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )
    config = _quality_breaker_config(tmp_path, hard_ok=False)
    record_quality_breaker_reset(
        config,
        operator_id=orch,
        rationale="reviewed red artifact for demo",
        recorded_at=AS_OF,
    )

    sweep = run_time_to_value_sweep(
        build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=orch,
        as_of=AS_OF,
        quality_breaker=config,
    )

    assert sweep.quality_breaker is not None
    assert sweep.quality_breaker["state"] == "closed"
    assert sweep.quality_breaker["cleared_by_event"]
    assert sweep.degraded_items == 0
    proposed = [
        item for item in sweep.work_items
        if item.disposition == "propose_customer_action"
    ]
    assert proposed
    assert all(item.proposal is not None for item in proposed)


def _quality_breaker_config(tmp_path, *, hard_ok: bool) -> QualityBreakerConfig:
    artifact = tmp_path / "quality_artifact.json"
    artifact.write_text(
        (
            '{"artifact":"quality-test","hard_ok":'
            f'{"true" if hard_ok else "false"}'
            ',"hard_failures":[]}\n'
        ),
        encoding="utf-8",
    )
    return QualityBreakerConfig(
        artifact_path=artifact,
        operator_events_path=tmp_path / "operator_events.jsonl",
    )


def _sweep_signature(sweep):
    return tuple(
        (
            item.account_id,
            item.disposition,
            item.recommended_action,
            item.customer_contact_allowed,
            item.priority.score if item.priority else None,
            tuple(
                (factor.name, factor.contribution)
                for factor in (item.priority.factors if item.priority else ())
            ),
            item.proposal.status if item.proposal else None,
        )
        for item in sweep.work_items
    )
