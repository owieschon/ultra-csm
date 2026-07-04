"""CSM action taxonomy for Agent 1 proposals.

This is the Phase-1 contract Agent 1 must target before it can emit any
customer-affecting proposal. It is intentionally pure: no database dependency,
no live connector import, and no LLM judgment. The action gate can already carry
the returned `action`, `autonomy_tier`, and `required_permission` fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


CSMActionName = Literal[
    "recommend_next_best_action",
    "draft_customer_outreach",
    "log_crm_activity",
    "update_cs_platform_record",
    "edit_success_plan",
    "initiate_customer_call",
    "campaign_enroll",
    "content_route",
    "cohort_action",
]
CSMActionType = CSMActionName

ReleaseCondition = Literal[
    "auto_internal_only",
    "human_approve",
    "human_approve_with_consent",
    "human_approve_with_dual_control",
]


class UnknownCSMActionError(ValueError):
    """Raised when Agent 1 tries to propose an undefined CSM action."""


@dataclass(frozen=True)
class CSMActionSpec:
    action: CSMActionName
    autonomy_tier: int
    required_permission: str
    release_condition: ReleaseCondition
    customer_affecting: bool
    description: str


CSM_ACTION_SPECS: dict[CSMActionName, CSMActionSpec] = {
    "recommend_next_best_action": CSMActionSpec(
        action="recommend_next_best_action",
        autonomy_tier=1,
        required_permission="csm.recommend",
        release_condition="auto_internal_only",
        customer_affecting=False,
        description="Internal CSM recommendation grounded in data-plane evidence.",
    ),
    "draft_customer_outreach": CSMActionSpec(
        action="draft_customer_outreach",
        autonomy_tier=2,
        required_permission="customer.outreach.draft",
        release_condition="human_approve_with_consent",
        customer_affecting=True,
        description="Customer-facing email/text draft; never sent without approval.",
    ),
    "log_crm_activity": CSMActionSpec(
        action="log_crm_activity",
        autonomy_tier=2,
        required_permission="crm.activity.write",
        release_condition="human_approve",
        customer_affecting=True,
        description="Salesforce activity write-back through the CRM connector.",
    ),
    "update_cs_platform_record": CSMActionSpec(
        action="update_cs_platform_record",
        autonomy_tier=2,
        required_permission="cs_platform.record.write",
        release_condition="human_approve",
        customer_affecting=True,
        description="Gainsight-style customer-success record update.",
    ),
    "edit_success_plan": CSMActionSpec(
        action="edit_success_plan",
        autonomy_tier=2,
        required_permission="cs_platform.success_plan.write",
        release_condition="human_approve",
        customer_affecting=True,
        description="Success-plan objective/status edit proposal.",
    ),
    "initiate_customer_call": CSMActionSpec(
        action="initiate_customer_call",
        autonomy_tier=3,
        required_permission="customer.call.initiate",
        release_condition="human_approve_with_dual_control",
        customer_affecting=True,
        description="Customer call initiation proposal; strictest tier.",
    ),
    "campaign_enroll": CSMActionSpec(
        action="campaign_enroll",
        autonomy_tier=2,
        required_permission="campaign.enroll",
        release_condition="human_approve",
        customer_affecting=True,
        description=(
            "Enroll an account/contact into a pre-approved lifecycle or nurture "
            "campaign; the campaign's own approved content is what reaches the "
            "customer, not CSM-authored prose."
        ),
    ),
    "content_route": CSMActionSpec(
        action="content_route",
        autonomy_tier=2,
        required_permission="content.route",
        release_condition="human_approve",
        customer_affecting=True,
        description=(
            "Route a pre-approved content-catalog asset (help doc, in-app tip, "
            "template) to a customer contact; only the routing decision is proposed."
        ),
    ),
    "cohort_action": CSMActionSpec(
        action="cohort_action",
        autonomy_tier=3,
        required_permission="cohort.action.initiate",
        release_condition="human_approve_with_dual_control",
        customer_affecting=True,
        description=(
            "Apply one motion across a defined account cohort/segment at scale; "
            "highest blast radius of any CSM action, strictest release tier."
        ),
    ),
}


# The playbook motion a CSMActionType implies, for the tier-forbidden-
# motion guard only (docs/UNIVERSE_V2_CONVENTIONS.md ยง2's full motion ->
# action-type table, narrowed to the two customer-contact-gated action
# types the guard needs). recommend_next_best_action has no forbidden-
# motion implication -- it is never customer-facing, so it is
# deliberately absent here, not an oversight.
ACTION_IMPLIED_MOTION: dict[CSMActionName, str] = {
    "draft_customer_outreach": "personal_email",
    "initiate_customer_call": "working_session",
}


def implied_motion_for_action(action: str) -> str | None:
    """The playbook motion *action* implies, or None if that action type
    has no forbidden-motion implication (e.g. it is not customer-facing)."""

    return ACTION_IMPLIED_MOTION.get(action)  # type: ignore[arg-type]


def csm_action_spec(action: str) -> CSMActionSpec:
    try:
        return CSM_ACTION_SPECS[action]  # type: ignore[index]
    except KeyError as exc:
        raise UnknownCSMActionError(f"undefined CSM action: {action}") from exc


def proposal_fields_for(action: str) -> dict[str, str | int]:
    """Return the ActionGate fields Agent 1 should use for a CSM action."""

    spec = csm_action_spec(action)
    return {
        "action": spec.action,
        "autonomy_tier": spec.autonomy_tier,
        "required_permission": spec.required_permission,
    }
