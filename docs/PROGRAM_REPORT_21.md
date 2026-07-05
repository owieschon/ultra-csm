# Program Report 21 — Harvest 2: The Agent's Daily Operating Cadence

The drip-seeder unfolds the fleetops world every morning at 07:00; until
this dispatch, the agent only looked when a human ran it by hand. This
program builds the daily operating run: `scripts/operating/daily_run.sh`
computes today's story day from the frozen live-reseed anchor, runs the
deterministic surfaces (tick's live sweep, demo-sweep) as-of that day,
ledgers them with cost, and -- credentials permitting, under a hard $2
cap -- judges the day's Slot B drafts with report 23/Act1's already-built
validated instrument. Branch `codex/operating-cadence`, worktree-isolated
(`~/dev/ultra-csm-operating-cadence`) per this repo's convention.

One manual end-to-end run is verified with real artifacts (story day 51,
12 real work items with resolved motions, judge lane ran for $0.231). The
launchd job is built and `plutil`-validated but **NOT loaded** -- that is
an owner-authorized action per the profile's risk posture, requested at
the end of this report.

## Tripwires (K12)

None fired. One IF/THEN correction was made mid-flight, recorded below:
the dispatch's own verify-command for report 24's precondition
(`git log origin/main --oneline | grep -qi "motion resolution in tick"`)
does not match, because `--oneline` only shows commit *subjects* and that
phrase lives in commit 7ef9aa7's *body* (squashed under PR #31's merge
commit). Precondition treated as satisfied via full-message grep
(`git log --all -i --grep`) plus functional verification of the actual
code path -- see IF/THEN section below for the full reasoning.

## DoD Evidence

| Check | Command | Result |
| --- | --- | --- |
| Suite | `LC_ALL=en_US.UTF-8 make eval` | `610 passed, 1 skipped` -- baseline (fresh worktree) was `606 passed, 1 skipped`; +4 is `tests/test_operating_run.py` |
| Lint/hygiene | `make lint hygiene` | `All checks passed!` / exit 0 |
| Batteries untouched | `make narrative-battery-csm content-battery-csm` | both `hard_ok: true` (8 and 5 cases respectively, zero failures) |
| Run artifact | `ls ~/ultra-csm-operating-runs/2026-07-05/` | non-empty: `briefing.json`, `sweep.json`, `tick.json`, `judge_live.json`, `judge_live.log`, `tick_state/`, `judge_gold/` |
| **Briefing read with eyes (OBSERVED BEHAVIOR)** | opened `~/ultra-csm-operating-runs/2026-07-05/briefing.json` and read it | Coherent brief for story day 51: 12 real work items across a 181-account book, account names/priority factors match the world state (e.g. Ironhorse Freight Co, TTV score 143), **5 real `motion` values present** (`working_session` x2, `campaign_enroll` x2, `content_route` x4, `personal_email` x3, `cohort_action` x1) -- report 24 is merged, motions are live. Quote below. |
| Operating log | `wc -l < ~/ultra-csm-operating-runs/operating_log.jsonl` | `1` |
| Plist valid | `plutil -lint ~/Library/LaunchAgents/com.ultracsm.operating-daily.plist` | `OK` |
| Clean diff | `git diff --check` | exit 0 |
| Status | `make status` | `STATUS.md is current` |

## Phases completed

- **Phase 0** -- bootstrap: worktree, `PROGRESS.md`, precondition checks
  (drip alive, `seeded_through_day >= 50`, report 24 on main -- confirmed
  via full-message grep + functional read of `tick.py`), fresh-worktree
  `make setup` + `make eval` baseline (`606 passed, 1 skipped`). Gate:
  `launchctl list | grep -c ultracsm` -> `1`. No commit (bootstrap only).
- **Phase 1** -- `scripts/operating/daily_run.sh` + story-day test.
  Commit `3b55971`.
- **Phase 2** -- the one manual run, end to end. Commit `460d538` (also
  fixed the judge lane's error handling, discovered live: `set -euo
  pipefail` was letting a judge-subprocess failure kill the whole run,
  contradicting the Decisions section's "abort the lane, not the run").
- **Phase 3** -- launchd plist (built, linted, NOT loaded) +
  `docs/OPERATING_PROOF.md` v2. Commit `2f2e86e`.
- **Phase 4** -- this report, plus a self-check fix: my first
  `OPERATING_PROOF.md` draft accidentally broke `render_status.py`'s
  drift-disclosure detector by paraphrasing v1's exact matched phrase
  (`lacks a \`claim_boundary\``) and by letting prose bleed onto the
  `Date:` line. Caught by running `make status` and reading the diff,
  not assumed clean -- fixed in the same phase, verified `STATUS.md is
  current` with the drift flag correctly back to `true`. Report + PR
  below.

## One full briefing sample (Phase 2, story day 51)

From `~/ultra-csm-operating-runs/2026-07-05/briefing.json`
(`tick_work_queue_20260811.json`, copied out by `daily_run.sh`), work
item 0 -- real motion, real account, real cited evidence:

```
account_id: f16ceec8-7a3a-5d9d-a0ee-a2e7f119fc43  (Ironhorse Freight Co)
motion: working_session
reason: Ironhorse Freight Co has deterministic Time-to-Value score 143
  from milestones_overdue=50, days_overdue=40, success_plan_overdue=20;
  draft customer outreach. Evidence
  [evidence:4635cdb7-5bb5-5c43-acc1-5dc989d4d583],
  [evidence:afbc6091-985b-50e5-8522-e1a916af56c9],
  [evidence:7d61c11f-73d4-52f6-a738-33ab96634a61].
```

Two more distinct motions from the same run, for the record: work item 1
(`campaign_enroll`, Ridgeline Warehousing, TTV score 112) and work item 2
(`content_route`, Pinehill Transport, TTV score 62). Full priority
factors (thresholds, evidence sources, contributions) are in the artifact
itself -- this quote is the minimum slice proving the claim, not the
whole record.

## Judge lane receipt (Phase 2)

`~/ultra-csm-operating-runs/2026-07-05/judge_live.log`:

```
pinehill-transport       disposition=propose_customer_action  exemplars=True pass=True
meridian-fleet           disposition=propose_customer_action  exemplars=True pass=True
harborview-fleet         disposition=propose_customer_action  exemplars=True pass=True
artifact -> /Users/owieschon/ultra-csm-operating-runs/2026-07-05/judge_gold/judge_live_50.json
```

Preflight cost estimate: `$0.2310` against a `$2.00` cap (worst-case,
using `ultra_csm.cost_tracker`'s existing pricing table -- 3 slugs x [1
opus-4-8 writer call + 3 sonnet-4-6 judge calls]). Actual judge-status in
the operating log: `"judge_status": "ran"`, `"cost_usd": 0.231`.

## IF/THEN Branches Taken

1. **IF** the dispatch's literal precondition-check command
   (`git log origin/main --oneline | grep -qi "motion resolution in
   tick"`) does not match against `origin/main` **THEN** check the full
   commit message (not just the subject line) before concluding the
   precondition is unmet -- `git log --all -i --grep="motion resolution
   in tick"` finds commit `7ef9aa7` ("Adopt motion resolution in tick
   daily loop"), squashed under `9f7b018` ("Harvest 6: Tick motion
   adoption ... (#31)"), confirmed on `main`. Verified functionally too:
   `tick.py:233` passes `playbook_tenant_slug=TICK_PLAYBOOK_TENANT_SLUG`
   into `run_time_to_value_sweep`, `tick.py:239` runs `collapse_cohorts`.
   Severity: cosmetic mismatch between the dispatch's exact grep string
   and where git puts commit-message prose after a squash-merge, not an
   8+ fork -- proceeded without asking, precondition satisfied by
   evidence stronger than the literal command specified.
2. **IF** `tick.py --as-of` takes fixture-space dates (not real calendar
   dates) **THEN** derive the correct mapping before building the script,
   rather than guessing: `anchor.py`'s own translation rule
   (`translated_date = fixture_date + (anchor_date - fixture_seed_date)`)
   implies fixture `day_offset == story_day` for "today" when
   `fixture_seed_date == SEED_DATE` (verified: both are literally
   `2026-06-21`). Confirmed by direct computation and by running
   `tick --as-of 2026-08-11 --dry-run --json` and reading `"day": 51`
   back out of the response -- matched the hand-derived value exactly
   before it was ever wired into the script.
3. **IF** `run_tick_cli`'s stdout JSON (`TickResult.to_dict()`) never
   includes `work_items`/`motion` (confirmed by reading `tick.py:110-119`
   and by an empirical run that found zero `motion` occurrences in the
   printed JSON) **THEN** use the artifact it WRITES to disk
   (`tick_work_queue_<stamp>.json`) as the briefing, not the printed
   summary -- this is where `CSMWorkItem.motion` actually lives (`asdict
   (item)` in `_sweep_payload_for_trigger`). Verified empirically before
   committing: ran tick non-dry-run once, inspected the written file,
   found 12 `motion`-bearing work items, THEN wired the script to copy
   that specific file out.
4. **IF** the judge lane's subprocess fails for any reason (discovered:
   `anthropic` package not installed in the fresh worktree venv) **THEN**
   the script's own `set -euo pipefail` must not be allowed to kill the
   whole run -- caught on the very first live run attempt (traceback:
   `ModuleNotFoundError: No module named 'anthropic'`), fixed two ways:
   installed the same `anthropic==0.112.0` main's venv already carries
   (an untracked, ad hoc dependency in `pyproject.toml` -- installing it
   locally is environment setup, not a source edit), AND hardened the
   script itself (`set +e`/`set -e` bracket around the judge subprocess
   call) so a FUTURE failure degrades to `JUDGE_STATUS=failed` instead of
   killing the deterministic artifacts already written. Re-ran end to
   end after both fixes; judge lane completed for real ($0.231, 3/3 pass).
5. **IF** `docs/OPERATING_PROOF.md`'s rewrite changes the exact phrase
   `render_status.py` string-matches for its drift-disclosure check
   **THEN** that is a real regression in the doc's own self-check, not
   cosmetic -- caught by actually running `make status` and reading the
   diff (not assumed harmless), traced to two independent causes (a
   paraphrase that dropped the literal `` lacks a `claim_boundary` ``
   substring, and prose wrapped onto the `Date:` line breaking the date
   parse), fixed both, reran `make status`, confirmed the drift flag
   correctly reads `true` again and the date reads `2026-07-05` cleanly.

## Consolidated Owner Ask

1. **`launchctl load ~/Library/LaunchAgents/com.ultracsm.operating-daily.plist`**
   -- starts the standing 07:30 daily job. This is the designed pause
   per the profile's risk posture on standing jobs; nothing about this
   dispatch requires it to happen today. `plutil -lint` confirms the
   plist is valid; the script itself was kickstarted manually and
   verified end-to-end (this report's DoD table). Unload command is in
   `docs/OPERATING_PROOF.md` v2 if the owner wants to stop it later.
2. **`anthropic` is not in `pyproject.toml`** even though both the main
   worktree's venv and this dispatch's fresh worktree venv need it
   installed ad hoc for the judge lane to run. A future program should
   consider adding it to the `api`/`dev` extras so `make setup` alone
   is sufficient -- carried over as an observation, not fixed here
   (outside `scripts/operating/**` / `docs/OPERATING_PROOF.md`
   ownership).
3. **`eval/deep_vs_shallow_detection.json` still lacks a
   `claim_boundary`** -- unchanged open drift from OPERATING_PROOF v1,
   out of this dispatch's ownership map, carried forward verbatim.

## STOP Conditions

None fired.
- The drip job is alive and healthy (`launchctl list` shows it running,
  log entries within the last day, `seeded_through_day=50 >= 50`) -- no
  silent-failure STOP.
- No live WRITE was ever needed or performed; the judge lane and the one
  live-read-capable path (Gmail, via the six arcs' existing wiring) stay
  strictly read-only, per this dispatch's Sanctioned Exception.
- The judge lane respected the $2 cap comfortably ($0.231 actual,
  preflight-estimated before the call was ever made) -- no abort needed.
- `launchctl load` was never attempted -- it always stops for the owner,
  by design, and is the Owner Ask above, not a STOP.

## Skeptical Reviewer Paragraph

**N=1 manual run proves the mechanism, not operation.** The story-day
computation, the live tick sweep with real motions, the ledger append,
and the judge lane's cost-capped invocation all executed correctly
exactly once, for exactly one day (story day 51, 2026-07-05). That proves
the code path works end to end today. It does NOT prove the job will
keep working unattended tomorrow, next week, or across a machine restart
-- only `launchctl load`-ing the plist and observing N consecutive
scheduled days accumulate in `operating_log.jsonl` without silent failure
would prove operation, and this dispatch deliberately does not do that
(the load step is the owner's, by design). The judge lane ran for real in
this run (`ANTHROPIC_API_KEY` was present in this environment) and cost
$0.231 against a $2.00 cap -- a single successful run at low cost is
reassuring but is not evidence the cap logic correctly aborts a lane that
WOULD exceed it; that branch was verified by code inspection and the
preflight-estimate arithmetic, not by an actual over-cap run (there was
no way to force the default 3-candidate judge-live-csm shape over $2
without either a contrived pricing change outside ownership, or padding
the candidate count -- neither was in scope). Similarly, the
`JUDGE_STATUS=skipped_no_key` path was verified by reading the script's
logic, not by a live run with the key absent, since this environment's
key is genuinely present and temporarily unsetting it to test a code
path already covered by `run_verification.sh`'s identical
credential-check pattern felt like manufactured verification rather than
real evidence. Both untested branches are disclosed here rather than
silently assumed correct.

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `610 passed, 1 skipped` |
| `make lint hygiene` | `All checks passed!` / exit 0 |
| `make narrative-battery-csm content-battery-csm` | both `hard_ok: true` |
| `bash scripts/operating/daily_run.sh` (fresh, end-to-end) | exit 0; story_day=51, fixture_as_of=2026-08-11, judge_status=ran, cost_usd=0.231 |
| `ls ~/ultra-csm-operating-runs/2026-07-05/` | non-empty (7 entries) |
| `wc -l < ~/ultra-csm-operating-runs/operating_log.jsonl` | `1` |
| `plutil -lint ~/Library/LaunchAgents/com.ultracsm.operating-daily.plist` | `OK` |
| `launchctl list \| grep -c ultracsm` | `1` (drip only -- new job confirmed NOT loaded) |
| `git diff --check` | exit 0 |
| `make status` | `STATUS.md is current` |
| `git status --short` (pre-final-commit) | `M STATUS.md`, `M docs/OPERATING_PROOF.md` (this phase's fix, committed with this report) |

## Receipts appendix

- Commits this program: `3b55971` (Phase 1: daily run script + test),
  `460d538` (Phase 2: first verified run + judge-lane error-handling
  fix), `2f2e86e` (Phase 3: plist + proof doc v2).
- Baseline `make eval` (fresh worktree, before any commit on this
  branch): `606 passed, 1 skipped` (main's own baseline was `606 passed,
  1 skipped` too -- no drift from `main`, since this worktree forked from
  synced `main` at `8a86806`).
- Run artifacts (out-of-repo, never committed):
  `~/ultra-csm-operating-runs/2026-07-05/{tick.json,sweep.json,
  briefing.json,judge_live.json,judge_live.log,tick_state/,judge_gold/}`,
  `~/ultra-csm-operating-runs/operating_log.jsonl`.
- Diff budget: 2 files (Phase 1) + 1 file (Phase 2) + 1 file (Phase 3) +
  2 files (Phase 4 fix, `STATUS.md` + `docs/OPERATING_PROOF.md`) + this
  report = 7 files across 4 commits, well within the 12-file/900-line
  guidance.
- Files owned and touched, verified via `git status --short` before every
  commit: `scripts/operating/daily_run.sh`, `tests/test_operating_run.py`,
  `docs/OPERATING_PROOF.md`, `STATUS.md` (auto-regenerated by `make
  status` from `docs/OPERATING_PROOF.md`'s own content -- not hand-edited),
  `docs/PROGRAM_REPORT_21.md` -- no others.
  `~/Library/LaunchAgents/com.ultracsm.operating-daily.plist` built
  out-of-repo per the ownership map. `src/ultra_csm/**`, batteries, the
  drip seeder, and `anchor.json` were read but never edited.
- Precondition full-message grep receipt: `git log --all -i
  --grep="motion resolution in tick"` -> `7ef9aa7 Adopt motion resolution
  in tick daily loop` (and its squash parent `9f7b018`).
- Cost preflight receipt: `writer per-call estimate (opus): 0.0275`,
  `judge per-call estimate (sonnet, reasoning): 0.0165`, `projected total
  for default judge_live_csm run: 0.231` (computed via
  `ultra_csm.cost_tracker.estimate_call_cost`/`compute_cost`, read-only
  import).

## Merge policy

Per this dispatch's own Merge policy section (kernel v1.1 K11), verified
mechanics first: `gh api repos/:owner/:repo --jq .allow_auto_merge` ->
`true`; `gh api repos/:owner/:repo/branches/main/protection` -> configured
(required status check `eval + CSM scorecard`, not a 404). Both
confirmed auto-merge is actually set up, so per the dispatch's own
instruction: `gh pr merge --auto --merge` was run once the PR was open
and this report's DoD table was clean. Not left open by a stricter,
self-imposed policy -- the dispatch's own conditional says to merge here,
and this program follows it exactly.
