"""Agent 1 Risk and Expansion lenses over the shared value model."""

from __future__ import annotations

import pytest

from eval.lens_expansion_scorecard import build_scorecard as build_expansion_scorecard
from eval.lens_risk_scorecard import build_scorecard as build_risk_scorecard
from tests._govhelpers import CLOCK, T1, setup_roster
from ultra_csm.agent1.lens_expansion import run_expansion_lens
from ultra_csm.agent1.lens_risk import run_risk_lens
from ultra_csm.data_plane import ACME_LOGISTICS, DEFAULT_TENANT, build_sweep_fixture_data_plane
from ultra_csm.governance import ActionGate, FixtureVerdictSource

AS_OF = "2026-06-27"


@pytest.fixture
def lens_conn(runtime_conn):
    runtime_conn.execute("BEGIN")
    try:
        yield runtime_conn
    finally:
        runtime_conn.rollback()


def test_risk_lens_defaults_to_internal_only_gate_binding(lens_conn):
    orch, _authority = setup_roster(lens_conn)
    gate = ActionGate(
        lens_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )

    result = run_risk_lens(
        build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=orch,
        as_of=AS_OF,
    )

    assert result.work_items
    assert all(item.recommended_action == "recommend_next_best_action" for item in result.work_items)
    assert all(item.proposal is not None for item in result.work_items)
    assert all(item.proposal.autonomy_tier == 1 for item in result.work_items if item.proposal)
    assert all(item.customer_draft is None for item in result.work_items)


def test_expansion_lens_defaults_to_strictest_customer_facing_gate_binding(lens_conn):
    orch, _authority = setup_roster(lens_conn)
    gate = ActionGate(
        lens_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )

    result = run_expansion_lens(
        build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=orch,
        as_of=AS_OF,
    )

    assert result.work_items
    assert all(item.recommended_action == "initiate_customer_call" for item in result.work_items)
    assert all(item.proposal is not None for item in result.work_items)
    assert all(item.proposal.autonomy_tier == 3 for item in result.work_items if item.proposal)
    assert all(item.proposal.status == "pending" for item in result.work_items if item.proposal)


def test_same_fixture_account_can_enter_risk_and_expansion_queues_without_conflict(lens_conn):
    orch, _authority = setup_roster(lens_conn)
    data_plane = build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT)
    risk = run_risk_lens(
        data_plane,
        DEFAULT_TENANT,
        ActionGate(
            lens_conn,
            tenant_id=T1,
            actor_principal_id=orch,
            verdict_source=FixtureVerdictSource(),
            now=CLOCK,
        ),
        sweep_principal_id=orch,
        as_of=AS_OF,
    )
    expansion = run_expansion_lens(
        data_plane,
        DEFAULT_TENANT,
        ActionGate(
            lens_conn,
            tenant_id=T1,
            actor_principal_id=orch,
            verdict_source=FixtureVerdictSource(),
            now=CLOCK,
        ),
        sweep_principal_id=orch,
        as_of=AS_OF,
    )

    risk_item = next(item for item in risk.work_items if item.account_id == ACME_LOGISTICS)
    expansion_item = next(item for item in expansion.work_items if item.account_id == ACME_LOGISTICS)
    assert risk_item.proposal is not None
    assert expansion_item.proposal is not None
    assert risk_item.proposal.proposal_id != expansion_item.proposal.proposal_id
    assert risk_item.recommended_action == "recommend_next_best_action"
    assert expansion_item.recommended_action == "initiate_customer_call"


def test_lens_scorecards_write_green_artifacts_with_unsafe_foil_failures(tmp_path):
    risk = build_risk_scorecard(output_path=tmp_path / "risk.json")
    expansion = build_expansion_scorecard(output_path=tmp_path / "expansion.json")

    assert risk["hard_ok"] is True
    assert expansion["hard_ok"] is True
    assert risk["unsafe_placeholder"]["passed"] is True
    assert expansion["unsafe_placeholder"]["passed"] is True
    assert len(risk["unsafe_placeholder"]["failed_hard_gates"]) >= 3
    assert len(expansion["unsafe_placeholder"]["failed_hard_gates"]) >= 3
    assert "Slot-B quality unvalidated" in risk["claim_boundary"]
    assert "Slot-B quality unvalidated" in expansion["claim_boundary"]
