"""Shared bounded-revise service for API and MCP verdict surfaces."""

from __future__ import annotations

from dataclasses import dataclass

from ultra_csm.agent1 import build_reason_draft_request_for_account
from ultra_csm.agent1.revise import run_slot_b_revise_loop
from ultra_csm.data_plane import CustomerDataPlane
from ultra_csm.governance import ActionGate, ActionProposal, GateError, Verdict


@dataclass(frozen=True)
class ReviseServiceError(Exception):
    """Stable failure returned by the bounded revise service."""

    code: str
    message: str
    proposal_id: str
    status_code: int = 409
    action: str | None = None

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "error": self.message,
            "code": self.code,
            "proposal_id": self.proposal_id,
        }
        if self.action is not None:
            payload["action"] = self.action
        return payload


@dataclass(frozen=True)
class BoundedReviseOutcome:
    """Result shape shared by REST and MCP after a successful revise verdict."""

    proposal_id: str
    status: str
    authorized: bool
    verdict: str
    payload_sha256: str
    superseding_proposal_id: str

    def to_dict(self) -> dict[str, object]:
        return {
            "proposal_id": self.proposal_id,
            "status": self.status,
            "authorized": self.authorized,
            "verdict": self.verdict,
            "payload_sha256": self.payload_sha256,
            "superseding_proposal_id": self.superseding_proposal_id,
        }


def build_revise_request_for_proposal(
    data_plane: CustomerDataPlane,
    tenant_id: str,
    proposal: ActionProposal,
) -> object:
    """Reconstruct the Slot B request needed to revise a draft proposal."""

    if proposal.action != "draft_customer_outreach":
        raise ReviseServiceError(
            code="REVISE_UNSUPPORTED_ACTION",
            message="Only draft_customer_outreach proposals support bounded revise",
            proposal_id=proposal.proposal_id,
            action=proposal.action,
        )

    account_id = proposal.payload.get("account_id")
    if not isinstance(account_id, str) or not account_id:
        raise ReviseServiceError(
            code="REVISE_NOT_RECONSTRUCTABLE",
            message="Proposal payload is missing account_id",
            proposal_id=proposal.proposal_id,
        )

    as_of = proposal.payload.get("as_of")
    evidence_ids = proposal.payload.get("evidence_ids")
    contact_id = proposal.payload.get("contact_id")
    if not isinstance(as_of, str) or not isinstance(evidence_ids, list | tuple):
        raise ReviseServiceError(
            code="REVISE_NOT_RECONSTRUCTABLE",
            message="Proposal payload is missing revise reconstruction fields",
            proposal_id=proposal.proposal_id,
        )

    request = build_reason_draft_request_for_account(
        data_plane,
        tenant_id,
        account_id,
        as_of=as_of,
        action="draft_customer_outreach",
        evidence_source_ids=tuple(str(item) for item in evidence_ids),
        contact_id=contact_id if isinstance(contact_id, str) else None,
    )
    if request is None:
        raise ReviseServiceError(
            code="REVISE_NOT_RECONSTRUCTABLE",
            message="Unable to reconstruct bounded Slot B request",
            proposal_id=proposal.proposal_id,
        )
    return request


def apply_bounded_revise(
    gate: ActionGate,
    proposal: ActionProposal,
    *,
    data_plane: CustomerDataPlane,
    tenant_id: str,
    human_principal_id: str,
    reason: str,
    edit_instruction: str | None,
    cause_ref: str,
) -> BoundedReviseOutcome:
    """Apply the shared bounded revise loop and return a stable response."""

    if not edit_instruction:
        raise ReviseServiceError(
            code="REVISE_INSTRUCTION_REQUIRED",
            message="Revise verdict requires edit_instruction",
            proposal_id=proposal.proposal_id,
        )

    request = build_revise_request_for_proposal(data_plane, tenant_id, proposal)
    verdict = Verdict(
        verdict="revise",
        human_principal_id=human_principal_id,
        revised_payload={"edit_instruction": edit_instruction},
        rationale=reason,
    )

    try:
        result = run_slot_b_revise_loop(
            gate,
            proposal,
            verdict,
            request,  # type: ignore[arg-type]
            cause_ref=cause_ref,
        )
    except GateError as exc:
        raise ReviseServiceError(
            code="REVISE_GATE_ERROR",
            message=str(exc),
            proposal_id=proposal.proposal_id,
        ) from exc

    if result.status == "refused":
        raise ReviseServiceError(
            code="REVISE_REFUSED",
            message=result.refusal_reason or "Revise instruction refused",
            proposal_id=proposal.proposal_id,
        )
    if result.status == "loop_bound_reached":
        raise ReviseServiceError(
            code="REVISE_BOUND_REACHED",
            message=result.refusal_reason or "Automatic revise loop already used",
            proposal_id=proposal.proposal_id,
        )

    assert result.superseding_proposal is not None
    return BoundedReviseOutcome(
        proposal_id=proposal.proposal_id,
        status="denied",
        authorized=False,
        verdict="revise",
        payload_sha256=proposal.payload_sha256,
        superseding_proposal_id=result.superseding_proposal.proposal_id,
    )
