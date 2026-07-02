"""Build a judge disagreement report for fast human label review.

The agreement artifact tells us which dimensions miss the gate; this report shows
the exact cases behind those misses. It is generated from the same clean and hard
gold layers as `run_quality_judge`, and it never edits labels.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Iterable

from eval.judge_csm import KAPPA_GATE, QUALITY_DIMENSIONS, weighted_cohen_kappa
from eval.judge_anthropic import AnthropicQualityJudge, overall_pass
from eval.run_quality_judge import load_clean, load_hard

OUT_PATH = Path(__file__).resolve().parent / "gold" / "judge_disagreement_report.json"


Progress = Callable[[int, int, dict], None]


def _score_with_judge(
    judge: AnthropicQualityJudge,
    items: list[dict],
    *,
    progress: Progress | None = None,
) -> list[dict]:
    scored = []
    total = len(items)
    for index, item in enumerate(items, start=1):
        if progress is not None:
            progress(index, total, item)
        copy = dict(item)
        judge_scores, judge_reasons = judge.score_output_with_reasons(
            copy["request"],
            copy["output"],
        )
        copy["judge"] = judge_scores
        copy["judge_reasons"] = judge_reasons
        scored.append(copy)
    return scored


def _layer_items(layer: str) -> list[dict]:
    if layer == "clean":
        return [{**item, "layer": "clean"} for item in load_clean()]
    if layer == "hard":
        return [{**item, "layer": "hard"} for item in load_hard()]
    if layer == "both":
        return _layer_items("clean") + _layer_items("hard")
    raise ValueError(f"unknown layer: {layer}")


def _dimension_kappas(items: Iterable[dict]) -> dict[str, float | None]:
    rows = list(items)
    if not rows:
        return {dimension: None for dimension in QUALITY_DIMENSIONS}
    kappas = {}
    for dimension in QUALITY_DIMENSIONS:
        reference = [item["reference"][dimension] for item in rows]
        judge = [item["judge"][dimension] for item in rows]
        kappas[dimension] = round(weighted_cohen_kappa(reference, judge), 3)
    return kappas


def _verdict(reference: dict[str, int], judge: dict[str, int]) -> str:
    reference_pass = overall_pass(reference)
    judge_pass = overall_pass(judge)
    if reference_pass and not judge_pass:
        return "false_positive"
    if judge_pass and not reference_pass:
        return "false_negative"
    if reference == judge:
        return "exact"
    return "score_delta"


def _output_text(output: dict) -> dict:
    return {
        "reason": output.get("reason"),
        "customer_draft": output.get("customer_draft"),
        "cited_evidence_ids": output.get("cited_evidence_ids", ()),
    }


def _request_context(request: dict) -> dict:
    return {
        "account_name": request.get("account_name"),
        "disposition": request.get("disposition"),
        "recommended_action": request.get("recommended_action"),
        "customer_contact_allowed": request.get("customer_contact_allowed"),
        "priority": request.get("priority"),
        "evidence": request.get("evidence", ()),
        "untrusted_text_fragments": request.get("untrusted_text_fragments", ()),
    }


def _review_row(item: dict) -> dict | None:
    reference = item["reference"]
    judge = item["judge"]
    disagree_dims = {
        dimension: {
            "reference": reference[dimension],
            "judge": judge[dimension],
            "judge_reason": item.get("judge_reasons", {}).get(dimension, ""),
        }
        for dimension in QUALITY_DIMENSIONS
        if reference[dimension] != judge[dimension]
    }
    if not disagree_dims:
        return None
    return {
        "candidate_id": item["candidate_id"],
        "layer": item["layer"],
        "family": item.get("family"),
        "verdict": _verdict(reference, judge),
        "disagree_dims": disagree_dims,
        "reference_scores": reference,
        "judge_scores": judge,
        "request": _request_context(item["request"]),
        "output": _output_text(item["output"]),
        "review_fields": {
            "bucket": None,
            "label_change": None,
            "rubric_change": None,
            "judge_prompt_change": None,
            "notes": "",
        },
    }


def build_report(
    judge: AnthropicQualityJudge,
    *,
    layer: str = "both",
    limit: int | None = None,
    progress: Progress | None = None,
) -> dict:
    raw_items = _layer_items(layer)
    if limit is not None:
        raw_items = raw_items[:limit]
    items = _score_with_judge(judge, raw_items, progress=progress)
    rows = [row for item in items if (row := _review_row(item)) is not None]
    by_layer: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        by_layer[item["layer"]].append(item)

    dim_counts = Counter()
    verdict_counts = Counter()
    family_counts = Counter()
    for row in rows:
        verdict_counts[row["verdict"]] += 1
        if row["family"]:
            family_counts[row["family"]] += 1
        for dimension in row["disagree_dims"]:
            dim_counts[dimension] += 1

    return {
        "artifact": "slot_b_judge_disagreement_report",
        "model_id": judge.model_id,
        "judge_reasoning": judge.reasoning,
        "kappa_gate": KAPPA_GATE,
        "summary": {
            "total_items_scored": len(items),
            "disagreement_items": len(rows),
            "disagreement_counts_by_dimension": dict(sorted(dim_counts.items())),
            "verdict_counts": dict(sorted(verdict_counts.items())),
            "hard_family_counts": dict(sorted(family_counts.items())),
            "kappa_by_layer": {
                name: _dimension_kappas(layer_items)
                for name, layer_items in sorted(by_layer.items())
            },
        },
        "claim_boundary": {
            "diagnostic_only": True,
            "labels_approved_by_report": False,
            "judge_validated": False,
        },
        "review_rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None)
    parser.add_argument("--layer", choices=("clean", "hard", "both"), default="both")
    parser.add_argument("--output", default=str(OUT_PATH))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--terse",
        action="store_true",
        help="Use terse judge output; default captures short judge reasons.",
    )
    args = parser.parse_args(argv)

    judge = AnthropicQualityJudge(model_id=args.model, reasoning=not args.terse)
    def _progress(index: int, total: int, item: dict) -> None:
        family = item.get("family") or "clean"
        print(
            f"scoring {index}/{total} "
            f"layer={item['layer']} family={family} id={item['candidate_id']}",
            flush=True,
        )

    report = build_report(judge, layer=args.layer, limit=args.limit, progress=_progress)
    out_path = Path(args.output)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = report["summary"]
    print(
        "disagreements="
        f"{summary['disagreement_items']}/{summary['total_items_scored']} "
        f"model={report['model_id']} reasoning={report['judge_reasoning']}"
    )
    for layer_name, kappas in summary["kappa_by_layer"].items():
        below_gate = {
            dimension: kappa
            for dimension, kappa in kappas.items()
            if kappa is not None and kappa < KAPPA_GATE
        }
        print(f"[{layer_name}] below_gate={below_gate}")
    print(f"report -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
