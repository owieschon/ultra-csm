from __future__ import annotations

from fastapi.testclient import TestClient

from tests._govhelpers import CLOCK, T1, setup_roster
from ultra_csm import api
from ultra_csm.data_plane.contracts import (
    AdoptionSummary,
    CRMAccount,
    CRMContact,
    CSCompany,
    CustomerDataPlane,
    Entitlement,
    HealthScore,
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
from ultra_csm.self_serve_activation import (
    SelfServeSignupEvent,
    run_self_serve_signup_activation,
)


ACCOUNT_ID = det_id("account", "self-serve-team")
WORKSPACE_ID = "workspace-self-serve-team"
CONTACT_ID = det_id("contact", ACCOUNT_ID, "signup")
AS_OF = "2026-07-08"


def test_self_serve_signup_selects_team_value_path_and_gates_customer_outreach(runtime_conn):
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
        packet = run_self_serve_signup_activation(
            data_plane=_self_serve_data_plane(
                usage_metrics=("workspace_created", "invite_sent", "invited_user_activated")
            ),
            gate=gate,
            event=_signup_event(),
            as_of=AS_OF,
        )
    finally:
        runtime_conn.rollback()

    assert packet.status == "ready"
    assert packet.workflow_id == "self_serve_signup_activation"
    assert packet.workflow_config_version == "self-serve-value-path-config-v2"
    assert packet.to_dict()["workflow"]["ui"]["renderer"] == "self_serve_value_path"
    assert packet.identity_resolution.state == "exactly_one"
    assert packet.value_path.path_id == "team_workspace_creator"
    assert packet.value_path.config_version == "self-serve-value-path-config-v2"
    assert packet.value_path.first_value_milestone_id == "first_value"
    assert packet.value_path.first_value_reached is True
    assert packet.value_path.first_value_definition == (
        "The user reaches first value when at least one teammate activates and shared work exists."
    )
    milestones = {item.milestone_id: item for item in packet.value_path.milestones}
    assert milestones["invite"].status == "completed"
    assert milestones["first_value"].status == "completed"
    assert packet.recommended_action.action_type == "recommend_next_feature"
    assert packet.recommended_action.trigger == "first_value_reached_with_feature_depth_gap"
    assert packet.customer_language is not None
    assert {proposal.action_type for proposal in packet.proposals} == {"draft_customer_outreach"}
    assert "product_telemetry" in packet.coverage.reviewed_sources
    assert "salesforce_contact" in packet.coverage.reviewed_sources


def test_self_serve_first_value_is_not_inferred_from_completed_step_count(runtime_conn):
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
        packet = run_self_serve_signup_activation(
            data_plane=_self_serve_data_plane(
                usage_metrics=("workspace_created", "profile_completed", "insight_viewed", "return_session")
            ),
            gate=gate,
            event=_signup_event(),
            as_of=AS_OF,
        )
    finally:
        runtime_conn.rollback()

    assert packet.value_path.path_id == "solo_evaluator"
    completed = set(packet.value_path.completed_milestone_ids)
    assert {"signup", "setup", "habit"} <= completed
    assert "first_value" not in completed
    assert packet.value_path.first_value_reached is False


def test_self_serve_preserves_secondary_value_path_hypotheses(runtime_conn):
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
        packet = run_self_serve_signup_activation(
            data_plane=_self_serve_data_plane(
                usage_metrics=("workspace_created", "invite_sent", "invited_user_activated", "crm_connect_clicked")
            ),
            gate=gate,
            event=_signup_event(),
            as_of=AS_OF,
        )
    finally:
        runtime_conn.rollback()

    assert packet.value_path.path_id == "team_workspace_creator"
    secondary = {item.path_id: item for item in packet.value_path.secondary_hypotheses}
    assert "crm_enterprise_curious" in secondary
    assert secondary["crm_enterprise_curious"].evidence_source_ids


def test_self_serve_domain_resolution_uses_event_tenant_scope():
    tenant_account = "acct-tenant-scoped"
    decoy_account = "acct-decoy"
    data = FixtureCustomerData(
        accounts=(
            CRMAccount(tenant_account, "Tenant Scoped Co", "owner-a", "software"),
            CRMAccount(decoy_account, "Default Decoy Co", "owner-b", "software"),
        ),
        companies=(),
        contacts=(
            CRMContact("contact-tenant", tenant_account, "operator@scoped.example", "Tenant User", "operator", None, True),
            CRMContact("contact-decoy", decoy_account, "other@scoped.example", "Decoy User", "operator", None, True),
        ),
        cases=(),
        opportunities=(),
        health_scores=(),
        ctas=(),
        success_plans=(),
        adoption_summaries=(),
        entitlements=(),
        usage_signals=(),
        milestones=(),
        tenant_accounts={T1: (tenant_account,), DEFAULT_TENANT: (decoy_account,)},
    )

    packet = run_self_serve_signup_activation(
        data_plane=CustomerDataPlane(
            crm=FixtureCRMDataConnector(tenant=DEFAULT_TENANT, data=data),
            cs=FixtureCSPlatformConnector(data=data),
            telemetry=FixtureProductTelemetryConnector(data=data),
            comms=FixtureCommsConnector(data=data),
        ),
        gate=None,
        event=SelfServeSignupEvent(
            tenant_id=T1,
            workspace_id="workspace-scoped",
            signup_email="new@scoped.example",
            observed_at="2026-07-08T12:00:00Z",
        ),
        as_of=AS_OF,
    )

    assert packet.identity_resolution.state == "exactly_one"
    assert packet.account_id == tenant_account


def test_crm_interest_is_enterprise_expansion_signal_not_self_serve_connect_action(runtime_conn):
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
        packet = run_self_serve_signup_activation(
            data_plane=_self_serve_data_plane(
                usage_metrics=("workspace_created", "crm_integration_viewed", "crm_connect_clicked")
            ),
            gate=gate,
            event=_signup_event(),
            as_of=AS_OF,
        )
    finally:
        runtime_conn.rollback()

    assert packet.status == "internal_only"
    assert packet.value_path.path_id == "crm_enterprise_curious"
    assert packet.value_path.enterprise_interest_signals
    assert packet.recommended_action.action_type == "internal_only_packet"
    assert packet.recommended_action.trigger == "strong_signal_but_unsafe_customer_action"
    assert "customer_outreach_requires_sales_assisted_review" in packet.recommended_action.suppression_reasons
    assert packet.customer_language is None
    assert {proposal.action_type for proposal in packet.proposals} == {"recommend_next_best_action"}
    packet_text = str(packet.to_dict()).lower()
    assert "connect your crm" not in packet_text
    assert "enterprise" in packet_text


def test_missing_product_telemetry_blocks_activation_judgment(runtime_conn):
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
        packet = run_self_serve_signup_activation(
            data_plane=_self_serve_data_plane(usage_metrics=()),
            gate=gate,
            event=_signup_event(),
            as_of=AS_OF,
        )
    finally:
        runtime_conn.rollback()

    assert packet.status == "needs_data"
    assert "product_telemetry" in packet.coverage.missing_required_sources
    assert "product_telemetry_required_for_activation_judgment" in packet.coverage.customer_output_blockers
    assert packet.value_path.first_value_reached is False
    assert packet.customer_language is None
    assert {proposal.action_type for proposal in packet.proposals} == {"recommend_next_best_action"}


def test_personal_email_domain_suppresses_org_outreach_even_with_usage(runtime_conn):
    personal_account = det_id("account", "personal-self-serve")
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
        packet = run_self_serve_signup_activation(
            data_plane=_self_serve_data_plane(
                account_id=personal_account,
                account_name="Personal Workspace",
                signup_email="operator@gmail.com",
                usage_metrics=("workspace_created", "profile_completed", "insight_saved"),
            ),
            gate=gate,
            event=SelfServeSignupEvent(
                tenant_id=T1,
                workspace_id="workspace-personal",
                signup_email="operator@gmail.com",
                observed_at="2026-07-08T12:00:00Z",
                account_id=personal_account,
            ),
            as_of=AS_OF,
        )
    finally:
        runtime_conn.rollback()

    assert packet.identity_resolution.personal_email_domain is True
    assert packet.status == "internal_only"
    assert "personal_email_domain_suppresses_org_outreach" in packet.coverage.customer_output_blockers
    assert packet.customer_language is None
    assert {proposal.action_type for proposal in packet.proposals} == {"recommend_next_best_action"}


def test_self_serve_signup_endpoint_runs_against_served_data_plane_and_persists(monkeypatch):
    def served_self_serve_plane(**_kwargs):
        return DataPlaneAssembly(
            data_plane=_self_serve_data_plane(
                usage_metrics=("workspace_created", "invite_sent", "invited_user_activated")
            ),
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
    monkeypatch.setattr(api, "build_served_data_plane", served_self_serve_plane)

    with TestClient(api.app) as client:
        resp = client.post(
            "/integrations/self-serve/signup",
            headers={"Authorization": "Bearer lane-a-token"},
            json={
                "workspace_id": WORKSPACE_ID,
                "signup_email": "operator@selfserve.example",
                "observed_at": "2026-07-08T12:00:00Z",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        packet_id = body["packet_id"]
        stored_resp = client.get(f"/self-serve/activation/packets/{packet_id}")
        list_resp = client.get(f"/self-serve/activation/packets?workspace_id={WORKSPACE_ID}")
        ledger_resp = client.get("/ledger?limit=50")

    assert body["status"] == "ready"
    assert body["account_id"] == ACCOUNT_ID
    assert body["data_plane_mode"] == "live"
    assert body["missing_required_sources"] == []
    assert len(body["proposal_ids"]) == 1
    assert body["packet"]["value_path"]["path_id"] == "team_workspace_creator"
    assert body["packet"]["value_path"]["first_value_reached"] is True

    assert stored_resp.status_code == 200
    stored = stored_resp.json()
    assert stored["packet_id"] == packet_id
    assert stored["packet"]["workspace_id"] == WORKSPACE_ID

    assert list_resp.status_code == 200
    assert any(item["packet_id"] == packet_id for item in list_resp.json()["packets"])

    assert ledger_resp.status_code == 200
    ledger_events = {item["event"] for item in ledger_resp.json()["events"]}
    assert {
        "self_serve_activation.trigger",
        "self_serve_activation.packet",
        "self_serve_activation.value_path",
    } <= ledger_events


def _signup_event(
    *,
    workspace_id: str = WORKSPACE_ID,
    signup_email: str = "operator@selfserve.example",
    account_id: str | None = None,
) -> SelfServeSignupEvent:
    return SelfServeSignupEvent(
        tenant_id=T1,
        workspace_id=workspace_id,
        signup_email=signup_email,
        observed_at="2026-07-08T12:00:00Z",
        account_id=account_id,
    )


def _self_serve_data_plane(
    *,
    account_id: str = ACCOUNT_ID,
    account_name: str = "Self Serve Team Co",
    signup_email: str = "operator@selfserve.example",
    usage_metrics: tuple[str, ...],
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
        accounts=(
            CRMAccount(
                account_id=account_id,
                name=account_name,
                owner_id="scaled-csm",
                industry="software",
            ),
        ),
        companies=(
            CSCompany(
                company_id=account_id,
                name=account_name,
                industry="software",
                arr_cents=0,
                lifecycle_stage="adopting",
                status="Self-serve",
                original_contract_date="2026-07-08",
                renewal_date="2027-07-08",
                csm_owner_id="scaled-csm",
                current_score=55.0,
            ),
        ),
        contacts=(
            CRMContact(
                contact_id=contact_id,
                account_id=account_id,
                email=signup_email,
                name="Self Serve Operator",
                role="operator",
                title="Operations",
                consent_to_contact=True,
                org_level=4,
            ),
        ),
        cases=(),
        opportunities=(),
        health_scores=(
            HealthScore(
                account_id=account_id,
                score=55.0,
                band="yellow",
                drivers=("early_activation",),
                measured_at="2026-07-08T00:00:00Z",
            ),
        ),
        ctas=(),
        success_plans=(),
        adoption_summaries=(
            AdoptionSummary(
                account_id=account_id,
                active_users=2,
                licensed_users=5,
                active_assets=0,
                entitled_assets=0,
                adoption_rate=0.4,
                underused_capabilities=("team_workflows",),
                measured_at="2026-07-08T00:00:00Z",
            ),
        ),
        entitlements=(
            Entitlement(account_id, "self_serve_workspace", 5, "users", "2026-07-08"),
        ),
        usage_signals=usage_signals,
        milestones=(),
        tenant_accounts={DEFAULT_TENANT: (account_id,)},
    )
    return CustomerDataPlane(
        crm=FixtureCRMDataConnector(tenant=DEFAULT_TENANT, data=data),
        cs=FixtureCSPlatformConnector(data=data),
        telemetry=FixtureProductTelemetryConnector(data=data),
        comms=FixtureCommsConnector(data=data),
    )
