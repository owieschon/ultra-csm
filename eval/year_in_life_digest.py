"""Credentialed year-in-the-life demo digest for the synthetic book.

The digest is a demo artifact, not an eval artifact: it may store full draft
text because the tenant is fictional. The deterministic spine is still checked
before live drafting so the model only changes wording, not account ordering or
priority values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg

from ultra_csm.agent1 import (
    AnthropicReasonDraftWriter,
    FixtureReasonDraftWriter,
    ReasonDraftRequest,
    ReasonDraftWriter,
    SlotBEvidence,
    SlotBPriority,
    SlotBPriorityFactor,
    run_time_to_value_sweep,
)
from ultra_csm.cost_tracker import CostTracker, estimate_call_cost
from ultra_csm.data_plane import (
    DEFAULT_DEMO_STATE_DIR,
    DEFAULT_TENANT,
    CustomerDataPlane,
    FixtureCRMDataConnector,
    FixtureCSPlatformConnector,
    FixtureCustomerData,
    FixtureProductTelemetryConnector,
)
from ultra_csm.data_plane.book_simulator import simulate_book
from ultra_csm.data_plane.synthetic_book import SEED_DATE, build_synthetic_book
from ultra_csm.governance import (
    ActionGate,
    FixtureVerdictSource,
    ROLE_CS_ORCHESTRATOR,
    make_principal,
    seed_roster,
)
from ultra_csm.platform import boot_seeded_cluster, session

REPO = Path(__file__).resolve().parents[1]
MIGRATIONS = REPO / "migrations"
DEFAULT_OUTPUT_PATH = DEFAULT_DEMO_STATE_DIR / "year_in_life_digest.json"
DEFAULT_DAYS = (0, 30, 60, 90, 120, 180, 270, 365)


def build_year_in_life_digest(
    *,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    days: tuple[int, ...] = DEFAULT_DAYS,
    top_n: int = 2,
    deep: bool = True,
    live: bool = False,
    model_id: str | None = None,
    max_cost_usd: float = 1.0,
) -> dict[str, Any]:
    """Build and write the year-in-the-life digest artifact."""

    if top_n < 1:
        raise ValueError("top_n must be >= 1")
    if not days:
        raise ValueError("at least one day is required")
    if live and not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is required for --live")

    base_book = build_synthetic_book()
    base_date = datetime.strptime(SEED_DATE, "%Y-%m-%d")
    cost_tracker = CostTracker()
    writer: ReasonDraftWriter = (
        AnthropicReasonDraftWriter(model_id=model_id, cost_tracker=cost_tracker)
        if live
        else FixtureReasonDraftWriter()
    )
    model_label = writer.model_id
    snapshots: list[dict[str, Any]] = []

    with boot_seeded_cluster(MIGRATIONS, limit=200) as (_cluster, dsn):
        with psycopg.connect(**dsn) as conn:
            principal, tenant_id = _setup_roster(conn)
            gate = ActionGate(
                conn,
                tenant_id=tenant_id,
                actor_principal_id=principal,
                verdict_source=FixtureVerdictSource(),
            )

            for day_index, day in enumerate(days, 1):
                as_of = (base_date + timedelta(days=day)).strftime("%Y-%m-%d")
                data = _data_for_day(base_book, day, deep=deep)
                plane = _plane(data)
                spine = _deterministic_sweep(
                    plane,
                    gate,
                    principal_id=principal,
                    as_of=as_of,
                )
                repeat = _deterministic_sweep(
                    plane,
                    gate,
                    principal_id=principal,
                    as_of=as_of,
                )
                spine_hash = _spine_hash(spine)
                if spine_hash != _spine_hash(repeat):
                    raise RuntimeError(f"deterministic spine mismatch at day {day}")

                eligible = tuple(
                    item for item in spine.work_items
                    if item.priority is not None and item.customer_contact_allowed
                )[:top_n]
                print(
                    f"[year-in-life] day {day_index}/{len(days)} "
                    f"offset={day} eligible={len(eligible)}",
                    flush=True,
                )

                drafted: list[dict[str, Any]] = []
                for item_index, item in enumerate(eligible, 1):
                    if item.account_id is None or item.recommended_action is None:
                        continue
                    estimated = estimate_call_cost(model_label)
                    if cost_tracker.current_sweep_cost + estimated > max_cost_usd:
                        raise RuntimeError(
                            "configured digest cost budget would be exceeded "
                            f"before day={day} item={item_index}"
                        )

                    print(
                        f"[year-in-life] drafting {item_index}/{len(eligible)} "
                        f"day={day} account={item.account_id}",
                        flush=True,
                    )
                    request = _request_for_item(
                        plane,
                        item,
                        as_of=as_of,
                    )
                    output = writer.write(request)
                    drafted.append({
                        "account_id": item.account_id,
                        "account_name": request.account_name,
                        "priority_score": item.priority.score,
                        "priority_factors": [
                            factor.name for factor in item.priority.factors
                        ],
                        "health_band": _health_band(plane, item.account_id),
                        "draft_mode": "live" if live else "fixture",
                        "model_id": output.model_id,
                        "prompt_version": output.prompt_version,
                        "reason": output.reason,
                        "customer_draft": output.customer_draft,
                        "cited_evidence_ids": list(output.cited_evidence_ids),
                    })

                snapshots.append({
                    "day": day,
                    "as_of": as_of,
                    "deterministic_spine_hash": spine_hash,
                    "selected_accounts": drafted,
                })

    artifact = {
        "artifact": "year_in_life_digest",
        "generated_by": "eval.year_in_life_digest",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "claim_boundary": {
            "simulation": True,
            "live_tenant": False,
            "external_writes": False,
            "contains_full_synthetic_drafts": True,
            "judge_validated_quality": False,
            "deterministic_spine_verified": True,
        },
        "config": {
            "days": list(days),
            "top_n": top_n,
            "deep": deep,
            "live": live,
            "model_id": model_label,
            "max_cost_usd": max_cost_usd,
        },
        "cost": {
            "summary": cost_tracker.stats(),
            "per_account": cost_tracker.cost_per_account(),
        },
        "snapshots": snapshots,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return artifact


def _data_for_day(base_book: FixtureCustomerData, day: int, *, deep: bool) -> FixtureCustomerData:
    data = base_book if day == 0 else simulate_book(base_book, day_offset=day)
    if deep:
        from ultra_csm.cli import _apply_deep_data_overlay

        return _apply_deep_data_overlay(data, day)
    return data


def _plane(data: FixtureCustomerData) -> CustomerDataPlane:
    return CustomerDataPlane(
        crm=FixtureCRMDataConnector(data=data),
        cs=FixtureCSPlatformConnector(data=data),
        telemetry=FixtureProductTelemetryConnector(data=data),
    )


def _setup_roster(conn) -> tuple[str, str]:
    tenant_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "ultra-csm:year-in-life-digest:tenant"))
    seed_actor = str(uuid.uuid5(uuid.NAMESPACE_URL, "ultra-csm:year-in-life-digest"))
    with session(conn, tenant_id=tenant_id, actor_id=seed_actor) as cur:
        cur.execute(
            "INSERT INTO tenant (tenant_id, name) VALUES (%s, %s) "
            "ON CONFLICT (tenant_id) DO NOTHING",
            (tenant_id, "year-in-life-digest"),
        )
        cur.execute(
            "INSERT INTO principal (principal_id, tenant_id, kind, display_name) "
            "VALUES (%s, %s, 'agent', %s) ON CONFLICT (principal_id) DO NOTHING",
            (seed_actor, tenant_id, "year-in-life-digest"),
        )
    seed_roster(conn, tenant_id=tenant_id, actor_id=seed_actor)
    principal = make_principal(
        conn,
        tenant_id=tenant_id,
        actor_id=seed_actor,
        display_name="year-in-life-digest",
        role=ROLE_CS_ORCHESTRATOR,
    )
    return principal, tenant_id


def _deterministic_sweep(
    plane: CustomerDataPlane,
    gate: ActionGate,
    *,
    principal_id: str,
    as_of: str,
):
    return run_time_to_value_sweep(
        plane,
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=principal_id,
        as_of=as_of,
        reason_draft_writer=FixtureReasonDraftWriter(),
    )


def _request_for_item(
    plane: CustomerDataPlane,
    item,
    *,
    as_of: str,
) -> ReasonDraftRequest:
    if item.account_id is None or item.priority is None or item.recommended_action is None:
        raise ValueError("work item cannot be drafted")
    account = plane.crm.get_account(item.account_id)
    if account is None:
        raise ValueError(f"missing account: {item.account_id}")
    contacts = tuple(plane.crm.list_contacts(item.account_id))
    contact = next((contact for contact in contacts if contact.consent_to_contact), None)
    return ReasonDraftRequest(
        tenant_id=item.tenant_id,
        account_id=item.account_id,
        account_name=account.name,
        disposition=item.disposition,
        recommended_action=item.recommended_action,
        customer_contact_allowed=item.customer_contact_allowed,
        priority=SlotBPriority(
            score=item.priority.score,
            factors=tuple(
                SlotBPriorityFactor(
                    factor.name,
                    factor.value,
                    factor.contribution,
                )
                for factor in item.priority.factors
            ),
        ),
        evidence=tuple(
            SlotBEvidence(ref.source, ref.source_id, ref.field, ref.observed_at)
            for ref in item.evidence
        ),
        as_of=as_of,
        contact_name=contact.name if contact else None,
        contact_email=contact.email if contact else None,
        untrusted_text_fragments=tuple(
            case.subject
            for case in plane.crm.list_cases(item.account_id)
            if case.subject
        ),
    )


def _spine_hash(sweep) -> str:
    rows = []
    for item in sweep.work_items:
        rows.append({
            "account_id": item.account_id,
            "disposition": item.disposition,
            "recommended_action": item.recommended_action,
            "priority": asdict(item.priority) if item.priority else None,
            "evidence": [asdict(ref) for ref in item.evidence],
        })
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _health_band(plane: CustomerDataPlane, account_id: str) -> str | None:
    health = plane.cs.get_health_score(account_id)
    return health.band if health else None


def _parse_days(raw: str) -> tuple[int, ...]:
    return tuple(int(part.strip()) for part in raw.split(",") if part.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Use live Slot B writer")
    parser.add_argument("--model", default=None, help="Override live model id")
    parser.add_argument("--top-n", type=int, default=2)
    parser.add_argument("--days", default=",".join(str(day) for day in DEFAULT_DAYS))
    parser.add_argument("--max-cost-usd", type=float, default=1.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--no-deep", action="store_true")
    args = parser.parse_args(argv)

    try:
        artifact = build_year_in_life_digest(
            output_path=args.output,
            days=_parse_days(args.days),
            top_n=args.top_n,
            deep=not args.no_deep,
            live=args.live,
            model_id=args.model,
            max_cost_usd=args.max_cost_usd,
        )
    except Exception as exc:
        print(f"year-in-life digest failed: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "artifact": str(args.output),
                "snapshots": len(artifact["snapshots"]),
                "live": artifact["config"]["live"],
                "total_cost_usd": artifact["cost"]["summary"]["total_cost_usd"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
