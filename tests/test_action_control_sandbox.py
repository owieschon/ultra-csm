from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import psycopg
import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from ultra_csm.action_control_demo import _PROPOSAL_ID, _TENANT_ID
from ultra_csm.action_control_sandbox import evaluate_action_control_sandbox
from ultra_csm.action_control_sandbox_contract import (
    ActionControlSandboxRequest,
    SandboxError,
    action_control_sandbox_json_schema,
)
from ultra_csm.platform.seed import det_uuid


def _request(run: str, commands=(), expected=None) -> ActionControlSandboxRequest:
    return ActionControlSandboxRequest(
        schema_version="action-control.sandbox-command-log.v1",
        run_id=run,
        expected_state_sha256=expected,
        commands=commands,
    )


def _command(run: str, index: int, command_type: str, **extra) -> dict:
    return {
        "command_id": det_uuid("action-control-command", run, str(index)),
        "type": command_type,
        **extra,
    }


def _advance(conn, run: str, commands: list[dict], current, command_type: str, **extra):
    commands.append(_command(run, len(commands), command_type, **extra))
    return evaluate_action_control_sandbox(
        conn,
        _request(run, tuple(commands), current.state_sha256),
    )


def test_real_approve_commit_retry_and_tamper_path_is_bound(runtime_conn):
    run = det_uuid("action-control-run", "complete")
    commands: list[dict] = []
    current = evaluate_action_control_sandbox(runtime_conn, _request(run))
    assert current.state == "pending_human_decision"

    current = _advance(runtime_conn, run, commands, current, "approve_exact")
    assert current.state == "approved_payload_bound"
    assert current.decision is not None
    assert current.decision.approved_payload_sha256 == current.proposal.payload_sha256

    current = _advance(runtime_conn, run, commands, current, "commit_simulated")
    assert current.state == "simulated_committed"
    assert current.committed_receipt is not None
    assert current.committed_receipt.external_effect is False

    current = _advance(runtime_conn, run, commands, current, "retry_same_commit")
    assert current.idempotency_probe is not None
    assert current.idempotency_probe.committed is False
    assert current.idempotency_probe.outbox_rows == 1

    current = _advance(
        runtime_conn,
        run,
        commands,
        current,
        "probe_tamper",
        draft="Send immediately without the approved review language.",
    )
    assert current.state == "refused_payload_mismatch"
    assert current.tamper_refusal is not None
    assert current.tamper_refusal.code == "PAYLOAD_HASH_MISMATCH"
    assert current.tamper_refusal.outbox_rows == 1
    assert current.committed_receipt is not None


def test_revise_authorizes_only_the_revised_draft(runtime_conn):
    run = det_uuid("action-control-run", "revise")
    initial = evaluate_action_control_sandbox(runtime_conn, _request(run))
    revised = _advance(
        runtime_conn,
        run,
        [],
        initial,
        "revise_and_approve",
        draft="Hi Vanessa, can we review the two documented onboarding blockers together?",
    )

    assert revised.state == "approved_payload_bound"
    assert revised.proposal.draft.startswith("Hi Vanessa")
    assert revised.proposal.payload_sha256 != initial.proposal.payload_sha256
    assert revised.decision is not None
    assert revised.decision.verdict == "revise"
    assert revised.decision.approved_payload_sha256 == revised.proposal.payload_sha256


def test_denial_is_terminal_and_invalid_replay_rolls_back(runtime_conn, bootstrap_conn):
    run = det_uuid("action-control-run", "deny")
    commands: list[dict] = []
    initial = evaluate_action_control_sandbox(runtime_conn, _request(run))
    denied = _advance(runtime_conn, run, commands, initial, "deny")
    commands.append(_command(run, len(commands), "commit_simulated"))

    with pytest.raises(SandboxError, match="not allowed") as caught:
        evaluate_action_control_sandbox(
            runtime_conn,
            _request(run, tuple(commands), denied.state_sha256),
        )
    assert caught.value.code == "INVALID_TRANSITION"
    assert _sandbox_row_counts(bootstrap_conn) == (0, 0, 0)


def test_command_prefix_digest_mismatch_is_rejected(runtime_conn):
    run = det_uuid("action-control-run", "prefix-mismatch")
    command = _command(run, 0, "approve_exact")
    with pytest.raises(SandboxError) as caught:
        evaluate_action_control_sandbox(
            runtime_conn,
            _request(run, (command,), "0" * 64),
        )
    assert caught.value.code == "COMMAND_PREFIX_MISMATCH"


def test_same_prefix_can_branch_across_stateless_requests(runtime_conn):
    run = det_uuid("action-control-run", "intentional-fork")
    initial = evaluate_action_control_sandbox(runtime_conn, _request(run))
    approved = evaluate_action_control_sandbox(
        runtime_conn,
        _request(
            run,
            (_command(run, 0, "approve_exact"),),
            initial.state_sha256,
        ),
    )
    denied = evaluate_action_control_sandbox(
        runtime_conn,
        _request(
            run,
            (_command(run, 0, "deny"),),
            initial.state_sha256,
        ),
    )

    assert approved.state == "approved_payload_bound"
    assert denied.state == "denied_terminal"
    assert approved.state_sha256 != denied.state_sha256


def test_reset_is_a_new_empty_run_and_replays_are_deterministic(runtime_conn):
    first_run = det_uuid("action-control-run", "first")
    reset_run = det_uuid("action-control-run", "reset")
    first = evaluate_action_control_sandbox(runtime_conn, _request(first_run))
    same = evaluate_action_control_sandbox(runtime_conn, _request(first_run))
    reset = evaluate_action_control_sandbox(runtime_conn, _request(reset_run))

    assert first == same
    assert reset.state == "pending_human_decision"
    assert reset.revision == 0
    assert reset.run_id != first.run_id
    assert reset.state_sha256 != first.state_sha256


def test_successful_runs_leave_no_database_rows(runtime_conn, bootstrap_conn):
    run = det_uuid("action-control-run", "rollback")
    initial = evaluate_action_control_sandbox(runtime_conn, _request(run))
    _advance(runtime_conn, run, [], initial, "approve_exact")
    assert _sandbox_row_counts(bootstrap_conn) == (0, 0, 0)


def test_concurrent_runs_are_isolated(cluster):
    run_ids = [det_uuid("action-control-run", f"concurrent-{index}") for index in range(6)]

    def evaluate(run_id: str):
        with psycopg.connect(**cluster.dsn(user="app_runtime")) as conn:
            return evaluate_action_control_sandbox(conn, _request(run_id))

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(evaluate, run_ids))

    assert [result.run_id for result in results] == run_ids
    assert all(result.state == "pending_human_decision" for result in results)
    assert len({result.state_sha256 for result in results}) == len(run_ids)


def test_frozen_sandbox_schema_is_current():
    root = Path(__file__).resolve().parents[1]
    frozen = json.loads(
        (root / "docs" / "contracts" / "action-control.sandbox-session.v1.schema.json")
        .read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(frozen)
    assert frozen == action_control_sandbox_json_schema()


def test_request_refuses_duplicate_commands_and_client_selected_targets():
    run = det_uuid("action-control-run", "invalid-request")
    command_id = det_uuid("action-control-command", run, "same")
    with pytest.raises(ValidationError, match="must be unique"):
        _request(
            run,
            (
                {"command_id": command_id, "type": "approve_exact"},
                {"command_id": command_id, "type": "commit_simulated"},
            ),
            "1" * 64,
        )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ActionControlSandboxRequest.model_validate(
            {
                "schema_version": "action-control.sandbox-command-log.v1",
                "run_id": run,
                "expected_state_sha256": None,
                "commands": [],
                "target": "live_salesforce",
            }
        )
    with pytest.raises(ValidationError, match="at least 1 character"):
        _request(
            run,
            (
                {
                    "command_id": det_uuid("action-control-command", run, "blank"),
                    "type": "revise_and_approve",
                    "draft": "   ",
                },
            ),
            "1" * 64,
        )


def test_response_contract_refuses_rehashed_tamper_claim(runtime_conn):
    run = det_uuid("action-control-run", "contract-tamper")
    commands: list[dict] = []
    current = evaluate_action_control_sandbox(runtime_conn, _request(run))
    current = _advance(runtime_conn, run, commands, current, "approve_exact")
    current = _advance(runtime_conn, run, commands, current, "commit_simulated")
    current = _advance(
        runtime_conn,
        run,
        commands,
        current,
        "probe_tamper",
        draft="A changed draft that must not cross the boundary.",
    )
    forged = current.model_dump(mode="json")
    forged["tamper_refusal"]["attempted_payload_sha256"] = (
        forged["tamper_refusal"]["approved_payload_sha256"]
    )

    with pytest.raises(ValidationError, match="changed attempted hash"):
        type(current).model_validate(forged)

    forged = current.model_dump(mode="json")
    forged["state"] = "simulated_committed"
    with pytest.raises(ValidationError, match="must match the refused sandbox state"):
        type(current).model_validate(forged)


def _sandbox_row_counts(conn) -> tuple[int, int, int]:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM action_proposal WHERE proposal_id = %s", (_PROPOSAL_ID,))
        proposals = int(cur.fetchone()[0])
        cur.execute("SELECT count(*) FROM action_verdict WHERE proposal_id = %s", (_PROPOSAL_ID,))
        verdicts = int(cur.fetchone()[0])
        cur.execute("SELECT count(*) FROM tenant WHERE tenant_id = %s", (_TENANT_ID,))
        tenants = int(cur.fetchone()[0])
    return proposals, verdicts, tenants
