# Operating Proof (v2)

<!-- sourcebound:purpose -->
Date: 2026-07-05.
<!-- sourcebound:end purpose -->

Supersedes the v1 note (see git history for this file) -- that version
proved local operation against `run_verification.sh`'s core gates; this
version proves the daily operating run built for
`docs/PROGRAM_REPORT_21.md`.

## Claim Boundary

**One verified manual run proves the mechanism works: the story-day
computation, the deterministic surfaces (tick's live sweep, demo-sweep),
the ledger, and the credentialed judge lane, all execute correctly and
produce the expected artifact shapes for one real day.**

**It does NOT prove operation.** Operation -- the job actually running
unattended, every morning, for weeks, without silent failure -- can only be
demonstrated by N consecutive scheduled days accumulating in
`operating_log.jsonl` and the launchd stdout/stderr logs. This note claims
only the first. The launchd job is built and validated but **not loaded**;
loading it (starting the standing schedule) is an owner-authorized action,
not something this dispatch performs, per the profile's risk posture on
standing jobs.

## Operating Surface

`scripts/operating/daily_run.sh`:

1. Computes `story_day = (today - anchor_date).days` from the frozen
   `~/ultra-csm-corpus-runs/live-reseed-20260704/anchor.json` -- the exact
   formula `drip_seed.py` uses, reused not reimplemented (locked down by
   `tests/test_operating_run.py` against three hand-computed dates).
2. Maps `story_day` onto the fixture-day-offset space `tick.py` /
   `demo-sweep` already use (`fixture_as_of = SEED_DATE + story_day`, since
   `anchor.py`'s own translation rule implies the two axes are the same
   count of days for "today").
3. Runs `ucsm tick --as-of <fixture_as_of>` **live** (not `--dry-run`) so
   the real sweep resolves motions (`CSMWorkItem.motion`, wired by report
   24/PR #31's `playbook_tenant_slug` + `collapse_cohorts` adoption) and
   writes `tick_work_queue_<stamp>.json` -- copied out as `briefing.json`.
4. Runs `ucsm demo-sweep --day <story_day> --deep --json` as the
   health/priority scorecard (`sweep.json`), feeding `accounts_flagged`
   into the ledger line.
5. Judge lane: if `ANTHROPIC_API_KEY` is present (checked in the
   environment, then in `$ANTHROPIC_ENV_FILE` or
   `~/dev/parts-cs-agent/.env`), pre-flights a worst-case cost estimate
   (via the existing `ultra_csm.cost_tracker.estimate_call_cost` /
   `compute_cost`, no new pricing logic) against a **hard $2/run cap** and,
   if under cap, invokes the already-built `eval.judge_live_csm` (report
   23/Act1's judge-on-live runner) to score the day's Slot B drafts with
   the validated `cot@N` instrument (`docs/DECISION_LOG.md`). Over cap:
   the LANE aborts, not the run. Absent key: a loud skip line, exit 0.
6. Appends exactly one line to `~/ultra-csm-operating-runs/
   operating_log.jsonl`: date, story day, accounts flagged, judge status,
   cost.

All artifacts land in `~/ultra-csm-operating-runs/<date>/` and are never
committed.

## Observed Result (2026-07-05 manual run, story day 51)

```
story_day=51 fixture_as_of=2026-08-11
tick: 12 real work items, motions resolved (working_session x2,
  campaign_enroll x2, content_route x4, personal_email x3, cohort_action x1)
demo-sweep: 181-account book scored
judge lane: ran (ANTHROPIC_API_KEY present) -- 3 candidates
  (pinehill-transport, meridian-fleet, harborview-fleet), all pass=true,
  cost $0.231 (cap $2.00)
operating_log.jsonl: gained exactly one line
```

The briefing artifact was read with eyes (not just schema-checked): account
names, priority factors, and evidence ids resolve to the actual narrative
book state at story day 51 (e.g. Ironhorse Freight Co, TTV score 143,
`milestones_overdue=50/days_overdue=40/success_plan_overdue=20`,
motion=`working_session`, evidence ids resolving to real telemetry/CS
platform sources) -- see `docs/PROGRAM_REPORT_21.md`'s receipts appendix
for the full 3-line quote.

## Degradation Ladder

The judge lane's cost cap and credential check are the degradation points
this run added. Both were exercised as designed: cap not hit (projected
$0.231 vs $2.00 cap), key present so the "loud skip" path was NOT exercised
in this run (see `daily_run.sh`'s `JUDGE_STATUS=skipped_no_key` branch for
the unexercised path -- covered by code inspection, not a live run, since
this environment has a working key).

## launchd (built, validated, NOT loaded)

Plist: `~/Library/LaunchAgents/com.ultracsm.operating-daily.plist`.
Scheduled for 07:30 (after the drip's 07:00), stdout/stderr to
`~/ultra-csm-operating-runs/operating_{stdout,stderr}.log`.

Validated: `plutil -lint ~/Library/LaunchAgents/com.ultracsm.operating-daily.plist` -> OK.

Script kickstarted manually end-to-end (see Observed Result above) --
NOT via `launchctl`.

**To load (owner-authorized action only):**

```bash
launchctl load ~/Library/LaunchAgents/com.ultracsm.operating-daily.plist
```

This starts a standing daily job at 07:30 that runs `daily_run.sh`
unattended, including live credentialed judge-lane calls (capped at
$2/run) whenever `ANTHROPIC_API_KEY` is resolvable at run time.

**To unload:**

```bash
launchctl unload ~/Library/LaunchAgents/com.ultracsm.operating-daily.plist
```

## Open Drift

None new. `eval/deep_vs_shallow_detection.json` currently lacks a `claim_boundary` (noted in v1, unchanged) -- out of ownership map for this dispatch.
