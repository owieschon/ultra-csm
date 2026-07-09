"""Takeover scoreboard read-only/tagging invariants."""

from __future__ import annotations

import inspect
import json

from eval import takeover_scoreboard
from eval.takeover_scoreboard import (
    AuditSignal,
    VerdictRow,
    build_scoreboard,
)
from ultra_csm.rejection_ledger import RejectionLedger


def test_takeover_scoreboard_writes_honest_status_tags(tmp_path):
    rejection_path = tmp_path / "week1_rejections_test.json"
    RejectionLedger(rejection_path).reject(
        tenant_id="tenant",
        account_id="acct",
        factor_name="usage_plateau",
        motion="draft_customer_outreach",
        reason="consent_missing",
        rejected_on_day=7,
        proposal_id="proposal-1",
    )
    output = tmp_path / "takeover_scoreboard.json"

    artifact = build_scoreboard(
        output_path=output,
        verdict_rows=(
            VerdictRow(
                proposal_id="proposal-1",
                category="draft_customer_outreach",
                action="draft_customer_outreach",
                autonomy_tier=2,
                release_condition="human_approve_with_consent",
                verdict="deny",
            ),
            VerdictRow(
                proposal_id="proposal-2",
                category="draft_customer_outreach",
                action="draft_customer_outreach",
                autonomy_tier=2,
                release_condition="human_approve_with_consent",
                verdict="approve",
            ),
        ),
        audit_signals=(
            AuditSignal(
                event_type="reobserve.result",
                category="draft_customer_outreach",
                account_ref="acct",
                payload={"outcome_state": "known"},
            ),
        ),
        rejection_paths=(rejection_path,),
        verdict_source_available=True,
        audit_source_available=True,
    )

    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8")) == artifact
    row = _row(artifact, "draft_customer_outreach")
    metrics = row["metrics"]
    assert metrics["verdict_mix"] == {
        "status": "measured",
        "value": {
            "total": 2,
            "counts": {"deny": 1, "approve": 1},
            "rates": {"approve": 0.5, "deny": 0.5},
        },
        "source": "action_proposal JOIN action_verdict",
    }
    assert metrics["human_minutes_per_account_week"]["status"] == "modeled"
    assert metrics["human_minutes_per_account_week"]["value"]["human_minutes"] == 5.0
    assert metrics["denial_taxonomy"]["value"] == {
        "total": 1,
        "reasons": {"consent_missing": 1},
    }
    assert metrics["outcome_reconciliation_coverage"]["value"]["observed_rate"] == 1.0
    assert metrics["coverage"]["status"] == "not_instrumented"
    assert metrics["coverage"]["value"] is None


def test_takeover_scoreboard_missing_sources_are_not_zero(tmp_path):
    artifact = build_scoreboard(
        output_path=tmp_path / "takeover_scoreboard.json",
        verdict_rows=(),
        audit_signals=(),
        rejection_records=(),
    )

    for row in artifact["rows"]:
        for metric in row["metrics"].values():
            assert metric["status"] in {"measured", "modeled", "not_instrumented"}
            if metric["status"] == "not_instrumented":
                assert metric["value"] is None


def test_takeover_scoreboard_imports_no_gate_or_rejection_write_path():
    source = inspect.getsource(takeover_scoreboard)

    assert "ActionGate" not in source
    assert "record_audit_event" not in source
    assert ".reject(" not in source


def _row(artifact: dict, category: str) -> dict:
    return next(row for row in artifact["rows"] if row["category"] == category)
