from __future__ import annotations

from ultra_csm.workflow_core import (
    WorkflowDecisionTrace,
    WorkflowEvidenceBundle,
    WorkflowEvidenceItem,
    WorkflowOutputContract,
    WorkflowValidationResult,
    build_execution_envelope,
    invariant_failures,
)
from ultra_csm.workflow_playbooks import (
    ENTERPRISE_CLOSED_WON_ONBOARDING,
    SELF_SERVE_SIGNUP_ACTIVATION,
)


def test_execution_envelope_allows_domain_specific_decision_payloads():
    enterprise = build_execution_envelope(
        ENTERPRISE_CLOSED_WON_ONBOARDING,
        trigger_ref="opp-1",
        idempotency_key="enterprise:opp-1",
        identity_state="exactly_one",
        evidence=_bundle("opp-1"),
        decisions=(
            WorkflowDecisionTrace(
                decision_kind="enterprise_success_plan",
                selected_hypothesis="relationship maps",
                alternatives=("pipeline review",),
                confidence=0.82,
                confidence_model=("rank first value from entitlements",),
                source_ids=("opp-1",),
                limitations=("confirm sponsor",),
                domain_payload={"success_plan_v0": [{"milestone": "First value event achieved"}]},
            ),
        ),
        validations=(_passing("value_model_available", "opp-1"),),
        outputs=(_internal_output("opp-1"),),
    )
    self_serve = build_execution_envelope(
        SELF_SERVE_SIGNUP_ACTIVATION,
        trigger_ref="workspace-1",
        idempotency_key="self-serve:workspace-1",
        identity_state="exactly_one",
        evidence=_bundle("workspace-1"),
        decisions=(
            WorkflowDecisionTrace(
                decision_kind="self_serve_value_path",
                selected_hypothesis="team_workspace_creator",
                alternatives=("crm_enterprise_curious",),
                confidence=0.72,
                confidence_model=("score source-backed metrics",),
                source_ids=("workspace-1",),
                limitations=("confirm champion",),
                domain_payload={"first_value_reached": True, "current_milestone_id": None},
            ),
        ),
        validations=(_passing("product_telemetry_present", "workspace-1"),),
        outputs=(_internal_output("workspace-1"),),
    )

    assert enterprise.workflow_id != self_serve.workflow_id
    assert enterprise.decisions[0].domain_payload != self_serve.decisions[0].domain_payload
    assert invariant_failures(enterprise) == ()
    assert invariant_failures(self_serve) == ()


def test_invariants_fail_when_claims_are_not_source_backed():
    envelope = build_execution_envelope(
        SELF_SERVE_SIGNUP_ACTIVATION,
        trigger_ref="workspace-1",
        idempotency_key="self-serve:workspace-1",
        identity_state="exactly_one",
        evidence=_bundle("workspace-1"),
        decisions=(
            WorkflowDecisionTrace(
                decision_kind="self_serve_value_path",
                selected_hypothesis="team_workspace_creator",
                alternatives=(),
                confidence=0.7,
                confidence_model=("score source-backed metrics",),
                source_ids=("missing-source",),
                limitations=(),
                domain_payload={"first_value_reached": True},
            ),
        ),
        validations=(_passing("product_telemetry_present", "workspace-1"),),
        outputs=(_internal_output("workspace-1"),),
    )

    assert "source_backed_claims_only" in invariant_failures(envelope)


def test_invariants_fail_when_customer_output_bypasses_gate():
    envelope = build_execution_envelope(
        SELF_SERVE_SIGNUP_ACTIVATION,
        trigger_ref="workspace-1",
        idempotency_key="self-serve:workspace-1",
        identity_state="exactly_one",
        evidence=_bundle("workspace-1"),
        decisions=(
            WorkflowDecisionTrace(
                decision_kind="self_serve_value_path",
                selected_hypothesis="team_workspace_creator",
                alternatives=(),
                confidence=0.7,
                confidence_model=("score source-backed metrics",),
                source_ids=("workspace-1",),
                limitations=(),
                domain_payload={"first_value_reached": True},
            ),
        ),
        validations=(_passing("product_telemetry_present", "workspace-1"),),
        outputs=(
            WorkflowOutputContract(
                artifact_type="email",
                audience="customer_facing",
                action_type="draft_customer_outreach",
                customer_affecting=True,
                gate_action=None,
                status="prepared",
                source_ids=("workspace-1",),
                suppression_reasons=(),
            ),
        ),
    )

    assert "customer_output_governed" in invariant_failures(envelope)


def _bundle(source_id: str) -> WorkflowEvidenceBundle:
    return WorkflowEvidenceBundle(
        reviewed_sources=("product_telemetry",),
        missing_required_sources=(),
        customer_output_blockers=(),
        items=(
            WorkflowEvidenceItem(
                source_type="product_telemetry",
                source_id=source_id,
                field="metric_name",
                observed_at="2026-07-08T12:00:00Z",
                authority="customer_observed",
                grain="account",
                customer_safe=True,
                claim="Source-backed claim.",
            ),
        ),
    )


def _passing(check_name: str, source_id: str) -> WorkflowValidationResult:
    return WorkflowValidationResult(
        check_name=check_name,
        passed=True,
        blocks_customer_output=True,
        detail="passed",
        source_ids=(source_id,),
    )


def _internal_output(source_id: str) -> WorkflowOutputContract:
    return WorkflowOutputContract(
        artifact_type="packet",
        audience="csm_facing",
        action_type="internal_review",
        customer_affecting=False,
        gate_action=None,
        status="prepared",
        source_ids=(source_id,),
        suppression_reasons=(),
    )
