"""Persistence helpers for self-serve activation packets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from ultra_csm.platform.db import session
from ultra_csm.self_serve_activation import SelfServeActivationPacket


@dataclass(frozen=True)
class StoredSelfServeActivationPacket:
    packet_id: str
    account_id: str
    workspace_id: str
    signup_email: str
    status: str
    payload: dict[str, Any]
    created_at: Any
    updated_at: Any


def upsert_self_serve_activation_packet(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    packet: SelfServeActivationPacket,
    payload: dict[str, Any] | None = None,
    now: Any = None,
) -> StoredSelfServeActivationPacket:
    packet_payload = payload or packet.to_dict()
    with session(
        conn,
        tenant_id=tenant_id,
        actor_id=actor_id,
        cause_ref=f"self_serve_activation.packet:{packet.packet_id}",
        now=now,
    ) as cur:
        cur.execute(
            "INSERT INTO self_serve_activation_packet "
            "(tenant_id, packet_id, account_id, workspace_id, signup_email, status, payload) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (tenant_id, packet_id) DO UPDATE SET "
            "  account_id = EXCLUDED.account_id, "
            "  workspace_id = EXCLUDED.workspace_id, "
            "  signup_email = EXCLUDED.signup_email, "
            "  status = EXCLUDED.status, "
            "  payload = EXCLUDED.payload, "
            "  updated_at = app.clock() "
            "RETURNING packet_id, account_id, workspace_id, signup_email, status, payload, created_at, updated_at",
            (
                tenant_id,
                packet.packet_id,
                packet.account_id,
                packet.workspace_id,
                packet.signup_email,
                packet.status,
                Jsonb(packet_payload),
            ),
        )
        row = cur.fetchone()
    return _stored_packet(row)


def get_self_serve_activation_packet(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    packet_id: str,
    now: Any = None,
) -> StoredSelfServeActivationPacket | None:
    with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=now) as cur:
        cur.execute(
            "SELECT packet_id, account_id, workspace_id, signup_email, status, payload, created_at, updated_at "
            "FROM self_serve_activation_packet WHERE packet_id = %s",
            (packet_id,),
        )
        row = cur.fetchone()
    return _stored_packet(row) if row else None


def list_self_serve_activation_packets(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    account_id: str | None = None,
    workspace_id: str | None = None,
    limit: int = 25,
    now: Any = None,
) -> tuple[StoredSelfServeActivationPacket, ...]:
    filters = []
    params: list[Any] = []
    if account_id:
        filters.append("account_id = %s")
        params.append(account_id)
    if workspace_id:
        filters.append("workspace_id = %s")
        params.append(workspace_id)
    where = "WHERE " + " AND ".join(filters) if filters else ""
    with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=now) as cur:
        cur.execute(
            "SELECT packet_id, account_id, workspace_id, signup_email, status, payload, created_at, updated_at "
            f"FROM self_serve_activation_packet {where} "
            "ORDER BY created_at DESC, packet_id DESC LIMIT %s",
            (*params, limit),
        )
        rows = cur.fetchall()
    return tuple(_stored_packet(row) for row in rows)


def _stored_packet(row) -> StoredSelfServeActivationPacket:
    payload = row[5] if isinstance(row[5], dict) else {}
    return StoredSelfServeActivationPacket(
        packet_id=str(row[0]),
        account_id=str(row[1]),
        workspace_id=str(row[2]),
        signup_email=str(row[3]),
        status=str(row[4]),
        payload=payload,
        created_at=row[6],
        updated_at=row[7],
    )
