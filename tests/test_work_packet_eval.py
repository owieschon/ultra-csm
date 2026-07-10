"""Tests for the MP-D2 packet validation spine."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests._govhelpers import CLOCK, T1, setup_roster
from ultra_csm.agent1 import run_time_to_value_sweep
from ultra_csm.data_plane import DEFAULT_TENANT, build_sweep_fixture_data_plane
from ultra_csm.governance import ActionGate, FixtureVerdictSource
from ultra_csm.rejection_ledger import RejectionLedger, recurring_rejection_reasons
from ultra_csm.work_packets import EvidenceChainStep
from eval.work_packet_eval import validate_packet, validate_packets

AS_OF = "2026-06-27"


@pytest.fixture
def packet(runtime_conn):
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
            as_of=AS_OF,
        )
        yield next(item.work_packet for item in sweep.work_items if item.work_packet)
    finally:
        runtime_conn.rollback()


def test_work_packet_eval_passes_real_sweep_packet(packet):
    report = validate_packets((packet,))
    assert report.passed is True
    assert report.findings == ()


def test_work_packet_eval_fails_ungraded_field(packet):
    validation = dict(packet.field_validation)
    validation.pop("allowed_ctas")
    broken = replace(packet, field_validation=validation)

    findings = validate_packet(broken)

    assert any(
        finding.field == "allowed_ctas"
        and "missing validation boundary" in finding.reason
        for finding in findings
    )


def test_work_packet_eval_fails_laundered_inference_as_raw_fact(packet):
    assert packet.evidence_chain
    step = packet.evidence_chain[0]
    broken_step = replace(
        step,
        provenance_tier="raw_fact",
        claim="This likely suggests an unverified hypothesis.",
    )
    broken = replace(
        packet,
        evidence_chain=(broken_step, *packet.evidence_chain[1:]),
    )

    findings = validate_packet(broken)

    assert any("inferential claim is labeled raw_fact" in finding.reason for finding in findings)


def test_work_packet_eval_fails_validated_hypothesis_step(packet):
    raw = packet.evidence_chain[0]
    broken_step = EvidenceChainStep(
        step_id="evidence:hypothesis:bad",
        provenance_tier="hypothesis",
        source=raw.source,
        source_id=raw.source_id,
        field=raw.field,
        observed_at=raw.observed_at,
        claim="Hypothesis that looks validated.",
        validation_status="oracle_graded",
    )
    broken = replace(packet, evidence_chain=(broken_step,))

    findings = validate_packet(broken)

    assert any("hypothesis evidence step cannot be shipped as validated" in finding.reason for finding in findings)


def test_work_packet_eval_fails_cta_gate_drift(packet):
    target = next(
        cta for cta in packet.allowed_ctas
        if cta.cta_id == "request_gate_approval"
    )
    broken_cta = replace(target, enabled=not target.enabled)
    broken = replace(
        packet,
        allowed_ctas=tuple(
            broken_cta if cta.cta_id == target.cta_id else cta
            for cta in packet.allowed_ctas
        ),
    )

    findings = validate_packet(broken)

    assert any("CTA enabled does not match governance" in finding.reason for finding in findings)


def test_rejection_ledger_mines_recurring_reasons():
    ledger = RejectionLedger()
    for index in range(3):
        ledger.reject(
            tenant_id="t1",
            account_id=f"a{index}",
            factor_name="usage_drop",
            motion="personal_email",
            reason="customer already has an active remediation plan",
            rejected_on_day=index,
            proposal_id=f"p{index}",
        )
    ledger.reject(
        tenant_id="t1",
        account_id="a4",
        factor_name="usage_drop",
        motion="personal_email",
        reason="one-off timing issue",
        rejected_on_day=4,
        proposal_id="p4",
    )

    assert recurring_rejection_reasons(ledger.all_records()) == (
        ("customer already has an active remediation plan", 3),
    )
