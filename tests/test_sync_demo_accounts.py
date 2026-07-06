"""sync_demo_accounts_to_postgres: without this, comms confirm/ingest can
only be exercised against manually-seeded test accounts, never a real
account /accounts (and the UI) actually shows -- every
comms_source_mapping/internal_note/communication_signal write has an
account_id FK into Postgres's account table. /accounts serves TWO
disjoint books depending on the ``day`` query param -- both need
covering."""

from __future__ import annotations

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


def test_accounts_endpoint_default_view_lists_the_persistent_9_account_book(client: TestClient):
    """No ``day`` param -> _data_plane_for_day returns the persistent
    9-account build_sweep_fixture_data_plane book, not the 181-account one."""

    resp = client.get("/accounts")
    assert resp.status_code == 200
    assert resp.json()["account_count"] == 9


def test_accounts_endpoint_day_param_lists_the_181_account_book(client: TestClient):
    resp = client.get("/accounts", params={"day": 140})
    assert resp.status_code == 200
    assert resp.json()["account_count"] == 181


def test_comms_confirm_succeeds_against_a_real_default_view_account_with_no_manual_seed(
    client: TestClient,
):
    """The actual value this sync exists for: a real account_id straight
    off /accounts' DEFAULT view, with zero manual `INSERT INTO account`
    in this test, satisfies comms_source_mapping's FK."""

    accounts = client.get("/accounts").json()["accounts"]
    real_account_id = accounts[0]["account_id"]

    resp = client.post(
        "/comms/mappings/confirm",
        headers=AUTH_HEADERS,
        json={
            "source_type": "slack_channel",
            "external_id": "C-sync-demo-test-default",
            "account_id": real_account_id,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["mapping_id"]


def test_comms_confirm_succeeds_against_a_real_day_param_account_with_no_manual_seed(
    client: TestClient,
):
    accounts = client.get("/accounts", params={"day": 140}).json()["accounts"]
    real_account_id = accounts[0]["account_id"]

    resp = client.post(
        "/comms/mappings/confirm",
        headers=AUTH_HEADERS,
        json={
            "source_type": "slack_channel",
            "external_id": "C-sync-demo-test-day140",
            "account_id": real_account_id,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["mapping_id"]


def test_sync_is_idempotent_across_repeated_calls(client: TestClient):
    """A second sync (e.g. a hypothetical future re-run) must not fail or
    duplicate rows -- ON CONFLICT DO UPDATE, not DO NOTHING-then-crash."""

    from ultra_csm._api_helpers import sync_demo_accounts_to_postgres
    from ultra_csm.api import _CLOCK, _conn, _SEED_AGENT, _TENANT_ID

    first = sync_demo_accounts_to_postgres(
        _conn, tenant_id=_TENANT_ID, actor_id=_SEED_AGENT, now=_CLOCK
    )
    second = sync_demo_accounts_to_postgres(
        _conn, tenant_id=_TENANT_ID, actor_id=_SEED_AGENT, now=_CLOCK
    )
    assert first == second == 190
