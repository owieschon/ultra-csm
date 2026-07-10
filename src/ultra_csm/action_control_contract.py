"""Versioned, evidence-bound API contract for the Action Control demo.

The public contract is a projection of a real synthetic run. It never creates
authorization objects itself: the production scenario emits through
``ActionGate``, records a human verdict, commits through
``SimOutboundCommitter``, and executes the tamper probe before this module may
serialize the resulting evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ultra_csm.governance import (
    ActionGate,
    ActionProposal,
    GateError,
    GateOutcome,
    canonical_payload_sha256,
)


CONTRACT_VERSION = "action-control.vertical-slice.v1"
SCENARIO_ID = "trailhead-logistics.payload-binding"
TAMPER_REFUSAL_CODE = "PAYLOAD_HASH_MISMATCH"
TAMPER_REFUSAL_REASON = "payload hash does not match the authorized verdict"
SHA256_PATTERN = r"^[0-9a-f]{64}$"
UUID_PATTERN = (
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
RECEIPT_ID_PATTERN = r"^[0-9a-f]{24}$"


class CommitReceiptLike(Protocol):
    receipt_id: str
    proposal_id: str
    action: str
    account_id: str
    idempotency_key: str
    committed: bool
    dry_run: bool
    target: str
    payload_sha256: str


class BoundReceiptVerifier(Protocol):
    def assert_committed_receipt(
        self,
        proposal: ActionProposal,
        outcome: GateOutcome,
        receipt: CommitReceiptLike,
    ) -> None: ...


@dataclass(frozen=True)
class ActionControlScenarioEvidence:
    """Objects returned by the real synthetic execution path.

    The fields remain explicit so negative tests can prove the projection
    rejects forged evidence. None is trusted without replaying its durable or
    physical binding check.
    """

    proposal: ActionProposal
    outcome: GateOutcome
    receipt: CommitReceiptLike
    human_principal_id: str
    tampered_payload: dict


class _ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ActionControlProposalView(_ContractModel):
    proposal_id: str = Field(pattern=UUID_PATTERN)
    account_id: str = Field(pattern=UUID_PATTERN)
    account_name: str = Field(min_length=1)
    action: Literal["draft_customer_outreach"]
    state: Literal["pending_human_decision"]
    recipient: str = Field(min_length=1)
    draft: str = Field(min_length=1)
    payload_sha256: str = Field(pattern=SHA256_PATTERN)


class ActionControlApprovalView(_ContractModel):
    verdict: Literal["approve"]
    state: Literal["approved_payload_bound"]
    human_principal_id: str = Field(pattern=UUID_PATTERN)
    approved_payload_sha256: str = Field(pattern=SHA256_PATTERN)


class ActionControlSimulatedReceiptView(_ContractModel):
    state: Literal["simulated_committed"]
    receipt_id: str = Field(pattern=RECEIPT_ID_PATTERN)
    proposal_id: str = Field(pattern=UUID_PATTERN)
    idempotency_key: str = Field(pattern=SHA256_PATTERN)
    target: Literal["simulated_outbox"]
    committed: Literal[True]
    dry_run: Literal[False]
    external_effect: Literal[False]
    payload_sha256: str = Field(pattern=SHA256_PATTERN)


class ActionControlTamperRefusalView(_ContractModel):
    state: Literal["refused_payload_mismatch"]
    code: Literal["PAYLOAD_HASH_MISMATCH"]
    reason: Literal["payload hash does not match the authorized verdict"]
    committed: Literal[False]
    approved_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    attempted_payload_sha256: str = Field(pattern=SHA256_PATTERN)


class ActionControlVerticalSlice(_ContractModel):
    schema_version: Literal["action-control.vertical-slice.v1"]
    scenario_id: Literal["trailhead-logistics.payload-binding"]
    mode: Literal["synthetic_sandbox"]
    outbound_effects_enabled: Literal[False]
    state_sequence: tuple[
        Literal["pending_human_decision"],
        Literal["approved_payload_bound"],
        Literal["simulated_committed"],
        Literal["refused_payload_mismatch"],
    ]
    proposal: ActionControlProposalView
    approval: ActionControlApprovalView
    simulated_receipt: ActionControlSimulatedReceiptView
    tamper_refusal: ActionControlTamperRefusalView

    @model_validator(mode="after")
    def hashes_and_identity_stay_bound(self) -> "ActionControlVerticalSlice":
        approved = self.approval.approved_payload_sha256
        if self.proposal.payload_sha256 != approved:
            raise ValueError("approval must bind the proposed payload hash")
        if self.simulated_receipt.payload_sha256 != approved:
            raise ValueError("receipt must bind the approved payload hash")
        if self.tamper_refusal.approved_payload_sha256 != approved:
            raise ValueError("refusal must name the approved payload hash")
        if self.tamper_refusal.attempted_payload_sha256 == approved:
            raise ValueError("tamper refusal requires a different attempted payload hash")
        if self.simulated_receipt.proposal_id != self.proposal.proposal_id:
            raise ValueError("receipt must identify the approved proposal")
        return self


def build_action_control_vertical_slice(
    *,
    gate: ActionGate,
    committer: BoundReceiptVerifier,
    evidence: ActionControlScenarioEvidence,
) -> ActionControlVerticalSlice:
    """Project only evidence that survives every real authority check."""

    proposal = evidence.proposal
    outcome = evidence.outcome
    receipt = evidence.receipt
    if proposal.action != "draft_customer_outreach":
        raise ValueError("vertical slice requires draft_customer_outreach")
    if proposal.status != "pending":
        raise ValueError("proposal snapshot must represent the pending decision")
    if not outcome.authorized or outcome.verdict != "approve":
        raise ValueError("vertical slice requires an authorizing human approval")
    if outcome.proposal_id != proposal.proposal_id:
        raise ValueError("approval must identify the proposed action")
    if outcome.payload_sha256 != proposal.payload_sha256:
        raise ValueError("approval must bind the original proposal payload")

    # Re-read the durable proposal/verdict and derive the approver from the
    # authority-bearing row. The evidence object's label is only accepted when
    # it matches that result exactly.
    bound_approver = gate.approval_principal_id(proposal, outcome)
    if evidence.human_principal_id != bound_approver:
        raise ValueError("approver evidence does not match the durable verdict")

    # Recompute the receipt and require its exact JSONL outbox row plus completed
    # idempotency record. Receipt-shaped caller data is not sufficient.
    committer.assert_committed_receipt(proposal, outcome, receipt)
    if receipt.action != proposal.action:
        raise ValueError("receipt must identify the approved action")
    if receipt.account_id != proposal.payload.get("account_id"):
        raise ValueError("receipt must identify the proposed account")
    if receipt.target != "simulated_outbox":
        raise ValueError("vertical slice receipt must target the simulated outbox")

    attempted_sha = canonical_payload_sha256(evidence.tampered_payload)
    if attempted_sha == outcome.payload_sha256:
        raise ValueError("tamper evidence must change the approved payload")
    try:
        gate.assert_payload_bound(proposal, outcome, evidence.tampered_payload)
    except GateError as exc:
        if str(exc) != TAMPER_REFUSAL_REASON:
            raise ValueError("tamper probe failed outside the payload-binding guard") from exc
        tamper_reason = str(exc)
    else:
        raise ValueError("tamper probe did not trigger the payload-binding guard")

    account_id = proposal.payload.get("account_id")
    account_name = proposal.payload.get("account_name")
    recipient = proposal.payload.get("contact_email")
    draft = proposal.payload.get("body")
    for label, value in (
        ("account_id", account_id),
        ("account_name", account_name),
        ("recipient", recipient),
        ("draft", draft),
    ):
        if not isinstance(value, str) or not value:
            raise ValueError(f"proposal must carry a non-empty {label}")

    return ActionControlVerticalSlice(
        schema_version=CONTRACT_VERSION,
        scenario_id=SCENARIO_ID,
        mode="synthetic_sandbox",
        outbound_effects_enabled=False,
        state_sequence=(
            "pending_human_decision",
            "approved_payload_bound",
            "simulated_committed",
            "refused_payload_mismatch",
        ),
        proposal=ActionControlProposalView(
            proposal_id=proposal.proposal_id,
            account_id=account_id,
            account_name=account_name,
            action="draft_customer_outreach",
            state="pending_human_decision",
            recipient=recipient,
            draft=draft,
            payload_sha256=proposal.payload_sha256,
        ),
        approval=ActionControlApprovalView(
            verdict="approve",
            state="approved_payload_bound",
            human_principal_id=bound_approver,
            approved_payload_sha256=outcome.payload_sha256,
        ),
        simulated_receipt=ActionControlSimulatedReceiptView(
            state="simulated_committed",
            receipt_id=receipt.receipt_id,
            proposal_id=receipt.proposal_id,
            idempotency_key=receipt.idempotency_key,
            target="simulated_outbox",
            committed=True,
            dry_run=False,
            external_effect=False,
            payload_sha256=receipt.payload_sha256,
        ),
        tamper_refusal=ActionControlTamperRefusalView(
            state="refused_payload_mismatch",
            code=TAMPER_REFUSAL_CODE,
            reason=tamper_reason,
            committed=False,
            approved_payload_sha256=outcome.payload_sha256,
            attempted_payload_sha256=attempted_sha,
        ),
    )


def action_control_json_schema() -> dict:
    schema = ActionControlVerticalSlice.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://ultra-csm.example/contracts/action-control.vertical-slice.v1.json"
    return schema
