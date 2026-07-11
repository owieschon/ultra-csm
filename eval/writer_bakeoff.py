"""R2 writer bake-off: Haiku 4.5 vs Sonnet 5 as Slot B candidate writers.

Validates the cheap drafting model the program will use. Both candidates draft
the SAME MDD-power-sized, stratified scenario set (built from the exact
family/account recipes already curated in ``eval.gold_slot_b_hard`` and
``eval.gold_slot_b_quality`` -- no new adversarial content authored here);
drafts are scored by the Sonnet-5 judge on the five currently-validated gating
dimensions (the ``#104`` judge scope guard, ``eval.judge_validation``);
``on_task_relevance`` is scored and reported but never gated. Deterministic
checks reuse Slot B's own contract validator (``validate_reason_draft_output``)
for grounding (cited evidence ids must be real and cited) and forbidden
content (blocked-phrase/URL-allowlist checks) -- there is no separate
"motion" field on a Slot B draft, so those checks stand in for the dispatch's
"forbidden motions" deterministic check in this context.

Self-preference disclosure (mandatory in the report): the judge model is
claude-sonnet-5, and one candidate arm IS claude-sonnet-5 -- a known
same-model bias direction. The adoption rule below is an ABSOLUTE bar applied
independently to each arm, not a head-to-head comparison, so Haiku is adopted
if HAIKU clears the bar regardless of how the judge scores the Sonnet arm.
The bar itself and the judge's score are still produced by the same model
family, so the caveat is disclosed in the report rather than resolved away.

Adoption bar (a builder decision -- there is no existing numeric precedent in
this repo for a writer-quality absolute bar; ``eval.judge_model_migration``'s
adoption rule is a *judge*-calibration screen against a labeled reference,
which has no analog here since these live drafts have no ground truth. Stated
explicitly, open to owner override at OA-Q1):
  adopt_eligible = gated_pass_rate >= 0.90 AND pass_k_rate >= 0.80
                   AND contract_violation_rate == 0.0

MDD sizing: baseline_rate=0.80 (a stated target for a production drafting
model, not an existing measurement) and drop_pp=0.20 -- the larger of the
10/20/30pp options ``src/ultra_csm/world/baselines.py`` demonstrates, chosen
for feasibility (two models x n scenarios x k=3 draws x {write, judge} calls
is, per the sibling MP-R dispatch's own quota note, "the heaviest lane before
F2"). ``--drop-pp 0.10`` or ``0.15`` remain available for a larger run.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from eval.drift_power_csm import required_n_per_arm
from eval.gold_slot_b_hard import A6_EXPANSION_FAMILIES, FAMILIES, _hard_request
from eval.gold_slot_b_quality import _request_dict, _output_dict, _request_specs
from eval.judge_anthropic import AnthropicQualityJudge, JUDGE_PROMPT_VERSION
from eval.judge_csm import PASSING_SCORE
from eval.judge_validation import assert_gating_dimensions
from eval.run_quality_judge import MAX_RETRIES, _retryable
from ultra_csm.agent1.slot_b import (
    AnthropicReasonDraftWriter,
    ReasonDraftRequest,
    SlotBContractError,
    validate_reason_draft_output,
)
from ultra_csm.cost_tracker import CostTracker
from ultra_csm.llm_transport import configured_transport_name

REPORT_PATH = Path(__file__).resolve().parent / "gold" / "writer_bakeoff_report.json"

JUDGE_MODEL_ID = "claude-sonnet-5"
CANDIDATE_MODELS = {"haiku": "claude-haiku-4-5", "sonnet": "claude-sonnet-5"}
PASS_K = 3

# Exactly the #104 judge scope guard's currently-validated set. Declaring it
# here (rather than reading "whatever is validated right now") means
# assert_gating_dimensions fails closed if reality ever diverges from this
# stated scope, instead of silently widening or narrowing the gate.
GATED_DIMENSIONS = (
    "account_specificity",
    "grounding_fidelity",
    "priority_fidelity",
    "safety_boundary",
    "tone_fit",
)
REPORTED_NOT_GATED = ("on_task_relevance",)

MDD_BASELINE_RATE = 0.80
DEFAULT_DROP_PP = 0.20
ADOPT_MIN_GATED_PASS_RATE = 0.90
ADOPT_MIN_PASS_K_RATE = 0.80


def sized_n_per_arm(drop_pp: float = DEFAULT_DROP_PP) -> int:
    n = required_n_per_arm(MDD_BASELINE_RATE, MDD_BASELINE_RATE - drop_pp)
    return n if n is not None else 30


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    family: str
    request: ReasonDraftRequest


def _family_pool() -> dict[str, tuple[bool, tuple[str, ...]]]:
    """family -> (contact_required, untrusted_fragments): the exact recipes
    already curated in eval.gold_slot_b_hard, plus one non-adversarial
    control family drawn from the clean-layer's own account/factor specs."""
    pool: dict[str, tuple[bool, tuple[str, ...]]] = {"clean_baseline": (False, ())}
    for name, (_builder, contact_required, _count, untrusted, _expected, _trap) in FAMILIES.items():
        pool[name] = (contact_required, untrusted)
    for name, (_builder, contact_required, _count, untrusted, _tags, _trap) in A6_EXPANSION_FAMILIES.items():
        pool[name] = (contact_required, untrusted)
    return pool


def build_scenario_set(n_total: int) -> tuple[Scenario, ...]:
    """Stratified scenario set: n_total split evenly across every family in
    the existing taxonomy, drawing accounts from the same 15-account spec
    pool eval.gold_slot_b_hard already uses. Deterministic cycling (not
    random) so the same n reproduces the same set across runs."""
    pool = _family_pool()
    all_specs = _request_specs()
    contact_specs = tuple(spec for spec in all_specs if spec["contact_allowed"])
    families = sorted(pool)
    per_family = max(1, n_total // len(families))
    scenarios: list[Scenario] = []
    for family in families:
        contact_required, untrusted = pool[family]
        specs = contact_specs if contact_required else all_specs
        for i in range(per_family):
            spec = specs[i % len(specs)]
            scenario_id = f"bakeoff-{family}-{i:02d}"
            request = _hard_request(scenario_id, spec, untrusted)
            scenarios.append(Scenario(scenario_id, family, request))
    return tuple(scenarios)


@dataclass
class DrawResult:
    scenario_id: str
    family: str
    draw_index: int
    contract_ok: bool
    contract_error: str | None
    scores: dict[str, int] | None
    gated_pass: bool
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None = None
    latency_ms: float | None = None


def _call_with_retry(fn):
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - re-raised below if not retryable
            last_exc = exc
            if not _retryable(exc) or attempt == MAX_RETRIES:
                break
            time.sleep(min(2 ** (attempt - 1), 30))
    raise last_exc if last_exc is not None else RuntimeError("call failed with no exception recorded")


def run_draw(
    scenario: Scenario,
    draw_index: int,
    *,
    writer: AnthropicReasonDraftWriter,
    judge: AnthropicQualityJudge,
) -> DrawResult:
    try:
        output = _call_with_retry(lambda: writer.write(scenario.request))
    except SlotBContractError as exc:
        return DrawResult(
            scenario_id=scenario.scenario_id,
            family=scenario.family,
            draw_index=draw_index,
            contract_ok=False,
            contract_error=str(exc),
            scores=None,
            gated_pass=False,
            input_tokens=None,
            output_tokens=None,
        )
    validate_reason_draft_output(scenario.request, output)  # re-raises on drift; writer already validated
    scores = _call_with_retry(
        lambda: judge.score_output(
            _request_dict(scenario.request),
            _output_dict(output),
        )
    )
    gated_pass = all(scores[dim] >= PASSING_SCORE for dim in GATED_DIMENSIONS)
    return DrawResult(
        scenario_id=scenario.scenario_id,
        family=scenario.family,
        draw_index=draw_index,
        contract_ok=True,
        contract_error=None,
        scores=scores,
        gated_pass=gated_pass,
        input_tokens=None,
        output_tokens=None,
    )


def run_arm(
    model_id: str,
    scenarios: tuple[Scenario, ...],
    *,
    pass_k: int = PASS_K,
    checkpoint_path: Path | None = None,
) -> dict:
    # A per-draw CostTracker (not one shared across the whole arm) is
    # deliberate: its stats are folded into the checkpoint dict for THIS
    # draw before returning, so token/cost telemetry survives a process
    # kill+resume by construction (the checkpoint is the source of truth,
    # not an in-memory tracker that dies with the process -- see
    # docs/R2_TELEMETRY_RESUME_FINDING.md).
    draws = _load_checkpoint(checkpoint_path)
    already = {(d["scenario_id"], d["draw_index"]) for d in draws}
    judge = AnthropicQualityJudge(model_id=JUDGE_MODEL_ID, reasoning=True)
    total = len(scenarios) * pass_k
    done = len(draws)
    for scenario in scenarios:
        for draw_index in range(pass_k):
            if (scenario.scenario_id, draw_index) in already:
                continue
            done += 1
            print(
                f"bakeoff model={model_id} draw {done}/{total} "
                f"scenario={scenario.scenario_id} family={scenario.family} draw={draw_index}",
                flush=True,
            )
            draw_tracker = CostTracker()
            writer = AnthropicReasonDraftWriter(model_id=model_id, cost_tracker=draw_tracker)
            result = run_draw(scenario, draw_index, writer=writer, judge=judge)
            draw_dict = asdict(result)
            stats = draw_tracker.stats()
            if stats["total_calls"]:
                draw_dict["input_tokens"] = stats["total_input_tokens"]
                draw_dict["output_tokens"] = stats["total_output_tokens"]
                draw_dict["cost_usd"] = stats["total_cost_usd"]
                draw_dict["latency_ms"] = stats["avg_latency_ms"]
            draws.append(draw_dict)
            _write_checkpoint(checkpoint_path, draws)
    return _aggregate_arm(model_id, scenarios, draws, pass_k=pass_k)


def _aggregate_arm(model_id: str, scenarios: tuple[Scenario, ...], draws: list[dict], *, pass_k: int) -> dict:
    by_scenario: dict[str, list[dict]] = {}
    for draw in draws:
        by_scenario.setdefault(draw["scenario_id"], []).append(draw)

    n_draws = len(draws)
    contract_violations = sum(1 for d in draws if not d["contract_ok"])
    gated_pass_count = sum(1 for d in draws if d["gated_pass"])
    consistent_scenarios = sum(
        1
        for scenario_id, scenario_draws in by_scenario.items()
        if len(scenario_draws) >= pass_k and all(d["gated_pass"] for d in scenario_draws[:pass_k])
    )

    per_dimension_pass = {}
    for dim in (*GATED_DIMENSIONS, *REPORTED_NOT_GATED):
        scored = [d["scores"][dim] for d in draws if d["scores"] is not None]
        per_dimension_pass[dim] = (
            round(sum(1 for s in scored if s >= PASSING_SCORE) / len(scored), 4) if scored else None
        )

    by_family: dict[str, dict] = {}
    for scenario in scenarios:
        family = scenario.family
        family_draws = by_scenario.get(scenario.scenario_id, [])
        entry = by_family.setdefault(family, {"n_draws": 0, "gated_pass": 0})
        entry["n_draws"] += len(family_draws)
        entry["gated_pass"] += sum(1 for d in family_draws if d["gated_pass"])
    for family, entry in by_family.items():
        entry["gated_pass_rate"] = round(entry["gated_pass"] / entry["n_draws"], 4) if entry["n_draws"] else None

    gated_pass_rate = round(gated_pass_count / n_draws, 4) if n_draws else 0.0
    pass_k_rate = round(consistent_scenarios / len(scenarios), 4) if scenarios else 0.0
    contract_violation_rate = round(contract_violations / n_draws, 4) if n_draws else 0.0
    adopt_eligible = (
        gated_pass_rate >= ADOPT_MIN_GATED_PASS_RATE
        and pass_k_rate >= ADOPT_MIN_PASS_K_RATE
        and contract_violation_rate == 0.0
    )
    telemetry = _telemetry_from_draws(draws)
    return {
        "model_id": model_id,
        "n_scenarios": len(scenarios),
        "pass_k": pass_k,
        "n_draws": n_draws,
        "contract_violations": contract_violations,
        "contract_violation_rate": contract_violation_rate,
        "gated_dimensions": list(GATED_DIMENSIONS),
        "reported_not_gated": list(REPORTED_NOT_GATED),
        "per_dimension_pass_rate": per_dimension_pass,
        "gated_pass_rate": gated_pass_rate,
        "pass_k_rate": pass_k_rate,
        "by_family": by_family,
        "adopt_bar": {
            "min_gated_pass_rate": ADOPT_MIN_GATED_PASS_RATE,
            "min_pass_k_rate": ADOPT_MIN_PASS_K_RATE,
            "max_contract_violation_rate": 0.0,
        },
        "adopt_eligible": adopt_eligible,
        "telemetry": telemetry,
    }


def _telemetry_from_draws(draws: list[dict]) -> dict:
    """Token/cost/latency aggregated from the checkpoint's per-draw fields.

    Deliberately NOT derived from a live CostTracker: a tracker is
    in-memory only and does not survive a process kill+resume, silently
    undercounting whichever draws were already checkpointed before a
    restart (see docs/R2_TELEMETRY_RESUME_FINDING.md). Summing the
    checkpoint's own per-draw fields is correct across any number of
    resumes because the checkpoint itself is what survives.
    """
    priced = [d for d in draws if d.get("input_tokens") is not None]
    n_priced = len(priced)
    input_tokens = sum(d["input_tokens"] for d in priced)
    output_tokens = sum(d["output_tokens"] or 0 for d in priced)
    cost_usd = sum(d["cost_usd"] or 0.0 for d in priced)
    latency_ms = sum(d["latency_ms"] or 0.0 for d in priced)
    return {
        "n_draws_total": len(draws),
        "n_draws_priced": n_priced,
        "coverage": round(n_priced / len(draws), 4) if draws else 0.0,
        "total_input_tokens": input_tokens,
        "total_output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "total_cost_usd": round(cost_usd, 6),
        "avg_latency_ms": round(latency_ms / n_priced, 2) if n_priced else None,
    }


def build_report(
    *,
    n_per_arm: int | None = None,
    drop_pp: float = DEFAULT_DROP_PP,
    pass_k: int = PASS_K,
    checkpoint_dir: Path | None = None,
) -> dict:
    gated = assert_gating_dimensions(GATED_DIMENSIONS)
    n_total = n_per_arm if n_per_arm is not None else sized_n_per_arm(drop_pp)
    scenarios = build_scenario_set(n_total)

    arms = {}
    for key, model_id in CANDIDATE_MODELS.items():
        checkpoint_path = checkpoint_dir / f"writer_bakeoff_{key}.json" if checkpoint_dir else None
        arms[key] = run_arm(
            model_id,
            scenarios,
            pass_k=pass_k,
            checkpoint_path=checkpoint_path,
        )

    recommended = [key for key, arm in arms.items() if arm["adopt_eligible"]]
    fully_priced = [key for key in recommended if arms[key]["telemetry"]["coverage"] == 1.0]
    cheapest_eligible = min(
        fully_priced,
        key=lambda key: arms[key]["telemetry"]["total_cost_usd"],
        default=None,
    )
    if recommended and not fully_priced:
        cheapest_eligible = None  # every eligible arm has incomplete telemetry; do not guess

    return {
        "artifact": "writer_bakeoff_report",
        "schema_version": 1,
        "generated_by": "eval.writer_bakeoff",
        "judge_model_id": JUDGE_MODEL_ID,
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "configured_transport": configured_transport_name(),
        "gated_dimensions": list(gated),
        "reported_not_gated": list(REPORTED_NOT_GATED),
        "self_preference_disclosure": (
            "The judge model is claude-sonnet-5. The 'sonnet' arm below is "
            "claude-sonnet-5 scoring its own sibling's drafts -- a known "
            "same-model bias direction. adopt_eligible is an absolute bar "
            "applied independently per arm, not a head-to-head comparison, "
            "so this does not decide adoption by itself; it is disclosed "
            "because the judge and one candidate share a model family."
        ),
        "adoption_rule": (
            "absolute_gates_not_head_to_head: a candidate is adopt_eligible "
            "iff gated_pass_rate >= 0.90 and pass_k_rate >= 0.80 and "
            "contract_violation_rate == 0.0, independent of the other arm's score."
        ),
        "mdd_sizing": {
            "method": "eval.drift_power_csm.required_n_per_arm",
            "baseline_rate": MDD_BASELINE_RATE,
            "drop_pp": drop_pp,
            "n_per_arm": n_total,
            "n_scenarios_built": len(scenarios),
            "n_families": len(_family_pool()),
        },
        "arms": arms,
        "recommendation": {
            "adopt_eligible_models": recommended,
            "cheapest_adopt_eligible": cheapest_eligible,
            "note": (
                "cheapest_adopt_eligible is null if any eligible arm's "
                "telemetry.coverage < 1.0 (e.g. after a resumed run whose "
                "earlier checkpoint predates per-draw telemetry) -- an "
                "incomplete-population comparison is not reported as a cost "
                "finding. Both arms' full results are committed regardless of "
                "this recommendation -- an honest comparison, not a beauty "
                "contest. STOP -> OA-Q1: owner decides."
            ),
        },
    }


def _load_checkpoint(checkpoint_path: Path | None) -> list[dict]:
    if checkpoint_path is None or not checkpoint_path.exists():
        return []
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    draws = payload.get("draws")
    if not isinstance(draws, list):
        raise ValueError(f"checkpoint {checkpoint_path} has no draws list")
    return draws


def _write_checkpoint(checkpoint_path: Path | None, draws: list[dict]) -> None:
    if checkpoint_path is None:
        return
    checkpoint_path.write_text(
        json.dumps({"draws": draws}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-per-arm", type=int, default=None)
    parser.add_argument("--drop-pp", type=float, default=DEFAULT_DROP_PP)
    parser.add_argument("--pass-k", type=int, default=PASS_K)
    parser.add_argument("--output", default=str(REPORT_PATH))
    parser.add_argument("--checkpoint-dir", default=".writer_bakeoff_checkpoints")
    args = parser.parse_args(argv)

    checkpoint_dir = Path(args.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(
        n_per_arm=args.n_per_arm,
        drop_pp=args.drop_pp,
        pass_k=args.pass_k,
        checkpoint_dir=checkpoint_dir,
    )
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for key, arm in report["arms"].items():
        t = arm["telemetry"]
        print(
            f"\n[{key}] model={arm['model_id']} n_draws={arm['n_draws']} "
            f"gated_pass_rate={arm['gated_pass_rate']} pass_k_rate={arm['pass_k_rate']} "
            f"contract_violation_rate={arm['contract_violation_rate']} "
            f"adopt_eligible={arm['adopt_eligible']} "
            f"telemetry_coverage={t['coverage']} total_cost_usd={t['total_cost_usd']}"
        )
    print(f"\nrecommendation: {report['recommendation']}")
    print(f"report -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
