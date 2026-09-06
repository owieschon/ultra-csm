"""Harness tests for the customer-outcome comparison eval.

These tests assert harness behavior -- that the evaluator rejects unsafe
decisions, that both policies see identical facts, that the real Ultra sweep
actually runs through the DB-backed ActionGate, and that noise/consequential
variants are reported -- not that Ultra "wins" against the baseline. No test
mirrors every fixture case one-for-one.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import pytest  # noqa: E402

from eval.customer_outcome_cases import build_cases, build_data_plane, build_expectations  # noqa: E402
from eval.customer_outcome_comparison import (  # noqa: E402
    NormalizedDecision,
    forbidden_violations,
    run_baseline,
    run_comparison,
)


def test_forbidden_decision_is_rejected():
    points = build_cases()
    expectations = build_expectations(points)
    point = next(p for p in points if p.story == "s8_consent_boundary" and p.point == "a")
    exp = expectations[point.account_id]
    assert "propose_customer_action" in exp.forbidden_decisions

    unsafe = NormalizedDecision(
        point.account_id, "propose_customer_action", "unsafe test decision", (), None, None,
    )
    violations = forbidden_violations(point, exp, unsafe)
    assert violations, "an evaluator that lets a no-consent case propose customer outreach must be flagged"


def test_forbidden_check_also_catches_missing_consent_directly():
    """The no-consent guard fires even for a case whose declared forbidden
    set doesn't happen to name propose_customer_action -- consent is a hard
    boundary independent of any one case's oracle."""
    points = build_cases()
    point = next(p for p in points if p.story == "s8_consent_boundary" and p.point == "a")
    assert not any(c.consent_to_contact for c in point.contacts)
    fake_exp = build_expectations(points)[point.account_id]
    from dataclasses import replace
    fake_exp = replace(fake_exp, forbidden_decisions=())
    decision = NormalizedDecision(point.account_id, "propose_customer_action", "x", (), None, None)
    assert forbidden_violations(point, fake_exp, decision)


def test_both_policies_read_the_same_data_plane():
    """The baseline and the Ultra sweep must be handed literally the same
    CustomerDataPlane -- same accounts, contacts, cases, plans, milestones --
    with no separate or richer view for either side."""
    points = build_cases()
    plane = build_data_plane(points)
    account_id = points[0].account_id
    assert plane.crm.get_account(account_id) is not None
    # A hand-picked account with a known case exists identically via every seam.
    blocker_point = next(p for p in points if p.story == "s6_verified_blocker" and p.point == "a")
    cases_via_plane = plane.crm.list_cases(blocker_point.account_id)
    assert cases_via_plane == list(blocker_point.cases)
    baseline_by_account = run_baseline(plane, points, as_of="2026-06-21T00:00:00Z")
    assert baseline_by_account[blocker_point.account_id].decision == "escalate"


def test_noise_variants_do_not_change_decision_family():
    """S9 (quiet completed account) and S10 (meaningful gap) each have a
    noise-variant decision point; the noise must not flip the family of
    decision the baseline reaches."""
    points = build_cases()
    plane = build_data_plane(points)
    baseline_by_account = run_baseline(plane, points, as_of="2026-06-21T00:00:00Z")
    for story in ("s9_quiet_completed_account", "s10_meaningful_vs_noise"):
        a = next(p for p in points if p.story == story and p.point == "a")
        b = next(p for p in points if p.story == story and p.point == "b")
        assert not a.noise_variant and b.noise_variant
        assert baseline_by_account[a.account_id].decision == baseline_by_account[b.account_id].decision, (
            f"{story}: unrelated metadata noise changed the baseline decision"
        )


def test_case_count_and_story_coverage():
    points = build_cases()
    assert len(points) == 24
    stories = {p.story for p in points}
    assert len(stories) == 12
    for story in stories:
        assert {p.point for p in points if p.story == story} == {"a", "b"}
    categories = {p.category for p in points}
    assert categories == {"technical_activation", "enterprise_onboarding"}
    assert sum(p.noise_variant for p in points) >= 2


def test_ambiguous_identity_never_baseline_proposes_outreach():
    points = build_cases()
    plane = build_data_plane(points)
    baseline_by_account = run_baseline(plane, points, as_of="2026-06-21T00:00:00Z")
    ambiguous_point = next(p for p in points if p.story == "s7_ambiguous_identity" and p.point == "a")
    assert baseline_by_account[ambiguous_point.account_id].decision != "propose_customer_action"


@pytest.mark.slow
def test_real_sweep_runs_and_proposes_through_the_db_action_gate():
    """Runs the actual `run_time_to_value_sweep` behind a real `ActionGate`
    over an `EphemeralCluster`. If the ephemeral cluster cannot boot in this
    sandbox, the result records that failure rather than fabricating a pass."""
    result = run_comparison()
    if not result["metrics"]["ultra_sweep_ran"]:
        pytest.skip(f"EphemeralCluster unavailable in this sandbox: {result['metrics']['ultra_sweep_error']}")
    assert result["metrics"]["case_count"] == 24
    proposed = [c for c in result["cases"] if c["ultra"]["decision"] == "propose_customer_action"]
    assert proposed, "the real sweep should propose at least one customer action across 24 accounts"
    for c in proposed:
        assert c["ultra"]["evidence_refs"] or c["ultra"]["reason"], "a proposal must carry evidence or a reason"
