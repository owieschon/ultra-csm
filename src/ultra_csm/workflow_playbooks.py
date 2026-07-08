"""Shared workflow/playbook contracts for governed CSM agents.

The concrete workflows still own their domain-specific evidence gathering and
packet construction. This module owns the reusable contract every workflow must
declare: trigger, sources, value logic, action policy, suppression rules,
validation gates, audit events, and UI projection metadata.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


WorkflowAudience = Literal["enterprise", "self_serve", "internal"]
WorkflowSourceMode = Literal["required", "optional", "conditional"]


@dataclass(frozen=True)
class WorkflowTriggerContract:
    source: str
    event_name: str
    required_fields: tuple[str, ...]
    idempotency_fields: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkflowEvidenceRequirement:
    source_type: str
    mode: WorkflowSourceMode
    reason: str
    blocks_customer_output: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkflowActionContract:
    action_type: str
    trigger: str
    customer_affecting: bool
    suppression_rules: tuple[str, ...]
    gate_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkflowValidationGate:
    check_name: str
    blocks_customer_output: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkflowUIMetadata:
    panel_title: str
    primary_metric: str
    secondary_metric: str
    renderer: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkflowDefinition:
    workflow_id: str
    config_version: str
    audience: WorkflowAudience
    trigger: WorkflowTriggerContract
    evidence_requirements: tuple[WorkflowEvidenceRequirement, ...]
    value_contract: str
    action_contracts: tuple[WorkflowActionContract, ...]
    validation_gates: tuple[WorkflowValidationGate, ...]
    audit_events: tuple[str, ...]
    ui: WorkflowUIMetadata

    def required_source_types(self) -> tuple[str, ...]:
        return tuple(
            item.source_type for item in self.evidence_requirements
            if item.mode == "required"
        )

    def customer_output_blocking_sources(self) -> tuple[str, ...]:
        return tuple(
            item.source_type for item in self.evidence_requirements
            if item.blocks_customer_output
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "config_version": self.config_version,
            "audience": self.audience,
            "trigger": self.trigger.to_dict(),
            "evidence_requirements": [
                item.to_dict() for item in self.evidence_requirements
            ],
            "value_contract": self.value_contract,
            "action_contracts": [
                item.to_dict() for item in self.action_contracts
            ],
            "validation_gates": [
                item.to_dict() for item in self.validation_gates
            ],
            "audit_events": list(self.audit_events),
            "ui": self.ui.to_dict(),
        }


@dataclass(frozen=True)
class WorkflowCoverageResult:
    workflow_id: str
    reviewed_sources: tuple[str, ...]
    missing_required_sources: tuple[str, ...]
    customer_output_blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WorkflowRegistry:
    def __init__(self, definitions: tuple[WorkflowDefinition, ...]) -> None:
        self._definitions = {definition.workflow_id: definition for definition in definitions}
        if len(self._definitions) != len(definitions):
            raise ValueError("workflow registry contains duplicate workflow_id")

    def get(self, workflow_id: str) -> WorkflowDefinition:
        try:
            return self._definitions[workflow_id]
        except KeyError as exc:
            raise KeyError(f"unknown workflow_id: {workflow_id}") from exc

    def list(self) -> tuple[WorkflowDefinition, ...]:
        return tuple(self._definitions[key] for key in sorted(self._definitions))

    def to_dict(self) -> dict[str, Any]:
        return {key: value.to_dict() for key, value in self._definitions.items()}


def evaluate_source_coverage(
    definition: WorkflowDefinition,
    *,
    reviewed_sources: tuple[str, ...],
) -> WorkflowCoverageResult:
    reviewed = frozenset(reviewed_sources)
    missing = tuple(
        requirement.source_type
        for requirement in definition.evidence_requirements
        if requirement.mode == "required" and requirement.source_type not in reviewed
    )
    blockers = tuple(
        requirement.source_type
        for requirement in definition.evidence_requirements
        if requirement.blocks_customer_output and requirement.source_type not in reviewed
    )
    return WorkflowCoverageResult(
        workflow_id=definition.workflow_id,
        reviewed_sources=tuple(sorted(reviewed)),
        missing_required_sources=missing,
        customer_output_blockers=blockers,
    )


def workflow_packet_metadata(definition: WorkflowDefinition) -> dict[str, Any]:
    return {
        "workflow_id": definition.workflow_id,
        "config_version": definition.config_version,
        "audience": definition.audience,
        "trigger": definition.trigger.to_dict(),
        "value_contract": definition.value_contract,
        "ui": definition.ui.to_dict(),
    }


ENTERPRISE_CLOSED_WON_ONBOARDING = WorkflowDefinition(
    workflow_id="enterprise_closed_won_onboarding",
    config_version="enterprise-success-plan-config-v2",
    audience="enterprise",
    trigger=WorkflowTriggerContract(
        source="salesforce",
        event_name="opportunity_closed_won",
        required_fields=("opportunity_id", "account_id", "stage_name", "observed_at"),
        idempotency_fields=("opportunity_id", "observed_at"),
    ),
    evidence_requirements=(
        WorkflowEvidenceRequirement("salesforce_opportunity", "required", "Commercial trigger and purchased account boundary.", True),
        WorkflowEvidenceRequirement("salesforce_account", "required", "Customer organization identity.", True),
        WorkflowEvidenceRequirement("salesforce_contacts", "required", "Stakeholder/contact context.", True),
        WorkflowEvidenceRequirement("entitlements", "required", "Purchased scope bounds the success plan.", True),
        WorkflowEvidenceRequirement("product_usage", "required", "Current product/provisioning state.", True),
        WorkflowEvidenceRequirement("customer_email_or_call_or_calendar", "required", "Customer-facing context grounds kickoff language.", True),
        WorkflowEvidenceRequirement("value_model_alignment", "required", "Measurable rails and thresholds.", True),
        WorkflowEvidenceRequirement("internal_handoff_notes", "optional", "Sales-to-CS context improves tailoring."),
        WorkflowEvidenceRequirement("onboarding_source", "optional", "Implementation state and task risk."),
    ),
    value_contract=(
        "Build success plan from explicit first-value hypotheses, purchased scope, "
        "customer context, stakeholder verification, and deterministic value-model rails."
    ),
    action_contracts=(
        WorkflowActionContract("draft_kickoff_outreach", "closed_won_enterprise_ready", True, ("missing_customer_context", "missing_consent", "failed_success_plan_validation"), "draft_customer_outreach"),
        WorkflowActionContract("propose_success_plan", "closed_won_enterprise_ready", True, ("failed_success_plan_validation",), "edit_success_plan"),
    ),
    validation_gates=(
        WorkflowValidationGate("value_model_available", True, "Success plan must use deterministic value model."),
        WorkflowValidationGate("first_value_milestone_explicit", True, "First value must be an explicit selected hypothesis."),
        WorkflowValidationGate("milestones_map_to_value_model_rails", True, "Every milestone must carry measurable rail target."),
        WorkflowValidationGate("customer_context_present", True, "No customer-facing output without customer/call/calendar context."),
    ),
    audit_events=(
        "enterprise_onboarding.trigger",
        "enterprise_onboarding.packet",
        "enterprise_onboarding.success_plan",
    ),
    ui=WorkflowUIMetadata(
        panel_title="Enterprise launch packet",
        primary_metric="ttv_priority_score",
        secondary_metric="value_model_alignment",
        renderer="enterprise_launch_packet",
    ),
)


SELF_SERVE_SIGNUP_ACTIVATION = WorkflowDefinition(
    workflow_id="self_serve_signup_activation",
    config_version="self-serve-value-path-config-v2",
    audience="self_serve",
    trigger=WorkflowTriggerContract(
        source="product",
        event_name="self_serve_signup",
        required_fields=("workspace_id", "signup_email", "observed_at"),
        idempotency_fields=("workspace_id", "signup_email", "observed_at"),
    ),
    evidence_requirements=(
        WorkflowEvidenceRequirement("resolved_organization", "required", "Map signup to a workspace/customer organization.", True),
        WorkflowEvidenceRequirement("product_telemetry", "required", "Activation judgment requires product behavior.", True),
        WorkflowEvidenceRequirement("contact_record", "required", "Customer-facing action requires a contact and consent.", True),
        WorkflowEvidenceRequirement("entitlement", "optional", "Capability scope improves path selection."),
        WorkflowEvidenceRequirement("adoption_summary", "optional", "Adoption rollups calibrate confidence."),
        WorkflowEvidenceRequirement("customer_email", "optional", "Customer intent context."),
        WorkflowEvidenceRequirement("call_transcript", "optional", "Customer intent context."),
        WorkflowEvidenceRequirement("internal_slack_or_note", "optional", "Internal context."),
        WorkflowEvidenceRequirement("salesforce_case", "optional", "Support friction context."),
    ),
    value_contract=(
        "Select and preserve ranked value-path hypotheses, then evaluate explicit "
        "thresholded milestones. First value is only true when the configured "
        "first-value milestone completes."
    ),
    action_contracts=(
        WorkflowActionContract("send_activation_nudge", "workspace_created_without_first_value", True, ("personal_email", "no_consent", "recent_nudge", "missing_product_telemetry"), "draft_customer_outreach"),
        WorkflowActionContract("send_invite_followup", "invites_sent_without_activation", True, ("personal_email", "no_consent", "recent_nudge"), "draft_customer_outreach"),
        WorkflowActionContract("recommend_next_feature", "first_value_reached_with_feature_depth_gap", True, ("personal_email", "no_consent"), "draft_customer_outreach"),
        WorkflowActionContract("route_to_sales_assisted_expansion", "enterprise_only_crm_interest", False, ("crm_enterprise_only",), "recommend_next_best_action"),
        WorkflowActionContract("internal_only_packet", "strong_signal_but_unsafe_customer_action", False, (), "recommend_next_best_action"),
    ),
    validation_gates=(
        WorkflowValidationGate("organization_identity_exact", True, "Organization identity must resolve exactly for customer outreach."),
        WorkflowValidationGate("product_telemetry_present", True, "Telemetry is required before activation claims."),
        WorkflowValidationGate("first_value_not_inferred_from_count", True, "First value must come from explicit milestone completion."),
        WorkflowValidationGate("secondary_hypotheses_preserved", False, "Alternate interpretations should remain visible."),
    ),
    audit_events=(
        "self_serve_activation.trigger",
        "self_serve_activation.packet",
        "self_serve_activation.value_path",
    ),
    ui=WorkflowUIMetadata(
        panel_title="Self-serve value path",
        primary_metric="first_value_reached",
        secondary_metric="secondary_hypotheses",
        renderer="self_serve_value_path",
    ),
)


WORKFLOW_REGISTRY = WorkflowRegistry((
    ENTERPRISE_CLOSED_WON_ONBOARDING,
    SELF_SERVE_SIGNUP_ACTIVATION,
))
