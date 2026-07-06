"""POST /comms/ingest -- real end-to-end: confirm a mapping via the API,
call ingest, and prove the resulting note is actually queryable back
through the brief endpoint's own connector (FixtureCommsConnector), all
within one running server process (the only place this app's ephemeral
Postgres persists data at all -- see the endpoint's own docstring)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

httpx = pytest.importorskip("httpx")
fastapi_mod = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from ultra_csm.api import app  # noqa: E402
from ultra_csm.data_plane.slack_reader import PendingSlackChannel, SlackMessage  # noqa: E402

AUTH_HEADERS = {"Authorization": "Bearer lane-a-token"}

_FAKE_PENDING = PendingSlackChannel(
    channel_id="C-endpoint-test",
    channel_name="C-endpoint-test",
    messages=(
        SlackMessage(author_display_name="Marcus Webb", text="renewal risk flagged", timestamp="2026-06-01T00:00:00.0000Z"),
    ),
    candidates=(),
)


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


def test_ingest_endpoint_writes_confirmed_slack_notes_and_they_read_back(client: TestClient):
    from ultra_csm.api import _conn, _TENANT_ID, _SEED_AGENT, _CLOCK
    from ultra_csm.platform.db import session

    account_id = "eeeeeeee-0000-0000-0000-000000000001"
    with session(_conn, tenant_id=_TENANT_ID, actor_id=_SEED_AGENT, now=_CLOCK) as cur:
        cur.execute(
            "INSERT INTO account (account_id, tenant_id, name) VALUES (%s, %s, %s) "
            "ON CONFLICT (account_id) DO NOTHING",
            (account_id, _TENANT_ID, "Ingest Endpoint Test Account"),
        )

    confirm_resp = client.post(
        "/comms/mappings/confirm",
        headers=AUTH_HEADERS,
        json={"source_type": "slack_channel", "external_id": "C-endpoint-test", "account_id": account_id},
    )
    assert confirm_resp.status_code == 200

    with patch("ultra_csm.comms_mapping.live_channel_messages", return_value=_FAKE_PENDING):
        ingest_resp = client.post("/comms/ingest", headers=AUTH_HEADERS)
    assert ingest_resp.status_code == 200
    body = ingest_resp.json()
    assert body["slack_notes_written"] >= 1

    # Prove it actually persisted where the brief endpoint's own connector reads.
    from ultra_csm.data_plane.fixtures import FixtureCommsConnector

    connector = FixtureCommsConnector(conn=_conn, tenant_id=_TENANT_ID)
    notes = connector.list_internal_notes(account_id)
    assert any(n.content == "renewal risk flagged" for n in notes)


def test_ingest_endpoint_requires_auth(client: TestClient):
    resp = client.post("/comms/ingest")
    assert resp.status_code in (401, 403)
