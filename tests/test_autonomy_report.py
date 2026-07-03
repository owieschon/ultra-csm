from __future__ import annotations

import json

import pytest

from eval.autonomy_report import (
    DEFAULT_LEDGER_PATH,
    DEFAULT_POLICY_PATH,
    AutonomyPolicyError,
    build_autonomy_report,
)
from ultra_csm.governance.csm_actions import CSM_ACTION_SPECS


def test_autonomy_report_emits_deterministic_stats_and_proposals(tmp_path):
    output = tmp_path / "autonomy_report.json"
    before = CSM_ACTION_SPECS["log_crm_activity"].autonomy_tier

    artifact = build_autonomy_report(output_path=output)

    assert output.exists()
    assert artifact["claim_boundary"] == {
        "sim": True,
        "live": False,
        "promotion_artifacts_only": True,
        "mutates_tier_config": False,
    }
    stats = {item["action_type"]: item for item in artifact["action_stats"]}
    assert stats["draft_customer_outreach"]["n"] == 8
    assert stats["draft_customer_outreach"]["rates"] == {
        "approve": 0.75,
        "revise": 0.125,
        "deny": 0.125,
    }
    assert stats["draft_customer_outreach"]["rejection_reasons"] == {"consent_missing": 1}
    assert stats["edit_success_plan"]["revision_reasons"] == {
        "objective_wording": 1,
        "owner_confirmation_needed": 1,
    }
    proposals = {
        (item["proposal_type"], item["action_type"]): item
        for item in artifact["tier_change_proposals"]
    }
    assert proposals[("promotion", "log_crm_activity")]["proposed_tier"] == 1
    assert proposals[("demotion", "edit_success_plan")]["proposed_tier"] == 3
    assert all(item["artifact_only"] for item in artifact["tier_change_proposals"])
    assert CSM_ACTION_SPECS["log_crm_activity"].autonomy_tier == before


def test_autonomy_report_rejects_auto_apply_flag(tmp_path):
    with pytest.raises(AutonomyPolicyError, match="auto_apply is forbidden"):
        build_autonomy_report(output_path=tmp_path / "x.json", auto_apply=True)


def test_autonomy_report_rejects_policy_auto_apply(tmp_path):
    policy = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
    policy["auto_apply"] = True
    policy_path = tmp_path / "unsafe_policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(AutonomyPolicyError, match="auto_apply is forbidden"):
        build_autonomy_report(
            policy_path=policy_path,
            ledger_path=DEFAULT_LEDGER_PATH,
            output_path=tmp_path / "x.json",
        )
