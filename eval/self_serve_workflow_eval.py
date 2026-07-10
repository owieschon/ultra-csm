"""Deterministic self-serve activation workflow eval.

This is not a golden-label judge. It proves falsifiable workflow behavior:
identity handling, all-available-source review, explicit value-path milestones,
governance suppression, and execution-envelope invariants.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from typing import Any

from ultra_csm.data_plane.contracts import (
    AdoptionSummary,
    CommunicationSignal,
    CRMAccount,
    CRMContact,
    CSCompany,
    CustomerDataPlane,
    Entitlement,
    HealthScore,
    InternalCommsNote,
    UsageSignal,
)
from ultra_csm.data_plane.fixtures import (
    DEFAULT_TENANT,
    FixtureCRMDataConnector,
    FixtureCSPlatformConnector,
    FixtureCommsConnector,
    FixtureCustomerData,
    FixtureProductTelemetryConnector,
    det_id,
)
from ultra_csm.self_serve_activation import (
    SelfServeActivationPacket,
    SelfServeSignupEvent,
    run_self_serve_signup_activation,
)
from ultra_csm.workflow_core import invariant_failures
from ultra_csm.workflow_playbooks import (
    ACCOUNT_ADOPTION_REGRESSION,
    ENTERPRISE_CLOSED_WON_ONBOARDING,
    SELF_SERVE_SIGNUP_ACTIVATION,
)


AS_OF = "2026-07-08"
ACCOUNT_ID = det_id("account", "self-serve-eval")
WORKSPACE_ID = "workspace-self-serve-eval"


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    passed: bool
    checks: tuple[str, ...]
    failures: tuple[str, ...]
    packet_summary: dict[str, Any]


@dataclass(frozen=True)
class SelfServeWorkflowEvalReport:
    artifact: str
    workflow_id: str
    validation_status: str
    dormant_verticals: tuple[str, ...]
    scenario_count: int
    passed: bool
    scenarios: tuple[ScenarioResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_eval() -> SelfServeWorkflowEvalReport:
    scenarios = (
        _team_first_value(),
        _count_is_not_first_value(),
        _crm_interest_is_internal(),
        _missing_telemetry_abstains(),
        _personal_email_suppresses_outreach(),
        _reviews_all_available_sources(),
    )
    return SelfServeWorkflowEvalReport(
        artifact="self_serve_workflow_eval",
        workflow_id=SELF_SERVE_SIGNUP_ACTIVATION.workflow_id,
        validation_status=SELF_SERVE_SIGNUP_ACTIVATION.validation_status,
        dormant_verticals=(
            ENTERPRISE_CLOSED_WON_ONBOARDING.workflow_id,
            ACCOUNT_ADOPTION_REGRESSION.workflow_id,
        ),
        scenario_count=len(scenarios),
        passed=all(scenario.passed for scenario in scenarios),
        scenarios=scenarios,
    )


def _team_first_value() -> ScenarioResult:
    packet = _packet("team-first-value", ("workspace_created", "invite_sent", "invited_user_activated"))
    return _scenario(
        "team_first_value",
        packet,
        {
            "path_is_team": packet.value_path.path_id == "team_workspace_creator",
            "first_value_true": packet.value_path.first_value_reached is True,
            "first_value_milestone_completed": "first_value" in packet.value_path.completed_milestone_ids,
            "action_is_depth": packet.recommended_action.action_type == "recommend_next_feature",
            "invariants_hold": invariant_failures(packet.execution_envelope) == (),
        },
    )


def _count_is_not_first_value() -> ScenarioResult:
    packet = _packet(
        "count-is-not-first-value",
        ("workspace_created", "profile_completed", "insight_viewed", "return_session"),
    )
    return _scenario(
        "count_is_not_first_value",
        packet,
        {
            "path_is_solo": packet.value_path.path_id == "solo_evaluator",
            "many_steps_do_not_complete_first_value": packet.value_path.first_value_reached is False,
            "first_value_milestone_not_completed": "first_value" not in packet.value_path.completed_milestone_ids,
            "validation_names_first_value_rule": any(
                item.check_name == "first_value_not_inferred_from_count" and item.passed
                for item in packet.execution_envelope.validations
            ),
            "invariants_hold": invariant_failures(packet.execution_envelope) == (),
        },
    )


def _crm_interest_is_internal() -> ScenarioResult:
    packet = _packet(
        "crm-interest",
        ("workspace_created", "crm_integration_viewed", "crm_connect_clicked", "champion_invited"),
    )
    return _scenario(
        "crm_interest_is_internal",
        packet,
        {
            "path_is_crm_enterprise_interest": packet.value_path.path_id == "crm_enterprise_curious",
            "crm_not_self_serve_connect_action": packet.recommended_action.action_type == "internal_only_packet",
            "customer_language_suppressed": packet.customer_language is None,
            "sales_assisted_review_required": (
                "customer_outreach_requires_sales_assisted_review"
                in packet.recommended_action.suppression_reasons
            ),
            "invariants_hold": invariant_failures(packet.execution_envelope) == (),
        },
    )


def _missing_telemetry_abstains() -> ScenarioResult:
    packet = _packet("missing-telemetry", ())
    return _scenario(
        "missing_telemetry_abstains",
        packet,
        {
            "status_needs_data": packet.status == "needs_data",
            "does_not_claim_first_value": packet.value_path.first_value_reached is False,
            "telemetry_missing_visible": "product_telemetry" in packet.coverage.missing_required_sources,
            "customer_language_suppressed": packet.customer_language is None,
            "invariants_hold": invariant_failures(packet.execution_envelope) == (),
        },
    )


def _personal_email_suppresses_outreach() -> ScenarioResult:
    packet = _packet(
        "personal-email",
        ("workspace_created", "profile_completed", "insight_saved"),
        signup_email="operator@gmail.com",
        account_id=det_id("account", "self-serve-personal-eval"),
    )
    return _scenario(
        "personal_email_suppresses_outreach",
        packet,
        {
            "personal_domain_detected": packet.identity_resolution.personal_email_domain is True,
            "customer_language_suppressed": packet.customer_language is None,
            "org_outreach_blocker_visible": (
                "personal_email_domain_suppresses_org_outreach"
                in packet.coverage.customer_output_blockers
            ),
            "invariants_hold": invariant_failures(packet.execution_envelope) == (),
        },
    )


def _reviews_all_available_sources() -> ScenarioResult:
    packet = _packet(
        "all-sources",
        ("workspace_created", "invite_sent"),
        include_comms=True,
    )
    reviewed = set(packet.coverage.reviewed_sources)
    return _scenario(
        "reviews_all_available_sources",
        packet,
        {
            "telemetry_reviewed": "product_telemetry" in reviewed,
            "entitlement_reviewed": "entitlement" in reviewed,
            "adoption_reviewed": "adoption_summary" in reviewed,
            "customer_email_reviewed": "customer_email" in reviewed,
            "call_transcript_reviewed": "call_transcript" in reviewed,
            "internal_note_reviewed": "internal_slack_or_note" in reviewed,
            "contact_reviewed": "contact_record" in reviewed,
            "invariants_hold": invariant_failures(packet.execution_envelope) == (),
        },
    )


def _scenario(
    scenario_id: str,
    packet: SelfServeActivationPacket,
    checks: dict[str, bool],
) -> ScenarioResult:
    failures = tuple(name for name, passed in checks.items() if not passed)
    return ScenarioResult(
        scenario_id=scenario_id,
        passed=not failures,
        checks=tuple(checks),
        failures=failures,
        packet_summary={
            "status": packet.status,
            "path_id": packet.value_path.path_id,
            "first_value_reached": packet.value_path.first_value_reached,
            "recommended_action": packet.recommended_action.action_type,
            "reviewed_sources": list(packet.coverage.reviewed_sources),
            "missing_required_sources": list(packet.coverage.missing_required_sources),
            "customer_output_blockers": list(packet.coverage.customer_output_blockers),
        },
    )


def _packet(
    suffix: str,
    usage_metrics: tuple[str, ...],
    *,
    signup_email: str = "operator@selfserve.example",
    account_id: str = ACCOUNT_ID,
    include_comms: bool = False,
) -> SelfServeActivationPacket:
    return run_self_serve_signup_activation(
        data_plane=_data_plane(
            account_id=account_id,
            signup_email=signup_email,
            usage_metrics=usage_metrics,
            include_comms=include_comms,
        ),
        gate=None,
        event=SelfServeSignupEvent(
            tenant_id=DEFAULT_TENANT,
            workspace_id=f"{WORKSPACE_ID}-{suffix}",
            signup_email=signup_email,
            observed_at="2026-07-08T12:00:00Z",
            account_id=account_id,
        ),
        as_of=AS_OF,
    )


def _data_plane(
    *,
    account_id: str,
    signup_email: str,
    usage_metrics: tuple[str, ...],
    include_comms: bool,
) -> CustomerDataPlane:
    contact_id = det_id("contact", account_id, "signup")
    usage_signals = tuple(
        UsageSignal(
            signal_id=det_id("signal", account_id, metric, "2026-07-08"),
            account_id=account_id,
            grain="company",
            subject_id=None,
            metric_name=metric,
            value=1.0,
            unit="event",
            observed_at="2026-07-08T12:00:00Z",
            source_ref=f"product-telemetry:{metric}",
        )
        for metric in usage_metrics
    )
    data = FixtureCustomerData(
        accounts=(CRMAccount(account_id, "Self Serve Eval Co", "scaled-csm", "software"),),
        companies=(
            CSCompany(
                account_id,
                "Self Serve Eval Co",
                "software",
                0,
                "adopting",
                "Self-serve",
                "2026-07-08",
                "2027-07-08",
                "scaled-csm",
                55.0,
            ),
        ),
        contacts=(
            CRMContact(
                contact_id,
                account_id,
                signup_email,
                "Self Serve Operator",
                "operator",
                "Operations",
                True,
                4,
            ),
        ),
        cases=(),
        opportunities=(),
        health_scores=(
            HealthScore(account_id, 55.0, "yellow", ("early_activation",), "2026-07-08T00:00:00Z"),
        ),
        ctas=(),
        success_plans=(),
        adoption_summaries=(
            AdoptionSummary(account_id, 2, 5, 0, 0, 0.4, ("team_workflows",), "2026-07-08T00:00:00Z"),
        ),
        entitlements=(
            Entitlement(account_id, "self_serve_workspace", 5, "users", "2026-07-08"),
        ),
        usage_signals=usage_signals,
        milestones=(),
        tenant_accounts={DEFAULT_TENANT: (account_id,)},
        communication_signals=_communication_signals(account_id, contact_id) if include_comms else (),
        internal_notes=(
            InternalCommsNote(
                det_id("internal-note", account_id, "signup-intent"),
                account_id,
                "scaled-csm",
                "2026-07-08T11:00:00Z",
                "Signup intent mentions team workflow evaluation.",
                "slack",
            ),
        ) if include_comms else (),
    )
    return CustomerDataPlane(
        crm=FixtureCRMDataConnector(tenant=DEFAULT_TENANT, data=data),
        cs=FixtureCSPlatformConnector(data=data),
        telemetry=FixtureProductTelemetryConnector(data=data),
        comms=FixtureCommsConnector(data=data),
    )


def _communication_signals(account_id: str, contact_id: str) -> tuple[CommunicationSignal, ...]:
    return (
        CommunicationSignal(
            det_id("comm", account_id, "email"),
            account_id,
            contact_id,
            "email",
            "inbound",
            "2026-07-08T10:00:00Z",
        ),
        CommunicationSignal(
            det_id("comm", account_id, "call"),
            account_id,
            contact_id,
            "call",
            "inbound",
            "2026-07-08T10:30:00Z",
            attendees=("operator@selfserve.example", "scaled-csm@example.com"),
        ),
    )


def main() -> int:
    report = run_eval()
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
