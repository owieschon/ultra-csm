"""Tests for the reconciliation agent (Harvest 31 / report 52)."""

from __future__ import annotations

import json

import pytest

from ultra_csm.data_plane import CustomerDataPlane
from ultra_csm.data_plane.fixtures import (
    FixtureCRMDataConnector,
    FixtureCSPlatformConnector,
    FixtureProductTelemetryConnector,
    account_id_for,
)
from ultra_csm.data_plane.synthetic_book import build_synthetic_book
from ultra_csm.reconciliation_agent import (
    CANDIDATE_DISCLAIMER,
    EXPLANATION_DISCLAIMER,
    MAX_CANDIDATE_DIVERGENCES,
    CandidateDivergence,
    FixtureReconciliationWriter,
    ReconciliationContractError,
    _parse_and_validate,
    _raw_evidence_pool,
    explain,
    gather_signals,
)

PINNACLE_SUPPLY = account_id_for("pinnacle-supply")
AS_OF = "2026-06-25"


def _data_plane() -> CustomerDataPlane:
    book = build_synthetic_book()
    return CustomerDataPlane(
        crm=FixtureCRMDataConnector(data=book),
        cs=FixtureCSPlatformConnector(data=book),
        telemetry=FixtureProductTelemetryConnector(data=book),
    )


def test_tier1_gathering_fidelity_matches_known_factors():
    """pinnacle-supply's known fired factors (report 32's champion/
    concentration arcs) must all appear, unchanged values -- verified
    against the account's real divergences/lens factors, not guessed."""

    signals = gather_signals(_data_plane(), PINNACLE_SUPPLY, as_of=AS_OF)
    assert signals is not None
    by_name = {s.name: s for s in signals}

    assert "single_threaded_risk" in by_name
    assert by_name["single_threaded_risk"].value == 1.0
    assert by_name["single_threaded_risk"].contribution == 20
    assert by_name["single_threaded_risk"].origin == "deterministic"

    assert "usage_concentration" in by_name
    assert by_name["usage_concentration"].value == 1.0
    assert by_name["usage_concentration"].contribution == 20

    assert "arr_risk_exposure" in by_name
    assert "expansion_readiness_high_adoption" in by_name
    assert "arr_expansion_surface" in by_name


def test_tier1_gathering_dedupes_across_lenses():
    """single_threaded_risk/usage_concentration are surfaced by BOTH
    value_model.divergences AND the risk lens (lens_risk.py splices
    model.divergences into its own factor list verbatim) -- gather_
    signals must not return the same fact twice."""

    signals = gather_signals(_data_plane(), PINNACLE_SUPPLY, as_of=AS_OF)
    assert signals is not None
    names = [s.name for s in signals]
    assert len(names) == len(set(names)), f"duplicate signal names: {names}"

    by_name = {s.name: s for s in signals}
    assert set(by_name["single_threaded_risk"].surfaced_by_lenses) == {
        "value_model",
        "risk_lens",
    }
    assert set(by_name["usage_concentration"].surfaced_by_lenses) == {
        "value_model",
        "risk_lens",
    }
    # expansion-only factor: surfaced by exactly one lens.
    assert by_name["arr_expansion_surface"].surfaced_by_lenses == ("expansion_lens",)


def test_tier1_signals_carry_no_disclaimer_field():
    """Deterministic signals are not non-deterministic output -- a
    disclaimer field here would blur the exact Tier-1/Tier-2 distinction
    this dispatch exists to make (Decisions)."""

    signals = gather_signals(_data_plane(), PINNACLE_SUPPLY, as_of=AS_OF)
    assert signals is not None
    for signal in signals:
        assert not hasattr(signal, "disclaimer")


def test_gather_signals_returns_none_for_missing_account():
    signals = gather_signals(_data_plane(), "not-a-real-account-id", as_of=AS_OF)
    assert signals is None


def _fields(obj) -> set[str]:
    import dataclasses
    return {f.name for f in dataclasses.fields(obj)}


def test_candidate_divergence_has_no_score_shaped_field():
    """Structural safety boundary: a candidate divergence must be
    impossible to mistake for a ValueFactor -- no contribution/value
    field exists on the dataclass at all (not merely unset)."""

    assert "contribution" not in _fields(CandidateDivergence)
    assert "value" not in _fields(CandidateDivergence)
    assert _fields(CandidateDivergence) == {"origin", "claim", "confidence", "evidence", "disclaimer"}


def test_candidate_divergence_cap_enforced_in_code():
    """A response naming more than MAX_CANDIDATE_DIVERGENCES candidates is
    truncated in code, not merely relying on the prompt instruction."""

    raw_evidence = _raw_evidence_pool(_data_plane(), PINNACLE_SUPPLY, as_of=AS_OF)
    over_cap = [
        {"claim": f"claim {i}", "confidence": "low", "evidence": []}
        for i in range(MAX_CANDIDATE_DIVERGENCES + 5)
    ]
    text = json.dumps({"explanation": "x" * 10, "candidate_divergences": over_cap})
    _explanation, candidates = _parse_and_validate(text, raw_evidence=raw_evidence)
    assert len(candidates) == MAX_CANDIDATE_DIVERGENCES


def test_candidate_divergence_rejects_fabricated_evidence():
    """A candidate citing a source_id not present in raw_evidence is
    rejected -- never a fabricated evidence reference."""

    raw_evidence = _raw_evidence_pool(_data_plane(), PINNACLE_SUPPLY, as_of=AS_OF)
    text = json.dumps({
        "explanation": "x" * 10,
        "candidate_divergences": [{
            "claim": "a claim",
            "confidence": "low",
            "evidence": [{"source_id": "not-a-real-evidence-id"}],
        }],
    })
    with pytest.raises(ReconciliationContractError):
        _parse_and_validate(text, raw_evidence=raw_evidence)


def test_candidate_divergence_rejects_high_confidence():
    """confidence must be low/medium -- an unverified LLM hypothesis may
    never claim high confidence (Decisions)."""

    raw_evidence = _raw_evidence_pool(_data_plane(), PINNACLE_SUPPLY, as_of=AS_OF)
    text = json.dumps({
        "explanation": "x" * 10,
        "candidate_divergences": [{"claim": "a claim", "confidence": "high", "evidence": []}],
    })
    with pytest.raises(ReconciliationContractError):
        _parse_and_validate(text, raw_evidence=raw_evidence)


def test_explain_end_to_end_with_fixture_writer_carries_disclaimers():
    """Every non-deterministic field carries its own disclaimer; Tier-1
    signals carry none; a fixture-mode candidate divergence (never
    reaching the score/proposal path) round-trips correctly."""

    raw_evidence = _raw_evidence_pool(_data_plane(), PINNACLE_SUPPLY, as_of=AS_OF)
    fixture_candidate = CandidateDivergence(
        origin="llm_hypothesis",
        claim="a fixture hypothesis",
        confidence="low",
        evidence=(raw_evidence[0],) if raw_evidence else (),
        disclaimer=CANDIDATE_DISCLAIMER,
    )
    writer = FixtureReconciliationWriter(
        explanation_text="Fixture explanation citing the deterministic signals.",
        candidates=(fixture_candidate,),
    )
    result = explain(_data_plane(), PINNACLE_SUPPLY, as_of=AS_OF, writer=writer)

    assert result is not None
    assert result.explanation.disclaimer == EXPLANATION_DISCLAIMER
    assert len(result.candidate_divergences) == 1
    assert result.candidate_divergences[0].origin == "llm_hypothesis"
    assert result.candidate_divergences[0].disclaimer == CANDIDATE_DISCLAIMER
    for signal in result.deterministic_signals:
        assert not hasattr(signal, "disclaimer")
