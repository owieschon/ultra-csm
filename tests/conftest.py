"""Boot one ephemeral cluster per session; isolate each test in a rolled-back txn.

The session-scoped cluster is the expensive part (initdb + migrate + seed). Each
test gets a fresh app_runtime connection and rolls back at teardown, so the
seeded reference state is never mutated.
"""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest

from ultra_csm.platform import boot_seeded_cluster

_REPO = Path(__file__).resolve().parents[1]
_MIGRATIONS = _REPO / "migrations"


@pytest.fixture(scope="session")
def cluster():
    with boot_seeded_cluster(_MIGRATIONS, limit=200) as (c, _dsn):
        yield c


@pytest.fixture
def runtime_conn(cluster):
    """A NOSUPERUSER NOBYPASSRLS connection — FORCE RLS is live for these."""
    conn = psycopg.connect(**cluster.dsn(user="app_runtime"))
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def bootstrap_conn(cluster):
    """A superuser connection — bypasses RLS (the asymmetry that proves FORCE)."""
    conn = psycopg.connect(**cluster.dsn(user=cluster.BOOTSTRAP_USER))
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()
