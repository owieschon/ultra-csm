from __future__ import annotations

import pytest

from eval.internal_bridge_battery import run_battery
from tests._govhelpers import CLOCK, T1, setup_roster
from ultra_csm.agent1 import run_time_to_value_sweep
from ultra_csm.data_plane import ACME_LOGISTICS, DEFAULT_TENANT, build_sweep_fixture_data_plane
from ultra_csm.internal_bridge import (
    InternalBridgePacketRequest,
    build_internal_bridge_packet,
    route_internal_bridge,
)
from ultra_csm.internal_bridge.packet import (
    InternalBridgePacket,
    InternalBridgePacketError,
    validate_internal_bridge_packet,
)
from ultra_csm.governance import ActionGate, FixtureVerdictSource


def test_internal_bridge_battery_hard_ok():
    report = run_battery()
    assert report["hard_ok"], report["failed_cases"]
    assert len(report["cases"]) == 18


def test_internal_bridge_battery_is_deterministic():
    assert run_battery() == run_battery()


def test_packet_cites_exact_decision_evidence_for_routed_foil():
    cases = tuple(build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT).crm.list_cases(ACME_LOGISTICS))
    decision = route_internal_bridge(cases, as_of="2026-06-27")
    packet = build_internal_bridge_packet(
        InternalBridgePacketRequest(
            tenant_id=DEFAULT_TENANT,
            account_id=ACME_LOGISTICS,
            account_name="Acme Logistics",
            as_of="2026-06-27",
            decision=decision,
        )
    )

    assert packet.abstained is False
    assert packet.cited_evidence_ids == tuple(ref.source_id for ref in decision.evidence)
    for evidence_id in packet.cited_evidence_ids:
        assert evidence_id in packet.body


def test_packet_has_reasoned_abstention_not_empty_body():
    decision = route_internal_bridge((), as_of="2026-06-27")
    packet = build_internal_bridge_packet(
        InternalBridgePacketRequest(
            tenant_id=DEFAULT_TENANT,
            account_id=ACME_LOGISTICS,
            account_name="Acme Logistics",
            as_of="2026-06-27",
            decision=decision,
        )
    )

    assert packet.abstained is True
    assert packet.reason
    assert packet.body
    assert packet.cited_evidence_ids == ()


def test_packet_rejects_missing_decision_evidence():
    cases = tuple(build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT).crm.list_cases(ACME_LOGISTICS))
    decision = route_internal_bridge(cases, as_of="2026-06-27")
    bad = InternalBridgePacket(
        target=decision.target,
        motion=decision.motion,
        abstained=decision.abstained,
        reason=decision.reason,
        body="Internal bridge packet without the real citation.",
        cited_evidence_ids=(),
        model_id="bad",
        prompt_version="agent1-slot-b-reason-draft-v4:internal-bridge-packet-v1",
    )
    with pytest.raises(InternalBridgePacketError):
        validate_internal_bridge_packet(
            InternalBridgePacketRequest(
                tenant_id=DEFAULT_TENANT,
                account_id=ACME_LOGISTICS,
                account_name="Acme Logistics",
                as_of="2026-06-27",
                decision=decision,
            ),
            bad,
        )


def test_sweep_work_item_carries_additive_internal_bridge_decision(runtime_conn):
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

        sweep = run_time_to_value_sweep(
            build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
            DEFAULT_TENANT,
            gate,
            sweep_principal_id=orch,
            as_of="2026-06-27",
        )

        acme = next(item for item in sweep.work_items if item.account_id == ACME_LOGISTICS)
        assert acme.internal_bridge_decision is not None
        assert acme.internal_bridge_decision.abstained is False
        assert acme.internal_bridge_decision.target == "engineering"
        assert acme.internal_bridge_decision.motion == "escalation"
    finally:
        runtime_conn.rollback()
