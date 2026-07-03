"""Evidence-derived judge validation status.

`judge_validated` is never a hand-flipped boolean: this module derives it from the
persisted evidence artifacts, recomputing the gate numbers from raw vectors where the
artifact carries them.

Gate (docs/DEMO_EXECUTION_PLAN.md §2 step 4, under the N-run methodology):
- clean layer (judge_agreement.json): every dimension's kappa >= 0.6 vs approved human
  labels, overall_pass false negatives == 0.
- hard layer (judge_compare.json, cot@N arm): per-dimension kappa of the N-run
  modal-aggregated vector vs the held-out key >= 0.6 on every dimension — recomputed
  here from the per-case vectors, not read from a stored summary — and aggregated
  overall_pass false negatives == 0.

The hard-layer gate instrument is N-run modal aggregation (eval/judge_nrun.py), not a
single call: single-run hard kappa on 36 rarely-failing items swings roughly +/-0.15
per run, so a single-run gate is a coin flip by construction. The claim boundary
reports this method explicitly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eval.judge_csm import PASSING_SCORE, QUALITY_DIMENSIONS, weighted_cohen_kappa

REPO = Path(__file__).resolve().parents[1]
AGREEMENT_PATH = REPO / "eval" / "gold" / "judge_agreement.json"
COMPARE_PATH = REPO / "eval" / "gold" / "judge_compare.json"
GATE_KAPPA = 0.6
HARD_ARM = "cot@N"
MIN_RUNS_PER_CASE = 3


def judge_validation_status(
    agreement_path: Path = AGREEMENT_PATH,
    compare_path: Path = COMPARE_PATH,
) -> dict[str, Any]:
    """Derive the judge-validation claim from the evidence artifacts on disk."""
    failures: list[str] = []
    agreement = _load(agreement_path, failures)
    compare = _load(compare_path, failures)
    if failures:
        return _status(False, failures, agreement, compare)

    clean = agreement.get("clean_layer") if isinstance(agreement, dict) else None
    if not isinstance(clean, dict):
        failures.append("agreement artifact has no clean_layer")
    else:
        kappas = clean.get("per_dimension_kappa")
        if not isinstance(kappas, dict):
            failures.append("clean_layer has no per_dimension_kappa")
        else:
            for dim in QUALITY_DIMENSIONS:
                value = kappas.get(dim)
                if not isinstance(value, (int, float)) or value < GATE_KAPPA:
                    failures.append(f"clean {dim} kappa {value} < {GATE_KAPPA}")
        if clean.get("overall_pass_false_negative") != 0:
            failures.append(
                f"clean false_neg {clean.get('overall_pass_false_negative')} != 0"
            )
        if not isinstance(clean.get("n"), int) or clean["n"] <= 0:
            failures.append("clean_layer has no cases")

    hard_kappas: dict[str, float] = {}
    hard_false_neg: list[str] = []
    hard_n = 0
    runs = compare.get("runs_per_case") if isinstance(compare, dict) else None
    arm = (
        compare.get("arms", {}).get(HARD_ARM)
        if isinstance(compare, dict)
        else None
    )
    cases = arm.get("cases") if isinstance(arm, dict) else None
    if not isinstance(runs, int) or runs < MIN_RUNS_PER_CASE:
        failures.append(f"compare runs_per_case {runs} < {MIN_RUNS_PER_CASE}")
    if not isinstance(cases, list) or not cases:
        failures.append(f"compare artifact has no {HARD_ARM} cases")
    else:
        hard_n = len(cases)
        try:
            for dim in QUALITY_DIMENSIONS:
                judge_col = [case["agg"]["vector"][dim] for case in cases]
                ref_col = [case["reference"][dim] for case in cases]
                hard_kappas[dim] = round(weighted_cohen_kappa(judge_col, ref_col), 3)
                if hard_kappas[dim] < GATE_KAPPA:
                    failures.append(f"hard {dim} kappa {hard_kappas[dim]} < {GATE_KAPPA}")
            for case in cases:
                ref_pass = all(
                    case["reference"][d] >= PASSING_SCORE for d in QUALITY_DIMENSIONS
                )
                agg_pass = all(
                    case["agg"]["vector"][d] >= PASSING_SCORE for d in QUALITY_DIMENSIONS
                )
                if agg_pass and not ref_pass:
                    hard_false_neg.append(str(case.get("candidate_id")))
        except (KeyError, TypeError) as exc:
            failures.append(f"compare cases malformed: {exc!r}")
        if hard_false_neg:
            failures.append(f"hard aggregated false negatives: {sorted(hard_false_neg)}")

    agreement_model = agreement.get("model_id") if isinstance(agreement, dict) else None
    compare_model = compare.get("model_id") if isinstance(compare, dict) else None
    if agreement_model != compare_model:
        failures.append(
            f"evidence model mismatch: agreement={agreement_model} compare={compare_model}"
        )
    prompt_version = (
        agreement.get("judge_prompt_version") if isinstance(agreement, dict) else None
    )
    if not prompt_version:
        failures.append("agreement artifact has no judge_prompt_version")

    return _status(
        not failures,
        failures,
        agreement,
        compare,
        hard_kappas=hard_kappas,
        hard_n=hard_n,
        agreement_path=agreement_path,
        compare_path=compare_path,
    )


def _status(
    validated: bool,
    failures: list[str],
    agreement: Any,
    compare: Any,
    *,
    hard_kappas: dict[str, float] | None = None,
    hard_n: int = 0,
    agreement_path: Path | None = None,
    compare_path: Path | None = None,
) -> dict[str, Any]:
    clean = agreement.get("clean_layer", {}) if isinstance(agreement, dict) else {}
    arm = compare.get("arms", {}).get(HARD_ARM, {}) if isinstance(compare, dict) else {}
    return {
        "validated": validated,
        "failures": sorted(failures),
        "method": {
            "clean_gate": "single-run per-dimension kappa vs approved human labels",
            "hard_gate": (
                f"per-dimension kappa of {HARD_ARM} N-run modal-aggregated vectors "
                "vs held-out key, recomputed from per-case vectors"
            ),
            "gate_kappa": GATE_KAPPA,
            "hard_arm": HARD_ARM,
            "runs_per_case": compare.get("runs_per_case") if isinstance(compare, dict) else None,
            "single_labeler": True,
            "judge_prompt_version": (
                agreement.get("judge_prompt_version") if isinstance(agreement, dict) else None
            ),
            "model_id": agreement.get("model_id") if isinstance(agreement, dict) else None,
        },
        "clean": {
            "n": clean.get("n"),
            "per_dimension_kappa": clean.get("per_dimension_kappa"),
            "false_neg": clean.get("overall_pass_false_negative"),
            "false_pos": clean.get("overall_pass_false_positive"),
        },
        "hard": {
            "n": hard_n,
            "per_dimension_kappa_aggregated": hard_kappas or {},
            "false_neg_aggregated": 0 if validated else None,
            "false_pos_aggregated": arm.get("false_pos"),
            "gate_repeatability": arm.get("gate_repeatability"),
            "indeterminate_ids": arm.get("indeterminate_ids"),
        },
        "evidence": {
            "agreement": _rel(agreement_path),
            "compare": _rel(compare_path),
        },
    }


def _load(path: Path, failures: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        failures.append(f"missing evidence artifact: {_rel(path)}")
    except (OSError, ValueError) as exc:
        failures.append(f"unreadable evidence artifact {_rel(path)}: {exc!r}")
    return None


def _rel(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return str(path)
