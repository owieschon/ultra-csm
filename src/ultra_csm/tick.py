"""The deterministic Ultra CSM tick runner.

Tick is an externally driven beat. It observes the simulated book at ``as_of``,
evaluates trigger config, runs existing sweep functions for fired work, and
records a ledger. It is not a daemon, queue, webhook server, or scheduler.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg

from ultra_csm.agent1 import SweepResult, collapse_cohorts, run_time_to_value_sweep
from ultra_csm.agent1.lens_expansion import ExpansionLensResult, run_expansion_lens
from ultra_csm.agent1.lens_risk import RiskLensResult, run_risk_lens
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
from ultra_csm.knowledge import load_playbooks
from ultra_csm.logging_config import setup_logging
from ultra_csm.platform import boot_seeded_cluster, session
from ultra_csm.platform.seed import SEED_CLOCK
from ultra_csm.snapshot_store import SnapshotStore
from ultra_csm.triggers import (
    AccountTriggerState,
    DEFAULT_TRIGGER_CONFIG_PATH,
    FiredTrigger,
    TriggerConfig,
    TriggerEvaluation,
    TriggerRuntime,
    TriggerState,
    evaluate_trigger_decisions,
    load_trigger_config,
    parse_trigger_config,
)
from ultra_csm.value_model import build_customer_value_model, load_value_model_config, project_ttv_lens

log = logging.getLogger(__name__)

# tick is fleetops/ultra-demo-only by construction (verified Report 23):
# fleetops' own book IS the fixture book tick.py drives, and no other
# tenant has a tick.py-equivalent daily driver. Unconditional per Decisions.
TICK_PLAYBOOK_TENANT_SLUG = "fleetops"

REPO = Path(__file__).resolve().parents[2]
MIGRATIONS = REPO / "migrations"
DEFAULT_TICK_LEDGER = DEFAULT_DEMO_STATE_DIR / "tick_ledger.jsonl"
TICK_TENANT_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "ultra-csm:tick:tenant"))
TICK_SEED_ACTOR_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "ultra-csm:tick:system-seed"))
BOOK_ACCOUNT = "__book__"


class TickError(RuntimeError):
    """A tick precondition failed."""


@dataclass(frozen=True)
class TickGateContext:
    conn: psycopg.Connection
    tenant_id: str
    actor_principal_id: str

    def gate(self) -> ActionGate:
        return ActionGate(
            self.conn,
            tenant_id=self.tenant_id,
            actor_principal_id=self.actor_principal_id,
            verdict_source=FixtureVerdictSource(),
            now=SEED_CLOCK,
        )


@dataclass(frozen=True)
class ObservedTickState:
    day: int
    as_of: str
    data: FixtureCustomerData
    data_plane: CustomerDataPlane
    trigger_state: TriggerState
    snapshot_payloads: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class TickResult:
    as_of: str
    day: int
    dry_run: bool
    evaluation: TriggerEvaluation
    artifacts_written: tuple[str, ...]
    ledger_entry: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "day": self.day,
            "dry_run": self.dry_run,
            "fired_triggers": [item.to_dict() for item in self.evaluation.fired],
            "suppressions": [item.to_dict() for item in self.evaluation.suppressions],
            "artifacts_written": list(self.artifacts_written),
            "ledger_entry": self.ledger_entry,
        }


def setup_tick_roster(conn: psycopg.Connection) -> TickGateContext:
    """Seed a deterministic offline principal for tick-driven proposals."""

    with session(conn, tenant_id=TICK_TENANT_ID, actor_id=TICK_SEED_ACTOR_ID, now=SEED_CLOCK) as cur:
        cur.execute(
            "INSERT INTO tenant (tenant_id, name) VALUES (%s, %s) "
            "ON CONFLICT (tenant_id) DO NOTHING",
            (TICK_TENANT_ID, "tick-runner-tenant"),
        )
        cur.execute(
            "INSERT INTO principal (principal_id, tenant_id, kind, display_name) "
            "VALUES (%s, %s, 'agent', %s) ON CONFLICT (principal_id) DO NOTHING",
            (TICK_SEED_ACTOR_ID, TICK_TENANT_ID, "system-seed"),
        )
    seed_roster(conn, tenant_id=TICK_TENANT_ID, actor_id=TICK_SEED_ACTOR_ID, now=SEED_CLOCK)
    actor = make_principal(
        conn,
        tenant_id=TICK_TENANT_ID,
        actor_id=TICK_SEED_ACTOR_ID,
        display_name="csm-tick-runner",
        role=ROLE_CS_ORCHESTRATOR,
        now=SEED_CLOCK,
    )
    return TickGateContext(
        conn=conn,
        tenant_id=TICK_TENANT_ID,
        actor_principal_id=actor,
    )


def run_tick(
    *,
    as_of: str,
    config_path: Path = DEFAULT_TRIGGER_CONFIG_PATH,
    state_dir: Path = DEFAULT_DEMO_STATE_DIR,
    dry_run: bool = False,
    conn: psycopg.Connection | None = None,
    gate_context: TickGateContext | None = None,
) -> TickResult:
    """Run one offline tick over the synthetic sim lane."""

    config = load_trigger_config(config_path)
    return run_tick_with_config(
        as_of=as_of,
        config=config,
        state_dir=state_dir,
        dry_run=dry_run,
        conn=conn,
        gate_context=gate_context,
    )


def run_tick_with_config(
    *,
    as_of: str,
    config: TriggerConfig,
    state_dir: Path = DEFAULT_DEMO_STATE_DIR,
    dry_run: bool = False,
    conn: psycopg.Connection | None = None,
    gate_context: TickGateContext | None = None,
) -> TickResult:
    observed = observe_sim_state(as_of)
    ledger_path = state_dir / "tick_ledger.jsonl"
    ledger_entries = _read_ledger(ledger_path)
    prev_snapshot = _previous_snapshot_from_ledger(ledger_entries)
    pending = _pending_trigger_accounts(
        ledger_entries,
        conn=conn,
        gate_context=gate_context,
    )
    runtime = _runtime_from_ledger(ledger_entries, pending_trigger_accounts=pending)
    evaluation = evaluate_trigger_decisions(
        observed.trigger_state,
        prev_snapshot,
        observed.as_of,
        config.with_runtime(runtime),
    )

    if dry_run:
        return TickResult(
            as_of=observed.as_of,
            day=observed.day,
            dry_run=True,
            evaluation=evaluation,
            artifacts_written=(),
            ledger_entry=None,
        )

    if conn is None:
        raise TickError("run_tick_with_config requires conn when dry_run=False")
    gate_context = gate_context or setup_tick_roster(conn)
    gate = gate_context.gate()
    snapshot_store = _snapshot_store(prev_snapshot, observed)
    playbooks = load_playbooks(TICK_PLAYBOOK_TENANT_SLUG)
    value_model_config = load_value_model_config()

    fired_runs: list[dict[str, Any]] = []
    fired_for_ledger: list[dict[str, Any]] = []
    for fired in evaluation.fired:
        sweep_data = (
            observed.data
            if fired.action.scope == "book"
            else _restrict_fixture_data(observed.data, fired.account_id)
        )
        lens_data_plane = _data_plane_from_fixture(sweep_data)
        if fired.action.lens == "risk":
            lens_result = run_risk_lens(
                lens_data_plane,
                DEFAULT_TENANT,
                gate,
                sweep_principal_id=gate_context.actor_principal_id,
                as_of=observed.as_of,
                snapshot_store=snapshot_store,
            )
            run_payload = _lens_payload_for_trigger(lens_result, fired)
        elif fired.action.lens == "expansion":
            lens_result = run_expansion_lens(
                lens_data_plane,
                DEFAULT_TENANT,
                gate,
                sweep_principal_id=gate_context.actor_principal_id,
                as_of=observed.as_of,
                snapshot_store=snapshot_store,
            )
            run_payload = _lens_payload_for_trigger(lens_result, fired)
        else:
            sweep = run_time_to_value_sweep(
                lens_data_plane,
                DEFAULT_TENANT,
                gate,
                sweep_principal_id=gate_context.actor_principal_id,
                as_of=observed.as_of,
                snapshot_store=snapshot_store,
                playbook_tenant_slug=TICK_PLAYBOOK_TENANT_SLUG,
            )
            # Cohort collapse needs the whole book (not the per-trigger
            # restricted sweep_data) to see every account's tier+triggers, per
            # collapse_cohorts' own docstring -- same tenant_id/playbooks/config
            # as the sweep above, just an unrestricted data_plane for detection.
            # TTV-lens-specific: risk/expansion lenses do not use cohort
            # collapse or playbook motion resolution (report 51 Decisions).
            sweep = collapse_cohorts(
                sweep,
                observed.data_plane,
                tenant_id=DEFAULT_TENANT,
                playbooks=playbooks,
                value_model_config=value_model_config,
                as_of=observed.as_of,
            )
            run_payload = _sweep_payload_for_trigger(sweep, fired)
        fired_runs.append(run_payload)
        fired_for_ledger.append({
            **fired.to_dict(),
            "created_proposals": run_payload["created_proposals"],
        })

    artifacts = _write_tick_artifacts(
        state_dir=state_dir,
        observed=observed,
        evaluation=evaluation,
        fired_runs=tuple(fired_runs),
    )
    ledger_entry = {
        "artifact": "tick_ledger_entry",
        "claim_boundary": {"sim": True, "live": False},
        "as_of": observed.as_of,
        "day": observed.day,
        "config_version": config.config_version,
        "fired_triggers": fired_for_ledger,
        "suppressions": [item.to_dict() for item in evaluation.suppressions],
        "artifacts_written": artifacts,
        "snapshot": observed.trigger_state.to_dict(),
    }
    _append_jsonl(ledger_path, ledger_entry)
    return TickResult(
        as_of=observed.as_of,
        day=observed.day,
        dry_run=False,
        evaluation=evaluation,
        artifacts_written=tuple(artifacts),
        ledger_entry=ledger_entry,
    )


def observe_sim_state(as_of: str | date | datetime) -> ObservedTickState:
    as_of_date = _parse_date(as_of)
    seed = date.fromisoformat(SEED_DATE)
    day = (as_of_date - seed).days
    if day < 0 or day > 365:
        raise TickError(f"as_of must be within the 365-day sim lane: {as_of_date.isoformat()}")
    base = build_synthetic_book()
    data = base if day == 0 else simulate_book(base, day_offset=day)
    data_plane = _data_plane_from_fixture(data)
    trigger_state, snapshot_payloads = _trigger_state_from_data(
        data_plane,
        as_of=as_of_date.isoformat(),
        day=day,
    )
    return ObservedTickState(
        day=day,
        as_of=as_of_date.isoformat(),
        data=data,
        data_plane=data_plane,
        trigger_state=trigger_state,
        snapshot_payloads=snapshot_payloads,
    )


def run_tick_cli(
    *,
    as_of: str,
    config_path: Path = DEFAULT_TRIGGER_CONFIG_PATH,
    state_dir: Path = DEFAULT_DEMO_STATE_DIR,
    dry_run: bool = False,
    json_output: bool = False,
) -> int:
    if dry_run:
        result = run_tick(as_of=as_of, config_path=config_path, state_dir=state_dir, dry_run=True)
    else:
        with boot_seeded_cluster(MIGRATIONS, limit=200) as (_cluster, dsn):
            with psycopg.connect(**dsn) as conn:
                context = setup_tick_roster(conn)
                result = run_tick(
                    as_of=as_of,
                    config_path=config_path,
                    state_dir=state_dir,
                    dry_run=False,
                    conn=conn,
                    gate_context=context,
                )
    if json_output:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        _print_tick_result(result)
    return 0


def build_tick_demo(
    *,
    state_dir: Path = DEFAULT_DEMO_STATE_DIR / "tick_demo",
) -> dict[str, Any]:
    if state_dir.exists():
        shutil.rmtree(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    config = _demo_trigger_config()
    days = (0, 10, 30, 45, 60, 70, 100, 180, 205, 240, 270, 300)
    results: list[TickResult] = []
    seed = date.fromisoformat(SEED_DATE)
    with boot_seeded_cluster(MIGRATIONS, limit=200) as (_cluster, dsn):
        with psycopg.connect(**dsn) as conn:
            context = setup_tick_roster(conn)
            for day in days:
                as_of = (seed + timedelta(days=day)).isoformat()
                results.append(run_tick_with_config(
                    as_of=as_of,
                    config=config,
                    state_dir=state_dir,
                    conn=conn,
                    gate_context=context,
                ))
    ledger = _read_ledger(state_dir / "tick_ledger.jsonl")
    narrative = _ledger_narrative(ledger)
    artifact = {
        "artifact": "tick_demo_csm",
        "claim_boundary": {"sim": True, "live": False},
        "state_dir": str(state_dir),
        "ticks": len(results),
        "narrative": narrative,
    }
    out_path = state_dir / "tick_demo_csm.json"
    out_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def _trigger_state_from_data(
    data_plane: CustomerDataPlane,
    *,
    as_of: str,
    day: int,
) -> tuple[TriggerState, dict[str, dict[str, Any]]]:
    accounts: list[AccountTriggerState] = []
    snapshots: dict[str, dict[str, Any]] = {}
    for account in data_plane.crm.list_accounts(tenant_id=DEFAULT_TENANT):
        company = data_plane.cs.get_company(account.account_id)
        health = data_plane.cs.get_health_score(account.account_id)
        if company is None or health is None:
            continue
        adoption = data_plane.cs.get_adoption_summary(account.account_id)
        entitlements = tuple(data_plane.telemetry.list_entitlements(account.account_id))
        signals = tuple(data_plane.telemetry.list_usage_signals(account.account_id))
        plans = tuple(data_plane.cs.list_success_plans(account.account_id))
        milestones = tuple(data_plane.telemetry.list_ttv_milestones(account.account_id))
        model = build_customer_value_model(
            account=account,
            company=company,
            health=health,
            adoption=adoption,
            entitlements=entitlements,
            usage_signals=signals,
            success_plans=plans,
        )
        open_milestones = tuple(
            milestone for milestone in milestones
            if milestone.achieved_at is None and milestone.expected_by < as_of
        )
        overdue_plans = tuple(
            plan for plan in plans
            if plan.status == "active" and plan.target_date < as_of
        )
        priority = project_ttv_lens(
            model,
            company=company,
            health=health,
            open_milestone_gaps=open_milestones,
            overdue_success_plans=overdue_plans,
            as_of=as_of,
        )
        state = AccountTriggerState(
            account_id=account.account_id,
            account_name=account.name,
            health_band=health.band,
            health_score=health.score,
            renewal_date=company.renewal_date,
            lifecycle_stage=company.lifecycle_stage,
            arr_cents=company.arr_cents,
            status=company.status,
        )
        accounts.append(state)
        snapshots[account.account_id] = {
            **state.to_snapshot_payload(),
            "priority_score": priority.score,
            "priority_factors": [factor.name for factor in priority.factors],
            "day": day,
        }
    return TriggerState(
        day=day,
        accounts=tuple(sorted(accounts, key=lambda item: item.account_id)),
    ), snapshots


def _snapshot_store(
    prev_snapshot: TriggerState | None,
    observed: ObservedTickState,
) -> SnapshotStore:
    store = SnapshotStore()
    if prev_snapshot is not None and prev_snapshot.day is not None:
        for account in prev_snapshot.accounts:
            store.store_snapshot(
                prev_snapshot.day,
                account.account_id,
                account.to_snapshot_payload(),
            )
    for account_id, payload in observed.snapshot_payloads.items():
        store.store_snapshot(observed.day, account_id, payload)
    return store


def _sweep_payload_for_trigger(sweep: SweepResult, fired: FiredTrigger) -> dict[str, Any]:
    work_items = []
    created_proposals = []
    for item in sweep.work_items:
        item_payload = asdict(item)
        item_payload["trigger_provenance"] = fired.to_dict()
        item_payload["trigger_evidence"] = fired.evidence
        if item.proposal is not None:
            created_proposals.append({
                "proposal_id": item.proposal.proposal_id,
                "status": item.proposal.status,
                "action": item.proposal.action_type,
                "account_id": item.account_id,
            })
        work_items.append(item_payload)
    return {
        "trigger": fired.to_dict(),
        "swept_accounts": list(sweep.swept_accounts),
        "work_items": work_items,
        "escalations": [
            {
                **asdict(item),
                "trigger_provenance": fired.to_dict(),
                "trigger_evidence": fired.evidence,
            }
            for item in sweep.escalations
        ],
        "created_proposals": created_proposals,
        "degraded_items": sweep.degraded_items,
        "budget_skipped": sweep.budget_skipped,
    }


def _lens_payload_for_trigger(
    lens_result: "RiskLensResult | ExpansionLensResult", fired: FiredTrigger
) -> dict[str, Any]:
    """Report 51: Risk/Expansion lens payload, mirroring
    ``_sweep_payload_for_trigger``'s shape for the narrower lens-result
    dataclasses (``tenant_id, lens_version, work_items, swept_accounts`` --
    no ``escalations``/``degraded_items``/``budget_skipped``, fields these
    lenses do not have)."""

    work_items = []
    created_proposals = []
    for item in lens_result.work_items:
        item_payload = asdict(item)
        item_payload["trigger_provenance"] = fired.to_dict()
        item_payload["trigger_evidence"] = fired.evidence
        if item.proposal is not None:
            created_proposals.append({
                "proposal_id": item.proposal.proposal_id,
                "status": item.proposal.status,
                "action": item.proposal.action_type,
                "account_id": item.account_id,
            })
        work_items.append(item_payload)
    return {
        "trigger": fired.to_dict(),
        "swept_accounts": list(lens_result.swept_accounts),
        "work_items": work_items,
        "created_proposals": created_proposals,
    }


def _write_tick_artifacts(
    *,
    state_dir: Path,
    observed: ObservedTickState,
    evaluation: TriggerEvaluation,
    fired_runs: tuple[dict[str, Any], ...],
) -> list[str]:
    state_dir.mkdir(parents=True, exist_ok=True)
    stamp = observed.as_of.replace("-", "")
    work_queue_path = state_dir / f"tick_work_queue_{stamp}.json"
    digest_path = state_dir / f"tick_digest_{stamp}.json"
    work_queue = {
        "artifact": "tick_work_queue",
        "claim_boundary": {"sim": True, "live": False},
        "as_of": observed.as_of,
        "day": observed.day,
        "fired_runs": list(fired_runs),
    }
    digest = {
        "artifact": "tick_digest",
        "claim_boundary": {"sim": True, "live": False},
        "as_of": observed.as_of,
        "day": observed.day,
        "fired_count": len(evaluation.fired),
        "suppression_count": len(evaluation.suppressions),
        "fired_triggers": [item.to_dict() for item in evaluation.fired],
        "suppressions": [item.to_dict() for item in evaluation.suppressions],
        "work_items": sum(len(run["work_items"]) for run in fired_runs),
        "proposals_created": sum(len(run["created_proposals"]) for run in fired_runs),
    }
    work_queue_path.write_text(json.dumps(work_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest_path.write_text(json.dumps(digest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return [str(work_queue_path), str(digest_path)]


def _runtime_from_ledger(
    entries: tuple[dict[str, Any], ...],
    *,
    pending_trigger_accounts: frozenset[tuple[str, str]],
) -> TriggerRuntime:
    last_fire: list[tuple[str, str, str]] = []
    keys: set[str] = set()
    for entry in entries:
        for fired in entry.get("fired_triggers", ()):
            trigger_name = str(fired.get("trigger_name", ""))
            if not trigger_name:
                continue
            account_key = _account_key(fired.get("account_id"))
            as_of = str(fired.get("as_of") or entry.get("as_of"))
            last_fire.append((trigger_name, account_key, as_of))
            key = fired.get("idempotency_key")
            if isinstance(key, str) and key:
                keys.add(key)
    return TriggerRuntime(
        last_fire_at=tuple(sorted(last_fire)),
        fired_idempotency_keys=frozenset(keys),
        pending_trigger_accounts=pending_trigger_accounts,
    )


def _pending_trigger_accounts(
    entries: tuple[dict[str, Any], ...],
    *,
    conn: psycopg.Connection | None,
    gate_context: TickGateContext | None,
) -> frozenset[tuple[str, str]]:
    pending_status = _pending_proposal_statuses(conn, gate_context)
    pending: set[tuple[str, str]] = set()
    for entry in entries:
        for fired in entry.get("fired_triggers", ()):
            trigger_name = fired.get("trigger_name")
            if not isinstance(trigger_name, str):
                continue
            trigger_account = _account_key(fired.get("account_id"))
            for proposal in fired.get("created_proposals", ()):
                proposal_id = proposal.get("proposal_id")
                status = pending_status.get(proposal_id, proposal.get("status"))
                if status != "pending":
                    continue
                proposal_account = proposal.get("account_id")
                pending.add((trigger_name, trigger_account))
                if isinstance(proposal_account, str) and proposal_account:
                    pending.add((trigger_name, proposal_account))
    return frozenset(pending)


def _pending_proposal_statuses(
    conn: psycopg.Connection | None,
    gate_context: TickGateContext | None,
) -> dict[str, str]:
    if conn is None or gate_context is None:
        return {}
    with session(
        conn,
        tenant_id=gate_context.tenant_id,
        actor_id=gate_context.actor_principal_id,
        now=SEED_CLOCK,
    ) as cur:
        cur.execute("SELECT proposal_id, status FROM action_proposal")
        return {str(row[0]): str(row[1]) for row in cur.fetchall()}


def _previous_snapshot_from_ledger(entries: tuple[dict[str, Any], ...]) -> TriggerState | None:
    for entry in reversed(entries):
        raw = entry.get("snapshot")
        if isinstance(raw, dict):
            return _trigger_state_from_dict(raw)
    return None


def _trigger_state_from_dict(raw: dict[str, Any]) -> TriggerState:
    accounts = tuple(
        AccountTriggerState(
            account_id=str(item["account_id"]),
            account_name=str(item.get("account_name") or item["account_id"]),
            health_band=item.get("health_band"),
            health_score=item.get("health_score"),
            renewal_date=item.get("renewal_date"),
            lifecycle_stage=item.get("lifecycle_stage"),
            arr_cents=item.get("arr_cents"),
            status=item.get("status"),
        )
        for item in raw.get("accounts", ())
    )
    return TriggerState(day=raw.get("day"), accounts=accounts)


def _restrict_fixture_data(data: FixtureCustomerData, account_id: str | None) -> FixtureCustomerData:
    if account_id is None:
        raise TickError("account-scoped trigger fired without account_id")
    return FixtureCustomerData(
        accounts=_filter_account(data.accounts, account_id),
        companies=tuple(item for item in data.companies if item.company_id == account_id),
        contacts=_filter_account(data.contacts, account_id),
        cases=_filter_account(data.cases, account_id),
        opportunities=_filter_account(data.opportunities, account_id),
        health_scores=_filter_account(data.health_scores, account_id),
        ctas=_filter_account(data.ctas, account_id),
        success_plans=_filter_account(data.success_plans, account_id),
        adoption_summaries=_filter_account(data.adoption_summaries, account_id),
        entitlements=_filter_account(data.entitlements, account_id),
        usage_signals=_filter_account(data.usage_signals, account_id),
        milestones=_filter_account(data.milestones, account_id),
        tenant_accounts={DEFAULT_TENANT: (account_id,)},
    )


def _filter_account(items: tuple[Any, ...], account_id: str) -> tuple[Any, ...]:
    return tuple(item for item in items if getattr(item, "account_id", None) == account_id)


def _data_plane_from_fixture(data: FixtureCustomerData) -> CustomerDataPlane:
    return CustomerDataPlane(
        crm=FixtureCRMDataConnector(data=data),
        cs=FixtureCSPlatformConnector(data=data),
        telemetry=FixtureProductTelemetryConnector(data=data),
    )


def _read_ledger(path: Path) -> tuple[dict[str, Any], ...]:
    """Parse the append-only ledger, skipping (never crashing on) a
    corrupted or truncated line -- e.g. from an abrupt process kill mid-
    append. A bad line is logged and dropped; every well-formed line
    before and after it is still returned."""

    if not path.exists():
        return ()
    entries = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError as exc:
            log.warning("skipping corrupted ledger line %s:%d: %s", path, line_no, exc)
    return tuple(entries)


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def _print_tick_result(result: TickResult) -> None:
    mode = "dry-run" if result.dry_run else "run"
    print(f"tick {mode}: as_of={result.as_of} day={result.day}")
    if result.evaluation.fired:
        print("fired:")
        for fired in result.evaluation.fired:
            account = fired.account_name or fired.account_id or "book"
            print(f"  - {fired.trigger_name} [{fired.kind}] {account}")
    else:
        print("fired: none")
    if result.evaluation.suppressions:
        print("suppressions:")
        for item in result.evaluation.suppressions:
            account = item.account_name or item.account_id or "book"
            print(f"  - {item.trigger_name} [{item.reason}] {account}")
    if result.artifacts_written:
        print("artifacts:")
        for path in result.artifacts_written:
            print(f"  - {path}")


def _demo_trigger_config() -> TriggerConfig:
    return parse_trigger_config({
        "config_version": "triggers-v1-demo",
        "triggers": [
            {
                "name": "daily_ttv",
                "kind": "schedule",
                "every": "30d",
                "action": {"lens": "ttv", "scope": "book"},
            },
            {
                "name": "renewal_window",
                "kind": "deadline",
                "when": [{"field": "renewal_date", "op": "within_days", "value": 90}],
                "action": {"lens": "ttv", "scope": "account"},
                "cooldown_days": 30,
            },
            {
                "name": "band_drop",
                "kind": "event",
                "when": [{"field": "health_band", "op": "transition", "value": ["green", "*"]}],
                "action": {"lens": "ttv", "scope": "account"},
                "cooldown_days": 14,
            },
            # Report 51: illustrative wiring for the Risk/Expansion lenses'
            # own "weekly_book_sweep" trigger_subscriptions
            # (lens_risk.py's RISK_LENS_SPEC / lens_expansion.py's
            # EXPANSION_LENS_SPEC) -- not a validated production trigger
            # policy (see report 51's Report contract).
            {
                "name": "weekly_risk_sweep",
                "kind": "schedule",
                "every": "7d",
                "action": {"lens": "risk", "scope": "book"},
            },
            {
                "name": "weekly_expansion_sweep",
                "kind": "schedule",
                "every": "7d",
                "action": {"lens": "expansion", "scope": "book"},
            },
        ],
    })


def _ledger_narrative(entries: tuple[dict[str, Any], ...]) -> list[str]:
    lines: list[str] = []
    for entry in entries:
        day = entry["day"]
        for fired in entry.get("fired_triggers", ()):
            account = fired.get("account_name") or fired.get("account_id") or "book"
            lines.append(f"day {day}: {fired['trigger_name']} fired for {account}")
        for suppression in entry.get("suppressions", ()):
            account = suppression.get("account_name") or suppression.get("account_id") or "book"
            reason = suppression.get("reason")
            lines.append(f"day {day}: {suppression['trigger_name']} suppressed by {reason} for {account}")
    return lines


def _account_key(account_id: Any) -> str:
    return str(account_id) if account_id else BOOK_ACCOUNT


def _parse_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value)
    if "T" in text:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    return date.fromisoformat(text)


def main(argv: list[str] | None = None) -> int:
    setup_logging("INFO")
    parser = argparse.ArgumentParser(prog="python -m ultra_csm.tick")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--as-of", default=SEED_DATE)
    parser.add_argument("--config", type=Path, default=DEFAULT_TRIGGER_CONFIG_PATH)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_DEMO_STATE_DIR)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.demo:
        artifact = build_tick_demo(state_dir=args.state_dir / "tick_demo")
        if args.json:
            print(json.dumps(artifact, indent=2, sort_keys=True))
        else:
            for line in artifact["narrative"]:
                print(line)
            print(f"artifact: {args.state_dir / 'tick_demo' / 'tick_demo_csm.json'}")
        return 0
    return run_tick_cli(
        as_of=args.as_of,
        config_path=args.config,
        state_dir=args.state_dir,
        dry_run=args.dry_run,
        json_output=args.json,
    )


if __name__ == "__main__":
    raise SystemExit(main())
