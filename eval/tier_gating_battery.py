"""Tier-gating battery (Harvest 5: Motion-path wiring, Phase 3).

The tier-forbidden-motion guard is the payoff of wiring playbooks.json
into the live agent path: a tech-touch account must never receive a
personal-touch motion its tier forbids. This battery proves that property
at three strengths, deliberately different per tenant because only two of
the four tenants can even construct a CSMWorkItem -- fieldstone and
crateworks have no CS platform, so `run_time_to_value_sweep` fails closed
for them (confirmed via `_slot_b_inputs_for_account`'s own
company/health/adoption None-check; unchanged, not touched by this
dispatch):

1. STATIC, all four tenants: no play in any tenant's playbooks.json
   targets a tier whose own config forbids that play's motion. This is a
   STRONGER, tenant-independent property than any per-account sweep (it
   holds for every possible account the tenant could ever seed, not just
   the ones seeded today) and needs no book/fixture data at all.
2. DYNAMIC, fleetops + loopway (the only two tenants with existing
   per-account trigger derivation and a CS platform): re-run the
   pre-existing full-book resolver sweeps
   (`eval/tier_policy_battery.py`'s and `eval/loopway_battery.py`'s own
   checks, by IMPORT, not reimplemented) confirming zero forbidden-motion
   emissions via the standalone resolver.
3. DYNAMIC, fleetops, through the REAL production sweep path (not the
   standalone resolver): a genuine ActionGate + ephemeral Postgres sweep
   at each of fleetops' own checkpoint days with motion resolution opted
   in (`playbook_tenant_slug="fleetops"`), asserting no tech-touch account
   with a consenting contact ever receives
   `recommended_action="draft_customer_outreach"` -- the actual
   behavior-changing property `sweep.py`'s guard exists to enforce.

RESIDUAL (disclosed, not hidden behind a passing gate): case 1 proves
config-consistency for fieldstone/crateworks, not that any real seeded
account exercises it -- weaker than case 2's actual account-level proof
for fleetops/loopway. Case 3 is fleetops-only, and its own coverage is
checked and reported (`detail["accounts_checked"]`/`"vacuous_pass"`) --
across fleetops' 180-account book, only accounts with fired priority
evidence ever reach `sweep.work_items`, and as seeded today zero of those
are BOTH tech_touch AND have a consenting contact, so this case's pass
does not by itself demonstrate the guard firing on a live account; cases
1 and 2 are what actually cover the underlying property today. Loopway's
own sweep-level wiring (`playbook_tenant_slug` passed to a real loopway
ActionGate sweep) is not built by this dispatch -- a follow-on Owner Ask,
not silently assumed equivalent.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import psycopg

from eval import loopway_battery, tier_policy_battery
from eval.week1_protocol import _fleetops_data_plane_as_of
from ultra_csm.agent1 import run_time_to_value_sweep
from ultra_csm.agent1.sweep import _account_tier_and_motion
from ultra_csm.data_plane.synthetic_book import SEED_DATE
from ultra_csm.governance import ActionGate, FixtureVerdictSource, ROLE_CS_ORCHESTRATOR, make_principal, seed_roster
from ultra_csm.knowledge import load_playbooks
from ultra_csm.motion_resolver import no_play_targets_a_forbidden_tier
from ultra_csm.platform import EphemeralCluster
from ultra_csm.platform.db import apply_migrations, session
from ultra_csm.platform.seed import SEED_CLOCK, det_uuid
from ultra_csm.value_model import load_value_model_config

REPO = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = Path(__file__).with_name("tier_gating_battery.json")
MIGRATIONS = REPO / "migrations"

TENANTS = ("fleetops", "loopway", "fieldstone", "crateworks")

TENANT_ID = det_uuid("tenant", "ultra-csm-tier-gating")
SEED_ACTOR_ID = det_uuid("principal", "ultra-csm-tier-gating", "system-seed")


def check(ok: bool, problems: list[str], label: str, detail: Any = None) -> None:
    if not ok:
        problems.append(f"{label}: {detail}" if detail is not None else label)


def _as_of(day_offset: int) -> str:
    return (date.fromisoformat(SEED_DATE) + timedelta(days=day_offset)).isoformat()


def check_no_play_targets_a_forbidden_tier() -> dict[str, Any]:
    """All four tenants, config-only: no play targets a tier whose own
    config forbids that play's motion."""

    problems: list[str] = []
    detail: dict[str, Any] = {}
    for tenant in TENANTS:
        playbooks = load_playbooks(tenant)
        violations = no_play_targets_a_forbidden_tier(playbooks)
        detail[tenant] = {"plays_checked": len(playbooks.plays), "violations": violations}
        for violation in violations:
            problems.append(f"{tenant}: {violation}")
    return {"case": "no-play-targets-a-forbidden-tier", "ok": not problems, "problems": problems, "detail": detail}


def check_dynamic_sweep_fleetops_loopway() -> dict[str, Any]:
    """Fleetops + loopway, via the pre-existing full-book resolver sweeps
    (imported, not reimplemented): zero tier-forbidden-motion emissions."""

    problems: list[str] = []
    fleetops_result = tier_policy_battery.check_no_tier_forbidden_motion_anywhere()
    loopway_result = loopway_battery.check_no_tier_forbidden_motion_sampled()
    if not fleetops_result["ok"]:
        problems.extend(f"fleetops: {p}" for p in fleetops_result["problems"])
    if not loopway_result["ok"]:
        problems.extend(f"loopway: {p}" for p in loopway_result["problems"])
    return {
        "case": "dynamic-sweep-fleetops-loopway",
        "ok": not problems,
        "problems": problems,
        "detail": {"fleetops": fleetops_result, "loopway": loopway_result},
    }


def _setup_gate(conn: psycopg.Connection) -> ActionGate:
    with session(conn, tenant_id=TENANT_ID, actor_id=SEED_ACTOR_ID, now=SEED_CLOCK) as cur:
        cur.execute(
            "INSERT INTO tenant (tenant_id, name) VALUES (%s, %s) "
            "ON CONFLICT (tenant_id) DO NOTHING",
            (TENANT_ID, "Ultra CSM Tier Gating Eval"),
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
        display_name="tier-gating-eval",
        role=ROLE_CS_ORCHESTRATOR,
        now=SEED_CLOCK,
    )
    return ActionGate(
        conn,
        tenant_id=TENANT_ID,
        actor_principal_id=actor_id,
        verdict_source=FixtureVerdictSource(),
        now=SEED_CLOCK,
    )


def check_real_sweep_guard_fleetops() -> dict[str, Any]:
    """The actual payoff, through the REAL production sweep path: run
    `run_time_to_value_sweep` for fleetops with motion resolution opted in,
    at each of fleetops' own checkpoint days, and assert zero tech-touch
    accounts (with a consenting contact) ever receive
    `recommended_action="draft_customer_outreach"` -- the customer-facing
    action the guard exists to block for that tier.

    COVERAGE CAVEAT (checked and disclosed, not assumed): only accounts
    with fired priority evidence appear in `sweep.work_items` at all
    (`_slot_b_inputs_for_account`'s own `priority.score <= 0` gate,
    unchanged). If zero such accounts are BOTH tech_touch AND have a
    consenting contact at any checkpoint day, this case's assertion holds
    vacuously -- `detail["accounts_checked"]` reports the true number so a
    reader can see this rather than trust a bare `ok: true`."""

    problems: list[str] = []
    detail: dict[str, Any] = {"accounts_swept_per_day": {}, "accounts_checked": 0}
    playbooks = load_playbooks("fleetops")
    cfg = load_value_model_config()

    with EphemeralCluster() as cluster:
        with psycopg.connect(**cluster.dsn(user=cluster.BOOTSTRAP_USER)) as boot:
            apply_migrations(boot, MIGRATIONS)
        with psycopg.connect(**cluster.dsn(user="app_runtime")) as conn:
            gate = _setup_gate(conn)
            for day in tier_policy_battery.CHECKPOINT_DAYS:
                data_plane = _fleetops_data_plane_as_of(day)
                sweep = run_time_to_value_sweep(
                    data_plane,
                    "ultra-demo",
                    gate,
                    sweep_principal_id=SEED_ACTOR_ID,
                    as_of=_as_of(day),
                    playbook_tenant_slug="fleetops",
                )
                detail["accounts_swept_per_day"][day] = len(sweep.swept_accounts)
                account_by_id = {a.account_id: a for a in data_plane.crm.list_accounts(tenant_id="ultra-demo")}
                for item in sweep.work_items:
                    account = account_by_id.get(item.account_id) if item.account_id else None
                    if account is None:
                        continue
                    result = _account_tier_and_motion(
                        data_plane, account, playbooks=playbooks, value_model_config=cfg
                    )
                    if result is None:
                        continue
                    tier, _motion = result
                    if tier != "tech_touch" or not item.customer_contact_allowed:
                        continue
                    detail["accounts_checked"] += 1
                    check(
                        item.recommended_action != "draft_customer_outreach",
                        problems,
                        f"day {day}, account {item.account_id} (tech_touch, consenting "
                        f"contact) received recommended_action={item.recommended_action!r} "
                        "-- tier-forbidden motion 'personal_email' was not blocked",
                    )

    if detail["accounts_checked"] == 0:
        detail["vacuous_pass"] = (
            "no account across any checkpoint day was BOTH tech_touch AND had "
            "fired priority evidence AND a consenting contact -- this case's "
            "ok:true does not demonstrate the guard fired on a real account; "
            "see check_no_play_targets_a_forbidden_tier and "
            "check_dynamic_sweep_fleetops_loopway for this dispatch's actual "
            "coverage of the underlying property"
        )

    return {"case": "real-sweep-guard-fleetops", "ok": not problems, "problems": problems, "detail": detail}


CASES = (
    check_no_play_targets_a_forbidden_tier,
    check_dynamic_sweep_fleetops_loopway,
    check_real_sweep_guard_fleetops,
)


def run_battery() -> dict[str, Any]:
    results = [fn() for fn in CASES]
    return {
        "artifact": "tier_gating_battery",
        "cases": results,
        "hard_ok": all(r["ok"] for r in results),
        "failed_cases": [r["case"] for r in results if not r["ok"]],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ARTIFACT_PATH)
    args = parser.parse_args(argv)
    report = run_battery()
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "artifact": str(args.output),
        "cases": len(report["cases"]),
        "hard_ok": report["hard_ok"],
        "failed_cases": report["failed_cases"],
    }, indent=2, sort_keys=True))
    return 0 if report["hard_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
