from __future__ import annotations

from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from ultra_csm.action_control_demo import _PROPOSAL_ID, _TENANT_ID
from ultra_csm.action_control_sandbox_api import app
from ultra_csm.committers import SimOutboundCommitter


def test_minimal_app_exposes_only_health_contract_and_sandbox():
    paths = {route.path for route in app.routes}
    assert "/health" in paths
    assert "/demo/action-control/sandbox/evaluate" in paths
    assert "/proposals/{proposal_id}/verdict" not in paths
    assert "/comms/mappings/confirm" not in paths


def test_minimal_app_marks_every_response_uncacheable():
    with TestClient(app) as client:
        responses = (client.get("/health"), client.get("/not-a-route"))

    assert [response.status_code for response in responses] == [200, 404]
    assert all(response.headers["cache-control"] == "no-store" for response in responses)


def test_minimal_app_runs_no_login_rollback_sandbox():
    with TestClient(app) as client:
        response = client.post(
            "/demo/action-control/sandbox/evaluate",
            json={
                "schema_version": "action-control.sandbox-command-log.v1",
                "run_id": "c2fc55a8-0940-4dd4-9976-44462a1fe553",
                "expected_state_sha256": None,
                "commands": [],
            },
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["mode"] == "rollback_isolated_synthetic"


def test_minimal_app_rejects_oversized_command_logs_before_evaluation():
    with TestClient(app) as client:
        response = client.post(
            "/demo/action-control/sandbox/evaluate",
            content=b"x" * (16 * 1024 + 1),
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "detail": {"code": "SANDBOX_REQUEST_TOO_LARGE"},
    }


def test_minimal_app_returns_stable_uncached_prefix_errors():
    with TestClient(app) as client:
        response = client.post(
            "/demo/action-control/sandbox/evaluate",
            json={
                "schema_version": "action-control.sandbox-command-log.v1",
                "run_id": "f67634c7-148d-40e8-9187-0474a4469ce7",
                "expected_state_sha256": "0" * 64,
                "commands": [
                    {
                        "command_id": "285df00d-f65d-476d-a209-df7bec6cb14d",
                        "type": "approve_exact",
                    }
                ],
            },
        )

    assert response.status_code == 409
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["detail"]["code"] == "COMMAND_PREFIX_MISMATCH"


def test_validation_error_never_reflects_private_draft_input():
    private_draft = "PRIVATE-DRAFT-SENTINEL-" + "x" * 800
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/demo/action-control/sandbox/evaluate",
            json={
                "schema_version": "action-control.sandbox-command-log.v1",
                "run_id": "b467c607-6b92-42a3-88bb-e9d27b0e1d9c",
                "expected_state_sha256": "0" * 64,
                "commands": [
                    {
                        "command_id": "2eb89528-15d9-4c60-a9c6-0bdc0a27129f",
                        "type": "revise_and_approve",
                        "draft": private_draft,
                    }
                ],
            },
        )

    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "detail": {
            "code": "INVALID_SANDBOX_REQUEST",
            "fields": ["commands.0.draft"],
        }
    }
    assert "PRIVATE-DRAFT-SENTINEL" not in response.text


def test_committer_failure_is_sanitized_and_erases_database_and_filesystem(monkeypatch):
    run_id = "3f67f7a6-2e9b-4fb7-bad3-f9f4d79fb142"
    approve = {
        "command_id": "6a6a06ae-493d-45b6-8230-da5566a752e6",
        "type": "approve_exact",
    }
    commit = {
        "command_id": "adf77940-125f-4f47-a7fe-d0ed7e4991b9",
        "type": "commit_simulated",
    }
    original_commit = SimOutboundCommitter.commit
    temporary_directories: list[Path] = []

    def fail_after_physical_commit(self, proposal, outcome, *, dry_run=False):
        original_commit(self, proposal, outcome, dry_run=dry_run)
        temporary_directories.append(self._state_dir)
        assert self._outbox.exists()
        raise RuntimeError("PRIVATE-COMMITTER-SENTINEL")

    with TestClient(app, raise_server_exceptions=False) as client:
        initial = client.post(
            "/demo/action-control/sandbox/evaluate",
            json={
                "schema_version": "action-control.sandbox-command-log.v1",
                "run_id": run_id,
                "expected_state_sha256": None,
                "commands": [],
            },
        ).json()
        approved = client.post(
            "/demo/action-control/sandbox/evaluate",
            json={
                "schema_version": "action-control.sandbox-command-log.v1",
                "run_id": run_id,
                "expected_state_sha256": initial["state_sha256"],
                "commands": [approve],
            },
        ).json()
        monkeypatch.setattr(SimOutboundCommitter, "commit", fail_after_physical_commit)
        response = client.post(
            "/demo/action-control/sandbox/evaluate",
            json={
                "schema_version": "action-control.sandbox-command-log.v1",
                "run_id": run_id,
                "expected_state_sha256": approved["state_sha256"],
                "commands": [approve, commit],
            },
        )

        cluster = app.state.cluster
        assert cluster is not None
        with psycopg.connect(**cluster.dsn(user=cluster.BOOTSTRAP_USER)) as connection:
            assert _sandbox_row_counts(connection) == (0, 0, 0, 0)

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "detail": {
            "code": "SANDBOX_INTERNAL_ERROR",
            "error": "Sandbox evaluation failed safely.",
        }
    }
    assert "PRIVATE-COMMITTER-SENTINEL" not in response.text
    assert temporary_directories
    assert all(not path.exists() for path in temporary_directories)


def _sandbox_row_counts(connection) -> tuple[int, int, int, int]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM action_proposal WHERE proposal_id = %s",
            (_PROPOSAL_ID,),
        )
        proposals = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT count(*) FROM action_verdict WHERE proposal_id = %s",
            (_PROPOSAL_ID,),
        )
        verdicts = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT count(*) FROM idempotency_keys WHERE tenant_id = %s",
            (_TENANT_ID,),
        )
        idempotency_keys = int(cursor.fetchone()[0])
        cursor.execute("SELECT count(*) FROM tenant WHERE tenant_id = %s", (_TENANT_ID,))
        tenants = int(cursor.fetchone()[0])
    return proposals, verdicts, idempotency_keys, tenants
