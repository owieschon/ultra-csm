"""Sim-only committers for approved CSM action proposals."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from ultra_csm.data_plane.sim_tenant import DEFAULT_DEMO_STATE_DIR, SimTenantStore
from ultra_csm.governance import (
    ActionGate,
    ActionProposal,
    GateError,
    GateOutcome,
    Verdict,
    canonical_payload_sha256,
    csm_action_spec,
)
from ultra_csm.platform.db import session


class CommitError(RuntimeError):
    """A proposal could not be committed safely."""


@dataclass(frozen=True)
class CommitReceipt:
    receipt_id: str
    proposal_id: str
    action: str
    account_id: str
    idempotency_key: str
    committed: bool
    dry_run: bool
    target: str
    payload_sha256: str


class Committer(Protocol):
    def commit(
        self,
        proposal: ActionProposal,
        outcome: GateOutcome,
        *,
        dry_run: bool = False,
    ) -> CommitReceipt: ...


def load_action_proposal(
    conn,
    *,
    tenant_id: str,
    actor_principal_id: str,
    proposal_id: str,
    now=None,
) -> ActionProposal:
    with session(conn, tenant_id=tenant_id, actor_id=actor_principal_id, now=now) as cur:
        cur.execute(
            "SELECT intent, action, payload, payload_sha256, autonomy_tier, "
            "required_permission, status FROM action_proposal WHERE proposal_id = %s",
            (proposal_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise GateError(f"proposal not found: {proposal_id}")
    intent, action, payload, payload_sha256, autonomy_tier, required_permission, status = row
    return ActionProposal(
        proposal_id=proposal_id,
        intent=str(intent),
        action=str(action),
        payload=dict(payload),
        payload_sha256=str(payload_sha256),
        autonomy_tier=int(autonomy_tier),
        required_permission=str(required_permission),
        status=str(status),
    )


def auto_approve_internal(
    gate: ActionGate,
    proposal: ActionProposal,
    *,
    system_principal_id: str,
) -> GateOutcome:
    spec = csm_action_spec(proposal.action)
    if spec.release_condition != "auto_internal_only":
        raise GateError(f"action is not auto-internal: {proposal.action}")
    return gate.record_verdict(
        proposal,
        Verdict(
            "approve",
            human_principal_id=system_principal_id,
            rationale="auto_internal_only release condition",
        ),
        cause_ref=f"auto-release:{proposal.proposal_id}",
    )


class SimOutboundCommitter:
    """Append approved customer-facing drafts to the demo outbox."""

    def __init__(
        self,
        gate: ActionGate,
        *,
        state_dir: Path | str = DEFAULT_DEMO_STATE_DIR,
    ) -> None:
        self._gate = gate
        self._state_dir = Path(state_dir)
        self._outbox = self._state_dir / "outbox.jsonl"

    def commit(
        self,
        proposal: ActionProposal,
        outcome: GateOutcome,
        *,
        dry_run: bool = False,
    ) -> CommitReceipt:
        if proposal.action != "draft_customer_outreach":
            raise CommitError(f"SimOutboundCommitter cannot commit {proposal.action}")
        self._gate.assert_payload_bound(outcome, proposal.payload)
        account_id = _required_str(proposal.payload, "account_id")
        key = _idempotency_key(proposal, outcome, target=str(self._outbox))
        already = (
            self._gate.idempotency_key_exists(key)
            if dry_run
            else not self._gate.claim_idempotency_key(
                key,
                request_id=proposal.proposal_id,
                result_ref=str(self._outbox),
                cause_ref=f"commit:{proposal.proposal_id}",
            )
        )
        receipt = _receipt(
            proposal,
            outcome,
            account_id=account_id,
            idempotency_key=key,
            target=str(self._outbox),
            dry_run=dry_run,
            committed=not already,
        )
        if dry_run or not receipt.committed:
            return receipt
        self._state_dir.mkdir(parents=True, exist_ok=True)
        _append_jsonl(self._outbox, {
            "receipt": asdict(receipt),
            "account_id": account_id,
            "contact_id": proposal.payload.get("contact_id"),
            "contact_email": proposal.payload.get("contact_email"),
            "subject": proposal.payload.get("subject"),
            "body": proposal.payload.get("body"),
            "evidence_ids": proposal.payload.get("evidence_ids", ()),
            "source": "sim",
        })
        _append_jsonl(self._state_dir / "commit_audit.jsonl", {
            "event_type": "outbound_committed",
            "receipt": asdict(receipt),
            "source": "sim",
        })
        self._gate.mark_idempotency_result(key, result_ref=str(self._outbox))
        return receipt


class SimCrmActivityCommitter:
    """Write approved activity records into the simulated CRM connector."""

    def __init__(self, gate: ActionGate, store: SimTenantStore) -> None:
        self._gate = gate
        self._store = store

    def commit(
        self,
        proposal: ActionProposal,
        outcome: GateOutcome,
        *,
        dry_run: bool = False,
    ) -> CommitReceipt:
        if proposal.action not in {
            "log_crm_activity",
            "draft_customer_outreach",
            "recommend_next_best_action",
        }:
            raise CommitError(f"SimCrmActivityCommitter cannot commit {proposal.action}")
        self._gate.assert_payload_bound(outcome, proposal.payload)
        account_id = _required_str(proposal.payload, "account_id")
        key = _idempotency_key(proposal, outcome, target=str(self._store.path))
        already = (
            self._gate.idempotency_key_exists(key)
            if dry_run
            else not self._gate.claim_idempotency_key(
                key,
                request_id=proposal.proposal_id,
                result_ref=str(self._store.path),
                cause_ref=f"commit:{proposal.proposal_id}",
            )
        )
        receipt = _receipt(
            proposal,
            outcome,
            account_id=account_id,
            idempotency_key=key,
            target=str(self._store.path),
            dry_run=dry_run,
            committed=not already,
        )
        if dry_run or already:
            return receipt
        self._store.record_activity(
            account_id,
            channel=str(proposal.payload.get("draft_channel") or proposal.payload.get("channel") or "email"),
            direction=_activity_direction(proposal.action),
            summary=str(proposal.payload.get("subject") or proposal.payload.get("body") or proposal.intent),
            idempotency_key=key,
            occurred_at=str(proposal.payload.get("as_of") or "2026-06-28") + "T12:00:00Z",
        )
        self._gate.mark_idempotency_result(key, result_ref=str(self._store.path))
        return receipt


def _receipt(
    proposal: ActionProposal,
    outcome: GateOutcome,
    *,
    account_id: str,
    idempotency_key: str,
    target: str,
    dry_run: bool,
    committed: bool,
) -> CommitReceipt:
    return CommitReceipt(
        receipt_id=canonical_payload_sha256({
            "proposal_id": proposal.proposal_id,
            "idempotency_key": idempotency_key,
            "target": target,
        })[:24],
        proposal_id=proposal.proposal_id,
        action=proposal.action,
        account_id=account_id,
        idempotency_key=idempotency_key,
        committed=committed,
        dry_run=dry_run,
        target=target,
        payload_sha256=outcome.payload_sha256,
    )


def _idempotency_key(proposal: ActionProposal, outcome: GateOutcome, *, target: str) -> str:
    return canonical_payload_sha256({
        "proposal_id": proposal.proposal_id,
        "payload_sha256": outcome.payload_sha256,
        "target": target,
    })


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise CommitError(f"payload missing required string field: {key}")
    return value


def _activity_direction(action: str) -> str:
    return "internal" if action == "recommend_next_best_action" else "outbound"


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
