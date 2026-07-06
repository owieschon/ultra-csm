"""Drift-detection power analysis for the Slot B quality judge.

This is deliberately an analysis over the committed, human-labeled gold set,
not a new labeling or prompt-tuning pass. The question is: given the current
validated judge/gold substrate, what quality drop can the eval honestly detect?
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from eval.gold_slot_b_quality import GOLD_PATH, KEY_PATH, read_gold_label_candidates, read_gold_label_key
from eval.judge_csm import PASSING_SCORE, QUALITY_DIMENSIONS
from eval.judge_validation import judge_validation_status
from eval.stochastic_csm import wilson_pass_rate_band

ARTIFACT_PATH = Path(__file__).with_name("drift_power_csm.json")
SCHEMA_VERSION = 1
BASELINE_VARIANT = "control_good"
NOOP_VARIANT = "noop_equivalent"
ALPHA = 0.05
TARGET_POWER = 0.8


def build_drift_power_report(
    *,
    gold_path: Path = GOLD_PATH,
    key_path: Path = KEY_PATH,
) -> dict[str, Any]:
    rows = {row["candidate_id"]: row for row in read_gold_label_candidates(gold_path)}
    key_rows = list(read_gold_label_key(key_path))
    by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for key in key_rows:
        row = rows[key["candidate_id"]]
        by_variant[key["quality_variant"]].append(row)

    if BASELINE_VARIANT not in by_variant:
        raise ValueError(f"missing baseline variant {BASELINE_VARIANT!r}")

    baseline = _summarize_variant(BASELINE_VARIANT, by_variant[BASELINE_VARIANT])
    rungs = [
        _compare_variant(baseline, _summarize_variant(name, by_variant[name]))
        for name in sorted(by_variant)
        if name != BASELINE_VARIANT
    ]
    noop = _noop_control(baseline)
    expected = [rung for rung in rungs if rung["expected_detection"]]
    missed = [rung["variant"] for rung in expected if not rung["detected"]]
    false_alarms = [noop["variant"]] if noop["detected"] else []
    current_n = baseline["n"]
    min_drop = minimum_detectable_drop(
        baseline["overall"]["pass_rate_band"]["point"],
        current_n,
        current_n,
        target_power=TARGET_POWER,
        alpha=ALPHA,
    )
    return {
        "artifact": "csm_drift_power",
        "schema_version": SCHEMA_VERSION,
        "generated_by": "eval.drift_power_csm",
        "mode": "offline_gold_power_analysis",
        "stores_full_text": False,
        "baseline_variant": BASELINE_VARIANT,
        "baseline": baseline,
        "degradation_ladder": rungs + [noop],
        "sensitivity": {
            "caught_rungs": [rung["variant"] for rung in expected if rung["detected"]],
            "missed_rungs": missed,
            "passed": not missed,
            "subtlety_floor": (
                "current gold ladder contains only 100 percentage-point overall-pass drops"
            ),
        },
        "specificity": {
            "negative_controls": [noop["variant"]],
            "false_alarms": false_alarms,
            "passed": not false_alarms,
        },
        "power": {
            "method": "one_sided_two_proportion_z_test_normal_approximation",
            "alpha": ALPHA,
            "target_power": TARGET_POWER,
            "current_independent_examples_per_arm": current_n,
            "minimum_detectable_drop_at_current_n": min_drop,
            "claim_supported": (
                f"At n={current_n} independent examples per arm, this eval supports "
                f"detection of about a {min_drop:.1%} or larger overall-pass-rate drop; "
                "smaller drift needs more independent examples."
            ),
            "required_n_per_arm": {
                "drop_10pp": required_n_per_arm(1.0, 0.9),
                "drop_20pp": required_n_per_arm(1.0, 0.8),
                "drop_50pp": required_n_per_arm(1.0, 0.5),
            },
        },
        "judge_validation": {
            "validated": judge_validation_status()["validated"],
            "method": judge_validation_status()["method"],
        },
        "claim_boundary": {
            "gold_labels_modified": False,
            "judge_prompt_modified": False,
            "overall_power_only": True,
            "single_labeler_caveat": True,
            "note": (
                "This establishes the current gold ladder's drift-detection power. "
                "It does not claim production retention-outcome drift or sub-threshold "
                "quality drift detection."
            ),
        },
        "hard_ok": not missed and not false_alarms,
        "hard_failures": [
            *(f"missed_expected_degradation:{name}" for name in missed),
            *(f"false_alarm_negative_control:{name}" for name in false_alarms),
        ],
    }


def write_drift_power_report(path: Path = ARTIFACT_PATH) -> dict[str, Any]:
    artifact = build_drift_power_report()
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def _summarize_variant(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    passed = [_overall_pass(row["human_labels"]["dimension_scores"]) for row in rows]
    by_dimension = {}
    for dimension in QUALITY_DIMENSIONS:
        dim_passed = sum(
            1
            for row in rows
            if row["human_labels"]["dimension_scores"][dimension] >= PASSING_SCORE
        )
        by_dimension[dimension] = {
            "pass_rate_band": wilson_pass_rate_band(dim_passed, len(rows)),
            "failure_count": len(rows) - dim_passed,
        }
    return {
        "variant": name,
        "n": len(rows),
        "overall": {
            "pass_count": sum(passed),
            "pass_rate_band": wilson_pass_rate_band(sum(passed), len(rows)),
        },
        "by_dimension": by_dimension,
        "candidate_ids": sorted(row["candidate_id"] for row in rows),
    }


def _compare_variant(baseline: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    p0 = baseline["overall"]["pass_rate_band"]["point"]
    p1 = variant["overall"]["pass_rate_band"]["point"]
    p_value = one_sided_two_proportion_p_value(
        baseline["overall"]["pass_count"],
        baseline["n"],
        variant["overall"]["pass_count"],
        variant["n"],
    )
    drop = round(p0 - p1, 4)
    return {
        **variant,
        "expected_detection": True,
        "drop_vs_baseline": drop,
        "p_value": p_value,
        "detected": p_value < ALPHA and drop > 0,
        "achieved_power_for_observed_drop": achieved_power(
            p0,
            p1,
            baseline["n"],
            variant["n"],
            alpha=ALPHA,
        ),
        "required_n_per_arm_for_observed_drop_80_power": required_n_per_arm(p0, p1),
    }


def _noop_control(baseline: dict[str, Any]) -> dict[str, Any]:
    p0 = baseline["overall"]["pass_rate_band"]["point"]
    p_value = one_sided_two_proportion_p_value(
        baseline["overall"]["pass_count"],
        baseline["n"],
        baseline["overall"]["pass_count"],
        baseline["n"],
    )
    return {
        **baseline,
        "variant": NOOP_VARIANT,
        "expected_detection": False,
        "drop_vs_baseline": 0.0,
        "p_value": p_value,
        "detected": False,
        "achieved_power_for_observed_drop": achieved_power(
            p0,
            p0,
            baseline["n"],
            baseline["n"],
            alpha=ALPHA,
        ),
        "required_n_per_arm_for_observed_drop_80_power": None,
    }


def one_sided_two_proportion_p_value(
    baseline_passed: int,
    baseline_total: int,
    candidate_passed: int,
    candidate_total: int,
) -> float:
    p0 = baseline_passed / baseline_total
    p1 = candidate_passed / candidate_total
    pooled = (baseline_passed + candidate_passed) / (baseline_total + candidate_total)
    se = math.sqrt(pooled * (1 - pooled) * (1 / baseline_total + 1 / candidate_total))
    if se == 0:
        return 0.0 if p0 > p1 else 1.0
    z = (p0 - p1) / se
    return round(1 - _normal_cdf(z), 6)


def achieved_power(
    baseline_rate: float,
    candidate_rate: float,
    baseline_n: int,
    candidate_n: int,
    *,
    alpha: float = ALPHA,
) -> float:
    drop = baseline_rate - candidate_rate
    if drop <= 0:
        return alpha
    se_alt = math.sqrt(
        baseline_rate * (1 - baseline_rate) / baseline_n
        + candidate_rate * (1 - candidate_rate) / candidate_n
    )
    if se_alt == 0:
        return 1.0
    z_alpha = _inverse_normal_cdf(1 - alpha)
    return round(_normal_cdf(drop / se_alt - z_alpha), 4)


def minimum_detectable_drop(
    baseline_rate: float,
    baseline_n: int,
    candidate_n: int,
    *,
    target_power: float = TARGET_POWER,
    alpha: float = ALPHA,
) -> float:
    max_drop = baseline_rate
    steps = int(max_drop * 1000)
    for step in range(1, steps + 1):
        drop = step / 1000
        if achieved_power(
            baseline_rate,
            max(0.0, baseline_rate - drop),
            baseline_n,
            candidate_n,
            alpha=alpha,
        ) >= target_power:
            return round(drop, 3)
    return round(max_drop, 3)


def required_n_per_arm(
    baseline_rate: float,
    candidate_rate: float,
    *,
    target_power: float = TARGET_POWER,
    alpha: float = ALPHA,
    max_n: int = 10_000,
) -> int | None:
    if baseline_rate <= candidate_rate:
        return None
    for n in range(2, max_n + 1):
        if achieved_power(
            baseline_rate,
            candidate_rate,
            n,
            n,
            alpha=alpha,
        ) >= target_power:
            return n
    return None


def _overall_pass(scores: dict[str, int]) -> bool:
    return all(scores[dimension] >= PASSING_SCORE for dimension in QUALITY_DIMENSIONS)


def _normal_cdf(value: float) -> float:
    return 0.5 * (1 + math.erf(value / math.sqrt(2)))


def _inverse_normal_cdf(probability: float) -> float:
    # Acklam's rational approximation, sufficient for eval reporting.
    if not 0 < probability < 1:
        raise ValueError("probability must be between 0 and 1")
    a = [
        -39.69683028665376,
        220.9460984245205,
        -275.9285104469687,
        138.357751867269,
        -30.66479806614716,
        2.506628277459239,
    ]
    b = [
        -54.47609879822406,
        161.5858368580409,
        -155.6989798598866,
        66.80131188771972,
        -13.28068155288572,
    ]
    c = [
        -0.007784894002430293,
        -0.3223964580411365,
        -2.400758277161838,
        -2.549732539343734,
        4.374664141464968,
        2.938163982698783,
    ]
    d = [
        0.007784695709041462,
        0.3224671290700398,
        2.445134137142996,
        3.754408661907416,
    ]
    low = 0.02425
    high = 1 - low
    if probability < low:
        q = math.sqrt(-2 * math.log(probability))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if probability <= high:
        q = probability - 0.5
        r = q * q
        return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (
            (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
        )
    q = math.sqrt(-2 * math.log(1 - probability))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ARTIFACT_PATH))
    args = parser.parse_args(argv)

    artifact = write_drift_power_report(Path(args.output))
    print(
        "CSM drift power: "
        f"hard_ok={artifact['hard_ok']} "
        f"mdd={artifact['power']['minimum_detectable_drop_at_current_n']} "
        f"sensitivity={artifact['sensitivity']['passed']} "
        f"specificity={artifact['specificity']['passed']}"
    )
    print(f"drift power JSON -> {args.output}")
    return 0 if artifact["hard_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
