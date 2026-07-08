"""Append-only operational audit ledger.

This is distinct from ``audit.change_log``: change_log proves row provenance,
while event_log records product-level events the operations surface can show
without deriving them again at read time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from ultra_csm.platform.db import session

EXPECTED_LEDGER_EVENTS = (
    "sweep.fired",
    "value_model",
    "slot_b.draft",
    "judge.score",
    "gmail.commit",
    "reobserve.queue",
    "enterprise_onboarding.trigger",
    "enterprise_onboarding.packet",
    "enterprise_onboarding.success_plan",
    "self_serve_activation.trigger",
    "self_serve_activation.packet",
    "self_serve_activation.value_path",
    "adoption_regression.trigger",
    "adoption_regression.packet",
    "adoption_regression.interpretation",
)


@dataclass(frozen=True)
class AuditContext:
    conn: psycopg.Connection
    tenant_id: str
    actor_id: str
    now: Any = None


@dataclass(frozen=True)
class AuditEvent:
    event_id: int
    ts: Any
    event_type: str
    proposal_id: str | None
    account_ref: str | None
    detail: str
    payload: dict[str, Any]
    source_ref: str


def record_audit_event(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    event_type: str,
    source_ref: str,
    detail: str,
    proposal_id: str | None = None,
    account_ref: str | None = None,
    payload: dict[str, Any] | None = None,
    now: Any = None,
) -> int | None:
    """Insert one idempotent operational event.

    ``source_ref`` is the caller's stable idempotency key for the event type.
    A retry that reaches the same event returns ``None`` rather than creating a
    duplicate ledger row.
    """

    if event_type not in (*EXPECTED_LEDGER_EVENTS, "reobserve.result"):
        raise ValueError(f"unknown audit event type: {event_type}")
    with session(
        conn,
        tenant_id=tenant_id,
        actor_id=actor_id,
        cause_ref=f"audit:{event_type}:{source_ref}",
        now=now,
    ) as cur:
        cur.execute(
            "INSERT INTO audit.event_log "
            "(tenant_id, event_type, proposal_id, account_ref, source_ref, detail, payload) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (tenant_id, event_type, source_ref) DO NOTHING "
            "RETURNING event_id",
            (
                tenant_id,
                event_type,
                proposal_id,
                account_ref,
                source_ref,
                detail,
                Jsonb(payload or {}),
            ),
        )
        row = cur.fetchone()
    return int(row[0]) if row else None


def list_audit_events(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    limit: int,
    now: Any = None,
) -> tuple[AuditEvent, ...]:
    with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=now) as cur:
        cur.execute(
            "SELECT event_id, ts, event_type, proposal_id::text, account_ref, "
            "       detail, payload, source_ref "
            "FROM audit.event_log "
            "ORDER BY ts DESC, event_id DESC LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()
    return tuple(
        AuditEvent(
            event_id=int(row[0]),
            ts=row[1],
            event_type=row[2],
            proposal_id=row[3],
            account_ref=row[4],
            detail=row[5],
            payload=row[6] if isinstance(row[6], dict) else {},
            source_ref=row[7],
        )
        for row in rows
    )


def audit_event_storage_ready(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    now: Any = None,
) -> bool:
    with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=now) as cur:
        cur.execute("SELECT to_regclass('audit.event_log') IS NOT NULL")
        return bool(cur.fetchone()[0])
