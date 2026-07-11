"""Minimal temporary-outbox committer used only by the rollback sandbox."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from ultra_csm.governance import (
    ActionGate,
    ActionProposal,
    GateError,
    GateOutcome,
    canonical_payload_sha256,
)
from ultra_csm.platform.db import session


class SandboxCommitError(RuntimeError):
    """The temporary sandbox outbox could not prove a simulated commit."""


@dataclass(frozen=True)
class SandboxCommitReceipt:
    receipt_id: str
    proposal_id: str
    action: str
    account_id: str
    idempotency_key: str
    committed: bool
    dry_run: bool
    target: str
    payload_sha256: str


def load_sandbox_proposal(
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


class RollbackSandboxCommitter:
    """Write only to a caller-owned temporary directory and prove its exact receipt."""

    def __init__(self, gate: ActionGate, *, state_dir: Path, target_ref: str) -> None:
        self._gate = gate
        self._state_dir = state_dir
        self._outbox = state_dir / "outbox.jsonl"
        self._audit = state_dir / "commit_audit.jsonl"
        self._target_ref = target_ref

    def commit(
        self,
        proposal: ActionProposal,
        outcome: GateOutcome,
    ) -> SandboxCommitReceipt:
        if proposal.action != "draft_customer_outreach":
            raise SandboxCommitError(f"sandbox cannot commit {proposal.action}")
        self._gate.assert_payload_bound(proposal, outcome, proposal.payload)
        account_id = _required_str(proposal.payload, "account_id")
        key = _idempotency_key(proposal, outcome, target=self._target_ref)
        state = self._gate.idempotency_state(key)
        target_has_result = _jsonl_contains_idempotency_key(self._outbox, key)
        attempt_token = None
        if state != "completed":
            attempt_token = self._gate.acquire_sim_idempotency_attempt(
                key,
                request_id=proposal.proposal_id,
                result_ref=self._target_ref,
                cause_ref=f"sandbox-commit:{proposal.proposal_id}",
            )
        if target_has_result and attempt_token is not None:
            _ensure_audit(self._audit, self._outbox, key)
            self._gate.mark_idempotency_result(
                key,
                result_ref=self._target_ref,
                attempt_token=attempt_token,
            )
            attempt_token = None
        already = target_has_result or attempt_token is None
        receipt = _receipt(
            proposal,
            outcome,
            account_id=account_id,
            idempotency_key=key,
            target=self._target_ref,
            committed=not already,
        )
        if already:
            return receipt
        try:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            _append_jsonl(
                self._outbox,
                {
                    "receipt": asdict(receipt),
                    "account_id": account_id,
                    "body": proposal.payload.get("body"),
                    "source": "rollback_sandbox",
                    "external_effect": False,
                },
            )
            _append_jsonl(
                self._audit,
                {
                    "event_type": "sandbox_outbound_simulated",
                    "receipt": asdict(receipt),
                    "external_effect": False,
                },
            )
        except Exception:
            self._gate.mark_idempotency_failed(
                key,
                result_ref=self._target_ref,
                attempt_token=attempt_token,
            )
            raise
        self._gate.mark_idempotency_result(
            key,
            result_ref=self._target_ref,
            attempt_token=attempt_token,
        )
        return receipt

    def assert_committed_receipt(
        self,
        proposal: ActionProposal,
        outcome: GateOutcome,
        receipt: SandboxCommitReceipt,
    ) -> None:
        self._gate.assert_payload_bound(proposal, outcome, proposal.payload)
        account_id = _required_str(proposal.payload, "account_id")
        key = _idempotency_key(proposal, outcome, target=self._target_ref)
        expected = _receipt(
            proposal,
            outcome,
            account_id=account_id,
            idempotency_key=key,
            target=self._target_ref,
            committed=True,
        )
        if receipt != expected:
            raise SandboxCommitError("sandbox receipt does not match the bound commit")
        if self._gate.idempotency_state(key) != "completed":
            raise SandboxCommitError("sandbox receipt is not durably complete")
        if not _jsonl_contains_receipt(self._outbox, receipt):
            raise SandboxCommitError("sandbox receipt is absent from the temporary outbox")


def _receipt(
    proposal: ActionProposal,
    outcome: GateOutcome,
    *,
    account_id: str,
    idempotency_key: str,
    target: str,
    committed: bool,
) -> SandboxCommitReceipt:
    return SandboxCommitReceipt(
        receipt_id=canonical_payload_sha256(
            {
                "proposal_id": proposal.proposal_id,
                "idempotency_key": idempotency_key,
                "target": target,
            }
        )[:24],
        proposal_id=proposal.proposal_id,
        action=proposal.action,
        account_id=account_id,
        idempotency_key=idempotency_key,
        committed=committed,
        dry_run=False,
        target=target,
        payload_sha256=outcome.payload_sha256,
    )


def _idempotency_key(proposal: ActionProposal, outcome: GateOutcome, *, target: str) -> str:
    return canonical_payload_sha256(
        {
            "proposal_id": proposal.proposal_id,
            "payload_sha256": outcome.payload_sha256,
            "target": target,
        }
    )


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise SandboxCommitError(f"payload missing required string field: {key}")
    return value


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _jsonl_contains_idempotency_key(path: Path, key: str) -> bool:
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        receipt = payload.get("receipt") if isinstance(payload, dict) else None
        if isinstance(receipt, dict) and receipt.get("idempotency_key") == key:
            return True
    return False


def _jsonl_contains_receipt(path: Path, receipt: SandboxCommitReceipt) -> bool:
    if not path.exists():
        return False
    expected = asdict(receipt)
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("receipt") == expected:
            return True
    return False


def _ensure_audit(audit_path: Path, outbox_path: Path, key: str) -> None:
    if _jsonl_contains_idempotency_key(audit_path, key):
        return
    receipt = None
    for line in outbox_path.read_text(encoding="utf-8").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        candidate = payload.get("receipt") if isinstance(payload, dict) else None
        if isinstance(candidate, dict) and candidate.get("idempotency_key") == key:
            receipt = candidate
            break
    if receipt is None:
        raise SandboxCommitError("temporary outbox result is missing during reconciliation")
    _append_jsonl(
        audit_path,
        {
            "event_type": "sandbox_outbound_reconciled",
            "receipt": receipt,
            "external_effect": False,
        },
    )
