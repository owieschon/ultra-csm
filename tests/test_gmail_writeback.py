"""Lane D: live Gmail write-back committer -- create-only send, ledgered,
idempotent, allowlist-fail-closed, byte-equal body check. Exercised here
against a fake HTTP transport (no live network, no real OAuth token
exchange); the live run against the real burner account is a separate,
env-gated, manually-invoked path documented in docs/PROGRAM_REPORT_26.md.
"""

from __future__ import annotations

import base64
import json
from dataclasses import replace

import pytest

from ultra_csm.agent1 import run_time_to_value_sweep
from ultra_csm.committers import CommitError, load_action_proposal
from ultra_csm.data_plane import DEFAULT_TENANT, SimTenantStore
from ultra_csm.data_plane.gmail_writeback import (
    GmailWriteError,
    LiveGmailOutboundCommitter,
    RecipientNotAllowedError,
    ledger_send_count,
)
from ultra_csm.data_plane.live_smoke import HttpRequest, HttpResponse
from ultra_csm.governance import ActionGate, FixtureVerdictSource, GateError, Verdict

from tests._govhelpers import CLOCK, T1, make_human_principal, setup_roster

AS_OF = "2026-06-27"
_ENV = {
    "ULTRA_CSM_GMAIL_OAUTH_CLIENT_ID": "fake-client-id",
    "ULTRA_CSM_GMAIL_OAUTH_CLIENT_SECRET": "fake-client-secret",
    "ULTRA_CSM_GMAIL_OAUTH_REFRESH_TOKEN": "fake-refresh-token",
}
_SENDER = "agenticardvarkpug@gmail.com"
_ALLOWED_RECIPIENT = "agenticardvarkpug@gmail.com"
_DISALLOWED_RECIPIENT = "someone-else@example.com"


class _FakeGmailClient:
    """Records every request; a token exchange followed by exactly one
    messages.send POST per non-idempotent, non-dry-run commit."""

    def __init__(self, *, send_status: int = 200, message_id: str = "18abcFakeMsgId0001"):
        self.requests: list[HttpRequest] = []
        self._send_status = send_status
        self._message_id = message_id

    def send(self, req: HttpRequest) -> HttpResponse:
        self.requests.append(req)
        if req.url.endswith("/token"):
            return HttpResponse(
                status=200,
                body=json.dumps({"access_token": "fake-access-token", "expires_in": 3599}).encode("utf-8"),
                headers={"content-type": "application/json"},
            )
        assert req.method == "POST", "gmail write-back must never issue a non-POST verb"
        assert req.url.endswith("/messages/send")
        return HttpResponse(
            status=self._send_status,
            body=json.dumps({"id": self._message_id}).encode("utf-8"),
            headers={"content-type": "application/json"},
        )

    @property
    def send_requests(self) -> list[HttpRequest]:
        return [r for r in self.requests if r.url.endswith("/messages/send")]


def _bridge_ctx(runtime_conn, tmp_path):
    """Build a real, DB-backed, APPROVED draft_customer_outreach proposal
    the same way the demo loop does -- gate state, not an invented queue."""
    orch, _authority = setup_roster(runtime_conn)
    human = make_human_principal(runtime_conn)
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
    item = next(
        i for i in sweep.work_items
        if i.proposal is not None and i.proposal.action_type == "draft_customer_outreach"
    )
    proposal = load_action_proposal(
        runtime_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        proposal_id=item.proposal.proposal_id,
        now=CLOCK,
    )
    outcome = gate.record_verdict(
        proposal,
        Verdict("approve", human_principal_id=human, rationale="test approval with consent"),
        cause_ref="test:approve",
    )
    return gate, proposal, outcome


def test_live_committer_sends_exactly_one_message_and_ledgers_it(runtime_conn, tmp_path):
    runtime_conn.execute("BEGIN")
    try:
        gate, proposal, outcome = _bridge_ctx(runtime_conn, tmp_path)
        client = _FakeGmailClient()
        ledger_dir = tmp_path / "gmail-ledger"
        committer = LiveGmailOutboundCommitter(
            gate, env=_ENV, ledger_dir=ledger_dir, sender=_SENDER, client=client,
        )

        receipt = committer.commit(proposal, outcome, recipient=_ALLOWED_RECIPIENT)

        assert receipt.committed is True
        assert len(client.send_requests) == 1
        req = client.send_requests[0]
        raw = base64.urlsafe_b64decode(json.loads(req.body)["raw"]).decode("utf-8")
        assert "UCSM-NARR2" in raw
        assert f"To: {_ALLOWED_RECIPIENT}" in raw
        assert str(proposal.payload.get("body") or "") in raw

        ledger_path = ledger_dir / "gmail_writeback_ledger.jsonl"
        assert ledger_path.exists()
        lines = [json.loads(line) for line in ledger_path.read_text().splitlines()]
        assert len(lines) == 1
        assert lines[0]["message_id"] == "18abcFakeMsgId0001"
        assert lines[0]["receipt"]["committed"] is True
        assert ledger_send_count(ledger_path) == 1
    finally:
        runtime_conn.rollback()


def test_live_committer_is_idempotent_second_call_sends_nothing(runtime_conn, tmp_path):
    runtime_conn.execute("BEGIN")
    try:
        gate, proposal, outcome = _bridge_ctx(runtime_conn, tmp_path)
        client = _FakeGmailClient()
        ledger_dir = tmp_path / "gmail-ledger"
        committer = LiveGmailOutboundCommitter(
            gate, env=_ENV, ledger_dir=ledger_dir, sender=_SENDER, client=client,
        )

        first = committer.commit(proposal, outcome, recipient=_ALLOWED_RECIPIENT)
        second = committer.commit(proposal, outcome, recipient=_ALLOWED_RECIPIENT)

        assert first.committed is True
        assert second.committed is False
        # No second messages.send request was ever sent -- idempotency is
        # enforced before the network call, not after.
        assert len(client.send_requests) == 1
        assert ledger_send_count(ledger_dir / "gmail_writeback_ledger.jsonl") == 1
    finally:
        runtime_conn.rollback()


def test_live_committer_dry_run_sends_nothing(runtime_conn, tmp_path):
    runtime_conn.execute("BEGIN")
    try:
        gate, proposal, outcome = _bridge_ctx(runtime_conn, tmp_path)
        client = _FakeGmailClient()
        ledger_dir = tmp_path / "gmail-ledger"
        committer = LiveGmailOutboundCommitter(
            gate, env=_ENV, ledger_dir=ledger_dir, sender=_SENDER, client=client,
        )

        receipt = committer.commit(proposal, outcome, recipient=_ALLOWED_RECIPIENT, dry_run=True)

        assert receipt.dry_run is True
        assert len(client.send_requests) == 0
        assert ledger_send_count(ledger_dir / "gmail_writeback_ledger.jsonl") == 0
    finally:
        runtime_conn.rollback()


def test_live_committer_refuses_recipient_outside_allowlist(runtime_conn, tmp_path):
    """Recipient allowlist is checked fail-closed at send time, even though
    the gate approved this exact payload -- the gate's authorization never
    widens the transport's authority over WHO it may address."""
    runtime_conn.execute("BEGIN")
    try:
        gate, proposal, outcome = _bridge_ctx(runtime_conn, tmp_path)
        client = _FakeGmailClient()
        ledger_dir = tmp_path / "gmail-ledger"
        committer = LiveGmailOutboundCommitter(
            gate, env=_ENV, ledger_dir=ledger_dir, sender=_SENDER, client=client,
        )

        with pytest.raises(RecipientNotAllowedError):
            committer.commit(proposal, outcome, recipient=_DISALLOWED_RECIPIENT)

        # Refused BEFORE any network call -- not even a token exchange.
        assert len(client.requests) == 0
        assert ledger_send_count(ledger_dir / "gmail_writeback_ledger.jsonl") == 0
        ledger_path = ledger_dir / "gmail_writeback_ledger.jsonl"
        lines = [json.loads(line) for line in ledger_path.read_text().splitlines()]
        assert lines[0]["refusal_reason"] == "RECIPIENT_NOT_ALLOWLISTED"
        assert lines[0]["receipt"]["committed"] is False
    finally:
        runtime_conn.rollback()


def test_live_committer_refuses_unapproved_proposal(runtime_conn, tmp_path):
    runtime_conn.execute("BEGIN")
    try:
        orch, authority = setup_roster(runtime_conn)
        gate = ActionGate(
            runtime_conn, tenant_id=T1, actor_principal_id=orch,
            verdict_source=FixtureVerdictSource(), now=CLOCK,
        )
        store = SimTenantStore.seed(tmp_path, tenant_id=DEFAULT_TENANT, reset=True)
        sweep = run_time_to_value_sweep(
            store.data_plane(), DEFAULT_TENANT, gate, sweep_principal_id=orch, as_of=AS_OF,
        )
        item = next(
            i for i in sweep.work_items
            if i.proposal is not None and i.proposal.action_type == "draft_customer_outreach"
        )
        proposal = load_action_proposal(
            runtime_conn, tenant_id=T1, actor_principal_id=orch,
            proposal_id=item.proposal.proposal_id, now=CLOCK,
        )
        # Deny instead of approve -- outcome.authorized is False.
        denied_outcome = gate.record_verdict(
            proposal,
            Verdict("deny", human_principal_id=authority, rationale="test denial"),
            cause_ref="test:deny",
        )
        client = _FakeGmailClient()
        committer = LiveGmailOutboundCommitter(
            gate, env=_ENV, ledger_dir=tmp_path, sender=_SENDER, client=client,
        )
        with pytest.raises(GateError):
            committer.commit(proposal, denied_outcome, recipient=_ALLOWED_RECIPIENT)
        assert len(client.requests) == 0
    finally:
        runtime_conn.rollback()


def test_live_committer_refuses_mutated_body(runtime_conn, tmp_path):
    """Byte-equal check: the body about to be sent must match the approved
    payload exactly -- a payload mutated after approval is refused."""
    runtime_conn.execute("BEGIN")
    try:
        gate, proposal, outcome = _bridge_ctx(runtime_conn, tmp_path)
        mutated = replace(proposal, payload={**proposal.payload, "body": "a different body entirely"})
        client = _FakeGmailClient()
        committer = LiveGmailOutboundCommitter(
            gate, env=_ENV, ledger_dir=tmp_path, sender=_SENDER, client=client,
        )
        # assert_payload_bound itself raises first (hash no longer matches
        # outcome.payload_sha256) -- this is the anti-TOCTOU path.
        with pytest.raises(GateError):
            committer.commit(mutated, outcome, recipient=_ALLOWED_RECIPIENT)
        assert len(client.requests) == 0
    finally:
        runtime_conn.rollback()


def test_live_committer_rejects_action_outside_writeback_scope(runtime_conn, tmp_path):
    runtime_conn.execute("BEGIN")
    try:
        gate, proposal, outcome = _bridge_ctx(runtime_conn, tmp_path)
        bad_proposal = replace(proposal, action="some_other_action")
        client = _FakeGmailClient()
        committer = LiveGmailOutboundCommitter(
            gate, env=_ENV, ledger_dir=tmp_path, sender=_SENDER, client=client,
        )
        with pytest.raises(CommitError):
            committer.commit(bad_proposal, outcome, recipient=_ALLOWED_RECIPIENT)
        assert len(client.requests) == 0
    finally:
        runtime_conn.rollback()


def test_live_committer_raises_on_non_2xx_status(runtime_conn, tmp_path):
    runtime_conn.execute("BEGIN")
    try:
        gate, proposal, outcome = _bridge_ctx(runtime_conn, tmp_path)
        client = _FakeGmailClient(send_status=400)
        committer = LiveGmailOutboundCommitter(
            gate, env=_ENV, ledger_dir=tmp_path, sender=_SENDER, client=client,
        )
        with pytest.raises(GmailWriteError):
            committer.commit(proposal, outcome, recipient=_ALLOWED_RECIPIENT)
    finally:
        runtime_conn.rollback()
