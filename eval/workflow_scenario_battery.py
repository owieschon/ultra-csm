"""Workflow scenario battery over the synthetic universe.

Anti-Goodhart note: docs/SYNTHETIC_UNIVERSE_BIBLE.md owns the account-world
truth. This battery may add scenarios or correct assertions only when the bible
or workflow contract changes; it must never be edited merely to match current
workflow output. The point is to catch workflow judgment drift against the
existing deterministic universe.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ultra_csm.workflow_scenario_eval import (
    SyntheticWorkflowScenarioResult,
    run_synthetic_workflow_scenario_report,
    synthetic_adoption_regression_scenarios,
    synthetic_self_serve_activation_scenarios,
)


REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO / "eval" / "workflow_scenario_battery.json"
FIXED_GENERATED_AT = "2026-07-08T00:00:00+00:00"


def build_workflow_scenario_battery_artifact(
    output_path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    scenarios = (
        synthetic_adoption_regression_scenarios()
        + synthetic_self_serve_activation_scenarios()
    )
    report = run_synthetic_workflow_scenario_report(
        scenarios,
        generated_at=FIXED_GENERATED_AT,
    )
    cases = [_case_summary(result) for result in report.results]
    hard_failures = [
        case["scenario_id"] for case in cases
        if not case["passed"]
    ]
    artifact = {
        "artifact": "workflow_scenario_battery",
        "generated_at": FIXED_GENERATED_AT,
        "claim_boundary": {
            "fixture": True,
            "synthetic_universe": True,
            "workflow_fixture_conventions": True,
            "live": False,
            "llm_judge": False,
            "network": False,
        },
        "measurement_scope": (
            "Runs real workflow code against deterministic fleetops synthetic "
            "universe snapshots and deterministic workflow-specific self-serve "
            "fixtures, then scores workflow packets with behavioral quality "
            "criteria and scenario-specific field assertions. No live connectors, "
            "LLM calls, or customer writes."
        ),
        "ground_truth_sources": (
            "docs/SYNTHETIC_UNIVERSE_BIBLE.md",
            "docs/UNIVERSE_V2_CONVENTIONS.md",
            "eval/gold/fleetops_expected_actions.json",
            "src/ultra_csm/workflow_playbooks.py",
            "tests/test_self_serve_activation_workflow.py",
        ),
        "anti_goodhart_rule": (
            "Bible/conventions own world truth; battery expectations change only "
            "with an explicit world or workflow-contract change."
        ),
        "score": {
            "passed": sum(1 for case in cases if case["passed"]),
            "total": len(cases),
        },
        "hard_ok": not hard_failures,
        "hard_failures": hard_failures,
        "cases": cases,
    }
    output_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return artifact


def _case_summary(result: SyntheticWorkflowScenarioResult) -> dict[str, Any]:
    packet = result.packet
    scenario = result.scenario
    quality_failures = [
        criterion.to_dict()
        for criterion in result.quality_result.criteria
        if not criterion.passed and criterion.severity == "error"
    ]
    field_failures = [
        field.to_dict() for field in result.field_results if not field.passed
    ]
    return {
        "scenario_id": scenario.scenario_id,
        "workflow_id": scenario.workflow_id,
        "tenant_id": scenario.tenant_id,
        "account_slug": scenario.account_slug,
        "baseline_day": scenario.baseline_day,
        "current_day": scenario.current_day,
        "metric_name": scenario.metric_name,
        "notes": scenario.notes,
        "passed": result.passed,
        "quality_failures": quality_failures,
        "field_failures": field_failures,
        "observed": {
            "packet_id": packet.get("packet_id"),
            "status": packet.get("status"),
            "severity": _first(packet, "interpretation.severity"),
            "selected_hypothesis": _first(packet, "interpretation.selected_hypothesis"),
            "recommended_action": _first(packet, "recommended_action.action_type"),
            "trigger": _first(packet, "recommended_action.trigger"),
            "drop_ratio": _first(packet, "metric_comparisons.drop_ratio"),
            "value_path": _first(packet, "value_path.path_id"),
            "first_value_definition": _first(packet, "value_path.first_value_definition"),
            "first_value_reached": _first(packet, "value_path.first_value_reached"),
            "current_milestone": _first(packet, "value_path.current_milestone_id"),
            "identity_state": _first(packet, "identity_resolution.state"),
            "identity_reason": _first(packet, "identity_resolution.reason"),
            "personal_email_domain": _first(packet, "identity_resolution.personal_email_domain"),
            "customer_language_present": bool(packet.get("customer_language")),
            "missing_required_sources": list(_first(packet, "coverage.missing_required_sources") or ()),
            "customer_output_blockers": list(_first(packet, "coverage.customer_output_blockers") or ()),
            "suppression_reasons": list(_first(packet, "recommended_action.suppression_reasons") or ()),
        },
    }


def _first(payload: Any, path: str) -> Any:
    values = _values_for_path(payload, path)
    if not values:
        return None
    value = values[0]
    if isinstance(value, tuple):
        return list(value)
    return value


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    artifact = build_workflow_scenario_battery_artifact(args.output)
    print(json.dumps(artifact, indent=2, sort_keys=True))
    return 0 if artifact["hard_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
