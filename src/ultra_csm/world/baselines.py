"""Deterministic baseline and power harness for the living world."""

from __future__ import annotations

from typing import Any

from eval.drift_power_csm import minimum_detectable_drop, required_n_per_arm
from ultra_csm.world.generator import WorldBuildResult
from ultra_csm.world.graph import ContextGraph


def build_baseline_report(result: WorldBuildResult, graph: ContextGraph) -> dict[str, Any]:
    decisions_by_id = {row.account_id: row for row in result.surface_decisions}
    health_by_id = {row.account_id: row for row in result.data.health_scores}
    adoption_by_id = {row.account_id: row for row in result.data.adoption_summaries}
    conflict_ids = {row.account_id for row in graph.conflict_nodes}
    open_cases_by_id = {
        fact.account_id: int(fact.value)
        for fact in graph.bitemporal_spine
        if fact.fact_key == "cases.open"
    }

    policies = {
        "never_surface": lambda account_id: False,
        "always_surface": lambda account_id: True,
        "health_only": lambda account_id: health_by_id[account_id].band == "red",
        "adoption_only": lambda account_id: adoption_by_id[account_id].adoption_rate < 0.45,
        "no_spine_ablation": lambda account_id: (
            health_by_id[account_id].band == "red"
            or adoption_by_id[account_id].adoption_rate < 0.45
        ),
        "spine_policy": lambda account_id: (
            health_by_id[account_id].band == "red"
            or adoption_by_id[account_id].adoption_rate < 0.45
            or (
                open_cases_by_id.get(account_id, 0) > 0
                and health_by_id[account_id].band == "red"
            )
            or (
                account_id in conflict_ids
                and decisions_by_id[account_id].surfaced
                and health_by_id[account_id].band == "red"
            )
        ),
    }
    scored = {
        name: _score_policy(result, policy)
        for name, policy in policies.items()
    }

    baseline_rate = scored["spine_policy"]["accuracy"]
    sample_n = len(result.latent_truth)
    return {
        "artifact": "living_world_baselines",
        "schema_version": 1,
        "n_accounts": sample_n,
        "policies": scored,
        "no_spine_ablation": {
            "full_spine_accuracy": scored["spine_policy"]["accuracy"],
            "no_spine_accuracy": scored["no_spine_ablation"]["accuracy"],
            "accuracy_delta": round(
                scored["spine_policy"]["accuracy"] - scored["no_spine_ablation"]["accuracy"],
                4,
            ),
        },
        "pass_k_handoff": {
            "built_not_executed": True,
            "recommended_command": (
                "ULTRA_CSM_LLM_TRANSPORT=claude_code "
                "python -m eval.world_scoreboard --seed 7 --scale 60 --pass-k 8 --model claude-sonnet-5"
            ),
            "reason": "Pass^k is metered and operator-owned by hard rule.",
        },
        "power_sizing": {
            "method": "existing_mdd_helpers_from_eval.drift_power_csm",
            "current_sample_n": sample_n,
            "minimum_detectable_drop_at_current_n": minimum_detectable_drop(
                baseline_rate,
                sample_n,
                sample_n,
            ),
            "required_n_per_arm": {
                "drop_10pp": required_n_per_arm(max(baseline_rate, 0.55), max(baseline_rate - 0.1, 0.05)),
                "drop_20pp": required_n_per_arm(max(baseline_rate, 0.55), max(baseline_rate - 0.2, 0.05)),
                "drop_30pp": required_n_per_arm(max(baseline_rate, 0.55), max(baseline_rate - 0.3, 0.05)),
            },
        },
    }


def _score_policy(result: WorldBuildResult, policy) -> dict[str, Any]:  # noqa: ANN001
    tp = fp = tn = fn = 0
    for latent in result.latent_truth:
        predicted = bool(policy(latent.account_id))
        actual = latent.doomed
        if predicted and actual:
            tp += 1
        elif predicted and not actual:
            fp += 1
        elif not predicted and actual:
            fn += 1
        else:
            tn += 1
    total = tp + fp + tn + fn
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "accuracy": round((tp + tn) / total, 4) if total else 0.0,
        "precision": round(tp / (tp + fp), 4) if (tp + fp) else 0.0,
        "recall": round(tp / (tp + fn), 4) if (tp + fn) else 0.0,
        "false_negative_rate": round(fn / (tp + fn), 4) if (tp + fn) else 0.0,
    }
