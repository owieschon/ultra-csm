"""CSM ActionGate state-machine tests."""

from __future__ import annotations

import json

import psycopg
import pytest

from ultra_csm.governance import (
    ActionGate,
    FixtureVerdictSource,
    GateError,
    Verdict,
    canonical_payload_sha256,
    PERM_ORDER_CONFIRM,
)
from ultra_csm.platform.db import session

from tests._govhelpers import (  # noqa: F401 - gov_conn is a pytest fixture used by injection
    CLOCK,
    T1,
    T1_AGENT,
    det,
    gov_conn,
    make_human_principal,
    setup_roster,
)


def _gate(conn, *, actor, source):
    return ActionGate(conn, tenant_id=T1, actor_principal_id=actor,
                      verdict_source=source, now=CLOCK)


def _seed_account_contact(conn, *, consent: bool):
    account_id = det("account", "outreach-consent", str(consent))
    contact_id = det("contact", "outreach-consent", str(consent))
    with session(conn, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK) as cur:
        cur.execute(
            "INSERT INTO account (account_id, tenant_id, name) "
            "VALUES (%s, %s, %s) ON CONFLICT (account_id) DO NOTHING",
            (account_id, T1, f"Consent test {consent}"),
        )
        cur.execute(
            "INSERT INTO contact (contact_id, tenant_id, account_id, email, name, consent) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (contact_id) DO UPDATE SET consent = EXCLUDED.consent",
            (
                contact_id,
                T1,
                account_id,
                f"consent-{consent}@example.com",
                "Consent Test",
                consent,
            ),
        )
    return account_id, contact_id


# ---------------------------------------------------------------------------
# State machine: approve / deny / revise
# ---------------------------------------------------------------------------
def test_gate_approve_authorizes(gov_conn):
    orch, _authority = setup_roster(gov_conn)
    human = make_human_principal(gov_conn)
    src = FixtureVerdictSource(default=Verdict("approve", human_principal_id=human))
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
    orch, _authority = setup_roster(gov_conn)
    human = make_human_principal(gov_conn)
    revised = {"to": "buyer@acme-diesel.example", "body": "corrected"}
    src = FixtureVerdictSource(default=Verdict(
        "revise", human_principal_id=human, revised_payload=revised))
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
    orch, _authority = setup_roster(gov_conn)
    human = make_human_principal(gov_conn)
    src = FixtureVerdictSource(default=Verdict("approve", human_principal_id=human))
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


def test_db_rejects_action_proposal_payload_hash_mismatch(gov_conn):
    """The database recomputes the canonical payload hash, so direct SQL cannot
    insert a proposal whose stored payload and anti-TOCTOU hash disagree."""
    orch, _authority = setup_roster(gov_conn)
    payload = {"body": "draft", "to": "buyer@example.com"}
    with pytest.raises(psycopg.errors.CheckViolation, match="payload hash mismatch"):
        with session(gov_conn, tenant_id=T1, actor_id=orch, now=CLOCK) as cur:
            cur.execute(
                "INSERT INTO action_proposal (tenant_id, actor_principal_id, intent, "
                "action, payload, payload_sha256, autonomy_tier, required_permission) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    T1,
                    orch,
                    "send_email",
                    "email.send",
                    json.dumps(payload),
                    "not-the-canonical-hash",
                    2,
                    "email.send",
                ),
            )


def test_db_rejects_approved_outreach_without_contact_consent(gov_conn):
    """REST/MCP have app-level consent checks; the DB is the backstop for any
    lower-level caller that tries to approve customer outreach directly."""
    account_id, contact_id = _seed_account_contact(gov_conn, consent=False)
    orch, _authority = setup_roster(gov_conn)
    human = make_human_principal(gov_conn)
    src = FixtureVerdictSource(default=Verdict("approve", human_principal_id=human))
    gate = _gate(gov_conn, actor=orch, source=src)

    prop = gate.propose(intent="customer_outreach", action="draft_customer_outreach",
                        payload={
                            "account_id": account_id,
                            "contact_id": contact_id,
                            "body": "Draft that must not send.",
                        },
                        autonomy_tier=2,
                        required_permission="customer.outreach.draft")
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match="outreach consent"):
        gate.record_verdict(prop)


def test_db_allows_approved_outreach_with_contact_consent(gov_conn):
    account_id, contact_id = _seed_account_contact(gov_conn, consent=True)
    orch, _authority = setup_roster(gov_conn)
    human = make_human_principal(gov_conn)
    src = FixtureVerdictSource(default=Verdict("approve", human_principal_id=human))
    gate = _gate(gov_conn, actor=orch, source=src)

    prop = gate.propose(intent="customer_outreach", action="draft_customer_outreach",
                        payload={
                            "account_id": account_id,
                            "contact_id": contact_id,
                            "body": "Consented draft.",
                        },
                        autonomy_tier=2,
                        required_permission="customer.outreach.draft")
    out = gate.record_verdict(prop)
    assert out.authorized is True


def test_verdict_unique_per_proposal(gov_conn):
    """UNIQUE(proposal_id): a second verdict on the same proposal is rejected by
    the DB — the gate is idempotent under retry / double-post."""
    orch, _authority = setup_roster(gov_conn)
    human = make_human_principal(gov_conn)
    src = FixtureVerdictSource(default=Verdict("approve", human_principal_id=human))
    gate = _gate(gov_conn, actor=orch, source=src)
    prop = gate.propose(intent="send_email", action="email.send",
                        payload={"to": "x"}, autonomy_tier=2,
                        required_permission="email.send")
    gate.record_verdict(prop)
    with pytest.raises(psycopg.errors.UniqueViolation):
        gate.record_verdict(prop)


def test_csm_orchestrator_verdict_cannot_mint_order_confirm_authority(gov_conn):
    """SoD via the PERMISSION layer: even a properly human, non-self approver
    who merely holds the cs-orchestrator role (not order-confirm-authority)
    cannot mint order.confirm authority. Distinct from the gate/DB human-ness
    check below -- this is Authorizer.can_confirm_order, a permission lookup,
    not a kind/self-approval check."""
    orch, _authority = setup_roster(gov_conn)
    human = make_human_principal(gov_conn)
    assert PERM_ORDER_CONFIRM == "order.confirm"
    src = FixtureVerdictSource(by_intent={
        "log_crm_activity": Verdict("approve", human_principal_id=human)})
    gate = _gate(gov_conn, actor=orch, source=src)
    prop = gate.propose(intent="log_crm_activity", action="log_crm_activity",
                        payload={"account_id": "acct", "body": "draft"}, autonomy_tier=2,
                        required_permission="crm.activity.write")
    out = gate.record_verdict(prop)
    assert out.authorized is True
    assert gate.confirm_authority_ok(out) is False


# ---------------------------------------------------------------------------
# Gate/DB human-ness check (Stream 23): for tier>=2 intents, an
# authorizing ('approve'/'revise') verdict's human_principal_id must be
# kind='human' and must differ from the proposal's own actor. This is a
# SECOND, independent layer under the token seam's `_ensure_human_principal`
# (`_api_helpers.py`, untouched) -- that seam already forces kind='human' for
# every real API/MCP request; this closes the gap for any caller that
# constructs a Verdict directly against the gate/DB layer itself.
# ---------------------------------------------------------------------------
def test_agent_kind_self_approve_rejected_for_tier_two(gov_conn):
    """The demonstrated gap: an agent-kind principal approving its OWN
    tier>=2 proposal must now be rejected at the gate/DB layer, not just
    return authorized=True (pre-fix, this was exactly the assertion at the
    top of this file's predecessor test)."""
    orch, _authority = setup_roster(gov_conn)
    src = FixtureVerdictSource(default=Verdict("approve", human_principal_id=orch))
    gate = _gate(gov_conn, actor=orch, source=src)
    prop = gate.propose(intent="send_email", action="email.send",
                        payload={"to": "buyer@acme-diesel.example", "body": "hi"},
                        autonomy_tier=2, required_permission="email.send")
    with pytest.raises(GateError, match="human"):
        gate.record_verdict(prop)


def test_agent_kind_distinct_approver_still_rejected_for_tier_two(gov_conn):
    """Differing from the actor is not sufficient on its own: an agent-kind
    `authority` (distinct from `orch`) approving a tier>=2 proposal is still
    rejected -- the check is kind='human' AND distinct-from-actor, not either
    alone."""
    orch, authority = setup_roster(gov_conn)
    src = FixtureVerdictSource(default=Verdict("approve", human_principal_id=authority))
    gate = _gate(gov_conn, actor=orch, source=src)
    prop = gate.propose(intent="send_email", action="email.send",
                        payload={"to": "buyer@acme-diesel.example", "body": "hi"},
                        autonomy_tier=2, required_permission="email.send")
    with pytest.raises(GateError, match="human"):
        gate.record_verdict(prop)


def test_human_kind_self_id_impossible_but_distinct_approver_authorizes_tier_two(gov_conn):
    """The legitimate path: a genuine kind='human' principal, distinct from
    the proposing actor, approving a tier>=2 proposal succeeds -- the check
    does not overreach into rejecting valid human approvals."""
    orch, _authority = setup_roster(gov_conn)
    human = make_human_principal(gov_conn)
    src = FixtureVerdictSource(default=Verdict("approve", human_principal_id=human))
    gate = _gate(gov_conn, actor=orch, source=src)
    prop = gate.propose(intent="send_email", action="email.send",
                        payload={"to": "buyer@acme-diesel.example", "body": "hi"},
                        autonomy_tier=2, required_permission="email.send")
    out = gate.record_verdict(prop)
    assert out.authorized is True


def test_gate_revise_also_enforces_human_ness_for_tier_two(gov_conn):
    """gate.py's own 'revise' path (auto-approve+mutate, status='approved')
    is an authorizing verdict too -- the human-ness check applies to it
    exactly like 'approve', not just to the literal string 'approve'."""
    orch, _authority = setup_roster(gov_conn)
    revised = {"to": "buyer@acme-diesel.example", "body": "corrected"}
    src = FixtureVerdictSource(default=Verdict(
        "revise", human_principal_id=orch, revised_payload=revised))
    gate = _gate(gov_conn, actor=orch, source=src)
    prop = gate.propose(intent="send_email", action="email.send",
                        payload={"to": "buyer@acme-diesel.example", "body": "draft"},
                        autonomy_tier=2, required_permission="email.send")
    with pytest.raises(GateError, match="human"):
        gate.record_verdict(prop)


def test_gate_deny_is_never_subject_to_human_ness_check(gov_conn):
    """A 'deny' verdict authorizes nothing -- there is no approving principal
    to check, so an agent-kind self-denial on a tier>=2 proposal is untouched
    by this dispatch (matches eval/week1_protocol.py's real deny-verdict
    usage, which relies on this)."""
    orch, _authority = setup_roster(gov_conn)
    src = FixtureVerdictSource(default=Verdict("deny", human_principal_id=orch))
    gate = _gate(gov_conn, actor=orch, source=src)
    prop = gate.propose(intent="send_email", action="email.send",
                        payload={"to": "x", "body": "y"},
                        autonomy_tier=2, required_permission="email.send")
    out = gate.record_verdict(prop)
    assert out.authorized is False
    assert out.status == "denied"
