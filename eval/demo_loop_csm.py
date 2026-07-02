"""Offline demo loop: sweep, approve, commit, re-observe simulated state."""

from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import psycopg

from ultra_csm.agent1 import (
    FixtureReasonDraftWriter,
    ReasonDraftOutput,
    ReasonDraftRequest,
    SLOT_B_PROMPT_VERSION,
    run_time_to_value_sweep,
)
from ultra_csm.committers import (
    SimCrmActivityCommitter,
    SimOutboundCommitter,
    auto_approve_internal,
    load_action_proposal,
)
from ultra_csm.data_plane import DEFAULT_DEMO_STATE_DIR, DEFAULT_TENANT, SimTenantStore
from ultra_csm.governance import (
    ActionGate,
    FixtureVerdictSource,
    ROLE_CS_ORCHESTRATOR,
    ROLE_ORDER_CONFIRM_AUTHORITY,
    Verdict,
    make_principal,
    proposal_fields_for,
    seed_roster,
)
from ultra_csm.platform import boot_seeded_cluster, session
from ultra_csm.quality_breaker import QualityBreakerConfig, record_quality_breaker_reset
from ultra_csm.value_model import build_customer_value_model

REPO = Path(__file__).resolve().parents[1]
MIGRATIONS = REPO / "migrations"
ARTIFACT_PATH = Path(__file__).with_name("demo_loop_csm.json")
AS_OF_FIRST = "2026-06-27"
AS_OF_SECOND = "2026-06-28"


class FailingOnceLiveWriter:
    """Fake live writer for the degradation beat; first call errors, later calls succeed."""

    model_id = "fake-live-slot-b"
    prompt_version = SLOT_B_PROMPT_VERSION

    def __init__(self) -> None:
        self.calls = 0
        self.failures = 0
        self._fixture = FixtureReasonDraftWriter()

    def write(self, request: ReasonDraftRequest) -> ReasonDraftOutput:
        self.calls += 1
        if self.calls == 1:
            self.failures += 1
            raise RuntimeError("simulated live Slot B outage")
        output = self._fixture.write(request)
        return replace(output, model_id=self.model_id)


def build_demo_loop_artifact(
    *,
    state_dir: Path = DEFAULT_DEMO_STATE_DIR,
    output_path: Path = ARTIFACT_PATH,
) -> dict[str, Any]:
    store = SimTenantStore.seed(state_dir, tenant_id=DEFAULT_TENANT, reset=True)
    writer = FailingOnceLiveWriter()

    with boot_seeded_cluster(MIGRATIONS, limit=200) as (_cluster, dsn):
        with psycopg.connect(**dsn) as conn:
            orch, authority, gate_tenant_id = _setup_demo_roster(conn)
            gate = ActionGate(
                conn,
                tenant_id=gate_tenant_id,
                actor_principal_id=orch,
                verdict_source=FixtureVerdictSource(),
            )

            first = run_time_to_value_sweep(
                store.data_plane(),
                DEFAULT_TENANT,
                gate,
                sweep_principal_id=orch,
                as_of=AS_OF_FIRST,
                reason_draft_writer=writer,
            )
            auto_internal_receipt = _auto_commit_internal_recommendation(
                gate,
                store,
                system_principal_id=orch,
                account_id=first.work_items[0].account_id or "",
            )
            item = next(item for item in first.work_items if item.proposal is not None)
            proposal = load_action_proposal(
                conn,
                tenant_id=gate_tenant_id,
                actor_principal_id=orch,
                proposal_id=item.proposal.proposal_id,
            )
            outcome = gate.record_verdict(
                proposal,
                Verdict(
                    "approve",
                    human_principal_id=authority,
                    rationale="demo-loop approval",
                ),
                cause_ref=f"demo-loop:{proposal.proposal_id}",
            )
            outbound_receipt = SimOutboundCommitter(gate, state_dir=state_dir).commit(
                proposal,
                outcome,
            )
            crm_receipt = SimCrmActivityCommitter(gate, store).commit(proposal, outcome)
            idempotent_receipt = SimOutboundCommitter(gate, state_dir=state_dir).commit(
                proposal,
                outcome,
            )
            advance = store.advance_after_commits(as_of=AS_OF_SECOND)
            second = run_time_to_value_sweep(
                store.data_plane(),
                DEFAULT_TENANT,
                gate,
                sweep_principal_id=orch,
                as_of=AS_OF_SECOND,
            )
            quality_breaker = _quality_breaker_demo(
                gate,
                state_dir=state_dir,
                system_principal_id=orch,
            )

    artifact = {
        "artifact": "demo_loop_csm",
        "generated_by": "eval.demo_loop_csm",
        "claim_boundary": {
            "loop_closed_sim": True,
            "loop_closed_live": False,
            "writes_external_systems": False,
            "degradation_flagged": first.degraded_items > 0,
            "quality_breaker_exercised": (
                quality_breaker["red"]["triggered"]
                and not quality_breaker["after_operator_reset"]["triggered"]
            ),
        },
        "tenant_id": DEFAULT_TENANT,
        "first_sweep": _sweep_summary(first),
        "commits": {
            "auto_internal_recommendation": _stable_receipt(auto_internal_receipt),
            "outbound": _stable_receipt(outbound_receipt),
            "crm_activity": _stable_receipt(crm_receipt),
            "idempotent_outbound_retry": _stable_receipt(idempotent_receipt),
        },
        "advance": advance,
        "outcomes": [
            _outcome_summary(store, account_id)
            for account_id in advance["completed_accounts"]
        ],
        "second_sweep": _sweep_summary(second),
        "quality_breaker": quality_breaker,
        "writer": {
            "model_id": writer.model_id,
            "calls": writer.calls,
            "failures": writer.failures,
        },
    }
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def _setup_demo_roster(conn) -> tuple[str, str, str]:
    tenant_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "ultra-csm:demo-loop:tenant"))
    seed_actor = str(uuid.uuid5(uuid.NAMESPACE_URL, "ultra-csm:demo-loop:system-seed"))
    with session(conn, tenant_id=tenant_id, actor_id=seed_actor) as cur:
        cur.execute(
            "INSERT INTO tenant (tenant_id, name) VALUES (%s, %s) "
            "ON CONFLICT (tenant_id) DO NOTHING",
            (tenant_id, "demo-loop-tenant"),
        )
        cur.execute(
            "INSERT INTO principal (principal_id, tenant_id, kind, display_name) "
            "VALUES (%s, %s, 'agent', %s) ON CONFLICT (principal_id) DO NOTHING",
            (seed_actor, tenant_id, "system-seed"),
        )
    seed_roster(conn, tenant_id=tenant_id, actor_id=seed_actor)
    orch = make_principal(
        conn,
        tenant_id=tenant_id,
        actor_id=seed_actor,
        display_name="cs-orchestrator",
        role=ROLE_CS_ORCHESTRATOR,
    )
    authority = make_principal(
        conn,
        tenant_id=tenant_id,
        actor_id=seed_actor,
        display_name="demo-approval-authority",
        role=ROLE_ORDER_CONFIRM_AUTHORITY,
    )
    return orch, authority, tenant_id


def _auto_commit_internal_recommendation(
    gate: ActionGate,
    store: SimTenantStore,
    *,
    system_principal_id: str,
    account_id: str,
):
    proposal = gate.propose(
        intent="demo_internal_recommendation",
        payload={
            "account_id": account_id,
            "subject": "Review activation blockers",
            "body": "Internal next-best action for the CSM.",
            "as_of": AS_OF_FIRST,
        },
        grounding_ref=f"demo:{account_id}:internal",
        cause_ref=f"demo:auto-internal:{account_id}",
        **proposal_fields_for("recommend_next_best_action"),
    )
    outcome = auto_approve_internal(
        gate,
        proposal,
        system_principal_id=system_principal_id,
    )
    return SimCrmActivityCommitter(gate, store).commit(proposal, outcome)


def _quality_breaker_demo(
    gate: ActionGate,
    *,
    state_dir: Path,
    system_principal_id: str,
) -> dict[str, Any]:
    breaker_state_dir = state_dir / "quality_breaker"
    breaker_store = SimTenantStore.seed(
        breaker_state_dir,
        tenant_id=DEFAULT_TENANT,
        reset=True,
    )
    artifact_path = breaker_state_dir / "red_quality_artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "artifact": "demo_quality_artifact",
                "hard_ok": False,
                "hard_failures": ["demo_planted_quality_failure"],
            },
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    operator_events_path = breaker_state_dir / "operator_events.jsonl"
    if operator_events_path.exists():
        operator_events_path.unlink()
    config = QualityBreakerConfig(
        artifact_path=artifact_path,
        operator_events_path=operator_events_path,
    )
    red = run_time_to_value_sweep(
        breaker_store.data_plane(),
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=system_principal_id,
        as_of=AS_OF_FIRST,
        quality_breaker=config,
    )
    reset_event = record_quality_breaker_reset(
        config,
        operator_id=system_principal_id,
        rationale="demo operator reviewed quality artifact",
        recorded_at=AS_OF_SECOND,
    )
    cleared = run_time_to_value_sweep(
        breaker_store.data_plane(),
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=system_principal_id,
        as_of=AS_OF_SECOND,
        quality_breaker=config,
    )
    return {
        "red": {
            "triggered": bool(red.quality_breaker and red.quality_breaker["triggered"]),
            "state": red.quality_breaker["state"] if red.quality_breaker else None,
            "degraded_items": red.degraded_items,
            "customer_proposals": _proposal_count(red),
        },
        "operator_reset_event": {
            "event_id": reset_event["event_id"],
            "event_type": reset_event["event_type"],
        },
        "after_operator_reset": {
            "triggered": bool(
                cleared.quality_breaker
                and cleared.quality_breaker["triggered"]
            ),
            "state": cleared.quality_breaker["state"] if cleared.quality_breaker else None,
            "degraded_items": cleared.degraded_items,
            "customer_proposals": _proposal_count(cleared),
        },
    }


def _sweep_summary(sweep) -> dict[str, Any]:
    return {
        "tenant_id": sweep.tenant_id,
        "degraded_items": sweep.degraded_items,
        "swept_accounts": list(sweep.swept_accounts),
        "work_items": [
            {
                "account_id": item.account_id,
                "disposition": item.disposition,
                "draft_mode": item.draft_mode,
                "priority_score": item.priority.score if item.priority else None,
                "priority_factors": (
                    [factor.name for factor in item.priority.factors]
                    if item.priority
                    else []
                ),
                "proposal_id": _stable_proposal_id(item) if item.proposal else None,
            }
            for item in sweep.work_items
        ],
        "escalations": [
            {
                "candidate_account_ids": list(item.candidate_account_ids),
                "reason": item.reason,
            }
            for item in sweep.escalations
        ],
    }


def _proposal_count(sweep) -> int:
    return sum(1 for item in sweep.work_items if item.proposal is not None)


def _stable_receipt(receipt) -> dict[str, Any]:
    data = asdict(receipt)
    stable_proposal = f"runtime-generated:{receipt.account_id}:{receipt.action}"
    stable_key = f"runtime-generated:{receipt.account_id}:{receipt.action}:idempotency"
    data["proposal_id"] = stable_proposal
    data["idempotency_key"] = stable_key
    data["receipt_id"] = f"receipt:{receipt.account_id}:{receipt.action}:{receipt.target}"
    return data


def _stable_proposal_id(item) -> str:
    return f"runtime-generated:{item.account_id}:{item.proposal.action_type}"


def _outcome_summary(store: SimTenantStore, account_id: str) -> dict[str, Any]:
    data_plane = store.data_plane()
    account = data_plane.crm.get_account(account_id)
    company = data_plane.cs.get_company(account_id)
    health = data_plane.cs.get_health_score(account_id)
    adoption = data_plane.cs.get_adoption_summary(account_id)
    if account is None or company is None or health is None:
        raise RuntimeError(f"missing sim facts for account {account_id}")
    model = build_customer_value_model(
        account=account,
        company=company,
        health=health,
        adoption=adoption,
        entitlements=tuple(data_plane.telemetry.list_entitlements(account_id)),
        usage_signals=tuple(data_plane.telemetry.list_usage_signals(account_id)),
        success_plans=tuple(data_plane.cs.list_success_plans(account_id)),
    )
    return {
        "account_id": account_id,
        "realized_state": model.outcome.realized_state,
        "stated_objectives": list(model.outcome.stated_objectives),
        "source": "sim",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_DEMO_STATE_DIR)
    parser.add_argument("--output", type=Path, default=ARTIFACT_PATH)
    args = parser.parse_args()
    artifact = build_demo_loop_artifact(state_dir=args.state_dir, output_path=args.output)
    print(json.dumps({
        "artifact": str(args.output),
        "loop_closed_sim": artifact["claim_boundary"]["loop_closed_sim"],
        "degraded_items": artifact["first_sweep"]["degraded_items"],
        "completed_accounts": artifact["advance"]["completed_accounts"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
