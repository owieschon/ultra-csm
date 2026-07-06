"""GET /comms/pending-mappings/{slack,notion} + POST /comms/mappings/confirm.

The two GET endpoints make a live call by design (a CSM-initiated review
action, not the high-frequency brief endpoint -- see their docstrings).
The underlying live-pull functions are mocked to raise their read errors
directly: this machine has real Slack/Notion credentials configured
(discovered live, 2026-07-05 -- an earlier version of this test assumed
no creds were present and instead hit a real network call that failed on
SSL in this sandbox), so asserting on ambient credential absence would be
flaky by construction. Mocking makes the 503 path deterministic
regardless of what's in ~/ultra-csm-live-creds.env on any given machine.
The POST endpoint needs no live credentials and is exercised for real.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

httpx = pytest.importorskip("httpx")
fastapi_mod = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from ultra_csm.api import app  # noqa: E402

AUTH_HEADERS = {"Authorization": "Bearer lane-a-token"}


@pytest.fixture(scope="module")
def client():
    env = pytest.MonkeyPatch()
    env.setenv("ULTRA_CSM_API_TOKENS", "lane-a-token:Lane A Manager")
    env.delenv("ULTRA_CSM_DEMO_NOAUTH", raising=False)
    try:
        with TestClient(app) as c:
            yield c
    finally:
        env.undo()


def test_pending_slack_mappings_503s_without_live_credentials(client: TestClient):
    from ultra_csm.data_plane.slack_reader import SlackReadError

    with patch(
        "ultra_csm.data_plane.slack_reader.live_slack_channels",
        side_effect=SlackReadError("missing ULTRA_CSM_SLACK_BOT_TOKEN"),
    ):
        resp = client.get("/comms/pending-mappings/slack", headers=AUTH_HEADERS)
    assert resp.status_code == 503
    assert resp.json()["code"] == "SLACK_READ_ERROR"


def test_pending_notion_mappings_503s_without_live_credentials(client: TestClient):
    from ultra_csm.data_plane.notion_call_transcripts import NotionTranscriptReadError

    with patch(
        "ultra_csm.data_plane.notion_call_transcripts.live_call_transcripts",
        side_effect=NotionTranscriptReadError("missing ULTRA_CSM_NOTION_TOKEN"),
    ):
        resp = client.get("/comms/pending-mappings/notion", headers=AUTH_HEADERS)
    assert resp.status_code == 503
    assert resp.json()["code"] == "NOTION_READ_ERROR"


def test_pending_mappings_require_auth(client: TestClient):
    resp = client.get("/comms/pending-mappings/slack")
    assert resp.status_code in (401, 403)


def test_confirm_mapping_persists_and_returns_a_mapping_id(client: TestClient):
    """Uses a Postgres-seeded account, not one from GET /accounts: the
    demo's 181 fictional accounts (CRMAccount fixtures) have no
    corresponding Postgres `account` row today (only tenant/principal are
    seeded -- platform/seed.py), so confirming a mapping against one of
    them 403/FK-violates for real, a genuine limitation this test does
    NOT paper over (verified by first running this test unmodified
    against a real /accounts id and observing the FK violation).
    Closing that gap means seeding fixture accounts into Postgres, a
    separate, larger reconciliation this dispatch does not attempt."""

    from ultra_csm.api import _conn, _TENANT_ID, _SEED_AGENT, _CLOCK
    from ultra_csm.platform.db import session

    account_id = "dddddddd-0000-0000-0000-000000000001"
    with session(_conn, tenant_id=_TENANT_ID, actor_id=_SEED_AGENT, now=_CLOCK) as cur:
        cur.execute(
            "INSERT INTO account (account_id, tenant_id, name) VALUES (%s, %s, %s) "
            "ON CONFLICT (account_id) DO NOTHING",
            (account_id, _TENANT_ID, "Review-Endpoint Test Account"),
        )

    resp = client.post(
        "/comms/mappings/confirm",
        headers=AUTH_HEADERS,
        json={"source_type": "slack_channel", "external_id": "C-review-test", "account_id": account_id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mapping_id"]

    # Re-confirming the same external_id updates rather than erroring.
    resp2 = client.post(
        "/comms/mappings/confirm",
        headers=AUTH_HEADERS,
        json={"source_type": "slack_channel", "external_id": "C-review-test", "account_id": account_id},
    )
    assert resp2.status_code == 200
    assert resp2.json()["mapping_id"] == body["mapping_id"]
