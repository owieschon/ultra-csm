"""R3/R4: no-spine ablation, operated with the adopted writer (OA-Q1).

Compares two DETERMINISTIC surfacing policies already defined in
``ultra_csm.world.baselines`` -- ``spine_policy`` (uses the context graph's
bitemporal facts and conflict nodes) vs ``no_spine_ablation`` (health/adoption
only) -- on two axes:

1. Deterministic latent-truth accuracy (does the policy's surfaced/not-surfaced
   call match ``latent.doomed``), with a Wilson 95% CI and a McNemar exact
   paired significance test between the two policies (paired by account_id --
   both policies score the SAME accounts, so a paired test is the correct one,
   reusing ``eval.judge_model_migration._mcnemar_exact_p_value`` rather than
   re-deriving it).
2. Live LLM draft quality for each policy's surfaced, world-actionable
   accounts, using the OA-Q1 adopted writer (claude-sonnet-5) for BOTH arms --
   so the comparison isolates policy architecture, not model -- graded by the
   same scoped judge and pass^k=3 gate ``eval.writer_bakeoff`` already
   implements. This module builds a different ``Scenario`` set (world-surfaced
   accounts, not the curated gold families) and calls
   ``eval.writer_bakeoff.run_arm`` unmodified.

World seed is fixed at 1 (the dispatch's stated seed for this operate step,
distinct from the scoreboard's default seed 7). Scale is power-sized from
``eval.drift_power_csm.required_n_per_arm`` against the observed spine_policy
accuracy, matching the sizing method ``baselines.py`` already documents.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from eval.drift_power_csm import required_n_per_arm
from eval.judge_model_migration import _mcnemar_exact_p_value
from eval.stochastic_csm import wilson_pass_rate_band
from eval.writer_bakeoff import PASS_K, Scenario, run_arm
from ultra_csm.agent1.sweep import build_reason_draft_request_for_account
from ultra_csm.data_plane.fixtures import DEFAULT_TENANT
from ultra_csm.world import WorldConfig, build_context_graph, generate_world
from ultra_csm.world.baselines import _score_policy, build_policy_table
from ultra_csm.world.generator import WorldBuildResult, build_data_plane

REPORT_PATH = Path(__file__).resolve().parent / "gold" / "no_spine_ablation_report.json"

WORLD_SEED = 1
ADOPTED_WRITER_MODEL_ID = "claude-sonnet-5"  # OA-Q1, docs/OA_Q1_WRITER_ADOPTION.md
ARM_POLICIES = ("spine_policy", "no_spine_ablation")
MDD_BASELINE_RATE = 0.80
DEFAULT_DROP_PP = 0.20
AS_OF = "2027-06-21"  # day 365, latest possible fixture state -- matches eval/canary_battery.py


def power_sized_scale(drop_pp: float = DEFAULT_DROP_PP, *, floor: int = 40) -> int:
    n = required_n_per_arm(MDD_BASELINE_RATE, MDD_BASELINE_RATE - drop_pp)
    return max(n, floor) if n is not None else floor


def build_world(scale: int) -> tuple[WorldBuildResult, Any]:
    result = generate_world(WorldConfig(seed=WORLD_SEED, scale=scale))
    graph = build_context_graph(result)
    return result, graph


def deterministic_comparison(result: WorldBuildResult, graph: Any) -> dict[str, Any]:
    policies = build_policy_table(result, graph)
    scored = {name: _score_policy(result, policies[name]) for name in ARM_POLICIES}
    for name, stats in scored.items():
        stats["accuracy_ci"] = wilson_pass_rate_band(stats["tp"] + stats["tn"], sum(
            stats[k] for k in ("tp", "fp", "tn", "fn")
        ))

    spine_fn = policies["spine_policy"]
    no_spine_fn = policies["no_spine_ablation"]
    b = c = 0  # McNemar: b = spine correct & no_spine wrong, c = spine wrong & no_spine correct
    for latent in result.latent_truth:
        actual = latent.doomed
        spine_correct = bool(spine_fn(latent.account_id)) == actual
        no_spine_correct = bool(no_spine_fn(latent.account_id)) == actual
        if spine_correct and not no_spine_correct:
            b += 1
        elif no_spine_correct and not spine_correct:
            c += 1
    p_value = _mcnemar_exact_p_value(b, c)
    verdict = "no-significant-difference"
    if p_value < 0.05 and b > c:
        verdict = "spine_significantly_more_accurate"
    elif p_value < 0.05 and c > b:
        verdict = "no_spine_significantly_more_accurate"

    return {
        "policies": scored,
        "mcnemar": {
            "method": "McNemar exact paired test",
            "spine_correct_no_spine_wrong": b,
            "no_spine_correct_spine_wrong": c,
            "discordant_total": b + c,
            "p_value": p_value,
            "alpha": 0.05,
            "verdict": verdict,
        },
    }


def build_scenario_set(result: WorldBuildResult, graph: Any, policy_name: str) -> tuple[Scenario, ...]:
    """Live drafting requests for accounts the named policy surfaces AND the
    world itself considers actionable (``recommended_action is not None``).
    The intersection avoids hand-deriving disposition for the internal_review/
    no-action case -- out of scope for this ablation, which tests whether
    surfacing catches doomed accounts, not internal-review drafting quality."""
    policy = build_policy_table(result, graph)[policy_name]
    decisions_by_id = {row.account_id: row for row in result.surface_decisions}
    data_plane = build_data_plane(result.data)
    scenarios: list[Scenario] = []
    for account in sorted(result.data.accounts, key=lambda row: row.account_id):
        decision = decisions_by_id[account.account_id]
        if not policy(account.account_id) or decision.recommended_action is None:
            continue
        request = build_reason_draft_request_for_account(
            data_plane,
            DEFAULT_TENANT,
            account.account_id,
            as_of=AS_OF,
            action=decision.recommended_action,
        )
        if request is None:
            continue
        scenarios.append(Scenario(f"{policy_name}-{account.account_id}", policy_name, request))
    return tuple(scenarios)


def build_report(
    *,
    drop_pp: float = DEFAULT_DROP_PP,
    scale: int | None = None,
    pass_k: int = PASS_K,
    checkpoint_dir: Path | None = None,
) -> dict[str, Any]:
    world_scale = scale if scale is not None else power_sized_scale(drop_pp)
    result, graph = build_world(world_scale)

    comparison = deterministic_comparison(result, graph)

    arms: dict[str, Any] = {}
    for policy_name in ARM_POLICIES:
        scenarios = build_scenario_set(result, graph, policy_name)
        checkpoint_path = (
            checkpoint_dir / f"no_spine_ablation_{policy_name}.json" if checkpoint_dir else None
        )
        arm = run_arm(
            ADOPTED_WRITER_MODEL_ID,
            scenarios,
            pass_k=pass_k,
            checkpoint_path=checkpoint_path,
        )
        arm["gated_pass_rate_ci"] = wilson_pass_rate_band(
            round(arm["gated_pass_rate"] * arm["n_draws"]) if arm["n_draws"] else 0,
            arm["n_draws"],
        )
        arm["pass_k_rate_ci"] = wilson_pass_rate_band(
            round(arm["pass_k_rate"] * arm["n_scenarios"]) if arm["n_scenarios"] else 0,
            arm["n_scenarios"],
        )
        arms[policy_name] = arm

    return {
        "artifact": "no_spine_ablation_report",
        "schema_version": 1,
        "generated_by": "eval.no_spine_ablation",
        "world_seed": WORLD_SEED,
        "world_scale": world_scale,
        "power_sizing": {
            "method": "eval.drift_power_csm.required_n_per_arm",
            "baseline_rate": MDD_BASELINE_RATE,
            "drop_pp": drop_pp,
        },
        "adopted_writer_model_id": ADOPTED_WRITER_MODEL_ID,
        "note": (
            "Both LLM arms use the SAME writer model (OA-Q1 adopted: "
            "claude-sonnet-5) so the comparison isolates surfacing-policy "
            "architecture (spine vs no-spine), not model choice."
        ),
        "deterministic_latent_truth_comparison": comparison,
        "llm_arms": arms,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--drop-pp", type=float, default=DEFAULT_DROP_PP)
    parser.add_argument("--scale", type=int, default=None)
    parser.add_argument("--pass-k", type=int, default=PASS_K)
    parser.add_argument("--output", default=str(REPORT_PATH))
    parser.add_argument("--checkpoint-dir", default=".no_spine_ablation_checkpoints")
    args = parser.parse_args(argv)

    checkpoint_dir = Path(args.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(
        drop_pp=args.drop_pp,
        scale=args.scale,
        pass_k=args.pass_k,
        checkpoint_dir=checkpoint_dir,
    )
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    det = report["deterministic_latent_truth_comparison"]
    for name, stats in det["policies"].items():
        print(f"[deterministic] {name} accuracy={stats['accuracy']} ci={stats['accuracy_ci']}")
    print(f"[deterministic] mcnemar={det['mcnemar']}")
    for name, arm in report["llm_arms"].items():
        print(
            f"[llm] {name} n_scenarios={arm['n_scenarios']} "
            f"gated_pass_rate={arm['gated_pass_rate']} ci={arm['gated_pass_rate_ci']} "
            f"pass_k_rate={arm['pass_k_rate']} ci={arm['pass_k_rate_ci']}"
        )
    print(f"report -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
