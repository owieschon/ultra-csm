"""World response battery (MP-W1R, Wave A). Deterministic, no LLM.

Verifies src/ultra_csm/world/response.py's respond() across the FULL
action-class mapping in knowledge/world_response_config.json -- not just
the one action type Phase 1's unit tests cover. Checks, per action:

- customer-facing actions: reply rate over N trials increases
  monotonically with the engagement band's stated probability (a real,
  ordered signal, not just "differs somehow"); determinism holds; no
  latent field appears verbatim.
- internal/no-response actions: respond() returns None for every trial,
  every engagement band, every seed tried.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import fields
from pathlib import Path
from typing import Any

from ultra_csm.world.generator import LatentAccountTruth
from ultra_csm.world.response import CONFIG_PATH, ObservableEvent, respond

ARTIFACT_DIR = Path(__file__).with_name("gold")
DEFAULT_OUTPUT = ARTIFACT_DIR / "world_response_battery.json"
TRIALS_PER_BAND = 200
SEEDS = (7, 42)


def _latent(account_id: str, champion_engagement: str) -> LatentAccountTruth:
    return LatentAccountTruth(
        account_id=account_id,
        account_slug=account_id,
        anchor_account=False,
        doomed=False,
        thriving=False,
        champion_engagement=champion_engagement,
        product_fit="adequate",
        org_state="stable",
        latent_label="battery",
        corruption_flags=(),
        causal_chain=(),
        observed_day=1,
    )


def _reply_rate(action_id: str, champion_engagement: str, seed: int) -> float:
    latent = _latent(f"acct-{champion_engagement}", champion_engagement)
    replies = sum(
        1
        for day in range(1, TRIALS_PER_BAND + 1)
        if (event := respond(action_id, latent, world_seed=seed, day=day)) is not None
        and event.replied
    )
    return replies / TRIALS_PER_BAND


def _check_customer_facing_action(action_id: str, config: dict[str, Any]) -> dict[str, Any]:
    bands = config["engagement_reply_probability"]
    ordered_bands = sorted(bands.items(), key=lambda kv: kv[1])
    problems: list[str] = []
    rates_by_seed: dict[int, dict[str, float]] = {}

    for seed in SEEDS:
        rates = {band: _reply_rate(action_id, band, seed) for band, _ in ordered_bands}
        rates_by_seed[seed] = rates
        observed_order = sorted(rates.items(), key=lambda kv: kv[1])
        if [b for b, _ in observed_order] != [b for b, _ in ordered_bands]:
            problems.append(
                f"seed={seed}: observed reply-rate order {observed_order} does not "
                f"match the configured probability order {ordered_bands}"
            )

    latent = _latent("acct-determinism", "engaged")
    first = respond(action_id, latent, world_seed=7, day=1)
    second = respond(action_id, latent, world_seed=7, day=1)
    if first != second:
        problems.append("respond() is not deterministic for identical inputs")

    event_field_names = {f.name for f in fields(ObservableEvent)}
    latent_field_names = {f.name for f in fields(LatentAccountTruth)} - {"account_id"}
    if event_field_names & latent_field_names:
        problems.append(f"ObservableEvent shares field name(s) with latent state: {event_field_names & latent_field_names}")

    return {
        "action_id": action_id,
        "response_class": "customer_facing",
        "reply_rates_by_seed": rates_by_seed,
        "problems": problems,
        "hard_ok": not problems,
    }


def _check_internal_action(action_id: str) -> dict[str, Any]:
    problems: list[str] = []
    for seed in SEEDS:
        for band in ("engaged", "high", "medium", "quiet"):
            latent = _latent(f"acct-{band}", band)
            event = respond(action_id, latent, world_seed=seed, day=1)
            if event is not None:
                problems.append(f"seed={seed} band={band}: expected None, got {event}")
    return {
        "action_id": action_id,
        "response_class": "internal_no_response",
        "problems": problems,
        "hard_ok": not problems,
    }


def run_battery() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    results = [
        _check_customer_facing_action(action_id, config)
        for action_id in config["customer_facing_actions"]
    ] + [
        _check_internal_action(action_id)
        for action_id in config["internal_no_response_actions"]
    ]
    return {
        "artifact": "world_response_battery",
        "config_path": str(CONFIG_PATH.relative_to(Path(__file__).resolve().parents[1])),
        "trials_per_band": TRIALS_PER_BAND,
        "seeds": list(SEEDS),
        "actions": results,
        "hard_ok": all(r["hard_ok"] for r in results),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    artifact = run_battery()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"world_response_battery: hard_ok={artifact['hard_ok']} actions_checked={len(artifact['actions'])}")
    for r in artifact["actions"]:
        if not r["hard_ok"]:
            print(f"  FAIL {r['action_id']}: {r['problems']}")
    print(f"artifact -> {args.output}")
    return 0 if artifact["hard_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
