"""Apply the ratified v6 on_task_relevance boundary to the clean gold labels.

This is a rule-mechanical re-score, not a re-judgment: it re-scores on_task_relevance
using the SAME deterministic functions the judge enforces at scoring time
(`deterministic_assignments` + `quality_floors` in `deterministic_quality`), so the
gold and the judge cannot diverge on this line.

Two ratified rules (owner-approved 2026-07-02):
  * v6-ontask-deferral-floor: propose_customer_action + passive deferral with no
    concrete ask => on_task_relevance 1 (proposes no action = fails the disposition).
  * v6-internal-review-assignment: internal_review + grounded reason + null draft
    => on_task_relevance 3 (that IS the correct output for the disposition). The
    grounded precondition is verified per cell via the citation check; any cell that
    fails groundedness keeps its label.

Only on_task_relevance (and tone_fit, if a register floor fires — expected: none, since
gold already scores those 1) can change. priority is untouched here.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from eval.deterministic_quality import (
    ON_TASK_DIMENSION,
    TONE_DIMENSION,
    deterministic_assignments,
    quality_floors,
)

# Inlined (not imported from gold_slot_b_quality) so this mechanical JSONL re-score
# stays free of the DB/agent import chain — it needs neither.
_GOLD_DIR = Path(__file__).resolve().parent / "gold"
GOLD_PATH = _GOLD_DIR / "slot_b_quality.jsonl"
HARD_PATH = _GOLD_DIR / "slot_b_quality_hard.jsonl"
HARD_KEY_PATH = _GOLD_DIR / "slot_b_quality_hard_key.jsonl"
APPLY_REPORT_PATH = _GOLD_DIR / "v6_ontask_apply_report.json"
APPROVED_LABELER = "owner-approved-single-labeler-2026-07-02"
AMENDMENT_ID = "v6-ontask-boundary-2026-07-02"
PASSING_SCORE = 2  # mirrors eval.judge_csm.PASSING_SCORE; inlined to stay DB-free.
_DIMENSIONS = (
    "grounding_fidelity",
    "on_task_relevance",
    "account_specificity",
    "priority_fidelity",
    "tone_fit",
    "safety_boundary",
)

# Which mechanism decided a change, for the provenance trail.
_ASSIGNMENT_RULE = "v6-internal-review-assignment"
_FLOOR_RULE = "v6-ontask-deferral-floor"


def _read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def _deterministic_ontask_tone(request: dict, output: dict) -> dict[str, tuple[int, str]]:
    """Return {dimension: (score, rule)} for on_task/tone cells code decides.

    Assignment first (can set any score), then the down-only floor (only lowers).
    priority is intentionally excluded — this amendment touches the on_task line only.
    """

    decided: dict[str, tuple[int, str]] = {}
    for dim, det in deterministic_assignments(request, output).items():
        decided[dim] = (det.score, _ASSIGNMENT_RULE)
    for dim, det in quality_floors(request, output).items():
        current = decided.get(dim, (det.score + 1, ""))[0]
        if current > det.score:
            decided[dim] = (det.score, _FLOOR_RULE)
    return decided


def apply_v6_rescore(
    *,
    clean_path: Path = GOLD_PATH,
    hard_path: Path = HARD_PATH,
    hard_key_path: Path = HARD_KEY_PATH,
    report_path: Path = APPLY_REPORT_PATH,
    write: bool = True,
) -> dict:
    changed_cells: list[dict] = []
    conflicts: list[dict] = []
    rule_counts: Counter[str] = Counter()

    # --- clean layer: re-score human_labels ---
    clean_records = _read_jsonl(clean_path)
    for record in clean_records:
        labels = record.get("human_labels")
        if not labels:
            continue
        scores = labels["dimension_scores"]
        decided = _deterministic_ontask_tone(record["request"], record["output"])
        for dim in (ON_TASK_DIMENSION, TONE_DIMENSION):
            if dim not in decided:
                continue
            new_score, rule = decided[dim]
            previous = int(scores[dim])
            if previous == new_score:
                continue
            scores[dim] = new_score
            rule_counts[f"clean:{rule}:{previous}->{new_score}"] += 1
            changed_cells.append(
                {"layer": "clean", "candidate_id": record["candidate_id"], "dimension": dim,
                 "previous": previous, "final": new_score, "rule": rule}
            )
        labels["overall_pass"] = all(int(v) >= PASSING_SCORE for v in scores.values())
        labels["labeler"] = APPROVED_LABELER

    # --- hard layer: re-score expected_vector, but NEVER auto-pass an intended trap ---
    hard_records = {r["candidate_id"]: r for r in _read_jsonl(hard_path)}
    hard_key_records = _read_jsonl(hard_key_path)
    for key in hard_key_records:
        cid = key["candidate_id"]
        source = hard_records.get(cid)
        if source is None:
            continue
        ev = key["expected_vector"]
        intended = set(key.get("intended_failing_dimensions") or ())
        decided = _deterministic_ontask_tone(source["request"], source["output"])
        for dim in (ON_TASK_DIMENSION, TONE_DIMENSION):
            if dim not in decided:
                continue
            new_score, rule = decided[dim]
            previous = int(ev[dim])
            if previous == new_score:
                continue
            # Conflict guard: refuse to lift an intended failing dimension to a pass.
            if dim in intended and new_score >= PASSING_SCORE:
                conflicts.append(
                    {"layer": "hard", "candidate_id": cid, "dimension": dim,
                     "expected": previous, "deterministic": new_score, "rule": rule,
                     "note": "deterministic rule would pass an INTENDED failing dim; left unchanged for owner review"}
                )
                continue
            ev[dim] = new_score
            rule_counts[f"hard:{rule}:{previous}->{new_score}"] += 1
            changed_cells.append(
                {"layer": "hard", "candidate_id": cid, "dimension": dim,
                 "previous": previous, "final": new_score, "rule": rule}
            )
        key["intended_failing_dimensions"] = [d for d in _DIMENSIONS if int(ev[d]) < PASSING_SCORE]

    if write:
        _write_jsonl(clean_path, clean_records)
        _write_jsonl(hard_key_path, hard_key_records)

    report = {
        "artifact": "slot_b_v6_ontask_apply_report",
        "amendment_id": AMENDMENT_ID,
        "date": "2026-07-02",
        "description": "mechanical re-score of on_task_relevance under ratified v6 boundary (clean + hard)",
        "clean_path": str(clean_path),
        "hard_key_path": str(hard_key_path),
        "approved_labeler": APPROVED_LABELER,
        "rules": {
            _ASSIGNMENT_RULE: "internal_review + grounded reason + null draft => on_task 3 (citation-verified per cell)",
            _FLOOR_RULE: "propose_customer_action + passive deferral, no concrete ask => on_task 1",
        },
        "changed_cell_count": len(changed_cells),
        "conflict_count": len(conflicts),
        "rule_counts": dict(sorted(rule_counts.items())),
        "changed_cells": sorted(changed_cells, key=lambda c: (c["layer"], c["rule"], c["candidate_id"])),
        "conflicts": conflicts,
        "claim_boundary": {
            "mechanical_rescore": True,
            "same_code_as_judge": True,
            "judge_prompt_changed_elsewhere": True,
            "single_labeler": True,
            "self_consistency_recheck_needed": False,
            "intended_traps_preserved": len(conflicts) == 0,
        },
    }
    if write:
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", default=str(GOLD_PATH))
    parser.add_argument("--report", default=str(APPLY_REPORT_PATH))
    parser.add_argument("--dry-run", action="store_true", help="report changes without writing")
    args = parser.parse_args(argv)
    report = apply_v6_rescore(
        clean_path=Path(args.clean), report_path=Path(args.report), write=not args.dry_run
    )
    print(f"v6 on_task re-score: {report['changed_cell_count']} cells  {report['rule_counts']}")
    if args.dry_run:
        print("(dry run — no files written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
