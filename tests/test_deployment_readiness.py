"""Universe v2 WS-Perturbation-Drift: deployment-readiness renderer checks."""

from __future__ import annotations

from scripts.render_deployment_readiness import render


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
