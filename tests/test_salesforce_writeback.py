"""Lane C: live Salesforce write-back committer -- create-only, ledgered,
idempotent. Exercised here against a fake HTTP transport (no live network);
the live run against a real seeded corpus B account is a separate,
env-gated, manually-invoked path documented in docs/PROGRAM_REPORT_6.md.
"""

from __future__ import annotations

import json

import pytest

from ultra_csm.agent1 import run_time_to_value_sweep
from ultra_csm.committers import load_action_proposal
from ultra_csm.data_plane import ACME_LOGISTICS, DEFAULT_TENANT, SimTenantStore
from ultra_csm.data_plane import salesforce_writeback as committer_module
from ultra_csm.data_plane.live_smoke import HttpRequest, HttpResponse
from ultra_csm.data_plane.salesforce_writeback import (
    LiveSalesforceActivityCommitter,
    SalesforceWriteError,
)
from ultra_csm.governance import ActionGate, FixtureVerdictSource, Verdict

from tests._govhelpers import CLOCK, T1, setup_roster

AS_OF = "2026-06-27"
_ENV = {
    "ULTRA_CSM_SALESFORCE_INSTANCE_URL": "https://fake.my.salesforce.com",
    "ULTRA_CSM_SALESFORCE_ACCESS_TOKEN": "fake-token",
    "ULTRA_CSM_SALESFORCE_API_VERSION": "v61.0",
}


class _FakeTaskClient:
    """Records every request; create-only -- no update/delete verb ever sent."""

    def __init__(self, *, status: int = 201, task_id: str = "00TfakeTaskId000001"):
        self.requests: list[HttpRequest] = []
        self._status = status
        self._task_id = task_id

    def send(self, req: HttpRequest) -> HttpResponse:
        self.requests.append(req)
        assert req.method == "POST", "write-back must never issue a non-POST verb"
        return HttpResponse(
            status=self._status,
            body=json.dumps({"id": self._task_id, "success": True}).encode("utf-8"),
            headers={"content-type": "application/json"},
        )


def _bridge_ctx(runtime_conn, tmp_path):
    orch, authority = setup_roster(runtime_conn)
    gate = ActionGate(
        runtime_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )
    store = SimTenantStore.seed(tmp_path, tenant_id=DEFAULT_TENANT, reset=True)
    sweep = run_time_to_value_sweep(
        store.data_plane(), DEFAULT_TENANT, gate, sweep_principal_id=orch, as_of=AS_OF,
    )
    item = next(i for i in sweep.work_items if i.account_id == ACME_LOGISTICS)
    proposal = load_action_proposal(
        runtime_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        proposal_id=item.proposal.proposal_id,
        now=CLOCK,
    )
    outcome = gate.record_verdict(
        proposal,
        Verdict("approve", human_principal_id=authority, rationale="test approval"),
        cause_ref="test:approve",
    )
    return gate, proposal, outcome


def test_live_committer_creates_exactly_one_task_and_ledgers_it(runtime_conn, tmp_path):
    runtime_conn.execute("BEGIN")
    try:
        gate, proposal, outcome = _bridge_ctx(runtime_conn, tmp_path)
        client = _FakeTaskClient()
        ledger_dir = tmp_path / "writeback-ledger"
        committer = LiveSalesforceActivityCommitter(
            gate, env=_ENV, ledger_dir=ledger_dir, client=client,
        )

        receipt = committer.commit(proposal, outcome)

        assert receipt.committed is True
        assert len(client.requests) == 1
        req = client.requests[0]
        assert req.method == "POST"
        assert req.url.endswith("/sobjects/Task")
        body = json.loads(req.body)
        assert body["Subject"].startswith("UCSM-P5A ")
        assert body["WhatId"] == ACME_LOGISTICS

        ledger_path = ledger_dir / "writeback_ledger.jsonl"
        assert ledger_path.exists()
        lines = [json.loads(line) for line in ledger_path.read_text().splitlines()]
        # Two-phase ledger: an intent row written before the POST, then a
        # confirmed row after success -- closes the crash window where a
        # process kill between the network call and the ledger append
        # could leave a real Salesforce Task with no local record.
        assert len(lines) == 2
        assert lines[0]["ledger_phase"] == "intent"
        assert lines[0]["sf_task_id"] is None
        assert lines[0]["receipt"]["committed"] is False
        assert lines[1]["ledger_phase"] == "confirmed"
        assert lines[1]["sf_task_id"] == "00TfakeTaskId000001"
        assert lines[1]["receipt"]["committed"] is True
    finally:
        runtime_conn.rollback()


def test_live_committer_is_idempotent_second_call_makes_no_request(runtime_conn, tmp_path):
    runtime_conn.execute("BEGIN")
    try:
        gate, proposal, outcome = _bridge_ctx(runtime_conn, tmp_path)
        client = _FakeTaskClient()
        ledger_dir = tmp_path / "writeback-ledger"
        committer = LiveSalesforceActivityCommitter(
            gate, env=_ENV, ledger_dir=ledger_dir, client=client,
        )

        first = committer.commit(proposal, outcome)
        second = committer.commit(proposal, outcome)

        assert first.committed is True
        assert second.committed is False
        # No second Task-create request was ever sent -- idempotency is
        # enforced before the network call, not after.
        assert len(client.requests) == 1
    finally:
        runtime_conn.rollback()


def test_live_committer_dry_run_makes_no_request(runtime_conn, tmp_path):
    runtime_conn.execute("BEGIN")
    try:
        gate, proposal, outcome = _bridge_ctx(runtime_conn, tmp_path)
        client = _FakeTaskClient()
        ledger_dir = tmp_path / "writeback-ledger"
        committer = LiveSalesforceActivityCommitter(
            gate, env=_ENV, ledger_dir=ledger_dir, client=client,
        )

        receipt = committer.commit(proposal, outcome, dry_run=True)

        assert receipt.dry_run is True
        assert len(client.requests) == 0
    finally:
        runtime_conn.rollback()


def test_live_committer_rejects_action_outside_writeback_allowlist(runtime_conn, tmp_path):
    from dataclasses import replace

    runtime_conn.execute("BEGIN")
    try:
        gate, proposal, outcome = _bridge_ctx(runtime_conn, tmp_path)
        bad_proposal = replace(proposal, action="some_other_action")
        client = _FakeTaskClient()
        committer = LiveSalesforceActivityCommitter(
            gate, env=_ENV, ledger_dir=tmp_path, client=client,
        )
        with pytest.raises(Exception):
            committer.commit(bad_proposal, outcome)
        assert len(client.requests) == 0
    finally:
        runtime_conn.rollback()


def test_live_committer_raises_on_non_2xx_status(runtime_conn, tmp_path):
    runtime_conn.execute("BEGIN")
    try:
        gate, proposal, outcome = _bridge_ctx(runtime_conn, tmp_path)
        client = _FakeTaskClient(status=400)
        committer = LiveSalesforceActivityCommitter(
            gate, env=_ENV, ledger_dir=tmp_path, client=client,
        )
        with pytest.raises(SalesforceWriteError):
            committer.commit(proposal, outcome)
    finally:
        runtime_conn.rollback()


class _LedgerCheckingClient:
    """Wraps a real client but asserts, at the moment the POST would fire,
    that an intent ledger row for this key already exists on disk --
    proving order-of-operations (ledger-write-before-POST), not just that
    a ledger row exists somewhere after the call returns."""

    def __init__(self, inner, *, ledger_path, idempotency_key):
        self._inner = inner
        self._ledger_path = ledger_path
        self._idempotency_key = idempotency_key
        self.checked_intent_present_before_post = False

    def send(self, req: HttpRequest) -> HttpResponse:
        assert self._ledger_path.exists(), "intent row must be on disk before the POST fires"
        lines = [json.loads(line) for line in self._ledger_path.read_text().splitlines()]
        matching = [
            line for line in lines
            if line["receipt"]["idempotency_key"] == self._idempotency_key
        ]
        assert len(matching) == 1, "exactly one intent row should exist before the POST"
        assert matching[0]["ledger_phase"] == "intent"
        assert matching[0]["receipt"]["committed"] is False
        self.checked_intent_present_before_post = True
        return self._inner.send(req)


def test_live_committer_writes_intent_ledger_row_before_the_post_fires(runtime_conn, tmp_path):
    """Order-of-operations proof: the intent record must be written and
    queryable BEFORE the network POST call, not only after success."""
    runtime_conn.execute("BEGIN")
    try:
        gate, proposal, outcome = _bridge_ctx(runtime_conn, tmp_path)
        ledger_dir = tmp_path / "writeback-ledger"
        ledger_path = ledger_dir / "writeback_ledger.jsonl"
        key = committer_module._idempotency_key(proposal, outcome)
        inner_client = _FakeTaskClient()
        checking_client = _LedgerCheckingClient(
            inner_client, ledger_path=ledger_path, idempotency_key=key,
        )
        committer = LiveSalesforceActivityCommitter(
            gate, env=_ENV, ledger_dir=ledger_dir, client=checking_client,
        )

        receipt = committer.commit(proposal, outcome)

        assert checking_client.checked_intent_present_before_post is True
        assert receipt.committed is True
        lines = [json.loads(line) for line in ledger_path.read_text().splitlines()]
        assert len(lines) == 2
        assert lines[0]["ledger_phase"] == "intent"
        assert lines[1]["ledger_phase"] == "confirmed"
    finally:
        runtime_conn.rollback()


def test_live_committer_ledgers_a_failed_phase_row_when_the_post_errors(runtime_conn, tmp_path):
    """A non-2xx response must still leave an intent row (and a failed
    row) on disk -- the crash window this fix closes covers a real error
    response, not only a process kill."""
    runtime_conn.execute("BEGIN")
    try:
        gate, proposal, outcome = _bridge_ctx(runtime_conn, tmp_path)
        ledger_dir = tmp_path / "writeback-ledger"
        client = _FakeTaskClient(status=400)
        committer = LiveSalesforceActivityCommitter(
            gate, env=_ENV, ledger_dir=ledger_dir, client=client,
        )

        with pytest.raises(SalesforceWriteError):
            committer.commit(proposal, outcome)

        ledger_path = ledger_dir / "writeback_ledger.jsonl"
        assert ledger_path.exists(), "an intent row must survive even a failed POST"
        lines = [json.loads(line) for line in ledger_path.read_text().splitlines()]
        assert len(lines) == 2
        assert lines[0]["ledger_phase"] == "intent"
        assert lines[1]["ledger_phase"] == "failed"
        assert lines[1]["receipt"]["committed"] is False
        assert lines[1]["sf_task_id"] is None
    finally:
        runtime_conn.rollback()


def test_live_committer_retries_after_a_failed_post_and_succeeds(runtime_conn, tmp_path):
    """A failed send must not be mistaken for committed -- a retry after a
    failure should still be free to attempt the real POST."""
    runtime_conn.execute("BEGIN")
    try:
        gate, proposal, outcome = _bridge_ctx(runtime_conn, tmp_path)
        ledger_dir = tmp_path / "writeback-ledger"
        failing_client = _FakeTaskClient(status=400)
        committer = LiveSalesforceActivityCommitter(
            gate, env=_ENV, ledger_dir=ledger_dir, client=failing_client,
        )
        with pytest.raises(SalesforceWriteError):
            committer.commit(proposal, outcome)

        succeeding_client = _FakeTaskClient()
        committer_retry = LiveSalesforceActivityCommitter(
            gate, env=_ENV, ledger_dir=ledger_dir, client=succeeding_client,
        )
        receipt = committer_retry.commit(proposal, outcome)

        assert receipt.committed is True
        assert len(succeeding_client.requests) == 1
    finally:
        runtime_conn.rollback()
