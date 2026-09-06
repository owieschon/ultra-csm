from __future__ import annotations

from dataclasses import replace

import pytest

from eval.internal_bridge_battery import run_battery
from eval.internal_bridge_validation import (
    FixturePacketProseScorer,
    build_validation_report,
    packet_quality_payload,
)
from eval.judge_csm import QUALITY_DIMENSIONS
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


def test_internal_bridge_validation_report_fixture_shape():
    report = build_validation_report(prose_scorer=FixturePacketProseScorer())

    assert report["routing_core_hard_ok"] is True
    assert report["confusion_matrix"]["confidently_wrong_cells"] == []
    assert report["abstain_axis"] == {
        "oracle_abstain_agent_abstain": 4,
        "oracle_route_agent_abstain": 0,
        "oracle_abstain_agent_route": 0,
        "oracle_route_agent_route": 14,
    }
    assert len(report["cases"]) == 18
    first_scores = report["cases"][0]["packet_prose"]["scores"]
    assert tuple(first_scores) == QUALITY_DIMENSIONS


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


def test_packet_quality_payload_matches_judge_contract_fields():
    cases = tuple(build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT).crm.list_cases(ACME_LOGISTICS))
    decision = route_internal_bridge(cases, as_of="2026-06-27")
    request = InternalBridgePacketRequest(
        tenant_id=DEFAULT_TENANT,
        account_id=ACME_LOGISTICS,
        account_name="Acme Logistics",
        as_of="2026-06-27",
        decision=decision,
    )
    packet = build_internal_bridge_packet(request)
    quality_request, quality_output = packet_quality_payload(request, packet)

    assert quality_request["disposition"] == "internal_review"
    assert quality_request["customer_contact_allowed"] is False
    assert quality_request["evidence"][0]["source_id"] == packet.cited_evidence_ids[0]
    assert quality_output["customer_draft"] is None
    assert quality_output["reason"] == packet.body
    assert quality_output["cited_evidence_ids"] == list(packet.cited_evidence_ids)


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


@pytest.fixture
def handoff_conn(runtime_conn):
    runtime_conn.execute("BEGIN")
    try:
        yield runtime_conn
    finally:
        runtime_conn.rollback()


def _handoff_sweep(conn, *, variant="engineering", consent=True, classifier=None):
    from ultra_csm.data_plane import CustomerDataPlane
    from ultra_csm.data_plane.contracts import CRMCase
    from ultra_csm.data_plane.fixtures import (
        NOVA_FIELD, default_fixture_data, FixtureCRMDataConnector,
        FixtureCSPlatformConnector, FixtureProductTelemetryConnector, FixtureCommsConnector,
    )

    data = default_fixture_data()
    subjects = {
        "engineering": "Activation blocked: integration cannot proceed",
        "operator": "Activation blocked: credentials rejected",
        "noise": "Invoice contact update",
        "unknown": "Account question received",
    }
    case = CRMCase(
        case_id="handoff-case", account_id=NOVA_FIELD, status="Open", priority="Low",
        origin="Web", subject=subjects.get(variant, subjects["engineering"]),
        created_at="2026-06-20", closed_at=None,
    )
    if variant == "closed":
        case = replace(case, status="Closed", closed_at="2026-06-25")
    elif variant == "future":
        case = replace(case, created_at="2026-06-29")
    elif variant == "foreign":
        case = replace(case, account_id=ACME_LOGISTICS)
    data = replace(
        data, accounts=tuple(a for a in data.accounts if a.account_id == NOVA_FIELD),
        companies=tuple(replace(c, arr_cents=1_000_000) for c in data.companies
                        if c.company_id == NOVA_FIELD),
        contacts=tuple(replace(c, consent_to_contact=consent) for c in data.contacts
                       if c.account_id == NOVA_FIELD),
        health_scores=tuple(replace(h, score=95, band="green") for h in data.health_scores
                            if h.account_id == NOVA_FIELD),
        adoption_summaries=tuple(a for a in data.adoption_summaries if a.account_id == NOVA_FIELD),
        cases=(case,), opportunities=(), ctas=(), success_plans=(),
        entitlements=(), usage_signals=(), milestones=(), tenant_accounts=None,
    )
    plane = CustomerDataPlane(
        crm=FixtureCRMDataConnector(data=data), cs=FixtureCSPlatformConnector(data=data),
        telemetry=FixtureProductTelemetryConnector(data=data), comms=FixtureCommsConnector(data=data),
    )
    orch, _ = setup_roster(conn)
    gate = ActionGate(conn, tenant_id=T1, actor_principal_id=orch,
                      verdict_source=FixtureVerdictSource(), now=CLOCK)
    kwargs = {} if classifier is None else {"case_note_classifier": classifier}
    sweep = run_time_to_value_sweep(plane, DEFAULT_TENANT, gate, sweep_principal_id=orch,
                                   as_of="2026-06-27", **kwargs)
    return next((i for i in sweep.work_items if i.account_id == NOVA_FIELD), None)


@pytest.mark.parametrize("variant,target,artifact", [
    ("engineering", "engineering", "handoff_outline"),
    ("operator", "operator", "internal_note"),
])
@pytest.mark.parametrize("consent", [True, False])
def test_open_blocker_prepares_internal_work_without_customer_action(
    handoff_conn, variant, target, artifact, consent,
):
    item = _handoff_sweep(handoff_conn, variant=variant, consent=consent)
    assert item is not None
    assert item.disposition == "internal_review"
    assert item.recommended_action == "recommend_next_best_action"
    assert item.customer_contact_allowed is False
    assert item.customer_draft is None and item.proposal is None
    assert item.recipient_name is None and item.recipient_role is None
    assert item.draft_mode == "fixture"
    assert item.draft_fallback_reason is None
    assert any(ref.source_id == "handoff-case" for ref in item.evidence)
    assert item.work_packet.recommended_action.target_actor == target
    assert item.work_packet.prepared_artifact.artifact_type == artifact
    assert item.work_packet.prepared_artifact.body


@pytest.mark.parametrize("variant", ["closed", "future", "noise", "unknown", "foreign"])
def test_ineligible_case_does_not_create_blocker_handoff(handoff_conn, variant):
    assert _handoff_sweep(handoff_conn, variant=variant) is None


@pytest.mark.parametrize("mutation", ["classification", "account_id", "case_id", "cited_case_id"])
def test_blocker_handoff_requires_bound_classification(mutation):
    from ultra_csm.agent1.sweep import _has_confirmed_open_blocker
    from ultra_csm.agent1.slot_a import (
        FixtureCaseNoteClassifier, CaseNoteClassificationRequest, SlotACaseRef,
    )
    from ultra_csm.data_plane.contracts import CRMCase

    case = CRMCase("case", "account", "Open", "Low", "Web",
                   "Activation blocked: integration cannot proceed", "2026-06-20")
    output = FixtureCaseNoteClassifier().classify(CaseNoteClassificationRequest(
        tenant_id=DEFAULT_TENANT, account_id="account", case_id="case",
        case_note_text=case.subject, account_case_refs=(SlotACaseRef("case", "account"),),
    ))
    assert _has_confirmed_open_blocker((output,), (case,), account_id="account", as_of="2026-06-27")
    bad = replace(output, **{mutation: "unknown" if mutation == "classification" else "foreign"})
    assert not _has_confirmed_open_blocker((bad,), (case,), account_id="account", as_of="2026-06-27")
    assert not _has_confirmed_open_blocker(
        (output,), (replace(case, account_id="foreign"),), account_id="account", as_of="2026-06-27",
    )
