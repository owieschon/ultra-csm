"""Deterministic MP-D2 work-packet validation battery.

This module validates packet structure and trust boundaries. It deliberately
does not decide whether a contested diagnosis is "correct"; inferential fields
pass only when they are honestly labeled outside the validated domain.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields, is_dataclass
from typing import Iterable

from ultra_csm.governance.csm_actions import UnknownCSMActionError, csm_action_spec
from ultra_csm.work_packets import (
    CSMWorkPacket,
    EvidenceChainStep,
    allowed_ctas_for,
)


ALLOWED_FIELD_VALIDATORS = frozenset({
    "deterministic_oracle",
    "judge_graded_in_domain",
    "judge_graded_in_domain_or_out_of_validated_domain",
    "out_of_validated_domain",
})


@dataclass(frozen=True)
class WorkPacketFinding:
    packet_id: str
    field: str
    severity: str
    reason: str


@dataclass(frozen=True)
class WorkPacketEvalReport:
    artifact: str
    packet_count: int
    passed: bool
    findings: tuple[WorkPacketFinding, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def validate_packets(packets: Iterable[CSMWorkPacket]) -> WorkPacketEvalReport:
    findings: list[WorkPacketFinding] = []
    packet_tuple = tuple(packets)
    for packet in packet_tuple:
        findings.extend(validate_packet(packet))
    return WorkPacketEvalReport(
        artifact="work_packet_eval",
        packet_count=len(packet_tuple),
        passed=not findings,
        findings=tuple(findings),
    )


def validate_packet(packet: CSMWorkPacket) -> tuple[WorkPacketFinding, ...]:
    findings: list[WorkPacketFinding] = []
    packet_id = _packet_id(packet)
    findings.extend(_field_validation_findings(packet, packet_id=packet_id))
    findings.extend(_evidence_chain_findings(packet.evidence_chain, packet_id=packet_id))
    findings.extend(_governance_findings(packet, packet_id=packet_id))
    findings.extend(_honest_inference_findings(packet, packet_id=packet_id))
    findings.extend(_feedback_hook_findings(packet, packet_id=packet_id))
    return tuple(findings)


def _field_validation_findings(
    packet: CSMWorkPacket, *, packet_id: str
) -> tuple[WorkPacketFinding, ...]:
    packet_fields = {field.name for field in fields(CSMWorkPacket)}
    declared = set(packet.field_validation)
    findings: list[WorkPacketFinding] = []
    for missing in sorted(packet_fields - declared):
        findings.append(_finding(packet_id, missing, "missing validation boundary"))
    for extra in sorted(declared - packet_fields):
        findings.append(_finding(packet_id, extra, "validation boundary for unknown field"))
    for name, validator in sorted(packet.field_validation.items()):
        if validator not in ALLOWED_FIELD_VALIDATORS:
            findings.append(_finding(
                packet_id,
                name,
                f"unknown validation boundary {validator!r}",
            ))
    return tuple(findings)


def _evidence_chain_findings(
    evidence_chain: tuple[EvidenceChainStep, ...], *, packet_id: str
) -> tuple[WorkPacketFinding, ...]:
    findings: list[WorkPacketFinding] = []
    for step in evidence_chain:
        field = f"evidence_chain.{step.step_id}"
        if step.provenance_tier == "raw_fact":
            if not (step.source and step.source_id and step.field and step.observed_at):
                findings.append(_finding(packet_id, field, "raw_fact lacks source receipt"))
            if step.validation_status != "oracle_graded":
                findings.append(_finding(packet_id, field, "raw_fact must be oracle_graded"))
            if _looks_inferential(step.claim):
                findings.append(_finding(
                    packet_id,
                    field,
                    "inferential claim is labeled raw_fact",
                ))
        elif step.provenance_tier == "interpreted_signal":
            if step.validation_status not in {
                "oracle_graded",
                "out_of_validated_domain",
            }:
                findings.append(_finding(
                    packet_id,
                    field,
                    "interpreted signal has invalid validation status",
                ))
        elif step.provenance_tier == "hypothesis":
            if step.validation_status != "out_of_validated_domain":
                findings.append(_finding(
                    packet_id,
                    field,
                    "hypothesis evidence step cannot be shipped as validated",
                ))
        else:
            findings.append(_finding(
                packet_id,
                field,
                f"unknown provenance tier {step.provenance_tier!r}",
            ))
    return tuple(findings)


def _governance_findings(
    packet: CSMWorkPacket, *, packet_id: str
) -> tuple[WorkPacketFinding, ...]:
    boundary = packet.governance_boundary
    findings: list[WorkPacketFinding] = []
    if boundary.action_type is None:
        if boundary.release_condition is not None or boundary.required_permission is not None:
            findings.append(_finding(
                packet_id,
                "governance_boundary",
                "ungoverned packet carries gate fields",
            ))
        return tuple(findings)

    try:
        spec = csm_action_spec(boundary.action_type)
    except UnknownCSMActionError:
        return (_finding(
            packet_id,
            "governance_boundary.action_type",
            "unknown action type",
        ),)

    expected_ctas = allowed_ctas_for(
        boundary.action_type,
        proposal_status=boundary.proposal_status,
        artifact_present=packet.prepared_artifact.artifact_type
        in {"customer_draft", "content_route"},
    )
    actual_by_id = {cta.cta_id: cta for cta in packet.allowed_ctas}
    for expected in expected_ctas:
        actual = actual_by_id.get(expected.cta_id)
        if actual is None:
            findings.append(_finding(
                packet_id,
                f"allowed_ctas.{expected.cta_id}",
                "missing backend-authored CTA",
            ))
            continue
        if actual.enabled != expected.enabled:
            findings.append(_finding(
                packet_id,
                f"allowed_ctas.{expected.cta_id}",
                "CTA enabled does not match governance release condition",
            ))
        if actual.governance_requirement != expected.governance_requirement:
            findings.append(_finding(
                packet_id,
                f"allowed_ctas.{expected.cta_id}",
                "CTA governance requirement drifted from action spec",
            ))
        if actual.source_organ != "governance.csm_actions":
            findings.append(_finding(
                packet_id,
                f"allowed_ctas.{expected.cta_id}",
                "CTA source organ is not governance.csm_actions",
            ))

    if boundary.release_condition != spec.release_condition:
        findings.append(_finding(
            packet_id,
            "governance_boundary.release_condition",
            "release condition drifted from csm_action_spec",
        ))
    if boundary.required_permission != spec.required_permission:
        findings.append(_finding(
            packet_id,
            "governance_boundary.required_permission",
            "required permission drifted from csm_action_spec",
        ))
    if boundary.autonomy_tier != spec.autonomy_tier:
        findings.append(_finding(
            packet_id,
            "governance_boundary.autonomy_tier",
            "autonomy tier drifted from csm_action_spec",
        ))
    if boundary.can_execute_from_ui:
        findings.append(_finding(
            packet_id,
            "governance_boundary.can_execute_from_ui",
            "packet cannot mint execution authority",
        ))
    return tuple(findings)


def _honest_inference_findings(
    packet: CSMWorkPacket, *, packet_id: str
) -> tuple[WorkPacketFinding, ...]:
    findings: list[WorkPacketFinding] = []
    hypothesis = packet.diagnostic_hypothesis
    if hypothesis.label != "unverified_hypothesis":
        findings.append(_finding(
            packet_id,
            "diagnostic_hypothesis.label",
            "diagnostic hypothesis is not honestly labeled",
        ))
    if hypothesis.validation_status != "out_of_validated_domain":
        findings.append(_finding(
            packet_id,
            "diagnostic_hypothesis.validation_status",
            "diagnostic hypothesis cannot be shipped as validated",
        ))
    if hypothesis.confidence > 0.72:
        findings.append(_finding(
            packet_id,
            "diagnostic_hypothesis.confidence",
            "unverified hypothesis confidence exceeds cap",
        ))
    return tuple(findings)


def _feedback_hook_findings(
    packet: CSMWorkPacket, *, packet_id: str
) -> tuple[WorkPacketFinding, ...]:
    findings = []
    for hook in packet.feedback_hooks:
        if hook.target != "rejection_ledger":
            findings.append(_finding(
                packet_id,
                f"feedback_hooks.{hook.hook_id}",
                "feedback hook bypasses RejectionLedger",
            ))
    return tuple(findings)


def _looks_inferential(claim: str) -> bool:
    lowered = claim.lower()
    return any(
        token in lowered
        for token in (
            "hypothesis",
            "likely",
            "appears",
            "suggests",
            "probably",
            "inferred",
        )
    )


def _packet_id(packet: CSMWorkPacket) -> str:
    account = packet.account_id or packet.coverage_trace.account_resolution
    return f"{packet.tenant_id}:{account}:{packet.as_of}:{packet.job_type}"


def _finding(packet_id: str, field: str, reason: str) -> WorkPacketFinding:
    return WorkPacketFinding(
        packet_id=packet_id,
        field=field,
        severity="error",
        reason=reason,
    )


def collect_api_packets() -> tuple[CSMWorkPacket, ...]:
    """Run the existing API sweep and collect serialized packets.

    This is the connected-system battery path: API -> sweep -> packet -> JSON.
    """

    os.environ.setdefault("ULTRA_CSM_API_TOKENS", "lane-a-token:Lane A Manager")
    os.environ.pop("ULTRA_CSM_DEMO_NOAUTH", None)
    from fastapi.testclient import TestClient
    from ultra_csm.api import app

    with TestClient(app) as client:
        response = client.post(
            "/sweep",
            headers={"Authorization": "Bearer lane-a-token"},
        )
        response.raise_for_status()
        body = response.json()
    packets = [
        item["work_packet"]
        for group in (body.get("work_items", ()), body.get("escalations", ()))
        for item in group
        if item.get("work_packet")
    ]
    return tuple(_packet_from_mapping(packet) for packet in packets)


def _packet_from_mapping(raw: dict) -> CSMWorkPacket:
    from ultra_csm.work_packets import (
        AllowedCTA,
        BucketTrace,
        CoverageTrace,
        DiagnosticHypothesis,
        GovernanceBoundary,
        PreparedArtifact,
        RecommendedAction,
        FeedbackHook,
    )

    return CSMWorkPacket(
        packet_version=raw["packet_version"],
        tenant_id=raw["tenant_id"],
        account_id=raw.get("account_id"),
        account_name=raw.get("account_name"),
        as_of=raw["as_of"],
        job_type=raw["job_type"],
        lane=raw["lane"],
        cadence=raw["cadence"],
        diagnostic_hypothesis=DiagnosticHypothesis(**raw["diagnostic_hypothesis"]),
        recommended_action=RecommendedAction(**raw["recommended_action"]),
        primary_next_step=raw["primary_next_step"],
        governance_boundary=GovernanceBoundary(**raw["governance_boundary"]),
        prepared_artifact=PreparedArtifact(**raw["prepared_artifact"]),
        evidence_chain=tuple(EvidenceChainStep(**step) for step in raw["evidence_chain"]),
        bucket_trace=tuple(BucketTrace(**row) for row in raw["bucket_trace"]),
        coverage_trace=CoverageTrace(**raw["coverage_trace"]),
        allowed_ctas=tuple(AllowedCTA(**cta) for cta in raw["allowed_ctas"]),
        feedback_hooks=tuple(FeedbackHook(**hook) for hook in raw["feedback_hooks"]),
        field_validation=dict(raw["field_validation"]),
    )


def _json_default(value):
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"not JSON serializable: {type(value)!r}")


def main() -> int:
    report = validate_packets(collect_api_packets())
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True, default=_json_default))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
