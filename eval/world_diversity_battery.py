"""World diversity battery (MP-W1R, Wave A). Deterministic, no LLM.

Verifies:
- D2 (shape heterogeneity): the LIVE evidence-construction path
  (``_slot_b_inputs_for_account``, the same function ``run_time_to_value_sweep``
  calls) produces genuinely varying evidence count, factor count, and source
  mix across the synthetic book's accounts -- not the deliberately-uniform
  frozen gold corpus under ``eval/gold/`` (ruler, untouched; that corpus is
  2-evidence/2-factor by design, for judge calibration, and stays that way).
  Deliberately bypasses ``run_time_to_value_sweep``/``ActionGate`` (which need
  a live Postgres governance ledger) -- this measures SHAPE, not governance
  decisions, so it calls the lower-level fixture-backed function directly,
  same pattern as ``eval/reconciliation_battery.py``'s data plane.
- D3 (dirty-data rates): the three independent
  ``field_missingness_rate``/``stale_observation_rate``/``contradictory_source_rate``
  configured in ``WorldConfig`` materialize on a generated world within
  +/-0.03 of their configured values.
- D5 (latent outcome enum): ``latent_outcome`` is a pure function of
  doomed/thriving across the generated population (no drift between the two
  representations).

These are WORLD-LEVEL properties (``LatentAccountTruth``), not yet wired
into the live agent-visible evidence path (that would require touching
``src/ultra_csm/agent1/sweep.py``, outside this dispatch's ownership map of
``src/ultra_csm/world/**`` -- a natural next-wave task, not this one).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from ultra_csm.agent1.slot_a import FixtureCaseNoteClassifier
from ultra_csm.agent1.sweep import _slot_b_inputs_for_account
from ultra_csm.data_plane import CustomerDataPlane
from ultra_csm.data_plane.fixtures import (
    FixtureCRMDataConnector,
    FixtureCSPlatformConnector,
    FixtureProductTelemetryConnector,
)
from ultra_csm.data_plane.synthetic_book import build_synthetic_book
from ultra_csm.world.generator import LatentAccountTruth, WorldConfig, generate_world

ARTIFACT_DIR = Path(__file__).with_name("gold")
DEFAULT_OUTPUT = ARTIFACT_DIR / "world_diversity_battery.json"
DEFAULT_AS_OF = "2026-06-28"
DEFAULT_TENANT_ID = "world-diversity-battery-tenant"


def _data_plane() -> tuple[CustomerDataPlane, Any]:
    book = build_synthetic_book()
    return (
        CustomerDataPlane(
            crm=FixtureCRMDataConnector(data=book),
            cs=FixtureCSPlatformConnector(data=book),
            telemetry=FixtureProductTelemetryConnector(data=book),
        ),
        book,
    )


def _sample_shapes(data_plane: CustomerDataPlane, accounts, *, as_of: str) -> list[dict[str, Any]]:
    classifier = FixtureCaseNoteClassifier()
    shapes = []
    for account in accounts:
        inputs = _slot_b_inputs_for_account(
            data_plane,
            account,
            tenant_id=DEFAULT_TENANT_ID,
            as_of=as_of,
            case_note_classifier=classifier,
        )
        if inputs is None:
            continue
        shapes.append(
            {
                "account_id": account.account_id,
                "evidence_count": len(inputs.evidence),
                "factor_count": len(inputs.priority.factors),
                "sources": sorted({ref.source for ref in inputs.evidence}),
            }
        )
    return shapes


def _variance_row(metric: str, values: list[int]) -> dict[str, Any]:
    if not values:
        return {"metric": metric, "n": 0, "min": None, "max": None, "variance_gt_0": False}
    return {
        "metric": metric,
        "n": len(values),
        "min": min(values),
        "max": max(values),
        "variance_gt_0": max(values) != min(values),
    }


DEFAULT_WORLD_SEED = 7
DEFAULT_WORLD_SCALE = 200  # large enough for all 4 D5 outcomes to appear
RATE_TOLERANCE = 0.03


def _check_dirty_data_rates(config: WorldConfig, latent_truth) -> dict[str, Any]:
    n = len(latent_truth)
    observed = {
        "missing_field": sum(1 for r in latent_truth if "missing_field" in r.data_quality_flags) / n,
        "stale_observation": sum(1 for r in latent_truth if "stale_observation" in r.data_quality_flags) / n,
        "contradictory_source": sum(1 for r in latent_truth if "contradictory_source" in r.data_quality_flags) / n,
    }
    configured = {
        "missing_field": config.field_missingness_rate,
        "stale_observation": config.stale_observation_rate,
        "contradictory_source": config.contradictory_source_rate,
    }
    deltas = {k: round(abs(observed[k] - configured[k]), 4) for k in configured}
    problems = [f"{k} rate {observed[k]:.4f} outside +/-{RATE_TOLERANCE} of configured {configured[k]}" for k, d in deltas.items() if d > RATE_TOLERANCE]
    return {
        "metric": "dirty_data_rates",
        "n": n,
        "configured": configured,
        "observed": {k: round(v, 4) for k, v in observed.items()},
        "delta": deltas,
        "tolerance": RATE_TOLERANCE,
        "ok": not problems,
        "problems": problems,
    }


def _check_latent_outcome_derivation(latent_truth) -> dict[str, Any]:
    problems = []
    outcomes_seen: set[str] = set()
    for row in latent_truth:
        outcomes_seen.add(row.latent_outcome)
        if row.doomed and row.latent_outcome not in ("churned", "downgraded"):
            problems.append(f"{row.account_id}: doomed but latent_outcome={row.latent_outcome!r}")
        if row.thriving and row.latent_outcome != "expanded":
            problems.append(f"{row.account_id}: thriving but latent_outcome={row.latent_outcome!r}")
        if not row.doomed and not row.thriving and row.latent_outcome != "flat":
            problems.append(f"{row.account_id}: neither doomed nor thriving but latent_outcome={row.latent_outcome!r}")
    return {
        "metric": "latent_outcome_derivation",
        "outcomes_seen": sorted(outcomes_seen),
        "all_four_outcomes_present": outcomes_seen == {"churned", "downgraded", "flat", "expanded"},
        "ok": not problems,
        "problems": problems[:10],  # cap: this is a derivation-bug signal, not a per-row report
    }


def _check_injection_events() -> dict[str, Any]:
    from ultra_csm.world.response import _config as response_config
    from ultra_csm.world.response import injection_event

    cfg = response_config()
    configured_rate = cfg["injection_event_rate"]
    expected_categories = set(cfg["injection_categories"])
    trials = 3000
    fired = 0
    categories_seen: set[str] = set()
    for day in range(1, trials + 1):
        event = injection_event("battery-acct", DEFAULT_WORLD_SEED, day)
        if event is not None:
            fired += 1
            categories_seen.add(event.category)
    observed_rate = fired / trials
    problems = []
    if abs(observed_rate - configured_rate) > RATE_TOLERANCE:
        problems.append(f"injection rate {observed_rate:.4f} outside +/-{RATE_TOLERANCE} of configured {configured_rate}")
    if categories_seen != expected_categories:
        problems.append(f"categories seen {sorted(categories_seen)} != configured {sorted(expected_categories)}")
    return {
        "metric": "injection_events",
        "trials": trials,
        "configured_rate": configured_rate,
        "observed_rate": round(observed_rate, 4),
        "categories_seen": sorted(categories_seen),
        "ok": not problems,
        "problems": problems,
    }


def _check_shock_window() -> dict[str, Any]:
    from ultra_csm.world.response import _config as response_config
    from ultra_csm.world.response import respond

    cfg = response_config()["shock"]
    start, duration, multiplier = cfg["shock_day"], cfg["shock_duration_days"], cfg["shock_reply_probability_multiplier"]
    latent = LatentAccountTruth(
        account_id="shock-acct", account_slug="shock-acct", anchor_account=False,
        doomed=False, thriving=False, champion_engagement="engaged", product_fit="adequate",
        org_state="stable", latent_label="battery", corruption_flags=(), causal_chain=(), observed_day=1,
    )
    before_rate = sum(
        1 for day in range(1, start) if respond("draft_customer_outreach", latent, DEFAULT_WORLD_SEED, day).replied
    ) / (start - 1)
    during_rate = sum(
        1
        for day in range(start, start + duration)
        if respond("draft_customer_outreach", latent, DEFAULT_WORLD_SEED, day).replied
    ) / duration
    problems = []
    if not during_rate < before_rate:
        problems.append(f"shock window did not lower reply rate: before={before_rate} during={during_rate}")
    return {
        "metric": "shock_window",
        "shock_day": start,
        "duration_days": duration,
        "multiplier": multiplier,
        "reply_rate_before": round(before_rate, 4),
        "reply_rate_during": round(during_rate, 4),
        "ok": not problems,
        "problems": problems,
    }


def run_battery(*, as_of: str = DEFAULT_AS_OF) -> dict[str, Any]:
    data_plane, book = _data_plane()
    shapes = _sample_shapes(data_plane, book.accounts, as_of=as_of)

    evidence_row = _variance_row("evidence_count", [s["evidence_count"] for s in shapes])
    factor_row = _variance_row("factor_count", [s["factor_count"] for s in shapes])
    source_mix = Counter(source for s in shapes for source in s["sources"])
    source_mix_row = {
        "metric": "source_mix",
        "distinct_sources": sorted(source_mix),
        "counts": dict(source_mix),
        "variance_gt_0": len(source_mix) > 1,
    }

    world_config = WorldConfig(seed=DEFAULT_WORLD_SEED, scale=DEFAULT_WORLD_SCALE)
    world = generate_world(world_config)
    dirty_data_row = _check_dirty_data_rates(world_config, world.latent_truth)
    outcome_row = _check_latent_outcome_derivation(world.latent_truth)
    injection_row = _check_injection_events()
    shock_row = _check_shock_window()

    problems = [row["metric"] for row in (evidence_row, factor_row, source_mix_row) if not row["variance_gt_0"]]
    if not shapes:
        problems.append("no accounts produced evidence -- cannot assess shape variance")
    if not dirty_data_row["ok"]:
        problems.append("dirty_data_rates")
    if not outcome_row["ok"]:
        problems.append("latent_outcome_derivation")
    if not injection_row["ok"]:
        problems.append("injection_events")
    if not shock_row["ok"]:
        problems.append("shock_window")

    return {
        "artifact": "world_diversity_battery",
        "n_accounts_total": len(book.accounts),
        "n_accounts_with_evidence": len(shapes),
        "as_of": as_of,
        "evidence_count": evidence_row,
        "factor_count": factor_row,
        "source_mix": source_mix_row,
        "dirty_data_rates": dirty_data_row,
        "latent_outcome_derivation": outcome_row,
        "injection_events": injection_row,
        "shock_window": shock_row,
        "problems": problems,
        "hard_ok": not problems,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--as-of", default=DEFAULT_AS_OF)
    args = parser.parse_args(argv)

    artifact = run_battery(as_of=args.as_of)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"world_diversity_battery: hard_ok={artifact['hard_ok']} "
        f"n_accounts_with_evidence={artifact['n_accounts_with_evidence']}/{artifact['n_accounts_total']}"
    )
    if artifact["problems"]:
        print(f"  problems: {artifact['problems']}")
    print(f"artifact -> {args.output}")
    return 0 if artifact["hard_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
