"""Deterministic seed constants and minimal CSM tenant fixtures."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from ultra_csm.platform.db import session

SEED = 20260607
SEED_CLOCK = datetime(2026, 6, 7, 12, 0, 0, tzinfo=timezone.utc)
SEED_NS = uuid.UUID("00000000-0000-0000-0000-0000000000ec")
_CLOCK = SEED_CLOCK
_NS = SEED_NS

_TENANTS = ("acme-csm", "summit-csm")


def det_uuid(*parts: str) -> str:
    """Deterministic uuid5 over the fixed seed namespace."""

    return str(uuid.uuid5(SEED_NS, ":".join(parts)))


_det_uuid = det_uuid


def engine_data_dir() -> Path:
    """Compatibility shim for callers that only need a stable repo-local path."""

    return Path(__file__).resolve().parents[3] / "eval"


def seed(bootstrap_conn: psycopg.Connection, *, limit: int | None = None) -> None:
    """Seed only the tenant/principal rows needed by the CSM governance tests."""

    del limit
    for tenant_name in _TENANTS:
        tenant_id = det_uuid("tenant", tenant_name)
        seed_agent = det_uuid("principal", tenant_name, "system-seed")
        with session(
            bootstrap_conn,
            tenant_id=tenant_id,
            actor_id=seed_agent,
            actor_kind="agent",
            cause_ref=f"seed:{SEED}",
            now=SEED_CLOCK,
        ) as cur:
            cur.execute(
                "INSERT INTO tenant (tenant_id, name) VALUES (%s, %s) "
                "ON CONFLICT (tenant_id) DO NOTHING",
                (tenant_id, tenant_name),
            )
            cur.execute(
                "INSERT INTO principal (principal_id, tenant_id, kind, display_name) "
                "VALUES (%s, %s, 'agent', %s) ON CONFLICT (principal_id) DO NOTHING",
                (seed_agent, tenant_id, "system-seed"),
            )
