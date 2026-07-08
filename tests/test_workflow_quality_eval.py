from __future__ import annotations

from copy import deepcopy

from tests._govhelpers import CLOCK, T1, setup_roster
from tests.test_adoption_regression_workflow import (
    AS_OF as REGRESSION_AS_OF,
    _regression_data_plane,
    _regression_event,
)
from tests.test_enterprise_onboarding_workflow import (
    AS_OF as ENTERPRISE_AS_OF,
    _GoogleCalendarProvider,
    _calendar_events,
    _closed_won_event,
    _enterprise_data_plane,
)
from tests.test_self_serve_activation_workflow import (
    AS_OF as SELF_SERVE_AS_OF,
    _self_serve_data_plane,
    _signup_event,
)
from ultra_csm.adoption_regression import run_account_adoption_regression
from ultra_csm.enterprise_onboarding import run_enterprise_closed_won_onboarding
from ultra_csm.governance import ActionGate, FixtureVerdictSource
from ultra_csm.self_serve_activation import run_self_serve_signup_activation
from ultra_csm.workflow_quality_eval import (
    WorkflowQualityCase,
    WorkflowQualityExpectation,
    evaluate_workflow_packet_quality,
    evaluate_workflow_quality_report,
)


def test_quality_eval_passes_current_canonical_workflows(runtime_conn):
    runtime_conn.execute("BEGIN")
    try:
        orch, _authority = setup_roster(runtime_conn, tenant=T1)
        gate = ActionGate(
            runtime_conn,
            tenant_id=T1,
            actor_principal_id=orch,
            verdict_source=FixtureVerdictSource(),
            now=CLOCK,
        )
        enterprise = run_enterprise_closed_won_onboarding(
            data_plane=_enterprise_data_plane(include_context=True, include_usage=True),
            gate=gate,
            event=_closed_won_event(),
            as_of=ENTERPRISE_AS_OF,
            calendar_provider=_GoogleCalendarProvider(_calendar_events()),
        )
        self_serve = run_self_serve_signup_activation(
            data_plane=_self_serve_data_plane(
                usage_metrics=("workspace_created", "invite_sent", "invited_user_activated", "crm_connect_clicked")
            ),
            gate=gate,
            event=_signup_event(),
            as_of=SELF_SERVE_AS_OF,
        )
        regression = run_account_adoption_regression(
            data_plane=_regression_data_plane(),
            gate=gate,
            event=_regression_event(),
            as_of=REGRESSION_AS_OF,
        )
    finally:
        runtime_conn.rollback()

    report = evaluate_workflow_quality_report((
        WorkflowQualityCase(
            packet=enterprise.to_dict(),
            expectation=WorkflowQualityExpectation(
                scenario_id="enterprise_closed_won_happy_path",
                workflow_id="enterprise_closed_won_onboarding",
                expected_statuses=("ready",),
                required_reviewed_sources=(
                    "salesforce_opportunity",
                    "salesforce_account",
                    "salesforce_contacts",
                    "entitlements",
                    "product_usage",
                    "customer_email_or_call_or_calendar",
                    "value_model_alignment",
                    "google_calendar_attendance",
                ),
                required_action_types=("draft_customer_outreach", "edit_success_plan"),
                required_decision_kinds=("enterprise_success_plan",),
                required_domain_paths=(
                    "success_plan_methodology.value_model_alignment.config_version",
                    "success_plan_methodology.first_value_hypotheses",
                    "success_plan_methodology.validation_checks",
                    "success_plan_v0.measurement.rail",
                    "stakeholder_verification.observed_sources",
                ),
                required_alternatives=("deal review workflows",),
                expect_customer_output=True,
            ),
        ),
        WorkflowQualityCase(
            packet=self_serve.to_dict(),
            expectation=WorkflowQualityExpectation(
                scenario_id="self_serve_signup_team_value_path",
                workflow_id="self_serve_signup_activation",
                expected_statuses=("ready",),
                required_reviewed_sources=(
                    "resolved_organization",
                    "product_telemetry",
                    "contact_record",
                    "entitlement",
                    "adoption_summary",
                ),
                required_action_types=("draft_customer_outreach",),
                required_decision_kinds=("self_serve_value_path",),
                required_domain_paths=(
                    "value_path.first_value_definition",
                    "value_path.first_value_milestone_id",
                    "value_path.milestones.status",
                    "value_path.secondary_hypotheses.path_id",
                ),
                required_alternatives=("crm_enterprise_curious",),
                expect_customer_output=True,
            ),
        ),
        WorkflowQualityCase(
            packet=regression.to_dict(),
            expectation=WorkflowQualityExpectation(
                scenario_id="adoption_regression_support_friction",
                workflow_id="account_adoption_regression",
                expected_statuses=("ready",),
                required_reviewed_sources=(
                    "account_identity",
                    "product_telemetry",
                    "baseline_usage_window",
                    "current_usage_window",
                    "entitlement",
                    "adoption_summary",
                    "value_model_alignment",
                    "support_pressure",
                ),
                required_action_types=("draft_customer_outreach",),
                required_decision_kinds=("account_adoption_regression",),
                required_domain_paths=(
                    "metric_comparisons.drop_ratio",
                    "metric_comparisons.severity",
                    "value_context.config_version",
                    "value_context.lifecycle_stage",
                    "contributing_context.support_pressure",
                    "interpretation.selected_hypothesis",
                ),
                required_alternatives=("telemetry_noise_or_seasonality",),
                expect_customer_output=True,
            ),
        ),
    ), generated_at="2026-07-08T00:00:00+00:00")

    assert report.passed is True
    body = report.to_dict()
    assert body["passed"] is True
    assert {item["workflow_id"] for item in body["results"]} == {
        "enterprise_closed_won_onboarding",
        "self_serve_signup_activation",
        "account_adoption_regression",
    }


def test_quality_eval_fails_when_required_source_is_missing(runtime_conn):
    runtime_conn.execute("BEGIN")
    try:
        orch, _authority = setup_roster(runtime_conn, tenant=T1)
        gate = ActionGate(
            runtime_conn,
            tenant_id=T1,
            actor_principal_id=orch,
            verdict_source=FixtureVerdictSource(),
            now=CLOCK,
        )
        packet = run_account_adoption_regression(
            data_plane=_regression_data_plane(),
            gate=gate,
            event=_regression_event(),
            as_of=REGRESSION_AS_OF,
        ).to_dict()
    finally:
        runtime_conn.rollback()

    packet = deepcopy(packet)
    packet["coverage"]["reviewed_sources"] = [
        source for source in packet["coverage"]["reviewed_sources"]
        if source != "support_pressure"
    ]
    packet["source_receipts"] = [
        receipt for receipt in packet["source_receipts"]
        if receipt["source_type"] != "support_pressure"
    ]
    packet["execution_envelope"]["evidence"]["reviewed_sources"] = [
        source for source in packet["execution_envelope"]["evidence"]["reviewed_sources"]
        if source != "support_pressure"
    ]
    packet["execution_envelope"]["evidence"]["items"] = [
        item for item in packet["execution_envelope"]["evidence"]["items"]
        if item["source_type"] != "support_pressure"
    ]
    result = evaluate_workflow_packet_quality(
        packet,
        WorkflowQualityExpectation(
            scenario_id="support_pressure_required_for_this_case",
            workflow_id="account_adoption_regression",
            expected_statuses=("ready",),
            required_reviewed_sources=("support_pressure",),
        ),
    )

    assert result.passed is False
    failures = {criterion.criterion_id: criterion for criterion in result.criteria if not criterion.passed}
    assert "all_required_sources_reviewed" in failures
    assert "support_pressure" in failures["all_required_sources_reviewed"].detail


def test_quality_eval_fails_when_customer_output_is_proposed_despite_weak_evidence():
    packet = {
        "workflow_id": "self_serve_signup_activation",
        "status": "needs_data",
        "execution_envelope": {
            "workflow_id": "self_serve_signup_activation",
            "evidence": {"reviewed_sources": ["resolved_organization"], "items": []},
            "decisions": [{"decision_kind": "value_path_selection", "alternatives": []}],
            "outputs": [
                {
                    "artifact_type": "email",
                    "audience": "customer_facing",
                    "action_type": "draft_customer_outreach",
                    "customer_affecting": True,
                    "status": "proposed",
                }
            ],
            "invariant_results": [
                {
                    "invariant": "blocking_validation_suppresses_customer_output",
                    "passed": False,
                }
            ],
        },
        "customer_language": "Let's get you activated.",
        "proposals": [{"action_type": "draft_customer_outreach"}],
    }

    result = evaluate_workflow_packet_quality(
        packet,
        WorkflowQualityExpectation(
            scenario_id="self_serve_missing_telemetry_blocks_outreach",
            workflow_id="self_serve_signup_activation",
            expected_statuses=("needs_data",),
            required_action_types=("draft_customer_outreach",),
            required_decision_kinds=("value_path_selection",),
            expect_customer_output=False,
        ),
    )

    failures = {criterion.criterion_id: criterion for criterion in result.criteria if not criterion.passed}
    assert result.passed is False
    assert "customer_output_policy" in failures
    assert "execution_envelope_invariants" in failures
