"""One-off: regenerate judge_compare.json with ONLY the cot@N arm.

compare_judges.py's default run scores both terse@N and cot@N (2x cost) for
its own terse-vs-cot comparison narrative. judge_validation_status() only
ever reads the cot@N arm (HARD_ARM = "cot@N" in judge_validation.py) for the
actual hard-layer gate. Report 31's job is the v7->v8 grounding-anchor fix,
not re-litigating that comparison, so this scopes the live spend to the arm
the gate actually needs -- a deliberate, disclosed cost cut (K2: additive,
smallest fork), not a silent one. terse@N is left as whatever the last
compare_judges.py run wrote (stale relative to this run) -- the report
states this plainly.
"""
from __future__ import annotations

import json
import sys

from eval.compare_judges import OUT_PATH
from eval.judge_anthropic import AnthropicQualityJudge
from eval.judge_nrun import aggregate, score_nrun_agreement
from eval.run_quality_judge import load_hard

RUNS = 5
MAX_RETRIES = 5  # K7: transient parse/format hiccups, not a systemic bug


def _score_with_retry(judge, request, output):
    last_exc = None
    for _ in range(MAX_RETRIES):
        try:
            return judge.score_output(request, output)
        except ValueError as exc:
            last_exc = exc
    raise last_exc


def run_arm_retrying(judge, items: list[dict], n: int) -> dict:
    scored = []
    for it in items:
        vectors = [_score_with_retry(judge, it["request"], it["output"]) for _ in range(n)]
        scored.append({
            "candidate_id": it["candidate_id"],
            "family": it["family"],
            "reference": it["reference"],
            "agg": aggregate(vectors),
        })
    report = score_nrun_agreement(scored)
    report["cases"] = scored
    return report


def main() -> int:
    items = load_hard()
    judge = AnthropicQualityJudge(reasoning=True)
    cot_arm = run_arm_retrying(judge, items, RUNS)

    existing = json.loads(OUT_PATH.read_text(encoding="utf-8")) if OUT_PATH.exists() else {}
    existing["model_id"] = judge.model_id
    existing["runs_per_case"] = RUNS
    existing.setdefault("arms", {})
    existing["arms"]["cot@N"] = cot_arm
    OUT_PATH.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"cot@N: n={cot_arm['n']} false_neg={cot_arm.get('false_neg')} false_pos={cot_arm.get('false_pos')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
