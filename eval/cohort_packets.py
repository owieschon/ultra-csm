"""Deterministic fixture artifact for manager cohort packets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ultra_csm.cohort_packets import (
    artifact_sha256,
    build_cohort_packets_artifact,
)
from ultra_csm.data_plane import FixtureCustomerData
from ultra_csm.data_plane.synthetic_book import SEED_DATE, build_synthetic_book
from ultra_csm.snapshot_store import SnapshotStore

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO / "eval" / "cohort_packets.json"


def build_fixture_artifact(output_path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    data = build_synthetic_book()
    first = _base_artifact(data)
    second = _base_artifact(data)
    first_hash = artifact_sha256(first)
    second_hash = artifact_sha256(second)
    if first_hash != second_hash:
        raise RuntimeError("cohort packet repeatability check failed")

    artifact = {
        **first,
        "as_of": SEED_DATE,
        "repeatability": {
            "matched": True,
            "first_sha256": first_hash,
            "second_sha256": second_hash,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def _base_artifact(data: FixtureCustomerData) -> dict[str, Any]:
    return build_cohort_packets_artifact(
        data,
        snapshots=_fixture_snapshots(data),
        divergence_patterns=_fixture_divergence_patterns(data),
        tick_ledger=_fixture_tick_ledger(data),
        action_packets=_fixture_action_packets(data),
    )


def _fixture_snapshots(data: FixtureCustomerData) -> SnapshotStore:
    store = SnapshotStore()
    companies = {company.company_id: company for company in data.companies}
    for index, health in enumerate(sorted(data.health_scores, key=lambda item: item.account_id)):
        company = companies[health.account_id]
        start_score = health.score
        if index % 5 == 0:
            start_score = min(100.0, health.score + 7.0)
        elif index % 5 == 1:
            start_score = max(0.0, health.score - 7.0)
        store.store_snapshot(0, health.account_id, _snapshot_payload(company, health, start_score))
        store.store_snapshot(30, health.account_id, _snapshot_payload(company, health, health.score))
    return store


def _snapshot_payload(company, health, score: float) -> dict[str, Any]:  # noqa: ANN001
    return {
        "health_band": health.band,
        "health_score": score,
        "priority_score": 0,
        "priority_factors": (),
        "lifecycle_stage": company.lifecycle_stage,
        "arr_cents": company.arr_cents,
    }


def _fixture_divergence_patterns(data: FixtureCustomerData) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for adoption in sorted(data.adoption_summaries, key=lambda item: item.account_id):
        if adoption.underused_capabilities:
            records.append({
                "account_id": adoption.account_id,
                "pattern": "observed_underused_entitlement",
            })
    for case in sorted(data.cases, key=lambda item: item.case_id):
        if case.status.lower() == "open":
            records.append({
                "account_id": case.account_id,
                "pattern": "observed_open_support_pressure",
            })
    return records


def _fixture_tick_ledger(data: FixtureCustomerData) -> list[dict[str, str]]:
    health = {score.account_id: score for score in data.health_scores}
    records: list[dict[str, str]] = []
    for company in sorted(data.companies, key=lambda item: item.company_id):
        if company.lifecycle_stage == "renewal":
            records.append({
                "account_id": company.company_id,
                "trigger_name": "renewal_window",
                "event_type": "trigger_fired",
            })
        if health[company.company_id].band == "red":
            records.append({
                "account_id": company.company_id,
                "trigger_name": "band_drop",
                "event_type": "trigger_fired",
            })
        if company.lifecycle_stage == "at_risk":
            records.append({
                "account_id": company.company_id,
                "event_type": "hold_created",
            })
    for company in sorted(data.companies, key=lambda item: item.company_id)[:2]:
        records.append({
            "account_id": company.company_id,
            "event_type": "hold_released",
        })
    return records


def _fixture_action_packets(data: FixtureCustomerData) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for opportunity in sorted(data.opportunities, key=lambda item: item.opportunity_id):
        status = "pending"
        if opportunity.opportunity_type.lower() == "renewal":
            status = "approved"
        records.append({
            "account_id": opportunity.account_id,
            "proposal": {
                "status": status,
                "action_type": opportunity.opportunity_type.lower(),
            },
        })
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    artifact = build_fixture_artifact(args.output)
    print(json.dumps({
        "artifact": str(args.output),
        "packet_count": artifact["packet_count"],
        "repeatability_matched": artifact["repeatability"]["matched"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
