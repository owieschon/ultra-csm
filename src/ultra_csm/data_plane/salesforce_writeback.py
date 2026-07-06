"""Live, create-only Salesforce write-back for approved CSM action proposals.

Mirrors :class:`~ultra_csm.committers.SimCrmActivityCommitter`'s contract
(the ``Committer`` protocol, the same idempotency-key derivation, the same
payload-binding check before executing) but commits to a real Salesforce
org instead of the simulated tenant store. Scope is deliberately narrow:

* One ``POST /sobjects/Task`` per approved proposal. Never PATCH, never
  DELETE -- no update/delete surface exists in this module at all.
* Every attempt (committed, already-committed, or dry-run) is appended to a
  ledger JSONL outside the repo so every live-created Task id stays
  traceable without ever being committed to git.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Mapping

from ultra_csm.committers import CommitError, CommitReceipt
from ultra_csm.data_plane.live_smoke import HttpClient, HttpRequest, UrllibHttpClient
from ultra_csm.data_plane.salesforce_live import salesforce_auth_from_env
from ultra_csm.governance import ActionGate, ActionProposal, GateOutcome, canonical_payload_sha256

_WRITEBACK_ACTIONS = frozenset({
    "log_crm_activity",
    "draft_customer_outreach",
    "recommend_next_best_action",
})


class SalesforceWriteError(RuntimeError):
    """A live Salesforce write-back attempt failed."""


class LiveSalesforceActivityCommitter:
    """Create-only live sibling of ``SimCrmActivityCommitter``: writes one
    Salesforce Task per approved proposal, ledgered outside the repo."""

    def __init__(
        self,
        gate: ActionGate,
        *,
        env: Mapping[str, str],
        ledger_dir: Path | str,
        client: HttpClient | None = None,
        subject_prefix: str = "UCSM-P5A",
    ) -> None:
        self._gate = gate
        self._env = env
        self._client = client or UrllibHttpClient()
        self._ledger_dir = Path(ledger_dir)
        self._ledger_path = self._ledger_dir / "writeback_ledger.jsonl"
        self._subject_prefix = subject_prefix

    def commit(
        self,
        proposal: ActionProposal,
        outcome: GateOutcome,
        *,
        dry_run: bool = False,
    ) -> CommitReceipt:
        if proposal.action not in _WRITEBACK_ACTIONS:
            raise CommitError(f"LiveSalesforceActivityCommitter cannot commit {proposal.action}")
        self._gate.assert_payload_bound(outcome, proposal.payload)
        account_id = _required_str(proposal.payload, "account_id")
        key = _idempotency_key(proposal, outcome, target="salesforce:Task")
        already = (
            self._gate.idempotency_key_exists(key)
            if dry_run
            else not self._gate.claim_idempotency_key(
                key,
                request_id=proposal.proposal_id,
                result_ref="salesforce:Task:intent",
                cause_ref=f"commit:{proposal.proposal_id}",
            )
        )
        receipt = CommitReceipt(
            receipt_id=canonical_payload_sha256({
                "proposal_id": proposal.proposal_id,
                "idempotency_key": key,
                "target": "salesforce:Task",
            })[:24],
            proposal_id=proposal.proposal_id,
            action=proposal.action,
            account_id=account_id,
            idempotency_key=key,
            committed=not already,
            dry_run=dry_run,
            target="salesforce:Task",
            payload_sha256=outcome.payload_sha256,
        )
        if dry_run or already:
            self._append_ledger(receipt, sf_task_id=None, subject=None, phase="skipped")
            return receipt

        subject = f"{self._subject_prefix} {proposal.payload.get('subject') or proposal.intent}"

        # Record intent BEFORE the POST fires, closing the crash window
        # where a process kill between the network call and the ledger
        # append could leave a real Salesforce Task with no local record. The
        # Postgres idempotency reservation above is the authority; this JSONL
        # intent row is the human-readable audit trail and always carries
        # committed=False via replace(), never the final receipt object.
        intent_receipt = replace(receipt, committed=False)
        self._append_ledger(intent_receipt, sf_task_id=None, subject=subject, phase="intent")

        auth = salesforce_auth_from_env(self._env, client=self._client)
        body = json.dumps({
            "WhatId": account_id,
            "Subject": subject[:255],
            "Status": "Completed",
            "ActivityDate": str(proposal.payload.get("as_of") or "")[:10] or None,
            "Description": str(proposal.payload.get("body") or "")[:32000],
        }, sort_keys=True).encode("utf-8")
        try:
            response = self._client.send(HttpRequest(
                "POST",
                f"{auth.instance_url}/services/data/{auth.api_version}/sobjects/Task",
                {
                    "authorization": f"Bearer {auth.access_token}",
                    "content-type": "application/json",
                },
                body=body,
            ))
            if response.status not in (200, 201):
                raise SalesforceWriteError(f"Task create failed: status {response.status}")
            result = response.json()
            sf_task_id = result.get("id") if isinstance(result, dict) else None
            if not isinstance(sf_task_id, str) or not sf_task_id:
                raise SalesforceWriteError("Task create response missing id")
        except SalesforceWriteError:
            self._append_ledger(
                replace(receipt, committed=False), sf_task_id=None, subject=subject, phase="failed",
            )
            self._gate.release_idempotency_key(key)
            raise
        self._gate.mark_idempotency_result(key, result_ref=f"salesforce:Task:{sf_task_id}")
        self._append_ledger(receipt, sf_task_id=sf_task_id, subject=subject, phase="confirmed")
        return receipt

    def _append_ledger(
        self,
        receipt: CommitReceipt,
        *,
        sf_task_id: str | None,
        subject: str | None,
        phase: str,
    ) -> None:
        self._ledger_dir.mkdir(parents=True, exist_ok=True)
        with self._ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "receipt": asdict(receipt),
                "sf_task_id": sf_task_id,
                "subject": subject,
                "ledger_phase": phase,
            }, sort_keys=True) + "\n")


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise CommitError(f"payload missing required string field: {key}")
    return value


def _idempotency_key(
    proposal: ActionProposal,
    outcome: GateOutcome,
    *,
    target: str = "salesforce:Task",
) -> str:
    return canonical_payload_sha256({
        "proposal_id": proposal.proposal_id,
        "payload_sha256": outcome.payload_sha256,
        "target": target,
    })
