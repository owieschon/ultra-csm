# Program Report 30 — Harvest 12: Runtime chaos / resilience battery

Branch `codex/runtime-chaos` off synced `main` (ed2bda3). Every existing
battery tests the system on the happy path -- correct data, live cluster,
healthy pipeline. The product runtime had never been tested against its
own failure modes, and one of them (silent drip failure) has actually
occurred and gone undetected before. This program builds a resilience
battery that injects the core four faults into the disposable ephemeral-
Postgres test harness and asserts the system either degrades gracefully
or fails CLOSED.

## FAULT -> SEAM table (verified against disk, not the dispatch's guesses)

| # | Fault | Seam (file:line) | Injection mechanism | Observed behavior |
| --- | --- | --- | --- | --- |
| 1 | DB killed mid-sweep | `src/ultra_csm/tick.py:220` (`for fired in evaluation.fired:` sweep loop); ledger append (`tick.py:271`, `_append_jsonl`) happens exactly once, only after the whole loop succeeds. Kill: `src/ultra_csm/platform/__init__.py:161` `EphemeralCluster.stop()`. | Stop the cluster mid-loop, after the connection is established but before the sweep completes. | `psycopg.OperationalError` ("server closed the connection unexpectedly") raised from inside the sweep's first proposal write; no ledger file existed after the kill; reboot on a fresh cluster produced exactly one clean ledger entry. |
| 2 | Corrupted/truncated ledger line | `src/ultra_csm/tick.py:647` `_read_ledger` -- `json.loads(line)` was UNGUARDED. | Write a malformed line into a temp ledger copy, call `_read_ledger` directly. | REAL BUG FOUND, root-fixed (own commit): before the fix, this crashed with `json.JSONDecodeError`. Fix wraps the per-line parse in try/except, `log.warning`s, and continues -- verified: a truncated line between two good lines is skipped with a logged warning, both good lines survive in order. |
| 3 | Dead-drip detection | NO EXISTING SEAM (`grep -rn "drip" scripts/ src/` -> zero matches). | N/A -- the absence was the finding. | Added `src/ultra_csm/drip_liveness.py`, a minimal pure detector (reads a drip log's last-timestamp vs a threshold). Verified: fresh (2h old, 24h threshold) -> not flagged; stale (96h old) -> flagged loud; missing log -> flagged loud. |
| 4 | Gate/verdict outage | `src/ultra_csm/governance/gate.py:154` `ActionGate.record_verdict` -- `session(self._conn, ...)`/`cur.execute`, no try/except around the DB call. | Stop the cluster after `gate.propose()` succeeds, before `record_verdict` is called. | `psycopg.OperationalError` raised, propagated uncaught; no `GateOutcome` ever returned. Already fail-closed by construction -- no fix needed. |

## DoD Evidence

| Phase | Result | Evidence |
| --- | --- | --- |
| 0: Bootstrap + baseline + fault-seam map | Complete | Preconditions verified: `EphemeralCluster`/`boot_seeded_cluster` present; ledger/tick surfaces present; drip liveness surface ABSENT (the Decision-#3 finding). `make eval`: 610 passed, 1 skipped, 194.66s baseline. FAULT->SEAM table above complete with real file:line for all four. |
| 1: DB-kill-mid-sweep + corrupt-ledger-line | Complete | Root fix to `_read_ledger` (own commit, see below). `eval/resilience_battery.py` cases 1-2, `hard_ok: true`, runtime ~2.4-2.6s. `make eval`: 611 passed, 1 skipped, zero drift. |
| 2: Dead-drip detection + gate outage | Complete | `src/ultra_csm/drip_liveness.py` added. `eval/resilience_battery.py` cases 3-4, `hard_ok: true` (all four), runtime ~3.5-3.7s. `make eval`: 611 passed, 1 skipped, zero drift. |
| 3: Full regression + report | Complete | `make eval`: 611 passed, 1 skipped, 194.62s. `make resilience-battery-csm`: `hard_ok: true`, all four cases, wall-clock 3.948s (budget 90s). `make tier-policy-battery-csm narrative-battery-csm`: both `hard_ok: true`, unchanged. `make lint`/`make hygiene`/`make status`/`git diff --check` all clean. |

## IF/THEN Branches Taken

- **DB-kill-mid-sweep framing corrected** (measured, not assumed): the
  dispatch's Decision #1 worried about "no double-applied proposals, no
  orphaned gate rows" surviving a reboot -- but `EphemeralCluster` is
  fully ephemeral (a killed cluster's data directory is torn down
  entirely), so DB-persisted proposals/gate rows can never survive a
  cluster kill to be double-applied in the first place. The real,
  provable idempotency concern is the FILESYSTEM-persisted ledger
  (`tick_ledger.jsonl`, outside the killed DB) -- does a mid-sweep kill
  leave it half-written? Reframed case 1's assertion around that; the
  append-once-at-the-end design already prevents this, and the case
  proves it rather than assuming it.
- **`_read_ledger` crash, root-fixed**: confirmed a real silent-fail risk
  (a crash on any one malformed line, taking down every future tick) and
  fixed at the root per K14 and the sanctioned exceptions -- try/except
  around the per-line `json.loads`, skip+log, continue. Its own commit,
  separate from the battery-cell addition (Sanctioned Exceptions clause).
- **Gate-verdict-outage harness bug, caught and fixed before it produced
  a false pass**: the case initially built its `ActionGate` via
  `context.gate()` (bare `FixtureVerdictSource()`, no configured default
  verdict) -- this raised `GateError("no verdict for intent 'send_email'")`
  BEFORE ever touching the DB, which would have made the case pass for
  the WRONG reason (K7: an injected fault must be the fault actually
  asserted, never a harness flake or setup bug masquerading as it).
  Fixed by constructing a real `ActionGate` with a configured
  `FixtureVerdictSource(default=Verdict("approve", ...))`; re-running
  confirmed the case now raises the genuine `psycopg.OperationalError`
  from the dead connection.
- Fresh worktree had no `.venv` -- created one (same pattern as Harvest
  11's worktree: `python3.14 -m venv .venv` + `pip install -e ".[dev,api,mcp]"`).
- Lint caught an E402 introduced by my own edit (inserted `log =
  logging.getLogger(__name__)` between two of `tick.py`'s existing import
  blocks) -- fixed by moving it after all imports, matching
  `mcp_server.py`'s existing placement convention.

## Consolidated Owner Ask

1. **Case 4 (gate/verdict outage) required no root fix** -- `ActionGate.record_verdict`
   was already fail-closed by construction (no swallowing try/except
   anywhere between the dead connection and the caller). This is
   evidence the property held before this program looked for it, not
   evidence the whole gate/governance surface is chaos-hardened
   end-to-end; only this one injection point was tested.
2. **The dead-drip detector is new and untested against the real drip's
   actual log format/location.** `check_drip_liveness` is a pure,
   parameterized function (log path + threshold); wiring it to the
   drip's real log path and choosing a production staleness threshold is
   a follow-on, owner-gated decision (the drip's launchd job itself was
   correctly never touched per the ownership map).
3. **Scope is exactly the core four faults** (owner-confirmed
   2026-07-05); resource-limit/rate-storm faults are explicitly OUT, a
   named follow-on, not silently assumed covered.

## STOP Conditions

No credentials were read, no live org was touched, no network call was
made anywhere in this program -- every case boots/kills/tears down its
own throwaway `EphemeralCluster`, reachable only over a local Unix socket
(`git grep -n "live\|real" eval/resilience_battery.py` reviewed: every
match is a docstring/comment describing offline behavior, never a live
credential or live-system reference). The drip's launchd job was never
touched -- only a new, pure, standalone detector was added. The happy-path
batteries (`tier-policy-battery-csm`, `narrative-battery-csm`) re-ran
unchanged-green after every phase. No test, threshold, or battery
assertion was weakened to pass -- the one genuine silent-fail found
(`_read_ledger`'s crash) was fixed at its root, in its own commit, not
routed around. Zero STOP events fired: no fault revealed a silent-wrong
failure whose fix would require a redesign; no required fault-injection
seam was missing (the drip's ABSENCE of a seam was itself the anticipated
Decision-#3 finding, not a blocker); nothing required a live system, real
credentials, or the drip's actual launchd job. Diff budget (12 files /
1,200 lines) not exceeded: 6 files touched across all phases (2 new
eval/detector files, 1 new test file, 1 production fix, the Makefile, and
the battery-artifact JSON), well under budget.

## Skeptical Reviewer Paragraph

A skeptical reviewer should weigh three real limits. First, this proves
fail-closed / detected / idempotent behavior at the FOUR injected fault
points on the disposable harness -- it does not prove resilience to every
fault, interleaving, or a real production topology (resource-limit and
rate-storm faults were explicitly out of scope, a named follow-on, not
silently covered). Second, the dead-drip detector is only as good as its
threshold and its wiring to the real drip's log -- this program built and
proved the pure detection logic, not a production deployment of it; a
24-hour threshold in the battery's own test is illustrative, not an owner-
ratified production value. Third, case 1's idempotency claim is narrower
than the dispatch's original framing suggested: it proves the
FILESYSTEM-persisted ledger never half-commits under a mid-sweep kill (a
property that held by construction, not by a new guard this program
added), not that every possible DB-persisted artifact (proposals, gate
rows) survives a kill in some recoverable state -- an ephemeral cluster's
data is gone entirely on kill, so that stronger claim was never the right
one to make or test here.

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `611 passed, 1 skipped` in `194.62s` (up from Phase 0's baseline `610 passed, 1 skipped` in `194.66s`; 1 new test, zero drift on pre-existing tests) |
| `LC_ALL=en_US.UTF-8 make resilience-battery-csm` | `hard_ok: true`, 4/4 cases |
| `git grep -n "live\|real" eval/resilience_battery.py` | reviewed: no live credentials/systems referenced; every case boots only `EphemeralCluster` |
| `time make resilience-battery-csm` | `3.948s` total (budget 90s) |
| `LC_ALL=en_US.UTF-8 make tier-policy-battery-csm narrative-battery-csm` | both `hard_ok: true`, unchanged |
| `LC_ALL=en_US.UTF-8 make lint` | `All checks passed!` |
| `LC_ALL=en_US.UTF-8 make hygiene` | Exited 0 |
| `LC_ALL=en_US.UTF-8 make status` | `STATUS.md is current` |
| `git diff --check` | Exited 0 |

## Merge Policy

Kernel v1.1 K11: `gh api repos/:owner/:repo --jq .allow_auto_merge` and
branch protection on `main` must be verified before any auto-merge
attempt; otherwise leave the PR open with the reason, never merge
directly. Sequencing note (per dispatch): this program and Harvest 11
(robustness-grid) both add Makefile targets to the same `.PHONY` line --
whichever merges SECOND rebases that one-line conflict; the two were not
run against the same worktree (this program used
`~/dev/ultra-csm-runtime-chaos`, branch `codex/runtime-chaos`).
