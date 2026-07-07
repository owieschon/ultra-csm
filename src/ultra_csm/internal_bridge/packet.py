"""Internal bridge packet generation for MP-B."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ultra_csm.agent1.slot_b import SLOT_B_PROMPT_VERSION
from ultra_csm.internal_bridge.routing import InternalBridgeDecision

INTERNAL_BRIDGE_PACKET_PROMPT_VERSION = f"{SLOT_B_PROMPT_VERSION}:internal-bridge-packet-v1"
FIXTURE_INTERNAL_BRIDGE_PACKET_MODEL_ID = "fixture-internal-bridge-packet-v1"

INTERNAL_BRIDGE_PACKET_SCHEMA = {
    "target": "engineering | product | null",
    "motion": "escalation | content_route | null",
    "abstained": "bool",
    "reason": "string",
    "body": "string",
    "cited_evidence_ids": ["source_id"],
    "model_id": "string",
    "prompt_version": "string",
}


@dataclass(frozen=True)
class InternalBridgePacketRequest:
    tenant_id: str
    account_id: str
    account_name: str
    as_of: str
    decision: InternalBridgeDecision


@dataclass(frozen=True)
class InternalBridgePacket:
    target: str | None
    motion: str | None
    abstained: bool
    reason: str
    body: str
    cited_evidence_ids: tuple[str, ...]
    model_id: str
    prompt_version: str


class InternalBridgePacketError(ValueError):
    """Raised when an internal bridge packet violates the schema."""


class InternalBridgePacketWriter(Protocol):
    model_id: str
    prompt_version: str

    def write(self, request: InternalBridgePacketRequest) -> InternalBridgePacket: ...


class FixtureInternalBridgePacketWriter:
    """Deterministic offline packet writer following Slot B's writer shape."""

    model_id = FIXTURE_INTERNAL_BRIDGE_PACKET_MODEL_ID
    prompt_version = INTERNAL_BRIDGE_PACKET_PROMPT_VERSION

    def write(self, request: InternalBridgePacketRequest) -> InternalBridgePacket:
        decision = request.decision
        evidence_ids = tuple(ref.source_id for ref in decision.evidence)
        if decision.abstained:
            body = (
                f"Internal bridge abstention for {request.account_name}: "
                f"{decision.reason}"
            )
        else:
            citations = " ".join(f"[evidence:{evidence_id}]" for evidence_id in evidence_ids)
            body = (
                f"Internal bridge packet for {request.account_name}. "
                f"Target: {decision.target}. Motion: {decision.motion}. "
                f"Signal: {decision.signal}. Reason: {decision.reason} "
                f"Evidence: {citations}"
            )
        packet = InternalBridgePacket(
            target=decision.target,
            motion=decision.motion,
            abstained=decision.abstained,
            reason=decision.reason,
            body=body,
            cited_evidence_ids=evidence_ids,
            model_id=self.model_id,
            prompt_version=self.prompt_version,
        )
        validate_internal_bridge_packet(request, packet)
        return packet


def build_internal_bridge_packet(
    request: InternalBridgePacketRequest,
    writer: InternalBridgePacketWriter | None = None,
) -> InternalBridgePacket:
    packet_writer = writer or FixtureInternalBridgePacketWriter()
    packet = packet_writer.write(request)
    validate_internal_bridge_packet(request, packet)
    return packet


def validate_internal_bridge_packet(
    request: InternalBridgePacketRequest,
    packet: InternalBridgePacket,
) -> None:
    decision = request.decision
    if packet.prompt_version != INTERNAL_BRIDGE_PACKET_PROMPT_VERSION:
        raise InternalBridgePacketError("unexpected prompt_version")
    if packet.target != decision.target:
        raise InternalBridgePacketError("packet target does not match decision")
    if packet.motion != decision.motion:
        raise InternalBridgePacketError("packet motion does not match decision")
    if packet.abstained != decision.abstained:
        raise InternalBridgePacketError("packet abstained field does not match decision")
    if not packet.reason.strip():
        raise InternalBridgePacketError("packet reason is required")
    if not packet.body.strip():
        raise InternalBridgePacketError("packet body is required")

    expected_ids = tuple(ref.source_id for ref in decision.evidence)
    if packet.cited_evidence_ids != expected_ids:
        raise InternalBridgePacketError("packet cited_evidence_ids must exactly match decision evidence")
    for evidence_id in expected_ids:
        if evidence_id not in packet.body:
            raise InternalBridgePacketError(f"packet body does not cite {evidence_id}")

    if decision.abstained and packet.cited_evidence_ids:
        raise InternalBridgePacketError("abstain packet must not cite evidence")
