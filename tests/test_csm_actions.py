"""CSM action taxonomy for Agent 1 proposals."""

from __future__ import annotations

import pytest

from ultra_csm.governance import (
    CSM_ACTION_SPECS,
    UnknownCSMActionError,
    csm_action_spec,
    proposal_fields_for,
)


def test_agent_one_actions_have_defined_gate_fields():
    assert proposal_fields_for("recommend_next_best_action") == {
        "action": "recommend_next_best_action",
        "autonomy_tier": 1,
        "required_permission": "csm.recommend",
    }
    assert proposal_fields_for("draft_customer_outreach") == {
        "action": "draft_customer_outreach",
        "autonomy_tier": 2,
        "required_permission": "customer.outreach.draft",
    }
    assert proposal_fields_for("initiate_customer_call") == {
        "action": "initiate_customer_call",
        "autonomy_tier": 3,
        "required_permission": "customer.call.initiate",
    }


def test_customer_affecting_actions_require_human_release():
    for spec in CSM_ACTION_SPECS.values():
        if not spec.customer_affecting:
            assert spec.release_condition == "auto_internal_only"
            continue
        assert spec.autonomy_tier in {2, 3}
        assert spec.release_condition in {
            "human_approve",
            "human_approve_with_consent",
            "human_approve_with_dual_control",
        }


def test_outbound_and_call_actions_have_stricter_release_conditions():
    outreach = csm_action_spec("draft_customer_outreach")
    assert outreach.release_condition == "human_approve_with_consent"
    assert outreach.required_permission == "customer.outreach.draft"

    call = csm_action_spec("initiate_customer_call")
    assert call.autonomy_tier == 3
    assert call.release_condition == "human_approve_with_dual_control"


def test_unknown_csm_action_fails_closed():
    with pytest.raises(UnknownCSMActionError):
        csm_action_spec("confirm_order")
    with pytest.raises(UnknownCSMActionError):
        proposal_fields_for("send_email")


def test_scale_motion_actions_have_defined_gate_fields():
    """Test parity for the Universe v2 scale-motion action types
    (campaign_enroll/content_route/cohort_action) with the pre-existing six."""

    assert proposal_fields_for("campaign_enroll") == {
        "action": "campaign_enroll",
        "autonomy_tier": 2,
        "required_permission": "campaign.enroll",
    }
    assert proposal_fields_for("content_route") == {
        "action": "content_route",
        "autonomy_tier": 2,
        "required_permission": "content.route",
    }
    assert proposal_fields_for("cohort_action") == {
        "action": "cohort_action",
        "autonomy_tier": 3,
        "required_permission": "cohort.action.initiate",
    }


def test_cohort_action_has_strictest_release_condition():
    cohort_action = csm_action_spec("cohort_action")
    assert cohort_action.autonomy_tier == 3
    assert cohort_action.release_condition == "human_approve_with_dual_control"


def test_csm_action_specs_has_nine_actions():
    assert len(CSM_ACTION_SPECS) == 9
