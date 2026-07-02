"""Build a judge disagreement report for fast human label review.

The agreement artifact tells us which dimensions miss the gate; this report shows
the exact cases behind those misses. It is generated from the same clean and hard
gold layers as `run_quality_judge`, and it never edits labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Iterable

from eval.judge_csm import KAPPA_GATE, QUALITY_DIMENSIONS, weighted_cohen_kappa
from eval.judge_anthropic import AnthropicQualityJudge, JUDGE_PROMPT_VERSION, overall_pass
from eval.run_quality_judge import load_clean, load_hard

OUT_PATH = Path(__file__).resolve().parent / "gold" / "judge_disagreement_report.json"
AGREED_AUDIT_PATH = Path(__file__).resolve().parent / "gold" / "judge_agreed_audit.json"
AGREED_AUDIT_KEY_PATH = Path(__file__).resolve().parent / "gold" / "judge_agreed_audit_key.json"


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
            "allowed_buckets": [
                "label_error",
                "rubric_ambiguity",
                "judge_systematic_error",
                "dimension_conflation",
                "regenerate_candidate",
            ],
            "label_change": None,
            "rubric_change": None,
            "judge_prompt_change": None,
            "candidate_change": None,
            "notes": "",
        },
    }


def _audit_id(item: dict, dimension: str) -> str:
    raw = f"{item['layer']}:{item['candidate_id']}:{dimension}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"judge-audit-{digest}"


def _agreed_cell_candidates(items: Iterable[dict]) -> list[tuple[str, dict]]:
    cells = []
    for item in items:
        for dimension in QUALITY_DIMENSIONS:
            if item["reference"][dimension] == item["judge"][dimension]:
                cells.append((dimension, item))
    return sorted(
        cells,
        key=lambda cell: hashlib.sha256(
            f"{cell[1]['candidate_id']}:{cell[0]}".encode("utf-8")
        ).hexdigest(),
    )


def build_agreed_cell_audit(
    items: Iterable[dict],
    *,
    sample_size: int = 10,
    exclude_audit_ids: set[str] | None = None,
) -> tuple[dict, dict]:
    """Return a blind agreed-cell audit and a separate key.

    The labeler-facing artifact contains no reference scores, judge scores,
    judge reasons, family names, or quality variants. It is intentionally a
    second, smaller review path for cells the disagreement report does not show.
    """

    excluded = exclude_audit_ids or set()
    selected = [
        (dimension, item)
        for dimension, item in _agreed_cell_candidates(items)
        if _audit_id(item, dimension) not in excluded
    ][:sample_size]
    cards = []
    key = []
    for dimension, item in selected:
        audit_id = _audit_id(item, dimension)
        cards.append(
            {
                "audit_id": audit_id,
                "candidate_id": item["candidate_id"],
                "layer": item["layer"],
                "dimension_to_score": dimension,
                "request": _request_context(item["request"]),
                "output": _output_text(item["output"]),
                "human_score": None,
                "notes": "",
            }
        )
        key.append(
            {
                "audit_id": audit_id,
                "candidate_id": item["candidate_id"],
                "layer": item["layer"],
                "dimension": dimension,
                "reference_score": item["reference"][dimension],
                "judge_score": item["judge"][dimension],
            }
        )
    return (
        {
            "artifact": "slot_b_judge_agreed_cell_audit",
            "sample_size": len(cards),
            "blind": True,
            "excluded_previous_cards": len(excluded),
            "cards": cards,
            "claim_boundary": {
                "agreed_cells_sampled": True,
                "contains_reference_scores": False,
                "contains_judge_scores": False,
                "contains_judge_reasons": False,
            },
        },
        {
            "artifact": "slot_b_judge_agreed_cell_audit_key",
            "sample_size": len(key),
            "key_records": key,
        },
    )


def _report_from_scored_items(
    judge: AnthropicQualityJudge,
    items: list[dict],
) -> dict:
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
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "judge_reasoning": judge.reasoning,
        "kappa_gate": KAPPA_GATE,
        "summary": {
            "total_items_scored": len(items),
            "disagreement_items": len(rows),
            "agreed_cell_count": sum(
                1
                for item in items
                for dimension in QUALITY_DIMENSIONS
                if item["reference"][dimension] == item["judge"][dimension]
            ),
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
    return _report_from_scored_items(judge, items)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None)
    parser.add_argument("--layer", choices=("clean", "hard", "both"), default="both")
    parser.add_argument("--output", default=str(OUT_PATH))
    parser.add_argument("--audit-output", default=str(AGREED_AUDIT_PATH))
    parser.add_argument("--audit-key-output", default=str(AGREED_AUDIT_KEY_PATH))
    parser.add_argument("--audit-size", type=int, default=10)
    parser.add_argument(
        "--include-existing-audit",
        action="store_true",
        help="Allow reusing audit cards from an existing audit key output.",
    )
    parser.add_argument("--no-audit", action="store_true")
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

    raw_items = _layer_items(args.layer)
    if args.limit is not None:
        raw_items = raw_items[: args.limit]
    scored_items = _score_with_judge(judge, raw_items, progress=_progress)

    report = _report_from_scored_items(judge, scored_items)
    out_path = Path(args.output)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not args.no_audit:
        exclude_audit_ids = set()
        audit_key_output = Path(args.audit_key_output)
        if audit_key_output.exists() and not args.include_existing_audit:
            existing_key = json.loads(audit_key_output.read_text(encoding="utf-8"))
            exclude_audit_ids = {
                str(record.get("audit_id"))
                for record in existing_key.get("key_records", ())
            }
        audit, audit_key = build_agreed_cell_audit(
            scored_items,
            sample_size=args.audit_size,
            exclude_audit_ids=exclude_audit_ids,
        )
        Path(args.audit_output).write_text(
            json.dumps(audit, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        audit_key_output.write_text(
            json.dumps(audit_key, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

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
    if not args.no_audit:
        print(f"agreed audit -> {args.audit_output}")
        print(f"agreed audit key -> {args.audit_key_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
