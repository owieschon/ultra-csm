"""Synthetic-universe scenario runner for workflow behavior evals.

The synthetic book and its bible already encode many CSM truths. This module
connects that universe to the workflow quality evaluator by running real
workflow code against dated synthetic snapshots and checking packet behavior.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from ultra_csm.adoption_regression import (
    ProductUsageRegressionEvent,
    run_account_adoption_regression,
)
from ultra_csm.data_plane.book_simulator import simulate_book
from ultra_csm.data_plane.contracts import CustomerDataPlane, UsageSignal
from ultra_csm.data_plane.fixtures import (
    DEFAULT_TENANT,
    FixtureCRMDataConnector,
    FixtureCSPlatformConnector,
    FixtureCommsConnector,
    FixtureProductTelemetryConnector,
    account_id_for,
    det_id,
)
from ultra_csm.data_plane.synthetic_book import build_synthetic_book
from ultra_csm.governance import ActionGate
from ultra_csm.workflow_quality_eval import (
    WorkflowQualityExpectation,
    WorkflowQualityScenarioResult,
    evaluate_workflow_packet_quality,
)


FieldExpectationMode = Literal["equals", "at_least", "at_most", "contains"]


class WorkflowScenarioEvalError(ValueError):
    """Raised when a synthetic workflow scenario cannot be run."""


@dataclass(frozen=True)
class WorkflowFieldExpectation:
    path: str
    mode: FieldExpectationMode
    expected: Any

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SyntheticWorkflowScenario:
    scenario_id: str
    workflow_id: str
    tenant_id: str
    account_slug: str
    current_day: int
    expectation: WorkflowQualityExpectation
    baseline_day: int | None = None
    metric_name: str = "daily_active_assets"
    include_baseline_usage: bool = True
    include_current_usage: bool = True
    field_expectations: tuple[WorkflowFieldExpectation, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["expectation"] = self.expectation.to_dict()
        payload["field_expectations"] = [
            expectation.to_dict() for expectation in self.field_expectations
        ]
        return payload


@dataclass(frozen=True)
class WorkflowFieldResult:
    path: str
    mode: FieldExpectationMode
    expected: Any
    observed: tuple[Any, ...]
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "mode": self.mode,
            "expected": self.expected,
            "observed": list(self.observed),
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class SyntheticWorkflowScenarioResult:
    scenario: SyntheticWorkflowScenario
    packet: dict[str, Any]
    quality_result: WorkflowQualityScenarioResult
    field_results: tuple[WorkflowFieldResult, ...]

    @property
    def passed(self) -> bool:
        return self.quality_result.passed and all(result.passed for result in self.field_results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario.to_dict(),
            "passed": self.passed,
            "quality_result": self.quality_result.to_dict(),
            "field_results": [result.to_dict() for result in self.field_results],
            "packet": self.packet,
        }


@dataclass(frozen=True)
class SyntheticWorkflowScenarioReport:
    generated_at: str
    passed: bool
    results: tuple[SyntheticWorkflowScenarioResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "passed": self.passed,
            "results": [result.to_dict() for result in self.results],
        }


def run_synthetic_workflow_scenario_report(
    scenarios: tuple[SyntheticWorkflowScenario, ...],
    *,
    gate: ActionGate | None = None,
    generated_at: str | None = None,
) -> SyntheticWorkflowScenarioReport:
    results = tuple(run_synthetic_workflow_scenario(scenario, gate=gate) for scenario in scenarios)
    return SyntheticWorkflowScenarioReport(
        generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
        passed=all(result.passed for result in results),
        results=results,
    )


def run_synthetic_workflow_scenario(
    scenario: SyntheticWorkflowScenario,
    *,
    gate: ActionGate | None = None,
) -> SyntheticWorkflowScenarioResult:
    packet = _run_packet(scenario, gate=gate)
    quality_result = evaluate_workflow_packet_quality(packet, scenario.expectation)
    field_results = tuple(
        _evaluate_field_expectation(packet, expectation)
        for expectation in scenario.field_expectations
    )
    return SyntheticWorkflowScenarioResult(
        scenario=scenario,
        packet=packet,
        quality_result=quality_result,
        field_results=field_results,
    )


def synthetic_adoption_regression_scenarios() -> tuple[SyntheticWorkflowScenario, ...]:
    """Canonical workflow scenarios adapted from the existing fleetops universe.

    These are not a human gold set. They are deterministic universe-derived
    cases that prove the workflow sees trend evidence, preserves uncertainty,
    suppresses unsafe customer motion for weak watch-level shifts, and ignores
    a no-shift control.
    """

    return (
        SyntheticWorkflowScenario(
            scenario_id="fleetops_aspenridge_silent_decline_day340",
            workflow_id="account_adoption_regression",
            tenant_id=DEFAULT_TENANT,
            account_slug="aspenridge-supply",
            baseline_day=90,
            current_day=340,
            expectation=WorkflowQualityExpectation(
                scenario_id="fleetops_aspenridge_silent_decline_day340",
                workflow_id="account_adoption_regression",
                expected_statuses=("internal_only",),
                required_reviewed_sources=(
                    "account_identity",
                    "product_telemetry",
                    "baseline_usage_window",
                    "current_usage_window",
                    "entitlement",
                    "adoption_summary",
                    "value_model_alignment",
                    "customer_email_or_call",
                ),
                required_action_types=("recommend_internal_review",),
                required_decision_kinds=("account_adoption_regression",),
                required_domain_paths=(
                    "metric_comparisons.drop_ratio",
                    "metric_comparisons.severity",
                    "value_context.lifecycle_stage",
                    "interpretation.selected_hypothesis",
                    "recommended_action.suppression_reasons",
                ),
                required_alternatives=("telemetry_noise_or_seasonality",),
                expect_customer_output=False,
            ),
            field_expectations=(
                WorkflowFieldExpectation("interpretation.severity", "equals", "watch"),
                WorkflowFieldExpectation("metric_comparisons.drop_ratio", "at_least", 0.10),
                WorkflowFieldExpectation("metric_comparisons.drop_ratio", "at_most", 0.20),
                WorkflowFieldExpectation("recommended_action.action_type", "equals", "recommend_internal_review"),
                WorkflowFieldExpectation("recommended_action.suppression_reasons", "contains", "regression_below_customer_motion_threshold"),
            ),
            notes=(
                "Synthetic Universe Bible arc 4: silent decline remains under the "
                "health-band threshold, so the workflow should detect a watch-level "
                "shift but keep it internal."
            ),
        ),
        SyntheticWorkflowScenario(
            scenario_id="fleetops_aspenridge_no_shift_control_day90",
            workflow_id="account_adoption_regression",
            tenant_id=DEFAULT_TENANT,
            account_slug="aspenridge-supply",
            baseline_day=90,
            current_day=90,
            expectation=WorkflowQualityExpectation(
                scenario_id="fleetops_aspenridge_no_shift_control_day90",
                workflow_id="account_adoption_regression",
                expected_statuses=("ignored",),
                required_reviewed_sources=(
                    "account_identity",
                    "product_telemetry",
                    "baseline_usage_window",
                    "current_usage_window",
                    "entitlement",
                    "adoption_summary",
                    "value_model_alignment",
                ),
                required_action_types=("suppress_regression_motion",),
                required_decision_kinds=("account_adoption_regression",),
                required_domain_paths=(
                    "metric_comparisons.drop_ratio",
                    "interpretation.severity",
                    "recommended_action.suppression_reasons",
                ),
                required_alternatives=("telemetry_noise_or_seasonality",),
                expect_customer_output=False,
            ),
            field_expectations=(
                WorkflowFieldExpectation("interpretation.severity", "equals", "none"),
                WorkflowFieldExpectation("metric_comparisons.drop_ratio", "equals", 0.0),
                WorkflowFieldExpectation("recommended_action.action_type", "equals", "suppress_regression_motion"),
                WorkflowFieldExpectation("recommended_action.suppression_reasons", "contains", "no_regression_observed"),
            ),
            notes="No-shift control: the workflow should not create internal review work.",
        ),
        SyntheticWorkflowScenario(
            scenario_id="fleetops_aspenridge_missing_current_window",
            workflow_id="account_adoption_regression",
            tenant_id=DEFAULT_TENANT,
            account_slug="aspenridge-supply",
            baseline_day=90,
            current_day=340,
            include_current_usage=False,
            expectation=WorkflowQualityExpectation(
                scenario_id="fleetops_aspenridge_missing_current_window",
                workflow_id="account_adoption_regression",
                expected_statuses=("needs_data",),
                required_reviewed_sources=(
                    "account_identity",
                    "product_telemetry",
                    "baseline_usage_window",
                    "entitlement",
                    "adoption_summary",
                    "value_model_alignment",
                ),
                required_action_types=("recommend_internal_review",),
                required_decision_kinds=("account_adoption_regression",),
                required_domain_paths=(
                    "coverage.customer_output_blockers",
                    "recommended_action.suppression_reasons",
                ),
                required_alternatives=("telemetry_noise_or_seasonality",),
                expect_customer_output=False,
            ),
            field_expectations=(
                WorkflowFieldExpectation("coverage.missing_required_sources", "contains", "current_usage_window"),
                WorkflowFieldExpectation("coverage.customer_output_blockers", "contains", "current_usage_window_missing"),
            ),
            notes="Counterfactual: remove the current usage window and require fail-closed behavior.",
        ),
    )


def _run_packet(
    scenario: SyntheticWorkflowScenario,
    *,
    gate: ActionGate | None,
) -> dict[str, Any]:
    if scenario.workflow_id != "account_adoption_regression":
        raise WorkflowScenarioEvalError(
            f"synthetic scenario runner does not support workflow {scenario.workflow_id!r}"
        )
    baseline_day = scenario.baseline_day
    if baseline_day is None:
        raise WorkflowScenarioEvalError("account_adoption_regression scenarios require baseline_day")
    account_id = account_id_for(scenario.account_slug)
    event = ProductUsageRegressionEvent(
        tenant_id=scenario.tenant_id,
        account_id=account_id,
        metric_name=scenario.metric_name,
        baseline_start=_day_clock(baseline_day),
        baseline_end=_day_end(baseline_day),
        current_start=_day_clock(scenario.current_day),
        current_end=_day_end(scenario.current_day),
        observed_at=_day_clock(scenario.current_day),
    )
    packet = run_account_adoption_regression(
        data_plane=_adoption_regression_data_plane(scenario),
        gate=gate,
        event=event,
        as_of=_day_iso(scenario.current_day),
    )
    return packet.to_dict()


def _adoption_regression_data_plane(scenario: SyntheticWorkflowScenario) -> CustomerDataPlane:
    baseline_day = scenario.baseline_day
    if baseline_day is None:
        raise WorkflowScenarioEvalError("account_adoption_regression scenarios require baseline_day")
    base = build_synthetic_book()
    current_book = simulate_book(base, scenario.current_day)
    baseline_book = simulate_book(base, baseline_day)
    account_id = account_id_for(scenario.account_slug)
    usage_signals = _historical_usage_signals(
        account_id=account_id,
        baseline_book=baseline_book,
        current_book=current_book,
        baseline_day=baseline_day,
        current_day=scenario.current_day,
        include_baseline=scenario.include_baseline_usage,
        include_current=scenario.include_current_usage,
    )
    data = replace(
        current_book,
        usage_signals=(
            tuple(signal for signal in current_book.usage_signals if signal.account_id != account_id)
            + usage_signals
        ),
    )
    return CustomerDataPlane(
        crm=FixtureCRMDataConnector(tenant=scenario.tenant_id, data=data),
        cs=FixtureCSPlatformConnector(data=data),
        telemetry=FixtureProductTelemetryConnector(data=data),
        comms=FixtureCommsConnector(data=data),
    )


def _historical_usage_signals(
    *,
    account_id: str,
    baseline_book: Any,
    current_book: Any,
    baseline_day: int,
    current_day: int,
    include_baseline: bool,
    include_current: bool,
) -> tuple[UsageSignal, ...]:
    signals: list[UsageSignal] = []
    if include_baseline:
        signals.extend(
            _versioned_signal(signal, "baseline", baseline_day, current_day)
            for signal in baseline_book.usage_signals
            if signal.account_id == account_id
        )
    if include_current:
        signals.extend(
            _versioned_signal(signal, "current", baseline_day, current_day)
            for signal in current_book.usage_signals
            if signal.account_id == account_id
        )
    return tuple(signals)


def _versioned_signal(
    signal: UsageSignal,
    window: Literal["baseline", "current"],
    baseline_day: int,
    current_day: int,
) -> UsageSignal:
    return replace(
        signal,
        signal_id=det_id("workflow-scenario-signal", signal.signal_id, window, baseline_day, current_day),
        source_ref=f"{signal.source_ref}:{window}:day{baseline_day if window == 'baseline' else current_day}",
    )


def _evaluate_field_expectation(
    packet: dict[str, Any],
    expectation: WorkflowFieldExpectation,
) -> WorkflowFieldResult:
    observed = tuple(_flatten(_values_for_path(packet, expectation.path)))
    passed = _field_passed(observed, expectation)
    return WorkflowFieldResult(
        path=expectation.path,
        mode=expectation.mode,
        expected=expectation.expected,
        observed=observed,
        passed=passed,
        detail=(
            "Field expectation passed."
            if passed
            else f"Expected {expectation.path} {expectation.mode} {expectation.expected!r}; observed {observed!r}."
        ),
    )


def _field_passed(values: tuple[Any, ...], expectation: WorkflowFieldExpectation) -> bool:
    if expectation.mode == "equals":
        return any(value == expectation.expected for value in values)
    if expectation.mode == "contains":
        return any(_contains(value, expectation.expected) for value in values)
    comparable = [value for value in values if isinstance(value, (int, float))]
    if expectation.mode == "at_least":
        return any(value >= expectation.expected for value in comparable)
    if expectation.mode == "at_most":
        return any(value <= expectation.expected for value in comparable)
    return False


def _contains(value: Any, expected: Any) -> bool:
    if isinstance(value, str):
        return str(expected) in value
    if isinstance(value, (list, tuple, set)):
        return expected in value
    return value == expected


def _values_for_path(payload: Any, path: str) -> list[Any]:
    values = [payload]
    for part in path.split("."):
        next_values: list[Any] = []
        for value in values:
            if isinstance(value, dict) and part in value:
                next_values.append(value[part])
            elif isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, dict) and part in item:
                        next_values.append(item[part])
        values = next_values
        if not values:
            return []
    return values


def _flatten(values: Any) -> list[Any]:
    flattened: list[Any] = []
    for value in _as_list(values):
        if isinstance(value, (list, tuple)):
            flattened.extend(_flatten(value))
        else:
            flattened.append(value)
    return flattened


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _day_clock(day_offset: int) -> str:
    base = datetime(2026, 6, 21, 0, 0, 0, tzinfo=timezone.utc)
    return (base + timedelta(days=day_offset)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _day_end(day_offset: int) -> str:
    base = datetime(2026, 6, 21, 23, 59, 59, tzinfo=timezone.utc)
    return (base + timedelta(days=day_offset)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _day_iso(day_offset: int) -> str:
    return _day_clock(day_offset)[:10]
