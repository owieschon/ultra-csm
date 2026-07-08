"""Adaptable workflow spine with hard invariants.

This module is intentionally not a universal packet schema. Workflows keep
their domain-specific decision models, but each one emits a comparable
execution envelope that proves identity, evidence, decision trace, governance,
audit, and idempotency invariants.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from ultra_csm.workflow_playbooks import WorkflowDefinition


IdentityState = Literal["exactly_one", "ambiguous", "none", "ignored"]
OutputAudience = Literal["agent_internal", "csm_facing", "customer_facing", "external_write"]
OutputStatus = Literal["prepared", "proposed", "suppressed", "not_applicable"]


@dataclass(frozen=True)
class WorkflowEvidenceItem:
    source_type: str
    source_id: str
    field: str
    observed_at: str
    authority: str
    grain: str
    customer_safe: bool
    claim: str
    freshness: str = "unknown"
    conflicts: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkflowEvidenceBundle:
    reviewed_sources: tuple[str, ...]
    missing_required_sources: tuple[str, ...]
    customer_output_blockers: tuple[str, ...]
    items: tuple[WorkflowEvidenceItem, ...]

    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(item.source_id for item in self.items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reviewed_sources": list(self.reviewed_sources),
            "missing_required_sources": list(self.missing_required_sources),
            "customer_output_blockers": list(self.customer_output_blockers),
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(frozen=True)
class WorkflowDecisionTrace:
    decision_kind: str
    selected_hypothesis: str
    alternatives: tuple[str, ...]
    confidence: float | None
    confidence_model: tuple[str, ...]
    source_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    domain_payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkflowValidationResult:
    check_name: str
    passed: bool
    blocks_customer_output: bool
    detail: str
    source_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkflowOutputContract:
    artifact_type: str
    audience: OutputAudience
    action_type: str | None
    customer_affecting: bool
    gate_action: str | None
    status: OutputStatus
    source_ids: tuple[str, ...]
    suppression_reasons: tuple[str, ...]
    proposal_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkflowInvariantResult:
    invariant: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkflowExecutionEnvelope:
    workflow_id: str
    config_version: str
    trigger_ref: str
    idempotency_key: str
    identity_state: IdentityState
    evidence: WorkflowEvidenceBundle
    decisions: tuple[WorkflowDecisionTrace, ...]
    validations: tuple[WorkflowValidationResult, ...]
    outputs: tuple[WorkflowOutputContract, ...]
    invariant_results: tuple[WorkflowInvariantResult, ...]
    audit_event_types: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "config_version": self.config_version,
            "trigger_ref": self.trigger_ref,
            "idempotency_key": self.idempotency_key,
            "identity_state": self.identity_state,
            "evidence": self.evidence.to_dict(),
            "decisions": [decision.to_dict() for decision in self.decisions],
            "validations": [validation.to_dict() for validation in self.validations],
            "outputs": [output.to_dict() for output in self.outputs],
            "invariant_results": [result.to_dict() for result in self.invariant_results],
            "audit_event_types": list(self.audit_event_types),
        }


def evidence_item_from_receipt(
    receipt: Any,
    *,
    grain: str = "account",
    authority: str | None = None,
    freshness: str = "unknown",
    conflicts: tuple[str, ...] = (),
) -> WorkflowEvidenceItem:
    return WorkflowEvidenceItem(
        source_type=str(getattr(receipt, "source_type", "unknown")),
        source_id=str(getattr(receipt, "source_id", "")),
        field=str(getattr(receipt, "field", "")),
        observed_at=str(getattr(receipt, "observed_at", "")),
        authority=str(authority or getattr(receipt, "authority", "inferred")),
        grain=grain,
        customer_safe=bool(getattr(receipt, "customer_safe", False)),
        claim=str(getattr(receipt, "claim", "")),
        freshness=freshness,
        conflicts=conflicts,
    )


def build_evidence_bundle(
    *,
    receipts: tuple[Any, ...],
    reviewed_sources: tuple[str, ...],
    missing_required_sources: tuple[str, ...],
    customer_output_blockers: tuple[str, ...],
) -> WorkflowEvidenceBundle:
    return WorkflowEvidenceBundle(
        reviewed_sources=tuple(sorted(dict.fromkeys(reviewed_sources))),
        missing_required_sources=tuple(dict.fromkeys(missing_required_sources)),
        customer_output_blockers=tuple(dict.fromkeys(customer_output_blockers)),
        items=tuple(evidence_item_from_receipt(receipt) for receipt in receipts),
    )


def build_execution_envelope(
    definition: WorkflowDefinition,
    *,
    trigger_ref: str,
    idempotency_key: str,
    identity_state: IdentityState,
    evidence: WorkflowEvidenceBundle,
    decisions: tuple[WorkflowDecisionTrace, ...],
    validations: tuple[WorkflowValidationResult, ...],
    outputs: tuple[WorkflowOutputContract, ...],
) -> WorkflowExecutionEnvelope:
    partial = WorkflowExecutionEnvelope(
        workflow_id=definition.workflow_id,
        config_version=definition.config_version,
        trigger_ref=trigger_ref,
        idempotency_key=idempotency_key,
        identity_state=identity_state,
        evidence=evidence,
        decisions=decisions,
        validations=validations,
        outputs=outputs,
        invariant_results=(),
        audit_event_types=definition.audit_events,
    )
    invariants = evaluate_invariants(definition, partial)
    return WorkflowExecutionEnvelope(
        workflow_id=partial.workflow_id,
        config_version=partial.config_version,
        trigger_ref=partial.trigger_ref,
        idempotency_key=partial.idempotency_key,
        identity_state=partial.identity_state,
        evidence=partial.evidence,
        decisions=partial.decisions,
        validations=partial.validations,
        outputs=partial.outputs,
        invariant_results=invariants,
        audit_event_types=partial.audit_event_types,
    )


def evaluate_invariants(
    definition: WorkflowDefinition,
    envelope: WorkflowExecutionEnvelope,
) -> tuple[WorkflowInvariantResult, ...]:
    evidence_ids = set(envelope.evidence.evidence_ids())
    output_source_ids = {
        source_id for output in envelope.outputs for source_id in output.source_ids
    }
    decision_source_ids = {
        source_id for decision in envelope.decisions for source_id in decision.source_ids
    }
    customer_outputs = tuple(output for output in envelope.outputs if output.customer_affecting)
    blocking_failures = tuple(
        result for result in envelope.validations
        if result.blocks_customer_output and not result.passed
    )
    return (
        WorkflowInvariantResult(
            "workflow_identity_versioned",
            envelope.workflow_id == definition.workflow_id
            and envelope.config_version == definition.config_version,
            "Envelope workflow id and config version must match registry definition.",
        ),
        WorkflowInvariantResult(
            "idempotency_key_present",
            bool(envelope.idempotency_key),
            "Every execution must have a stable idempotency key.",
        ),
        WorkflowInvariantResult(
            "identity_exact_or_explicitly_unresolved",
            envelope.identity_state in {"exactly_one", "ambiguous", "none", "ignored"},
            "Identity must be exact or explicitly unresolved; silent guessing is forbidden.",
        ),
        WorkflowInvariantResult(
            "missing_evidence_visible",
            bool(envelope.evidence.reviewed_sources) or bool(envelope.evidence.missing_required_sources),
            "Workflow must expose reviewed or missing evidence sources.",
        ),
        WorkflowInvariantResult(
            "decision_trace_present",
            bool(envelope.decisions),
            "Workflow must expose a decision trace, even for ignored/internal-only outcomes.",
        ),
        WorkflowInvariantResult(
            "source_backed_claims_only",
            bool(evidence_ids)
            and bool(decision_source_ids <= evidence_ids)
            and bool(output_source_ids <= evidence_ids),
            "Decision and output source ids must be present in the evidence bundle.",
        ),
        WorkflowInvariantResult(
            "customer_output_governed",
            all(
                output.status in {"proposed", "suppressed", "not_applicable"}
                and bool(output.gate_action)
                for output in customer_outputs
            ),
            "Customer-affecting outputs must be proposed/suppressed behind a gate action.",
        ),
        WorkflowInvariantResult(
            "blocking_validation_suppresses_customer_output",
            not blocking_failures
            or not any(output.status == "proposed" for output in customer_outputs),
            "Blocking validation failures must prevent proposed customer-facing outputs.",
        ),
        WorkflowInvariantResult(
            "audit_events_declared",
            set(definition.audit_events) <= set(envelope.audit_event_types),
            "Envelope must declare the workflow audit events emitted by the runtime.",
        ),
    )


def invariant_failures(envelope: WorkflowExecutionEnvelope) -> tuple[str, ...]:
    return tuple(
        result.invariant for result in envelope.invariant_results if not result.passed
    )
