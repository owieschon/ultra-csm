"""Behavioral quality evaluation for governed CSM workflows.

Authoring readiness answers "is this workflow wired?"  The execution envelope
answers "is this workflow governed?"  This module answers the more CSM-specific
question: "did this workflow use the right evidence, preserve uncertainty, and
produce an action that is fit for customer-facing work in this scenario?"

The evaluator is deliberately path-based instead of enforcing a universal packet
schema. Workflow packets keep their domain-specific model, while quality cases
declare the behavioral obligations that matter for a scenario.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Literal


CriterionSeverity = Literal["error", "warning"]


@dataclass(frozen=True)
class WorkflowQualityCriterion:
    criterion_id: str
    label: str
    passed: bool
    detail: str
    severity: CriterionSeverity = "error"
    source_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_ids"] = list(self.source_ids)
        return payload


@dataclass(frozen=True)
class WorkflowQualityExpectation:
    scenario_id: str
    workflow_id: str
    expected_statuses: tuple[str, ...]
    required_reviewed_sources: tuple[str, ...] = ()
    required_action_types: tuple[str, ...] = ()
    required_decision_kinds: tuple[str, ...] = ()
    required_domain_paths: tuple[str, ...] = ()
    required_alternatives: tuple[str, ...] = ()
    require_all_invariants_pass: bool = True
    expect_customer_output: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "workflow_id": self.workflow_id,
            "expected_statuses": list(self.expected_statuses),
            "required_reviewed_sources": list(self.required_reviewed_sources),
            "required_action_types": list(self.required_action_types),
            "required_decision_kinds": list(self.required_decision_kinds),
            "required_domain_paths": list(self.required_domain_paths),
            "required_alternatives": list(self.required_alternatives),
            "require_all_invariants_pass": self.require_all_invariants_pass,
            "expect_customer_output": self.expect_customer_output,
        }


@dataclass(frozen=True)
class WorkflowQualityCase:
    packet: dict[str, Any]
    expectation: WorkflowQualityExpectation


@dataclass(frozen=True)
class WorkflowQualityScenarioResult:
    scenario_id: str
    workflow_id: str
    passed: bool
    criteria: tuple[WorkflowQualityCriterion, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "workflow_id": self.workflow_id,
            "passed": self.passed,
            "criteria": [criterion.to_dict() for criterion in self.criteria],
        }


@dataclass(frozen=True)
class WorkflowQualityReport:
    generated_at: str
    passed: bool
    results: tuple[WorkflowQualityScenarioResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "passed": self.passed,
            "results": [result.to_dict() for result in self.results],
        }


def evaluate_workflow_quality_report(
    cases: tuple[WorkflowQualityCase, ...],
    *,
    generated_at: str | None = None,
) -> WorkflowQualityReport:
    results = tuple(
        evaluate_workflow_packet_quality(case.packet, case.expectation)
        for case in cases
    )
    return WorkflowQualityReport(
        generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
        passed=all(result.passed for result in results),
        results=results,
    )


def evaluate_workflow_packet_quality(
    packet: dict[str, Any],
    expectation: WorkflowQualityExpectation,
) -> WorkflowQualityScenarioResult:
    criteria = (
        _workflow_identity_criterion(packet, expectation),
        _status_criterion(packet, expectation),
        _source_coverage_criterion(packet, expectation),
        _decision_trace_criterion(packet, expectation),
        _action_criterion(packet, expectation),
        _domain_paths_criterion(packet, expectation),
        _alternatives_criterion(packet, expectation),
        _customer_output_criterion(packet, expectation),
        _invariants_criterion(packet, expectation),
    )
    return WorkflowQualityScenarioResult(
        scenario_id=expectation.scenario_id,
        workflow_id=expectation.workflow_id,
        passed=all(item.passed or item.severity == "warning" for item in criteria),
        criteria=criteria,
    )


def _workflow_identity_criterion(
    packet: dict[str, Any],
    expectation: WorkflowQualityExpectation,
) -> WorkflowQualityCriterion:
    observed = str(packet.get("workflow_id") or _get(packet, "execution_envelope.workflow_id") or "")
    passed = observed == expectation.workflow_id
    return WorkflowQualityCriterion(
        "workflow_identity",
        "Packet belongs to the expected workflow.",
        passed,
        f"Expected {expectation.workflow_id!r}; observed {observed!r}.",
    )


def _status_criterion(
    packet: dict[str, Any],
    expectation: WorkflowQualityExpectation,
) -> WorkflowQualityCriterion:
    observed = str(packet.get("status") or "")
    passed = observed in set(expectation.expected_statuses)
    return WorkflowQualityCriterion(
        "scenario_status",
        "Workflow reached the expected scenario state.",
        passed,
        f"Expected one of {list(expectation.expected_statuses)!r}; observed {observed!r}.",
    )


def _source_coverage_criterion(
    packet: dict[str, Any],
    expectation: WorkflowQualityExpectation,
) -> WorkflowQualityCriterion:
    observed = _observed_source_types(packet)
    required = set(expectation.required_reviewed_sources)
    missing = tuple(sorted(required - observed))
    return WorkflowQualityCriterion(
        "all_required_sources_reviewed",
        "Workflow reviewed every source required for this scenario.",
        not missing,
        (
            "All required sources were observed."
            if not missing
            else f"Missing required reviewed sources: {list(missing)!r}."
        ),
        source_ids=_observed_source_ids(packet),
    )


def _decision_trace_criterion(
    packet: dict[str, Any],
    expectation: WorkflowQualityExpectation,
) -> WorkflowQualityCriterion:
    decisions = _as_list(_get(packet, "execution_envelope.decisions"))
    observed = {
        str(item.get("decision_kind"))
        for item in decisions
        if isinstance(item, dict) and item.get("decision_kind")
    }
    missing = tuple(sorted(set(expectation.required_decision_kinds) - observed))
    passed = bool(decisions) and not missing
    detail = "Decision trace is present."
    if missing:
        detail = f"Missing decision kinds: {list(missing)!r}."
    elif not decisions:
        detail = "No decision trace found."
    return WorkflowQualityCriterion(
        "scenario_decision_trace",
        "Workflow exposes the required decision trace.",
        passed,
        detail,
    )


def _action_criterion(
    packet: dict[str, Any],
    expectation: WorkflowQualityExpectation,
) -> WorkflowQualityCriterion:
    observed = _observed_action_types(packet)
    missing = tuple(sorted(set(expectation.required_action_types) - observed))
    return WorkflowQualityCriterion(
        "scenario_action_contract",
        "Workflow proposed the expected governed action type.",
        not missing,
        (
            "Expected action types were proposed."
            if not missing
            else f"Missing action types: {list(missing)!r}; observed {sorted(observed)!r}."
        ),
    )


def _domain_paths_criterion(
    packet: dict[str, Any],
    expectation: WorkflowQualityExpectation,
) -> WorkflowQualityCriterion:
    missing = tuple(
        path for path in expectation.required_domain_paths
        if not _path_has_value(packet, path)
    )
    return WorkflowQualityCriterion(
        "domain_specific_value_model",
        "Workflow populated the scenario-specific value and judgment fields.",
        not missing,
        (
            "Required domain paths are populated."
            if not missing
            else f"Missing or empty domain paths: {list(missing)!r}."
        ),
    )


def _alternatives_criterion(
    packet: dict[str, Any],
    expectation: WorkflowQualityExpectation,
) -> WorkflowQualityCriterion:
    if not expectation.required_alternatives:
        return WorkflowQualityCriterion(
            "uncertainty_preserved",
            "Workflow preserves uncertainty where required.",
            True,
            "No scenario-specific alternatives required.",
        )
    observed = _observed_alternatives(packet)
    missing = tuple(sorted(set(expectation.required_alternatives) - observed))
    return WorkflowQualityCriterion(
        "uncertainty_preserved",
        "Workflow preserves alternate explanations or value-path hypotheses.",
        not missing,
        (
            "Required alternatives were preserved."
            if not missing
            else f"Missing alternatives: {list(missing)!r}; observed {sorted(observed)!r}."
        ),
    )


def _customer_output_criterion(
    packet: dict[str, Any],
    expectation: WorkflowQualityExpectation,
) -> WorkflowQualityCriterion:
    proposed_customer_output = _has_proposed_customer_output(packet)
    if expectation.expect_customer_output is None:
        return WorkflowQualityCriterion(
            "customer_output_policy",
            "Customer-facing output policy is not asserted for this scenario.",
            True,
            "No customer-output expectation set.",
        )
    passed = proposed_customer_output is expectation.expect_customer_output
    expected = "proposed" if expectation.expect_customer_output else "suppressed"
    observed = "proposed" if proposed_customer_output else "suppressed"
    return WorkflowQualityCriterion(
        "customer_output_policy",
        "Customer-facing output is proposed or suppressed according to evidence strength.",
        passed,
        f"Expected customer output {expected}; observed {observed}.",
    )


def _invariants_criterion(
    packet: dict[str, Any],
    expectation: WorkflowQualityExpectation,
) -> WorkflowQualityCriterion:
    if not expectation.require_all_invariants_pass:
        return WorkflowQualityCriterion(
            "execution_envelope_invariants",
            "Execution envelope invariants are not asserted for this scenario.",
            True,
            "Invariant pass requirement disabled.",
        )
    failures = tuple(
        str(item.get("invariant"))
        for item in _as_list(_get(packet, "execution_envelope.invariant_results"))
        if isinstance(item, dict) and not item.get("passed")
    )
    return WorkflowQualityCriterion(
        "execution_envelope_invariants",
        "Execution envelope invariants pass.",
        not failures,
        (
            "All execution envelope invariants passed."
            if not failures
            else f"Failed invariants: {list(failures)!r}."
        ),
    )


def _observed_source_types(packet: dict[str, Any]) -> set[str]:
    observed: set[str] = set()
    for path in (
        "execution_envelope.evidence.reviewed_sources",
        "execution_envelope.evidence.missing_required_sources",
        "coverage.reviewed_sources",
        "coverage.missing_required_sources",
        "coverage.original_success_plan_sources",
        "coverage.current_state_sources",
        "coverage.stakeholder_verification_sources",
    ):
        observed.update(str(value) for value in _flatten(_values_for_path(packet, path)) if value)

    for item in _as_list(_get(packet, "execution_envelope.evidence.items")):
        if isinstance(item, dict) and item.get("source_type"):
            observed.add(str(item["source_type"]))
    for item in _as_list(packet.get("source_receipts")):
        if isinstance(item, dict) and item.get("source_type"):
            observed.add(str(item["source_type"]))

    observed.update(_derived_source_types(packet))
    return observed


def _derived_source_types(packet: dict[str, Any]) -> set[str]:
    derived: set[str] = set()
    observed_receipt_types = {
        str(value)
        for value in _flatten(_values_for_path(packet, "source_receipts.source_type"))
        if value
    }
    observed_source_names = {
        str(value)
        for path in (
            "coverage.original_success_plan_sources",
            "coverage.current_state_sources",
            "coverage.stakeholder_verification_sources",
            "coverage.reviewed_sources",
        )
        for value in _flatten(_values_for_path(packet, path))
        if value
    }
    if _get(packet, "identity_resolution.state") == "exactly_one":
        derived.add("resolved_organization")
    if "salesforce_contact" in observed_receipt_types:
        derived.add("contact_record")
    if _path_has_value(packet, "success_plan_methodology.value_model_alignment") or _path_has_value(packet, "value_context"):
        derived.add("value_model_alignment")
    if {
        "customer_email",
        "call_or_meeting_context",
        "google_calendar",
        "calendar_or_call_attendance",
        "google_calendar_attendance",
    } & observed_source_names:
        derived.add("customer_email_or_call_or_calendar")
    if _path_has_value(packet, "metric_comparisons.baseline_value"):
        derived.add("baseline_usage_window")
    if _path_has_value(packet, "metric_comparisons.current_value"):
        derived.add("current_usage_window")
    if _path_has_value(packet, "metric_comparisons.metric_name") or _path_has_value(packet, "value_path.milestones"):
        derived.add("product_telemetry")
    return derived


def _observed_source_ids(packet: dict[str, Any]) -> tuple[str, ...]:
    source_ids: set[str] = set()
    for path in (
        "execution_envelope.evidence.items.source_id",
        "source_receipts.source_id",
        "trigger_receipt.source_id",
    ):
        source_ids.update(str(value) for value in _flatten(_values_for_path(packet, path)) if value)
    return tuple(sorted(source_ids))


def _observed_action_types(packet: dict[str, Any]) -> set[str]:
    observed: set[str] = set()
    for item in _as_list(packet.get("proposals")):
        if isinstance(item, dict) and item.get("action_type"):
            observed.add(str(item["action_type"]))
    for item in _as_list(_get(packet, "execution_envelope.outputs")):
        if isinstance(item, dict) and item.get("action_type"):
            observed.add(str(item["action_type"]))
    action = _get(packet, "recommended_action.action_type") or packet.get("recommended_next_action")
    if action:
        observed.add(str(action))
    return observed


def _observed_alternatives(packet: dict[str, Any]) -> set[str]:
    alternatives: set[str] = set()
    for path in (
        "execution_envelope.decisions.alternatives",
        "interpretation.alternatives",
        "value_path.secondary_hypotheses.path_id",
        "success_plan_methodology.first_value_hypotheses.capability",
    ):
        alternatives.update(str(value) for value in _flatten(_values_for_path(packet, path)) if value)
    return alternatives


def _has_proposed_customer_output(packet: dict[str, Any]) -> bool:
    for item in _as_list(_get(packet, "execution_envelope.outputs")):
        if not isinstance(item, dict):
            continue
        is_customer = item.get("audience") == "customer_facing" or bool(item.get("customer_affecting"))
        if is_customer and item.get("status") == "proposed":
            return True
    return bool(packet.get("customer_language") or packet.get("customer_welcome_draft"))


def _path_has_value(payload: Any, path: str) -> bool:
    return any(_truthy(value) for value in _values_for_path(payload, path))


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


def _get(payload: Any, path: str) -> Any:
    values = _values_for_path(payload, path)
    return values[0] if values else None


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


def _truthy(value: Any) -> bool:
    if value is None:
        return False
    if value is False:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True
