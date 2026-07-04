"""Unit coverage for the additive rejection ledger (Universe v2 Wave 1,
WS-Week1-Harness). See docs/DECISION_LOG.md for the two-sentence mechanism
summary; see eval/week1_protocol.py for the feedback-persistence check that
consumes this ledger."""

from __future__ import annotations

import json

import pytest

from ultra_csm.rejection_ledger import RejectionLedger, top_factor_name


class _Factor:
    def __init__(self, name: str, contribution: int) -> None:
        self.name = name
        self.contribution = contribution


def test_reject_then_lookup_round_trips_in_memory():
    ledger = RejectionLedger()
    assert ledger.lookup(
        tenant_id="fleetops", account_id="acc-1", factor_name="reply_latency_trend", motion="escalation"
    ) is None

    record = ledger.reject(
        tenant_id="fleetops",
        account_id="acc-1",
        factor_name="reply_latency_trend",
        motion="escalation",
        reason="already being handled by CSM directly",
        rejected_on_day=3,
        proposal_id="prop-1",
    )
    assert record.key() == ("fleetops", "acc-1", "reply_latency_trend", "escalation")

    found = ledger.lookup(
        tenant_id="fleetops", account_id="acc-1", factor_name="reply_latency_trend", motion="escalation"
    )
    assert found is not None
    assert found.reason == "already being handled by CSM directly"
    assert found.rejected_on_day == 3


def test_lookup_is_scoped_to_exact_key():
    ledger = RejectionLedger()
    ledger.reject(
        tenant_id="fleetops", account_id="acc-1", factor_name="reply_latency_trend",
        motion="escalation", reason="r", rejected_on_day=3, proposal_id="prop-1",
    )
    # Different motion, different account, different factor -> no match.
    assert ledger.lookup(
        tenant_id="fleetops", account_id="acc-1", factor_name="reply_latency_trend", motion="personal_email"
    ) is None
    assert ledger.lookup(
        tenant_id="fleetops", account_id="acc-2", factor_name="reply_latency_trend", motion="escalation"
    ) is None
    assert ledger.lookup(
        tenant_id="fleetops", account_id="acc-1", factor_name="ticket_frequency_window", motion="escalation"
    ) is None


def test_persists_to_disk_and_reloads(tmp_path):
    path = tmp_path / "rejections.json"
    ledger = RejectionLedger(path)
    ledger.reject(
        tenant_id="fleetops", account_id="acc-1", factor_name="ticket_frequency_window",
        motion="escalation", reason="handled offline", rejected_on_day=7, proposal_id="prop-2",
    )
    assert path.exists()
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert len(on_disk["rejections"]) == 1

    reloaded = RejectionLedger(path)
    found = reloaded.lookup(
        tenant_id="fleetops", account_id="acc-1", factor_name="ticket_frequency_window", motion="escalation"
    )
    assert found is not None
    assert found.proposal_id == "prop-2"


def test_lookup_returns_most_recent_rejection_for_a_key():
    ledger = RejectionLedger()
    ledger.reject(
        tenant_id="fleetops", account_id="acc-1", factor_name="f", motion="escalation",
        reason="first reason", rejected_on_day=1, proposal_id="prop-a",
    )
    ledger.reject(
        tenant_id="fleetops", account_id="acc-1", factor_name="f", motion="escalation",
        reason="second reason", rejected_on_day=5, proposal_id="prop-b",
    )
    found = ledger.lookup(tenant_id="fleetops", account_id="acc-1", factor_name="f", motion="escalation")
    assert found is not None
    assert found.reason == "second reason"
    assert found.proposal_id == "prop-b"


@pytest.mark.parametrize(
    "factors,expected",
    [
        ((), None),
        ((_Factor("a", 3),), "a"),
        ((_Factor("a", 3), _Factor("b", 9), _Factor("c", 5)), "b"),
        # Tie on contribution -> deterministic tiebreak by name.
        ((_Factor("zeta", 5), _Factor("alpha", 5)), "alpha"),
    ],
)
def test_top_factor_name_picks_max_contribution_with_deterministic_tiebreak(factors, expected):
    assert top_factor_name(factors) == expected
