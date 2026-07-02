"""Tests for the Ultra CSM REST API.

Uses FastAPI's TestClient to exercise every endpoint without a real server.
The API boots its own ephemeral Postgres via lifespan, so these tests are
self-contained and require only a local PostgreSQL 16 toolchain.
"""

from __future__ import annotations

import pytest

# httpx is a dev dependency; TestClient needs it.
httpx = pytest.importorskip("httpx")
fastapi_mod = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from ultra_csm.api import app  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture: shared TestClient (one lifespan boot per module)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    """A TestClient that triggers the FastAPI lifespan (ephemeral Postgres,
    seed, governance roster) once for the whole test module."""
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_ok(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["db_connected"] is True
        assert body["config_loaded"] is True
        assert body["accounts_loaded"] > 0
        assert "tenant_id" in body


# ---------------------------------------------------------------------------
# GET /accounts
# ---------------------------------------------------------------------------


class TestAccountsEndpoint:
    def test_list_accounts(self, client: TestClient):
        resp = client.get("/accounts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["account_count"] > 0
        assert len(body["accounts"]) == body["account_count"]

        # Each account should have at least id and name.
        for acct in body["accounts"]:
            assert "account_id" in acct
            assert "account_name" in acct

    def test_accounts_sorted_by_priority(self, client: TestClient):
        resp = client.get("/accounts")
        body = resp.json()
        scores = [
            a.get("priority_score", -1) for a in body["accounts"]
        ]
        # Should be sorted descending (allowing for None/-1 at the end).
        for i in range(len(scores) - 1):
            if scores[i] is not None and scores[i + 1] is not None:
                assert scores[i] >= scores[i + 1], (
                    f"Accounts not sorted: {scores[i]} < {scores[i + 1]}"
                )


# ---------------------------------------------------------------------------
# GET /accounts/{account_id}
# ---------------------------------------------------------------------------


class TestAccountDetailEndpoint:
    def test_get_valid_account(self, client: TestClient):
        # First get the list to find a real account_id.
        accounts = client.get("/accounts").json()["accounts"]
        account_id = accounts[0]["account_id"]

        resp = client.get(f"/accounts/{account_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["account_id"] == account_id
        assert "lifecycle_stage" in body
        assert "priority" in body
        assert "score" in body["priority"]
        assert "divergences" in body

    def test_missing_account_404(self, client: TestClient):
        resp = client.get("/accounts/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "ACCOUNT_NOT_FOUND"


# ---------------------------------------------------------------------------
# GET /accounts/{account_id}/brief
# ---------------------------------------------------------------------------


class TestAccountBriefEndpoint:
    def test_get_brief(self, client: TestClient):
        accounts = client.get("/accounts").json()["accounts"]
        # Pick an account that has health data (skip ones without).
        account_id = None
        for a in accounts:
            if a.get("health_band") is not None:
                account_id = a["account_id"]
                break
        assert account_id is not None, "No account with health data found"

        resp = client.get(f"/accounts/{account_id}/brief")
        assert resp.status_code == 200
        body = resp.json()
        assert body["account_id"] == account_id
        assert "health_snapshot" in body
        assert "suggested_talking_points" in body
        assert isinstance(body["suggested_talking_points"], list)
        assert "company" in body
        assert "priority" in body

    def test_brief_missing_account_404(self, client: TestClient):
        resp = client.get("/accounts/00000000-0000-0000-0000-000000000000/brief")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /sweep
# ---------------------------------------------------------------------------


class TestSweepEndpoint:
    def test_trigger_sweep(self, client: TestClient):
        resp = client.post("/sweep")
        assert resp.status_code == 200
        body = resp.json()
        assert "work_items" in body
        assert "escalations" in body
        assert "swept_accounts" in body
        assert len(body["swept_accounts"]) > 0

    def test_sweep_produces_work_items(self, client: TestClient):
        body = client.post("/sweep").json()
        # The fixture data should produce at least one work item.
        assert len(body["work_items"]) > 0


# ---------------------------------------------------------------------------
# GET /proposals  +  POST /proposals/{id}/verdict
# ---------------------------------------------------------------------------


class TestGovernanceEndpoints:
    def test_list_proposals_initially(self, client: TestClient):
        resp = client.get("/proposals")
        assert resp.status_code == 200
        body = resp.json()
        assert "proposals" in body
        assert isinstance(body["proposals"], list)

    def test_sweep_then_list_proposals(self, client: TestClient):
        # A sweep should generate proposals.
        client.post("/sweep")
        resp = client.get("/proposals")
        assert resp.status_code == 200
        body = resp.json()
        # May or may not have pending proposals depending on fixture state.
        assert "pending_count" in body

    def test_verdict_on_missing_proposal_404(self, client: TestClient):
        resp = client.post(
            "/proposals/00000000-0000-0000-0000-000000000000/verdict",
            json={"verdict": "approve", "reason": "test"},
        )
        assert resp.status_code == 404

    def test_verdict_approve(self, client: TestClient):
        # Sweep to create proposals.
        client.post("/sweep")
        proposals = client.get("/proposals").json()["proposals"]

        if not proposals:
            pytest.skip("No pending proposals to verdict")

        proposal_id = proposals[0]["proposal_id"]
        resp = client.post(
            f"/proposals/{proposal_id}/verdict",
            json={"verdict": "approve", "reason": "Approved in test"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["proposal_id"] == proposal_id
        assert body["status"] == "approved"
        assert body["authorized"] is True

    def test_verdict_already_decided_409(self, client: TestClient):
        # Sweep to create proposals.
        client.post("/sweep")
        proposals = client.get("/proposals").json()["proposals"]

        if not proposals:
            pytest.skip("No pending proposals to verdict")

        proposal_id = proposals[0]["proposal_id"]

        # First verdict.
        resp1 = client.post(
            f"/proposals/{proposal_id}/verdict",
            json={"verdict": "deny", "reason": "First verdict"},
        )
        assert resp1.status_code == 200

        # Second verdict on same proposal should be 409.
        resp2 = client.post(
            f"/proposals/{proposal_id}/verdict",
            json={"verdict": "approve", "reason": "Second attempt"},
        )
        assert resp2.status_code == 409

    def test_invalid_verdict_rejected(self, client: TestClient):
        # The Pydantic model should reject invalid verdict values.
        resp = client.post(
            "/proposals/00000000-0000-0000-0000-000000000000/verdict",
            json={"verdict": "maybe", "reason": "test"},
        )
        assert resp.status_code == 422  # Pydantic validation error


# ---------------------------------------------------------------------------
# GET /digest
# ---------------------------------------------------------------------------


class TestDigestEndpoint:
    def test_digest_returns_accounts(self, client: TestClient):
        resp = client.get("/digest")
        assert resp.status_code == 200
        body = resp.json()
        assert "prioritized_accounts" in body
        assert len(body["prioritized_accounts"]) > 0
        assert "pending_proposals" in body
        assert "commitments" in body
        assert "as_of" in body
