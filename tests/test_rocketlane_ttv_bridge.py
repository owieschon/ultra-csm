"""R2: the TTV bridge -- Rocketlane onboarding evidence lights up the fourth
(outcome/TTV) value-model rail and Agent 1's existing sweep/single-account
paths, with the existing logic itself unchanged (only optional new inputs).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests._govhelpers import CLOCK, T1, setup_roster
from ultra_csm._util import iso_date
from ultra_csm.agent1 import TimeToValueAccelerator, run_time_to_value_sweep
from ultra_csm.data_plane import (
    DEFAULT_TENANT,
    STARK_INSUFFICIENT,
    CustomerDataPlane,
    FixtureCSPlatformConnector,
    FixtureOnboardingConnector,
    FixtureOnboardingData,
    OnboardingPhase,
    OnboardingProject,
    OnboardingTask,
    build_sweep_fixture_data_plane,
    det_rocketlane_id,
    onboarding_activation_gap_ids,
    sweep_fixture_data,
)
from ultra_csm.governance import ActionGate, FixtureVerdictSource
from ultra_csm.value_model import build_customer_value_model

AS_OF = "2026-06-27"


def _stark_onboarding_data(*, achieved: bool) -> FixtureOnboardingData:
    project_id = det_rocketlane_id("project", "stark-bridge-test")
    phase_id = det_rocketlane_id("phase", "stark-bridge-test-kickoff")
    task_id = det_rocketlane_id("task", "stark-bridge-test-task")
    project = OnboardingProject(
        project_id=project_id,
        account_id=STARK_INSUFFICIENT,
        name="[Fixture] Stark bridge test",
        status_value=2,
        status_label="In progress",
        owner_id=det_rocketlane_id("user", "csm-owner"),
        progress="none",
        start_date="2026-06-01",
        start_date_actual="2026-06-01",
        due_date="2026-06-20",
        due_date_actual=None,
        arr_cents=4_500_000,
    )
    phase = OnboardingPhase(
        phase_id=phase_id,
        project_id=project_id,
        name="Kickoff",
        start_date="2026-06-01",
        start_date_actual="2026-06-01",
        due_date="2026-06-20",
        due_date_actual="2026-06-19" if achieved else None,
        status_label="Completed" if achieved else "In Progress",
        private=False,
    )
    task = OnboardingTask(
        task_id=task_id,
        project_id=project_id,
        phase_id=phase_id,
        name="Kickoff call",
        status_label="Completed" if achieved else "In progress",
        start_date="2026-06-01",
        due_date="2026-06-20",
        due_date_actual="2026-06-19" if achieved else None,
        at_risk=False,
        assignee_ids=(det_rocketlane_id("user", "csm-owner"),),
    )
    return FixtureOnboardingData(projects=(project,), phases=(phase,), tasks=(task,))


class _RaisingOnboardingConnector:
    """Simulates a connector outage/timeout/auth error for fail-closed tests."""

    def list_projects_for_account(self, account_id):
        raise RuntimeError("simulated Rocketlane outage")

    def get_project(self, project_id):
        raise RuntimeError("simulated Rocketlane outage")

    def list_phases(self, project_id):
        raise RuntimeError("simulated Rocketlane outage")

    def list_tasks(self, project_id, *, at_risk_only=False, phase_id=None):
        raise RuntimeError("simulated Rocketlane outage")

    def derive_ttv_milestones(self, account_id):
        raise RuntimeError("simulated Rocketlane outage")


# ---------------------------------------------------------------------------
# Value-model outcome rail: both states asserted explicitly.
# ---------------------------------------------------------------------------


def _stark_model_inputs():
    data = sweep_fixture_data()
    account = next(a for a in data.accounts if a.account_id == STARK_INSUFFICIENT)
    company = next(c for c in data.companies if c.company_id == STARK_INSUFFICIENT)
    health = next(h for h in data.health_scores if h.account_id == STARK_INSUFFICIENT)
    adoption = next(a for a in data.adoption_summaries if a.account_id == STARK_INSUFFICIENT)
    return account, company, health, adoption


def test_outcome_rail_degrades_honestly_with_no_onboarding_source():
    """Absence state: no success plans, no onboarding milestones -> not_instrumented.
    This is the "TTV rails unknown" honest-degradation baseline."""
    account, company, health, adoption = _stark_model_inputs()
    model = build_customer_value_model(
        account=account,
        company=company,
        health=health,
        adoption=adoption,
        entitlements=(),
        usage_signals=(),
        success_plans=(),
    )
    assert model.outcome.realized_state == "not_instrumented"
    assert not model.outcome.stated_objectives


def test_outcome_rail_goes_known_when_onboarding_milestone_achieved():
    """Presence state: a mapped onboarding source with an achieved milestone
    flips realized_state to known, citing rocketlane evidence -- this is the
    rail "going live" the program exists to prove."""
    account, company, health, adoption = _stark_model_inputs()
    onboarding_data = _stark_onboarding_data(achieved=True)
    conn = FixtureOnboardingConnector(data=onboarding_data)
    milestones = tuple(conn.derive_ttv_milestones(STARK_INSUFFICIENT))
    assert milestones and milestones[0].achieved_at is not None

    model = build_customer_value_model(
        account=account,
        company=company,
        health=health,
        adoption=adoption,
        entitlements=(),
        usage_signals=(),
        success_plans=(),
        onboarding_milestones=milestones,
    )
    assert model.outcome.realized_state == "known"
    factor = next(f for f in model.outcome.factors if f.name == "onboarding_milestone_achieved")
    assert factor.evidence
    assert all(ref.source == "rocketlane" for ref in factor.evidence)


def test_outcome_rail_stays_not_instrumented_when_onboarding_milestone_unachieved():
    """An open (not-yet-achieved) Rocketlane milestone alone does not flip
    realized_state -- realization requires an achieved milestone or a
    realized success plan, never guessed from an open gap."""
    account, company, health, adoption = _stark_model_inputs()
    onboarding_data = _stark_onboarding_data(achieved=False)
    conn = FixtureOnboardingConnector(data=onboarding_data)
    milestones = tuple(conn.derive_ttv_milestones(STARK_INSUFFICIENT))
    assert milestones and milestones[0].achieved_at is None

    model = build_customer_value_model(
        account=account,
        company=company,
        health=health,
        adoption=adoption,
        entitlements=(),
        usage_signals=(),
        success_plans=(),
        onboarding_milestones=milestones,
    )
    assert model.outcome.realized_state == "not_instrumented"


# ---------------------------------------------------------------------------
# Agent 1 single-account path: evidence_signal_ids cite Rocketlane ids.
# ---------------------------------------------------------------------------


def _stark_data_plane(onboarding) -> CustomerDataPlane:
    base = build_sweep_fixture_data_plane()
    return CustomerDataPlane(
        crm=base.crm,
        cs=base.cs,
        telemetry=base.telemetry,
        onboarding=onboarding,
    )


def test_agent1_build_evidence_cites_rocketlane_ids_when_telemetry_is_absent():
    """STARK_INSUFFICIENT has zero usage signals and zero success plans in the
    fixture book -- without an onboarding source it has no evidence_signal_ids
    at all. With one, an OPEN (overdue, unachieved) Rocketlane milestone's
    phase/task ids surface as grounded evidence."""
    onboarding_data = _stark_onboarding_data(achieved=False)
    plane_without = _stark_data_plane(None)
    agent_without = TimeToValueAccelerator(plane_without)
    evidence_without = agent_without.build_evidence(STARK_INSUFFICIENT, as_of=AS_OF)
    assert evidence_without is not None
    assert evidence_without.evidence_signal_ids == ()

    plane_with = _stark_data_plane(FixtureOnboardingConnector(data=onboarding_data))
    agent_with = TimeToValueAccelerator(plane_with)
    evidence_with = agent_with.build_evidence(STARK_INSUFFICIENT, as_of=AS_OF)
    assert evidence_with is not None
    assert evidence_with.evidence_signal_ids != ()
    phase_task_ids = {onboarding_data.phases[0].phase_id, onboarding_data.tasks[0].task_id}
    assert set(evidence_with.evidence_signal_ids) <= phase_task_ids
    assert set(evidence_with.evidence_signal_ids)  # non-empty overlap


def test_agent1_fails_closed_on_onboarding_connector_outage():
    """A connector outage must degrade to no-evidence, never raise into the
    caller and never fabricate a milestone."""
    plane = _stark_data_plane(_RaisingOnboardingConnector())
    agent = TimeToValueAccelerator(plane)
    evidence = agent.build_evidence(STARK_INSUFFICIENT, as_of=AS_OF)
    assert evidence is not None
    assert evidence.milestones == ()
    assert evidence.evidence_signal_ids == ()


# ---------------------------------------------------------------------------
# Agent 1 sweep: end-to-end TTV proposal through the action gate, citing
# Rocketlane ids.
# ---------------------------------------------------------------------------


@pytest.fixture
def bridge_conn(runtime_conn):
    runtime_conn.execute("BEGIN")
    try:
        yield runtime_conn
    finally:
        runtime_conn.rollback()


def test_agent1_sweep_produces_ttv_proposal_from_rocketlane_evidence_alone(bridge_conn):
    """Before this program, STARK_INSUFFICIENT produces no work item (its
    fixture name says so). With a mapped Rocketlane onboarding source citing
    a concrete phase/task gap, Agent 1's *unchanged* sweep logic now proposes
    a gated Time-to-Value outreach for it, citing the Rocketlane evidence ids
    -- proving the fourth rail is live end-to-end through the action gate."""
    orch, _authority = setup_roster(bridge_conn)
    gate = ActionGate(
        bridge_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )

    onboarding_data = _stark_onboarding_data(achieved=False)
    base_plane = build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT)
    plane = CustomerDataPlane(
        crm=base_plane.crm,
        cs=base_plane.cs,
        telemetry=base_plane.telemetry,
        onboarding=FixtureOnboardingConnector(data=onboarding_data),
    )

    without_onboarding = run_time_to_value_sweep(
        base_plane, DEFAULT_TENANT, gate, sweep_principal_id=orch, as_of=AS_OF,
    )
    assert STARK_INSUFFICIENT not in {i.account_id for i in without_onboarding.work_items}

    with_onboarding = run_time_to_value_sweep(
        plane, DEFAULT_TENANT, gate, sweep_principal_id=orch, as_of=AS_OF,
    )
    work_by_account = {item.account_id: item for item in with_onboarding.work_items}
    assert STARK_INSUFFICIENT in work_by_account

    item = work_by_account[STARK_INSUFFICIENT]
    rocketlane_refs = [ref for f in item.priority.factors for ref in f.evidence if ref.source == "rocketlane"]
    assert rocketlane_refs
    phase_task_ids = {onboarding_data.phases[0].phase_id, onboarding_data.tasks[0].task_id}
    assert {ref.source_id for ref in rocketlane_refs} <= phase_task_ids


# ---------------------------------------------------------------------------
# Lane A: lifecycle-aware TTV scoring. An onboarding-stage account whose only
# signal is delivery slippage (not yet overdue by date, only activation-gap)
# was invisible to the sweep's score>0 gate before this fix -- reproduced,
# then closed, per docs/PROGRAM_REPORT_4.md Owner Ask #2.
# ---------------------------------------------------------------------------


def _stark_activation_gap_onboarding_data() -> FixtureOnboardingData:
    """D3-shaped: a phase not yet overdue by date, but a task under it is
    explicitly at_risk. No milestone here ever clears the date-based
    ``expected_by <= as_of`` filter -- the exact blind spot this fix closes.
    """
    project_id = det_rocketlane_id("project", "stark-activation-gap-test")
    phase_id = det_rocketlane_id("phase", "stark-activation-gap-test-setup")
    task_id = det_rocketlane_id("task", "stark-activation-gap-test-task")
    project = OnboardingProject(
        project_id=project_id,
        account_id=STARK_INSUFFICIENT,
        name="[Fixture] Stark activation-gap test",
        status_value=2,
        status_label="In progress",
        owner_id=det_rocketlane_id("user", "csm-owner"),
        progress="none",
        start_date="2026-06-01",
        start_date_actual="2026-06-01",
        due_date="2026-12-01",
        due_date_actual=None,
        arr_cents=4_500_000,
    )
    phase = OnboardingPhase(
        phase_id=phase_id,
        project_id=project_id,
        name="Setup",
        start_date="2026-06-01",
        start_date_actual="2026-06-01",
        due_date="2026-12-01",
        due_date_actual=None,
        status_label="In Progress",
        private=False,
    )
    task = OnboardingTask(
        task_id=task_id,
        project_id=project_id,
        phase_id=phase_id,
        name="Integration setup",
        status_label="In progress",
        start_date="2026-06-01",
        due_date="2026-11-01",
        due_date_actual=None,
        at_risk=True,
        assignee_ids=(det_rocketlane_id("user", "csm-owner"),),
    )
    return FixtureOnboardingData(projects=(project,), phases=(phase,), tasks=(task,))


def test_activation_gap_milestone_clears_no_date_based_gap():
    """Reproduces the blindness directly: derive_ttv_milestones' own output
    for this fixture never satisfies the date-based open-gap filter, because
    the phase isn't overdue -- only its task is at_risk."""
    onboarding_data = _stark_activation_gap_onboarding_data()
    conn = FixtureOnboardingConnector(data=onboarding_data)
    milestones = tuple(conn.derive_ttv_milestones(STARK_INSUFFICIENT))
    assert milestones
    milestone = milestones[0]
    assert milestone.achieved_at is None
    assert iso_date(milestone.expected_by) > iso_date(AS_OF)


def test_onboarding_activation_gap_ids_surfaces_at_risk_task_not_yet_overdue():
    """Unit-level proof that the fixture's only signal (an at-risk task
    under a not-yet-due phase) is exactly what onboarding_activation_gap_ids
    is meant to catch, independent of any date-based filter."""
    onboarding_data = _stark_activation_gap_onboarding_data()
    gap_ids = onboarding_activation_gap_ids(
        projects=onboarding_data.projects,
        phases=onboarding_data.phases,
        tasks=onboarding_data.tasks,
        as_of=AS_OF,
    )
    assert gap_ids, "fixture must actually carry activation-gap evidence"
    assert set(gap_ids) == {onboarding_data.phases[0].phase_id, onboarding_data.tasks[0].task_id}

    # covered_milestone_names excludes a phase already surfaced as an open
    # date-based gap -- no double-counting the same phase both ways.
    covered = onboarding_activation_gap_ids(
        projects=onboarding_data.projects,
        phases=onboarding_data.phases,
        tasks=onboarding_data.tasks,
        as_of=AS_OF,
        covered_milestone_names=frozenset({onboarding_data.phases[0].name}),
    )
    assert covered == ()


def test_agent1_sweep_proposes_ttv_outreach_from_activation_gap_alone(bridge_conn):
    """The fix: an onboarding-stage account with zero date-based gaps but a
    live activation-gap signal now clears the sweep's score>0 gate, citing
    the real Rocketlane phase/task ids as evidence -- not a global
    score>0 loosening, since the same fixture on a non-onboarding lifecycle
    stage stays invisible (see the paired negative test below)."""
    orch, _authority = setup_roster(bridge_conn)
    gate = ActionGate(
        bridge_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )

    onboarding_data = _stark_activation_gap_onboarding_data()
    base_plane = build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT)
    plane = CustomerDataPlane(
        crm=base_plane.crm,
        cs=base_plane.cs,
        telemetry=base_plane.telemetry,
        onboarding=FixtureOnboardingConnector(data=onboarding_data),
    )

    without_onboarding = run_time_to_value_sweep(
        base_plane, DEFAULT_TENANT, gate, sweep_principal_id=orch, as_of=AS_OF,
    )
    assert STARK_INSUFFICIENT not in {i.account_id for i in without_onboarding.work_items}

    with_onboarding = run_time_to_value_sweep(
        plane, DEFAULT_TENANT, gate, sweep_principal_id=orch, as_of=AS_OF,
    )
    work_by_account = {item.account_id: item for item in with_onboarding.work_items}
    assert STARK_INSUFFICIENT in work_by_account

    item = work_by_account[STARK_INSUFFICIENT]
    activation_refs = [
        ref for f in item.priority.factors for ref in f.evidence
        if ref.source == "rocketlane" and ref.field == "activation_gap"
    ]
    assert activation_refs
    phase_task_ids = {onboarding_data.phases[0].phase_id, onboarding_data.tasks[0].task_id}
    assert {ref.source_id for ref in activation_refs} <= phase_task_ids
    factor_names = {f.name for f in item.priority.factors}
    assert "onboarding_activation_gap" in factor_names
    # Never a global loosening: no date-based milestone_overdue factor fired.
    assert "milestones_overdue" not in factor_names


def test_agent1_sweep_activation_gap_not_scored_outside_onboarding_stage(bridge_conn):
    """Same activation-gap fixture, but the account's lifecycle stage is not
    onboarding -- the sweep must NOT score it. Proves this is a
    lifecycle-aware fix, not a global score>0 loosening."""
    orch, _authority = setup_roster(bridge_conn)
    gate = ActionGate(
        bridge_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )

    onboarding_data = _stark_activation_gap_onboarding_data()
    base_plane = build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT)
    data = sweep_fixture_data(tenant_id=DEFAULT_TENANT)
    steady_state_company = replace(
        next(c for c in data.companies if c.company_id == STARK_INSUFFICIENT),
        lifecycle_stage="steady_state",
    )
    companies = tuple(
        steady_state_company if c.company_id == STARK_INSUFFICIENT else c
        for c in data.companies
    )
    steady_state_data = replace(data, companies=companies)
    plane = CustomerDataPlane(
        crm=base_plane.crm,
        cs=FixtureCSPlatformConnector(data=steady_state_data),
        telemetry=base_plane.telemetry,
        onboarding=FixtureOnboardingConnector(data=onboarding_data),
    )

    result = run_time_to_value_sweep(
        plane, DEFAULT_TENANT, gate, sweep_principal_id=orch, as_of=AS_OF,
    )
    assert STARK_INSUFFICIENT not in {i.account_id for i in result.work_items}
