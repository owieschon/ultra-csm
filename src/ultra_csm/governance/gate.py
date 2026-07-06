"""The universal approve/deny/revise action gate (ARCHITECTURE §10b; design
Part 1.2). Every real-world-affecting action (write / commit / outbound) emits an
`action_proposal`; a human verdict (`action_verdict`) is what releases it. The
LLM never mints authority — the verdict is data, the authorization is code-minted.

State machine on `action_proposal.status`: `pending → {approved | denied}`. A
`revise` verdict transitions to `approved` while atomically updating the
proposal's payload + payload_sha256 to the human's edit (so the *revised* action
is the one authorized). `deny` → `denied` (the committer must NOT proceed → the
caller escalates). The committer recomputes the payload hash and requires
equality (anti-TOCTOU): a payload tampered after approval is refused.

Determinism: the "human" is an injectable `VerdictSource`. `FixtureVerdictSource`
returns a pre-supplied verdict for the offline scored path (no network, no key);
the live console is a different source over the same tables/state machine.

Authority composition (additive): when a gated action's `intent == 'confirm_order'`,
an APPROVED verdict cast by a principal that holds `order.confirm` authority is what a
caller turns into a code-minted authorization. The LLM-driven proposal never carries that
authority itself — the separation-of-duties gate enforces that the agent principal cannot
mint order-confirm authority through a proposal.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from ultra_csm.governance.authorizer import Authorizer, canonical_payload_sha256
from ultra_csm.platform.db import session

CONFIRM_ORDER_INTENT = "confirm_order"


class GateError(Exception):
    """A gate precondition failed (no verdict, hash mismatch, denied action)."""


@dataclass(frozen=True)
class Verdict:
    """A human verdict to apply to a proposal (the unit a VerdictSource returns)."""

    verdict: str  # 'approve' | 'deny' | 'revise'
    human_principal_id: str
    revised_payload: dict | None = None
    rationale: str | None = None


@dataclass(frozen=True)
class ActionProposal:
    proposal_id: str
    intent: str
    action: str
    payload: dict
    payload_sha256: str
    autonomy_tier: int
    required_permission: str
    status: str


@dataclass(frozen=True)
class GateOutcome:
    """The result of recording a verdict. `authorized` is True iff the committer
    may proceed; `payload` is the effective (possibly revised) action body, and
    `payload_sha256` is what the committer must match before executing."""

    proposal_id: str
    status: str            # 'approved' | 'denied'
    authorized: bool
    payload: dict
    payload_sha256: str
    verdict: str


# ---------------------------------------------------------------------------
# Injectable verdict source (the offline/live seam)
# ---------------------------------------------------------------------------
class VerdictSource:
    """The boundary where a human decision enters the gate. Offline this is a
    fixture; live it is the governance console. One method: given a proposal,
    return the Verdict to record."""

    def verdict_for(self, proposal: ActionProposal) -> Verdict:  # pragma: no cover
        raise NotImplementedError


class FixtureVerdictSource(VerdictSource):
    """Deterministic verdict for the scored eval/tests. Keyed by intent (and
    optionally by an exact (intent, action) pair); falls back to a default. The
    verdict is data → the scored path stays byte-reproducible."""

    def __init__(self, default: Verdict | None = None,
                 by_intent: dict[str, Verdict] | None = None) -> None:
        self._default = default
        self._by_intent = by_intent or {}

    def verdict_for(self, proposal: ActionProposal) -> Verdict:
        v = self._by_intent.get(proposal.intent, self._default)
        if v is None:
            raise GateError(
                f"FixtureVerdictSource has no verdict for intent {proposal.intent!r}"
            )
        return v


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------
class ActionGate:
    """Emits proposals and records verdicts against the live tables, through the
    same `session()` seam so every row is provenanced + RLS-scoped. Wraps one
    psycopg connection scoped to the proposing principal."""

    def __init__(self, conn, *, tenant_id: str, actor_principal_id: str,
                 verdict_source: VerdictSource, now=None) -> None:
        self._conn = conn
        self._tenant_id = tenant_id
        self._actor = actor_principal_id
        self._source = verdict_source
        self._now = now
        self._authz = Authorizer(conn, tenant_id=tenant_id,
                                 actor_id=actor_principal_id, now=now)

    # -- emit ---------------------------------------------------------------
    def propose(self, *, intent: str, action: str, payload: dict,
                autonomy_tier: int, required_permission: str,
                grounding_ref: str | None = None, case_id: str | None = None,
                request_id: str | None = None, turn_id: str | None = None,
                cause_ref: str | None = None) -> ActionProposal:
        """Emit an action_proposal (status='pending'). payload_sha256 is computed
        at emit and binds the action body until a verdict authorizes it."""
        sha = canonical_payload_sha256(payload)
        with session(self._conn, tenant_id=self._tenant_id, actor_id=self._actor,
                     cause_ref=cause_ref, request_id=request_id, turn_id=turn_id,
                     now=self._now) as cur:
            cur.execute(
                "INSERT INTO action_proposal (tenant_id, actor_principal_id, "
                "case_id, intent, action, payload, payload_sha256, grounding_ref, "
                "autonomy_tier, required_permission, request_id, turn_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "RETURNING proposal_id",
                (self._tenant_id, self._actor, case_id, intent, action,
                 json.dumps(payload), sha, grounding_ref, autonomy_tier,
                 required_permission, request_id, turn_id),
            )
            proposal_id = str(cur.fetchone()[0])
        return ActionProposal(
            proposal_id=proposal_id, intent=intent, action=action,
            payload=payload, payload_sha256=sha, autonomy_tier=autonomy_tier,
            required_permission=required_permission, status="pending",
        )

    # -- record a verdict ---------------------------------------------------
    def record_verdict(self, proposal: ActionProposal,
                       verdict: Verdict | None = None,
                       *, cause_ref: str | None = None) -> GateOutcome:
        """Record the human verdict and transition the proposal. `verdict` may be
        supplied directly (the live console) or omitted to pull it from the
        injected VerdictSource (the fixture path). Writes exactly one
        action_verdict row (UNIQUE(proposal_id) → idempotent under retry) and
        moves the proposal to its terminal status, atomically with the revise
        payload edit. Returns the bound GateOutcome the committer checks.

        For tier>=2 intents, an 'approve'/'revise' verdict's human_principal_id
        must be a kind='human' principal distinct from the proposing actor
        (GateError if not) -- a second, independent layer under the token seam's
        `_ensure_human_principal`, backstopped by the 0005 DB trigger. Tier-1
        auto_internal_only verdicts (committers.py::auto_approve_internal) are
        exempt by design."""
        v = verdict or self._source.verdict_for(proposal)
        if v.verdict not in ("approve", "deny", "revise"):
            raise GateError(f"unknown verdict {v.verdict!r}")

        eff_payload = proposal.payload
        eff_sha = proposal.payload_sha256
        if v.verdict == "revise":
            if v.revised_payload is None:
                raise GateError("revise verdict requires a revised_payload")
            eff_payload = v.revised_payload
            eff_sha = canonical_payload_sha256(eff_payload)

        new_status = "denied" if v.verdict == "deny" else "approved"
        approved_sha = None if v.verdict == "deny" else eff_sha

        with session(self._conn, tenant_id=self._tenant_id, actor_id=self._actor,
                     cause_ref=cause_ref, now=self._now) as cur:
            # Gate/DB human-ness check (defense-in-depth; the DB trigger in
            # 0005_gate_human_ness.sql is the hard backstop -- this is the
            # clean application-level error before that raw exception would
            # hit). Scoped to verdicts that AUTHORIZE (approved_sha is not
            # None: 'approve' and gate.py's own payload-mutating 'revise')
            # for tier>=2 intents only -- tier-1 auto_internal_only legitimately
            # auto-approves via a non-human system_principal_id
            # (committers.py::auto_approve_internal) and must stay untouched.
            if approved_sha is not None and proposal.autonomy_tier >= 2:
                cur.execute(
                    "SELECT kind FROM principal WHERE principal_id = %s",
                    (v.human_principal_id,),
                )
                row = cur.fetchone()
                approver_kind = row[0] if row else None
                if approver_kind != "human":
                    raise GateError(
                        f"gate human-ness: approving principal "
                        f"{v.human_principal_id!r} is not kind='human' "
                        f"(tier {proposal.autonomy_tier})")
                if v.human_principal_id == self._actor:
                    raise GateError(
                        f"gate human-ness: approving principal "
                        f"{v.human_principal_id!r} cannot be the proposal's "
                        f"own actor (tier {proposal.autonomy_tier})")

            # revise edits the proposal payload + hash atomically with the verdict.
            if v.verdict == "revise":
                cur.execute(
                    "UPDATE action_proposal SET payload = %s, payload_sha256 = %s, "
                    "status = %s, row_version = row_version + 1 "
                    "WHERE proposal_id = %s",
                    (json.dumps(eff_payload), eff_sha, new_status,
                     proposal.proposal_id),
                )
            else:
                cur.execute(
                    "UPDATE action_proposal SET status = %s, "
                    "row_version = row_version + 1 WHERE proposal_id = %s",
                    (new_status, proposal.proposal_id),
                )
            cur.execute(
                "INSERT INTO action_verdict (tenant_id, proposal_id, verdict, "
                "revised_payload, approved_payload_sha256, rationale, "
                "human_principal_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (self._tenant_id, proposal.proposal_id, v.verdict,
                 json.dumps(v.revised_payload) if v.revised_payload is not None
                 else None, approved_sha, v.rationale, v.human_principal_id),
            )
        return GateOutcome(
            proposal_id=proposal.proposal_id, status=new_status,
            authorized=(new_status == "approved"), payload=eff_payload,
            payload_sha256=eff_sha, verdict=v.verdict,
        )

    # -- deny + supersede (the bounded draft-revise loop's verdict path) ----
    def reject_and_supersede(self, proposal: ActionProposal, *,
                             human_principal_id: str, revised_payload: dict,
                             rationale: str | None = None,
                             cause_ref: str | None = None) -> None:
        """Record a deny+supersede verdict: the ORIGINAL proposal is denied
        (never mutated -- distinct from `record_verdict`'s own 'revise', which
        approves in place). Used by the bounded Slot B draft-revise loop
        (agent1/revise.py), which emits a fresh superseding proposal via
        `propose()` separately; this method only closes out the rejected one.

        `revised_payload` here is the revise-loop's edit-instruction record
        (`{"kind": ..., "edit_instruction": ...}`), NOT an authorized action
        body -- `approved_payload_sha256` is always None for this path,
        because nothing is being authorized to commit. This is why the
        gate/DB human-ness check (record_verdict, above) does not apply here:
        that check is scoped to verdicts that AUTHORIZE
        (approved_payload_sha256 IS NOT NULL), and this path's whole point is
        that it never does.

        Raises GateError if the proposal is not currently 'pending' (a
        compare-and-set on the UPDATE, not a blind write) -- callers must not
        reject_and_supersede a proposal that already has a terminal verdict."""
        with session(self._conn, tenant_id=self._tenant_id, actor_id=self._actor,
                     cause_ref=cause_ref, now=self._now) as cur:
            cur.execute(
                "UPDATE action_proposal SET status = %s, row_version = row_version + 1 "
                "WHERE proposal_id = %s AND status = %s",
                ("denied", proposal.proposal_id, "pending"),
            )
            if cur.rowcount != 1:
                raise GateError(f"proposal is not pending: {proposal.proposal_id}")
            cur.execute(
                "INSERT INTO action_verdict (tenant_id, proposal_id, verdict, "
                "revised_payload, approved_payload_sha256, rationale, "
                "human_principal_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (self._tenant_id, proposal.proposal_id, "revise",
                 json.dumps(revised_payload), None, rationale, human_principal_id),
            )

    # -- the committer's anti-TOCTOU check ----------------------------------
    def assert_payload_bound(self, outcome: GateOutcome, payload: dict) -> None:
        """Fail-closed before executing: the action the committer is about to run
        must hash-match exactly what the verdict authorized. A payload tampered
        after approval (or a re-used denied/stale outcome) is refused."""
        if not outcome.authorized:
            raise GateError(
                f"action not authorized (status={outcome.status})")
        if canonical_payload_sha256(payload) != outcome.payload_sha256:
            raise GateError("payload hash does not match the authorized verdict")

    def idempotency_key_exists(self, idem_key: str) -> bool:
        """Return True if a committer already reserved this mutation key."""
        with session(self._conn, tenant_id=self._tenant_id, actor_id=self._actor,
                     now=self._now) as cur:
            cur.execute(
                "SELECT 1 FROM idempotency_keys WHERE tenant_id = %s AND idem_key = %s",
                (self._tenant_id, idem_key),
            )
            return cur.fetchone() is not None

    def claim_idempotency_key(
        self,
        idem_key: str,
        *,
        request_id: str | None = None,
        result_ref: str | None = None,
        cause_ref: str | None = None,
    ) -> bool:
        """Atomically reserve a committer mutation key.

        Returns True only for the caller that inserted the row. Concurrent or
        retried callers get False and must skip the external mutation.
        """
        with session(self._conn, tenant_id=self._tenant_id, actor_id=self._actor,
                     cause_ref=cause_ref, now=self._now) as cur:
            cur.execute(
                "INSERT INTO idempotency_keys (tenant_id, idem_key, request_id, result_ref) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING idem_key",
                (self._tenant_id, idem_key, request_id, result_ref),
            )
            return cur.fetchone() is not None

    def record_outreach_contact_ref(
        self,
        *,
        account_ref: str,
        contact_ref: str,
        email: str | None = None,
        name: str | None = None,
        consent: bool,
        cause_ref: str | None = None,
    ) -> None:
        """Mirror the contact consent fact a customer-outreach proposal relies on."""
        if not account_ref or not contact_ref:
            raise GateError("outreach contact ref requires account_ref and contact_ref")
        with session(self._conn, tenant_id=self._tenant_id, actor_id=self._actor,
                     cause_ref=cause_ref, now=self._now) as cur:
            cur.execute(
                "INSERT INTO outreach_contact_consent_ref "
                "(tenant_id, account_ref, contact_ref, email, name, consent) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (tenant_id, account_ref, contact_ref) DO UPDATE SET "
                "email = EXCLUDED.email, name = EXCLUDED.name, "
                "consent = EXCLUDED.consent, observed_at = app.clock()",
                (self._tenant_id, account_ref, contact_ref, email, name, consent),
            )

    def mark_idempotency_result(self, idem_key: str, *, result_ref: str) -> None:
        """Attach the external result reference to an already-reserved key."""
        with session(self._conn, tenant_id=self._tenant_id, actor_id=self._actor,
                     now=self._now) as cur:
            cur.execute(
                "UPDATE idempotency_keys SET result_ref = %s "
                "WHERE tenant_id = %s AND idem_key = %s",
                (result_ref, self._tenant_id, idem_key),
            )

    def release_idempotency_key(self, idem_key: str) -> None:
        """Release a reservation when the external system explicitly refused it.

        Ambiguous process crashes keep the row, which is the safer duplicate
        prevention behavior for live writes.
        """
        with session(self._conn, tenant_id=self._tenant_id, actor_id=self._actor,
                     now=self._now) as cur:
            cur.execute(
                "DELETE FROM idempotency_keys WHERE tenant_id = %s AND idem_key = %s",
                (self._tenant_id, idem_key),
            )

    def confirm_authority_ok(self, outcome: GateOutcome) -> bool:
        """For a confirm_order action: True iff the approving verdict was cast by
        a principal that actually holds `order.confirm` — the SoD bridge to Slice
        1's code-minted AuthorizationDecision. The cs-orchestrator principal,
        lacking the permission, fails this."""
        if not outcome.authorized:
            return False
        return self._authz.can_confirm_order(self._human_for(outcome.proposal_id))

    def _human_for(self, proposal_id: str) -> str:
        with session(self._conn, tenant_id=self._tenant_id, actor_id=self._actor,
                     now=self._now) as cur:
            cur.execute(
                "SELECT human_principal_id FROM action_verdict "
                "WHERE proposal_id = %s", (proposal_id,))
            row = cur.fetchone()
        return str(row[0]) if row else ""
