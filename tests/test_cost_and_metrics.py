"""Tests for cost tracking, budget enforcement, and the /metrics endpoint."""

from __future__ import annotations

import pytest

from ultra_csm.agent1.slot_b import (
    FixtureReasonDraftWriter,
    ReasonDraftOutput,
    ReasonDraftRequest,
    SLOT_B_PROMPT_VERSION,
)
from ultra_csm.api_metrics import APIMetrics, SweepTiming
from ultra_csm.cost_tracker import (
    CallRecord,
    CostBudget,
    CostTracker,
    compute_cost,
    estimate_call_cost,
)


# ---------------------------------------------------------------------------
# Unit: compute_cost
# ---------------------------------------------------------------------------


def test_compute_cost_opus():
    # claude-opus-4-8: $5/Mtok in, $25/Mtok out
    cost = compute_cost("claude-opus-4-8", 1_000_000, 1_000_000)
    assert cost == pytest.approx(30.0)


def test_compute_cost_known_tokens():
    # 100 input tokens, 25 output tokens for opus
    cost = compute_cost("claude-opus-4-8", 100, 25)
    expected = (100 * 5.0 + 25 * 25.0) / 1_000_000
    assert cost == pytest.approx(expected)


def test_compute_cost_fixture_is_zero():
    cost = compute_cost("fixture-agent1-slot-b-v1", 10000, 10000)
    assert cost == 0.0


def test_compute_cost_unknown_model_uses_default():
    # Unknown model should use the default (opus-like) pricing.
    cost = compute_cost("unknown-model-xyz", 1_000_000, 0)
    assert cost == pytest.approx(5.0)


def test_estimate_call_cost_opus():
    est = estimate_call_cost("claude-opus-4-8")
    # 2000 * 5 + 700 * 25 = 10000 + 17500 = 27500 per Mtok
    expected = 27500 / 1_000_000
    assert est == pytest.approx(expected)


def test_estimate_call_cost_fixture_is_zero():
    assert estimate_call_cost("fixture-agent1-slot-b-v1") == 0.0


# ---------------------------------------------------------------------------
# Unit: CostTracker
# ---------------------------------------------------------------------------


def test_cost_tracker_records_and_reports_stats():
    tracker = CostTracker()

    rec = tracker.record(
        model_id="claude-opus-4-8",
        input_tokens=100,
        output_tokens=25,
        latency_ms=500.0,
        account_id="acct-1",
    )

    assert isinstance(rec, CallRecord)
    assert rec.total_tokens == 125
    assert rec.cost_usd == pytest.approx(compute_cost("claude-opus-4-8", 100, 25))
    assert rec.latency_ms == 500.0
    assert rec.account_id == "acct-1"

    stats = tracker.stats()
    assert stats["total_calls"] == 1
    assert stats["total_tokens"] == 125
    assert stats["total_cost_usd"] == pytest.approx(rec.cost_usd, abs=1e-6)
    assert stats["avg_latency_ms"] == 500.0


def test_cost_tracker_accumulates_multiple_calls():
    tracker = CostTracker()

    tracker.record(
        model_id="claude-opus-4-8",
        input_tokens=100, output_tokens=25,
        latency_ms=500.0, account_id="acct-1",
    )
    tracker.record(
        model_id="claude-opus-4-8",
        input_tokens=200, output_tokens=50,
        latency_ms=1000.0, account_id="acct-2",
    )

    stats = tracker.stats()
    assert stats["total_calls"] == 2
    assert stats["total_tokens"] == 375  # (100+25) + (200+50)
    assert stats["avg_latency_ms"] == 750.0


def test_cost_tracker_cost_per_account():
    tracker = CostTracker()

    tracker.record(
        model_id="claude-opus-4-8",
        input_tokens=100, output_tokens=25,
        latency_ms=100.0, account_id="acct-1",
    )
    tracker.record(
        model_id="claude-opus-4-8",
        input_tokens=100, output_tokens=25,
        latency_ms=100.0, account_id="acct-1",
    )
    tracker.record(
        model_id="claude-opus-4-8",
        input_tokens=100, output_tokens=25,
        latency_ms=100.0, account_id="acct-2",
    )

    per_account = tracker.cost_per_account()
    assert "acct-1" in per_account
    assert "acct-2" in per_account
    single_cost = compute_cost("claude-opus-4-8", 100, 25)
    assert per_account["acct-1"] == pytest.approx(2 * single_cost, abs=1e-6)
    assert per_account["acct-2"] == pytest.approx(single_cost, abs=1e-6)


def test_cost_tracker_sweep_lifecycle():
    tracker = CostTracker()

    tracker.record(
        model_id="claude-opus-4-8",
        input_tokens=100, output_tokens=25,
        latency_ms=100.0,
    )
    first_cost = tracker.current_sweep_cost
    assert first_cost > 0

    # Reset for a new sweep.
    tracker.reset_sweep()
    assert tracker.current_sweep_cost == 0.0

    # Cumulative stats still hold the old data.
    assert tracker.stats()["total_calls"] == 1


def test_cost_tracker_today_cost():
    tracker = CostTracker()
    assert tracker.today_cost_usd() == 0.0

    tracker.record(
        model_id="claude-opus-4-8",
        input_tokens=100, output_tokens=25,
        latency_ms=100.0,
    )
    assert tracker.today_cost_usd() > 0


# ---------------------------------------------------------------------------
# Unit: CostBudget
# ---------------------------------------------------------------------------


def test_cost_budget_sweep_limit():
    budget = CostBudget(max_cost_per_sweep_usd=0.05, max_cost_per_day_usd=10.0)
    assert not budget.would_exceed_sweep(0.0, 0.03)
    assert budget.would_exceed_sweep(0.03, 0.03)  # 0.03 + 0.03 > 0.05


def test_cost_budget_daily_limit():
    budget = CostBudget(max_cost_per_sweep_usd=10.0, max_cost_per_day_usd=0.05)
    assert not budget.would_exceed_daily(0.0, 0.03)
    assert budget.would_exceed_daily(0.03, 0.03)


# ---------------------------------------------------------------------------
# Unit: APIMetrics
# ---------------------------------------------------------------------------


def test_api_metrics_records_and_reports():
    metrics = APIMetrics()

    metrics.record_request("/health", 10.0)
    metrics.record_request("/health", 20.0)
    metrics.record_request("/sweep", 500.0)

    snap = metrics.snapshot()
    assert snap["total_requests"] == 3
    assert snap["requests_by_endpoint"] == {"/health": 2, "/sweep": 1}
    assert snap["avg_response_time_ms"] == pytest.approx(176.67, abs=0.1)
    assert snap["p50_response_time_ms"] >= 10.0
    assert snap["p99_response_time_ms"] >= 10.0


def test_api_metrics_sweep_snapshot_empty():
    metrics = APIMetrics()
    snap = metrics.sweep_snapshot()
    assert snap["total_sweeps"] == 0
    assert snap["avg_sweep_duration_ms"] == 0.0


def test_api_metrics_sweep_snapshot_with_data():
    metrics = APIMetrics()
    metrics.record_sweep(SweepTiming(
        total_ms=1000.0,
        value_model_ms=200.0,
        slot_b_total_ms=600.0,
        slot_b_avg_per_account_ms=120.0,
        slot_b_call_count=5,
        governance_ms=200.0,
        accounts_swept=5,
    ))

    snap = metrics.sweep_snapshot()
    assert snap["total_sweeps"] == 1
    assert snap["avg_sweep_duration_ms"] == 1000.0
    assert snap["avg_accounts_per_sweep"] == 5.0
    assert snap["last_sweep"]["total_ms"] == 1000.0
    assert snap["last_sweep"]["slot_b_total_ms"] == 600.0


# ---------------------------------------------------------------------------
# Integration: Budget enforcement in sweep
# ---------------------------------------------------------------------------


class _CostTrackingWriter:
    """A fixture writer that pretends to be an expensive model for budget tests.

    Produces valid fixture output but records a non-zero cost in the
    cost tracker after each call.
    """

    model_id = "claude-opus-4-8"
    prompt_version = SLOT_B_PROMPT_VERSION

    def __init__(self, cost_tracker: CostTracker) -> None:
        self._inner = FixtureReasonDraftWriter()
        self._tracker = cost_tracker
        self.calls: list[str] = []  # track which account_ids were called

    def write(self, request: ReasonDraftRequest) -> ReasonDraftOutput:
        output = self._inner.write(request)
        self.calls.append(request.account_id)
        self._tracker.record(
            model_id=self.model_id,
            input_tokens=2000,
            output_tokens=500,
            latency_ms=100.0,
            account_id=request.account_id,
        )
        return ReasonDraftOutput(
            reason=output.reason,
            cited_evidence_ids=output.cited_evidence_ids,
            customer_draft=output.customer_draft,
            model_id=self.model_id,
            prompt_version=output.prompt_version,
        )


def test_budget_enforcement_skips_remaining_accounts(sweep_conn):
    """When the cost budget is exceeded mid-sweep, remaining Slot B calls
    fall back to the fixture writer and are counted as budget_skipped."""
    from tests._govhelpers import CLOCK, T1, setup_roster
    from ultra_csm.agent1 import run_time_to_value_sweep
    from ultra_csm.data_plane import DEFAULT_TENANT, build_sweep_fixture_data_plane
    from ultra_csm.governance import ActionGate, FixtureVerdictSource

    orch, _authority = setup_roster(sweep_conn)
    gate = ActionGate(
        sweep_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )

    tracker = CostTracker()
    writer = _CostTrackingWriter(tracker)

    # The cost per call is compute_cost("claude-opus-4-8", 2000, 500)
    #   = (2000*5 + 500*25) / 1_000_000 = (10000+12500)/1M = 0.0225
    # The estimate per call is estimate_call_cost("claude-opus-4-8")
    #   = (2000*5 + 700*25) / 1_000_000 = 0.0275
    # Set budget to allow exactly 1 call: 0 + 0.0275 < 0.03, but
    # after 1st call: 0.0225 + 0.0275 = 0.05 > 0.03 → exceeded.
    budget = CostBudget(max_cost_per_sweep_usd=0.03, max_cost_per_day_usd=100.0)

    sweep = run_time_to_value_sweep(
        build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=orch,
        as_of="2026-06-27",
        reason_draft_writer=writer,
        cost_tracker=tracker,
        cost_budget=budget,
    )

    # The writer should have been called for the first eligible account only.
    assert len(writer.calls) == 1, (
        f"Expected exactly 1 writer call but got {len(writer.calls)}"
    )

    # The sweep should still produce work items (with fixture fallback).
    assert len(sweep.work_items) > 1, (
        "Sweep should produce work items even when budget is exceeded"
    )

    # Budget-skipped items count.
    assert sweep.budget_skipped > 0, (
        "Expected some accounts to be budget-skipped"
    )

    # All work items should still have valid reasons and priorities.
    for item in sweep.work_items:
        assert item.reason
        assert item.priority is not None
        assert item.priority.score > 0


def test_budget_enforcement_no_skip_when_budget_is_generous(sweep_conn):
    """With a generous budget, no accounts are skipped."""
    from tests._govhelpers import CLOCK, T1, setup_roster
    from ultra_csm.agent1 import run_time_to_value_sweep
    from ultra_csm.data_plane import DEFAULT_TENANT, build_sweep_fixture_data_plane
    from ultra_csm.governance import ActionGate, FixtureVerdictSource

    orch, _authority = setup_roster(sweep_conn)
    gate = ActionGate(
        sweep_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )

    tracker = CostTracker()
    writer = _CostTrackingWriter(tracker)
    budget = CostBudget(max_cost_per_sweep_usd=100.0, max_cost_per_day_usd=100.0)

    sweep = run_time_to_value_sweep(
        build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=orch,
        as_of="2026-06-27",
        reason_draft_writer=writer,
        cost_tracker=tracker,
        cost_budget=budget,
    )

    assert sweep.budget_skipped == 0
    # The writer should have been called for every work item.
    assert len(writer.calls) == len(sweep.work_items)


def test_sweep_without_budget_args_is_unchanged(sweep_conn):
    """Passing no cost_tracker/cost_budget works exactly as before."""
    from tests._govhelpers import CLOCK, T1, setup_roster
    from ultra_csm.agent1 import run_time_to_value_sweep
    from ultra_csm.data_plane import DEFAULT_TENANT, build_sweep_fixture_data_plane
    from ultra_csm.governance import ActionGate, FixtureVerdictSource

    orch, _authority = setup_roster(sweep_conn)
    gate = ActionGate(
        sweep_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )

    sweep = run_time_to_value_sweep(
        build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=orch,
        as_of="2026-06-27",
    )

    assert sweep.budget_skipped == 0
    assert sweep.work_items


# ---------------------------------------------------------------------------
# Integration: /metrics endpoint
# ---------------------------------------------------------------------------


@pytest.fixture
def sweep_conn(runtime_conn):
    runtime_conn.execute("BEGIN")
    try:
        yield runtime_conn
    finally:
        runtime_conn.rollback()
