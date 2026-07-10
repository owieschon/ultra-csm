from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from ultra_csm.action_control_contract import (
    ActionControlVerticalSlice,
    action_control_json_schema,
    build_action_control_vertical_slice,
)
from ultra_csm.action_control_demo import (
    action_control_synthetic_run,
    run_action_control_synthetic_scenario,
)
from ultra_csm.committers import CommitError
from ultra_csm.governance import GateError
from ultra_csm.platform.seed import det_uuid


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "contracts" / "action-control.vertical-slice.v1.schema.json"
EXAMPLE_PATH = ROOT / "ui" / "public" / "demo-api" / "action-control-vertical-slice-v1.json"


def test_frozen_schema_and_example_are_current_and_executable(runtime_conn):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    actual = run_action_control_synthetic_scenario(runtime_conn)

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(example)
    parsed = ActionControlVerticalSlice.model_validate(example)

    assert schema == action_control_json_schema()
    assert parsed == actual
    assert parsed.outbound_effects_enabled is False
    assert parsed.simulated_receipt.external_effect is False
    assert parsed.tamper_refusal.attempted_payload_sha256 != (
        parsed.approval.approved_payload_sha256
    )


def test_synthetic_runner_is_deterministic_and_rolls_back_its_state(runtime_conn):
    first = run_action_control_synthetic_scenario(runtime_conn)
    second = run_action_control_synthetic_scenario(runtime_conn)

    assert first == second


def test_contract_rejects_a_tamper_probe_that_reuses_the_approved_hash(runtime_conn):
    payload = run_action_control_synthetic_scenario(runtime_conn).model_dump(mode="json")
    payload["tamper_refusal"]["attempted_payload_sha256"] = (
        payload["approval"]["approved_payload_sha256"]
    )

    with pytest.raises(ValidationError, match="different attempted payload hash"):
        ActionControlVerticalSlice.model_validate(payload)


def test_projection_rejects_a_forged_blank_receipt(runtime_conn):
    with action_control_synthetic_run(runtime_conn) as run:
        forged_receipt = replace(run.evidence.receipt, receipt_id="")
        forged = replace(run.evidence, receipt=forged_receipt)

        with pytest.raises(CommitError, match="identifiers must be non-empty"):
            build_action_control_vertical_slice(
                gate=run.gate,
                committer=run.committer,
                evidence=forged,
            )


def test_projection_rejects_an_arbitrary_approver(runtime_conn):
    with action_control_synthetic_run(runtime_conn) as run:
        forged = replace(
            run.evidence,
            human_principal_id=det_uuid("principal", "forged-approver"),
        )

        with pytest.raises(ValueError, match="does not match the durable verdict"):
            build_action_control_vertical_slice(
                gate=run.gate,
                committer=run.committer,
                evidence=forged,
            )


def test_projection_rejects_forged_tamper_evidence(runtime_conn):
    with action_control_synthetic_run(runtime_conn) as run:
        forged = replace(
            run.evidence,
            tampered_payload=dict(run.evidence.proposal.payload),
        )

        with pytest.raises(ValueError, match="must change the approved payload"):
            build_action_control_vertical_slice(
                gate=run.gate,
                committer=run.committer,
                evidence=forged,
            )


def test_projection_rejects_unbound_proposal_evidence(runtime_conn):
    with action_control_synthetic_run(runtime_conn) as run:
        forged_proposal = replace(
            run.evidence.proposal,
            payload={
                **run.evidence.proposal.payload,
                "evidence_ids": [det_uuid("evidence", "invented")],
            },
        )
        forged = replace(run.evidence, proposal=forged_proposal)

        with pytest.raises(GateError, match="payload hash does not match"):
            build_action_control_vertical_slice(
                gate=run.gate,
                committer=run.committer,
                evidence=forged,
            )
