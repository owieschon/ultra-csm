# Program Report 59 - Master Live Build Phase 9: Sustained Operation

Branch `codex/master-live-phase9` off `origin/main`
(`79a023e`, PR #86 merged). This report captures Phase 9 of
`MASTER_LIVE_BUILD.md`: load the daily job, run it through launchd against
persistent state, and wire monitoring/alarms with an honest Sentry credential
boundary.

## Scope

| Area | Change |
| --- | --- |
| LaunchAgent | Added `scripts/operating/install_launch_agent.py` to regenerate `com.ultracsm.operating-daily.plist` for the current worktree instead of the old operating-cadence path |
| Persistent DB | Added `scripts/operating/ensure_local_persistent_db.py` to provision a local persistent Postgres runtime and write `/Users/owieschon/ultra-csm-operating.env` with local socket DSNs |
| Daily run | Updated `scripts/operating/daily_run.sh` to resolve its repo root from its own path, dotenv-load allowlisted env vars, wrap the run in Sentry check-ins, and write monitor alarm output |
| Monitoring | Added `ultra_csm.operating_monitor` for Sentry envelope events/check-ins, missed-run alarms, and daily cost-budget alarms |
| API errors | Unhandled API exceptions now call the same monitor seam before returning the existing 500 response |
| Tests | Added fake-transport tests for Sentry envelopes/alarms and LaunchAgent rendering tests |

## Definition Of Done

| Gate | Receipt |
| --- | --- |
| LaunchAgent loaded | `launchctl list | grep com.ultracsm.operating-daily` -> `- 0 com.ultracsm.operating-daily` |
| Plist valid | `plutil -lint /Users/owieschon/Library/LaunchAgents/com.ultracsm.operating-daily.plist` -> `OK` |
| Scheduled path run | `launchctl kickstart gui/$(id -u)/com.ultracsm.operating-daily` completed; latest launchd status `0` |
| Durable DB ledger | After the run, persistent `audit.event_log` contains `sweep.fired` with `source_ref=tick:2026-08-12:sweep.fired` and detail `Tick fired 3 trigger runs and created 206 proposals` |
| Restart durability | `pg_ctl ... restart` completed, then the same `audit.event_log` source ref was still present |
| Alarm simulation | Missed-run simulation returned `{"alarms":["missed_run"],"sent":0,"sentry_configured":false}`; cost simulation returned `{"alarms":["cost_budget"],"sent":0,"sentry_configured":false}` |
| Sentry error path | Fake-transport tests verify check-in/event envelopes; live induced send is blocked because no `SENTRY_DSN` exists on disk |

## Gate Receipts

Baseline:

```text
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 make eval
786 passed, 1 skipped, 1 warning in 133.24s (0:02:13)
eval/gold/slot_b_quality_status.json is current
eval/gold/slot_b_quality_hard_status.json is current
```

Focused Phase 9 tests:

```text
pytest tests/test_operating_monitor.py tests/test_operating_launchd.py tests/test_operating_run.py -q
11 passed in 0.29s
```

Focused lint:

```text
ruff check src/ultra_csm/api.py src/ultra_csm/operating_monitor.py \
  scripts/operating/install_launch_agent.py \
  scripts/operating/ensure_local_persistent_db.py \
  tests/test_operating_monitor.py tests/test_operating_launchd.py
All checks passed!
```

Launchd:

```text
plutil -lint /Users/owieschon/Library/LaunchAgents/com.ultracsm.operating-daily.plist
/Users/owieschon/Library/LaunchAgents/com.ultracsm.operating-daily.plist: OK

launchctl list | grep ultracsm
- 0 com.ultracsm.operating-daily
- 0 com.ultracsm.narrative-drip
```

Scheduled-path run:

```text
Ultra-CSM daily operating run: 2026-07-06
story_day=52 fixture_as_of=2026-08-12
Run complete: 2026-07-06 (story day 52)
Artifacts: /Users/owieschon/ultra-csm-operating-runs/2026-07-06
Ledger: /Users/owieschon/ultra-csm-operating-runs/operating_log.jsonl
```

Persistent DB source ref:

```text
sweep.fired|tick:2026-08-12:sweep.fired|Tick fired 3 trigger runs and created 206 proposals
```

Idempotent repeat run:

```text
judge.score|11
slot_b.draft|11
sweep.fired|1
value_model|207
```

## Owner Ask

OA-4 remains open: the name-only search found no `SENTRY_DSN` or
`SENTRY_AUTH_TOKEN` in `/Users/owieschon/ultra-csm-live-creds.env` or
`/Users/owieschon/dev/*/.env`. Add `SENTRY_DSN` to
`/Users/owieschon/ultra-csm-live-creds.env`, then rerun the induced-error
receipt to prove delivery in the real Sentry project.

## IF/THEN Branches

1. IF the LaunchAgent plist already exists, THEN Phase 9 regenerates it for the
   current worktree before loading it.
2. IF `/Users/owieschon/ultra-csm-live-creds.env` is not shell-sourceable, THEN
   `daily_run.sh` uses a dotenv parser and exports only allowlisted names.
3. IF no Sentry DSN is configured, THEN monitoring calls no-op with
   `sentry_configured=false` and the daily job continues.
4. IF the optional judge lane lacks the `anthropic` package in the fresh venv,
   THEN it records `skipped_no_anthropic_package` instead of failing the run.
5. IF launchd kickstarts the same `as_of` twice, THEN audit source refs remain
   idempotent and no duplicate `sweep.fired` row is created.

## Skeptical Reviewer Paragraph

This phase proves a loaded launchd job can run the current merged code against
persistent state, write durable audit rows, survive a database restart, and
evaluate monitoring alarms through tested Sentry envelope/check-in payloads. It
does not prove live Sentry ingestion, because no `SENTRY_DSN` exists on disk;
that receipt is deliberately blocked on OA-4 rather than faked. It also does not
claim weeks of unattended operation yet: it proves the schedule is loaded and
the scheduled path runs once cleanly.
