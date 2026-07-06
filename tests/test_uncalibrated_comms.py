"""Four routine-check-in comms fixtures (docs/SYNTHETIC_UNIVERSE_BIBLE.md's
"Routine health check-ins" section, dispatch 28 / Harvest 17): cobalt-fleet-ops,
northbend-haulage, cedarfield-industrial-supply, elmwood-trucking. Each is
verified deterministic, day-offset gated, and free of any invented claim
beyond the single real ``health_yellow`` factor each account actually carries.
"""

from __future__ import annotations

from ultra_csm.data_plane.cedarfield_comms import (
    ALEX_CONTACT_ID,
    CEDARFIELD_ACCOUNT_ID,
    cedarfield_communication_signals,
)
from ultra_csm.data_plane.cobalt_comms import (
    COBALT_ACCOUNT_ID,
    SAM_CONTACT_ID as COBALT_SAM_CONTACT_ID,
    cobalt_communication_signals,
)
from ultra_csm.data_plane.elmwood_comms import (
    ELMWOOD_ACCOUNT_ID,
    SAM_CONTACT_ID as ELMWOOD_SAM_CONTACT_ID,
    elmwood_communication_signals,
)
from ultra_csm.data_plane.fixtures import account_id_for
from ultra_csm.data_plane.northbend_comms import (
    JORDAN_CONTACT_ID,
    NORTHBEND_ACCOUNT_ID,
    northbend_communication_signals,
)


def test_account_ids_match_synthetic_book_slugs():
    assert COBALT_ACCOUNT_ID == account_id_for("cobalt-fleet-ops")
    assert NORTHBEND_ACCOUNT_ID == account_id_for("northbend-haulage")
    assert CEDARFIELD_ACCOUNT_ID == account_id_for("cedarfield-industrial-supply")
    assert ELMWOOD_ACCOUNT_ID == account_id_for("elmwood-trucking")


def test_no_signals_before_first_scheduled_message():
    assert cobalt_communication_signals(0) == []
    assert northbend_communication_signals(0) == []
    assert cedarfield_communication_signals(0) == []
    assert elmwood_communication_signals(0) == []


def test_cobalt_three_messages_by_day_140():
    signals = cobalt_communication_signals(140)
    assert len(signals) == 3
    assert all(s.account_id == COBALT_ACCOUNT_ID for s in signals)
    assert all(s.contact_id == COBALT_SAM_CONTACT_ID for s in signals)
    assert signals[0].direction == "outbound"
    assert signals[1].direction == "inbound"
    assert signals[1].response_time_hours is not None


def test_northbend_two_messages_by_day_140():
    signals = northbend_communication_signals(140)
    assert len(signals) == 2
    assert all(s.account_id == NORTHBEND_ACCOUNT_ID for s in signals)
    assert all(s.contact_id == JORDAN_CONTACT_ID for s in signals)


def test_cedarfield_three_messages_by_day_140():
    signals = cedarfield_communication_signals(140)
    assert len(signals) == 3
    assert all(s.account_id == CEDARFIELD_ACCOUNT_ID for s in signals)
    assert all(s.contact_id == ALEX_CONTACT_ID for s in signals)


def test_elmwood_two_messages_by_day_140():
    signals = elmwood_communication_signals(140)
    assert len(signals) == 2
    assert all(s.account_id == ELMWOOD_ACCOUNT_ID for s in signals)
    assert all(s.contact_id == ELMWOOD_SAM_CONTACT_ID for s in signals)


def test_reader_respects_as_of_day():
    # Northbend's second message is scheduled day 59; day 58 sees only the
    # first (outbound) message, matching the day-offset gating every
    # existing *_comms.py module follows.
    assert len(northbend_communication_signals(58)) == 1
    assert len(northbend_communication_signals(59)) == 2
