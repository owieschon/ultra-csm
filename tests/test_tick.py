"""Tick runner integration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ultra_csm import cli
from ultra_csm.governance import proposal_fields_for
from ultra_csm.platform import session
from ultra_csm.platform.seed import SEED_CLOCK
from ultra_csm.tick import (
    setup_tick_roster,
    observe_sim_state,
    run_tick_with_config,
)
from ultra_csm.triggers import parse_trigger_config


@pytest.fixture
def tick_conn(runtime_conn):
    runtime_conn.execute("BEGIN")
    try:
        yield runtime_conn
    finally:
        runtime_conn.rollback()


def test_tick_dry_run_reports_fires_without_ledger_write(tmp_path: Path):
    config = parse_trigger_config({
        "config_version": "test-triggers",
        "triggers": [{
            "name": "daily_ttv",
            "kind": "schedule",
            "every": "1d",
            "action": {"lens": "ttv", "scope": "book"},
        }],
    })

    result = run_tick_with_config(
        as_of="2026-06-21",
        config=config,
        state_dir=tmp_path,
        dry_run=True,
    )

    assert result.dry_run is True
    assert [item.trigger_name for item in result.evaluation.fired] == ["daily_ttv"]
    assert not (tmp_path / "tick_ledger.jsonl").exists()


def test_tick_runs_sweep_writes_provenance_and_preserves_action_tier(
    tmp_path: Path,
    tick_conn,
):
    context = setup_tick_roster(tick_conn)
    config = parse_trigger_config({
        "config_version": "test-triggers",
        "triggers": [{
            "name": "daily_ttv",
            "kind": "schedule",
            "every": "1d",
            "action": {"lens": "ttv", "scope": "book"},
        }],
    })

    result = run_tick_with_config(
        as_of="2026-06-21",
        config=config,
        state_dir=tmp_path,
        conn=tick_conn,
        gate_context=context,
    )

    assert result.ledger_entry is not None
    assert result.artifacts_written
    ledger = (tmp_path / "tick_ledger.jsonl").read_text(encoding="utf-8")
    assert "daily_ttv" in ledger

    work_queue = json.loads(Path(result.artifacts_written[0]).read_text(encoding="utf-8"))
    first_item = work_queue["fired_runs"][0]["work_items"][0]
    assert first_item["trigger_provenance"]["trigger_name"] == "daily_ttv"
    assert first_item["trigger_evidence"]["type"] == "schedule"

    with session(
        tick_conn,
        tenant_id=context.tenant_id,
        actor_id=context.actor_principal_id,
        now=SEED_CLOCK,
    ) as cur:
        cur.execute(
            "SELECT action, autonomy_tier, required_permission "
            "FROM action_proposal ORDER BY created_ts"
        )
        rows = cur.fetchall()

    assert rows
    for action, autonomy_tier, required_permission in rows:
        expected = proposal_fields_for(action)
        assert autonomy_tier == expected["autonomy_tier"]
        assert required_permission == expected["required_permission"]


def test_tick_records_cooldown_suppressions_in_ledger(tmp_path: Path, tick_conn):
    context = setup_tick_roster(tick_conn)
    config = parse_trigger_config({
        "config_version": "test-triggers",
        "triggers": [{
            "name": "renewal_window",
            "kind": "deadline",
            "when": [{"field": "renewal_date", "op": "within_days", "value": 90}],
            "action": {"lens": "ttv", "scope": "account"},
            "cooldown_days": 30,
        }],
    })
    first = run_tick_with_config(
        as_of="2026-06-21",
        config=config,
        state_dir=tmp_path,
        dry_run=True,
    )
    observed = observe_sim_state("2026-06-21")
    assert first.evaluation.fired
    (tmp_path / "tick_ledger.jsonl").write_text(
        json.dumps({
            "as_of": "2026-06-21",
            "day": first.day,
            "fired_triggers": [item.to_dict() for item in first.evaluation.fired],
            "snapshot": observed.trigger_state.to_dict(),
        }, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    second = run_tick_with_config(
        as_of="2026-06-22",
        config=config,
        state_dir=tmp_path,
        conn=tick_conn,
        gate_context=context,
    )

    assert second.ledger_entry is not None
    assert second.evaluation.fired == ()
    assert {item.reason for item in second.evaluation.suppressions} == {"cooldown"}
    ledger_rows = [
        json.loads(line)
        for line in (tmp_path / "tick_ledger.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert ledger_rows[-1]["suppressions"]
    assert ledger_rows[-1]["suppressions"][0]["reason"] == "cooldown"


def test_cli_registers_tick(monkeypatch, tmp_path: Path):
    seen = []

    def fake_run_tick_cli(**kwargs):
        seen.append(kwargs)
        return 0

    import ultra_csm.tick as tick_module

    monkeypatch.setattr(tick_module, "run_tick_cli", fake_run_tick_cli)

    code = cli.main([
        "tick",
        "--as-of",
        "2026-06-21",
        "--state-dir",
        str(tmp_path),
        "--dry-run",
        "--json",
    ])

    assert code == 0
    assert seen == [{
        "as_of": "2026-06-21",
        "config_path": Path("config/trigger_config.json"),
        "state_dir": tmp_path,
        "dry_run": True,
        "json_output": True,
    }]
