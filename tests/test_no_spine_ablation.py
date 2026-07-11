"""Tests for the R3/R4 no-spine ablation harness (no live creds)."""

from __future__ import annotations

from unittest.mock import patch

from eval.no_spine_ablation import (
    ARM_POLICIES,
    build_report,
    build_scenario_set,
    build_world,
    deterministic_comparison,
    power_sized_scale,
)
from ultra_csm.world.baselines import build_policy_table

TEST_SCALE = 40


def test_power_sized_scale_respects_floor():
    assert power_sized_scale(drop_pp=0.20, floor=40) >= 40


def test_deterministic_comparison_matches_manual_scoring():
    result, graph = build_world(TEST_SCALE)
    comparison = deterministic_comparison(result, graph)

    assert set(comparison["policies"]) == set(ARM_POLICIES)
    for name, stats in comparison["policies"].items():
        total = stats["tp"] + stats["fp"] + stats["tn"] + stats["fn"]
        assert total == len(result.latent_truth)
        ci = stats["accuracy_ci"]
        assert ci["lower"] <= stats["accuracy"] <= ci["upper"]

    mcnemar = comparison["mcnemar"]
    assert mcnemar["discordant_total"] == (
        mcnemar["spine_correct_no_spine_wrong"] + mcnemar["no_spine_correct_spine_wrong"]
    )
    assert 0.0 <= mcnemar["p_value"] <= 1.0
    assert mcnemar["verdict"] in (
        "no-significant-difference",
        "spine_significantly_more_accurate",
        "no_spine_significantly_more_accurate",
    )


def test_scenario_set_only_covers_policy_surfaced_actionable_accounts():
    result, graph = build_world(TEST_SCALE)
    policies = build_policy_table(result, graph)
    decisions_by_id = {row.account_id: row for row in result.surface_decisions}

    for policy_name in ARM_POLICIES:
        scenarios = build_scenario_set(result, graph, policy_name)
        expected_ids = {
            account.account_id
            for account in result.data.accounts
            if policies[policy_name](account.account_id)
            and decisions_by_id[account.account_id].recommended_action is not None
        }
        got_ids = {s.scenario_id.removeprefix(f"{policy_name}-") for s in scenarios}
        # build_reason_draft_request_for_account can decline (e.g. no eligible
        # contact for draft_customer_outreach) -- the built set is a subset,
        # never a superset, of the policy-surfaced/actionable set.
        assert got_ids <= expected_ids
        assert all(s.family == policy_name for s in scenarios)


def test_scenario_ids_are_unique_and_stable_across_calls():
    result, graph = build_world(TEST_SCALE)
    first = build_scenario_set(result, graph, "spine_policy")
    second = build_scenario_set(result, graph, "spine_policy")
    assert [s.scenario_id for s in first] == [s.scenario_id for s in second]
    assert len({s.scenario_id for s in first}) == len(first)


def test_build_report_structure_with_stubbed_arms():
    """No live LLM calls: run_arm is stubbed. Verifies report assembly,
    including that both arms are told to use the SAME adopted writer model."""
    seen_model_ids = []

    def _fake_run_arm(model_id, scenarios, *, pass_k, checkpoint_path):
        seen_model_ids.append(model_id)
        return {
            "model_id": model_id,
            "n_scenarios": len(scenarios),
            "pass_k": pass_k,
            "n_draws": len(scenarios) * pass_k,
            "gated_pass_rate": 1.0,
            "pass_k_rate": 1.0,
        }

    with patch("eval.no_spine_ablation.run_arm", side_effect=_fake_run_arm):
        report = build_report(scale=TEST_SCALE, checkpoint_dir=None)

    assert set(report["llm_arms"]) == set(ARM_POLICIES)
    assert len(set(seen_model_ids)) == 1
    assert seen_model_ids[0] == "claude-sonnet-5"
    for arm in report["llm_arms"].values():
        assert "gated_pass_rate_ci" in arm
        assert "pass_k_rate_ci" in arm
    assert report["world_seed"] == 1
    assert report["deterministic_latent_truth_comparison"]["mcnemar"]["p_value"] is not None
