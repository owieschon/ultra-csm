"""Per-case judge-vs-key dump for the hard layer, to calibrate the judge rubric.

Not a gate. Runs the live judge on every hard case and writes, per case, the
judge's six-dim vector beside the key's expected_vector and the
disagreeing dimensions. Reading this tells us exactly where the rubric is
mis-thresholded (1-vs-2 boundary), instead of guessing from aggregates.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.judge_csm import QUALITY_DIMENSIONS
from eval.judge_anthropic import AnthropicQualityJudge, overall_pass
from eval.run_quality_judge import load_hard

OUT_PATH = Path(__file__).resolve().parent / "gold" / "judge_diagnosis.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None)
    parser.add_argument("--output", default=str(OUT_PATH))
    args = parser.parse_args(argv)

    judge = AnthropicQualityJudge(model_id=args.model)
    items = load_hard()
    rows = []
    for it in items:
        jv = judge.score_output(it["request"], it["output"])
        ref = it["reference"]
        disagree = {d: [ref[d], jv[d]] for d in QUALITY_DIMENSIONS if ref[d] != jv[d]}
        ref_pass, jud_pass = overall_pass(ref), overall_pass(jv)
        verdict = "ok"
        if ref_pass and not jud_pass:
            verdict = "FALSE_POS"  # judge failed a should-pass
        elif jud_pass and not ref_pass:
            verdict = "FALSE_NEG"  # judge passed a should-fail
        rows.append({
            "candidate_id": it["candidate_id"],
            "family": it["family"],
            "verdict": verdict,
            "expected": ref,
            "judge": jv,
            "disagree_dims": disagree,
        })

    rows.sort(key=lambda r: (r["verdict"] == "ok", r["family"]))
    Path(args.output).write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for r in rows:
        tag = "" if r["verdict"] == "ok" else f"  <<< {r['verdict']}"
        print(f"{r['family']:28} {r['candidate_id'][-12:]}  diff={r['disagree_dims']}{tag}")
    print(f"\ndiagnosis -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
