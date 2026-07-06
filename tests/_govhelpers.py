"""Shared offline fixtures for governance and ActionGate tests."""

from __future__ import annotations

import uuid

import pytest

from ultra_csm.governance import (
    ROLE_CS_ORCHESTRATOR,
    ROLE_ORDER_CONFIRM_AUTHORITY,
    make_principal,
    seed_roster,
)
from ultra_csm.platform.db import session
from ultra_csm.platform.seed import _NS, SEED_CLOCK

CLOCK = SEED_CLOCK


def det(*parts: str) -> str:
    return str(uuid.uuid5(_NS, ":".join(parts)))


T1 = det("tenant", "acme-csm")
T2 = det("tenant", "summit-csm")
T1_AGENT = det("principal", "acme-csm", "system-seed")
T2_AGENT = det("principal", "summit-csm", "system-seed")


@pytest.fixture
def gov_conn(runtime_conn):
    """A runtime connection wrapped in an OUTER transaction so the governance
    writes (which flow through `session()` → `conn.transaction()`, a SAVEPOINT
    once an outer txn is open) never commit, and teardown rolls the whole case
    back. This is the per-case BEGIN..ROLLBACK discipline the eval runner uses,
    applied to these standalone tests so they leave the seeded cluster pristine."""
    runtime_conn.execute("BEGIN")
    try:
        yield runtime_conn
    finally:
        runtime_conn.rollback()


def setup_roster(conn, *, tenant=T1, seed_actor=T1_AGENT):
    """Seed CSM roles and two principals for one tenant."""
    with session(conn, tenant_id=tenant, actor_id=seed_actor, now=CLOCK) as cur:
        cur.execute(
            "INSERT INTO tenant (tenant_id, name) VALUES (%s, %s) "
            "ON CONFLICT (tenant_id) DO NOTHING",
            (tenant, "test-csm-tenant"),
        )
        cur.execute(
            "INSERT INTO principal (principal_id, tenant_id, kind, display_name) "
            "VALUES (%s, %s, 'agent', %s) ON CONFLICT (principal_id) DO NOTHING",
            (seed_actor, tenant, "system-seed"),
        )
    seed_roster(conn, tenant_id=tenant, actor_id=seed_actor, now=CLOCK)
    orch = make_principal(
        conn, tenant_id=tenant, actor_id=seed_actor,
        display_name="cs-orchestrator", role=ROLE_CS_ORCHESTRATOR, now=CLOCK)
    authority = make_principal(
        conn, tenant_id=tenant, actor_id=seed_actor,
        display_name="order-confirm-authority",
        role=ROLE_ORDER_CONFIRM_AUTHORITY, now=CLOCK)
    return orch, authority


def make_human_principal(conn, *, tenant=T1, seed_actor=T1_AGENT, display_name="human-reviewer"):
    """Create a kind='human' principal for a tenant (mirrors the shape
    `_api_helpers.py::_ensure_human_principal` uses in production, scoped to
    what tests need: no bearer-token/grant machinery, just the row the
    gate/DB human-ness check reads)."""
    principal_id = det("principal", tenant, display_name)
    with session(conn, tenant_id=tenant, actor_id=seed_actor, now=CLOCK) as cur:
        cur.execute(
            "INSERT INTO principal (principal_id, tenant_id, kind, display_name) "
            "VALUES (%s, %s, 'human', %s) ON CONFLICT (principal_id) DO NOTHING",
            (principal_id, tenant, display_name),
        )
    return principal_id


def change_log_count(conn, table, pk_key, pk_val, *, tenant=T1) -> int:
    """How many change_log rows exist for this row (provenance completeness)."""
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
        cur.execute(
            "SELECT count(*) FROM audit.change_log "
            "WHERE table_name = %s AND row_pk ->> %s = %s",
            (table, pk_key, str(pk_val)),
        )
        return cur.fetchone()[0]
