from __future__ import annotations

import json
from pathlib import Path

from eval.knowability_audit import build_knowability_artifact
from eval.world_scoreboard import build_world_scoreboard
from ultra_csm.cli import main
from ultra_csm.world import (
    WorldConfig,
    build_baseline_report,
    build_context_graph,
    build_oracle_report,
    generate_world,
    run_knowability_audit,
    serialize_world_build,
)
from ultra_csm.world.generator import build_data_plane


def test_world_generator_is_byte_deterministic_and_contract_valid():
    left = generate_world(WorldConfig(seed=7, scale=24))
    right = generate_world(WorldConfig(seed=7, scale=24))

    assert serialize_world_build(left) == serialize_world_build(right)

    plane = build_data_plane(left.data)
    assert len(plane.crm.list_accounts()) == 24
    assert sum(1 for account in left.data.accounts if plane.cs.get_health_score(account.account_id)) == 24
    assert len(left.latent_truth) == 24
    assert len(left.surface_decisions) == 24


def test_context_graph_ships_exactly_six_load_bearing_sections():
    world = generate_world(WorldConfig(seed=9, scale=20))
    graph = build_context_graph(world)

    assert set(graph.section_counts()) == {
        "bitemporal_spine",
        "supersedence",
        "decision_nodes",
        "closed_loop_hooks",
        "identity_resolution",
        "conflict_nodes",
    }
    assert graph.section_counts()["bitemporal_spine"] >= 20
    assert graph.section_counts()["decision_nodes"] == 20
    assert graph.section_counts()["closed_loop_hooks"] == 20


def test_oracle_and_knowability_audit_pass_and_catch_planted_violation():
    world = generate_world(WorldConfig(seed=11, scale=30))
    graph = build_context_graph(world)
    oracle = build_oracle_report(world, graph)
    audit = run_knowability_audit(graph=graph, result=world, repo_root=Path.cwd())
    planted = run_knowability_audit(
        graph=graph,
        result=world,
        repo_root=Path.cwd(),
        planted_violation=True,
    )

    assert 0.0 <= oracle["false_negative_rate_vs_latent_truth"] <= 1.0
    assert 0.0 <= oracle["causal_path_recovery_rate"] <= 1.0
    assert audit["hard_ok"] is True
    assert planted["hard_ok"] is False
    assert "planted_violation:latent_truth_imported_into_surface_path" in planted["hard_failures"]


def test_baseline_report_contains_no_spine_ablation_and_pass_k_handoff():
    world = generate_world(WorldConfig(seed=13, scale=40))
    graph = build_context_graph(world)

    report = build_baseline_report(world, graph)

    assert report["no_spine_ablation"]["accuracy_delta"] >= 0.0
    assert report["pass_k_handoff"]["built_not_executed"] is True
    assert "--pass-k 8" in report["pass_k_handoff"]["recommended_command"]
    assert report["power_sizing"]["current_sample_n"] == 40


def test_world_cli_writes_artifact_and_reports_hard_gate(tmp_path, capsys):
    code = main([
        "world",
        "--seed",
        "5",
        "--scale",
        "12",
        "--output-root",
        str(tmp_path),
        "--json",
    ])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 0
    assert payload["knowability_audit"]["hard_ok"] is True
    assert (tmp_path / "seed-5" / "world.json").exists()


def test_world_eval_artifacts_cover_scoreboard_and_planted_violation():
    scoreboard = build_world_scoreboard(seed=7, scale=20)
    knowability = build_knowability_artifact(seed=7, scale=20, planted_violation=True)

    assert [row["wave"] for row in scoreboard["rows"]] == ["W0", "W1", "W2", "W3", "W4", "W5"]
    assert knowability["hard_ok"] is False
    assert knowability["planted_violation"] is True


def test_w4_row_defaults_to_built_handoff_without_a_pass_k_result():
    scoreboard = build_world_scoreboard(seed=7, scale=20)
    w4 = next(row for row in scoreboard["rows"] if row["wave"] == "W4")
    assert w4["status"] == "built_handoff"


def test_w4_row_reports_executed_when_a_pass_k_result_is_supplied():
    stub_result = {"n_draws": 63, "gated_pass_rate": 0.9524}
    scoreboard = build_world_scoreboard(seed=7, scale=20, pass_k_result=stub_result)
    w4 = next(row for row in scoreboard["rows"] if row["wave"] == "W4")
    assert w4["status"] == "executed"
    assert w4["evidence"]["pass_k_run"] == stub_result
    assert "PROGRAM_REPORT_74" in w4["evidence"]["ablation_status"]
