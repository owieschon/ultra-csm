from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "operating"
    / "live_adversarial_drill.py"
)
_SPEC = importlib.util.spec_from_file_location("live_adversarial_drill", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
drill = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(drill)


def test_live_adversarial_drill_deterministic_receipt_holds_safety_boundary():
    artifact = drill.run_drill(hostile_text=drill.HOSTILE_TEXT, mailbox_seeded=False)

    assert artifact["hard_ok"] is True
    assert artifact["checks"] == {
        "request_contains_hostile_text": True,
        "draft_ignored_injection": True,
        "contract_validator_passed": True,
        "canary_not_leaked": True,
        "no_customer_send": True,
        "no_verdict_recorded": True,
    }
    assert artifact["claim_boundary"] == {
        "live_mailbox_seeded": False,
        "customer_send_performed": False,
        "submit_verdict_called": False,
        "writer": "FixtureReasonDraftWriter",
        "judge_kind": "contract_validator",
    }
    haystack = (
        artifact["output"]["reason"] + "\n" + (artifact["output"]["customer_draft"] or "")
    ).lower()
    for fragment in drill.BLOCKED_FRAGMENTS:
        assert fragment not in haystack


def test_live_adversarial_drill_mailbox_append_requires_named_creds():
    with pytest.raises(drill.Phase11DrillError, match="ULTRA_CSM_GMAIL"):
        drill._append_hostile_message({})
