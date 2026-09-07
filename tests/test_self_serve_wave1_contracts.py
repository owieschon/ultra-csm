"""MP-E Wave 1 and Wave 6 contract fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.self_serve_nudge_gold import (
    SelfServeNudgeGoldError,
    load_self_serve_nudge_candidates,
)
from ultra_csm.agent1.content_route_matcher import load_tenant_content_catalog
from ultra_csm.data_plane.contracts import (
    IdentityResolution,
    ProductUser,
    ProductUserUsageLink,
)
from ultra_csm.data_plane.fixtures import ACME_LOGISTICS
from ultra_csm.data_plane.self_serve_fixtures import (
    FixtureCallIntelligenceConnector,
    FixtureLifecycleEmailConnector,
    FixtureSalesEngagementConnector,
    TranscriptDomainError,
    assert_transcript_out_of_slot_b_domain,
)


def _product_user() -> ProductUser:
    return ProductUser(
        user_id="usr_selfserve_test",
        email="jordan@example.test",
        account_id=ACME_LOGISTICS,
        signup_at="2026-07-01T12:00:00Z",
        plan="trial",
        tier="self_serve",
        lifecycle_state="aha_pending",
    )


def test_product_user_identity_contract_uses_shared_resolution_states():
    user = _product_user()
    exactly_one = IdentityResolution(
        state="exactly_one",
        user_id=user.user_id,
        email=user.email,
        contact_id="contact-1",
        account_id=user.account_id,
    )
    ambiguous = IdentityResolution(
        state="ambiguous",
        user_id=user.user_id,
        email=user.email,
        contact_id=None,
        account_id=None,
        candidate_contact_ids=("contact-1", "contact-2"),
        candidate_account_ids=(ACME_LOGISTICS, "acct-2"),
    )
    none = IdentityResolution(
        state="none",
        user_id="usr_pure_selfserve",
        email="new-user@example.test",
        contact_id=None,
        account_id=None,
    )

    assert exactly_one.account_id == ACME_LOGISTICS
    assert ambiguous.account_id is None
    assert set(ambiguous.candidate_contact_ids) == {"contact-1", "contact-2"}
    assert none.account_id is None


def test_usage_signal_user_link_is_additive_to_existing_usage_signal_shape():
    link = ProductUserUsageLink(
        signal_id="sig-user-1",
        user_id="usr_selfserve_test",
        account_id=ACME_LOGISTICS,
        source_ref="posthog_fixture:event:1",
    )

    assert link.signal_id == "sig-user-1"
    assert link.user_id == "usr_selfserve_test"


def test_loops_and_amplemarket_fixture_adapters_record_but_never_execute():
    user = _product_user()
    loops = FixtureLifecycleEmailConnector().create_draft(
        user=user,
        content_id="ss-content-first-value-checklist",
        subject="Get to first value",
        body="Fixture body",
        idempotency_key="idem-1",
        created_at="2026-07-02T12:00:00Z",
    )
    amplemarket = FixtureSalesEngagementConnector().create_enrollment_draft(
        user=user,
        sequence_id="seq-self-serve-team-invite",
        content_id="ss-content-team-invite-playbook",
        step_metadata=(("step_1", "content_route"),),
        idempotency_key="idem-2",
        created_at="2026-07-03T12:00:00Z",
    )

    assert loops.send_performed is False
    assert amplemarket.enrollment_performed is False
    assert amplemarket.step_metadata == (("step_1", "content_route"),)


def test_self_serve_catalog_extends_existing_content_matcher_shape():
    entries = load_tenant_content_catalog("self_serve_activation")

    assert {entry.content_id for entry in entries} >= {
        "ss-content-first-value-checklist",
        "ss-content-team-invite-playbook",
    }
    assert {entry.addresses_gap for entry in entries} >= {"aha_pending", "solo_usage_stall"}


def test_self_serve_blind_label_candidates_validate_with_no_owner_labels():
    rows = load_self_serve_nudge_candidates()

    assert len(rows) == 12
    assert all(row.owner_label is None for row in rows)
    assert {row.identity_state for row in rows} == {"exactly_one", "ambiguous", "none"}
    assert {row.candidate_action.channel for row in rows if row.candidate_action.channel} == {
        "lifecycle_email",
        "sales_engagement",
    }
    assert any(row.candidate_action.motion == "none" for row in rows)


def test_self_serve_candidates_reject_premature_owner_labels(tmp_path):
    source = Path("eval/gold/self_serve_nudge_candidates.json")
    rows = json.loads(source.read_text(encoding="utf-8"))
    rows[0]["owner_label"] = {"mode": "nudge"}
    path = tmp_path / "candidates.json"
    path.write_text(json.dumps(rows), encoding="utf-8")

    with pytest.raises(SelfServeNudgeGoldError, match="owner_label values must stay null"):
        load_self_serve_nudge_candidates(path)


def test_gong_fixture_is_contract_only_and_rejected_from_slot_b_domain():
    transcripts = FixtureCallIntelligenceConnector().list_transcripts(ACME_LOGISTICS)

    assert len(transcripts) == 2
    assert {row.provider for row in transcripts} == {"gong"}
    with pytest.raises(TranscriptDomainError, match="out_of_validated_domain"):
        assert_transcript_out_of_slot_b_domain(transcripts[0])
