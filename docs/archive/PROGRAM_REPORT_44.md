# Program Report 44 — Stream 27: Operability hardening

Repo `~/dev/ultra-csm`, worktree `~/dev/ultra-csm-operability-hardening`,
branch `codex/operability-hardening` off synced `origin/main` (`96bda58`,
Harvest 17 merged as PR #50). Six operability findings from a completed
`/shipcheck`: `make serve` binding `0.0.0.0` by default, MCP-mode stderr
logging every record twice, the daily `tick.py` job emitting zero
structured telemetry, four untimed `subprocess.run` calls in the
ephemeral-Postgres bootstrap path, no reaper for orphaned ephemeral-Postgres
clusters from prior interrupted sessions, and no troubleshooting
documentation anywhere. Separately, `salesforce_writeback.py`'s idempotency
ledger recorded intent only after the remote POST succeeded, leaving a
crash window.

## Tripwires (K12)

Ledger count: 1/8 (threshold 8, no STOP). One disclosed deviation, a scope
fork not a behavior risk:

1. **Diff budget exceeded.** Dispatch's stated budget: 7 files / 180 lines.
   Actual: **10 files, 493 insertions(+), 27 deletions(-)** against
   `origin/main` (`git diff origin/main... --stat`). See "Diff budget"
   section below for the full breakdown and the reasoning for not trimming
   further. Not one of the three explicitly named STOP conditions, so
   recorded here and in IF/THEN rather than treated as a blocker.

## Preconditions verified (Phase 0)

- `main` synced: `git -C ~/dev/ultra-csm fetch origin --quiet && git log origin/main -1 --oneline` → succeeded, `96bda58`.
- `grep -n "0.0.0.0" Makefile` → matched (line 12, `serve` target).
- `grep -n "setup_logging" src/ultra_csm/tick.py` → no match (confirmed absent).

Worktree created explicitly off `origin/main` (not local `main`, which had
diverged 4 commits each direction from `origin/main` at dispatch time, and
the shared `~/dev/ultra-csm` checkout had substantial unrelated uncommitted
work from other sessions sitting in it) — no git operations were performed
in the shared main checkout at any point.

BASELINE (`LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 make eval`): **668 passed, 1
skipped, 1 warning in 637.67s**. This run (and every subsequent one in this
report) executed under heavy contention: 10 sibling wave dispatches were
running `make eval` concurrently on the same machine, which is why wall
times are long — not itself a defect.

## Phases completed

- **Phase 1 — HOST bind default.** Added `HOST ?= 127.0.0.1` Makefile
  variable; `serve` target changed from a hardcoded `--host 0.0.0.0` to
  `--host $(HOST)`. Verified via `make -n serve` (resolves to `127.0.0.1`)
  and `make -n serve HOST=0.0.0.0` (resolves to `0.0.0.0`), plus a real
  boot+`lsof` check confirming the live listener binds `localhost:8000`,
  not `0.0.0.0:8000`. Commit `d4c9961`.

- **Phase 2 — Logging fixes.** Root-caused the MCP double-log bug
  precisely (not just patched around the symptom): `mcp_server.py`
  constructs `mcp = FastMCP(...)` at module level, whose `__init__` calls
  `configure_logging()` → `logging.basicConfig(handlers=[StreamHandler()])`
  — this installs the FIRST root handler (root had none yet at that point,
  so `basicConfig` is not a no-op). `_boot()` runs later at import time,
  calling `setup_logging("INFO")`, whose old dedup guard only checked for
  an existing `JSONFormatter`-formatted handler (found none, since the
  first handler was MCP's own plain one) and added a second `StreamHandler`
  on top. Both handlers then fired on every record. Empirically reproduced
  pre-fix: `grep -c "MCP server ready"` = `2`.
  Fixed `logging_config.py`'s `setup_logging`: after the existing
  JSONFormatter-dedup early-return, it now also removes any pre-existing
  plain `StreamHandler` (no `JSONFormatter`) from root before installing
  its own. API-mode has zero pre-existing root handlers when its own
  `setup_logging("INFO")` runs (verified directly: uvicorn/FastAPI's
  lifespan path installs nothing on root before this point), so the
  removal loop is a no-op there — confirmed no regression via a real boot.
  Added `setup_logging("INFO")` at the top of `tick.py`'s `main()`,
  matching `api.py:312` and `mcp_server.py:274` exactly.
  Commit `b20c383`.

- **Phase 3 — Subprocess timeouts + stale-cluster reaper.** Added
  `timeout=120` to the three `subprocess.run` calls in
  `platform/__init__.py` (`initdb`, `pg_ctl start`, `pg_ctl stop`) and the
  one in `doctor.py` (the pg-tooling `--version` check).
  Built `reap_stale_clusters()` in `platform/__init__.py` (the natural
  home — it already owns all `EphemeralCluster` lifecycle logic). Wired
  into `make clean` (new `scripts/reap_stale_clusters.py`, run BEFORE
  `rm -rf build/tmp`) and `make doctor` (a new `check_stale_clusters` entry
  in its `CHECKS` tuple), both reporting what they find/reap rather than
  running silently. Did not wire into `conftest.py` — no evidence was
  sought or found that per-test-run invocation is cheap/safe, so the
  explicit `make clean`/`make doctor` points are used per Decisions'
  stated default.
  Commit `dda8c5e`.

- **Phase 4 — Troubleshooting doc + salesforce ordering fix.**
  Verified at runtime that the writeback ledger (append-only JSONL, one
  reader — `_ledger_has_committed_key`, which only trusts `committed=True`
  rows — and no other consumer anywhere in the repo) supports an additive
  two-phase intent/confirmed/failed pattern with no breaking change.
  Implemented the fix (not scoped to an Owner Ask): an intent row (always
  `committed=False`, via `dataclasses.replace()` — never the real receipt
  object as-is, since the real receipt's `committed` field is set to `not
  already` at construction time, BEFORE the POST fires, and would already
  read `committed=True` on a first-ever attempt if written unmodified,
  corrupting the idempotency read) is written BEFORE the POST fires. A
  confirmed row follows on success; a failed row on error (the POST call
  and response handling are now wrapped in `try/except SalesforceWriteError`
  specifically to append that failed row before re-raising). Added the
  five-hazard troubleshooting section to `docs/OBSERVABILITY.md`.
  Commit `d879980`.

- **Phase 0** had no commit (per its own spec: "Commit: none").

## Diff budget

`git diff origin/main... --stat`: **10 files changed, 493 insertions(+), 27
deletions(-)** — over the dispatch's stated 7-file / 180-line budget.

| File | +/- | Why |
| --- | --- | --- |
| `Makefile` | +6/-1 | `HOST` variable + `serve`/`clean` target edits |
| `docs/OBSERVABILITY.md` | +47/-0 | five-hazard troubleshooting section |
| `scripts/doctor.py` | +19/-1 | timeout on the version-check subprocess call; new `check_stale_clusters` |
| `scripts/reap_stale_clusters.py` | +27/-0 (new file) | `make clean`'s reaper invocation point |
| `src/ultra_csm/data_plane/salesforce_writeback.py` | +39/-18 | two-phase intent/confirmed/failed ledger ordering |
| `src/ultra_csm/logging_config.py` | +19/-1 | dedup-guard fix for pre-existing plain StreamHandlers |
| `src/ultra_csm/platform/__init__.py` | +103/-3 | 3 subprocess timeouts + `reap_stale_clusters`/`ReapedCluster`/helpers |
| `src/ultra_csm/tick.py` | +2/-0 | `setup_logging("INFO")` import + call |
| `tests/test_platform_boot_tier.py` | +110/-0 | 5 reaper tests (live-PID-untouched, dead-PID-reaped, no-pidfile-cleanup, non-pgdata-ignored, missing-base-dir) |
| `tests/test_salesforce_writeback.py` | +121/-3 | updated 2-line-ledger assertion + 3 new ordering/failure/retry tests |

**Why over budget, and why not trimmed further:** ~47% of the total line
count (231 of 493 insertion lines) is in the two touched-module test files.
Both are directly mandated by this dispatch's own Routing table: the
salesforce fix requires an explicit order-of-operations proof ("the test
should at minimum prove the intent record is written and queryable BEFORE
the POST call fires"), and the reaper — gated by an explicit STOP condition
about a destructive-operation-adjacent risk — needed both directions of the
live/dead-PID safety proof, not just the one mocked test the gate literally
requires. Diff-budget overage is not one of the three explicitly named STOP
conditions; shipping under-tested destructive-adjacent code to hit a line
count would risk the actual STOP this dispatch names. Considered trimming
the three smaller reaper edge-case tests (no-pidfile cleanup, non-pgdata
ignored, missing-base-dir — roughly 10-15 lines apiece) to claw back
budget; kept them since each tests a distinct behavior of new code whose
failure mode is destructive, and the marginal budget improvement from
dropping them didn't change the overall picture. Recorded here plainly
rather than silently exceeded or destructively cut for a number.

## IF/THEN branches taken

1. **Where the reaper function lives.** Decisions left this open
   ("`platform/__init__.py` or a small new script — verify the cleanest
   home"). Chose `platform/__init__.py` for the detection/reap logic itself
   (it already owns all `EphemeralCluster` lifecycle code), plus a small
   new `scripts/reap_stale_clusters.py` CLI wrapper (also explicitly
   sanctioned by Decisions' own wording) as `make clean`'s invocation
   point, since this Makefile has no existing `python -c` inline-script
   convention to conform to instead — every other target invokes a module
   or a script file.

2. **Subprocess-timeout count discrepancy.** The DoD table's literal gate
   (`grep -c "timeout=" src/ultra_csm/platform/__init__.py scripts/doctor.py`
   → expected `4`) was written to check the fix for the four PRE-EXISTING
   call sites named in the Mission. The new reaper's own `pg_ctl stop -m
   fast` call (a fifth, brand-new subprocess call, `platform/__init__.py:295`)
   also carries `timeout=120`, for the same reason the other four now do —
   this dispatch's own stated goal is "every subprocess call in scope has a
   timeout." This makes the literal combined grep count **5, not 4**.
   Chose to keep the timeout on the new call (correct, conformant, and
   consistent with this dispatch's own intent) over dropping it just to
   match a count written before this function existed. The four ORIGINAL
   sites each individually carry exactly one `timeout=` (verified: lines
   140, 158, 170 in `platform/__init__.py`; one in `doctor.py`) — the
   dispatch's actual ask is fully satisfied; the discrepancy is against the
   DoD table's arithmetic, not its intent.

3. **Diff budget overage.** See "Diff budget" section above — recorded as
   Tripwire 1 and here rather than trimmed at the cost of safety-test
   coverage on destructive-adjacent code.

## Owner Asks

None required. The salesforce ordering fix was fully implementable within
this dispatch's ownership map and Sanctioned Exceptions — the ledger's
append-only JSONL format with a single, narrowly-scoped reader supported
the two-phase pattern additively, with no breaking change and no need to
invoke the Sanctioned Exceptions escape valve.

On the troubleshooting-doc placement question the Report contract asks to
be stated plainly: the troubleshooting section was added to
`docs/OBSERVABILITY.md` per the Ownership map and Decisions (README/
QUICKSTART/TOUR are explicitly Stream 22's — MUST NOT TOUCH). It does not,
on reflection, obviously belong in README instead: README is this repo's
quickstart/install surface, while OBSERVABILITY.md is already the
structured-logging/telemetry landing page this section extends naturally
(missing pg tooling and the locale hazard both concern the exact
ephemeral-Postgres bootstrap OBSERVABILITY.md's neighbor sections already
discuss under the hood via `_pg_env`). No cross-reference to Stream 22 is
needed beyond noting the ownership boundary was respected as specified.

## STOP conditions hit

None. All three explicitly named STOP conditions were checked and did not
fire:

- MCP stderr dedup did not break API-mode logging (verified: a real API
  boot after the fix shows a single JSON line for "Booting ephemeral
  Postgres cluster for API", no plain-text duplicate) — and API-mode
  logging did not break MCP-mode (verified: MCP-mode boot post-fix shows
  `grep -c "MCP server ready"` = `1`, was `2` pre-fix).
- The salesforce ledger schema supported the intent-before-POST pattern
  without a breaking change (verified at runtime: single reader, no other
  consumer) — the Sanctioned Exceptions escape valve was not needed.
- The reaper does not risk stopping a Postgres cluster that isn't actually
  orphaned. See "Skeptical Reviewer paragraph" below for the full safety
  proof, including a real (non-mocked) live-cluster test performed directly
  against this machine's actual `build/tmp/` directory.

## Skeptical Reviewer paragraph

The reaper's detection rule (directory-pattern match AND a confirmed-dead
postmaster PID, never pattern-match alone) was arrived at by direct
empirical audit of this machine's real `build/tmp/` directories — not
designed in the abstract and hoped correct. While auditing `~/dev/ultra-csm`
(main repo) and this worktree with 10 sibling wave dispatches running
concurrently, I found `pgdata.c2ugcsk3` (main repo) carrying a postmaster
PID that was alive at the moment of inspection, and which was cleaned up by
its own owning session moments later — direct proof that a
directory-pattern-plus-pidfile-exists rule alone would have produced a
false positive on a cluster that was genuinely mid-run. I separately found
`pgdata.nods_9x2` (main repo) with a dead postmaster PID and a `stopping`
status line left over from a crashed/killed prior session — a genuine
orphan. Both observations directly shaped the final detection rule.
Beyond the dispatch's own required mocked pytest test (5 tests total, all
passing — `pytest tests/ -v -k reaper`), I ran two REAL, non-mocked
end-to-end proofs before writing any test: (1) booted a genuine live
`EphemeralCluster` via this repo's own code and ran the real (unmocked)
`reap_stale_clusters()` against the real `build/tmp/` directory while that
cluster was actively running — it correctly returned an empty reaped list
and left the live datadir untouched, and the cluster subsequently stopped
cleanly via its own normal path afterward; (2) manufactured a genuinely
dead-PID orphan (fork+immediately-reap a child PID, write a realistic
`postmaster.pid` including the real `stopping` status line format) and
confirmed the real reaper detected and removed it. I additionally ran the
REAL (not mocked) `make doctor` and `make clean` against manufactured real
orphans placed directly in this worktree's actual `build/tmp/` and
confirmed both correctly found, reported by name and PID, and removed them.
What is NOT tested, and cannot safely be tested in this environment: a
genuine live-orphan scenario where a real Postgres postmaster process is
killed out from under its own tracking (e.g., `kill -9` on a real running
`postgres` process, then immediately auditing whether the reaper correctly
identifies the resulting dead-PID state before any OS PID-reuse race could
occur) — this dispatch's own Routing table names this exact residual
("the real end-to-end behavior against a genuinely orphaned live cluster is
harder to test safely in CI... sampled/manual verification recommended on
a real orphan if one is available"). The `pgdata.nods_9x2` orphan found on
this machine during the audit IS such a real orphan and was not artificially
staged — but it was audited read-only (`kill -0`, never signaled), and not
formally reaped as part of this dispatch's own change (it belongs to the
main repo, outside this worktree's ownership; reaping it would be a
git-operations-in-the-shared-checkout action explicitly out of scope per
this dispatch's own first-action instruction). A future manual verification
run against `~/dev/ultra-csm`'s own `make doctor`/`make clean` (outside this
dispatch, by whoever owns that checkout) would close this residual for
real.

## Final verification table

| Check | Command | Expected | Actual |
| --- | --- | --- | --- |
| HOST default is loopback | `grep -n "HOST ?= 127.0.0.1" Makefile` | match | match (line 5) |
| MCP logs deduped | `ULTRA_CSM_MCP_READONLY=1 .venv/bin/python -m ultra_csm.mcp_server 2>&1 \| grep -c "MCP server ready"` | `1` | `1` (real boot+kill, confirmed) |
| tick emits telemetry | `PYTHONPATH=src:. .venv/bin/python -m ultra_csm.tick --demo 2>&1 \| grep -c sweep_timing` | ≥1 | `194` |
| all 4 originally-targeted subprocess calls timed out | `grep -c "timeout=" src/ultra_csm/platform/__init__.py scripts/doctor.py` | `4` | `5` (see IF/THEN #2 — 4 original sites confirmed individually, 5th is the new reaper's own additional call) |
| reaper test passes | `LC_ALL=en_US.UTF-8 pytest tests/ -v -k reaper` | pass | `5 passed` |
| troubleshooting section exists | `grep -ciE "postmaster\|orphan\|credential\|tokenless" docs/OBSERVABILITY.md` | ≥4 | `13` (individual: postmaster=5, orphan=1, credential=5, tokenless=2) |
| salesforce ordering (or Owner Ask) | `LC_ALL=en_US.UTF-8 pytest tests/test_salesforce_writeback.py -v` | pass | `8 passed` (3 new: order-of-operations proof, failed-phase ledger row, post-failure retry) |
| zero-drift full suite | `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 make eval` | passing count == baseline + new tests | **676 passed, 1 skipped, 1 warning, 409.64s** — baseline (668) + 8 new tests (5 reaper + 3 salesforce ordering), zero pre-existing test broke |
| lint clean | `make lint` | `All checks passed!` | `All checks passed!` |
| diff budget held | `git diff origin/main... --stat \| tail -1` | ≤7 files, ≤180 lines | `10 files changed, 493 insertions(+), 27 deletions(-)` — OVER budget, see Tripwire 1 / Diff budget section |

## Receipts appendix (K4)

- Baseline: `make eval` = 668 passed, 1 skipped, 1 warning, 637.67s (before any change; run under 10-way sibling-wave contention).
- Final: `make eval` = 676 passed, 1 skipped, 1 warning, 409.64s (run under easing sibling-wave contention, hence the shorter wall time than baseline despite more work). Delta: +8 passed, exactly the 8 new tests added (5 reaper tests in `test_platform_boot_tier.py` + 3 salesforce ordering/failure/retry tests in `test_salesforce_writeback.py`) — zero pre-existing test broke, zero pre-existing assertion changed unexpectedly (the one intentionally-updated assertion, the ledger-line-count check in `test_live_committer_creates_exactly_one_task_and_ledgers_it`, reflects the new correct two-phase behavior, not drift).
- `make lint`: `ruff check src eval tests scripts` → `All checks passed!`.
- Directly-touched-module test subset (`tests/test_tick.py tests/test_platform_boot_tier.py tests/test_salesforce_writeback.py tests/test_api.py`): `50 passed, 1 warning`.
- Commits (branch `codex/operability-hardening`, off `origin/main` at `96bda58`):
  1. `d4c9961` — `fix: make serve binds 127.0.0.1 by default; HOST=0.0.0.0 remains an explicit opt-in`.
  2. `b20c383` — `fix: dedup MCP-mode stderr logging; add structured telemetry to the daily tick job`.
  3. `dda8c5e` — `fix: add timeouts to bootstrap subprocess calls; add stale ephemeral-Postgres cluster reaper`.
  4. `d879980` — `docs: add troubleshooting section to OBSERVABILITY.md; fix salesforce writeback idempotency ordering`.
- Diff vs branch point: `git diff origin/main... --stat` → 10 files changed, 493 insertions(+), 27 deletions(-) (see Diff budget table for the per-file breakdown).
- Real orphan evidence (informed detection design, not fabricated): `~/dev/ultra-csm/build/tmp/pgdata.c2ugcsk3` (alive PID at audit time, self-cleaned moments later by its owning session) and `~/dev/ultra-csm/build/tmp/pgdata.nods_9x2` (dead PID `28463`, `stopping` status line) — both audited read-only via `kill -0`, never signaled or modified.
- Merge-mechanics check (K11): `gh api repos/:owner/:repo --jq .allow_auto_merge` → `true`; branch protection on `main` → `required_status_checks` present (`"eval + CSM scorecard"`). Mechanics ARE configured. Per this wave's explicit override, `gh pr merge --auto` was NOT run regardless — PR left OPEN for manual review, stated in the PR body.
