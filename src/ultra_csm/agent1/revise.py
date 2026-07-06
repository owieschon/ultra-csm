"""Bounded Slot B draft-revise loop.

This is the draft lane for a human `revise` verdict that carries an edit
instruction. Unlike the legacy gate revise path, this loop never mutates the
original proposal payload. It records the original draft as rejected and emits a
new pending superseding proposal after one deterministic Slot B re-run.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from ultra_csm.agent1.slot_b import (
    FixtureReasonDraftWriter,
    ReasonDraftOutput,
    ReasonDraftRequest,
    ReasonDraftWriter,
    validate_reason_draft_output,
)
from ultra_csm.governance import ActionGate, ActionProposal, GateError, Verdict
from ultra_csm.knowledge import is_safe_customer_ask

UNREVIEWED_PREFERENCE_LABEL = "unreviewed_preference_data"
REVISION_KIND = "slot_b_bounded_redraft"
DEFAULT_MAX_AUTO_RERUNS = 1
MAX_EDIT_INSTRUCTION_CHARS = 280
_HOSTILE_EDIT_TERMS = (
    "approval",
    "approve",
    "approved",
    "commercial terms",
    "contract",
    "credit",
    "discount",
    "free month",
    "guarantee",
    "promise",
    "refund",
    "waive",
)

ReviseLoopStatus = Literal["superseded", "refused", "loop_bound_reached"]


@dataclass(frozen=True)
class PreferencePairArtifact:
    """Unreviewed preference data for later reviewer curation."""

    rejected_draft: dict[str, Any]
    edit_instruction: str
    accepted_superseding_draft: dict[str, Any]
    provenance: dict[str, Any]
    label: str = UNREVIEWED_PREFERENCE_LABEL
    gold: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PreferencePairRecorder(Protocol):
    def record(self, pair: PreferencePairArtifact) -> None: ...


class InMemoryPreferencePairRecorder:
    def __init__(self) -> None:
        self.pairs: list[PreferencePairArtifact] = []

    def record(self, pair: PreferencePairArtifact) -> None:
        self.pairs.append(pair)


class JsonlPreferencePairRecorder:
    """Append-only artifact sink for unreviewed preference pairs."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def record(self, pair: PreferencePairArtifact) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(pair.to_dict(), sort_keys=True) + "\n")


@dataclass(frozen=True)
class ReviseLoopResult:
    status: ReviseLoopStatus
    original_proposal: ActionProposal
    superseding_proposal: ActionProposal | None
    preference_pair: PreferencePairArtifact | None
    refusal_reason: str | None = None
    auto_reruns: int = 0


@dataclass(frozen=True)
class _ConstrainedEditInstruction:
    text: str


def run_slot_b_revise_loop(
    gate: ActionGate,
    proposal: ActionProposal,
    verdict: Verdict,
    request: ReasonDraftRequest,
    *,
    reason_draft_writer: ReasonDraftWriter | None = None,
    preference_recorder: PreferencePairRecorder | None = None,
    max_auto_reruns: int = DEFAULT_MAX_AUTO_RERUNS,
    cause_ref: str | None = None,
) -> ReviseLoopResult:
    """Apply one bounded draft revise request.

    A safe edit instruction produces a fresh pending proposal with the same
    authority fields and evidence ids as the rejected draft. Unsafe instructions
    are refused before any proposal or verdict row is written.
    """

    if verdict.verdict != "revise":
        raise GateError("draft revise loop requires a revise verdict")

    existing_reruns = _auto_reruns_for(proposal)
    if existing_reruns >= max_auto_reruns:
        return ReviseLoopResult(
            status="loop_bound_reached",
            original_proposal=proposal,
            superseding_proposal=None,
            preference_pair=None,
            refusal_reason="automatic draft revise loop already used",
            auto_reruns=existing_reruns,
        )

    instruction_or_reason = _constrain_edit_instruction(verdict)
    if isinstance(instruction_or_reason, str):
        return ReviseLoopResult(
            status="refused",
            original_proposal=proposal,
            superseding_proposal=None,
            preference_pair=None,
            refusal_reason=instruction_or_reason,
            auto_reruns=existing_reruns,
        )
    instruction = instruction_or_reason

    writer = reason_draft_writer or FixtureReasonDraftWriter()
    slot_b_output = writer.write(_request_with_edit_context(request, instruction.text))
    revised_output = _apply_safe_edit_instruction(
        request,
        slot_b_output,
        instruction,
    )
    validate_reason_draft_output(request, revised_output)

    new_payload = _superseding_payload(
        proposal,
        revised_output,
        instruction=instruction,
        auto_reruns=existing_reruns + 1,
    )
    _assert_no_commercial_commitment(new_payload)

    gate.reject_and_supersede(
        proposal,
        human_principal_id=verdict.human_principal_id,
        revised_payload={
            "kind": REVISION_KIND,
            "edit_instruction": instruction.text,
        },
        rationale=verdict.rationale,
        cause_ref=cause_ref,
    )
    superseding = gate.propose(
        intent=proposal.intent,
        action=proposal.action,
        payload=new_payload,
        autonomy_tier=proposal.autonomy_tier,
        required_permission=proposal.required_permission,
        grounding_ref=_superseding_grounding_ref(proposal),
        cause_ref=cause_ref or f"draft-revise:{proposal.proposal_id}",
    )
    pair = _preference_pair(
        proposal,
        superseding,
        instruction=instruction,
        slot_b_output=revised_output,
        human_principal_id=verdict.human_principal_id,
    )
    if preference_recorder is not None:
        preference_recorder.record(pair)

    return ReviseLoopResult(
        status="superseded",
        original_proposal=proposal,
        superseding_proposal=superseding,
        preference_pair=pair,
        auto_reruns=existing_reruns + 1,
    )


def _constrain_edit_instruction(verdict: Verdict) -> _ConstrainedEditInstruction | str:
    raw = None
    if isinstance(verdict.revised_payload, dict):
        raw = verdict.revised_payload.get("edit_instruction")
    if not isinstance(raw, str) or not raw.strip():
        return "revise verdict requires an edit_instruction"

    text = " ".join(raw.split())
    if len(text) > MAX_EDIT_INSTRUCTION_CHARS:
        return "edit_instruction is too long"
    lowered = text.lower()
    if (
        not is_safe_customer_ask(text)
        or any(term in lowered for term in _HOSTILE_EDIT_TERMS)
    ):
        return "edit_instruction asks for an unsafe customer commitment"
    return _ConstrainedEditInstruction(text=text)


def _request_with_edit_context(
    request: ReasonDraftRequest,
    edit_instruction: str,
) -> ReasonDraftRequest:
    return ReasonDraftRequest(
        tenant_id=request.tenant_id,
        account_id=request.account_id,
        account_name=request.account_name,
        disposition=request.disposition,
        recommended_action=request.recommended_action,
        customer_contact_allowed=request.customer_contact_allowed,
        priority=request.priority,
        evidence=request.evidence,
        as_of=request.as_of,
        contact_name=request.contact_name,
        contact_email=request.contact_email,
        untrusted_text_fragments=(
            *request.untrusted_text_fragments,
            edit_instruction,
        ),
        org_context=request.org_context,
    )


def _apply_safe_edit_instruction(
    request: ReasonDraftRequest,
    output: ReasonDraftOutput,
    instruction: _ConstrainedEditInstruction,
) -> ReasonDraftOutput:
    if not request.customer_contact_allowed:
        return output
    draft = output.customer_draft
    if not draft:
        return output

    text = instruction.text.lower()
    edited = draft
    if "warmer" in text or "friendly" in text or "softer" in text:
        edited = edited.replace("Can we ", "Would you be open to ")
        if edited == draft:
            edited = f"{draft} I am happy to help."
    if "concise" in text or "shorter" in text or "brief" in text:
        edited = edited.replace(" is showing an onboarding risk tied to", " has onboarding risk from")
    if "evidence" in text:
        evidence_text = ", ".join(request.evidence_ids()[:2])
        edited = f"{edited} I am basing this on evidence {evidence_text}."
    if edited == draft:
        edited = f"{draft} I want to make sure this is useful for your team."

    return ReasonDraftOutput(
        reason=output.reason,
        cited_evidence_ids=output.cited_evidence_ids,
        customer_draft=edited,
        model_id=output.model_id,
        prompt_version=output.prompt_version,
    )


def _superseding_payload(
    proposal: ActionProposal,
    output: ReasonDraftOutput,
    *,
    instruction: _ConstrainedEditInstruction,
    auto_reruns: int,
) -> dict[str, Any]:
    payload = dict(proposal.payload)
    if output.customer_draft is not None:
        payload["body"] = output.customer_draft
    payload["evidence_ids"] = list(_payload_evidence_ids(proposal.payload))
    root_proposal_id = _root_proposal_id(proposal)
    payload["revise_chain"] = {
        "kind": REVISION_KIND,
        "root_proposal_id": root_proposal_id,
        "parent_proposal_id": proposal.proposal_id,
        "auto_reruns": auto_reruns,
        "edit_instruction": instruction.text,
    }
    return payload


def _preference_pair(
    rejected: ActionProposal,
    accepted: ActionProposal,
    *,
    instruction: _ConstrainedEditInstruction,
    slot_b_output: ReasonDraftOutput,
    human_principal_id: str,
) -> PreferencePairArtifact:
    return PreferencePairArtifact(
        rejected_draft=_draft_artifact_payload(rejected),
        edit_instruction=instruction.text,
        accepted_superseding_draft=_draft_artifact_payload(accepted),
        provenance={
            "artifact_type": "draft_preference_pair",
            "review_status": "unreviewed",
            "gold": False,
            "root_proposal_id": _root_proposal_id(accepted),
            "rejected_proposal_id": rejected.proposal_id,
            "superseding_proposal_id": accepted.proposal_id,
            "human_principal_id": human_principal_id,
            "model_id": slot_b_output.model_id,
            "prompt_version": slot_b_output.prompt_version,
            "cited_evidence_ids": list(slot_b_output.cited_evidence_ids),
            "authority_fields": {
                "intent": accepted.intent,
                "action": accepted.action,
                "autonomy_tier": accepted.autonomy_tier,
                "required_permission": accepted.required_permission,
            },
        },
    )


def _draft_artifact_payload(proposal: ActionProposal) -> dict[str, Any]:
    return {
        "proposal_id": proposal.proposal_id,
        "payload": proposal.payload,
        "payload_sha256": proposal.payload_sha256,
    }


def _auto_reruns_for(proposal: ActionProposal) -> int:
    chain = proposal.payload.get("revise_chain")
    if not isinstance(chain, dict):
        return 0
    value = chain.get("auto_reruns", 0)
    return value if isinstance(value, int) else 0


def _root_proposal_id(proposal: ActionProposal) -> str:
    chain = proposal.payload.get("revise_chain")
    if isinstance(chain, dict) and isinstance(chain.get("root_proposal_id"), str):
        return chain["root_proposal_id"]
    return proposal.proposal_id


def _payload_evidence_ids(payload: dict[str, Any]) -> tuple[str, ...]:
    value = payload.get("evidence_ids")
    if not isinstance(value, list | tuple):
        return ()
    return tuple(str(item) for item in value)


def _assert_no_commercial_commitment(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    if not is_safe_customer_ask(text) or any(term in text for term in _HOSTILE_EDIT_TERMS):
        raise GateError("superseding draft contains unsafe customer commitment")


def _superseding_grounding_ref(proposal: ActionProposal) -> str:
    return f"revise:{REVISION_KIND}:{proposal.proposal_id}"
