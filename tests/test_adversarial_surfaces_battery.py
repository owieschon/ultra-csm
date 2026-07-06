from __future__ import annotations

import json

import pytest

from eval.adversarial_surfaces_battery import run_battery
from tests.test_agent1_slot_b import _BOOKING_ORG_CONTEXT, _request
from ultra_csm.agent1 import (
    ReasonDraftOutput,
    SLOT_B_PROMPT_VERSION,
    SlotBContractError,
    validate_reason_draft_output,
)


def test_adversarial_surfaces_battery_hard_ok():
    report = run_battery()

    assert report["hard_ok"], report["failed_cases"]
    assert [case["case"] for case in report["cases"]] == [
        "url-smuggle-set",
        "ui-rendered-content-text-only",
        "verdict-contract-abuse-guards",
        "preexisting-canary-battery",
    ]
    assert report["claim_boundary"] == {
        "offline_deterministic": True,
        "live_mailbox_seeded": False,
        "customer_send_performed": False,
    }


def test_adversarial_surfaces_battery_two_runs_byte_identical():
    first = run_battery()
    second = run_battery()

    assert json.dumps(first, sort_keys=True, default=str) == json.dumps(
        second, sort_keys=True, default=str
    )


@pytest.mark.parametrize(
    "draft",
    [
        "Hi Jordan, [Schedule](javascript:alert(1))",
        "Hi Jordan, open data:text/html,<script>alert(1)</script>",
    ],
)
def test_slot_b_validator_rejects_dangerous_uri_schemes(draft: str):
    request = _request(org_context=_BOOKING_ORG_CONTEXT)
    output = ReasonDraftOutput(
        reason="Score 95 from evidence [evidence:sig-1].",
        cited_evidence_ids=("sig-1",),
        customer_draft=draft,
        model_id="test",
        prompt_version=SLOT_B_PROMPT_VERSION,
    )

    with pytest.raises(SlotBContractError, match="unsafe URI scheme"):
        validate_reason_draft_output(request, output)
