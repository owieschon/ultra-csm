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
        target_ref: str | None = None,
    ) -> None:
        self._gate = gate
        self._state_dir = Path(state_dir)
        self._outbox = self._state_dir / "outbox.jsonl"
        self._target_ref = target_ref or str(self._outbox)

    def commit(
        self,
        proposal: ActionProposal,
        outcome: GateOutcome,
        *,
        dry_run: bool = False,
    ) -> CommitReceipt:
        if proposal.action != "draft_customer_outreach":
            raise CommitError(f"SimOutboundCommitter cannot commit {proposal.action}")
        self._gate.assert_payload_bound(
            proposal, outcome, proposal.payload, require_durable=not dry_run,
        )
        account_id = _required_str(proposal.payload, "account_id")
        key = _idempotency_key(proposal, outcome, target=self._target_ref)
        state = self._gate.idempotency_state(key)
        target_has_result = _jsonl_contains_idempotency_key(self._outbox, key)
        attempt_token = None
        if not dry_run and state != "completed":
            attempt_token = self._gate.acquire_sim_idempotency_attempt(
                key,
                request_id=proposal.proposal_id,
                result_ref=self._target_ref,
                cause_ref=f"commit:{proposal.proposal_id}",
            )
        if target_has_result and not dry_run and attempt_token is not None:
            # Only the owner of a newly acquired failed/expired lease may
            # reconcile. A caller observing an active lease returns in-progress
            # and cannot steal completion from the writer.
            _ensure_outbound_audit(
                self._state_dir / "commit_audit.jsonl", self._outbox, key,
            )
            self._gate.mark_idempotency_result(
                key, result_ref=self._target_ref, attempt_token=attempt_token,
            )
            state = "completed"
            attempt_token = None
        already = (
            state is not None or target_has_result
            if dry_run
            else target_has_result or attempt_token is None
        )
        receipt = _receipt(
            proposal,
            outcome,
            account_id=account_id,
            idempotency_key=key,
            target=self._target_ref,
            dry_run=dry_run,
            committed=not already,
        )
        if dry_run or not receipt.committed:
            return receipt
        if attempt_token is None:  # defensive narrowing; committed implies lease ownership
            raise CommitError(f"missing idempotency lease for {key}")
        try:
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
        except Exception:
            self._gate.mark_idempotency_failed(
                key, result_ref=self._target_ref, attempt_token=attempt_token,
            )
            raise
        self._gate.mark_idempotency_result(
            key, result_ref=self._target_ref, attempt_token=attempt_token,
        )
        return receipt

    def assert_committed_receipt(
        self,
        proposal: ActionProposal,
        outcome: GateOutcome,
        receipt: CommitReceipt,
    ) -> None:
        """Require a receipt produced by this bound simulated outbox.

        A receipt-shaped object is not evidence. This check recomputes every
        deterministic receipt field, requires the idempotency record to be
        complete, and finds the exact receipt in the physical outbox before a
        reporting layer may present it as a completed simulated action.
        """

        self._gate.assert_payload_bound(proposal, outcome, proposal.payload)
        if not receipt.receipt_id or not receipt.idempotency_key:
            raise CommitError("simulated receipt identifiers must be non-empty")
        if not receipt.committed or receipt.dry_run:
            raise CommitError("simulated receipt must represent a committed attempt")
        account_id = _required_str(proposal.payload, "account_id")
        key = _idempotency_key(proposal, outcome, target=self._target_ref)
        expected = _receipt(
            proposal,
            outcome,
            account_id=account_id,
            idempotency_key=key,
            target=self._target_ref,
            dry_run=False,
            committed=True,
        )
        if receipt != expected:
            raise CommitError("simulated receipt does not match the bound commit")
        if self._gate.idempotency_state(key) != "completed":
            raise CommitError("simulated receipt idempotency record is not complete")
        if not _jsonl_contains_receipt(self._outbox, receipt):
            raise CommitError("simulated receipt is absent from the outbox")


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
        self._gate.assert_payload_bound(
            proposal, outcome, proposal.payload, require_durable=not dry_run,
        )
        account_id = _required_str(proposal.payload, "account_id")
        key = _idempotency_key(proposal, outcome, target=str(self._store.path))
        state = self._gate.idempotency_state(key)
        attempt_token = None
        if not dry_run and state != "completed":
            attempt_token = self._gate.acquire_sim_idempotency_attempt(
                key,
                request_id=proposal.proposal_id,
                result_ref=str(self._store.path),
                cause_ref=f"commit:{proposal.proposal_id}",
            )
        already = state is not None if dry_run else attempt_token is None
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
        if attempt_token is None:  # defensive narrowing; committed implies lease ownership
            raise CommitError(f"missing idempotency lease for {key}")
        try:
            # SimTenantStore.record_activity is itself idempotent by key, so a
            # pending/failed reservation can safely replay after a crash.
            self._store.record_activity(
                account_id,
                channel=str(proposal.payload.get("draft_channel") or proposal.payload.get("channel") or "email"),
                direction=_activity_direction(proposal.action),
                summary=str(proposal.payload.get("subject") or proposal.payload.get("body") or proposal.intent),
                idempotency_key=key,
                occurred_at=str(proposal.payload.get("as_of") or "2026-06-28") + "T12:00:00Z",
            )
        except Exception:
            self._gate.mark_idempotency_failed(
                key, result_ref=str(self._store.path), attempt_token=attempt_token,
            )
            raise
        self._gate.mark_idempotency_result(
            key, result_ref=str(self._store.path), attempt_token=attempt_token,
        )
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


def _jsonl_contains_idempotency_key(path: Path, key: str) -> bool:
    """Return whether a completed simulated target row already carries ``key``.

    Malformed/truncated rows are ignored: they are not proof of a completed
    mutation and a later append remains distinguishable by the stable key.
    """
    if not path.exists():
        return False
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            receipt = payload.get("receipt") if isinstance(payload, dict) else None
            if isinstance(receipt, dict) and receipt.get("idempotency_key") == key:
                return True
    return False


def _jsonl_contains_receipt(path: Path, receipt: CommitReceipt) -> bool:
    """Return whether the outbox contains this exact receipt payload."""

    if not path.exists():
        return False
    expected = asdict(receipt)
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("receipt") == expected:
                return True
    return False


def _ensure_outbound_audit(audit_path: Path, outbox_path: Path, key: str) -> None:
    """Repair the audit half of an outbox write before marking it complete."""
    if _jsonl_contains_idempotency_key(audit_path, key):
        return
    receipt = None
    with outbox_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            candidate = payload.get("receipt") if isinstance(payload, dict) else None
            if isinstance(candidate, dict) and candidate.get("idempotency_key") == key:
                receipt = candidate
                break
    if receipt is None:
        raise CommitError(f"outbox result missing while reconciling key {key}")
    _append_jsonl(audit_path, {
        "event_type": "outbound_reconciled",
        "receipt": receipt,
        "source": "sim",
    })
