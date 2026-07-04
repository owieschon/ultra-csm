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
from dataclasses import asdict
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
        key = _idempotency_key(proposal, outcome)
        already = _ledger_has_committed_key(self._ledger_path, key)
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
            self._append_ledger(receipt, sf_task_id=None, subject=None)
            return receipt

        subject = f"{self._subject_prefix} {proposal.payload.get('subject') or proposal.intent}"
        auth = salesforce_auth_from_env(self._env, client=self._client)
        body = json.dumps({
            "WhatId": account_id,
            "Subject": subject[:255],
            "Status": "Completed",
            "ActivityDate": str(proposal.payload.get("as_of") or "")[:10] or None,
            "Description": str(proposal.payload.get("body") or "")[:32000],
        }, sort_keys=True).encode("utf-8")
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
        self._append_ledger(receipt, sf_task_id=sf_task_id, subject=subject)
        return receipt

    def _append_ledger(
        self,
        receipt: CommitReceipt,
        *,
        sf_task_id: str | None,
        subject: str | None,
    ) -> None:
        self._ledger_dir.mkdir(parents=True, exist_ok=True)
        with self._ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "receipt": asdict(receipt),
                "sf_task_id": sf_task_id,
                "subject": subject,
            }, sort_keys=True) + "\n")


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise CommitError(f"payload missing required string field: {key}")
    return value


def _idempotency_key(proposal: ActionProposal, outcome: GateOutcome) -> str:
    return canonical_payload_sha256({
        "proposal_id": proposal.proposal_id,
        "payload_sha256": outcome.payload_sha256,
    })


def _ledger_has_committed_key(path: Path, key: str) -> bool:
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if (
            entry["receipt"]["idempotency_key"] == key
            and entry["receipt"]["committed"]
            and not entry["receipt"]["dry_run"]
        ):
            return True
    return False
