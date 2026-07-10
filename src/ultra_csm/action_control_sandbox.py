"""Rollback-only command-log evaluator for the public Action Control sandbox."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from psycopg import Connection
from psycopg.pq import TransactionStatus

from ultra_csm.action_control_contract import (
    SCENARIO_ID,
    TAMPER_REFUSAL_CODE,
    TAMPER_REFUSAL_REASON,
)
from ultra_csm.action_control_demo import (
    _ACCOUNT_ID,
    _CONTACT_ID,
    _EVIDENCE_IDS,
    _PROPOSAL_ID,
    _TENANT_ID,
    _initialize_demo_principals,
)
from ultra_csm.action_control_sandbox_contract import (
    ActionControlSandboxRequest,
    ActionControlSandboxSession,
    SandboxDecisionView,
    SandboxError,
    SandboxEventView,
    SandboxEvidenceView,
    SandboxIdempotencyProbeView,
    SandboxIsolationView,
    SandboxProposalView,
    SandboxReceiptView,
    SandboxScenarioView,
    SandboxTamperRefusalView,
)
from ultra_csm.committers import SimOutboundCommitter, load_action_proposal
from ultra_csm.governance import (
    ActionGate,
    ActionProposal,
    FixtureVerdictSource,
    GateError,
    GateOutcome,
    Verdict,
    canonical_payload_sha256,
)
from ultra_csm.platform.seed import SEED_CLOCK


_CONTACT_EMAIL = "vanessa.torres@trailhead-logistics.example"
_ORIGINAL_DRAFT = (
    "Hi Vanessa, Trailhead Logistics is showing an onboarding risk tied to an "
    "overdue success plan. Can we review the activation blockers?"
)
_ISOLATION = SandboxIsolationView(
    database_transaction="rolled_back",
    filesystem="temporary_directory_removed",
    external_effect=False,
)


def _base_payload() -> dict:
    return {
        "account_id": _ACCOUNT_ID,
        "account_name": "Trailhead Logistics",
        "contact_id": _CONTACT_ID,
        "contact_email": _CONTACT_EMAIL,
        "body": _ORIGINAL_DRAFT,
        "evidence_ids": list(_EVIDENCE_IDS),
    }


def _outbox_rows(path: Path, idempotency_key: str) -> int:
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        receipt = row.get("receipt") if isinstance(row, dict) else None
        if isinstance(receipt, dict) and receipt.get("idempotency_key") == idempotency_key:
            count += 1
    return count


def _invalid(state: str, command: str) -> SandboxError:
    return SandboxError(
        "INVALID_TRANSITION",
        f"{command} is not allowed while the sandbox is {state}",
    )


def _allowed(state: str, *, retried: bool) -> tuple[str, ...]:
    if state == "pending_human_decision":
        return ("approve_exact", "revise_and_approve", "deny")
    if state == "approved_payload_bound":
        return ("commit_simulated",)
    if state == "simulated_committed":
        return (("probe_tamper",) if retried else ("retry_same_commit", "probe_tamper"))
    return ()


def _receipt_view(receipt) -> SandboxReceiptView:
    return SandboxReceiptView(
        state="simulated_committed",
        receipt_id=receipt.receipt_id,
        proposal_id=receipt.proposal_id,
        idempotency_key=receipt.idempotency_key,
        target="simulated_outbox",
        committed=True,
        dry_run=False,
        external_effect=False,
        payload_sha256=receipt.payload_sha256,
    )


def _jsonable(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _render(
    *,
    request: ActionControlSandboxRequest,
    revision: int,
    state: str,
    proposal: ActionProposal,
    decision: SandboxDecisionView | None,
    committed_receipt: SandboxReceiptView | None,
    idempotency_probe: SandboxIdempotencyProbeView | None,
    tamper_refusal: SandboxTamperRefusalView | None,
    events: list[SandboxEventView],
) -> ActionControlSandboxSession:
    payload = {
        "schema_version": "action-control.sandbox-session.v1",
        "run_id": request.run_id,
        "revision": revision,
        "state": state,
        "allowed_commands": _allowed(state, retried=idempotency_probe is not None),
        "mode": "rollback_isolated_synthetic",
        "outbound_effects_enabled": False,
        "scenario": SandboxScenarioView(
            scenario_id=SCENARIO_ID,
            account_id=_ACCOUNT_ID,
            account_name="Trailhead Logistics",
            contact_name="Vanessa Torres",
            recipient=_CONTACT_EMAIL,
            original_draft=_ORIGINAL_DRAFT,
            evidence=(
                SandboxEvidenceView(
                    evidence_id=_EVIDENCE_IDS[0],
                    label="Activation gap remains unresolved",
                    provenance="synthetic_fixture",
                ),
                SandboxEvidenceView(
                    evidence_id=_EVIDENCE_IDS[1],
                    label="Success plan is overdue",
                    provenance="synthetic_fixture",
                ),
            ),
        ),
        "proposal": SandboxProposalView(
            proposal_id=proposal.proposal_id,
            action="draft_customer_outreach",
            status=proposal.status,
            draft=str(proposal.payload["body"]),
            payload_sha256=proposal.payload_sha256,
        ),
        "decision": decision,
        "committed_receipt": committed_receipt,
        "idempotency_probe": idempotency_probe,
        "tamper_refusal": tamper_refusal,
        "events": tuple(events),
        "isolation": _ISOLATION,
    }
    digest = canonical_payload_sha256(_jsonable(payload))
    return ActionControlSandboxSession(state_sha256=digest, **payload)


def evaluate_action_control_sandbox(
    conn: Connection,
    request: ActionControlSandboxRequest,
) -> ActionControlSandboxSession:
    """Replay a bounded command log through real governance, then erase it all."""

    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise RuntimeError("Action Control sandbox requires an idle connection")

    result: ActionControlSandboxSession | None = None
    state_dir: Path | None = None
    conn.execute("BEGIN")
    try:
        # V1 uses fixed deterministic fixture IDs. Serialize these short demo
        # transactions so concurrent no-login runs cannot contend on those rows.
        conn.execute("SELECT pg_advisory_xact_lock(hashtext('action-control-sandbox-v1'))")
        orchestrator, human = _initialize_demo_principals(conn)
        gate = ActionGate(
            conn,
            tenant_id=_TENANT_ID,
            actor_principal_id=orchestrator,
            verdict_source=FixtureVerdictSource(),
            now=SEED_CLOCK,
        )
        gate.record_outreach_contact_ref(
            account_ref=_ACCOUNT_ID,
            contact_ref=_CONTACT_ID,
            email=_CONTACT_EMAIL,
            name="Vanessa Torres",
            consent=True,
            cause_ref=f"sandbox:{request.run_id}:consent",
        )
        proposal = gate.propose(
            proposal_id=_PROPOSAL_ID,
            intent="agent1_time_to_value_sweep",
            action="draft_customer_outreach",
            payload=_base_payload(),
            autonomy_tier=2,
            required_permission="customer.outreach.draft",
            cause_ref=f"sandbox:{request.run_id}:propose",
        )
        state = "pending_human_decision"
        outcome: GateOutcome | None = None
        decision: SandboxDecisionView | None = None
        committed_receipt: SandboxReceiptView | None = None
        idempotency_probe: SandboxIdempotencyProbeView | None = None
        tamper_refusal: SandboxTamperRefusalView | None = None
        events = [
            SandboxEventView(
                sequence=0,
                state="pending_human_decision",
                label="Draft proposed",
                technical_event="gate.propose",
                detail="A synthetic customer draft is waiting for a human decision.",
                payload_sha256=proposal.payload_sha256,
            )
        ]

        with tempfile.TemporaryDirectory(prefix="ultra-action-control-sandbox-") as raw_dir:
            state_dir = Path(raw_dir)
            committer = SimOutboundCommitter(
                gate,
                state_dir=state_dir,
                target_ref="simulated_outbox",
            )
            for index, command in enumerate(request.commands):
                if index == len(request.commands) - 1:
                    prefix = _render(
                        request=request,
                        revision=index,
                        state=state,
                        proposal=proposal,
                        decision=decision,
                        committed_receipt=committed_receipt,
                        idempotency_probe=idempotency_probe,
                        tamper_refusal=tamper_refusal,
                        events=events,
                    )
                    if prefix.state_sha256 != request.expected_state_sha256:
                        raise SandboxError(
                            "COMMAND_PREFIX_MISMATCH",
                            "The expected digest does not match the submitted command prefix.",
                        )

                if command.type in {"approve_exact", "revise_and_approve", "deny"}:
                    if state != "pending_human_decision":
                        raise _invalid(state, command.type)
                    revised_payload = None
                    verdict_name = command.type
                    if command.type == "approve_exact":
                        verdict = "approve"
                    elif command.type == "deny":
                        verdict = "deny"
                    else:
                        verdict = "revise"
                        revised_payload = {**proposal.payload, "body": command.draft.strip()}
                    outcome = gate.record_verdict(
                        proposal,
                        Verdict(
                            verdict,
                            human_principal_id=human,
                            revised_payload=revised_payload,
                            rationale=f"Synthetic sandbox command: {verdict_name}",
                        ),
                        cause_ref=f"sandbox:{request.run_id}:{command.type}",
                    )
                    proposal = load_action_proposal(
                        conn,
                        tenant_id=_TENANT_ID,
                        actor_principal_id=orchestrator,
                        proposal_id=proposal.proposal_id,
                        now=SEED_CLOCK,
                    )
                    state = (
                        "denied_terminal" if verdict == "deny" else "approved_payload_bound"
                    )
                    bound_human = (
                        human if verdict == "deny" else gate.approval_principal_id(proposal, outcome)
                    )
                    decision = SandboxDecisionView(
                        verdict=verdict,
                        human_principal_id=bound_human,
                        approved_payload_sha256=(
                            None if verdict == "deny" else outcome.payload_sha256
                        ),
                    )
                    events.append(
                        SandboxEventView(
                            sequence=len(events),
                            state=state,
                            label=(
                                "Draft denied"
                                if verdict == "deny"
                                else "Revised draft approved"
                                if verdict == "revise"
                                else "Exact draft approved"
                            ),
                            technical_event=f"gate.{verdict}",
                            detail=(
                                "No payload was authorized."
                                if verdict == "deny"
                                else "The durable human verdict is bound to this payload hash."
                            ),
                            payload_sha256=(None if verdict == "deny" else outcome.payload_sha256),
                        )
                    )
                    continue

                if command.type == "commit_simulated":
                    if state != "approved_payload_bound" or outcome is None:
                        raise _invalid(state, command.type)
                    receipt = committer.commit(proposal, outcome)
                    committer.assert_committed_receipt(proposal, outcome, receipt)
                    if _outbox_rows(state_dir / "outbox.jsonl", receipt.idempotency_key) != 1:
                        raise RuntimeError("simulated commit did not produce exactly one outbox row")
                    committed_receipt = _receipt_view(receipt)
                    state = "simulated_committed"
                    events.append(
                        SandboxEventView(
                            sequence=len(events),
                            state=state,
                            label="Simulated outbox committed",
                            technical_event="sim_outbound.commit",
                            detail="One temporary outbox row was physically verified; no external send occurred.",
                            payload_sha256=receipt.payload_sha256,
                        )
                    )
                    continue

                if command.type == "retry_same_commit":
                    if (
                        state != "simulated_committed"
                        or outcome is None
                        or committed_receipt is None
                        or idempotency_probe is not None
                    ):
                        raise _invalid(state, command.type)
                    retry = committer.commit(proposal, outcome)
                    rows = _outbox_rows(state_dir / "outbox.jsonl", retry.idempotency_key)
                    if retry.committed or rows != 1:
                        raise RuntimeError("idempotency retry was not suppressed")
                    idempotency_probe = SandboxIdempotencyProbeView(
                        state="duplicate_suppressed",
                        receipt_id=retry.receipt_id,
                        idempotency_key=retry.idempotency_key,
                        committed=False,
                        outbox_rows=1,
                    )
                    events.append(
                        SandboxEventView(
                            sequence=len(events),
                            state=state,
                            label="Duplicate commit suppressed",
                            technical_event="idempotency.duplicate",
                            detail="The same key returned committed=false and the outbox stayed at one row.",
                            payload_sha256=retry.payload_sha256,
                        )
                    )
                    continue

                if command.type == "probe_tamper":
                    if state != "simulated_committed" or outcome is None:
                        raise _invalid(state, command.type)
                    tampered = {**proposal.payload, "body": command.draft.strip()}
                    attempted_sha = canonical_payload_sha256(tampered)
                    if attempted_sha == outcome.payload_sha256:
                        raise SandboxError(
                            "TAMPER_PAYLOAD_UNCHANGED",
                            "Change the approved draft before running the tamper probe.",
                        )
                    forged = ActionProposal(
                        proposal_id=proposal.proposal_id,
                        intent=proposal.intent,
                        action=proposal.action,
                        payload=tampered,
                        payload_sha256=attempted_sha,
                        autonomy_tier=proposal.autonomy_tier,
                        required_permission=proposal.required_permission,
                        status=proposal.status,
                    )
                    try:
                        committer.commit(forged, outcome)
                    except GateError as exc:
                        if str(exc) != TAMPER_REFUSAL_REASON:
                            raise
                    else:
                        raise RuntimeError("tampered payload unexpectedly reached the outbox")
                    if committed_receipt is None:
                        raise RuntimeError("tamper probe lost the original committed receipt")
                    rows = _outbox_rows(
                        state_dir / "outbox.jsonl", committed_receipt.idempotency_key
                    )
                    if rows != 1:
                        raise RuntimeError("tamper probe changed the simulated outbox")
                    tamper_refusal = SandboxTamperRefusalView(
                        state="refused_payload_mismatch",
                        code=TAMPER_REFUSAL_CODE,
                        reason=TAMPER_REFUSAL_REASON,
                        committed=False,
                        approved_payload_sha256=outcome.payload_sha256,
                        attempted_payload_sha256=attempted_sha,
                        outbox_rows=1,
                    )
                    state = "refused_payload_mismatch"
                    events.append(
                        SandboxEventView(
                            sequence=len(events),
                            state=state,
                            label="Altered payload refused",
                            technical_event="committer.payload_mismatch",
                            detail="The original simulated receipt remains; the changed draft added no row.",
                            payload_sha256=attempted_sha,
                        )
                    )
                    continue

                raise SandboxError("UNKNOWN_COMMAND", f"Unsupported command: {command.type}")

            result = _render(
                request=request,
                revision=len(request.commands),
                state=state,
                proposal=proposal,
                decision=decision,
                committed_receipt=committed_receipt,
                idempotency_probe=idempotency_probe,
                tamper_refusal=tamper_refusal,
                events=events,
            )
    finally:
        conn.rollback()

    if state_dir is not None and state_dir.exists():
        raise RuntimeError("sandbox temporary outbox survived cleanup")
    if result is None:
        raise RuntimeError("sandbox evaluation produced no result")
    return result
