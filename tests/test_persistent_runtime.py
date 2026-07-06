"""Persistent Postgres runtime proofs.

These tests still use a local throwaway Postgres server, but the application
sees it only through the persistent env-var contract. That proves the served
path can restart without dropping state while ``make eval`` keeps its normal
ephemeral default.
"""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

httpx = pytest.importorskip("httpx")
fastapi_mod = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from ultra_csm.api import app  # noqa: E402
from ultra_csm.platform import EphemeralCluster  # noqa: E402
from ultra_csm.platform.db import apply_migrations, assert_rls_safe_role, session  # noqa: E402
from ultra_csm.platform.runtime import (  # noqa: E402
    ADMIN_DATABASE_URL_ENV,
    RUNTIME_DATABASE_URL_ENV,
    bootstrap_persistent_database,
    connect_persistent_runtime_database,
)
from ultra_csm.platform.seed import det_uuid  # noqa: E402

_REPO = Path(__file__).resolve().parents[1]
_MIGRATIONS = _REPO / "migrations"
_AUTH_HEADERS = {"Authorization": "Bearer lane-a-token"}
_T1 = det_uuid("tenant", "acme-csm")
_T1_AGENT = det_uuid("principal", "acme-csm", "system-seed")
_T2 = det_uuid("tenant", "summit-csm")
_T2_AGENT = det_uuid("principal", "summit-csm", "system-seed")


def _conninfo(cluster: EphemeralCluster, *, user: str) -> str:
    return make_conninfo("", **cluster.dsn(user=user))


def test_migrations_are_idempotent_under_persistent_ledger():
    with EphemeralCluster() as cluster:
        with psycopg.connect(**cluster.dsn(user=cluster.BOOTSTRAP_USER)) as boot:
            apply_migrations(boot, _MIGRATIONS)
            apply_migrations(boot, _MIGRATIONS)
            cur = boot.execute("SELECT count(*) FROM public.schema_migration")
            applied = cur.fetchone()[0]

    assert applied == len(sorted(_MIGRATIONS.glob("[0-9]*_*.sql")))


def test_persistent_api_restart_keeps_proposal_verdict_and_ledger(monkeypatch):
    with EphemeralCluster() as cluster:
        monkeypatch.setenv(
            ADMIN_DATABASE_URL_ENV,
            _conninfo(cluster, user=cluster.BOOTSTRAP_USER),
        )
        monkeypatch.setenv(RUNTIME_DATABASE_URL_ENV, _conninfo(cluster, user="app_runtime"))
        monkeypatch.setenv("ULTRA_CSM_API_TOKENS", "lane-a-token:Lane A Manager")
        monkeypatch.delenv("ULTRA_CSM_DEMO_NOAUTH", raising=False)

        with TestClient(app) as client:
            sweep = client.post("/sweep", headers=_AUTH_HEADERS)
            assert sweep.status_code == 200
            proposals = client.get("/proposals").json()["proposals"]
            assert proposals
            proposal_id = proposals[0]["proposal_id"]
            verdict = client.post(
                f"/proposals/{proposal_id}/verdict",
                json={"verdict": "deny", "reason": "persistent restart proof"},
                headers=_AUTH_HEADERS,
            )
            assert verdict.status_code == 200
            assert verdict.json()["status"] == "denied"

        with TestClient(app) as restarted:
            ledger = restarted.get("/ledger?limit=200")
            assert ledger.status_code == 200
            events = ledger.json()["events"]

        persisted_events = {
            (event["proposal_id"], event["event"])
            for event in events
            if event["proposal_id"] == proposal_id
        }
        assert {
            (proposal_id, "gate.propose"),
            (proposal_id, "gate.deny"),
        } <= persisted_events
        assert {
            (proposal_id, "value_model"),
            (proposal_id, "slot_b.draft"),
            (proposal_id, "judge.score"),
        } <= persisted_events


def test_persistent_runtime_enforces_cross_tenant_rls(monkeypatch):
    with EphemeralCluster() as cluster:
        monkeypatch.setenv(
            ADMIN_DATABASE_URL_ENV,
            _conninfo(cluster, user=cluster.BOOTSTRAP_USER),
        )
        monkeypatch.setenv(RUNTIME_DATABASE_URL_ENV, _conninfo(cluster, user="app_runtime"))

        assert bootstrap_persistent_database(_MIGRATIONS) is True
        conn = connect_persistent_runtime_database()
        try:
            assert_rls_safe_role(conn)
            with session(conn, tenant_id=_T1, actor_id=_T1_AGENT) as cur:
                cur.execute(
                    "INSERT INTO principal (principal_id, tenant_id, kind, display_name) "
                    "VALUES (gen_random_uuid(), %s, 'human', %s) RETURNING principal_id",
                    (_T1, "persistent-cross-tenant-rls-probe"),
                )
                principal_id = str(cur.fetchone()[0])

            with session(conn, tenant_id=_T1, actor_id=_T1_AGENT) as cur:
                cur.execute(
                    "SELECT count(*) FROM principal WHERE principal_id = %s",
                    (principal_id,),
                )
                same_tenant_count = cur.fetchone()[0]
            with session(conn, tenant_id=_T2, actor_id=_T2_AGENT) as cur:
                cur.execute(
                    "SELECT count(*) FROM principal WHERE principal_id = %s",
                    (principal_id,),
                )
                cross_tenant_count = cur.fetchone()[0]
        finally:
            conn.close()

    assert same_tenant_count == 1
    assert cross_tenant_count == 0
