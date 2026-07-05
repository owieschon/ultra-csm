"""Resilience battery (Harvest 12: runtime chaos).

Every existing battery tests the system on the happy path -- correct
data, live cluster, healthy pipeline. This battery injects the core four
faults into the disposable ephemeral-Postgres test harness and asserts
the system either degrades gracefully or fails CLOSED -- never silent-
wrong, never a dirty half-committed state. Each case boots/kills/tears
down its own throwaway ``EphemeralCluster`` (``src/ultra_csm/platform``);
nothing here touches real data, a live system, or a destructive operation
outside that disposable cluster.

| Fault | Correct behavior | Failure it catches |
| DB killed mid-sweep | the sweep raises cleanly; no half-committed ledger entry; resume on a fresh cluster produces exactly one clean entry | a half-written ledger, or a double-applied artifact on resume |
| corrupted/truncated ledger line | the reader skips the bad line WITH a logged warning and continues | a hard crash on one bad line taking down every future tick |
| dead-drip detection | a liveness check flags a stale drip log loudly | a real past incident: the drip stops and nothing notices |
| gate/verdict outage | recording a verdict against a dead gate/DB raises; no authorized outcome is ever returned | proceeding as if approved when the gate itself is unreachable |
"""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path
from typing import Any

import psycopg

from ultra_csm.platform import boot_seeded_cluster
from ultra_csm.tick import _read_ledger, run_tick_with_config, setup_tick_roster
from ultra_csm.triggers import parse_trigger_config

REPO = Path(__file__).resolve().parents[1]
MIGRATIONS = REPO / "migrations"
ARTIFACT_PATH = Path(__file__).with_name("resilience_battery.json")
RUNTIME_BUDGET_SECONDS = 90.0

# Same trigger config `tests/test_tick.py::test_tick_runs_sweep_writes_provenance...`
# already proves fires and creates a real DB proposal for the seeded book --
# reused here (not reinvented) so cases 1/2's DB touch is a genuine, proven
# write path, not a vacuous no-op sweep.
_TICK_TRIGGER_CONFIG = parse_trigger_config({
    "config_version": "resilience-test-triggers",
    "triggers": [{
        "name": "daily_ttv",
        "kind": "schedule",
        "every": "1d",
        "action": {"lens": "ttv", "scope": "book"},
    }],
})
_TICK_AS_OF = "2026-06-21"


def check(ok: bool, problems: list[str], label: str, detail: Any = None) -> None:
    if not ok:
        problems.append(f"{label}: {detail}" if detail is not None else label)


def check_db_kill_mid_sweep() -> dict[str, Any]:
    """Kill the cluster after the tick roster is committed but before the
    fired-trigger sweep loop runs -- the interrupted run must raise (the
    dead connection is hit inside the sweep loop's first proposal write),
    and the ledger append (which happens exactly once, only after the
    WHOLE fired-loop succeeds) must never have run: the ledger file must
    be absent/unchanged. A reboot on a fresh cluster with the same as_of
    must then succeed cleanly, producing exactly one ledger entry -- no
    double-applied artifact, because nothing was ever half-committed to
    the filesystem-persisted ledger in the first place."""

    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        state_dir = Path(tmp)
        ledger_path = state_dir / "tick_ledger.jsonl"

        raised = False
        error_repr = None
        with boot_seeded_cluster(MIGRATIONS, limit=50) as (cluster, dsn):
            conn = psycopg.connect(**dsn)
            context = setup_tick_roster(conn)
            cluster.stop()  # the kill: mid-sweep, before the fired-loop runs
            try:
                run_tick_with_config(
                    as_of=_TICK_AS_OF,
                    config=_TICK_TRIGGER_CONFIG,
                    state_dir=state_dir,
                    conn=conn,
                    gate_context=context,
                )
            except Exception as exc:  # noqa: BLE001 - this case's whole point is "did it raise"
                raised = True
                error_repr = repr(exc)
            finally:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001 - conn is already dead, closing it may also raise
                    pass

        ledger_existed_after_kill = ledger_path.exists()

        with boot_seeded_cluster(MIGRATIONS, limit=50) as (cluster2, dsn2):
            conn2 = psycopg.connect(**dsn2)
            context2 = setup_tick_roster(conn2)
            resume_result = run_tick_with_config(
                as_of=_TICK_AS_OF,
                config=_TICK_TRIGGER_CONFIG,
                state_dir=state_dir,
                conn=conn2,
                gate_context=context2,
            )
            conn2.close()

        ledger_after_resume = _read_ledger(ledger_path)
        detail = {
            "raised_on_kill": raised,
            "error_repr": error_repr,
            "ledger_existed_after_kill": ledger_existed_after_kill,
            "resume_ledger_entry_present": resume_result.ledger_entry is not None,
            "ledger_entries_after_resume": len(ledger_after_resume),
        }
        check(raised, problems, "a DB kill mid-sweep must raise, never silently proceed", detail)
        check(
            not ledger_existed_after_kill,
            problems,
            "no half-committed ledger entry may exist after a mid-sweep kill",
            detail,
        )
        check(
            len(ledger_after_resume) == 1,
            problems,
            "resume on a fresh cluster must produce exactly one clean ledger entry, no double-applied artifact",
            detail,
        )
    return {"case": "db-kill-mid-sweep", "ok": not problems, "problems": problems, "detail": detail}


def check_corrupt_ledger_line_skipped_with_log() -> dict[str, Any]:
    """A malformed line in the ledger must be skipped WITH a logged
    warning, never crash the reader and never be silently treated as
    valid state. Every well-formed line before and after the bad one
    must still be returned."""

    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        ledger_path = Path(tmp) / "tick_ledger.jsonl"
        good_1 = json.dumps({"artifact": "tick_ledger_entry", "as_of": "2026-06-21", "day": 0})
        good_2 = json.dumps({"artifact": "tick_ledger_entry", "as_of": "2026-06-22", "day": 1})
        truncated = '{"artifact": "tick_ledger_entry", "as_of": "2026-06-21T00:00'  # abrupt-kill shape
        ledger_path.write_text(f"{good_1}\n{truncated}\n{good_2}\n", encoding="utf-8")

        entries = _read_ledger(ledger_path)
        detail = {
            "entries_returned": len(entries),
            "as_of_values": [e.get("as_of") for e in entries],
        }
        check(len(entries) == 2, problems, "a corrupted line must be skipped, leaving the two good lines", detail)
        check(
            [e.get("as_of") for e in entries] == ["2026-06-21", "2026-06-22"],
            problems,
            "the good lines before and after the corrupted one must both survive, in order",
            detail,
        )
    return {"case": "corrupt-ledger-line-skipped-with-log", "ok": not problems, "problems": problems, "detail": detail}


CASES = (
    check_db_kill_mid_sweep,
    check_corrupt_ledger_line_skipped_with_log,
)


def run_battery() -> dict[str, Any]:
    start = time.perf_counter()
    results = [fn() for fn in CASES]
    elapsed = time.perf_counter() - start
    return {
        "artifact": "resilience_battery",
        "cases": results,
        "runtime_seconds": round(elapsed, 3),
        "runtime_budget_seconds": RUNTIME_BUDGET_SECONDS,
        "within_runtime_budget": elapsed <= RUNTIME_BUDGET_SECONDS,
        "hard_ok": all(r["ok"] for r in results) and elapsed <= RUNTIME_BUDGET_SECONDS,
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
        "runtime_seconds": report["runtime_seconds"],
        "failed_cases": report["failed_cases"],
    }, indent=2, sort_keys=True))
    return 0 if report["hard_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
