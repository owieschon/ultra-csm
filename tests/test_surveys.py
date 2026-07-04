"""Quarterly NPS survey exhaust (Universe v2, WS-Data-Classes Phase 4)."""

from __future__ import annotations

from ultra_csm.data_plane.fixtures import account_id_for
from ultra_csm.data_plane.surveys import (
    QUARRYSTONE_ACCOUNT_ID,
    SURVEY_WAVES,
    response_rate_by_account,
    survey_responses_as_of,
)


def test_survey_waves_are_45_135_225_315():
    assert SURVEY_WAVES == (45, 135, 225, 315)


def test_pinehill_day45_is_a_detractor_citing_dispatch_integration():
    pinehill = account_id_for("pinehill-transport")
    responses = survey_responses_as_of(pinehill, 45)
    assert len(responses) == 1
    assert responses[0].score <= 6.0  # detractor range
    assert "dispatch integration" in responses[0].comment.lower()


def test_pinehill_recovers_by_day_315():
    pinehill = account_id_for("pinehill-transport")
    responses = survey_responses_as_of(pinehill, 315)
    assert len(responses) == 4
    assert responses[0].score < responses[-1].score
    assert responses[-1].score >= 8.0


def test_quarrystone_never_responds():
    responses = survey_responses_as_of(QUARRYSTONE_ACCOUNT_ID, 315)
    assert responses == []


def test_quarrystone_response_rate_is_zero():
    rates = response_rate_by_account(315)
    assert rates[QUARRYSTONE_ACCOUNT_ID] == 0.0


def test_trailhead_is_a_promoter_at_every_wave():
    trailhead = account_id_for("trailhead-logistics")
    responses = survey_responses_as_of(trailhead, 315)
    assert len(responses) == 4
    assert all(r.score >= 9.0 for r in responses)


def test_herrings_are_mid_range_and_benign():
    cedar_valley = account_id_for("cedar-valley")
    ironridge = account_id_for("ironridge-fleet")
    for account_id in (cedar_valley, ironridge):
        responses = survey_responses_as_of(account_id, 315)
        assert len(responses) == 4
        assert all(6.0 <= r.score <= 8.5 for r in responses)


def test_no_response_before_its_wave_day():
    pinehill = account_id_for("pinehill-transport")
    assert survey_responses_as_of(pinehill, 44) == []
    assert len(survey_responses_as_of(pinehill, 45)) == 1


def test_deterministic_across_two_calls():
    pinehill = account_id_for("pinehill-transport")
    first = survey_responses_as_of(pinehill, 315)
    second = survey_responses_as_of(pinehill, 315)
    assert first == second
