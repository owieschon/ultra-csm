from __future__ import annotations

from fastapi.testclient import TestClient

from ultra_csm import api
from ultra_csm.workflow_playbooks import (
    ACCOUNT_ADOPTION_REGRESSION,
    ENTERPRISE_CLOSED_WON_ONBOARDING,
    SELF_SERVE_SIGNUP_ACTIVATION,
    WORKFLOW_REGISTRY,
    evaluate_source_coverage,
    workflow_packet_metadata,
)


def test_workflow_registry_exposes_reusable_workflow_contracts():
    workflows = {definition.workflow_id: definition for definition in WORKFLOW_REGISTRY.list()}

    assert workflows["enterprise_closed_won_onboarding"] is ENTERPRISE_CLOSED_WON_ONBOARDING
    assert workflows["self_serve_signup_activation"] is SELF_SERVE_SIGNUP_ACTIVATION
    assert workflows["account_adoption_regression"] is ACCOUNT_ADOPTION_REGRESSION
    assert ENTERPRISE_CLOSED_WON_ONBOARDING.config_version == "enterprise-success-plan-config-v2"
    assert SELF_SERVE_SIGNUP_ACTIVATION.config_version == "self-serve-value-path-config-v2"
    assert ACCOUNT_ADOPTION_REGRESSION.config_version == "account-adoption-regression-config-v1"
    assert ENTERPRISE_CLOSED_WON_ONBOARDING.validation_status == "dormant_unvalidated"
    assert SELF_SERVE_SIGNUP_ACTIVATION.validation_status == "validated_by_deterministic_oracle"
    assert ACCOUNT_ADOPTION_REGRESSION.validation_status == "dormant_unvalidated"
    assert ENTERPRISE_CLOSED_WON_ONBOARDING.trigger.source == "salesforce"
    assert SELF_SERVE_SIGNUP_ACTIVATION.trigger.source == "product"
    assert ACCOUNT_ADOPTION_REGRESSION.trigger.event_name == "usage_regression_detected"


def test_workflow_definitions_declare_sources_actions_gates_audit_and_ui():
    for definition in WORKFLOW_REGISTRY.list():
        assert definition.trigger.required_fields
        assert definition.required_source_types()
        assert definition.customer_output_blocking_sources()
        assert definition.action_contracts
        assert definition.validation_gates
        assert definition.audit_events
        assert definition.ui.panel_title
        assert definition.ui.renderer

    self_serve_actions = {
        action.action_type: action for action in SELF_SERVE_SIGNUP_ACTIVATION.action_contracts
    }
    assert self_serve_actions["route_to_sales_assisted_expansion"].customer_affecting is False
    assert self_serve_actions["send_activation_nudge"].gate_action == "draft_customer_outreach"

    enterprise_gates = {gate.check_name for gate in ENTERPRISE_CLOSED_WON_ONBOARDING.validation_gates}
    assert {
        "value_model_available",
        "first_value_milestone_explicit",
        "milestones_map_to_value_model_rails",
    } <= enterprise_gates


def test_shared_coverage_evaluator_identifies_missing_blocking_sources():
    coverage = evaluate_source_coverage(
        SELF_SERVE_SIGNUP_ACTIVATION,
        reviewed_sources=("resolved_organization",),
    )

    assert coverage.workflow_id == "self_serve_signup_activation"
    assert "product_telemetry" in coverage.missing_required_sources
    assert "contact_record" in coverage.missing_required_sources
    assert "product_telemetry" in coverage.customer_output_blockers
    assert "contact_record" in coverage.customer_output_blockers


def test_workflow_packet_metadata_is_serializable_and_ui_ready():
    meta = workflow_packet_metadata(ENTERPRISE_CLOSED_WON_ONBOARDING)

    assert meta["workflow_id"] == "enterprise_closed_won_onboarding"
    assert meta["config_version"] == "enterprise-success-plan-config-v2"
    assert meta["validation_status"] == "dormant_unvalidated"
    assert meta["trigger"]["event_name"] == "opportunity_closed_won"
    assert meta["ui"]["renderer"] == "enterprise_launch_packet"


def test_workflow_playbooks_endpoint_exposes_registry():
    with TestClient(api.app) as client:
        resp = client.get("/workflow-playbooks")

    assert resp.status_code == 200
    body = resp.json()
    assert "enterprise_closed_won_onboarding" in body["workflows"]
    assert "self_serve_signup_activation" in body["workflows"]
    assert "account_adoption_regression" in body["workflows"]
    assert (
        body["workflows"]["enterprise_closed_won_onboarding"]["validation_status"]
        == "dormant_unvalidated"
    )
    assert (
        body["workflows"]["self_serve_signup_activation"]["validation_status"]
        == "validated_by_deterministic_oracle"
    )
    assert (
        body["workflows"]["self_serve_signup_activation"]["value_contract"]
        .startswith("Select and preserve ranked value-path hypotheses")
    )
