"""Bounded read-only outcome re-observation after committed actions."""

from __future__ import annotations

from typing import Any

import psycopg

from ultra_csm.audit_ledger import AuditEvent, record_audit_event
from ultra_csm.data_plane import CustomerDataPlane
from ultra_csm.governance import ActionProposal
from ultra_csm.platform.db import session


def queue_reobservation_for_proposal(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    proposal: ActionProposal,
    commit_ref: str,
    now: Any = None,
) -> int | None:
    account_id = str(proposal.payload.get("account_id") or "")
    return record_audit_event(
        conn,
        tenant_id=tenant_id,
        actor_id=actor_id,
        event_type="reobserve.queue",
        proposal_id=proposal.proposal_id,
        account_ref=account_id or None,
        source_ref=f"reobserve.queue:{proposal.proposal_id}:{commit_ref}",
        detail="Queued bounded outcome re-observation",
        payload={
            "proposal_id": proposal.proposal_id,
            "action": proposal.action,
            "account_id": account_id,
            "proposal_as_of": proposal.payload.get("as_of"),
            "commit_ref": commit_ref,
            "observations": (
                "customer_reply",
                "milestone_movement",
                "health_band_recovery",
            ),
            "customer_action": False,
        },
        now=now,
    )


def perform_due_reobservations(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    data_plane: CustomerDataPlane,
    as_of: str,
    limit: int = 25,
    now: Any = None,
) -> tuple[AuditEvent, ...]:
    """Observe queued outcomes once, read-only, and persist evidence rows."""

    queues = _pending_queues(
        conn, tenant_id=tenant_id, actor_id=actor_id, limit=limit, now=now
    )
    written: list[AuditEvent] = []
    for queue in queues:
        account_id = queue.account_ref or str(queue.payload.get("account_id") or "")
        evidence = _observe_account(data_plane, account_id=account_id, as_of=as_of)
        event_id = record_audit_event(
            conn,
            tenant_id=tenant_id,
            actor_id=actor_id,
            event_type="reobserve.result",
            proposal_id=queue.proposal_id,
            account_ref=account_id or None,
            source_ref=f"reobserve.result:{queue.event_id}",
            detail="Recorded bounded outcome re-observation",
            payload={
                "queue_event_id": queue.event_id,
                "proposal_id": queue.proposal_id,
                "account_id": account_id,
                "as_of": as_of,
                "evidence": evidence,
                "customer_action": False,
            },
            now=now,
        )
        if event_id is not None:
            written.append(
                AuditEvent(
                    event_id=event_id,
                    ts=now,
                    event_type="reobserve.result",
                    proposal_id=queue.proposal_id,
                    account_ref=account_id or None,
                    detail="Recorded bounded outcome re-observation",
                    payload=evidence,
                    source_ref=f"reobserve.result:{queue.event_id}",
                )
            )
    return tuple(written)


def _pending_queues(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    limit: int,
    now: Any = None,
) -> tuple[AuditEvent, ...]:
    with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=now) as cur:
        cur.execute(
            "SELECT q.event_id, q.ts, q.event_type, q.proposal_id::text, "
            "       q.account_ref, q.detail, q.payload, q.source_ref "
            "FROM audit.event_log q "
            "WHERE q.event_type = 'reobserve.queue' "
            "  AND NOT EXISTS ("
            "    SELECT 1 FROM audit.event_log r "
            "    WHERE r.event_type = 'reobserve.result' "
            "      AND r.payload ->> 'queue_event_id' = q.event_id::text"
            "  ) "
            "ORDER BY q.ts ASC, q.event_id ASC LIMIT %s",
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


def _observe_account(
    data_plane: CustomerDataPlane,
    *,
    account_id: str,
    as_of: str,
) -> dict[str, Any]:
    health = data_plane.cs.get_health_score(account_id) if account_id else None
    milestones = tuple(data_plane.telemetry.list_ttv_milestones(account_id)) if account_id else ()
    gmail_signals = tuple(data_plane.comms.list_gmail_signals(account_id)) if account_id else ()
    return {
        "health_band": health.band if health is not None else None,
        "health_score": health.score if health is not None else None,
        "health_observed_at": health.measured_at if health is not None else None,
        "health_recovered": (
            health.band in {"green", "healthy"} if health is not None else None
        ),
        "milestones_achieved": [
            {
                "milestone": item.milestone,
                "achieved_at": item.achieved_at,
            }
            for item in milestones
            if item.achieved_at is not None and item.achieved_at <= as_of
        ],
        "customer_reply_observed": any(
            getattr(signal, "direction", "") == "inbound" for signal in gmail_signals
        ),
        "as_of": as_of,
    }
