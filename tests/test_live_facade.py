from __future__ import annotations

import pytest

from eval.salesforce_simulated_onboarding import (
    API_VERSION,
    BASE_URL,
    FakeSalesforceClient,
    build_salesforce_fixture_payloads,
)
from ultra_csm.data_plane.contracts import (
    CRMAccount,
    CRMCase,
    CRMContact,
    CRMOpportunity,
    OnboardingPhase,
    OnboardingProject,
    OnboardingTask,
)
from ultra_csm.data_plane.fixtures import DEFAULT_TENANT, FixtureCustomerData
from ultra_csm.data_plane.live_smoke import HttpResponse
from ultra_csm.data_plane.live_facade import (
    LiveDataPlaneError,
    LiveOnboardingData,
    build_live_facade_from_data,
    build_served_data_plane,
)
from ultra_csm.data_plane.synthetic_book import build_synthetic_book


class HybridLiveClient:
    def __init__(self, salesforce_client: FakeSalesforceClient, rocketlane_account_id: str) -> None:
        self._salesforce_client = salesforce_client
        self._rocketlane_account_id = rocketlane_account_id

    def send(self, req):
        if req.url.startswith("https://api.rocketlane.com/api/1.0/projects"):
            return HttpResponse(
                status=200,
                headers={},
                body=(
                    b'{"data":[{"projectId":101,"customer":{"companyId":"'
                    + self._rocketlane_account_id.encode("utf-8")
                    + b'"},"projectName":"Live fake launch","status":{"value":2,'
                    b'"label":"In progress"},"owner":{"userId":77},'
                    b'"inferredProgress":"RUNNING_LATE","startDate":"2026-06-01",'
                    b'"dueDate":"2026-06-30","annualizedRecurringRevenue":1200}]}'
                ),
            )
        if req.url.startswith("https://api.rocketlane.com/api/1.0/phases"):
            return HttpResponse(
                status=200,
                headers={},
                body=(
                    b'{"data":[{"phaseId":201,"project":{"projectId":101},'
                    b'"phaseName":"Kickoff","startDate":"2026-06-01",'
                    b'"dueDate":"2026-06-20","status":{"label":"In progress"},'
                    b'"private":false}]}'
                ),
            )
        if req.url.startswith("https://api.rocketlane.com/api/1.0/tasks"):
            return HttpResponse(
                status=200,
                headers={},
                body=(
                    b'{"data":[{"taskId":301,"project":{"projectId":101},'
                    b'"phase":{"phaseId":201},"taskName":"Validate sync",'
                    b'"status":{"label":"Open"},"startDate":"2026-06-05",'
                    b'"dueDate":"2026-06-20","atRisk":true,'
                    b'"assignees":{"members":[{"userId":77}]}}]}'
                ),
            )
        return self._salesforce_client.send(req)


def _sf_book() -> FixtureCustomerData:
    account_id = "001-live-account"
    return FixtureCustomerData(
        accounts=(
            CRMAccount(
                account_id=account_id,
                name="Live Trailhead Logistics",
                owner_id="sf-owner-1",
                industry="Logistics",
            ),
        ),
        companies=(),
        contacts=(
            CRMContact(
                contact_id="003-live-contact",
                account_id=account_id,
                email="champion@trailhead-logistics.example",
                name="Avery Champion",
                role="champion",
                title="VP Operations",
                consent_to_contact=True,
            ),
        ),
        cases=(
            CRMCase(
                case_id="500-high-case",
                account_id=account_id,
                status="New",
                priority="High",
                origin="Email",
                subject="Integration outage blocking launch",
                created_at="2026-06-25T10:00:00Z",
            ),
        ),
        opportunities=(
            CRMOpportunity(
                opportunity_id="006-renewal",
                account_id=account_id,
                stage_name="Renewal Review",
                amount_cents=125_000_00,
                close_date="2026-08-01",
                opportunity_type="Renewal",
            ),
        ),
        health_scores=(),
        ctas=(),
        success_plans=(),
        adoption_summaries=(),
        entitlements=(),
        usage_signals=(),
        milestones=(),
        tenant_accounts={DEFAULT_TENANT: (account_id,)},
    )


def _rocketlane_data() -> LiveOnboardingData:
    return LiveOnboardingData(
        projects=(
            OnboardingProject(
                project_id="rl-project-1",
                account_id="001-live-account",
                name="Trailhead launch",
                status_value=2,
                status_label="In progress",
                owner_id="rl-owner-1",
                progress="running_late",
                start_date="2026-06-01",
                start_date_actual="2026-06-01",
                due_date="2026-06-28",
                due_date_actual=None,
                arr_cents=125_000_00,
            ),
        ),
        phases=(
            OnboardingPhase(
                phase_id="rl-phase-1",
                project_id="rl-project-1",
                name="Data sync",
                start_date="2026-06-01",
                start_date_actual="2026-06-01",
                due_date="2026-06-20",
                due_date_actual=None,
                status_label="In progress",
                private=False,
            ),
        ),
        tasks=(
            OnboardingTask(
                task_id="rl-task-1",
                project_id="rl-project-1",
                phase_id="rl-phase-1",
                name="Validate connector",
                status_label="Open",
                start_date="2026-06-10",
                due_date="2026-06-20",
                due_date_actual=None,
                at_risk=True,
                assignee_ids=("rl-owner-1",),
            ),
        ),
        status="live",
    )


def test_fixture_mode_is_default_served_data_plane():
    assembly = build_served_data_plane(env={"ULTRA_CSM_DATA_PLANE_MODE": "fixture"})

    assert assembly.mode == "fixture"
    assert assembly.health_source == "fixture_cs_platform"
    assert assembly.data_plane.crm.list_accounts(tenant_id=DEFAULT_TENANT)


def test_explicit_live_mode_fails_closed_without_salesforce_creds(monkeypatch, tmp_path):
    monkeypatch.setenv("ULTRA_CSM_LIVE_CREDS_PATH", str(tmp_path / "missing.env"))
    for key in (
        "ULTRA_CSM_SALESFORCE_INSTANCE_URL",
        "ULTRA_CSM_SALESFORCE_ACCESS_TOKEN",
        "ULTRA_CSM_SALESFORCE_CLIENT_ID",
        "ULTRA_CSM_SALESFORCE_CLIENT_SECRET",
        "ULTRA_CSM_SALESFORCE_REFRESH_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(LiveDataPlaneError, match="missing Salesforce live env names"):
        build_served_data_plane(env={"ULTRA_CSM_DATA_PLANE_MODE": "live"})


def test_live_mode_selector_builds_salesforce_rocketlane_facade_with_fake_clients(monkeypatch, tmp_path):
    monkeypatch.setenv("ULTRA_CSM_LIVE_CREDS_PATH", str(tmp_path / "missing.env"))
    book = build_synthetic_book()
    first_account_id = book.accounts[0].account_id
    client = HybridLiveClient(
        FakeSalesforceClient(build_salesforce_fixture_payloads(book)),
        rocketlane_account_id=first_account_id,
    )

    assembly = build_served_data_plane(
        env={
            "ULTRA_CSM_DATA_PLANE_MODE": "live",
            "ULTRA_CSM_SALESFORCE_INSTANCE_URL": BASE_URL,
            "ULTRA_CSM_SALESFORCE_ACCESS_TOKEN": "short-lived-token",
            "ULTRA_CSM_SALESFORCE_API_VERSION": API_VERSION,
            "ULTRA_CSM_ROCKETLANE_API_KEY": "fake-rocketlane-key",
            "ULTRA_CSM_LIVE_ROW_CAP": "3",
        },
        http_client=client,
    )

    assert assembly.mode == "live"
    assert assembly.source_status["salesforce"] == "live"
    assert assembly.source_status["rocketlane"] == "live"
    assert assembly.health_source == "derived_raw_signals"
    health = assembly.data_plane.cs.get_health_score(first_account_id)
    assert health is not None
    assert "rocketlane_project_running_late" in health.drivers


def test_live_facade_derives_health_from_raw_crm_and_rocketlane_signals():
    assembly = build_live_facade_from_data(
        salesforce_data=_sf_book(),
        onboarding_data=_rocketlane_data(),
        as_of="2026-06-27",
        source_status={"salesforce": "live", "rocketlane": "live", "gmail": "not_instrumented"},
    )

    health = assembly.data_plane.cs.get_health_score("001-live-account")
    assert health is not None
    assert assembly.health_source == "derived_raw_signals"
    assert health.band == "red"
    assert "crm_high_priority_open_case" in health.drivers
    assert "rocketlane_project_running_late" in health.drivers
    assert "rocketlane_at_risk_task" in health.drivers
    assert "comms_not_instrumented" in health.drivers

    ctas = assembly.data_plane.cs.list_ctas("001-live-account", status="open")
    assert {cta.reason for cta in ctas} >= {
        "Open High support case: Integration outage blocking launch",
        "Rocketlane onboarding risk: Trailhead launch",
    }
    assert assembly.data_plane.telemetry.list_ttv_milestones("001-live-account")
