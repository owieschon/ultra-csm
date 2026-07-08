from __future__ import annotations

from fastapi.testclient import TestClient

from tests._govhelpers import CLOCK, T1, setup_roster
from ultra_csm import api
from ultra_csm.adoption_regression import (
    ProductUsageRegressionEvent,
    run_account_adoption_regression,
)
from ultra_csm.data_plane.contracts import (
    AdoptionSummary,
    CommunicationSignal,
    CRMAccount,
    CRMCase,
    CRMContact,
    CSCompany,
    CTA,
    CustomerDataPlane,
    Entitlement,
    HealthScore,
    InternalCommsNote,
    SuccessPlan,
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
from ultra_csm.data_plane.live_facade import DataPlaneAssembly
from ultra_csm.governance import ActionGate, FixtureVerdictSource
from ultra_csm.workflow_core import invariant_failures


ACCOUNT_ID = det_id("account", "adoption-regression")
CONTACT_ID = det_id("contact", ACCOUNT_ID, "champion")
AS_OF = "2026-07-08"


def test_adoption_regression_compares_windows_and_gates_customer_outreach(runtime_conn):
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
            as_of=AS_OF,
        )
    finally:
        runtime_conn.rollback()

    assert packet.status == "ready"
    assert packet.workflow_id == "account_adoption_regression"
    assert packet.workflow_config_version == "account-adoption-regression-config-v1"
    assert packet.to_dict()["workflow"]["ui"]["renderer"] == "adoption_regression_review"
    assert packet.execution_envelope.workflow_id == packet.workflow_id
    assert invariant_failures(packet.execution_envelope) == ()
    primary = packet.metric_comparisons[0]
    assert primary.metric_name == "weekly_active_users"
    assert primary.baseline_value == 79
    assert primary.current_value == 31
    assert primary.drop_ratio > 0.60
    assert primary.severity == "severe"
    assert packet.value_context is not None
    assert packet.value_context.lifecycle_stage == "adopting"
    assert packet.value_context.active_users == 31
    assert packet.value_context.licensed_users == 80
    assert packet.value_context.underused_capabilities == ("route_optimization",)
    assert packet.contributing_context.support_pressure == "high"
    assert packet.interpretation.selected_hypothesis == "usage_regression_with_support_friction"
    assert "telemetry_noise_or_seasonality" in packet.interpretation.alternatives
    assert packet.recommended_action.action_type == "draft_regression_review_outreach"
    assert packet.recommended_action.trigger == "source_backed_regression_with_safe_contact"
    assert packet.customer_language is not None
    assert {proposal.action_type for proposal in packet.proposals} == {"draft_customer_outreach"}


def test_adoption_regression_blocks_customer_output_without_current_window(runtime_conn):
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
            data_plane=_regression_data_plane(include_current=False),
            gate=gate,
            event=_regression_event(),
            as_of=AS_OF,
        )
    finally:
        runtime_conn.rollback()

    assert packet.status == "needs_data"
    assert "current_usage_window" in packet.coverage.missing_required_sources
    assert "current_usage_window_missing" in packet.coverage.customer_output_blockers
    assert packet.customer_language is None
    assert packet.recommended_action.action_type == "recommend_internal_review"
    assert {proposal.action_type for proposal in packet.proposals} == {"recommend_next_best_action"}
    proposed_customer_outputs = [
        output for output in packet.execution_envelope.outputs
        if output.customer_affecting and output.status == "proposed"
    ]
    assert proposed_customer_outputs == []


def test_adoption_regression_api_trigger_persists_packet_and_ledger(
    runtime_conn,
    monkeypatch,
):
    def served_regression_plane(**_kwargs):
        return DataPlaneAssembly(
            data_plane=_regression_data_plane(),
            mode="live",
            source_status={
                "salesforce": "live",
                "product_telemetry": "live",
                "gainsight": "fixture",
            },
            health_source="fixture_cs_platform",
        )

    monkeypatch.setenv("ULTRA_CSM_API_TOKENS", "lane-a-token:Lane A Manager")
    monkeypatch.delenv("ULTRA_CSM_DEMO_NOAUTH", raising=False)
    monkeypatch.setattr(api, "build_served_data_plane", served_regression_plane)

    with TestClient(api.app) as client:
        resp = client.post(
            "/integrations/product/adoption-regression",
            headers={"Authorization": "Bearer lane-a-token"},
            json={
                "account_id": ACCOUNT_ID,
                "metric_name": "weekly_active_users",
                "baseline_start": "2026-06-01T00:00:00Z",
                "baseline_end": "2026-06-15T23:59:59Z",
                "current_start": "2026-07-01T00:00:00Z",
                "current_end": "2026-07-08T23:59:59Z",
                "observed_at": "2026-07-08T12:00:00Z",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        packet_id = body["packet_id"]
        stored_resp = client.get(f"/adoption-regression/packets/{packet_id}")
        list_resp = client.get(f"/adoption-regression/packets?account_id={ACCOUNT_ID}")
        ledger_resp = client.get("/ledger?limit=80")

    assert body["status"] == "ready"
    assert body["account_id"] == ACCOUNT_ID
    assert body["metric_name"] == "weekly_active_users"
    assert body["data_plane_mode"] == "live"
    assert body["missing_required_sources"] == []
    assert len(body["proposal_ids"]) == 1
    assert body["packet"]["interpretation"]["selected_hypothesis"] == "usage_regression_with_support_friction"
    assert body["packet"]["execution_envelope"]["workflow_id"] == "account_adoption_regression"

    assert stored_resp.status_code == 200
    stored = stored_resp.json()
    assert stored["packet_id"] == packet_id
    assert stored["packet"]["metric_comparisons"][0]["metric_name"] == "weekly_active_users"

    assert list_resp.status_code == 200
    assert any(item["packet_id"] == packet_id for item in list_resp.json()["packets"])

    assert ledger_resp.status_code == 200
    ledger_events = {item["event"] for item in ledger_resp.json()["events"]}
    assert {
        "adoption_regression.trigger",
        "adoption_regression.packet",
        "adoption_regression.interpretation",
    } <= ledger_events


def _regression_event() -> ProductUsageRegressionEvent:
    return ProductUsageRegressionEvent(
        tenant_id=T1,
        account_id=ACCOUNT_ID,
        metric_name="weekly_active_users",
        baseline_start="2026-06-01T00:00:00Z",
        baseline_end="2026-06-15T23:59:59Z",
        current_start="2026-07-01T00:00:00Z",
        current_end="2026-07-08T23:59:59Z",
        observed_at="2026-07-08T12:00:00Z",
    )


def _regression_data_plane(*, include_current: bool = True) -> CustomerDataPlane:
    account = CRMAccount(
        account_id=ACCOUNT_ID,
        name="Regression Freight Co",
        owner_id="csm-regression",
        industry="transportation",
    )
    usage = [
        UsageSignal(
            det_id("signal", ACCOUNT_ID, "wau", "2026-06-03"),
            ACCOUNT_ID,
            "company",
            None,
            "weekly_active_users",
            80,
            "users",
            "2026-06-03T00:00:00Z",
            "product:weekly_active_users",
        ),
        UsageSignal(
            det_id("signal", ACCOUNT_ID, "wau", "2026-06-12"),
            ACCOUNT_ID,
            "company",
            None,
            "weekly_active_users",
            78,
            "users",
            "2026-06-12T00:00:00Z",
            "product:weekly_active_users",
        ),
        UsageSignal(
            det_id("signal", ACCOUNT_ID, "routes", "2026-06-12"),
            ACCOUNT_ID,
            "company",
            None,
            "route_optimization_trips",
            420,
            "trips",
            "2026-06-12T00:00:00Z",
            "product:route_optimization_trips",
        ),
    ]
    if include_current:
        usage.extend([
            UsageSignal(
                det_id("signal", ACCOUNT_ID, "wau", "2026-07-03"),
                ACCOUNT_ID,
                "company",
                None,
                "weekly_active_users",
                32,
                "users",
                "2026-07-03T00:00:00Z",
                "product:weekly_active_users",
            ),
            UsageSignal(
                det_id("signal", ACCOUNT_ID, "wau", "2026-07-07"),
                ACCOUNT_ID,
                "company",
                None,
                "weekly_active_users",
                30,
                "users",
                "2026-07-07T00:00:00Z",
                "product:weekly_active_users",
            ),
            UsageSignal(
                det_id("signal", ACCOUNT_ID, "routes", "2026-07-07"),
                ACCOUNT_ID,
                "company",
                None,
                "route_optimization_trips",
                180,
                "trips",
                "2026-07-07T00:00:00Z",
                "product:route_optimization_trips",
            ),
        ])
    data = FixtureCustomerData(
        accounts=(account,),
        companies=(
            CSCompany(
                company_id=ACCOUNT_ID,
                name=account.name,
                industry="transportation",
                arr_cents=12_500_000,
                lifecycle_stage="adopting",
                status="Active",
                original_contract_date="2026-03-01",
                renewal_date="2027-03-01",
                csm_owner_id="csm-regression",
                current_score=49.0,
            ),
        ),
        contacts=(
            CRMContact(
                contact_id=CONTACT_ID,
                account_id=ACCOUNT_ID,
                email="champion@regression-freight.example",
                name="Riley Morgan",
                role="operations",
                title="VP Operations",
                consent_to_contact=True,
                org_level=2,
            ),
        ),
        cases=(
            CRMCase(
                case_id=det_id("case", ACCOUNT_ID, "sync-failure"),
                account_id=ACCOUNT_ID,
                status="Open",
                priority="High",
                origin="Email",
                subject="Dispatch sync failures blocking route review",
                created_at="2026-07-02T10:00:00Z",
            ),
        ),
        opportunities=(),
        health_scores=(
            HealthScore(
                account_id=ACCOUNT_ID,
                score=49.0,
                band="yellow",
                drivers=("usage_decline", "open_high_priority_case"),
                measured_at="2026-07-08T00:00:00Z",
            ),
        ),
        ctas=(
            CTA(
                cta_id=det_id("cta", ACCOUNT_ID, "usage-review"),
                account_id=ACCOUNT_ID,
                reason="Usage regression review",
                priority="High",
                status="open",
                due_date="2026-07-10",
                owner_id="csm-regression",
            ),
        ),
        success_plans=(
            SuccessPlan(
                plan_id=det_id("success-plan", ACCOUNT_ID, "route-adoption"),
                account_id=ACCOUNT_ID,
                status="active",
                objectives=("recover_route_review_cadence", "expand_dispatcher_usage"),
                target_date="2026-08-01",
            ),
        ),
        adoption_summaries=(
            AdoptionSummary(
                account_id=ACCOUNT_ID,
                active_users=31,
                licensed_users=80,
                active_assets=42,
                entitled_assets=100,
                adoption_rate=0.39,
                underused_capabilities=("route_optimization",),
                measured_at="2026-07-08T00:00:00Z",
            ),
        ),
        entitlements=(
            Entitlement(ACCOUNT_ID, "route_optimization", 80, "users", "2026-03-01"),
            Entitlement(ACCOUNT_ID, "dispatch_sync", 100, "assets", "2026-03-01"),
        ),
        usage_signals=tuple(usage),
        milestones=(),
        tenant_accounts={DEFAULT_TENANT: (ACCOUNT_ID,)},
        communication_signals=(
            CommunicationSignal(
                signal_id=det_id("email", ACCOUNT_ID, "usage-drop"),
                account_id=ACCOUNT_ID,
                contact_id=CONTACT_ID,
                channel="email",
                direction="inbound",
                timestamp="2026-07-06T14:00:00Z",
            ),
        ),
        internal_notes=(
            InternalCommsNote(
                note_id=det_id("note", ACCOUNT_ID, "support-context"),
                account_id=ACCOUNT_ID,
                author="csm-regression",
                timestamp="2026-07-06T15:00:00Z",
                content="Champion says dispatch sync failures are reducing route review usage.",
                source="csm_note",
            ),
        ),
    )
    return CustomerDataPlane(
        crm=FixtureCRMDataConnector(tenant=DEFAULT_TENANT, data=data),
        cs=FixtureCSPlatformConnector(data=data),
        telemetry=FixtureProductTelemetryConnector(data=data),
        comms=FixtureCommsConnector(data=data),
    )
