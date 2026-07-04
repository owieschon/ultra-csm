"""Job-change signal class (Universe v2, WS-Data-Classes Phase 6)."""

from __future__ import annotations

from ultra_csm.data_plane.pinnacle_comms import DEREK_CONTACT_ID, PINNACLE_ACCOUNT_ID
from ultra_csm.data_plane.relationship_signals import (
    DEREK_VAUGHN_DEPARTURE,
    MIKE_LINDGREN_PROMOTION,
    SIGNALS,
    TRAILHEAD_ACCOUNT_ID,
    job_change_signals_as_of,
)


def test_two_signals_authored():
    assert len(SIGNALS) == 2


def test_derek_vaughn_departure_is_a_pinnacle_signal_at_day_5():
    assert DEREK_VAUGHN_DEPARTURE.account_id == PINNACLE_ACCOUNT_ID
    assert DEREK_VAUGHN_DEPARTURE.contact_id == DEREK_CONTACT_ID
    assert DEREK_VAUGHN_DEPARTURE.change_type == "departure"
    assert DEREK_VAUGHN_DEPARTURE.day_offset == 5


def test_derek_vaughn_departure_precedes_the_health_band_move_at_day_14():
    # The bible's HealthBandChange for pinnacle-supply fires day 14; this
    # signal is the enrichment feed that would beat it to the punch.
    assert DEREK_VAUGHN_DEPARTURE.day_offset < 14


def test_mike_lindgren_promotion_is_benign_and_same_company():
    assert MIKE_LINDGREN_PROMOTION.account_id == TRAILHEAD_ACCOUNT_ID
    assert MIKE_LINDGREN_PROMOTION.change_type == "promotion"
    assert MIKE_LINDGREN_PROMOTION.same_company is True
    assert MIKE_LINDGREN_PROMOTION.new_title is not None


def test_reader_respects_as_of_day():
    assert job_change_signals_as_of(PINNACLE_ACCOUNT_ID, 4) == []
    assert job_change_signals_as_of(PINNACLE_ACCOUNT_ID, 5) == [DEREK_VAUGHN_DEPARTURE]
    assert job_change_signals_as_of(TRAILHEAD_ACCOUNT_ID, 199) == []
    assert job_change_signals_as_of(TRAILHEAD_ACCOUNT_ID, 200) == [MIKE_LINDGREN_PROMOTION]


def test_departure_has_no_new_title():
    assert DEREK_VAUGHN_DEPARTURE.new_title is None
