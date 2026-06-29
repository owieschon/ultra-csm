"""Head-to-head: terse single-shot judge vs CoT judge, each under N-run aggregation.

Measures the two "do better" levers together against the hard layer:
  terse@N  = current bare-score judge, aggregated over N runs
  cot@N    = reasoning-before-score judge, aggregated over N runs

Reports per arm: gate false_pos / false_neg vs the key, gate repeatability (how often
the N runs agree), exact-vector match, and the indeterminate set. Decision rule we care
about: cot should LOWER false_neg toward 0 AND raise gate_repeatability without blowing
up false_pos. Writes eval/gold/judge_compare.json.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.judge_anthropic import AnthropicQualityJudge
from eval.judge_nrun import aggregate, score_nrun_agreement
from eval.run_quality_judge import load_hard

OUT_PATH = Path(__file__).resolve().parent / "gold" / "judge_compare.json"


def run_arm(judge, items: list[dict], n: int) -> dict:
    scored = []
    for it in items:
        vectors = [judge.score_output(it["request"], it["output"]) for _ in range(n)]
        scored.append({
            "candidate_id": it["candidate_id"],
            "family": it["family"],
            "reference": it["reference"],
            "agg": aggregate(vectors),
        })
    report = score_nrun_agreement(scored)
    report["cases"] = scored
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--output", default=str(OUT_PATH))
    args = parser.parse_args(argv)

    items = load_hard()
    arms = {
        "terse@N": AnthropicQualityJudge(model_id=args.model, reasoning=False),
        "cot@N": AnthropicQualityJudge(model_id=args.model, reasoning=True),
    }
    out = {"model_id": next(iter(arms.values())).model_id, "runs_per_case": args.runs, "arms": {}}
    for name, judge in arms.items():
        out["arms"][name] = run_arm(judge, items, args.runs)

    Path(args.output).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"\nmodel={out['model_id']}  runs/case={args.runs}  (hard layer, n={out['arms']['terse@N']['n']})")
    print(f"{'arm':10} {'false_neg':>10} {'false_pos':>10} {'gate_repeat':>12} {'exact':>7} {'indeterminate':>14}")
    for name, r in out["arms"].items():
        print(f"{name:10} {r['false_neg']:>10} {r['false_pos']:>10} {r['gate_repeatability']:>12} "
              f"{r['exact_vector_match']:>7} {len(r['indeterminate_ids']):>14}")
    print(f"\ncompare -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
