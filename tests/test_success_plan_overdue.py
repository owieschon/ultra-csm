"""Completed plans stop generating overdue alerts; unfinished work remains actionable."""

from __future__ import annotations

import dataclasses
import pytest

from tests._govhelpers import CLOCK, T1, setup_roster
from ultra_csm.agent1 import run_time_to_value_sweep
from ultra_csm.governance import ActionGate, FixtureVerdictSource

from ultra_csm._api_helpers import _build_account_brief, _score_one_account
from ultra_csm.data_plane import CustomerDataPlane, DEFAULT_TENANT
from ultra_csm.data_plane.contracts import SuccessPlan, TimeToValueMilestone
from ultra_csm.data_plane.fixtures import (
    NOVA_FIELD,
    FixtureCRMDataConnector,
    FixtureCSPlatformConnector,
    FixtureCommsConnector,
    FixtureProductTelemetryConnector,
    default_fixture_data,
)
from ultra_csm.value_model import (
    build_customer_value_model,
    project_ttv_lens,
)

_AS_OF = "2026-07-20"


def _quiet_nova_plane(*, status: str, target_date: str = "2026-07-01") -> CustomerDataPlane:
    """NOVA_FIELD with its one success plan swapped for a single plan at the
    given status/target_date, and no other material signal (green health,
    no open case, no CTA due, non-terminal opportunity)."""

    data = default_fixture_data()
    plan = SuccessPlan(
        plan_id="plan-nova-quiet",
        account_id=NOVA_FIELD,
        status=status,
        objectives=("renew_contract",),
        target_date=target_date,
    )
    data = dataclasses.replace(
        data,
        success_plans=tuple(p for p in data.success_plans if p.account_id != NOVA_FIELD) + (plan,),
    )
    return CustomerDataPlane(
        crm=FixtureCRMDataConnector(tenant=DEFAULT_TENANT, data=data),
        cs=FixtureCSPlatformConnector(data=data),
        telemetry=FixtureProductTelemetryConnector(data=data),
        comms=FixtureCommsConnector(data=data),
    )


def _factor_names(scored: dict) -> set[str]:
    return {f["name"] for f in scored["priority"]["factors"]}


def test_score_account_priority_ignores_a_completed_overdue_plan():
    plane = _quiet_nova_plane(status="complete")
    scored = _score_one_account(NOVA_FIELD, data_plane=plane, as_of=_AS_OF)
    assert "success_plan_overdue" not in _factor_names(scored)


def test_score_account_priority_still_flags_an_active_overdue_plan():
    plane = _quiet_nova_plane(status="active")
    scored = _score_one_account(NOVA_FIELD, data_plane=plane, as_of=_AS_OF)
    assert "success_plan_overdue" in _factor_names(scored)


def test_account_brief_ignores_a_completed_overdue_plan():
    for status in ("realized", "achieved", "complete"):
        plane = _quiet_nova_plane(status=status)
        brief = _build_account_brief(NOVA_FIELD, data_plane=plane, as_of=_AS_OF)
        assert "success_plan_overdue" not in {f["name"] for f in brief["priority"]["factors"]}


def test_account_brief_flags_mixed_complete_and_active_overdue_plans():
    data = default_fixture_data()
    completed = SuccessPlan(
        plan_id="plan-nova-done", account_id=NOVA_FIELD, status="realized",
        objectives=("renew_contract",), target_date="2026-06-01",
    )
    active = SuccessPlan(
        plan_id="plan-nova-open", account_id=NOVA_FIELD, status="active",
        objectives=("expand_reporting_usage",), target_date="2026-07-01",
    )
    data = dataclasses.replace(
        data,
        success_plans=tuple(p for p in data.success_plans if p.account_id != NOVA_FIELD)
        + (completed, active),
    )
    plane = CustomerDataPlane(
        crm=FixtureCRMDataConnector(tenant=DEFAULT_TENANT, data=data),
        cs=FixtureCSPlatformConnector(data=data),
        telemetry=FixtureProductTelemetryConnector(data=data),
        comms=FixtureCommsConnector(data=data),
    )
    brief = _build_account_brief(NOVA_FIELD, data_plane=plane, as_of=_AS_OF)
    factor = next(f for f in brief["priority"]["factors"] if f["name"] == "success_plan_overdue")
    assert factor["value"] == 1.0
    assert [ev["source_id"] for ev in factor["evidence"]] == ["plan-nova-open"]


def test_completed_overdue_plan_does_not_mask_an_independent_open_milestone_gap():
    """An unrelated, still-open milestone gap stays actionable even when the
    account's only success plan is complete-and-overdue -- the fix must not
    suppress independent risk signals, only the overdue-plan-specific one."""

    plane = _quiet_nova_plane(status="complete")
    milestone = TimeToValueMilestone(
        account_id=NOVA_FIELD,
        milestone="expand_reporting_usage",
        expected_by="2026-06-01",
        achieved_at=None,
        evidence_signal_ids=("sig-nova-milestone",),
    )
    account = plane.crm.get_account(NOVA_FIELD)
    company = plane.cs.get_company(NOVA_FIELD)
    health = plane.cs.get_health_score(NOVA_FIELD)
    adoption = plane.cs.get_adoption_summary(NOVA_FIELD)
    entitlements = tuple(plane.telemetry.list_entitlements(NOVA_FIELD))
    signals = tuple(plane.telemetry.list_usage_signals(NOVA_FIELD))
    plans = tuple(plane.cs.list_success_plans(NOVA_FIELD))
    model = build_customer_value_model(
        account=account, company=company, health=health, adoption=adoption,
        entitlements=entitlements, usage_signals=signals, success_plans=plans, as_of=_AS_OF,
    )
    projected = project_ttv_lens(
        model, company=company, health=health,
        open_milestone_gaps=(milestone,), overdue_success_plans=plans, as_of=_AS_OF,
    )
    names = {f.name for f in projected.factors}
    assert "milestones_overdue" in names
    assert "success_plan_overdue" not in names


def test_project_ttv_lens_defensive_filter_drops_completed_plans_from_caller():
    """Even if a caller's ``overdue_success_plans`` list still includes a
    complete plan, the central priority projection must not score it."""

    data = default_fixture_data()
    account = next(a for a in data.accounts if a.account_id == NOVA_FIELD)
    company = next(c for c in data.companies if c.company_id == NOVA_FIELD)
    health = next(h for h in data.health_scores if h.account_id == NOVA_FIELD)
    adoption = next(a for a in data.adoption_summaries if a.account_id == NOVA_FIELD)
    completed = SuccessPlan(
        plan_id="plan-nova-done", account_id=NOVA_FIELD, status="achieved",
        objectives=("renew_contract",), target_date="2026-06-01",
    )
    model = build_customer_value_model(
        account=account, company=company, health=health, adoption=adoption,
        entitlements=(), usage_signals=(), success_plans=(completed,), as_of=_AS_OF,
    )
    projected = project_ttv_lens(
        model, company=company, health=health, overdue_success_plans=(completed,), as_of=_AS_OF,
    )
    assert not any(f.name == "success_plan_overdue" for f in projected.factors)



@pytest.mark.parametrize("status,expect_overdue", [("complete", False), ("achieved", False), ("realized", False), ("active", True), ("unknown", True)])
def test_sweep_overdue_factor_tracks_unfinished_plans(runtime_conn, status, expect_overdue):
    runtime_conn.execute("BEGIN")
    orch, _ = setup_roster(runtime_conn)
    gate = ActionGate(runtime_conn, tenant_id=T1, actor_principal_id=orch,
                      verdict_source=FixtureVerdictSource(), now=CLOCK)
    result = run_time_to_value_sweep(_quiet_nova_plane(status=status), DEFAULT_TENANT,
                                    gate, sweep_principal_id=orch, as_of=_AS_OF)
    item = next((i for i in result.work_items if i.account_id == NOVA_FIELD), None)
    if expect_overdue:
        assert item is not None
        assert "success_plan_overdue" in {f.name for f in item.priority.factors}
    else:
        assert item is None
