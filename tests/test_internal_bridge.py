from __future__ import annotations

from eval.internal_bridge_battery import run_battery
from tests._govhelpers import CLOCK, T1, setup_roster
from ultra_csm.agent1 import run_time_to_value_sweep
from ultra_csm.data_plane import ACME_LOGISTICS, DEFAULT_TENANT, build_sweep_fixture_data_plane
from ultra_csm.governance import ActionGate, FixtureVerdictSource


def test_internal_bridge_battery_hard_ok():
    report = run_battery()
    assert report["hard_ok"], report["failed_cases"]
    assert len(report["cases"]) == 18


def test_internal_bridge_battery_is_deterministic():
    assert run_battery() == run_battery()


def test_sweep_work_item_carries_additive_internal_bridge_decision(runtime_conn):
    runtime_conn.execute("BEGIN")
    try:
        orch, _authority = setup_roster(runtime_conn)
        gate = ActionGate(
            runtime_conn,
            tenant_id=T1,
            actor_principal_id=orch,
            verdict_source=FixtureVerdictSource(),
            now=CLOCK,
        )

        sweep = run_time_to_value_sweep(
            build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
            DEFAULT_TENANT,
            gate,
            sweep_principal_id=orch,
            as_of="2026-06-27",
        )

        acme = next(item for item in sweep.work_items if item.account_id == ACME_LOGISTICS)
        assert acme.internal_bridge_decision is not None
        assert acme.internal_bridge_decision.abstained is False
        assert acme.internal_bridge_decision.target == "engineering"
        assert acme.internal_bridge_decision.motion == "escalation"
    finally:
        runtime_conn.rollback()
