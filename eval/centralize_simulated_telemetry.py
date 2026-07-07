"""Materialized FleetOps + PostHog telemetry dataset.

The dataset is fixture-only: it simulates FleetOps app usage and PostHog
telemetry for every live synthetic account. The six named Synthetic Universe
Bible arcs keep their hand-scripted story exhaust; the rest use deterministic
persona/lifecycle telemetry with account/day perturbation. Raw events and
derived ``UsageSignal`` rows stay separate.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from ultra_csm.data_plane.centralize_telemetry import (
    CENTRALIZE_ARC_PROFILES,
    FleetOpsAppEvent,
    FleetOpsPostHogEvent,
    centralize_account_slugs,
    centralize_telemetry_bundle,
    centralize_telemetry_timeline,
)
from ultra_csm.data_plane.contracts import UsageSignal

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO / "eval" / "centralize_simulated_telemetry.json"


def build_centralize_simulated_telemetry_artifact(
    *, output_path: Path = DEFAULT_OUTPUT
) -> dict[str, Any]:
    accounts: dict[str, Any] = {}
    for slug in centralize_account_slugs():
        profile = CENTRALIZE_ARC_PROFILES.get(slug)
        checkpoint_days = profile.checkpoint_days if profile is not None else (30, 90, 140)
        checkpoints = []
        for day in checkpoint_days:
            bundle = centralize_telemetry_bundle(slug, day)
            checkpoints.append(
                {
                    "day_offset": day,
                    "app_events": [_app_event(event) for event in bundle.app_events],
                    "posthog_events": [_posthog_event(event) for event in bundle.posthog_events],
                    "derived_usage_signals": [
                        _usage_signal(signal) for signal in bundle.usage_signals
                    ],
                }
            )
        timeline = []
        for bundle in centralize_telemetry_timeline(slug, max(checkpoint_days)):
            timeline.append(
                {
                    "day_offset": bundle.day_offset,
                    "app_events": [_app_event(event) for event in bundle.app_events],
                    "posthog_events": [_posthog_event(event) for event in bundle.posthog_events],
                    "derived_usage_signals": [
                        _usage_signal(signal) for signal in bundle.usage_signals
                    ],
                }
            )
        first_props = dict(checkpoints[0]["app_events"][0]["properties"])
        arc = profile.arc if profile is not None else first_props.get("archetype", "generic_account")
        accounts[slug] = {
            "arc": arc,
            "centralize_truth": (
                profile.centralize_truth
                if profile is not None
                else "deterministic lifecycle/persona app exhaust with account-level perturbation"
            ),
            "posthog_truth": (
                profile.posthog_truth
                if profile is not None
                else "PostHog-shaped pageview/autocapture/session replay exhaust with identity and noise jitter"
            ),
            "checkpoint_days": list(checkpoint_days),
            "checkpoints": checkpoints,
            "timeline": timeline,
        }

    artifact = {
        "artifact": "centralize_simulated_telemetry",
        "generated_by": "eval.centralize_simulated_telemetry",
        "claim_boundary": {
            "sim": True,
            "live": False,
            "uses_live_credentials": False,
            "live_tenant_proven": False,
            "posthog_project_access_proven": False,
        },
        "measurement_scope": (
            "FleetOps app/domain events plus PostHog-shaped raw telemetry for "
            "all live synthetic accounts. Six named fleetops bible arcs are "
            "hand-scripted; the remaining accounts use deterministic archetypes "
            "with per-account/day perturbation. Each account includes compact "
            "checkpoint snapshots plus a bounded sampled timeline. Raw PostHog "
            "events are not treated as semantic product truth; UsageSignal rows "
            "are derived separately."
        ),
        "source_boundaries": {
            "centralize_app": "simulated app/backend/extension events",
            "posthog": "simulated raw PostHog events emitted from FleetOps app surfaces",
            "derived_usage_signals": "agent-facing rollups derived from raw events",
        },
        "accounts": accounts,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def _app_event(event: FleetOpsAppEvent) -> dict[str, Any]:
    data = asdict(event)
    data["properties"] = dict(event.properties)
    return data


def _posthog_event(event: FleetOpsPostHogEvent) -> dict[str, Any]:
    data = asdict(event)
    data["properties"] = dict(event.properties)
    return data


def _usage_signal(signal: UsageSignal) -> dict[str, Any]:
    return asdict(signal)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    artifact = build_centralize_simulated_telemetry_artifact(output_path=args.output)
    print(
        json.dumps(
            {
                "artifact": str(args.output),
                "accounts": sorted(artifact["accounts"]),
                "live_tenant_proven": artifact["claim_boundary"]["live_tenant_proven"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
