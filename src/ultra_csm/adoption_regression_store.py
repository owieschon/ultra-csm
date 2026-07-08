"""Persistence helpers for adoption regression packets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from ultra_csm.adoption_regression import AdoptionRegressionPacket
from ultra_csm.platform.db import session


@dataclass(frozen=True)
class StoredAdoptionRegressionPacket:
    packet_id: str
    account_id: str
    metric_name: str
    status: str
    payload: dict[str, Any]
    created_at: Any
    updated_at: Any


def upsert_adoption_regression_packet(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    packet: AdoptionRegressionPacket,
    payload: dict[str, Any] | None = None,
    now: Any = None,
) -> StoredAdoptionRegressionPacket:
    packet_payload = payload or packet.to_dict()
    metric_name = (
        packet.metric_comparisons[0].metric_name
        if packet.metric_comparisons
        else "unknown"
    )
    with session(
        conn,
        tenant_id=tenant_id,
        actor_id=actor_id,
        cause_ref=f"adoption_regression.packet:{packet.packet_id}",
        now=now,
    ) as cur:
        cur.execute(
            "INSERT INTO adoption_regression_packet "
            "(tenant_id, packet_id, account_id, metric_name, status, payload) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (tenant_id, packet_id) DO UPDATE SET "
            "  account_id = EXCLUDED.account_id, "
            "  metric_name = EXCLUDED.metric_name, "
            "  status = EXCLUDED.status, "
            "  payload = EXCLUDED.payload, "
            "  updated_at = app.clock() "
            "RETURNING packet_id, account_id, metric_name, status, payload, created_at, updated_at",
            (
                tenant_id,
                packet.packet_id,
                packet.account_id,
                metric_name,
                packet.status,
                Jsonb(packet_payload),
            ),
        )
        row = cur.fetchone()
    return _stored_packet(row)


def get_adoption_regression_packet(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    packet_id: str,
    now: Any = None,
) -> StoredAdoptionRegressionPacket | None:
    with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=now) as cur:
        cur.execute(
            "SELECT packet_id, account_id, metric_name, status, payload, created_at, updated_at "
            "FROM adoption_regression_packet WHERE packet_id = %s",
            (packet_id,),
        )
        row = cur.fetchone()
    return _stored_packet(row) if row else None


def list_adoption_regression_packets(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    account_id: str | None = None,
    metric_name: str | None = None,
    limit: int = 25,
    now: Any = None,
) -> tuple[StoredAdoptionRegressionPacket, ...]:
    filters = []
    params: list[Any] = []
    if account_id:
        filters.append("account_id = %s")
        params.append(account_id)
    if metric_name:
        filters.append("metric_name = %s")
        params.append(metric_name)
    where = "WHERE " + " AND ".join(filters) if filters else ""
    with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=now) as cur:
        cur.execute(
            "SELECT packet_id, account_id, metric_name, status, payload, created_at, updated_at "
            f"FROM adoption_regression_packet {where} "
            "ORDER BY created_at DESC, packet_id DESC LIMIT %s",
            (*params, limit),
        )
        rows = cur.fetchall()
    return tuple(_stored_packet(row) for row in rows)


def _stored_packet(row) -> StoredAdoptionRegressionPacket:
    payload = row[4] if isinstance(row[4], dict) else {}
    return StoredAdoptionRegressionPacket(
        packet_id=str(row[0]),
        account_id=str(row[1]),
        metric_name=str(row[2]),
        status=str(row[3]),
        payload=payload,
        created_at=row[5],
        updated_at=row[6],
    )
