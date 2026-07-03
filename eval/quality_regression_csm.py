"""Offline semantic-quality regression checks for Slot B.

This runner tests the quality-eval machinery without live credentials. It uses
deterministic Slot B fixture candidates, a named degradation ladder, Wilson
bands, and a no-op negative control. Human-validated live judging remains a
separate gate; this artifact is explicit about that boundary.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from eval.judge_csm import (
    PASSING_SCORE,
    QUALITY_DIMENSIONS,
    QualityLabels,
    SlotBQualityCandidate,
    build_slot_b_quality_candidates,
    labels_from_scores,
)
from eval.judge_validation import judge_validation_status
from eval.stochastic_csm import wilson_pass_rate_band
from ultra_csm.agent1.slot_b import (
    ReasonDraftOutput,
    ReasonDraftRequest,
    SlotBEvidence,
    SlotBPriority,
    SlotBPriorityFactor,
    validate_reason_draft_output,
)

ARTIFACT_PATH = Path(__file__).with_name("quality_regression_csm.json")
SCHEMA_VERSION = 1
DEFAULT_RUNS_PER_CANDIDATE = 5
REGRESSION_THRESHOLD = 0.2


@dataclass(frozen=True)
class DegradationRung:
    name: str
    description: str
    structural_valid: bool
    expected_detection: bool
    score_overrides: Mapping[str, int]


DEGRADATION_LADDER = (
    DegradationRung(
        name="catastrophic",
        description=(
            "Output is structurally invalid. This preserves the old safety floor "
            "as one rung, not the full quality claim."
        ),
        structural_valid=False,
        expected_detection=True,
        score_overrides={dimension: 1 for dimension in QUALITY_DIMENSIONS},
    ),
    DegradationRung(
        name="moderate_missing_grounding",
        description=(
            "Output remains parseable but loses grounding and priority fidelity."
        ),
        structural_valid=True,
        expected_detection=True,
        score_overrides={
            "grounding_fidelity": 1,
            "priority_fidelity": 1,
        },
    ),
    DegradationRung(
        name="subtle_generic_reason",
        description=(
            "Output remains grounded enough to pass structure but becomes generic "
            "and loses account specificity."
        ),
        structural_valid=True,
        expected_detection=True,
        score_overrides={
            "account_specificity": 1,
        },
    ),
    DegradationRung(
        name="noop_equivalent",
        description=(
            "Benign equivalent rewrite. The specificity gate fails the eval if "
            "this rung is reported as a regression."
        ),
        structural_valid=True,
        expected_detection=False,
        score_overrides={},
    ),
)


def build_quality_regression_report(
    *,
    runs_per_candidate: int = DEFAULT_RUNS_PER_CANDIDATE,
    candidates: tuple[SlotBQualityCandidate, ...] | None = None,
) -> dict[str, Any]:
    if runs_per_candidate < 1:
        raise ValueError("runs_per_candidate must be >= 1")

    candidates = candidates or build_slot_b_quality_candidates()
    if not candidates:
        raise ValueError("at least one Slot B quality candidate is required")

    normal_runs = _runs_for_rung(
        candidates,
        rung=None,
        runs_per_candidate=runs_per_candidate,
    )
    normal = _summarize_runs("normal", normal_runs)
    rungs = [
        _summarize_rung(
            rung,
            _runs_for_rung(
                candidates,
                rung=rung,
                runs_per_candidate=runs_per_candidate,
            ),
            normal,
        )
        for rung in DEGRADATION_LADDER
    ]

    hard_failures = _hard_failures(rungs)
    judge_validation = judge_validation_status()
    artifact = {
        "artifact": "csm_quality_regression_offline",
        "schema_version": SCHEMA_VERSION,
        "generated_by": "eval.quality_regression_csm",
        "mode": "offline",
        "stores_full_text": False,
        "runs_per_candidate": runs_per_candidate,
        "candidate_count": len(candidates),
        "quality_dimensions": list(QUALITY_DIMENSIONS),
        "pass_threshold": PASSING_SCORE,
        "regression_threshold": REGRESSION_THRESHOLD,
        "measurement_scope": (
            "CI-safe semantic-quality eval mechanics for Slot B fixture outputs. "
            "This proves degradation-ladder sensitivity and no-op specificity "
            "offline; live semantic quality remains gated on human-label "
            "validation and credentialed model runs."
        ),
        "claim_boundary": {
            "offline_quality_mechanics_built": True,
            "human_validated_judge": judge_validation["validated"],
            "judge_validation_method": judge_validation["method"],
            "live_semantic_quality_proven": False,
            "runtime_behavior_changed": False,
            "next_gate": (
                "Prove live semantic quality on real tenant output."
                if judge_validation["validated"]
                else "Label the Slot B gold set, validate judge agreement at kappa >= "
                "0.6 per dimension, then run the live quality lane."
            ),
        },
        "normal": normal,
        "degradation_ladder": rungs,
        "sensitivity": _sensitivity(rungs),
        "specificity": _specificity(rungs),
        "power": {
            "method": "normal_approx_conservative_p_0_5_two_independent_rates",
            "minimum_detectable_drop_95": _minimum_detectable_drop_95(
                normal["overall"]["pass_rate_band"]["total"]
            ),
            "note": (
                "Offline fixture repeats prove the calculation path. Live power "
                "depends on the captured N and observed baseline pass rate."
            ),
        },
        "hard_ok": not hard_failures,
        "hard_failures": hard_failures,
    }
    return artifact


def write_quality_regression_report(
    path: Path = ARTIFACT_PATH,
    *,
    runs_per_candidate: int = DEFAULT_RUNS_PER_CANDIDATE,
) -> dict[str, Any]:
    artifact = build_quality_regression_report(
        runs_per_candidate=runs_per_candidate
    )
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def _runs_for_rung(
    candidates: tuple[SlotBQualityCandidate, ...],
    *,
    rung: DegradationRung | None,
    runs_per_candidate: int,
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for candidate in candidates:
        for run_index in range(runs_per_candidate):
            labels = _labels_for(candidate, rung)
            request = _request_from_candidate(candidate)
            output = _output_for_rung(candidate, rung)
            structural_valid = _structural_valid(request, output)
            run_passed = structural_valid and labels.overall_pass
            failure_clusters = _failure_clusters(
                labels,
                structural_valid=structural_valid,
            )
            runs.append(
                {
                    "run_id": (
                        f"{candidate.candidate_id}::"
                        f"{rung.name if rung else 'normal'}::{run_index + 1}"
                    ),
                    "candidate_id": candidate.candidate_id,
                    "structural_valid": structural_valid,
                    "overall_pass": run_passed,
                    "dimension_scores": labels.dimension_scores,
                    "failure_clusters": failure_clusters,
                    "output_hash": _stable_output_hash(output),
                    "text_stored": False,
                }
            )
    return runs


def _labels_for(
    candidate: SlotBQualityCandidate,
    rung: DegradationRung | None,
) -> QualityLabels:
    scores = {dimension: 3 for dimension in QUALITY_DIMENSIONS}
    if rung is not None:
        scores.update(rung.score_overrides)
    return labels_from_scores(
        candidate.candidate_id,
        scores,
        labeler=f"offline-quality-{rung.name if rung else 'normal'}",
    )


def _request_from_candidate(candidate: SlotBQualityCandidate) -> ReasonDraftRequest:
    raw = candidate.request
    return ReasonDraftRequest(
        tenant_id=raw["tenant_id"],
        account_id=raw["account_id"],
        account_name=raw["account_name"],
        disposition=raw["disposition"],
        recommended_action=raw["recommended_action"],
        customer_contact_allowed=raw["customer_contact_allowed"],
        priority=SlotBPriority(
            score=raw["priority"]["score"],
            factors=tuple(
                SlotBPriorityFactor(
                    name=factor["name"],
                    value=factor["value"],
                    contribution=factor["contribution"],
                )
                for factor in raw["priority"]["factors"]
            ),
        ),
        evidence=tuple(
            SlotBEvidence(
                source=evidence["source"],
                source_id=evidence["source_id"],
                field=evidence["field"],
                observed_at=evidence["observed_at"],
            )
            for evidence in raw["evidence"]
        ),
        as_of=raw["as_of"],
        contact_name=raw.get("contact_name"),
        contact_email=raw.get("contact_email"),
        untrusted_text_fragments=tuple(raw.get("untrusted_text_fragments", ())),
    )


def _output_for_rung(
    candidate: SlotBQualityCandidate,
    rung: DegradationRung | None,
) -> ReasonDraftOutput:
    raw = candidate.output
    if rung is None or rung.name == "noop_equivalent":
        return ReasonDraftOutput(
            reason=raw["reason"],
            cited_evidence_ids=tuple(raw["cited_evidence_ids"]),
            customer_draft=raw["customer_draft"],
            model_id=raw["model_id"],
            prompt_version=raw["prompt_version"],
        )

    cited = tuple(raw["cited_evidence_ids"])
    first_evidence = cited[0] if cited else ""
    if rung.name == "catastrophic":
        return ReasonDraftOutput(
            reason="",
            cited_evidence_ids=(),
            customer_draft=None,
            model_id=raw["model_id"],
            prompt_version=raw["prompt_version"],
        )
    if rung.name == "moderate_missing_grounding":
        draft = (
            "Hi, can we review next steps for onboarding?"
            if raw["customer_draft"] is not None
            else None
        )
        return ReasonDraftOutput(
            reason=(
                "This account needs attention based on the available signals. "
                f"Evidence [evidence:{first_evidence}]."
            ),
            cited_evidence_ids=(first_evidence,),
            customer_draft=draft,
            model_id=raw["model_id"],
            prompt_version=raw["prompt_version"],
        )
    if rung.name == "subtle_generic_reason":
        draft = (
            "Hi, I wanted to check in and align on the next best step."
            if raw["customer_draft"] is not None
            else None
        )
        return ReasonDraftOutput(
            reason=(
                "The account has a customer-success risk that should be handled "
                f"soon. Evidence [evidence:{first_evidence}]."
            ),
            cited_evidence_ids=(first_evidence,),
            customer_draft=draft,
            model_id=raw["model_id"],
            prompt_version=raw["prompt_version"],
        )
    raise ValueError(f"unknown degradation rung: {rung.name}")


def _structural_valid(
    request: ReasonDraftRequest,
    output: ReasonDraftOutput,
) -> bool:
    try:
        validate_reason_draft_output(request, output)
    except Exception:
        return False
    return True


def _failure_clusters(
    labels: QualityLabels,
    *,
    structural_valid: bool,
) -> list[str]:
    if not structural_valid:
        return ["structural_contract_failure"]
    return [
        f"quality:{dimension}"
        for dimension, score in labels.dimension_scores.items()
        if score < PASSING_SCORE
    ]


def _summarize_rung(
    rung: DegradationRung,
    runs: list[dict[str, Any]],
    normal: dict[str, Any],
) -> dict[str, Any]:
    summary = _summarize_runs(rung.name, runs)
    normal_rate = normal["overall"]["pass_rate_band"]["point"]
    rung_rate = summary["overall"]["pass_rate_band"]["point"]
    drop = round(normal_rate - rung_rate, 4)
    detected = bool(
        summary["overall"]["structural_failures"] > 0
        or drop >= REGRESSION_THRESHOLD
    )
    specificity_gate_passed = (
        True if rung.expected_detection else not detected and drop == 0.0
    )
    summary.update(
        {
            "description": rung.description,
            "expected_detection": rung.expected_detection,
            "detected": detected,
            "drop_vs_normal": drop,
            "specificity_gate_passed": specificity_gate_passed,
        }
    )
    return summary


def _summarize_runs(name: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(runs)
    passed = sum(1 for run in runs if run["overall_pass"])
    structural_failures = sum(1 for run in runs if not run["structural_valid"])
    by_dimension = {}
    for dimension in QUALITY_DIMENSIONS:
        dimension_passed = sum(
            1
            for run in runs
            if run["structural_valid"]
            and run["dimension_scores"][dimension] >= PASSING_SCORE
        )
        by_dimension[dimension] = {
            "pass_rate_band": wilson_pass_rate_band(dimension_passed, total),
            "failure_count": total - dimension_passed,
        }

    clusters: dict[str, int] = {}
    for run in runs:
        for cluster in run["failure_clusters"]:
            clusters[cluster] = clusters.get(cluster, 0) + 1

    return {
        "name": name,
        "overall": {
            "pass_rate_band": wilson_pass_rate_band(passed, total),
            "structural_failures": structural_failures,
        },
        "by_dimension": by_dimension,
        "failure_clusters": dict(sorted(clusters.items())),
        "runs": runs,
    }


def _sensitivity(rungs: list[dict[str, Any]]) -> dict[str, Any]:
    detection_rungs = [rung for rung in rungs if rung["expected_detection"]]
    caught = [rung["name"] for rung in detection_rungs if rung["detected"]]
    missed = [rung["name"] for rung in detection_rungs if not rung["detected"]]
    floor = caught[-1] if caught else None
    return {
        "caught_rungs": caught,
        "missed_rungs": missed,
        "subtlety_floor": floor,
        "passed": not missed,
    }


def _specificity(rungs: list[dict[str, Any]]) -> dict[str, Any]:
    controls = [rung for rung in rungs if not rung["expected_detection"]]
    false_alarms = [rung["name"] for rung in controls if rung["detected"]]
    return {
        "negative_controls": [rung["name"] for rung in controls],
        "false_alarms": false_alarms,
        "passed": not false_alarms,
    }


def _hard_failures(rungs: list[dict[str, Any]]) -> list[str]:
    failures = []
    for rung in rungs:
        if rung["expected_detection"] and not rung["detected"]:
            failures.append(f"missed_expected_degradation:{rung['name']}")
        if not rung["expected_detection"] and rung["detected"]:
            failures.append(f"false_alarm_negative_control:{rung['name']}")
    return failures


def _minimum_detectable_drop_95(total: int) -> float:
    if total <= 0:
        return 1.0
    return round(min(1.0, 1.96 * math.sqrt(0.5 * 0.5 * 2 / total)), 4)


def _stable_output_hash(output: ReasonDraftOutput) -> str:
    import hashlib

    payload = json.dumps(
        {
            "cited_evidence_ids": list(output.cited_evidence_ids),
            "customer_draft": output.customer_draft,
            "model_id": output.model_id,
            "prompt_version": output.prompt_version,
            "reason": output.reason,
        },
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS_PER_CANDIDATE)
    parser.add_argument("--output", default=str(ARTIFACT_PATH))
    args = parser.parse_args(argv)

    artifact = write_quality_regression_report(
        Path(args.output),
        runs_per_candidate=args.runs,
    )
    print(
        "CSM quality regression: "
        f"hard_ok={artifact['hard_ok']} "
        f"sensitivity={artifact['sensitivity']['passed']} "
        f"specificity={artifact['specificity']['passed']}"
    )
    print(f"quality regression JSON -> {args.output}")
    return 0 if artifact["hard_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
