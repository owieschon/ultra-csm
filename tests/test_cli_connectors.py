"""CLI behavior for connector smoke checks."""

from __future__ import annotations

from ultra_csm.cli import main


def test_connector_smoke_cli_reports_missing_credentials(capsys):
    code = main(["connectors", "smoke", "attio_crm", "--json"])

    captured = capsys.readouterr()

    assert code == 2
    assert '"connector_id": "attio_crm"' in captured.out
    assert '"state": "shape_verified_pending_live_creds"' in captured.out
    assert "ULTRA_CSM_ATTIO_ACCESS_TOKEN" in captured.out


def test_connector_smoke_cli_dry_run_uses_configured_boundary(monkeypatch, capsys):
    monkeypatch.setenv("ULTRA_CSM_ROCKETLANE_API_KEY", "token")

    code = main(["connectors", "smoke", "rocketlane_onboarding", "--dry-run"])

    captured = capsys.readouterr()

    assert code == 0
    assert "rocketlane_onboarding: shape_verified_pending_live_creds" in captured.out
    assert "ok: projects_sample" in captured.out
