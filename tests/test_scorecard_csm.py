"""CSM-native deterministic scorecard artifact tests."""

from __future__ import annotations

from eval.scorecard_csm import build_scorecard
from ultra_csm.agent1.slot_b import SLOT_B_PROMPT_VERSION


def test_agent1_csm_scorecard_writes_passing_artifact(tmp_path):
    output = tmp_path / "scorecard_csm.json"
    work_queue = tmp_path / "csm_work_queue.json"

    artifact = build_scorecard(output_path=output, work_queue_path=work_queue)

    assert output.exists()
    assert work_queue.exists()
    assert artifact["name"] == "agent1_time_to_value"
    assert artifact["score"] == {"passed": 24, "total": 24}
    assert artifact["hard_ok"] is True
    assert artifact["hard_failures"] == []
    case_ids = {case["case_id"] for case in artifact["cases"]}
    assert {
        "evidence_bundle_complete",
        "gated_outreach_pending",
        "ambiguous_identity_escalates",
        "missing_telemetry_blocks",
        "contact_consent_blocks",
        "import_quarantine",
        "sweep_fixture_book_covers_expected_accounts",
        "slot_b_prompt_artifact_is_versioned",
        "slot_b_contract_accepts_grounded_output",
        "slot_b_blocks_no_consent_draft",
        "slot_b_rejects_unsafe_output",
        "slot_b_rejects_unknown_evidence",
        "degradation_fallback_is_loud",
        "H_cross_tenant",
        "H_ambiguous_no_autopick",
        "H_refusal",
        "H_grounding",
        "H_consent",
        "H_proposal_only",
        "H_no_authority_mint",
        "H_injection",
        "H_reproducible",
        "H_strict_order",
        "H_harness",
    } <= case_ids
    assert artifact["unsafe_placeholder"]["expected_to_fail"] is True
    assert artifact["unsafe_placeholder"]["passed"] is True
    assert len(artifact["unsafe_placeholder"]["failed_hard_gates"]) >= 5
    assert artifact["slot_b"]["prompt_version"] == SLOT_B_PROMPT_VERSION
