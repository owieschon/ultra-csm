from __future__ import annotations

from fastapi.testclient import TestClient

from tests._govhelpers import CLOCK, T1, setup_roster
from ultra_csm import api
from ultra_csm.data_plane.contracts import (
    AdoptionSummary,
    CommunicationSignal,
    CRMAccount,
    CRMContact,
    CRMOpportunity,
    CSCompany,
    CTA,
    CustomerDataPlane,
    Entitlement,
    HealthScore,
    InternalCommsNote,
    OnboardingPhase,
    OnboardingProject,
    OnboardingTask,
    StakeholderRelationship,
    SuccessPlan,
    TimeToValueMilestone,
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
from ultra_csm.data_plane.rocketlane_fixtures import (
    FixtureOnboardingConnector,
    FixtureOnboardingData,
)
from ultra_csm.data_plane.live_facade import DataPlaneAssembly
from ultra_csm.enterprise_onboarding import (
    SalesforceClosedWonEvent,
    resolve_account_by_calendar_attendee_domain,
    run_enterprise_closed_won_onboarding,
)
from ultra_csm.governance import ActionGate, FixtureVerdictSource


ACCOUNT_ID = det_id("account", "enterprise-launch")
OPPORTUNITY_ID = det_id("opportunity", ACCOUNT_ID, "new-business")
CHAMPION_ID = det_id("contact", ACCOUNT_ID, "champion")
TECH_ID = det_id("contact", ACCOUNT_ID, "technical")
SPONSOR_ID = det_id("contact", ACCOUNT_ID, "sponsor")
AS_OF = "2026-07-08"


class _GoogleCalendarProvider:
    def __init__(self, events: dict) -> None:
        self.events = events
        self.calls: list[tuple[str, str | None, str | None]] = []

    def list_events(
        self,
        account_id: str,
        *,
        opportunity_id: str | None = None,
        until: str | None = None,
    ) -> dict:
        self.calls.append((account_id, opportunity_id, until))
        return self.events


def test_enterprise_closed_won_builds_launch_packet_from_connected_sources(runtime_conn):
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
        calendar = _GoogleCalendarProvider(_calendar_events())

        packet = run_enterprise_closed_won_onboarding(
            data_plane=_enterprise_data_plane(include_context=True, include_usage=True),
            gate=gate,
            event=_closed_won_event(),
            as_of=AS_OF,
            calendar_provider=calendar,
        )
    finally:
        runtime_conn.rollback()

    assert packet.status == "ready"
    assert calendar.calls == [(ACCOUNT_ID, OPPORTUNITY_ID, AS_OF)]
    assert packet.trigger_receipt.source_type == "salesforce_opportunity"
    assert set(packet.coverage.original_success_plan_sources) >= {
        "salesforce_opportunity",
        "salesforce_account",
        "salesforce_contacts",
        "entitlements",
        "customer_email",
        "call_or_meeting_context",
        "internal_handoff_notes",
        "google_calendar",
    }
    assert "google_calendar_attendance" in packet.coverage.stakeholder_verification_sources
    assert packet.coverage.missing_required_sources == ()
    assert packet.customer_welcome_draft is not None
    assert "kickoff" in packet.customer_welcome_draft.lower()
    assert len(packet.success_plan_v0) >= 5
    integrations = {item.family: item for item in packet.customer_integrations}
    assert "mcp" in integrations
    assert "mp" not in integrations
    assert integrations["mcp"].label == "MCP"
    assert integrations["crm"].status == "configured"
    assert integrations["crm"].provider == "salesforce"
    assert integrations["email"].status == "observed"
    assert integrations["calendar"].status == "observed"
    assert integrations["calendar"].provider == "google_calendar"
    assert integrations["calls"].status == "observed"
    assert "gong" in integrations["calls"].provider_options
    assert "grain" in integrations["calls"].provider_options
    assert integrations["sequences"].provider_options == ("outreach", "gong_engage")
    assert any(receipt.source_type == "google_calendar_event" for receipt in packet.source_receipts)
    assert any(
        row.person_key == "it.owner@enterprise-launch.example"
        and row.verification_state == "declared_and_observed"
        and "google_calendar:attendee" in row.observed_sources
        for row in packet.stakeholder_verification
    )
    assert any(
        row.person_key == "procurement@enterprise-launch.example"
        and row.verification_state == "observed_missing_from_crm"
        for row in packet.stakeholder_verification
    )
    assert {proposal.action_type for proposal in packet.proposals} == {
        "draft_customer_outreach",
        "edit_success_plan",
    }


def test_enterprise_closed_won_stops_before_customer_output_when_context_missing(runtime_conn):
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
        packet = run_enterprise_closed_won_onboarding(
            data_plane=_enterprise_data_plane(include_context=False, include_usage=False),
            gate=gate,
            event=_closed_won_event(),
            as_of=AS_OF,
            calendar_provider=_GoogleCalendarProvider({"items": []}),
        )
    finally:
        runtime_conn.rollback()

    assert packet.status == "needs_data"
    assert "sales_or_customer_context" in packet.coverage.missing_required_sources
    assert "customer_facing_email_call_or_calendar_context" in packet.coverage.missing_required_sources
    assert "product_tenant_or_provisioning_state" in packet.coverage.missing_required_sources
    assert packet.customer_welcome_draft is None
    assert packet.proposals == ()
    assert packet.recommended_next_action == (
        "Complete missing onboarding evidence before customer-facing activity."
    )


def test_non_enterprise_closed_won_event_is_ignored():
    data_plane = _enterprise_data_plane(include_context=True, include_usage=True, amount_cents=2_500_000)
    packet = run_enterprise_closed_won_onboarding(
        data_plane=data_plane,
        gate=None,
        event=_closed_won_event(),
        as_of=AS_OF,
        calendar_provider=_GoogleCalendarProvider(_calendar_events()),
    )

    assert packet.status == "ignored"
    assert packet.proposals == ()
    assert packet.customer_welcome_draft is None
    assert "not enterprise-sized" in packet.recommended_next_action.lower() or packet.risks


def test_calendar_domain_resolution_does_not_pick_ambiguous_customer_domain():
    account_a = CRMAccount("acct-a", "Shared Domain North", "owner-a", "software")
    account_b = CRMAccount("acct-b", "Shared Domain South", "owner-b", "software")
    data = FixtureCustomerData(
        accounts=(account_a, account_b),
        companies=(),
        contacts=(
            CRMContact("contact-a", "acct-a", "admin@shared.example", "Admin A", "admin", None, True),
            CRMContact("contact-b", "acct-b", "it@shared.example", "IT B", "technical", None, True),
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
        tenant_accounts={DEFAULT_TENANT: ("acct-a", "acct-b")},
    )

    resolution = resolve_account_by_calendar_attendee_domain(
        FixtureCRMDataConnector(tenant=DEFAULT_TENANT, data=data),
        {
            "items": [{
                "id": "cal-1",
                "status": "confirmed",
                "attendees": [{"email": "buyer@shared.example", "responseStatus": "accepted"}],
            }],
        },
        tenant_id=DEFAULT_TENANT,
    )

    assert resolution.state == "ambiguous"
    assert resolution.account_id is None
    assert resolution.candidate_account_ids == ("acct-a", "acct-b")


def test_salesforce_closed_won_endpoint_runs_workflow_against_served_data_plane(monkeypatch):
    def served_enterprise_plane(**_kwargs):
        return DataPlaneAssembly(
            data_plane=_enterprise_data_plane(include_context=True, include_usage=True),
            mode="live",
            source_status={
                "salesforce": "live",
                "rocketlane": "fixture",
                "gmail": "fixture_or_persisted",
                "google_calendar": "request_events_list",
            },
            health_source="derived_from_live_sources",
        )

    monkeypatch.setenv("ULTRA_CSM_API_TOKENS", "lane-a-token:Lane A Manager")
    monkeypatch.delenv("ULTRA_CSM_DEMO_NOAUTH", raising=False)
    monkeypatch.setattr(api, "build_served_data_plane", served_enterprise_plane)

    with TestClient(api.app) as client:
        resp = client.post(
            "/integrations/salesforce/opportunity-closed-won",
            headers={"Authorization": "Bearer lane-a-token"},
            json={
                "opportunity_id": OPPORTUNITY_ID,
                "stage_name": "Closed Won",
                "observed_at": "2026-07-08T12:00:00Z",
                "google_calendar_events": _calendar_events(),
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["account_id"] == ACCOUNT_ID
    assert body["data_plane_mode"] == "live"
    assert body["missing_required_sources"] == []
    assert len(body["proposal_ids"]) == 2
    assert body["calendar_account_resolution"]["state"] == "exactly_one"
    assert body["calendar_account_resolution"]["account_id"] == ACCOUNT_ID
    assert body["calendar_account_resolution"]["matched_domains"] == ["enterprise-launch.example"]
    packet = body["packet"]
    api_integrations = {item["family"]: item for item in packet["customer_integrations"]}
    assert api_integrations["crm"]["provider"] == "salesforce"
    assert api_integrations["calendar"]["provider"] == "google_calendar"
    assert api_integrations["calls"]["provider_options"] == [
        "gong",
        "salesloft",
        "clari_copilot",
        "avoma",
        "chorus",
        "fathom",
        "granola",
        "attention",
        "fireflies",
        "grain",
    ]
    assert api_integrations["sequences"]["provider_options"] == ["outreach", "gong_engage"]
    assert "google_calendar" in packet["coverage"]["original_success_plan_sources"]
    assert "google_calendar_attendance" in packet["coverage"]["stakeholder_verification_sources"]
    assert any(
        row["person_key"] == "procurement@enterprise-launch.example"
        and row["verification_state"] == "observed_missing_from_crm"
        for row in packet["stakeholder_verification"]
    )


def _closed_won_event() -> SalesforceClosedWonEvent:
    return SalesforceClosedWonEvent(
        tenant_id=T1,
        opportunity_id=OPPORTUNITY_ID,
        account_id=ACCOUNT_ID,
        stage_name="Closed Won",
        observed_at="2026-07-08T12:00:00Z",
    )


def _enterprise_data_plane(
    *,
    include_context: bool,
    include_usage: bool,
    amount_cents: int = 18_000_000,
) -> CustomerDataPlane:
    account = CRMAccount(
        account_id=ACCOUNT_ID,
        name="Enterprise Launch Co",
        owner_id="csm-enterprise",
        industry="software",
    )
    champion = CRMContact(
        CHAMPION_ID,
        ACCOUNT_ID,
        "champion@enterprise-launch.example",
        "Ari Champion",
        "champion",
        "RevOps Lead",
        True,
    )
    technical = CRMContact(
        TECH_ID,
        ACCOUNT_ID,
        "it.owner@enterprise-launch.example",
        "Theo Technical",
        "technical_lead",
        "IT Owner",
        True,
    )
    sponsor = CRMContact(
        SPONSOR_ID,
        ACCOUNT_ID,
        "sponsor@enterprise-launch.example",
        "Evan Sponsor",
        "executive_sponsor",
        "VP Sales",
        True,
    )
    opportunity = CRMOpportunity(
        OPPORTUNITY_ID,
        ACCOUNT_ID,
        "Closed Won",
        amount_cents,
        "2026-07-08",
        "New Business",
    )
    signals = (
        UsageSignal(
            det_id("signal", ACCOUNT_ID, "workspace_provisioned"),
            ACCOUNT_ID,
            "company",
            None,
            "workspace_provisioned",
            1.0,
            "boolean",
            "2026-07-08T12:30:00Z",
            "product:workspace",
        ),
    ) if include_usage else ()
    comms = (
        CommunicationSignal(
            det_id("email", ACCOUNT_ID, "champion"),
            ACCOUNT_ID,
            CHAMPION_ID,
            "email",
            "inbound",
            "2026-07-07T16:00:00Z",
            2.0,
            ("champion@enterprise-launch.example",),
        ),
        CommunicationSignal(
            det_id("call", ACCOUNT_ID, "handoff"),
            ACCOUNT_ID,
            SPONSOR_ID,
            "call",
            "inbound",
            "2026-07-06T17:00:00Z",
            None,
            ("sponsor@enterprise-launch.example", "it.owner@enterprise-launch.example"),
        ),
    ) if include_context else ()
    notes = (
        InternalCommsNote(
            det_id("note", ACCOUNT_ID, "handoff"),
            ACCOUNT_ID,
            "ae-1",
            "2026-07-07T18:00:00Z",
            "Customer wants first value in the first enterprise pipeline review.",
            "csm_note",
        ),
    ) if include_context else ()
    data = FixtureCustomerData(
        accounts=(account,),
        companies=(
            CSCompany(
                ACCOUNT_ID,
                account.name,
                account.industry,
                amount_cents,
                "onboarding",
                "Active",
                "2026-07-08",
                "2027-07-08",
                "csm-enterprise",
                70.0,
            ),
        ),
        contacts=(champion, technical, sponsor),
        cases=(),
        opportunities=(opportunity,),
        health_scores=(
            HealthScore(ACCOUNT_ID, 70.0, "green", ("new_customer",), "2026-07-08T12:00:00Z"),
        ),
        ctas=(
            CTA(
                det_id("cta", ACCOUNT_ID, "kickoff"),
                ACCOUNT_ID,
                "Schedule enterprise kickoff",
                "High",
                "open",
                "2026-07-12",
                "csm-enterprise",
            ),
        ),
        success_plans=(
            SuccessPlan(
                det_id("plan", ACCOUNT_ID, "launch"),
                ACCOUNT_ID,
                "draft",
                ("launch_relationship_intelligence",),
                "2026-08-01",
            ),
        ),
        adoption_summaries=(
            AdoptionSummary(ACCOUNT_ID, 0, 75, 0, 75, 0.0, ("relationship_maps",), "2026-07-08"),
        ),
        entitlements=(
            Entitlement(ACCOUNT_ID, "relationship_maps", 75, "seats", "2026-07-08"),
            Entitlement(ACCOUNT_ID, "deal_review_workflows", 75, "seats", "2026-07-08"),
        ),
        usage_signals=signals,
        milestones=(
            TimeToValueMilestone(
                ACCOUNT_ID,
                "first_relationship_map",
                "2026-07-22",
                None,
                (det_id("signal", ACCOUNT_ID, "workspace_provisioned"),),
            ),
        ),
        tenant_accounts={DEFAULT_TENANT: (ACCOUNT_ID,)},
        stakeholder_relationships=(
            StakeholderRelationship(ACCOUNT_ID, CHAMPION_ID, "champion", "strong", "2026-07-07", 2),
            StakeholderRelationship(ACCOUNT_ID, TECH_ID, "technical_lead", "moderate", "2026-07-06", 2),
            StakeholderRelationship(ACCOUNT_ID, SPONSOR_ID, "executive_sponsor", "strong", "2026-07-06", 3),
        ),
        communication_signals=comms,
        internal_notes=notes,
    )
    onboarding = FixtureOnboardingConnector(
        data=FixtureOnboardingData(
            projects=(
                OnboardingProject(
                    det_id("project", ACCOUNT_ID, "launch"),
                    ACCOUNT_ID,
                    "Enterprise Launch Co onboarding",
                    1,
                    "Not started",
                    "csm-enterprise",
                    "on_track",
                    "2026-07-08",
                    None,
                    "2026-08-01",
                    None,
                    amount_cents,
                ),
            ),
            phases=(
                OnboardingPhase(
                    det_id("phase", ACCOUNT_ID, "kickoff"),
                    det_id("project", ACCOUNT_ID, "launch"),
                    "Kickoff and implementation design",
                    "2026-07-08",
                    None,
                    "2026-07-15",
                    None,
                    "Not started",
                    False,
                ),
            ),
            tasks=(
                OnboardingTask(
                    det_id("task", ACCOUNT_ID, "admin"),
                    det_id("project", ACCOUNT_ID, "launch"),
                    det_id("phase", ACCOUNT_ID, "kickoff"),
                    "Confirm admin and technical owner",
                    "Not started",
                    "2026-07-08",
                    "2026-07-12",
                    None,
                    False,
                    ("csm-enterprise",),
                ),
            ),
        )
    )
    return CustomerDataPlane(
        crm=FixtureCRMDataConnector(tenant=DEFAULT_TENANT, data=data),
        cs=FixtureCSPlatformConnector(data=data),
        telemetry=FixtureProductTelemetryConnector(data=data),
        onboarding=onboarding,
        comms=FixtureCommsConnector(data=data),
    )


def _calendar_events() -> dict:
    return {
        "items": [
            {
                "id": det_id("calendar-event", ACCOUNT_ID, "technical-validation"),
                "summary": "Enterprise Launch Co technical validation",
                "start": {"dateTime": "2026-07-06T17:00:00Z"},
                "end": {"dateTime": "2026-07-06T17:30:00Z"},
                "status": "confirmed",
                "attendees": [
                    {"email": "csm@centralize.example", "responseStatus": "accepted"},
                    {"email": "it.owner@enterprise-launch.example", "responseStatus": "accepted"},
                    {"email": "sponsor@enterprise-launch.example", "responseStatus": "accepted"},
                    {"email": "procurement@enterprise-launch.example", "responseStatus": "accepted"},
                ],
            }
        ]
    }
