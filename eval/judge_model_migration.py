"""Judge model migration screen using paired McNemar comparisons.

The shipped judge is validated through ``eval/gold/judge_compare.json``: the
``cot@N`` hard-layer arm, aggregated over N runs. This script keeps that
committed arm as the baseline, runs a candidate judge model on the same held-out
hard cases, and reports whether the candidate is safe to adopt.

Adoption is deliberately conservative:
- candidate hard-layer kappas must satisfy the same validation floor;
- aggregated overall false negatives (bad output passed by judge) must be zero;
- paired McNemar must show no regression for every dimension and overall pass/fail;
- fail-open false passes must not increase for any dimension or overall pass/fail.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

from eval.compare_judges import OUT_PATH
from eval.judge_anthropic import AnthropicQualityJudge, JUDGE_PROMPT_VERSION
from eval.judge_csm import PASSING_SCORE, QUALITY_DIMENSIONS, weighted_cohen_kappa
from eval.judge_nrun import aggregate, score_nrun_agreement
from eval.judge_validation import GATE_KAPPA, HARD_ARM
from eval.run_quality_judge import load_hard

REPO = Path(__file__).resolve().parents[1]
OUT_PATH_MIGRATION = REPO / "eval" / "gold" / "judge_model_migration.json"
DEFAULT_CANDIDATE_MODEL_ID = "claude-sonnet-5"
MAX_RETRIES = 5
RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 529}

# Introductory Claude Sonnet 5 pricing through 2026-08-31 per Anthropic docs.
_MODEL_PRICING = {
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-5": (2.00, 10.00),
}


class UsageRecordingClient:
    def __init__(self, *, usage_path: Path | None = None) -> None:
        from anthropic import Anthropic

        self._client = Anthropic()
        self.messages = self
        self.calls: list[dict[str, Any]] = []
        self.usage_path = usage_path
        self._write_summary()

    def create(self, **kwargs: Any) -> Any:
        started = time.monotonic()
        msg = self._client.messages.create(**kwargs)
        elapsed_ms = (time.monotonic() - started) * 1000
        usage = getattr(msg, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        model_id = str(kwargs.get("model") or "unknown")
        self.calls.append(
            {
                "model_id": model_id,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": _compute_cost(model_id, input_tokens, output_tokens),
                "latency_ms": elapsed_ms,
            }
        )
        self._write_summary()
        return msg

    def summary(self) -> dict[str, Any]:
        return {
            "calls": len(self.calls),
            "input_tokens": sum(call["input_tokens"] for call in self.calls),
            "output_tokens": sum(call["output_tokens"] for call in self.calls),
            "cost_usd": round(sum(call["cost_usd"] for call in self.calls), 6),
        }

    def _write_summary(self) -> None:
        if self.usage_path is not None:
            self.usage_path.write_text(
                json.dumps(self.summary(), sort_keys=True) + "\n",
                encoding="utf-8",
            )


def run_candidate_arm(
    judge: AnthropicQualityJudge,
    items: list[dict[str, Any]],
    n: int,
    *,
    checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    scored = _load_checkpoint(checkpoint_path)
    already_scored = {case["candidate_id"] for case in scored}
    total = len(items)
    for index, item in enumerate(items, start=1):
        if item["candidate_id"] in already_scored:
            print(
                f"candidate model={judge.model_id} hard case {index}/{total} "
                f"id={item['candidate_id']} checkpoint-hit",
                flush=True,
            )
            continue
        print(
            f"candidate model={judge.model_id} hard case {index}/{total} "
            f"id={item['candidate_id']}",
            flush=True,
        )
        vectors = [
            _score_with_retry(judge, item["request"], item["output"])
            for _ in range(n)
        ]
        scored.append(
            {
                "candidate_id": item["candidate_id"],
                "family": item["family"],
                "reference": item["reference"],
                "agg": aggregate(vectors),
            }
        )
        _write_checkpoint(checkpoint_path, scored)
    report = score_nrun_agreement(scored)
    report["cases"] = scored
    return report


def build_migration_report(
    *,
    baseline_compare: dict[str, Any],
    candidate_arm: dict[str, Any],
    candidate_model_id: str,
    usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    baseline_arm = baseline_compare["arms"][HARD_ARM]
    baseline_cases = _cases_by_id(baseline_arm["cases"])
    candidate_cases = _cases_by_id(candidate_arm["cases"])
    if set(baseline_cases) != set(candidate_cases):
        raise ValueError("baseline and candidate cases must have identical candidate_id sets")

    comparisons = {
        dim: _paired_dimension_report(baseline_cases, candidate_cases, dim)
        for dim in QUALITY_DIMENSIONS
    }
    comparisons["overall_pass"] = _paired_overall_report(baseline_cases, candidate_cases)
    hard_gate = _hard_gate_report(candidate_arm["cases"])
    adoption_blockers = _adoption_blockers(comparisons, hard_gate)
    adoption = {
        "adopt": not adoption_blockers,
        "blockers": adoption_blockers,
        "rule": (
            "adopt only if candidate validates on hard-layer kappas, has zero "
            "aggregated overall false negatives, has no paired McNemar regression "
            "on any dimension or overall pass/fail, and does not increase fail-open "
            "false passes"
        ),
    }
    return {
        "artifact": "slot_b_judge_model_migration",
        "schema_version": 1,
        "generated_by": "eval.judge_model_migration",
        "baseline_model_id": baseline_compare.get("model_id"),
        "candidate_model_id": candidate_model_id,
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "baseline_judge_prompt_version": baseline_compare.get("judge_prompt_version"),
        "hard_arm": HARD_ARM,
        "runs_per_case": baseline_compare.get("runs_per_case"),
        "n_cases": len(candidate_cases),
        "comparison": comparisons,
        "candidate_hard_gate": hard_gate,
        "candidate_arm_summary": _arm_summary(candidate_arm),
        "baseline_arm_summary": _arm_summary(baseline_arm),
        "adoption_decision": adoption,
        "usage": usage or {},
        "stores_full_text": False,
        "claim_boundary": {
            "gold_labels_modified": False,
            "judge_prompt_modified": False,
            "baseline_from_committed_artifact": "eval/gold/judge_compare.json",
            "candidate_hard_cases": "same candidate_id set as committed baseline",
        },
    }


def _paired_dimension_report(
    baseline_cases: dict[str, dict[str, Any]],
    candidate_cases: dict[str, dict[str, Any]],
    dim: str,
) -> dict[str, Any]:
    pairs = []
    baseline_false_pass: list[str] = []
    candidate_false_pass: list[str] = []
    for candidate_id in sorted(baseline_cases):
        baseline = baseline_cases[candidate_id]
        candidate = candidate_cases[candidate_id]
        reference = int(candidate["reference"][dim])
        baseline_score = int(baseline["agg"]["vector"][dim])
        candidate_score = int(candidate["agg"]["vector"][dim])
        baseline_correct = baseline_score == reference
        candidate_correct = candidate_score == reference
        pairs.append(
            {
                "candidate_id": candidate_id,
                "baseline_correct": baseline_correct,
                "candidate_correct": candidate_correct,
            }
        )
        if reference < PASSING_SCORE and baseline_score >= PASSING_SCORE:
            baseline_false_pass.append(candidate_id)
        if reference < PASSING_SCORE and candidate_score >= PASSING_SCORE:
            candidate_false_pass.append(candidate_id)
    return _paired_report(
        pairs,
        baseline_false_pass=baseline_false_pass,
        candidate_false_pass=candidate_false_pass,
    )


def _paired_overall_report(
    baseline_cases: dict[str, dict[str, Any]],
    candidate_cases: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    pairs = []
    baseline_false_pass: list[str] = []
    candidate_false_pass: list[str] = []
    for candidate_id in sorted(baseline_cases):
        baseline = baseline_cases[candidate_id]
        candidate = candidate_cases[candidate_id]
        ref_pass = _overall_pass(candidate["reference"])
        baseline_pass = bool(baseline["agg"]["aggregate_pass"])
        candidate_pass = bool(candidate["agg"]["aggregate_pass"])
        pairs.append(
            {
                "candidate_id": candidate_id,
                "baseline_correct": baseline_pass == ref_pass,
                "candidate_correct": candidate_pass == ref_pass,
            }
        )
        if not ref_pass and baseline_pass:
            baseline_false_pass.append(candidate_id)
        if not ref_pass and candidate_pass:
            candidate_false_pass.append(candidate_id)
    return _paired_report(
        pairs,
        baseline_false_pass=baseline_false_pass,
        candidate_false_pass=candidate_false_pass,
    )


def _paired_report(
    pairs: list[dict[str, Any]],
    *,
    baseline_false_pass: list[str],
    candidate_false_pass: list[str],
) -> dict[str, Any]:
    baseline_correct_candidate_wrong = [
        pair["candidate_id"]
        for pair in pairs
        if pair["baseline_correct"] and not pair["candidate_correct"]
    ]
    baseline_wrong_candidate_correct = [
        pair["candidate_id"]
        for pair in pairs
        if not pair["baseline_correct"] and pair["candidate_correct"]
    ]
    b = len(baseline_correct_candidate_wrong)
    c = len(baseline_wrong_candidate_correct)
    p_value = _mcnemar_exact_p_value(b, c)
    verdict = "no-evidence-of-regression"
    if p_value < 0.05 and b > c:
        verdict = "regressed"
    elif p_value < 0.05 and c > b:
        verdict = "improved"
    return {
        "method": "McNemar exact paired test",
        "baseline_correct_candidate_wrong": b,
        "baseline_wrong_candidate_correct": c,
        "discordant_total": b + c,
        "p_value": p_value,
        "alpha": 0.05,
        "verdict": verdict,
        "baseline_correct_candidate_wrong_ids": baseline_correct_candidate_wrong,
        "baseline_wrong_candidate_correct_ids": baseline_wrong_candidate_correct,
        "baseline_false_pass": len(baseline_false_pass),
        "candidate_false_pass": len(candidate_false_pass),
        "fail_open_delta": len(candidate_false_pass) - len(baseline_false_pass),
        "candidate_false_pass_ids": candidate_false_pass,
    }


def _hard_gate_report(cases: list[dict[str, Any]]) -> dict[str, Any]:
    kappas = {}
    false_pass_ids: list[str] = []
    for dim in QUALITY_DIMENSIONS:
        ref_col = [case["reference"][dim] for case in cases]
        judge_col = [case["agg"]["vector"][dim] for case in cases]
        kappas[dim] = round(weighted_cohen_kappa(ref_col, judge_col), 3)
    for case in cases:
        if case["agg"]["aggregate_pass"] and not _overall_pass(case["reference"]):
            false_pass_ids.append(str(case["candidate_id"]))
    failures = [
        f"{dim} kappa {value} < {GATE_KAPPA}"
        for dim, value in kappas.items()
        if value < GATE_KAPPA
    ]
    if false_pass_ids:
        failures.append(f"aggregated overall false negatives: {sorted(false_pass_ids)}")
    return {
        "validated": not failures,
        "failures": sorted(failures),
        "gate_kappa": GATE_KAPPA,
        "per_dimension_kappa_aggregated": kappas,
        "overall_false_pass_ids": false_pass_ids,
    }


def _adoption_blockers(
    comparisons: dict[str, dict[str, Any]],
    hard_gate: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if not hard_gate["validated"]:
        blockers.extend(f"candidate hard gate failed: {failure}" for failure in hard_gate["failures"])
    for name, report in comparisons.items():
        if report["verdict"] == "regressed":
            blockers.append(f"{name} paired McNemar verdict regressed")
        if report["fail_open_delta"] > 0:
            blockers.append(
                f"{name} fail-open false passes increased by {report['fail_open_delta']}"
            )
    return blockers


def _arm_summary(arm: dict[str, Any]) -> dict[str, Any]:
    return {
        "n": arm.get("n"),
        "false_neg": arm.get("false_neg"),
        "false_pos": arm.get("false_pos"),
        "gate_repeatability": arm.get("gate_repeatability"),
        "indeterminate_ids": arm.get("indeterminate_ids"),
        "exact_vector_match": arm.get("exact_vector_match"),
    }


def _cases_by_id(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(case["candidate_id"]): case for case in cases}


def _load_checkpoint(checkpoint_path: Path | None) -> list[dict[str, Any]]:
    if checkpoint_path is None or not checkpoint_path.exists():
        return []
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError(f"checkpoint {checkpoint_path} has no cases list")
    return cases


def _write_checkpoint(checkpoint_path: Path | None, cases: list[dict[str, Any]]) -> None:
    if checkpoint_path is None:
        return
    checkpoint_path.write_text(
        json.dumps({"cases": cases}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _overall_pass(scores: dict[str, int]) -> bool:
    return all(scores[dim] >= PASSING_SCORE for dim in QUALITY_DIMENSIONS)


def _mcnemar_exact_p_value(b: int, c: int) -> float:
    discordant = b + c
    if discordant == 0:
        return 1.0
    tail = sum(
        math.comb(discordant, k) * (0.5 ** discordant)
        for k in range(0, min(b, c) + 1)
    )
    return min(1.0, 2.0 * tail)


def _score_with_retry(judge: AnthropicQualityJudge, request: dict[str, Any], output: dict[str, Any]) -> dict[str, int]:
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return judge.score_output(request, output)
        except Exception as exc:
            last_exc = exc
            if not _retryable(exc) or attempt == MAX_RETRIES:
                break
            time.sleep(min(2 ** (attempt - 1), 30))
    raise last_exc if last_exc is not None else RuntimeError("judge scoring failed")


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, ValueError):
        return True
    status_code = getattr(exc, "status_code", None)
    if status_code in RETRYABLE_STATUS_CODES:
        return True
    return exc.__class__.__name__ in {
        "APIConnectionError",
        "APITimeoutError",
        "InternalServerError",
        "OverloadedError",
        "RateLimitError",
    }


def _compute_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    input_rate, output_rate = _MODEL_PRICING.get(model_id, (5.00, 25.00))
    return (input_tokens / 1_000_000 * input_rate) + (output_tokens / 1_000_000 * output_rate)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-model", default=DEFAULT_CANDIDATE_MODEL_ID)
    parser.add_argument("--baseline-compare", default=str(OUT_PATH))
    parser.add_argument("--runs", type=int, default=None)
    parser.add_argument("--output", default=str(OUT_PATH_MIGRATION))
    parser.add_argument("--usage-output", default=".judge_model_migration_usage.json")
    parser.add_argument("--checkpoint", default=".judge_model_migration_checkpoint.json")
    parser.add_argument("--max-tokens", type=int, default=1400)
    args = parser.parse_args(argv)

    baseline_compare = json.loads(Path(args.baseline_compare).read_text(encoding="utf-8"))
    runs = args.runs or int(baseline_compare.get("runs_per_case") or 5)
    items = load_hard()
    usage_path = Path(args.usage_output) if args.usage_output else None
    client = UsageRecordingClient(usage_path=usage_path)
    judge = AnthropicQualityJudge(
        client=client,
        model_id=args.candidate_model,
        reasoning=True,
    )
    judge._max_tokens = max(judge._max_tokens, args.max_tokens)
    candidate_arm = run_candidate_arm(
        judge,
        items,
        runs,
        checkpoint_path=Path(args.checkpoint) if args.checkpoint else None,
    )
    report = build_migration_report(
        baseline_compare=baseline_compare,
        candidate_arm=candidate_arm,
        candidate_model_id=judge.model_id,
        usage=client.summary(),
    )
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    decision = report["adoption_decision"]
    print(
        f"\njudge migration baseline={report['baseline_model_id']} "
        f"candidate={report['candidate_model_id']} runs={runs} "
        f"adopt={decision['adopt']}"
    )
    if decision["blockers"]:
        for blocker in decision["blockers"]:
            print(f"blocker: {blocker}")
    print(f"usage: {client.summary()}")
    print(f"report -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
