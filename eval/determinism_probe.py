"""Step 0: prove (or refute) judge non-determinism cleanly, and quantify it.

The whole self-consistency case rested on a SINGLE observed flip of one case across
two runs — suggestive, not a measured flip rate. This probe runs the SAME payloads N
times against the FROZEN current judge prompt and reports, per case and per dimension,
the score distribution, the pass/fail flip rate, and the corpus repeatability. No human,
no key to the gold labels, leaks nothing. Output: eval/gold/determinism_probe.json.

Reads the determinism verdict straight off the data:
- repeatability == 1.0 everywhere  -> judge is effectively deterministic; the earlier
  "flip" was a stale-run/reporting artifact, and the N-run stack is unnecessary.
- some cases flip                  -> quantified per-call flip rate; THEN (and only then)
  calibrate aggregation N from these numbers, and flag p~=0.5 cases as indeterminate.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from eval.judge_csm import QUALITY_DIMENSIONS
from eval.judge_anthropic import AnthropicQualityJudge, overall_pass
from eval.run_quality_judge import load_hard

OUT_PATH = Path(__file__).resolve().parent / "gold" / "determinism_probe.json"

# A spread across the boundary, not just the flipper: a clean control, a clear pass, a
# clear fail, and the three boundary families where the gate actually lives. One case per
# family (first match) keeps the probe cheap while still characterising the noise floor.
DEFAULT_FAMILIES = [
    "H_control",            # the case that flipped — the headline question
    "H1_terse_correct",     # should be a stable pass
    "H6b_warm_but_generic", # should be a stable fail
    "H3a_mixed_soft_pass",  # boundary: should-pass, judge over-failed
    "H4a_boundary_two",     # boundary: should-pass, two soft dips
    "H4b_boundary_one",     # boundary: one factor short
]


# Where a family has several cases, pin the specific one whose behaviour is the question
# (the H_control case that flipped across runs), not just the first match.
PINNED_ID_SUFFIX = {"H_control": "068e7f8cb453"}


def _select(items: list[dict], families: list[str]) -> list[dict]:
    by_family: dict[str, dict] = {}
    for it in items:
        fam = it["family"]
        pin = PINNED_ID_SUFFIX.get(fam)
        if pin and it["candidate_id"].endswith(pin):
            by_family[fam] = it  # exact pin wins
        else:
            by_family.setdefault(fam, it)
    return [by_family[f] for f in families if f in by_family]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None)
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--families", nargs="*", default=DEFAULT_FAMILIES)
    parser.add_argument("--output", default=str(OUT_PATH))
    args = parser.parse_args(argv)

    judge = AnthropicQualityJudge(model_id=args.model)
    cases = _select(load_hard(), args.families)

    rows = []
    fully_repeatable = 0
    for it in cases:
        vectors = [judge.score_output(it["request"], it["output"]) for _ in range(args.runs)]
        per_dim = {}
        for d in QUALITY_DIMENSIONS:
            dist = Counter(v[d] for v in vectors)
            per_dim[d] = {
                "dist": dict(sorted(dist.items())),
                "modal": dist.most_common(1)[0][0],
                "n_distinct": len(dist),
            }
        passes = sum(1 for v in vectors if overall_pass(v))
        pass_rate = passes / args.runs
        # gate flips iff the N runs disagree on pass/fail
        gate_flipped = 0 < passes < args.runs
        if all(per_dim[d]["n_distinct"] == 1 for d in QUALITY_DIMENSIONS):
            fully_repeatable += 1
        rows.append({
            "candidate_id": it["candidate_id"],
            "family": it["family"],
            "runs": args.runs,
            "pass_rate": round(pass_rate, 3),
            "gate_flipped": gate_flipped,
            "per_dimension": per_dim,
        })

    report = {
        "artifact": "judge_determinism_probe",
        "model_id": judge.model_id,
        "runs_per_case": args.runs,
        "n_cases": len(rows),
        "fully_repeatable_cases": fully_repeatable,
        "corpus_repeatability": round(fully_repeatable / len(rows), 3) if rows else None,
        "any_gate_flip": any(r["gate_flipped"] for r in rows),
        "cases": rows,
    }
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"\nmodel={report['model_id']}  runs/case={args.runs}  "
          f"corpus_repeatability={report['corpus_repeatability']}  "
          f"any_gate_flip={report['any_gate_flip']}")
    for r in rows:
        flips = [d for d in QUALITY_DIMENSIONS if r["per_dimension"][d]["n_distinct"] > 1]
        flag = "  <<< GATE FLIPS" if r["gate_flipped"] else ""
        print(f"  {r['family']:24} pass_rate={r['pass_rate']:.2f}  "
              f"noisy_dims={flips or '—'}{flag}")
    print(f"\nprobe -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
