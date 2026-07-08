from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ultra_csm import api
from ultra_csm.workflow_authoring import (
    WORKFLOW_AUTHORING_SPECS,
    WorkflowAuthoringSpec,
    WorkflowTestAnchor,
    evaluate_workflow_authoring_readiness,
)
from ultra_csm.workflow_playbooks import (
    SELF_SERVE_SIGNUP_ACTIVATION,
    WORKFLOW_REGISTRY,
    WorkflowActionContract,
    WorkflowDefinition,
    WorkflowEvidenceRequirement,
    WorkflowRegistry,
    WorkflowTriggerContract,
    WorkflowUIMetadata,
    WorkflowValidationGate,
)


REPO = Path(__file__).resolve().parents[1]


def test_current_workflow_registry_passes_authoring_readiness():
    report = evaluate_workflow_authoring_readiness(WORKFLOW_REGISTRY)

    assert report.ready is True
    assert report.registry_issues == ()
    assert {item.workflow_id for item in report.workflows} == {
        "enterprise_closed_won_onboarding",
        "self_serve_signup_activation",
        "account_adoption_regression",
    }
    for workflow in report.workflows:
        assert workflow.ready is True
        assert workflow.issues == ()
        assert {
            "happy_path",
            "suppression_or_missing_data_path",
            "execution_envelope_invariants",
            "action_gate_path",
            "api_trigger_persistence_ledger",
            "ui_projection_contract",
        } <= set(workflow.declared_test_obligations)


def test_workflow_authoring_readiness_endpoint_exposes_report():
    with TestClient(api.app) as client:
        resp = client.get("/workflow-authoring/readiness")

    assert resp.status_code == 200
    body = resp.json()
    assert body["report"]["ready"] is True
    assert "account_adoption_regression" in body["report"]["workflows"]
    assert body["report"]["workflows"]["account_adoption_regression"]["ready"] is True


def test_workflow_authoring_test_anchors_exist_in_repo():
    for spec in WORKFLOW_AUTHORING_SPECS.values():
        for anchor in spec.test_anchors:
            source = (REPO / anchor.test_module).read_text(encoding="utf-8")
            assert anchor.test_name in source, (
                f"{spec.workflow_id} authoring anchor {anchor.obligation} "
                f"does not exist: {anchor.test_module}::{anchor.test_name}"
            )


def test_authoring_readiness_rejects_malformed_workflow_definition():
    bad = WorkflowDefinition(
        workflow_id="bad_workflow",
        config_version="",
        audience="enterprise",
        trigger=WorkflowTriggerContract(
            source="product",
            event_name="bad_event",
            required_fields=("account_id",),
            idempotency_fields=("missing_from_required_fields",),
        ),
        evidence_requirements=(
            WorkflowEvidenceRequirement("nice_to_have", "optional", "Not enough."),
        ),
        value_contract="Too short.",
        action_contracts=(
            WorkflowActionContract(
                action_type="email_customer_anyway",
                trigger="bad_trigger",
                customer_affecting=True,
                suppression_rules=(),
                gate_action="recommend_next_best_action",
            ),
        ),
        validation_gates=(
            WorkflowValidationGate(
                check_name="advisory_only",
                blocks_customer_output=False,
                reason="Does not block.",
            ),
        ),
        audit_events=("bad_workflow.packet",),
        ui=WorkflowUIMetadata(
            panel_title="Bad workflow",
            primary_metric="",
            secondary_metric="",
            renderer="bad_renderer",
        ),
    )
    registry = WorkflowRegistry((bad,))
    spec = WorkflowAuthoringSpec(
        workflow_id="bad_workflow",
        owns_external_trigger=True,
        owns_persisted_packet=True,
        ui_renderer="expected_renderer",
        test_anchors=(
            WorkflowTestAnchor("happy_path", "tests/test_bad.py", "test_bad_happy_path"),
        ),
    )

    report = evaluate_workflow_authoring_readiness(registry, specs={"bad_workflow": spec})

    assert report.ready is False
    issues = {
        issue.check_name
        for workflow in report.workflows
        for issue in workflow.issues
    }
    assert {
        "config_version_declared",
        "idempotency_fields_in_trigger",
        "required_evidence_sources",
        "customer_output_blocking_sources",
        "value_contract_substantive",
        "customer_action_suppression_rules",
        "customer_action_not_internal_gate",
        "blocking_validation_gate",
        "trigger_audit_event",
        "ui_renderer_matches_authoring_spec",
        "ui_projection_complete",
        "test_obligations_declared",
    } <= issues


def test_registered_workflow_without_authoring_spec_fails_readiness():
    registry = WorkflowRegistry((SELF_SERVE_SIGNUP_ACTIVATION,))

    report = evaluate_workflow_authoring_readiness(registry, specs={})

    assert report.ready is False
    assert any(
        issue.check_name == "authoring_spec_declared"
        for issue in report.registry_issues
    )
