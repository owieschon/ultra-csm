from __future__ import annotations

from eval.centralize_simulated_telemetry import (
    build_centralize_simulated_telemetry_artifact,
)


def test_centralize_simulated_telemetry_artifact_materializes_full_live_dataset(tmp_path):
    artifact = build_centralize_simulated_telemetry_artifact(
        output_path=tmp_path / "centralize_simulated_telemetry.json"
    )

    assert artifact["claim_boundary"] == {
        "sim": True,
        "live": False,
        "uses_live_credentials": False,
        "live_tenant_proven": False,
        "posthog_project_access_proven": False,
    }
    assert len(artifact["accounts"]) == 181
    assert {
        "pinehill-transport",
        "pinnacle-supply",
        "quarrystone-logistics",
        "aspenridge-supply",
        "meridian-fleet",
        "trailhead-logistics",
    } <= set(artifact["accounts"])
    seen_shapes_by_arc: dict[str, set[tuple[int, int]]] = {}
    for payload in artifact["accounts"].values():
        assert payload["checkpoints"]
        assert payload["timeline"]
        assert len(payload["timeline"]) > len(payload["checkpoints"])
        seen_shapes_by_arc.setdefault(payload["arc"], set())
        for checkpoint in payload["checkpoints"]:
            assert checkpoint["app_events"]
            assert checkpoint["posthog_events"]
            assert checkpoint["derived_usage_signals"]
            seen_shapes_by_arc[payload["arc"]].add(
                (len(checkpoint["app_events"]), len(checkpoint["posthog_events"]))
            )
        for point in payload["timeline"]:
            assert point["app_events"]
            assert point["posthog_events"]
            assert point["derived_usage_signals"]
    assert any(len(shapes) > 3 for shapes in seen_shapes_by_arc.values())


def test_centralize_simulated_telemetry_artifact_is_deterministic(tmp_path):
    first = build_centralize_simulated_telemetry_artifact(output_path=tmp_path / "first.json")
    second = build_centralize_simulated_telemetry_artifact(output_path=tmp_path / "second.json")

    assert first == second
