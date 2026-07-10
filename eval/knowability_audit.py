"""Hard-gate knowability audit for the living world."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ultra_csm.world import WorldConfig, build_context_graph, generate_world, run_knowability_audit

ARTIFACT_PATH = Path(__file__).with_name("knowability_audit.json")


def build_knowability_artifact(
    *,
    seed: int,
    scale: int,
    planted_violation: bool = False,
) -> dict[str, Any]:
    world = generate_world(WorldConfig(seed=seed, scale=scale))
    graph = build_context_graph(world)
    audit = run_knowability_audit(
        world,
        graph,
        planted_violation=planted_violation,
        repo_root=Path(__file__).resolve().parents[1],
    )
    return {
        "artifact": "knowability_audit",
        "schema_version": 1,
        "seed": seed,
        "scale": scale,
        **audit,
    }


def write_knowability_artifact(
    path: Path = ARTIFACT_PATH,
    *,
    seed: int,
    scale: int,
    planted_violation: bool = False,
) -> dict[str, Any]:
    artifact = build_knowability_artifact(
        seed=seed,
        scale=scale,
        planted_violation=planted_violation,
    )
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--scale", type=int, default=60)
    parser.add_argument("--output", default=str(ARTIFACT_PATH))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--planted-violation", action="store_true")
    args = parser.parse_args(argv)

    artifact = write_knowability_artifact(
        Path(args.output),
        seed=args.seed,
        scale=args.scale,
        planted_violation=args.planted_violation,
    )
    print(
        f"seed={artifact['seed']} scale={artifact['scale']} "
        f"hard_ok={artifact['hard_ok']} failures={len(artifact['hard_failures'])}"
    )
    if args.check and not artifact["hard_ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
