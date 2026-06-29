"""Offline stochastic-eval skeleton for Agent 1 Time-to-Value cases.

Phase 2 establishes the repeated-run artifact shape and pass-rate band before
live LLM slots exist. The default runner is deterministic, socket-free, and does
not claim live model competence.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

SELECTED_AGENT1_CASE_IDS = (
    "sweep_reason_quality_acme",
    "sweep_reason_quality_globex",
    "sweep_reason_quality_initech",
    "sweep_reason_quality_cyberdyne_internal",
    "sweep_reason_quality_soylent_injection",
    "sweep_escalation_lane_wayne",
    "sweep_refusal_umbrella",
    "sweep_refusal_stark",
)
ARTIFACT_LABEL = (
    "deterministic offline stochastic skeleton; not live LLM competence evidence"
)
ARTIFACT_PATH = Path(__file__).with_name("stochastic_csm.json")


def wilson_pass_rate_band(passed: int, total: int, *, z: float = 1.96) -> dict[str, Any]:
    if total < 0 or passed < 0 or passed > total:
        raise ValueError("passed must be between 0 and total")
    if total == 0:
        return {
            "method": "wilson_score_interval_95",
            "passed": passed,
            "total": total,
            "point": 0.0,
            "lower": 0.0,
            "upper": 0.0,
        }

    phat = passed / total
    denominator = 1 + z * z / total
    center = (phat + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt((phat * (1 - phat) + z * z / (4 * total)) / total)
        / denominator
    )
    return {
        "method": "wilson_score_interval_95",
        "passed": passed,
        "total": total,
        "point": round(phat, 4),
        "lower": round(max(center - margin, 0.0), 4),
        "upper": round(min(center + margin, 1.0), 4),
    }


def build_stochastic_report(
    *,
    n_runs: int = 5,
    selected_case_ids: tuple[str, ...] = SELECTED_AGENT1_CASE_IDS,
    mode: str = "offline",
) -> dict[str, Any]:
    if n_runs < 1:
        raise ValueError("n_runs must be >= 1")
    if mode != "offline":
        raise NotImplementedError("live stochastic slots are reserved for Phase 3")

    cases = [
        _offline_case_report(case_id, case_index=index, n_runs=n_runs)
        for index, case_id in enumerate(selected_case_ids)
    ]
    passed = sum(run["passed"] for case in cases for run in case["runs"])
    total = sum(len(case["runs"]) for case in cases)

    return {
        "artifact": "stochastic_csm_skeleton",
        "schema_version": 1,
        "generated_by": "eval.stochastic_csm",
        "label": ARTIFACT_LABEL,
        "measurement_scope": (
            "Repeated-run report contract for selected Agent 1 cases. Offline "
            "mode measures skeleton determinism only; live judgment quality is "
            "not claimed until a live runner is wired later."
        ),
        "mode": mode,
        "selected_case_ids": list(selected_case_ids),
        "runs_per_case": n_runs,
        "pass_rate_band": wilson_pass_rate_band(passed, total),
        "book_sweep_surface": {
            "deterministic_scores_checked_elsewhere": True,
            "hard_gate": "H_reproducible",
            "llm_slot_scope": "reason phrasing and recommendation text only",
            "priority_scope": "deterministic spine, not model-authored",
        },
        "shipping_band": {
            "minimum_point_estimate": 0.8,
            "minimum_lower_bound": 0.7,
            "method": "pre-agent Phase 2 proposed band; enforce for live Agent 1 in Phase 3",
        },
        "live_extension": {
            "enabled": False,
            "requires_credentials": True,
            "planned_slot": "Agent 1 live LLM judgment runner",
            "status": "reserved_for_phase_3",
        },
        "cases": cases,
    }


def write_stochastic_report(path: Path = ARTIFACT_PATH, *, n_runs: int = 5) -> dict[str, Any]:
    artifact = build_stochastic_report(n_runs=n_runs)
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def _offline_case_report(case_id: str, *, case_index: int, n_runs: int) -> dict[str, Any]:
    runs = []
    for run_index in range(n_runs):
        runs.append(
            {
                "run_id": f"{case_id}::offline::{run_index + 1}",
                "case_id": case_id,
                "passed": True,
                "failure_cluster": None,
                "latency_ms": 0,
                "cost_usd": 0.0,
                "scorer": "offline_skeleton_contract",
                "deterministic_seed": case_index * 10_000 + run_index,
            }
        )
    passed = sum(run["passed"] for run in runs)
    return {
        "case_id": case_id,
        "runs": runs,
        "summary": {
            "passed": passed,
            "total": n_runs,
            "pass_rate_band": wilson_pass_rate_band(passed, n_runs),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--output", default=str(ARTIFACT_PATH))
    args = parser.parse_args(argv)
    artifact = write_stochastic_report(Path(args.output), n_runs=args.runs)
    print(
        "wrote "
        f"{args.output} "
        f"({len(artifact['selected_case_ids'])} cases x {artifact['runs_per_case']} runs)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
