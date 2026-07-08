"""Authoring readiness checks for governed CSM workflows.

The registry defines what a workflow is. This module defines what makes a
workflow shippable: contract completeness, ActionGate alignment, customer-output
suppression policy, audit declarations, UI projection, and explicit test
obligations. It is intentionally structural; concrete workflows still own their
domain-specific packet shape and decision model.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from ultra_csm.governance.csm_actions import UnknownCSMActionError, csm_action_spec
from ultra_csm.workflow_playbooks import WORKFLOW_REGISTRY, WorkflowDefinition, WorkflowRegistry


IssueSeverity = Literal["error", "warning"]

REQUIRED_TEST_OBLIGATIONS = (
    "happy_path",
    "suppression_or_missing_data_path",
    "execution_envelope_invariants",
    "action_gate_path",
    "behavioral_quality_eval",
)
API_TEST_OBLIGATION = "api_trigger_persistence_ledger"
UI_TEST_OBLIGATION = "ui_projection_contract"


@dataclass(frozen=True)
class WorkflowTestAnchor:
    obligation: str
    test_module: str
    test_name: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkflowAuthoringSpec:
    workflow_id: str
    owns_external_trigger: bool
    owns_persisted_packet: bool
    ui_renderer: str
    test_anchors: tuple[WorkflowTestAnchor, ...]

    def declared_obligations(self) -> tuple[str, ...]:
        return tuple(anchor.obligation for anchor in self.test_anchors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "owns_external_trigger": self.owns_external_trigger,
            "owns_persisted_packet": self.owns_persisted_packet,
            "ui_renderer": self.ui_renderer,
            "test_anchors": [anchor.to_dict() for anchor in self.test_anchors],
        }


@dataclass(frozen=True)
class WorkflowAuthoringIssue:
    workflow_id: str
    check_name: str
    severity: IssueSeverity
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkflowReadiness:
    workflow_id: str
    ready: bool
    issues: tuple[WorkflowAuthoringIssue, ...]
    declared_test_obligations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "ready": self.ready,
            "issues": [issue.to_dict() for issue in self.issues],
            "declared_test_obligations": list(self.declared_test_obligations),
        }


@dataclass(frozen=True)
class WorkflowAuthoringReport:
    ready: bool
    workflows: tuple[WorkflowReadiness, ...]
    registry_issues: tuple[WorkflowAuthoringIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "workflows": {
                item.workflow_id: item.to_dict() for item in self.workflows
            },
            "registry_issues": [issue.to_dict() for issue in self.registry_issues],
        }


WORKFLOW_AUTHORING_SPECS: dict[str, WorkflowAuthoringSpec] = {
    "enterprise_closed_won_onboarding": WorkflowAuthoringSpec(
        workflow_id="enterprise_closed_won_onboarding",
        owns_external_trigger=True,
        owns_persisted_packet=True,
        ui_renderer="enterprise_launch_packet",
        test_anchors=(
            WorkflowTestAnchor("happy_path", "tests/test_enterprise_onboarding_workflow.py", "test_enterprise_closed_won_builds_launch_packet_from_connected_sources"),
            WorkflowTestAnchor("suppression_or_missing_data_path", "tests/test_enterprise_onboarding_workflow.py", "test_enterprise_closed_won_stops_before_customer_output_when_context_missing"),
            WorkflowTestAnchor("execution_envelope_invariants", "tests/test_enterprise_onboarding_workflow.py", "invariant_failures(packet.execution_envelope) == ()"),
            WorkflowTestAnchor("action_gate_path", "tests/test_enterprise_onboarding_workflow.py", "draft_customer_outreach"),
            WorkflowTestAnchor("behavioral_quality_eval", "tests/test_workflow_quality_eval.py", "enterprise_closed_won_happy_path"),
            WorkflowTestAnchor(API_TEST_OBLIGATION, "tests/test_enterprise_onboarding_workflow.py", "test_salesforce_closed_won_endpoint_runs_workflow_against_served_data_plane"),
            WorkflowTestAnchor(UI_TEST_OBLIGATION, "tests/test_ui_contract.py", "test_queue_detail_surfaces_enterprise_onboarding_packet"),
        ),
    ),
    "self_serve_signup_activation": WorkflowAuthoringSpec(
        workflow_id="self_serve_signup_activation",
        owns_external_trigger=True,
        owns_persisted_packet=True,
        ui_renderer="self_serve_value_path",
        test_anchors=(
            WorkflowTestAnchor("happy_path", "tests/test_self_serve_activation_workflow.py", "test_self_serve_signup_selects_team_value_path_and_gates_customer_outreach"),
            WorkflowTestAnchor("suppression_or_missing_data_path", "tests/test_self_serve_activation_workflow.py", "test_missing_product_telemetry_blocks_activation_judgment"),
            WorkflowTestAnchor("execution_envelope_invariants", "tests/test_self_serve_activation_workflow.py", "invariant_failures(packet.execution_envelope) == ()"),
            WorkflowTestAnchor("action_gate_path", "tests/test_self_serve_activation_workflow.py", "draft_customer_outreach"),
            WorkflowTestAnchor("behavioral_quality_eval", "tests/test_workflow_quality_eval.py", "self_serve_signup_team_value_path"),
            WorkflowTestAnchor(API_TEST_OBLIGATION, "tests/test_self_serve_activation_workflow.py", "test_self_serve_signup_endpoint_runs_against_served_data_plane_and_persists"),
            WorkflowTestAnchor(UI_TEST_OBLIGATION, "tests/test_ui_contract.py", "test_queue_detail_surfaces_self_serve_activation_packet"),
        ),
    ),
    "account_adoption_regression": WorkflowAuthoringSpec(
        workflow_id="account_adoption_regression",
        owns_external_trigger=True,
        owns_persisted_packet=True,
        ui_renderer="adoption_regression_review",
        test_anchors=(
            WorkflowTestAnchor("happy_path", "tests/test_adoption_regression_workflow.py", "test_adoption_regression_compares_windows_and_gates_customer_outreach"),
            WorkflowTestAnchor("suppression_or_missing_data_path", "tests/test_adoption_regression_workflow.py", "test_adoption_regression_blocks_customer_output_without_current_window"),
            WorkflowTestAnchor("execution_envelope_invariants", "tests/test_adoption_regression_workflow.py", "invariant_failures(packet.execution_envelope) == ()"),
            WorkflowTestAnchor("action_gate_path", "tests/test_adoption_regression_workflow.py", "draft_customer_outreach"),
            WorkflowTestAnchor("behavioral_quality_eval", "tests/test_workflow_quality_eval.py", "adoption_regression_support_friction"),
            WorkflowTestAnchor(API_TEST_OBLIGATION, "tests/test_adoption_regression_workflow.py", "test_adoption_regression_api_trigger_persists_packet_and_ledger"),
            WorkflowTestAnchor(UI_TEST_OBLIGATION, "tests/test_ui_contract.py", "test_queue_detail_surfaces_adoption_regression_packet"),
        ),
    ),
}


def evaluate_workflow_authoring_readiness(
    registry: WorkflowRegistry = WORKFLOW_REGISTRY,
    *,
    specs: dict[str, WorkflowAuthoringSpec] | None = None,
) -> WorkflowAuthoringReport:
    authoring_specs = WORKFLOW_AUTHORING_SPECS if specs is None else specs
    definitions = {definition.workflow_id: definition for definition in registry.list()}
    registry_issues: list[WorkflowAuthoringIssue] = []

    for workflow_id in sorted(definitions):
        if workflow_id not in authoring_specs:
            registry_issues.append(_issue(
                workflow_id,
                "authoring_spec_declared",
                "Workflow is registered without a WorkflowAuthoringSpec.",
            ))
    for workflow_id in sorted(authoring_specs):
        if workflow_id not in definitions:
            registry_issues.append(_issue(
                workflow_id,
                "authoring_spec_matches_registry",
                "WorkflowAuthoringSpec exists for a workflow not present in the registry.",
            ))

    workflow_readiness = tuple(
        _evaluate_definition(definition, authoring_specs.get(definition.workflow_id))
        for definition in registry.list()
    )
    ready = (
        not any(issue.severity == "error" for issue in registry_issues)
        and all(item.ready for item in workflow_readiness)
    )
    return WorkflowAuthoringReport(
        ready=ready,
        workflows=workflow_readiness,
        registry_issues=tuple(registry_issues),
    )


def _evaluate_definition(
    definition: WorkflowDefinition,
    spec: WorkflowAuthoringSpec | None,
) -> WorkflowReadiness:
    issues: list[WorkflowAuthoringIssue] = []
    if spec is None:
        return WorkflowReadiness(
            workflow_id=definition.workflow_id,
            ready=False,
            issues=(_issue(definition.workflow_id, "authoring_spec_declared", "Missing authoring spec."),),
            declared_test_obligations=(),
        )

    issues.extend(_definition_contract_issues(definition, spec))
    issues.extend(_test_obligation_issues(definition, spec))
    ready = not any(issue.severity == "error" for issue in issues)
    return WorkflowReadiness(
        workflow_id=definition.workflow_id,
        ready=ready,
        issues=tuple(issues),
        declared_test_obligations=spec.declared_obligations(),
    )


def _definition_contract_issues(
    definition: WorkflowDefinition,
    spec: WorkflowAuthoringSpec,
) -> tuple[WorkflowAuthoringIssue, ...]:
    issues: list[WorkflowAuthoringIssue] = []
    workflow_id = definition.workflow_id
    if not definition.config_version:
        issues.append(_issue(workflow_id, "config_version_declared", "Workflow config_version is empty."))
    if not definition.trigger.required_fields:
        issues.append(_issue(workflow_id, "trigger_required_fields", "Trigger has no required fields."))
    if not definition.trigger.idempotency_fields:
        issues.append(_issue(workflow_id, "trigger_idempotency_fields", "Trigger has no idempotency fields."))
    missing_idempotency = set(definition.trigger.idempotency_fields) - set(definition.trigger.required_fields)
    if missing_idempotency:
        issues.append(_issue(
            workflow_id,
            "idempotency_fields_in_trigger",
            f"Idempotency fields are not required trigger fields: {sorted(missing_idempotency)}.",
        ))
    required_sources = [item for item in definition.evidence_requirements if item.mode == "required"]
    if not required_sources:
        issues.append(_issue(workflow_id, "required_evidence_sources", "Workflow has no required evidence sources."))
    blocking_sources = [item for item in definition.evidence_requirements if item.blocks_customer_output]
    if not blocking_sources:
        issues.append(_issue(
            workflow_id,
            "customer_output_blocking_sources",
            "Workflow has no evidence source that blocks customer-facing output.",
        ))
    if not definition.value_contract or len(definition.value_contract.strip()) < 40:
        issues.append(_issue(workflow_id, "value_contract_substantive", "Value contract is missing or too short."))
    if not definition.action_contracts:
        issues.append(_issue(workflow_id, "action_contracts_declared", "Workflow has no action contracts."))
    for action in definition.action_contracts:
        try:
            csm_action_spec(action.gate_action)
        except UnknownCSMActionError:
            issues.append(_issue(
                workflow_id,
                "gate_action_known",
                f"Action {action.action_type!r} uses unknown gate_action {action.gate_action!r}.",
            ))
        if action.customer_affecting and not action.suppression_rules:
            issues.append(_issue(
                workflow_id,
                "customer_action_suppression_rules",
                f"Customer-affecting action {action.action_type!r} has no suppression rules.",
            ))
        if action.customer_affecting and action.gate_action == "recommend_next_best_action":
            issues.append(_issue(
                workflow_id,
                "customer_action_not_internal_gate",
                f"Customer-affecting action {action.action_type!r} maps to an internal-only gate.",
            ))
    if not any(gate.blocks_customer_output for gate in definition.validation_gates):
        issues.append(_issue(
            workflow_id,
            "blocking_validation_gate",
            "Workflow has no validation gate that blocks customer-facing output.",
        ))
    if len(definition.audit_events) < 2:
        issues.append(_issue(workflow_id, "audit_events_declared", "Workflow must declare trigger/packet audit events."))
    if spec.owns_external_trigger and not any(event.endswith(".trigger") for event in definition.audit_events):
        issues.append(_issue(workflow_id, "trigger_audit_event", "Externally triggered workflow lacks a trigger audit event."))
    if spec.owns_persisted_packet and not any(event.endswith(".packet") for event in definition.audit_events):
        issues.append(_issue(workflow_id, "packet_audit_event", "Persisted workflow lacks a packet audit event."))
    if definition.ui.renderer != spec.ui_renderer:
        issues.append(_issue(
            workflow_id,
            "ui_renderer_matches_authoring_spec",
            f"Registry renderer {definition.ui.renderer!r} does not match authoring spec {spec.ui_renderer!r}.",
        ))
    if not definition.ui.panel_title or not definition.ui.primary_metric or not definition.ui.secondary_metric:
        issues.append(_issue(workflow_id, "ui_projection_complete", "UI metadata is incomplete."))
    return tuple(issues)


def _test_obligation_issues(
    definition: WorkflowDefinition,
    spec: WorkflowAuthoringSpec,
) -> tuple[WorkflowAuthoringIssue, ...]:
    required = set(REQUIRED_TEST_OBLIGATIONS)
    if spec.owns_external_trigger or spec.owns_persisted_packet:
        required.add(API_TEST_OBLIGATION)
    if spec.ui_renderer:
        required.add(UI_TEST_OBLIGATION)
    declared = set(spec.declared_obligations())
    missing = sorted(required - declared)
    if not missing:
        return ()
    return (_issue(
        definition.workflow_id,
        "test_obligations_declared",
        f"Missing required test obligations: {missing}.",
    ),)


def _issue(
    workflow_id: str,
    check_name: str,
    detail: str,
    severity: IssueSeverity = "error",
) -> WorkflowAuthoringIssue:
    return WorkflowAuthoringIssue(
        workflow_id=workflow_id,
        check_name=check_name,
        severity=severity,
        detail=detail,
    )
