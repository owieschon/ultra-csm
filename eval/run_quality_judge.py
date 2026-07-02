"""Run the Anthropic quality judge against both gold layers and report agreement.

Clean layer reference = the human labels. Hard layer reference = the held-out key's
`expected_vector` (designer intent; the judge never saw it). Kappa is reported
PER LAYER and never averaged — a judge can ace clean and miss the hard cases, and
that gap is the whole point. Also reports overall-pass false positives / false
negatives, and a per-family breakdown on the hard layer.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.deterministic_quality import DETERMINISTIC_DIMENSIONS
from eval.judge_csm import ORDINAL_SCORES, QUALITY_DIMENSIONS, weighted_cohen_kappa
from eval.judge_anthropic import AnthropicQualityJudge, JUDGE_PROMPT_VERSION, overall_pass
from eval.gold_slot_b_quality import GOLD_PATH, read_gold_label_candidates, read_gold_label_key
from eval.gold_slot_b_hard import HARD_PATH, HARD_KEY_PATH

REPORT_PATH = Path(__file__).resolve().parent / "gold" / "judge_agreement.json"


def load_clean() -> list[dict]:
    items = []
    for r in read_gold_label_candidates(GOLD_PATH):
        hl = r.get("human_labels")
        if hl is None:
            continue
        items.append({
            "candidate_id": r["candidate_id"],
            "request": r["request"],
            "output": r["output"],
            "reference": dict(hl["dimension_scores"]),
            "family": None,
        })
    return items


def load_hard() -> list[dict]:
    key = {k["candidate_id"]: k for k in read_gold_label_key(HARD_KEY_PATH)}
    items = []
    for r in read_gold_label_candidates(HARD_PATH):
        k = key[r["candidate_id"]]
        items.append({
            "candidate_id": r["candidate_id"],
            "request": r["request"],
            "output": r["output"],
            "reference": {d: int(s) for d, s in k["expected_vector"].items()},
            "family": k["quality_variant"],
        })
    return items


def run_judge(judge, items: list[dict], *, layer: str) -> list[dict]:
    total = len(items)
    for index, it in enumerate(items, start=1):
        family = it.get("family") or layer
        print(
            f"scoring {index}/{total} layer={layer} "
            f"family={family} id={it['candidate_id']}",
            flush=True,
        )
        it["judge"] = judge.score_output(it["request"], it["output"])
    return items


def score_agreement(items: list[dict]) -> dict:
    per_dim = {}
    for dim in QUALITY_DIMENSIONS:
        ref = [it["reference"][dim] for it in items]
        jud = [it["judge"][dim] for it in items]
        per_dim[dim] = round(weighted_cohen_kappa(ref, jud, labels=ORDINAL_SCORES), 3)

    false_pos, false_neg, exact = [], [], 0
    for it in items:
        ref_pass = overall_pass(it["reference"])
        jud_pass = overall_pass(it["judge"])
        exact += int(it["reference"] == it["judge"])
        if ref_pass and not jud_pass:
            false_pos.append(it["candidate_id"])  # gold says ok, judge fails it
        if jud_pass and not ref_pass:
            false_neg.append(it["candidate_id"])  # gold says bad, judge passes it (dangerous)

    judge_scored = {
        dimension: kappa
        for dimension, kappa in per_dim.items()
        if dimension not in DETERMINISTIC_DIMENSIONS
    }
    deterministic = {
        dimension: kappa
        for dimension, kappa in per_dim.items()
        if dimension in DETERMINISTIC_DIMENSIONS
    }

    return {
        "n": len(items),
        "per_dimension_kappa": per_dim,
        "judge_scored_per_dimension_kappa": judge_scored,
        "deterministic_per_dimension_kappa": deterministic,
        "min_dimension_kappa": round(min(per_dim.values()), 3) if per_dim else None,
        "min_judge_scored_dimension_kappa": round(min(judge_scored.values()), 3) if judge_scored else None,
        "exact_vector_match": exact,
        "overall_pass_false_positive": len(false_pos),
        "overall_pass_false_negative": len(false_neg),
        "false_positive_ids": false_pos,
        "false_negative_ids": false_neg,
    }


def by_family(items: list[dict]) -> dict:
    fams = {}
    for it in items:
        fam = it["family"]
        d = fams.setdefault(fam, {"n": 0, "pass_match": 0, "exact": 0})
        d["n"] += 1
        d["pass_match"] += int(overall_pass(it["reference"]) == overall_pass(it["judge"]))
        d["exact"] += int(it["reference"] == it["judge"])
    return dict(sorted(fams.items()))


def build_report(judge) -> dict:
    clean = run_judge(judge, load_clean(), layer="clean")
    hard = run_judge(judge, load_hard(), layer="hard")
    return {
        "artifact": "slot_b_judge_agreement",
        "model_id": judge.model_id,
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "deterministic_dimensions": list(DETERMINISTIC_DIMENSIONS),
        "clean_layer": score_agreement(clean),
        "hard_layer": {**score_agreement(hard), "by_family": by_family(hard)},
        "claim_boundary": {
            "judge_is_independent_of_authoring": True,
            "clean_reference": "human labels (pending approval)",
            "hard_reference": "held-out key expected_vector (designer intent)",
            "note": "Model agreement is reported only for judge-scored dimensions. Deterministic dimensions are checked separately.",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None)
    parser.add_argument("--output", default=str(REPORT_PATH))
    args = parser.parse_args(argv)

    judge = AnthropicQualityJudge(model_id=args.model)
    report = build_report(judge)
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for layer in ("clean_layer", "hard_layer"):
        s = report[layer]
        print(f"\n[{layer}]  n={s['n']}  min_judge_dim_kappa={s['min_judge_scored_dimension_kappa']}  "
              f"exact={s['exact_vector_match']}/{s['n']}  "
              f"false_pos={s['overall_pass_false_positive']}  false_neg={s['overall_pass_false_negative']}")
        for dim, k in s["judge_scored_per_dimension_kappa"].items():
            print(f"    {dim:22} kappa={k}")
        for dim, k in s["deterministic_per_dimension_kappa"].items():
            print(f"    {dim:22} deterministic_kappa={k}")
    print(f"\nreport -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
