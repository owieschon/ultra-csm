"""CLI behavior for connector smoke checks."""

from __future__ import annotations

import json

from ultra_csm import cli
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


def test_proposals_list_cli_reads_api(monkeypatch, capsys):
    seen = []

    def fake_urlopen(req, timeout):  # noqa: ANN001 - urllib test double
        seen.append((req.full_url, req.get_method(), timeout))
        return _Response({
            "pending_count": 1,
            "proposals": [{
                "proposal_id": "prop-1",
                "action": "draft_customer_outreach",
                "autonomy_tier": 2,
                "required_permission": "customer.outreach.draft",
                "status": "pending",
                "payload": {"account_name": "Acme Logistics"},
            }],
        })

    monkeypatch.setattr(cli.request, "urlopen", fake_urlopen)

    code = main(["proposals", "list", "--api-url", "http://api.test"])

    captured = capsys.readouterr()

    assert code == 0
    assert seen == [("http://api.test/proposals", "GET", 10)]
    assert "pending proposals: 1" in captured.out
    assert "prop-1" in captured.out
    assert "Acme Logistics" in captured.out


def test_proposals_show_cli_filters_pending_queue(monkeypatch, capsys):
    monkeypatch.setattr(cli.request, "urlopen", lambda _req, timeout: _Response({
        "pending_count": 1,
        "proposals": [{
            "proposal_id": "prop-2",
            "intent": "agent1_time_to_value_sweep",
            "action": "draft_customer_outreach",
            "autonomy_tier": 2,
            "required_permission": "customer.outreach.draft",
            "status": "pending",
            "payload": {"subject": "Time-to-Value follow-up"},
        }],
    }))

    code = main(["proposals", "show", "prop-2", "--json"])

    captured = capsys.readouterr()

    assert code == 0
    assert '"proposal_id": "prop-2"' in captured.out
    assert "Time-to-Value follow-up" in captured.out


def test_proposals_approve_cli_posts_verdict(monkeypatch, capsys):
    seen = []

    def fake_urlopen(req, timeout):  # noqa: ANN001 - urllib test double
        seen.append((
            req.full_url,
            req.get_method(),
            json.loads(req.data.decode("utf-8")),
            timeout,
        ))
        return _Response({
            "proposal_id": "prop-3",
            "status": "approved",
            "authorized": True,
            "verdict": "approve",
            "payload_sha256": "sha",
        })

    monkeypatch.setattr(cli.request, "urlopen", fake_urlopen)

    code = main([
        "proposals",
        "approve",
        "prop-3",
        "--reason",
        "Looks good",
        "--api-url",
        "http://api.test",
    ])

    captured = capsys.readouterr()

    assert code == 0
    assert seen == [(
        "http://api.test/proposals/prop-3/verdict",
        "POST",
        {"verdict": "approve", "reason": "Looks good"},
        10,
    )]
    assert "prop-3: approved (authorized=true)" in captured.out


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")
