"""Stateful sim-loop tests."""

from __future__ import annotations

import pytest

from ultra_csm.agent1 import run_time_to_value_sweep
from ultra_csm.committers import (
    SimCrmActivityCommitter,
    SimOutboundCommitter,
    auto_approve_internal,
    load_action_proposal,
)
from ultra_csm.data_plane import ACME_LOGISTICS, DEFAULT_TENANT, SimTenantStore
from ultra_csm.governance import (
    ActionGate,
    FixtureVerdictSource,
    GateError,
    Verdict,
    proposal_fields_for,
)
from ultra_csm.value_model import build_customer_value_model

from tests._govhelpers import CLOCK, T1, setup_roster

AS_OF = "2026-06-27"


def test_sim_commit_reobserves_outcome_and_is_idempotent(runtime_conn, tmp_path):
    runtime_conn.execute("BEGIN")
    try:
        orch, authority = setup_roster(runtime_conn)
        gate = ActionGate(
            runtime_conn,
            tenant_id=T1,
            actor_principal_id=orch,
            verdict_source=FixtureVerdictSource(),
            now=CLOCK,
        )
        store = SimTenantStore.seed(tmp_path, tenant_id=DEFAULT_TENANT, reset=True)

        first = run_time_to_value_sweep(
            store.data_plane(),
            DEFAULT_TENANT,
            gate,
            sweep_principal_id=orch,
            as_of=AS_OF,
        )
        item = next(item for item in first.work_items if item.account_id == ACME_LOGISTICS)
        proposal = load_action_proposal(
            runtime_conn,
            tenant_id=T1,
            actor_principal_id=orch,
            proposal_id=item.proposal.proposal_id,
            now=CLOCK,
        )
        outcome = gate.record_verdict(
            proposal,
            Verdict("approve", human_principal_id=authority, rationale="test approval"),
            cause_ref="test:approve",
        )

        outbound = SimOutboundCommitter(gate, state_dir=tmp_path)
        first_receipt = outbound.commit(proposal, outcome)
        second_receipt = outbound.commit(proposal, outcome)
        crm_receipt = SimCrmActivityCommitter(gate, store).commit(proposal, outcome)
        advance = store.advance_after_commits(as_of="2026-06-28")

        assert first_receipt.committed is True
        assert second_receipt.committed is False
        assert crm_receipt.committed is True
        assert advance["completed_accounts"] == (ACME_LOGISTICS,)

        after_milestones = store.data_plane().telemetry.list_ttv_milestones(ACME_LOGISTICS)
        assert after_milestones
        assert all(milestone.achieved_at is not None for milestone in after_milestones)
        assert _outcome_state(store, ACME_LOGISTICS) == "known"

        second = run_time_to_value_sweep(
            store.data_plane(),
            DEFAULT_TENANT,
            gate,
            sweep_principal_id=orch,
            as_of="2026-06-28",
        )
        acme = next(item for item in second.work_items if item.account_id == ACME_LOGISTICS)
        assert acme.priority is not None
        assert "milestones_overdue" not in {factor.name for factor in acme.priority.factors}
    finally:
        runtime_conn.rollback()


def test_sim_committer_requires_approved_bound_payload(runtime_conn, tmp_path):
    runtime_conn.execute("BEGIN")
    try:
        orch, _authority = setup_roster(runtime_conn)
        gate = ActionGate(
            runtime_conn,
            tenant_id=T1,
            actor_principal_id=orch,
            verdict_source=FixtureVerdictSource(),
            now=CLOCK,
        )
        store = SimTenantStore.seed(tmp_path, tenant_id=DEFAULT_TENANT, reset=True)
        sweep = run_time_to_value_sweep(
            store.data_plane(),
            DEFAULT_TENANT,
            gate,
            sweep_principal_id=orch,
            as_of=AS_OF,
        )
        item = next(item for item in sweep.work_items if item.proposal is not None)
        proposal = load_action_proposal(
            runtime_conn,
            tenant_id=T1,
            actor_principal_id=orch,
            proposal_id=item.proposal.proposal_id,
            now=CLOCK,
        )

        with pytest.raises(GateError):
            SimOutboundCommitter(gate, state_dir=tmp_path).commit(
                proposal,
                type("Outcome", (), {
                    "authorized": False,
                    "status": "pending",
                    "payload_sha256": proposal.payload_sha256,
                })(),
            )
    finally:
        runtime_conn.rollback()


def test_tier_one_internal_action_auto_executes_through_gate(runtime_conn, tmp_path):
    runtime_conn.execute("BEGIN")
    try:
        orch, _authority = setup_roster(runtime_conn)
        gate = ActionGate(
            runtime_conn,
            tenant_id=T1,
            actor_principal_id=orch,
            verdict_source=FixtureVerdictSource(),
            now=CLOCK,
        )
        store = SimTenantStore.seed(tmp_path, tenant_id=DEFAULT_TENANT, reset=True)
        proposal = gate.propose(
            intent="demo_internal_recommendation",
            payload={
                "account_id": ACME_LOGISTICS,
                "subject": "Review activation blockers",
                "body": "Internal next-best action for the CSM.",
                "as_of": AS_OF,
            },
            grounding_ref=f"demo:{ACME_LOGISTICS}:internal",
            cause_ref="test:auto-internal",
            **proposal_fields_for("recommend_next_best_action"),
        )

        outcome = auto_approve_internal(gate, proposal, system_principal_id=orch)
        receipt = SimCrmActivityCommitter(gate, store).commit(proposal, outcome)

        assert outcome.authorized is True
        assert receipt.committed is True
        activity = store.state().activities[0]
        assert activity.account_id == ACME_LOGISTICS
        assert activity.direction == "internal"
    finally:
        runtime_conn.rollback()


def test_tier_two_and_three_actions_never_auto_execute(runtime_conn):
    runtime_conn.execute("BEGIN")
    try:
        orch, _authority = setup_roster(runtime_conn)
        gate = ActionGate(
            runtime_conn,
            tenant_id=T1,
            actor_principal_id=orch,
            verdict_source=FixtureVerdictSource(),
            now=CLOCK,
        )
        for action in ("draft_customer_outreach", "initiate_customer_call"):
            proposal = gate.propose(
                intent=f"demo_forbidden_auto_{action}",
                payload={
                    "account_id": ACME_LOGISTICS,
                    "subject": "Customer-affecting action",
                    "body": "Requires human approval.",
                },
                grounding_ref=f"demo:{ACME_LOGISTICS}:{action}",
                cause_ref=f"test:forbidden-auto:{action}",
                **proposal_fields_for(action),
            )
            with pytest.raises(GateError):
                auto_approve_internal(gate, proposal, system_principal_id=orch)
    finally:
        runtime_conn.rollback()


def _outcome_state(store: SimTenantStore, account_id: str) -> str:
    data_plane = store.data_plane()
    account = data_plane.crm.get_account(account_id)
    company = data_plane.cs.get_company(account_id)
    health = data_plane.cs.get_health_score(account_id)
    adoption = data_plane.cs.get_adoption_summary(account_id)
    assert account is not None and company is not None and health is not None
    model = build_customer_value_model(
        account=account,
        company=company,
        health=health,
        adoption=adoption,
        entitlements=tuple(data_plane.telemetry.list_entitlements(account_id)),
        usage_signals=tuple(data_plane.telemetry.list_usage_signals(account_id)),
        success_plans=tuple(data_plane.cs.list_success_plans(account_id)),
    )
    return model.outcome.realized_state
