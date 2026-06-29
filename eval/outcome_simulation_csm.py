"""Synthetic Time-to-Value outcome simulation for Agent 1 eval planning.

This module uses only the deterministic Ultra CSM data-plane fixtures. The
artifact is training/eval evidence about the measurement method, not evidence of
real customer outcomes or production lift.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

from ultra_csm.data_plane import ACME_LOGISTICS, build_fixture_data_plane
from ultra_csm.data_plane.contracts import CustomerDataPlane, TimeToValueMilestone

ARTIFACT_LABEL = (
    "synthetic training/eval evidence only; fixture counterfactuals are not real "
    "customer outcome evidence"
)
ARTIFACT_PATH = Path(__file__).with_name("outcome_simulation_csm.json")
WORK_QUEUE_PATH = Path(__file__).with_name("csm_work_queue.json")
REPO = Path(__file__).resolve().parents[1]
FIXTURE_SOURCE = "src/ultra_csm/data_plane/fixtures.py"
SIMULATION_DATE = "2026-06-21"


def build_outcome_simulation(
    *,
    data_plane: CustomerDataPlane | None = None,
    simulation_date: str = SIMULATION_DATE,
    work_queue_path: Path | None = WORK_QUEUE_PATH,
) -> dict[str, Any]:
    plane = data_plane or build_fixture_data_plane()
    account_id = ACME_LOGISTICS
    account = plane.crm.get_account(account_id)
    company = plane.cs.get_company(account_id)
    health = plane.cs.get_health_score(account_id)
    adoption = plane.cs.get_adoption_summary(account_id)
    if account is None or company is None or health is None or adoption is None:
        raise RuntimeError("fixture data plane missing required Acme TTV context")

    cases = plane.crm.list_cases(account_id)
    opportunities = plane.crm.list_opportunities(account_id)
    ctas = plane.cs.list_ctas(account_id)
    success_plans = plane.cs.list_success_plans(account_id)
    entitlements = plane.telemetry.list_entitlements(account_id)
    usage_signals = plane.telemetry.list_usage_signals(account_id)
    usage_by_id = {signal.signal_id: signal for signal in usage_signals}

    scenarios = []
    for milestone in plane.telemetry.list_ttv_milestones(account_id):
        if milestone.achieved_at is not None:
            continue
        evidence_signals = [
            usage_by_id[signal_id]
            for signal_id in milestone.evidence_signal_ids
            if signal_id in usage_by_id
        ]
        scenarios.append(
            _simulate_milestone(
                milestone,
                simulation_date=simulation_date,
                contract_start=company.original_contract_date,
                account_name=account.name,
                lifecycle_stage=company.lifecycle_stage,
                health_score=health.score,
                health_band=health.band,
                health_drivers=health.drivers,
                adoption_rate=adoption.adoption_rate,
                underused_capabilities=adoption.underused_capabilities,
                open_case_ids=tuple(case.case_id for case in cases if case.closed_at is None),
                open_case_subjects=tuple(case.subject for case in cases if case.closed_at is None),
                opportunity_ids=tuple(opp.opportunity_id for opp in opportunities),
                cta_ids=tuple(cta.cta_id for cta in ctas),
                success_plan_ids=tuple(plan.plan_id for plan in success_plans),
                entitlement_capabilities=tuple(e.capability for e in entitlements),
                evidence_signals=evidence_signals,
            )
        )

    baseline_days = [s["baseline_agent_1_behavior"]["estimated_days_to_value"] for s in scenarios]
    improved_days = [s["improved_agent_1_behavior"]["estimated_days_to_value"] for s in scenarios]
    synthetic_delta = (
        round(mean(baseline_days) - mean(improved_days), 2)
        if baseline_days and improved_days
        else 0.0
    )
    work_queue_projection = _book_level_projection(work_queue_path)

    return {
        "artifact": "outcome_simulation_csm",
        "schema_version": 1,
        "generated_by": "eval.outcome_simulation_csm",
        "label": ARTIFACT_LABEL,
        "measurement_scope": (
            "Counterfactual Time-to-Value deltas over deterministic synthetic "
            "fixtures. Use this to test eval/training instrumentation only."
        ),
        "fixture_source": FIXTURE_SOURCE,
        "simulation_date": simulation_date,
        "data_sources": [
            "Salesforce-mapped CRM fixture",
            "Gainsight-mapped CS-platform fixture",
            "Product telemetry fixture",
        ],
        "accounts": [account_id],
        "scenarios": scenarios,
        "aggregate": {
            "scenario_count": len(scenarios),
            "synthetic_baseline_mean_days_to_value": round(mean(baseline_days), 2)
            if baseline_days
            else 0.0,
            "synthetic_improved_mean_days_to_value": round(mean(improved_days), 2)
            if improved_days
            else 0.0,
            "synthetic_delta_days": synthetic_delta,
            "claim": "not_real_customer_outcome_evidence",
        },
        "book_level_projection": work_queue_projection,
    }


def write_outcome_simulation(path: Path = ARTIFACT_PATH) -> dict[str, Any]:
    artifact = build_outcome_simulation()
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def _book_level_projection(work_queue_path: Path | None) -> dict[str, Any]:
    if work_queue_path is None or not work_queue_path.exists():
        return {
            "source": None,
            "work_item_count": 0,
            "escalation_count": 0,
            "synthetic_projected_ttv_days_saved": 0,
            "claim": "not_real_customer_outcome_evidence",
        }

    queue = json.loads(work_queue_path.read_text())
    work_items = queue.get("work_items", [])
    escalations = queue.get("escalations", [])
    proposed_items = [
        item for item in work_items
        if item.get("disposition") == "propose_customer_action"
    ]
    internal_items = [
        item for item in work_items
        if item.get("disposition") == "internal_review"
    ]
    projected_days = sum(
        min(item.get("priority", {}).get("score", 0) // 10, 14)
        for item in work_items
    )
    return {
        "source": _display_path(work_queue_path),
        "work_item_count": len(work_items),
        "proposed_action_count": len(proposed_items),
        "internal_review_count": len(internal_items),
        "escalation_count": len(escalations),
        "synthetic_projected_ttv_days_saved": int(projected_days),
        "claim": "synthetic_book_level_projection_not_real_customer_lift",
    }


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return str(path)


def _simulate_milestone(
    milestone: TimeToValueMilestone,
    *,
    simulation_date: str,
    contract_start: str,
    account_name: str,
    lifecycle_stage: str,
    health_score: float,
    health_band: str,
    health_drivers: tuple[str, ...],
    adoption_rate: float,
    underused_capabilities: tuple[str, ...],
    open_case_ids: tuple[str, ...],
    open_case_subjects: tuple[str, ...],
    opportunity_ids: tuple[str, ...],
    cta_ids: tuple[str, ...],
    success_plan_ids: tuple[str, ...],
    entitlement_capabilities: tuple[str, ...],
    evidence_signals: list[Any],
) -> dict[str, Any]:
    expected = _parse_date(milestone.expected_by)
    as_of = _parse_date(simulation_date)
    days_overdue = max((as_of - expected).days, 0)
    support_blocked = bool(open_case_ids)
    entitlement_gap = any(
        capability in underused_capabilities
        for capability in entitlement_capabilities
    )
    baseline_delay = 21 if support_blocked else 14
    improved_delay = 8 if support_blocked else 6
    if entitlement_gap and not support_blocked:
        improved_delay = 5

    baseline_date = expected + timedelta(days=baseline_delay)
    improved_date = expected + timedelta(days=improved_delay)
    contract_start_date = _parse_date(contract_start)

    return {
        "scenario_id": f"synthetic_ttv_{milestone.milestone}",
        "account_id": milestone.account_id,
        "account_name": account_name,
        "milestone": milestone.milestone,
        "expected_by": milestone.expected_by,
        "achieved_at": milestone.achieved_at,
        "days_overdue_as_of_simulation": days_overdue,
        "evidence": {
            "lifecycle_stage": lifecycle_stage,
            "health_score": health_score,
            "health_band": health_band,
            "health_drivers": list(health_drivers),
            "adoption_rate": adoption_rate,
            "underused_capabilities": list(underused_capabilities),
            "open_case_ids": list(open_case_ids),
            "open_case_subjects": list(open_case_subjects),
            "opportunity_ids": list(opportunity_ids),
            "cta_ids": list(cta_ids),
            "success_plan_ids": list(success_plan_ids),
            "entitlement_capabilities": list(entitlement_capabilities),
            "usage_signal_ids": [signal.signal_id for signal in evidence_signals],
            "usage_metrics": [
                {
                    "metric_name": signal.metric_name,
                    "value": signal.value,
                    "unit": signal.unit,
                    "observed_at": signal.observed_at,
                    "source_ref": signal.source_ref,
                }
                for signal in evidence_signals
            ],
        },
        "baseline_agent_1_behavior": {
            "policy": "weekly_manual_review_after_gap",
            "estimated_value_date": baseline_date.isoformat(),
            "estimated_days_to_value": (baseline_date - contract_start_date).days,
            "intervention": "CSM notices missed milestone during routine review",
        },
        "improved_agent_1_behavior": {
            "policy": "evidence_triggered_ttv_accelerator",
            "estimated_value_date": improved_date.isoformat(),
            "estimated_days_to_value": (improved_date - contract_start_date).days,
            "intervention": (
                "Agent 1 surfaces milestone gap with telemetry, entitlement, "
                "support, CTA, and success-plan evidence for gated CSM action"
            ),
        },
        "synthetic_delta_days": (baseline_date - improved_date).days,
        "outcome_claim": "synthetic_counterfactual_not_real_customer_lift",
    }


def _parse_date(value: str) -> date:
    if "T" in value:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    return date.fromisoformat(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ARTIFACT_PATH))
    args = parser.parse_args(argv)
    artifact = write_outcome_simulation(Path(args.output))
    print(
        "wrote "
        f"{args.output} "
        f"({artifact['aggregate']['scenario_count']} synthetic scenarios)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
