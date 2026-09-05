"""Absent outcome-completion evidence must not become an asserted onboarding
failure or activation blocker in a customer action.

Reproduces the Trailhead Logistics day-140 case: usage_outcome_unverified
(unresolved success-plan objective + high usage, no completion evidence)
must not be phrased as "onboarding risk" / "activation blockers"."""

from __future__ import annotations

from dataclasses import replace

import pytest

from ultra_csm.agent1.sweep import Priority, _slot_b_request
from ultra_csm.agent1.slot_b import (
    FixtureReasonDraftWriter,
    SlotBContractError,
    UnsafeReasonDraftWriter,
    validate_reason_draft_output,
)
from ultra_csm.data_plane.contracts import CRMAccount, CRMContact
from ultra_csm.data_plane.contracts import EvidenceRef
from ultra_csm.value_model import ValueFactor

AS_OF = "2026-11-08"


def _account() -> CRMAccount:
    return CRMAccount(
        account_id="21830db9-7182-5d97-b22e-d57c4e28f696",
        name="Trailhead Logistics",
        owner_id="csm-101",
        industry="logistics",
    )


def _contact() -> CRMContact:
    return CRMContact(
        contact_id="5ba7aa51-a5eb-5220-9d3b-71bbe67377a1",
        account_id="21830db9-7182-5d97-b22e-d57c4e28f696",
        name="Vanessa Torres",
        email="vanessa@trailhead.example",
        role="admin",
        title="VP Operations",
        consent_to_contact=True,
    )


def _factor(name: str, contribution: int, *, evidence: tuple[EvidenceRef, ...] = ()) -> ValueFactor:
    return ValueFactor(
        name=name,
        value=1.0,
        contribution=contribution,
        evidence=evidence or (EvidenceRef("cs_platform", "plan-1", "objectives", AS_OF),),
        config_version="value-model-config-v1",
        rule_name="high_arr_review_default",
        threshold_name="t",
        threshold_value=1.0,
    )


def _request(factors, *, contact=None):
    priority = Priority(score=sum(f.contribution for f in factors), factors=tuple(factors))
    evidence = tuple({e for f in factors for e in f.evidence})
    return _slot_b_request(
        tenant_id="ultra-demo",
        account=_account(),
        disposition="propose_customer_action",
        action="draft_customer_outreach",
        customer_contact_allowed=True,
        evidence=evidence,
        priority=priority,
        as_of=AS_OF,
        contact=contact if contact is not None else _contact(),
        cases=(),
    )


TRAILHEAD_FACTORS = (
    _factor("success_plan_overdue", 20),
    _factor("arr_tier", 5),
    _factor("single_threaded_risk", 20),
    _factor("usage_outcome_unverified", 18),
)


def test_trailhead_factor_contract_preserves_uncertainty():
    request = _request(TRAILHEAD_FACTORS)
    assert request.decision_purpose == "outcome_verification"

    output = FixtureReasonDraftWriter().write(request)

    lowered = f"{output.reason}\n{output.customer_draft}".lower()
    assert "onboarding risk" not in lowered
    assert "activation blocker" not in lowered
    assert "churn" not in lowered
    assert any(marker in output.customer_draft.lower() for marker in ("confirm", "verify"))
    # Every contributing factor -- including the 4th -- must be visible in
    # the internal reason, not silently dropped.
    for factor in TRAILHEAD_FACTORS:
        assert factor.name in output.reason


def test_reordered_equivalent_evidence_still_verification():
    reordered = tuple(reversed(TRAILHEAD_FACTORS))
    request = _request(reordered)
    assert request.decision_purpose == "outcome_verification"
    output = FixtureReasonDraftWriter().write(request)
    assert "activation blocker" not in output.customer_draft.lower()


def test_confirmed_blocker_positive_control_keeps_standard_wording():
    """The existing classified-case factor retains its response path."""

    factors = TRAILHEAD_FACTORS + (_factor("slot_a_case_blocker", 15),)
    request = _request(factors)
    assert request.decision_purpose == "standard"
    output = FixtureReasonDraftWriter().write(request)
    assert "activation blocker" in output.customer_draft.lower()


def test_non_verification_case_unaffected():
    factors = (
        _factor("success_plan_overdue", 20),
        _factor("health_yellow", 10),
    )
    request = _request(factors)
    assert request.decision_purpose == "standard"
    output = FixtureReasonDraftWriter().write(request)
    assert "activation blocker" in output.customer_draft.lower()


def test_live_writer_inappropriate_diagnosis_is_rejected_for_verification_purpose():
    request = _request(TRAILHEAD_FACTORS)
    bad_output = FixtureReasonDraftWriter().write(request)
    tampered = bad_output.__class__(
        reason=bad_output.reason,
        cited_evidence_ids=bad_output.cited_evidence_ids,
        customer_draft="Hi there, this account has an onboarding risk and activation blockers.",
        model_id=bad_output.model_id,
        prompt_version=bad_output.prompt_version,
    )
    try:
        validate_reason_draft_output(request, tampered)
        raised = False
    except SlotBContractError:
        raised = True
    assert raised


def test_unsafe_writer_output_still_rejected_regardless_of_purpose():
    request = _request(TRAILHEAD_FACTORS)
    output = UnsafeReasonDraftWriter().write(request)
    try:
        validate_reason_draft_output(request, output)
        raised = False
    except SlotBContractError:
        raised = True
    assert raised


def test_contact_prohibition_and_consent_binding_preserved():
    factors = (_factor("usage_outcome_unverified", 18),)
    priority = Priority(score=sum(f.contribution for f in factors), factors=tuple(factors))
    evidence = tuple({e for f in factors for e in f.evidence})
    request = _slot_b_request(
        tenant_id="ultra-demo",
        account=_account(),
        disposition="internal_review",
        action="recommend_next_best_action",
        customer_contact_allowed=False,
        evidence=evidence,
        priority=priority,
        as_of=AS_OF,
        contact=None,
        cases=(),
    )
    output = FixtureReasonDraftWriter().write(request)
    assert output.customer_draft is None


@pytest.mark.parametrize("field,text", [
    ("customer_draft", "Hi Vanessa, your rollout is unsuccessful. Can you confirm how we can rescue it?"),
    ("customer_draft", "Hi Vanessa, your compliance reporting delivered the promised savings. Can you confirm a purchase?"),
    ("reason", "Your rollout is broken. Evidence [evidence:plan-1]."),
])
def test_paraphrased_assertions_cannot_cross_verification_contract(field, text):
    request = _request(TRAILHEAD_FACTORS)
    safe = FixtureReasonDraftWriter().write(request)
    with pytest.raises(SlotBContractError):
        validate_reason_draft_output(request, replace(safe, **{field: text}))


def test_configured_play_cannot_override_verification_purpose():
    request = _request(TRAILHEAD_FACTORS)
    hostile = replace(request, org_context={"gap_plays": [{
        "factor": "usage_outcome_unverified",
        "customer_ask": "confirm that the unsuccessful rollout requires recovery",
    }]})
    assert FixtureReasonDraftWriter().write(hostile) == FixtureReasonDraftWriter().write(request)
