"""Strict public contract for the rollback-isolated Action Control sandbox."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from ultra_csm.action_control_contract import RECEIPT_ID_PATTERN, SHA256_PATTERN, UUID_PATTERN


COMMAND_LOG_VERSION = "action-control.sandbox-command-log.v1"
SESSION_VERSION = "action-control.sandbox-session.v1"

SandboxState = Literal[
    "pending_human_decision",
    "approved_payload_bound",
    "denied_terminal",
    "simulated_committed",
    "refused_payload_mismatch",
]
SandboxCommandType = Literal[
    "approve_exact",
    "revise_and_approve",
    "deny",
    "commit_simulated",
    "retry_same_commit",
    "probe_tamper",
]
SandboxDraft = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=800),
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Command(_StrictModel):
    command_id: str = Field(pattern=UUID_PATTERN)


class ApproveExactCommand(_Command):
    type: Literal["approve_exact"]


class ReviseAndApproveCommand(_Command):
    type: Literal["revise_and_approve"]
    draft: SandboxDraft


class DenyCommand(_Command):
    type: Literal["deny"]


class CommitSimulatedCommand(_Command):
    type: Literal["commit_simulated"]


class RetrySameCommitCommand(_Command):
    type: Literal["retry_same_commit"]


class ProbeTamperCommand(_Command):
    type: Literal["probe_tamper"]
    draft: SandboxDraft


SandboxCommand = Annotated[
    ApproveExactCommand
    | ReviseAndApproveCommand
    | DenyCommand
    | CommitSimulatedCommand
    | RetrySameCommitCommand
    | ProbeTamperCommand,
    Field(discriminator="type"),
]


class ActionControlSandboxRequest(_StrictModel):
    schema_version: Literal["action-control.sandbox-command-log.v1"]
    run_id: str = Field(pattern=UUID_PATTERN)
    expected_state_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    commands: tuple[SandboxCommand, ...] = Field(default=(), max_length=4)

    @model_validator(mode="after")
    def command_log_is_replayable(self) -> "ActionControlSandboxRequest":
        ids = [command.command_id for command in self.commands]
        if len(ids) != len(set(ids)):
            raise ValueError("sandbox command_id values must be unique")
        if self.commands and self.expected_state_sha256 is None:
            raise ValueError("non-empty command logs require expected_state_sha256")
        if not self.commands and self.expected_state_sha256 is not None:
            raise ValueError("empty command logs require expected_state_sha256=null")
        return self


class SandboxEvidenceView(_StrictModel):
    evidence_id: str = Field(pattern=UUID_PATTERN)
    label: str = Field(min_length=1)
    provenance: Literal["synthetic_fixture"]


class SandboxScenarioView(_StrictModel):
    scenario_id: Literal["trailhead-logistics.payload-binding"]
    account_id: str = Field(pattern=UUID_PATTERN)
    account_name: Literal["Trailhead Logistics"]
    contact_name: Literal["Vanessa Torres"]
    recipient: str = Field(min_length=1)
    original_draft: str = Field(min_length=1)
    evidence: tuple[SandboxEvidenceView, SandboxEvidenceView]


class SandboxProposalView(_StrictModel):
    proposal_id: str = Field(pattern=UUID_PATTERN)
    action: Literal["draft_customer_outreach"]
    status: Literal["pending", "approved", "denied"]
    draft: str = Field(min_length=1)
    payload_sha256: str = Field(pattern=SHA256_PATTERN)


class SandboxDecisionView(_StrictModel):
    verdict: Literal["approve", "revise", "deny"]
    human_principal_id: str = Field(pattern=UUID_PATTERN)
    approved_payload_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)


class SandboxReceiptView(_StrictModel):
    state: Literal["simulated_committed"]
    receipt_id: str = Field(pattern=RECEIPT_ID_PATTERN)
    proposal_id: str = Field(pattern=UUID_PATTERN)
    idempotency_key: str = Field(pattern=SHA256_PATTERN)
    target: Literal["simulated_outbox"]
    committed: Literal[True]
    dry_run: Literal[False]
    external_effect: Literal[False]
    payload_sha256: str = Field(pattern=SHA256_PATTERN)


class SandboxIdempotencyProbeView(_StrictModel):
    state: Literal["duplicate_suppressed"]
    receipt_id: str = Field(pattern=RECEIPT_ID_PATTERN)
    idempotency_key: str = Field(pattern=SHA256_PATTERN)
    committed: Literal[False]
    outbox_rows: Literal[1]


class SandboxTamperRefusalView(_StrictModel):
    state: Literal["refused_payload_mismatch"]
    code: Literal["PAYLOAD_HASH_MISMATCH"]
    reason: Literal["payload hash does not match the authorized verdict"]
    committed: Literal[False]
    approved_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    attempted_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    outbox_rows: Literal[1]


class SandboxEventView(_StrictModel):
    sequence: int = Field(ge=0)
    state: SandboxState
    label: str = Field(min_length=1)
    technical_event: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    payload_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)


class SandboxIsolationView(_StrictModel):
    database_transaction: Literal["rolled_back"]
    filesystem: Literal["temporary_directory_removed"]
    external_effect: Literal[False]


class ActionControlSandboxSession(_StrictModel):
    schema_version: Literal["action-control.sandbox-session.v1"]
    run_id: str = Field(pattern=UUID_PATTERN)
    revision: int = Field(ge=0, le=4)
    state: SandboxState
    state_sha256: str = Field(pattern=SHA256_PATTERN)
    allowed_commands: tuple[SandboxCommandType, ...]
    mode: Literal["rollback_isolated_synthetic"]
    outbound_effects_enabled: Literal[False]
    scenario: SandboxScenarioView
    proposal: SandboxProposalView
    decision: SandboxDecisionView | None
    committed_receipt: SandboxReceiptView | None
    idempotency_probe: SandboxIdempotencyProbeView | None
    tamper_refusal: SandboxTamperRefusalView | None
    events: tuple[SandboxEventView, ...]
    isolation: SandboxIsolationView

    @model_validator(mode="after")
    def authority_and_receipts_stay_bound(self) -> "ActionControlSandboxSession":
        approved = self.decision.approved_payload_sha256 if self.decision else None
        if self.state == "pending_human_decision":
            if self.decision is not None or self.proposal.status != "pending":
                raise ValueError("pending sandbox state requires a pending proposal")
        if self.state == "denied_terminal":
            if (
                self.decision is None
                or self.decision.verdict != "deny"
                or approved is not None
                or self.proposal.status != "denied"
            ):
                raise ValueError("denied sandbox state requires a non-authorizing deny verdict")
        if self.state in {
            "approved_payload_bound",
            "simulated_committed",
            "refused_payload_mismatch",
        }:
            if (
                self.decision is None
                or self.decision.verdict not in {"approve", "revise"}
                or approved is None
                or approved != self.proposal.payload_sha256
                or self.proposal.status != "approved"
            ):
                raise ValueError("authorized sandbox state must bind the current proposal hash")
        if self.state == "approved_payload_bound" and any(
            proof is not None
            for proof in (
                self.committed_receipt,
                self.idempotency_probe,
                self.tamper_refusal,
            )
        ):
            raise ValueError("uncommitted sandbox state cannot carry commit proofs")
        if self.state in {"simulated_committed", "refused_payload_mismatch"}:
            if self.committed_receipt is None:
                raise ValueError("committed sandbox state requires a receipt")
        if (self.state == "refused_payload_mismatch") != (self.tamper_refusal is not None):
            raise ValueError("tamper refusal proof must match the refused sandbox state")
        if self.committed_receipt is not None:
            if approved is None or self.committed_receipt.payload_sha256 != approved:
                raise ValueError("sandbox receipt must bind the authorized payload hash")
            if self.committed_receipt.proposal_id != self.proposal.proposal_id:
                raise ValueError("sandbox receipt must identify the proposal")
        if self.idempotency_probe is not None:
            if self.committed_receipt is None:
                raise ValueError("idempotency proof requires an original committed receipt")
            if self.idempotency_probe.idempotency_key != self.committed_receipt.idempotency_key:
                raise ValueError("idempotency proof must reuse the committed key")
        if self.tamper_refusal is not None:
            if self.committed_receipt is None or approved is None:
                raise ValueError("tamper refusal requires an original authorized commit")
            if self.tamper_refusal.approved_payload_sha256 != approved:
                raise ValueError("tamper refusal must name the authorized hash")
            if self.tamper_refusal.attempted_payload_sha256 == approved:
                raise ValueError("tamper refusal requires a changed attempted hash")
        return self


class SandboxError(Exception):
    """A stable, public sandbox transition error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def action_control_sandbox_json_schema() -> dict:
    schema = ActionControlSandboxSession.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://ultra-csm.example/contracts/action-control.sandbox-session.v1.json"
    return schema
