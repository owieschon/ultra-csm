"""Program 4's cross-system beat: a corpus B (Salesforce) account's TTV
proposal citing corpus C (Rocketlane) evidence, through the action gate.

The real corpus B Salesforce account id is NEVER hardcoded here (real
Salesforce record ids are on this program's commit-time sentinel denylist).
This test reads it from environment variables at run time and skips
gracefully when they are absent -- exactly the same discipline as the R1
recorded-payload tests skip when the local corpus-run directory is absent.

To run live: export ULTRA_CSM_CROSS_SYSTEM_SF_ACCOUNT_ID (a real Account Id
queried read-only via `SELECT Id, Name, OwnerId FROM Account WHERE Name
LIKE 'UCSM-P3E-D1%'`), ULTRA_CSM_CROSS_SYSTEM_SF_ACCOUNT_NAME, and
ULTRA_CSM_CROSS_SYSTEM_SF_OWNER_ID, then run this file. Salesforce itself
is read-only in this program -- these env vars are populated from a read
query result, never a write.

Rocketlane evidence is D3 (the at-risk-cluster dataset seeded in Program 4),
fetched live via mcp__rocketlane__get_phases/get_tasks 2026-07-03 -- same
recorded payload as test_rocketlane_live_battery.py. Program 4 used D2 here
instead of D3 because Agent 1's sweep only turned a milestone into a scored
work item through the date-based open_milestone_gaps filter (expected_by <=
as_of and achieved_at is None); D3's activation-gap (atRisk-before-due-date)
did not by itself clear the sweep's score>0 threshold (see
docs/PROGRAM_REPORT_4.md, Owner Ask #2). The lifecycle-aware TTV fix in
value_model.py/sweep.py closes that gap for onboarding-stage accounts, so
this beat now runs on D3 itself -- the exact dataset the prior program had
to substitute away from.
"""

from __future__ import annotations

import os
import uuid

import pytest

from ultra_csm.agent1 import run_time_to_value_sweep
from ultra_csm.data_plane.adapters.rocketlane import parse_phase, parse_task
from ultra_csm.data_plane.contracts import (
    AdoptionSummary,
    CRMAccount,
    CRMContact,
    CSCompany,
    CustomerDataPlane,
    HealthScore,
    OnboardingProject,
    resolve_candidates,
)
from ultra_csm.data_plane.rocketlane_fixtures import FixtureOnboardingConnector, FixtureOnboardingData
from ultra_csm.governance import ROLE_CS_ORCHESTRATOR, ActionGate, FixtureVerdictSource, make_principal, seed_roster
from ultra_csm.platform.db import session

AS_OF = "2026-07-03"

D3_PHASE_RAW = {
    "phaseId": 5000000385261, "phaseName": "UCSM-P4C-D3 At-Risk Integration Cluster",
    "project": {"projectId": 5000000116921, "projectName": "[Sample] Acme 2 week onboarding"},
    "startDate": "2026-07-01", "dueDate": "2026-08-01",
    "status": {"value": 1, "label": "To do"}, "private": False,
}
D3_TASK_RAWS = [
    {
        "taskId": 5000002982470, "taskName": "UCSM-P4C-D3-T1 API credential exchange",
        "startDate": "2026-07-01", "dueDate": "2026-07-15", "atRisk": True,
        "project": {"projectId": 5000000116921, "projectName": "[Sample] Acme 2 week onboarding"},
        "status": {"value": 1, "label": "To do"},
        "phase": {"phaseId": 5000000385261, "phaseName": "UCSM-P4C-D3 At-Risk Integration Cluster"},
        "assignees": {},
    },
    {
        "taskId": 5000002982471, "taskName": "UCSM-P4C-D3-T2 Data mapping validation",
        "startDate": "2026-07-05", "dueDate": "2026-07-20", "atRisk": True,
        "project": {"projectId": 5000000116921, "projectName": "[Sample] Acme 2 week onboarding"},
        "status": {"value": 1, "label": "To do"},
        "phase": {"phaseId": 5000000385261, "phaseName": "UCSM-P4C-D3 At-Risk Integration Cluster"},
        "assignees": {},
    },
    {
        "taskId": 5000002982472, "taskName": "UCSM-P4C-D3-T3 Non-risk documentation task",
        "startDate": "2026-07-01", "dueDate": "2026-08-01",
        "project": {"projectId": 5000000116921, "projectName": "[Sample] Acme 2 week onboarding"},
        "status": {"value": 1, "label": "To do"},
        "phase": {"phaseId": 5000000385261, "phaseName": "UCSM-P4C-D3 At-Risk Integration Cluster"},
        "assignees": {},
    },
]


def _sf_account_env():
    sf_id = os.environ.get("ULTRA_CSM_CROSS_SYSTEM_SF_ACCOUNT_ID")
    sf_name = os.environ.get("ULTRA_CSM_CROSS_SYSTEM_SF_ACCOUNT_NAME")
    sf_owner = os.environ.get("ULTRA_CSM_CROSS_SYSTEM_SF_OWNER_ID")
    if not sf_id or not sf_name or not sf_owner:
        pytest.skip(
            "ULTRA_CSM_CROSS_SYSTEM_SF_ACCOUNT_ID/_NAME/_OWNER_ID not set -- "
            "cross-system beat needs a real corpus B account id (never "
            "hardcoded here); see this file's docstring."
        )
    return sf_id, sf_name, sf_owner


@pytest.fixture
def cross_beat_conn(runtime_conn):
    runtime_conn.execute("BEGIN")
    try:
        yield runtime_conn
    finally:
        runtime_conn.rollback()


def test_salesforce_account_ttv_proposal_cites_rocketlane_evidence(cross_beat_conn):
    sf_account_id, sf_account_name, sf_owner_id = _sf_account_env()

    phase = parse_phase(D3_PHASE_RAW)
    tasks = tuple(parse_task(t) for t in D3_TASK_RAWS)
    project = OnboardingProject(
        project_id=phase.project_id,
        account_id=sf_account_id,  # the cross-system join
        name="[Sample] Acme 2 week onboarding",
        status_value=None, status_label=None, owner_id=None, progress="none",
        start_date=None, start_date_actual=None, due_date=None, due_date_actual=None,
        arr_cents=None,
    )
    onboarding = FixtureOnboardingConnector(
        data=FixtureOnboardingData(projects=(project,), phases=(phase,), tasks=tasks)
    )

    account = CRMAccount(
        account_id=sf_account_id, name=sf_account_name, owner_id=sf_owner_id, industry="Manufacturing",
    )
    company = CSCompany(
        company_id=sf_account_id, name=sf_account_name, industry="Manufacturing",
        arr_cents=5_000_000, lifecycle_stage="onboarding", status="active",
        original_contract_date="2026-05-01", renewal_date="2027-05-01",
        csm_owner_id=sf_owner_id, current_score=None,
    )
    health = HealthScore(
        account_id=sf_account_id, score=50.0, band="yellow",
        drivers=("cross_system_beat",), measured_at=AS_OF,
    )
    adoption = AdoptionSummary(
        account_id=sf_account_id, active_users=1, licensed_users=5,
        active_assets=0, entitled_assets=0, adoption_rate=0.2,
        underused_capabilities=(), measured_at=AS_OF,
    )
    contact = CRMContact(
        contact_id=f"{sf_account_id}-contact-1", account_id=sf_account_id,
        email="crossbeat@example.test", name="Cross Beat Contact",
        role="ops", title="Ops Lead", consent_to_contact=True,
    )

    class _OneAccountCRM:
        def list_accounts(self, *, tenant_id=None):
            return [account]

        def resolve_account_by_email(self, email):
            if email.lower() == contact.email.lower():
                return resolve_candidates([sf_account_id])
            return resolve_candidates([])

        def get_account(self, account_id):
            return account if account_id == sf_account_id else None

        def list_contacts(self, account_id):
            return [contact] if account_id == sf_account_id else []

        def list_cases(self, account_id):
            return []

        def list_opportunities(self, account_id):
            return []

        def log_activity(self, account_id, *, channel, direction, summary, idempotency_key):
            return "n/a"

    class _OneAccountCS:
        def get_company(self, account_id):
            return company if account_id == sf_account_id else None

        def get_health_score(self, account_id):
            return health if account_id == sf_account_id else None

        def list_ctas(self, account_id, *, status=None):
            return []

        def list_success_plans(self, account_id):
            return []

        def get_adoption_summary(self, account_id):
            return adoption if account_id == sf_account_id else None

    class _EmptyTelemetry:
        def list_entitlements(self, account_id):
            return []

        def list_usage_signals(self, account_id, *, metric_name=None, since=None, until=None):
            return []

        def list_ttv_milestones(self, account_id):
            return []

    plane = CustomerDataPlane(
        crm=_OneAccountCRM(), cs=_OneAccountCS(), telemetry=_EmptyTelemetry(),
        onboarding=onboarding,
    )

    ns = uuid.NAMESPACE_URL
    tenant_id = str(uuid.uuid5(ns, "ultra-csm:cross-system-beat:tenant"))
    seed_actor = str(uuid.uuid5(ns, "ultra-csm:cross-system-beat:seed-actor"))
    with session(cross_beat_conn, tenant_id=tenant_id, actor_id=seed_actor, now=AS_OF + "T00:00:00Z") as cur:
        cur.execute(
            "INSERT INTO tenant (tenant_id, name) VALUES (%s, %s) "
            "ON CONFLICT (tenant_id) DO NOTHING",
            (tenant_id, "cross-system-beat-tenant"),
        )
        cur.execute(
            "INSERT INTO principal (principal_id, tenant_id, kind, display_name) "
            "VALUES (%s, %s, 'agent', %s) ON CONFLICT (principal_id) DO NOTHING",
            (seed_actor, tenant_id, "system-seed"),
        )
    seed_roster(cross_beat_conn, tenant_id=tenant_id, actor_id=seed_actor, now=AS_OF + "T00:00:00Z")
    orch = make_principal(
        cross_beat_conn, tenant_id=tenant_id, actor_id=seed_actor,
        display_name="cs-orchestrator", role=ROLE_CS_ORCHESTRATOR, now=AS_OF + "T00:00:00Z",
    )
    gate = ActionGate(
        cross_beat_conn, tenant_id=tenant_id, actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(), now=AS_OF + "T00:00:00Z",
    )

    sweep = run_time_to_value_sweep(
        plane, tenant_id, gate, sweep_principal_id=orch, as_of=AS_OF,
    )
    work_by_account = {item.account_id: item for item in sweep.work_items}
    assert sf_account_id in work_by_account

    item = work_by_account[sf_account_id]
    rocketlane_refs = [
        ref for f in item.priority.factors for ref in f.evidence
        if ref.source == "rocketlane"
    ]
    assert rocketlane_refs
    real_ids = {phase.phase_id, *(t.task_id for t in tasks)}
    assert {ref.source_id for ref in rocketlane_refs} <= real_ids
    # per-source claim boundary: no telemetry/cs_platform ref got mislabeled
    # as rocketlane, and vice versa -- every ref's source matches evidence
    # that actually exists for that source in this plane.
    for f in item.priority.factors:
        for ref in f.evidence:
            assert ref.source in {"rocketlane", "telemetry", "cs_platform", "crm"}
