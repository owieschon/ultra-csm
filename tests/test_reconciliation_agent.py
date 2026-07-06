"""Tests for the reconciliation agent (Harvest 31 / report 52)."""

from __future__ import annotations

from ultra_csm.data_plane import CustomerDataPlane
from ultra_csm.data_plane.fixtures import (
    FixtureCRMDataConnector,
    FixtureCSPlatformConnector,
    FixtureProductTelemetryConnector,
    account_id_for,
)
from ultra_csm.data_plane.synthetic_book import build_synthetic_book
from ultra_csm.reconciliation_agent import gather_signals

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
