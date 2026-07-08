"""Persistence helpers for enterprise onboarding packets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from ultra_csm.enterprise_onboarding import EnterpriseOnboardingLaunchPacket
from ultra_csm.platform.db import session


@dataclass(frozen=True)
class StoredEnterpriseOnboardingPacket:
    packet_id: str
    account_id: str
    opportunity_id: str
    status: str
    payload: dict[str, Any]
    created_at: Any
    updated_at: Any


def upsert_enterprise_onboarding_packet(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    packet: EnterpriseOnboardingLaunchPacket,
    payload: dict[str, Any] | None = None,
    now: Any = None,
) -> StoredEnterpriseOnboardingPacket:
    packet_payload = payload or packet.to_dict()
    with session(
        conn,
        tenant_id=tenant_id,
        actor_id=actor_id,
        cause_ref=f"enterprise_onboarding.packet:{packet.packet_id}",
        now=now,
    ) as cur:
        cur.execute(
            "INSERT INTO enterprise_onboarding_packet "
            "(tenant_id, packet_id, account_id, opportunity_id, status, payload) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (tenant_id, packet_id) DO UPDATE SET "
            "  account_id = EXCLUDED.account_id, "
            "  opportunity_id = EXCLUDED.opportunity_id, "
            "  status = EXCLUDED.status, "
            "  payload = EXCLUDED.payload, "
            "  updated_at = app.clock() "
            "RETURNING packet_id, account_id, opportunity_id, status, payload, created_at, updated_at",
            (
                tenant_id,
                packet.packet_id,
                packet.account_id,
                packet.opportunity_id,
                packet.status,
                Jsonb(packet_payload),
            ),
        )
        row = cur.fetchone()
    return _stored_packet(row)


def get_enterprise_onboarding_packet(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    packet_id: str,
    now: Any = None,
) -> StoredEnterpriseOnboardingPacket | None:
    with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=now) as cur:
        cur.execute(
            "SELECT packet_id, account_id, opportunity_id, status, payload, created_at, updated_at "
            "FROM enterprise_onboarding_packet WHERE packet_id = %s",
            (packet_id,),
        )
        row = cur.fetchone()
    return _stored_packet(row) if row else None


def list_enterprise_onboarding_packets(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    account_id: str | None = None,
    opportunity_id: str | None = None,
    limit: int = 25,
    now: Any = None,
) -> tuple[StoredEnterpriseOnboardingPacket, ...]:
    filters = []
    params: list[Any] = []
    if account_id:
        filters.append("account_id = %s")
        params.append(account_id)
    if opportunity_id:
        filters.append("opportunity_id = %s")
        params.append(opportunity_id)
    where = "WHERE " + " AND ".join(filters) if filters else ""
    with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=now) as cur:
        cur.execute(
            "SELECT packet_id, account_id, opportunity_id, status, payload, created_at, updated_at "
            f"FROM enterprise_onboarding_packet {where} "
            "ORDER BY created_at DESC, packet_id DESC LIMIT %s",
            (*params, limit),
        )
        rows = cur.fetchall()
    return tuple(_stored_packet(row) for row in rows)


def _stored_packet(row) -> StoredEnterpriseOnboardingPacket:
    payload = row[4] if isinstance(row[4], dict) else {}
    return StoredEnterpriseOnboardingPacket(
        packet_id=str(row[0]),
        account_id=str(row[1]),
        opportunity_id=str(row[2]),
        status=str(row[3]),
        payload=payload,
        created_at=row[5],
        updated_at=row[6],
    )
