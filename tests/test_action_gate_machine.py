"""CSM ActionGate state-machine tests."""

from __future__ import annotations

import pytest

from ultra_csm.governance import (
    ActionGate,
    FixtureVerdictSource,
    GateError,
    Verdict,
    canonical_payload_sha256,
    PERM_ORDER_CONFIRM,
)

from tests._govhelpers import (
    CLOCK,
    gov_conn,
    T1,
    setup_roster,
)


def _gate(conn, *, actor, source):
    return ActionGate(conn, tenant_id=T1, actor_principal_id=actor,
                      verdict_source=source, now=CLOCK)


# ---------------------------------------------------------------------------
# State machine: approve / deny / revise
# ---------------------------------------------------------------------------
def test_gate_approve_authorizes(gov_conn):
    orch, authority = setup_roster(gov_conn)
    src = FixtureVerdictSource(default=Verdict("approve", human_principal_id=authority))
    gate = _gate(gov_conn, actor=orch, source=src)

    prop = gate.propose(intent="send_email", action="email.send",
                        payload={"to": "buyer@acme-diesel.example", "body": "hi"},
                        autonomy_tier=2, required_permission="email.send")
    out = gate.record_verdict(prop)
    assert out.authorized is True
    assert out.status == "approved"
    assert out.verdict == "approve"
    # The committer's bind check passes for the authorized payload.
    gate.assert_payload_bound(out, prop.payload)


def test_gate_deny_blocks(gov_conn):
    orch, authority = setup_roster(gov_conn)
    src = FixtureVerdictSource(default=Verdict("deny", human_principal_id=authority))
    gate = _gate(gov_conn, actor=orch, source=src)

    prop = gate.propose(intent="send_email", action="email.send",
                        payload={"to": "x", "body": "y"},
                        autonomy_tier=2, required_permission="email.send")
    out = gate.record_verdict(prop)
    assert out.authorized is False
    assert out.status == "denied"
    # The committer refuses to execute a denied action.
    with pytest.raises(GateError):
        gate.assert_payload_bound(out, prop.payload)


def test_gate_revise_applies_revised_payload(gov_conn):
    """A revise verdict supersedes the original payload: the committer is bound to
    the HUMAN's edited body, and the original hash no longer authorizes."""
    orch, authority = setup_roster(gov_conn)
    revised = {"to": "buyer@acme-diesel.example", "body": "corrected"}
    src = FixtureVerdictSource(default=Verdict(
        "revise", human_principal_id=authority, revised_payload=revised))
    gate = _gate(gov_conn, actor=orch, source=src)

    prop = gate.propose(intent="send_email", action="email.send",
                        payload={"to": "buyer@acme-diesel.example", "body": "draft"},
                        autonomy_tier=2, required_permission="email.send")
    original_sha = prop.payload_sha256
    out = gate.record_verdict(prop)

    assert out.authorized is True and out.verdict == "revise"
    assert out.payload == revised
    assert out.payload_sha256 == canonical_payload_sha256(revised)
    assert out.payload_sha256 != original_sha
    # Bound to the revised payload; the ORIGINAL payload now fails the bind check.
    gate.assert_payload_bound(out, revised)
    with pytest.raises(GateError):
        gate.assert_payload_bound(out, prop.payload)

    # The proposal row itself was atomically updated to the revised payload+hash.
    from ultra_csm.platform.db import session
    with session(gov_conn, tenant_id=T1, actor_id=orch, now=CLOCK) as cur:
        cur.execute("SELECT payload_sha256, status FROM action_proposal "
                    "WHERE proposal_id = %s", (prop.proposal_id,))
        sha, status = cur.fetchone()
    assert sha == out.payload_sha256 and status == "approved"


# ---------------------------------------------------------------------------
# Anti-TOCTOU: payload_sha256 binds (a tampered payload post-approval is refused)
# ---------------------------------------------------------------------------
def test_gate_tampered_payload_refused(gov_conn):
    orch, authority = setup_roster(gov_conn)
    src = FixtureVerdictSource(default=Verdict("approve", human_principal_id=authority))
    gate = _gate(gov_conn, actor=orch, source=src)

    prop = gate.propose(intent="send_email", action="email.send",
                        payload={"to": "buyer", "amount_cents": 100},
                        autonomy_tier=2, required_permission="email.send")
    out = gate.record_verdict(prop)
    assert out.authorized

    # Someone tampers the action body after approval — the bind check fail-closes.
    tampered = {"to": "buyer", "amount_cents": 999999}
    with pytest.raises(GateError):
        gate.assert_payload_bound(out, tampered)


def test_verdict_unique_per_proposal(gov_conn):
    """UNIQUE(proposal_id): a second verdict on the same proposal is rejected by
    the DB — the gate is idempotent under retry / double-post."""
    import psycopg
    orch, authority = setup_roster(gov_conn)
    src = FixtureVerdictSource(default=Verdict("approve", human_principal_id=authority))
    gate = _gate(gov_conn, actor=orch, source=src)
    prop = gate.propose(intent="send_email", action="email.send",
                        payload={"to": "x"}, autonomy_tier=2,
                        required_permission="email.send")
    gate.record_verdict(prop)
    with pytest.raises(psycopg.errors.UniqueViolation):
        gate.record_verdict(prop)


def test_csm_orchestrator_verdict_cannot_mint_order_confirm_authority(gov_conn):
    orch, _authority = setup_roster(gov_conn)
    assert PERM_ORDER_CONFIRM == "order.confirm"
    src = FixtureVerdictSource(by_intent={
        "customer_outreach": Verdict("approve", human_principal_id=orch)})
    gate = _gate(gov_conn, actor=orch, source=src)
    prop = gate.propose(intent="customer_outreach", action="draft_customer_outreach",
                        payload={"account_id": "acct", "body": "draft"}, autonomy_tier=2,
                        required_permission="customer.outreach.draft")
    out = gate.record_verdict(prop)
    assert out.authorized is True
    assert gate.confirm_authority_ok(out) is False
