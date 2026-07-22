"""Universe v2 WS-Perturbation-Drift: deployment-readiness renderer checks."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.render_deployment_readiness import (
    DRIFT_ARTIFACTS,
    PERTURBATION_ARTIFACTS,
    render,
)


ROOT = Path(__file__).resolve().parents[1]


def test_deployment_readiness_has_no_missing_or_unreadable_cells():
    rendered = render()
    assert "MISSING ARTIFACT" not in rendered
    assert "UNREADABLE" not in rendered


def test_deployment_readiness_summary_is_all_true():
    rendered = render()
    assert "All tenant + cross-cutting batteries `hard_ok`: **true**" in rendered
    assert "All four tenants' week-1 protocol `ok`: **true**" in rendered


def test_deployment_readiness_is_deterministic():
    assert render() == render()


def test_deployment_readiness_includes_each_tenants_resilience_artifacts():
    rendered = render()
    expected_tenants = {"fleetops", "fieldstone", "crateworks", "loopway"}

    assert {tenant for tenant, _path in PERTURBATION_ARTIFACTS} == expected_tenants
    assert {tenant for tenant, _path in DRIFT_ARTIFACTS} == expected_tenants
    for tenant, path in (*PERTURBATION_ARTIFACTS, *DRIFT_ARTIFACTS):
        payload = json.loads((ROOT / path).read_text(encoding="utf-8"))
        assert payload["hard_ok"] is True
        assert f"| {tenant} |" in rendered
        assert f"`{path}`" in rendered


def test_active_eval_docs_match_committed_execution_state():
    world = (ROOT / "docs/WORLD.md").read_text(encoding="utf-8")
    standard = (ROOT / "docs/EVAL_STANDARD.md").read_text(encoding="utf-8")
    conventions = (ROOT / "docs/UNIVERSE_V2_CONVENTIONS.md").read_text(encoding="utf-8")
    pass_k = json.loads((ROOT / "eval/gold/q4_pass_k_report.json").read_text())

    assert str(pass_k["arm"]["n_draws"]) in world
    assert str(pass_k["arm"]["pass_k_rate"]) in world
    assert "blocked, not run" in standard
    assert "operator handoff only" not in standard
    assert "(eventually) perturbation/drift" not in conventions
    assert "no downstream lens/sweep/precedence" not in conventions
