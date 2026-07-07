"""Materialized Centralize + PostHog telemetry dataset.

The dataset is fixture-only: it simulates Centralize app usage and PostHog
telemetry for the six named Synthetic Universe Bible arcs, with raw events and
derived ``UsageSignal`` rows kept separate.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from ultra_csm.data_plane.centralize_telemetry import (
    CENTRALIZE_ARC_PROFILES,
    CentralizeAppEvent,
    CentralizePostHogEvent,
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
    for slug, profile in CENTRALIZE_ARC_PROFILES.items():
        checkpoints = []
        for day in profile.checkpoint_days:
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
        for bundle in centralize_telemetry_timeline(slug, max(profile.checkpoint_days)):
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
        accounts[slug] = {
            "arc": profile.arc,
            "centralize_truth": profile.centralize_truth,
            "posthog_truth": profile.posthog_truth,
            "checkpoint_days": list(profile.checkpoint_days),
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
            "Centralize app/domain events plus PostHog-shaped raw telemetry for "
            "the six named fleetops bible arcs. Each account includes compact "
            "checkpoint snapshots plus a bounded sampled timeline over the arc. "
            "Raw PostHog events are not treated as semantic product truth; "
            "UsageSignal rows are derived separately."
        ),
        "source_boundaries": {
            "centralize_app": "simulated app/backend/extension events",
            "posthog": "simulated raw PostHog events emitted from Centralize app surfaces",
            "derived_usage_signals": "agent-facing rollups derived from raw events",
        },
        "accounts": accounts,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def _app_event(event: CentralizeAppEvent) -> dict[str, Any]:
    data = asdict(event)
    data["properties"] = dict(event.properties)
    return data


def _posthog_event(event: CentralizePostHogEvent) -> dict[str, Any]:
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
