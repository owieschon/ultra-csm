from __future__ import annotations

import inspect
import ast
import hashlib
import json

from eval import takeover_scoreboard as scoreboard
from tests._govhelpers import CLOCK, T1, make_human_principal, setup_roster
from ultra_csm.platform.db import session
from ultra_csm.rejection_ledger import RejectionLedger


def test_takeover_scoreboard_module_is_read_only():
    source = inspect.getsource(scoreboard)
    tree = ast.parse(source)
    forbidden_imports = {
        "ActionGate",
        "FixtureVerdictSource",
        "record_audit_event",
        "run_self_serve_signup_activation",
        "run_time_to_value_sweep",
    }
    forbidden_calls = {
        "propose",
        "record_verdict",
        "approve",
        "deny",
        "revise",
        "record_audit_event",
        "run_self_serve_signup_activation",
        "run_time_to_value_sweep",
    }

    imported = set()
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.update(alias.name.rsplit(".", 1)[-1] for alias in node.names)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called.add(node.func.attr)

    assert not (forbidden_imports & imported)
    assert not (forbidden_calls & called)


def test_all_metrics_carry_status_and_missing_sources_are_not_zero():
    artifact = scoreboard.build_takeover_scoreboard(
        verdict_records=(),
        audit_events=(),
        accounts_in_scope=9,
    ).to_dict()

    rows = (artifact["book_rollup"], *artifact["rows"])
    for row in rows:
        for metric in row["metrics"]:
            assert metric["status"] in {"measured", "modeled", "not_instrumented"}
            if metric["status"] == "not_instrumented":
                assert metric["value"] is None

    metrics = {metric["name"]: metric for metric in artifact["book_rollup"]["metrics"]}
    assert metrics["human_minutes_per_account_week"]["status"] == "modeled"
    assert metrics["coverage"]["status"] == "not_instrumented"
    assert metrics["coverage"]["value"] is None


def test_verdict_mix_reads_real_governance_tables(runtime_conn):
    runtime_conn.execute("BEGIN")
    try:
        orch, _authority = setup_roster(runtime_conn, tenant=T1)
        human = make_human_principal(runtime_conn, tenant=T1)
        _seed_proposal_and_verdict(
            runtime_conn,
            actor_id=orch,
            human_id=human,
            proposal_id="11111111-1111-4111-8111-111111111111",
            action="update_cs_platform_record",
            autonomy_tier=2,
            verdict="approve",
            rationale="clear_next_step",
        )
        _seed_proposal_and_verdict(
            runtime_conn,
            actor_id=orch,
            human_id=human,
            proposal_id="22222222-2222-4222-8222-222222222222",
            action="update_cs_platform_record",
            autonomy_tier=2,
            verdict="deny",
            rationale="consent_missing",
        )
        records = scoreboard.read_gate_verdict_records(
            runtime_conn,
            tenant_id=T1,
            actor_id=orch,
            now=CLOCK,
        )
    finally:
        runtime_conn.rollback()

    artifact = scoreboard.build_takeover_scoreboard(
        verdict_records=records,
        accounts_in_scope=4,
    ).to_dict()
    row = next(row for row in artifact["rows"] if row["category"] == "cs_record_update")
    metrics = {metric["name"]: metric for metric in row["metrics"]}

    assert len(records) == 2
    assert metrics["verdict_mix"]["status"] == "measured"
    assert metrics["verdict_mix"]["value"]["approve"] == {"count": 1, "share": 0.5}
    assert metrics["verdict_mix"]["value"]["deny"] == {"count": 1, "share": 0.5}
    assert metrics["release_mix"]["value"]["per_action_review"] == {"count": 2, "share": 1.0}
    assert metrics["denial_taxonomy"]["value"] == {"consent_missing": 1}


def test_rejection_ledger_reasons_feed_denial_taxonomy():
    ledger = RejectionLedger()
    ledger.reject(
        tenant_id="tenant",
        account_id="account",
        factor_name="usage_below_target",
        motion="draft_customer_outreach",
        reason="handled offline",
        rejected_on_day=7,
        proposal_id="proposal",
    )

    artifact = scoreboard.build_takeover_scoreboard(
        verdict_records=(),
        rejection_ledger=ledger,
        accounts_in_scope=1,
    ).to_dict()
    metrics = {metric["name"]: metric for metric in artifact["book_rollup"]["metrics"]}

    assert metrics["denial_taxonomy"]["status"] == "measured"
    assert metrics["denial_taxonomy"]["value"] == {"handled offline": 1}


def test_takeover_scoreboard_writes_deterministic_json(tmp_path):
    output = tmp_path / "takeover_scoreboard.json"

    payload = scoreboard.build_fixture_scoreboard(output_path=output)
    on_disk = json.loads(output.read_text(encoding="utf-8"))

    assert payload == on_disk
    assert payload["artifact"] == "takeover_scoreboard"
    assert payload["book_rollup"]["metrics"]
    assert "MP-E graduation sampling audit records" in payload["instrumentation_gaps"]
    assert "VM-8-full outcome observation" in payload["instrumentation_gaps"]


def _seed_proposal_and_verdict(
    conn,
    *,
    actor_id: str,
    human_id: str,
    proposal_id: str,
    action: str,
    autonomy_tier: int,
    verdict: str,
    rationale: str,
) -> None:
    with session(conn, tenant_id=T1, actor_id=actor_id, now=CLOCK) as cur:
        payload_sha = hashlib.sha256(b"{}").hexdigest()
        cur.execute(
            "INSERT INTO action_proposal "
            "(proposal_id, tenant_id, actor_principal_id, intent, action, payload, "
            " payload_sha256, grounding_ref, autonomy_tier, required_permission, status) "
            "VALUES (%s, %s, %s, %s, %s, '{}'::jsonb, %s, %s, %s, %s, %s)",
            (
                proposal_id,
                T1,
                actor_id,
                "scoreboard_test",
                action,
                payload_sha,
                f"grounding:{proposal_id}",
                autonomy_tier,
                "customer.outreach.draft",
                "approved" if verdict == "approve" else "denied",
            ),
        )
        cur.execute(
            "INSERT INTO action_verdict "
            "(tenant_id, proposal_id, verdict, approved_payload_sha256, rationale, human_principal_id) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                T1,
                proposal_id,
                verdict,
                payload_sha if verdict == "approve" else None,
                rationale,
                human_id,
            ),
        )
