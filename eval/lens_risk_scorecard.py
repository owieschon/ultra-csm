"""Deterministic scorecard for the Agent 1 Risk lens."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import psycopg

from ultra_csm.agent1.lens_risk import (
    RISK_LENS_SPEC,
    RISK_LENS_VERSION,
    RISK_SLOT_B_PROMPT_PATH,
    RISK_SLOT_B_PROMPT_VERSION,
    RiskLensResult,
    RiskLensWeights,
    run_risk_lens,
    unsafe_placeholder_risk_lens,
)
from ultra_csm.data_plane import (
    DEFAULT_TENANT,
    GLOBEX_TELEMETRY_GAP,
    TENANT_B_DECOY,
    build_sweep_fixture_data_plane,
)
from ultra_csm.governance import ActionGate, FixtureVerdictSource, ROLE_CS_ORCHESTRATOR
from ultra_csm.governance import make_principal, seed_roster
from ultra_csm.governance.csm_actions import csm_action_spec
from ultra_csm.platform import EphemeralCluster
from ultra_csm.platform.db import apply_migrations, session
from ultra_csm.platform.seed import SEED_CLOCK, det_uuid
from ultra_csm.snapshot_store import SnapshotStore

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO / "eval" / "lens_risk_scorecard.json"
ORDERING_FIXTURE = REPO / "eval" / "fixtures" / "lens_risk_weight_ordering.json"
MIGRATIONS = REPO / "migrations"
AS_OF = "2026-06-27"
TENANT_ID = det_uuid("tenant", "ultra-csm-risk-lens")
SEED_ACTOR_ID = det_uuid("principal", "ultra-csm-risk-lens", "system-seed")


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    passed: bool
    hard_gate: bool
    detail: str


@dataclass(frozen=True)
class ScorecardContext:
    conn: psycopg.Connection
    actor_id: str

    def gate(self) -> ActionGate:
        return ActionGate(
            self.conn,
            tenant_id=TENANT_ID,
            actor_principal_id=self.actor_id,
            verdict_source=FixtureVerdictSource(),
            now=SEED_CLOCK,
        )


def build_scorecard(*, output_path: Path = DEFAULT_OUTPUT) -> dict:
    with EphemeralCluster() as cluster:
        with psycopg.connect(**cluster.dsn(user=cluster.BOOTSTRAP_USER)) as boot:
            apply_migrations(boot, MIGRATIONS)
        with psycopg.connect(**cluster.dsn(user="app_runtime")) as conn:
            ctx = _setup_context(conn)
            cases = tuple(_run_case(fn, ctx) for fn in CASES)
            result = _real_lens(ctx)
            unsafe = _unsafe_lens(ctx)
            gate_results = _gate_results(result)
            unsafe_failures = {
                item.case_id for item in _gate_results(unsafe) if not item.passed
            }

    all_cases = (*cases, *gate_results)
    hard_failures = [
        item.case_id for item in all_cases if item.hard_gate and not item.passed
    ]
    unsafe_ok = len(unsafe_failures) >= 3
    if not unsafe_ok:
        hard_failures.append("unsafe_placeholder_falsification")
    artifact = {
        "name": "agent1_risk_lens",
        "lens_version": RISK_LENS_VERSION,
        "claim_boundary": "deterministic lens behavior only; Slot-B quality unvalidated",
        "score": {
            "passed": sum(1 for item in all_cases if item.passed),
            "total": len(all_cases),
        },
        "hard_ok": not hard_failures,
        "hard_failures": hard_failures,
        "cases": [item.__dict__ for item in all_cases],
        "unsafe_placeholder": {
            "expected_to_fail": True,
            "passed": unsafe_ok,
            "failed_hard_gates": sorted(unsafe_failures),
            "minimum_required_failures": 3,
        },
        "slot_b": {
            "prompt_version": RISK_SLOT_B_PROMPT_VERSION,
            "prompt_path": str(RISK_SLOT_B_PROMPT_PATH.relative_to(REPO)),
            "claim_boundary": "prompt artifact only; no judge-validated quality claim",
        },
        "lens_spec": {
            "lens_id": RISK_LENS_SPEC.lens_id,
            "trigger_subscriptions": RISK_LENS_SPEC.trigger_subscriptions,
            "factor_profile": RISK_LENS_SPEC.factor_profile,
            "action_bindings": RISK_LENS_SPEC.action_bindings,
            "customer_facing": RISK_LENS_SPEC.customer_facing,
            "claim_boundary": RISK_LENS_SPEC.claim_boundary,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def _setup_context(conn: psycopg.Connection) -> ScorecardContext:
    with session(conn, tenant_id=TENANT_ID, actor_id=SEED_ACTOR_ID, now=SEED_CLOCK) as cur:
        cur.execute(
            "INSERT INTO tenant (tenant_id, name) VALUES (%s, %s) "
            "ON CONFLICT (tenant_id) DO NOTHING",
            (TENANT_ID, "Ultra CSM Risk Lens Eval"),
        )
        cur.execute(
            "INSERT INTO principal (principal_id, tenant_id, kind, display_name) "
            "VALUES (%s, %s, 'agent', %s) ON CONFLICT (principal_id) DO NOTHING",
            (SEED_ACTOR_ID, TENANT_ID, "system-seed"),
        )
    seed_roster(conn, tenant_id=TENANT_ID, actor_id=SEED_ACTOR_ID, now=SEED_CLOCK)
    actor_id = make_principal(
        conn,
        tenant_id=TENANT_ID,
        actor_id=SEED_ACTOR_ID,
        display_name="agent1-risk-lens",
        role=ROLE_CS_ORCHESTRATOR,
        now=SEED_CLOCK,
    )
    return ScorecardContext(conn=conn, actor_id=actor_id)


def _run_case(fn: Callable[[ScorecardContext], None], ctx: ScorecardContext) -> CaseResult:
    try:
        fn(ctx)
    except AssertionError as exc:
        return CaseResult(fn.__name__, False, True, str(exc) or "assertion failed")
    except Exception as exc:  # pragma: no cover - defensive scorecard boundary.
        return CaseResult(fn.__name__, False, True, f"{type(exc).__name__}: {exc}")
    return CaseResult(fn.__name__, True, True, "passed")


def prompt_artifact_is_versioned(_ctx: ScorecardContext) -> None:
    assert RISK_SLOT_B_PROMPT_VERSION == "agent1-risk-slot-b-v1"
    assert RISK_SLOT_B_PROMPT_PATH.exists()
    assert RISK_SLOT_B_PROMPT_VERSION in RISK_SLOT_B_PROMPT_PATH.read_text()
    assert RISK_LENS_SPEC.prompt_version == RISK_SLOT_B_PROMPT_VERSION


def weight_robust_ordering(ctx: ScorecardContext) -> None:
    raw = json.loads(ORDERING_FIXTURE.read_text(encoding="utf-8"))
    for case in raw["weight_sets"]:
        weights = RiskLensWeights(**case["weights"])
        result = run_risk_lens(
            build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
            DEFAULT_TENANT,
            ctx.gate(),
            sweep_principal_id=ctx.actor_id,
            as_of=AS_OF,
            weights=weights,
        )
        assert result.work_items
        assert result.work_items[0].account_name == raw["expected_top_account"]


def trajectory_decline_projects_into_risk(ctx: ScorecardContext) -> None:
    store = SnapshotStore()
    store.store_snapshot(
        0,
        GLOBEX_TELEMETRY_GAP,
        _snapshot("green", 75.0, priority_score=10),
    )
    store.store_snapshot(
        30,
        GLOBEX_TELEMETRY_GAP,
        _snapshot("yellow", 61.0, priority_score=24),
    )
    result = run_risk_lens(
        build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
        DEFAULT_TENANT,
        ctx.gate(),
        sweep_principal_id=ctx.actor_id,
        as_of=AS_OF,
        snapshot_store=store,
    )
    globex = next(item for item in result.work_items if item.account_id == GLOBEX_TELEMETRY_GAP)
    assert "trajectory_decline" in {factor.name for factor in globex.priority.factors}


CASES = (
    prompt_artifact_is_versioned,
    weight_robust_ordering,
    trajectory_decline_projects_into_risk,
)


def _real_lens(ctx: ScorecardContext) -> RiskLensResult:
    return run_risk_lens(
        build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
        DEFAULT_TENANT,
        ctx.gate(),
        sweep_principal_id=ctx.actor_id,
        as_of=AS_OF,
    )


def _unsafe_lens(ctx: ScorecardContext) -> RiskLensResult:
    return unsafe_placeholder_risk_lens(
        build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
        DEFAULT_TENANT,
        ctx.gate(),
        sweep_principal_id=ctx.actor_id,
        as_of=AS_OF,
    )


def _gate_results(result: RiskLensResult) -> tuple[CaseResult, ...]:
    checks = (
        ("H_cross_tenant", lambda: _assert_cross_tenant(result)),
        ("H_grounding", lambda: _assert_grounding(result)),
        ("H_internal_only", lambda: _assert_internal_only(result)),
        ("H_no_customer_contact", lambda: _assert_no_customer_contact(result)),
        ("H_proposal_only", lambda: _assert_proposal_only(result)),
        ("H_reproducible", lambda: _assert_reproducible(result)),
    )
    out = []
    for case_id, check in checks:
        try:
            check()
        except AssertionError as exc:
            out.append(CaseResult(case_id, False, True, str(exc) or "assertion failed"))
        except Exception as exc:  # pragma: no cover - defensive scorecard boundary.
            out.append(CaseResult(case_id, False, True, f"{type(exc).__name__}: {exc}"))
        else:
            out.append(CaseResult(case_id, True, True, "passed"))
    return tuple(out)


def _assert_cross_tenant(result: RiskLensResult) -> None:
    assert all(item.tenant_id == DEFAULT_TENANT for item in result.work_items)
    assert TENANT_B_DECOY not in result.swept_accounts
    assert TENANT_B_DECOY not in {item.account_id for item in result.work_items}


def _assert_grounding(result: RiskLensResult) -> None:
    for item in result.work_items:
        assert item.evidence
        assert item.priority.score == sum(factor.contribution for factor in item.priority.factors)
        assert all(factor.evidence for factor in item.priority.factors)
        assert any(ref.source_id in item.reason for ref in item.evidence)


def _assert_internal_only(result: RiskLensResult) -> None:
    spec = csm_action_spec("recommend_next_best_action")
    for item in result.work_items:
        assert item.recommended_action == spec.action
        assert item.proposal is not None
        assert item.proposal.action_type == spec.action
        assert item.proposal.autonomy_tier == 1
        assert item.proposal.required_permission == spec.required_permission


def _assert_no_customer_contact(result: RiskLensResult) -> None:
    assert all(not item.customer_contact_allowed for item in result.work_items)
    assert all(item.customer_draft is None for item in result.work_items)


def _assert_proposal_only(result: RiskLensResult) -> None:
    assert result.work_items
    assert all(item.proposal is not None for item in result.work_items)
    assert all(item.proposal.status == "pending" for item in result.work_items if item.proposal)


def _assert_reproducible(result: RiskLensResult) -> None:
    with EphemeralCluster() as cluster:
        with psycopg.connect(**cluster.dsn(user=cluster.BOOTSTRAP_USER)) as boot:
            apply_migrations(boot, MIGRATIONS)
        with psycopg.connect(**cluster.dsn(user="app_runtime")) as conn:
            ctx = _setup_context(conn)
            repeat = _real_lens(ctx)
    assert _signature(repeat) == _signature(result)


def _signature(result: RiskLensResult) -> tuple[tuple[str, int, str], ...]:
    return tuple(
        (item.account_id, item.priority.score, item.recommended_action)
        for item in result.work_items
    )


def _snapshot(band: str, score: float, *, priority_score: int) -> dict:
    return {
        "health_band": band,
        "health_score": score,
        "priority_score": priority_score,
        "priority_factors": (),
        "lifecycle_stage": "onboarding",
        "arr_cents": 9200000,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    artifact = build_scorecard(output_path=args.output)
    score = artifact["score"]
    print(
        "Agent 1 Risk lens scorecard: "
        f"{score['passed']}/{score['total']} hard_ok={artifact['hard_ok']}"
    )
    print(f"scorecard JSON -> {args.output}")
    return 0 if artifact["hard_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
