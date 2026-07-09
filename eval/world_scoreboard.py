"""Scoreboard rows for the MP-F1 living-world build."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ultra_csm.world import (
    WorldConfig,
    build_baseline_report,
    build_context_graph,
    build_oracle_report,
    generate_world,
    run_knowability_audit,
)

ARTIFACT_PATH = Path(__file__).with_name("world_scoreboard.json")


def build_world_scoreboard(
    *,
    seed: int,
    scale: int,
    pass_k: int = 8,
    model: str = "claude-sonnet-5",
) -> dict[str, Any]:
    world = generate_world(WorldConfig(seed=seed, scale=scale))
    graph = build_context_graph(world)
    oracle = build_oracle_report(world, graph)
    audit = run_knowability_audit(
        world,
        graph,
        repo_root=Path(__file__).resolve().parents[1],
    )
    baselines = build_baseline_report(world, graph)
    return {
        "artifact": "living_world_scoreboard",
        "schema_version": 1,
        "seed": seed,
        "scale": scale,
        "rows": [
            {
                "wave": "W0",
                "status": "built",
                "summary": "Transport adapter routes live calls through Anthropic API or Claude Code with token telemetry.",
                "evidence": "docs/OPERATOR_RUNBOOK.md#r0-transport-adapter",
            },
            {
                "wave": "W1",
                "status": "built",
                "summary": "Deterministic seeded living world with anchors, corruption processes, and latent/surface split.",
                "evidence": f"accounts={len(world.data.accounts)} latent={len(world.latent_truth)}",
            },
            {
                "wave": "W2",
                "status": "built",
                "summary": "Context graph ships exactly the six required sections and no staged stubs.",
                "evidence": graph.section_counts(),
            },
            {
                "wave": "W3",
                "status": "built",
                "summary": "Oracle metrics and knowability audit are live; planted-violation mode is available for proof.",
                "evidence": {
                    "hard_ok": audit["hard_ok"],
                    "false_negative_rate": oracle["false_negative_rate_vs_latent_truth"],
                },
            },
            {
                "wave": "W4",
                "status": "built_handoff",
                "summary": "Deterministic degenerate baselines run locally; pass^k is documented but not executed.",
                "evidence": {
                    "pass_k": pass_k,
                    "model": model,
                    "command": baselines["pass_k_handoff"]["recommended_command"],
                },
            },
            {
                "wave": "W5",
                "status": "built",
                "summary": "Scoreboard artifact and docs map the build against the stated frontier standard and remaining gaps.",
                "evidence": "docs/WORLD.md docs/EVAL_STANDARD.md",
            },
        ],
        "oracle": oracle,
        "knowability_audit": audit,
        "baselines": baselines,
    }


def write_world_scoreboard(
    path: Path = ARTIFACT_PATH,
    *,
    seed: int,
    scale: int,
    pass_k: int = 8,
    model: str = "claude-sonnet-5",
) -> dict[str, Any]:
    artifact = build_world_scoreboard(seed=seed, scale=scale, pass_k=pass_k, model=model)
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--scale", type=int, default=60)
    parser.add_argument("--pass-k", type=int, default=8)
    parser.add_argument("--model", default="claude-sonnet-5")
    parser.add_argument("--output", default=str(ARTIFACT_PATH))
    args = parser.parse_args(argv)

    artifact = write_world_scoreboard(
        Path(args.output),
        seed=args.seed,
        scale=args.scale,
        pass_k=args.pass_k,
        model=args.model,
    )
    for row in artifact["rows"]:
        print(f"{row['wave']}: {row['status']} - {row['summary']}")
    print(f"artifact -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
