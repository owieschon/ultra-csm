"""MP-D2 work-packet contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests._govhelpers import CLOCK, T1, setup_roster
from ultra_csm.agent1 import run_time_to_value_sweep
from ultra_csm.data_plane import DEFAULT_TENANT, build_sweep_fixture_data_plane
from ultra_csm.governance import ActionGate, FixtureVerdictSource
from ultra_csm.governance.csm_actions import csm_action_spec
from ultra_csm.work_packets import allowed_ctas_for

AS_OF = "2026-06-27"


@pytest.fixture
def sweep_conn(runtime_conn):
    runtime_conn.execute("BEGIN")
    try:
        yield runtime_conn
    finally:
        runtime_conn.rollback()


def _sweep(sweep_conn):
    orch, _authority = setup_roster(sweep_conn)
    gate = ActionGate(
        sweep_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )
    return run_time_to_value_sweep(
        build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=orch,
        as_of=AS_OF,
    )


def test_real_sweep_items_carry_work_packets(sweep_conn):
    sweep = _sweep(sweep_conn)

    assert sweep.work_items
    for item in sweep.work_items:
        packet = item.work_packet
        assert packet is not None
        assert packet.packet_version == "csm-work-packet-v1"
        assert packet.tenant_id == item.tenant_id
        assert packet.account_id == item.account_id
        assert packet.as_of == item.swept_at
        assert packet.field_validation["allowed_ctas"] == "deterministic_oracle"
        assert packet.diagnostic_hypothesis.label == "unverified_hypothesis"
        assert packet.diagnostic_hypothesis.confidence <= 0.72
        assert {
            step.provenance_tier for step in packet.evidence_chain
        } <= {"raw_fact"}


def test_allowed_ctas_derive_from_governance_release_condition(sweep_conn):
    sweep = _sweep(sweep_conn)
    governed_items = [
        item for item in sweep.work_items if item.recommended_action is not None
    ]
    assert governed_items

    for item in governed_items:
        packet = item.work_packet
        assert packet is not None
        spec = csm_action_spec(item.recommended_action)
        boundary = packet.governance_boundary
        assert boundary.release_condition == spec.release_condition
        assert boundary.required_permission == spec.required_permission
        assert boundary.autonomy_tier == spec.autonomy_tier
        assert boundary.can_execute_from_ui is False

        request_approval = next(
            cta for cta in packet.allowed_ctas
            if cta.cta_id == "request_gate_approval"
        )
        expected_enabled = (
            item.proposal is not None
            and item.proposal.status == "pending"
            and spec.release_condition != "auto_internal_only"
        )
        assert request_approval.enabled is expected_enabled
        assert request_approval.governance_requirement == spec.release_condition


def test_cta_helper_has_no_second_approval_truth():
    pending_customer = allowed_ctas_for(
        "draft_customer_outreach",
        proposal_status="pending",
        artifact_present=True,
    )
    pending_internal = allowed_ctas_for(
        "recommend_next_best_action",
        proposal_status=None,
        artifact_present=False,
    )

    approval = next(
        cta for cta in pending_customer if cta.cta_id == "request_gate_approval"
    )
    mark_internal = next(
        cta for cta in pending_internal if cta.cta_id == "mark_internal_reviewed"
    )
    assert approval.enabled is True
    assert approval.governance_requirement == "human_approve_with_consent"
    assert mark_internal.enabled is True
    assert mark_internal.governance_requirement == "auto_internal_only"


def test_work_packet_planner_has_no_generation_imports():
    source = Path("src/ultra_csm/work_packets.py").read_text()
    forbidden = (
        "openai",
        "anthropic",
        "ReasonDraftWriter",
        "FixtureReasonDraftWriter",
        "LIVE_SLOT_B",
        "generateText",
        "streamText",
    )
    for token in forbidden:
        assert token not in source
