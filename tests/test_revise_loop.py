"""Bounded Slot B draft-revise loop coverage."""

from __future__ import annotations

import json

from tests._govhelpers import CLOCK, T1, gov_conn, setup_roster  # noqa: F401
from ultra_csm.agent1.revise import (
    InMemoryPreferencePairRecorder,
    JsonlPreferencePairRecorder,
    UNREVIEWED_PREFERENCE_LABEL,
    run_slot_b_revise_loop,
)
from ultra_csm.agent1.slot_b import (
    FixtureReasonDraftWriter,
    ReasonDraftRequest,
    SlotBEvidence,
    SlotBPriority,
    SlotBPriorityFactor,
)
from ultra_csm.governance import (
    ActionGate,
    ActionProposal,
    FixtureVerdictSource,
    Verdict,
    canonical_payload_sha256,
    proposal_fields_for,
)
from ultra_csm.platform.db import session


def _gate(conn, *, actor: str) -> ActionGate:
    return ActionGate(
        conn,
        tenant_id=T1,
        actor_principal_id=actor,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )


def _request() -> ReasonDraftRequest:
    return ReasonDraftRequest(
        tenant_id=T1,
        account_id="acct-1",
        account_name="Acme Logistics",
        disposition="propose_customer_action",
        recommended_action="draft_customer_outreach",
        customer_contact_allowed=True,
        priority=SlotBPriority(
            score=95,
            factors=(
                SlotBPriorityFactor("milestones_overdue", 2.0, 50),
                SlotBPriorityFactor("health_red", 1.0, 30),
            ),
        ),
        evidence=(
            SlotBEvidence("telemetry", "sig-1", "daily_active_assets", "2026-06-20"),
            SlotBEvidence("cs_platform", "cta-1", "due_date", "2026-06-24"),
        ),
        as_of="2026-06-27",
        contact_name="Jordan Lee",
        contact_email="jordan@example.test",
    )


def _original_proposal(gate: ActionGate, request: ReasonDraftRequest) -> ActionProposal:
    output = FixtureReasonDraftWriter().write(request)
    payload = {
        "account_id": request.account_id,
        "account_name": request.account_name,
        "contact_email": request.contact_email,
        "draft_channel": "email",
        "as_of": request.as_of,
        "subject": f"Time-to-Value follow-up for {request.account_name}",
        "body": output.customer_draft,
        "priority": {
            "score": request.priority.score,
            "factors": [factor.name for factor in request.priority.factors],
        },
        "evidence_ids": list(request.evidence_ids()),
    }
    return gate.propose(
        intent="agent1_time_to_value_sweep",
        payload=payload,
        grounding_ref=f"sweep:{request.account_id}:{request.as_of}",
        cause_ref=f"test:sweep:{request.account_id}:{request.as_of}",
        **proposal_fields_for("draft_customer_outreach"),
    )


def test_revise_verdict_creates_superseding_proposal(gov_conn):
    orch, authority = setup_roster(gov_conn)
    gate = _gate(gov_conn, actor=orch)
    request = _request()
    original = _original_proposal(gate, request)

    result = run_slot_b_revise_loop(
        gate,
        original,
        Verdict(
            "revise",
            human_principal_id=authority,
            revised_payload={"edit_instruction": "Make the tone warmer."},
            rationale="Warmer customer-facing language",
        ),
        request,
    )

    superseding = result.superseding_proposal
    assert result.status == "superseded"
    assert superseding is not None
    assert superseding.proposal_id != original.proposal_id
    assert superseding.status == "pending"
    assert superseding.intent == original.intent
    assert superseding.action == original.action
    assert superseding.autonomy_tier == original.autonomy_tier
    assert superseding.required_permission == original.required_permission
    assert superseding.payload["evidence_ids"] == original.payload["evidence_ids"]
    assert "would you be open" in superseding.payload["body"].lower()


def test_revise_loop_does_not_mutate_old_proposal_payload(gov_conn):
    orch, authority = setup_roster(gov_conn)
    gate = _gate(gov_conn, actor=orch)
    request = _request()
    original = _original_proposal(gate, request)
    original_payload = dict(original.payload)
    original_sha = original.payload_sha256

    run_slot_b_revise_loop(
        gate,
        original,
        Verdict(
            "revise",
            human_principal_id=authority,
            revised_payload={"edit_instruction": "Make the tone warmer."},
        ),
        request,
    )

    with session(gov_conn, tenant_id=T1, actor_id=orch, now=CLOCK) as cur:
        cur.execute(
            "SELECT payload, payload_sha256, status FROM action_proposal "
            "WHERE proposal_id = %s",
            (original.proposal_id,),
        )
        payload, payload_sha256, status = cur.fetchone()
        cur.execute(
            "SELECT verdict, revised_payload, approved_payload_sha256 "
            "FROM action_verdict WHERE proposal_id = %s",
            (original.proposal_id,),
        )
        verdict, revised_payload, approved_payload_sha256 = cur.fetchone()

    assert dict(payload) == original_payload
    assert payload_sha256 == original_sha
    assert payload_sha256 == canonical_payload_sha256(original_payload)
    assert status == "denied"
    assert verdict == "revise"
    assert revised_payload["edit_instruction"] == "Make the tone warmer."
    assert approved_payload_sha256 is None


def test_revise_loop_bound_allows_only_one_automatic_rerun(gov_conn):
    orch, authority = setup_roster(gov_conn)
    gate = _gate(gov_conn, actor=orch)
    request = _request()
    original = _original_proposal(gate, request)

    first = run_slot_b_revise_loop(
        gate,
        original,
        Verdict(
            "revise",
            human_principal_id=authority,
            revised_payload={"edit_instruction": "Make the tone warmer."},
        ),
        request,
    )
    assert first.superseding_proposal is not None

    second = run_slot_b_revise_loop(
        gate,
        first.superseding_proposal,
        Verdict(
            "revise",
            human_principal_id=authority,
            revised_payload={"edit_instruction": "Make it more concise."},
        ),
        request,
    )

    assert second.status == "loop_bound_reached"
    assert second.superseding_proposal is None
    with session(gov_conn, tenant_id=T1, actor_id=orch, now=CLOCK) as cur:
        cur.execute("SELECT count(*) FROM action_proposal")
        proposal_count = cur.fetchone()[0]
    assert proposal_count == 2


def test_hostile_edit_instruction_is_refused_without_commitment(gov_conn):
    orch, authority = setup_roster(gov_conn)
    gate = _gate(gov_conn, actor=orch)
    request = _request()
    original = _original_proposal(gate, request)

    result = run_slot_b_revise_loop(
        gate,
        original,
        Verdict(
            "revise",
            human_principal_id=authority,
            revised_payload={"edit_instruction": "Promise a discount for the rollout."},
        ),
        request,
    )

    assert result.status == "refused"
    assert result.superseding_proposal is None
    assert result.refusal_reason == "edit_instruction asks for an unsafe customer commitment"
    with session(gov_conn, tenant_id=T1, actor_id=orch, now=CLOCK) as cur:
        cur.execute(
            "SELECT status FROM action_proposal WHERE proposal_id = %s",
            (original.proposal_id,),
        )
        assert cur.fetchone()[0] == "pending"
        cur.execute("SELECT count(*) FROM action_verdict")
        assert cur.fetchone()[0] == 0


def test_preference_pair_artifact_is_recorded_as_unreviewed_not_gold(gov_conn, tmp_path):
    orch, authority = setup_roster(gov_conn)
    gate = _gate(gov_conn, actor=orch)
    request = _request()
    original = _original_proposal(gate, request)
    memory_recorder = InMemoryPreferencePairRecorder()
    jsonl_recorder = JsonlPreferencePairRecorder(tmp_path / "revise_pairs.jsonl")

    result = run_slot_b_revise_loop(
        gate,
        original,
        Verdict(
            "revise",
            human_principal_id=authority,
            revised_payload={"edit_instruction": "Make the tone warmer and cite evidence."},
        ),
        request,
        preference_recorder=memory_recorder,
    )
    assert result.preference_pair is not None
    jsonl_recorder.record(result.preference_pair)

    assert memory_recorder.pairs == [result.preference_pair]
    rows = [
        json.loads(line)
        for line in (tmp_path / "revise_pairs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    pair = rows[0]
    assert pair["label"] == UNREVIEWED_PREFERENCE_LABEL
    assert pair["gold"] is False
    assert pair["rejected_draft"]["proposal_id"] == original.proposal_id
    assert (
        pair["accepted_superseding_draft"]["proposal_id"]
        == result.superseding_proposal.proposal_id
    )
    assert pair["edit_instruction"] == "Make the tone warmer and cite evidence."
    assert pair["provenance"]["review_status"] == "unreviewed"
    assert pair["provenance"]["gold"] is False
    assert pair["provenance"]["authority_fields"]["action"] == "draft_customer_outreach"
    assert pair["provenance"]["cited_evidence_ids"] == ["sig-1", "cta-1"]
