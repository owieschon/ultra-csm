# Program Report 58 - Master Live Build Layer 2: Wire

Branch `codex/master-live-phase8` off `origin/main`
(`37bec5c`, PR #85 merged). This report captures Phase 8 of
`MASTER_LIVE_BUILD.md` and closes the Layer 2 wire section across Phases 5-8:
persistent state, live lenses, live serving, and the closed audit ledger with
outcome re-observation.

## Scope

| Area | Change |
| --- | --- |
| Phase 5 persistence | Persistent Postgres runtime, migration runner, durability proof, and tenant-isolated RLS paths are the state foundation for later live work |
| Phase 6 lenses | Risk and expansion triggers are live in the tick path, with precedence/rejection-loop behavior captured in the packet instead of remaining dormant |
| Phase 7 serving | API/MCP can serve a live-backed data plane for the granted Salesforce/Rocketlane/Gmail posture while preserving fixture fallback |
| Phase 8 audit ledger | Added append-only `audit.event_log` with tenant RLS, idempotent event source refs, and `/ledger` coverage for operational events |
| Phase 8 outcome loop | Gmail draft commits now write `gmail.commit`, enqueue `reobserve.queue`, and support read-only `reobserve.result` evidence collection |
| Phase 8 UI | Risk, Expansion, and Program lens chips render as live lens controls instead of disabled placeholder labels |

## Phase 8 Definition Of Done

| Gate | Receipt |
| --- | --- |
| Append-only audit event storage | `migrations/0010_audit_event_log.sql` creates `audit.event_log`, grants runtime SELECT/INSERT, enables and forces RLS, and blocks UPDATE/DELETE/TRUNCATE |
| Ledger gap closed | Live API verification returned `ledger_gap=[]` with operational events in `/ledger` |
| Sweep and tick producers | `/sweep` and `tick.py` write `sweep.fired`, `value_model`, `slot_b.draft`, and `judge.score` audit rows |
| Gmail commit trail | Successful draft creation with an audit context writes `gmail.commit` and queues re-observation |
| Re-observation | `perform_due_reobservations(...)` reads prior queued work and writes bounded read-only `reobserve.result` evidence |
| UI lens activation | Browser verification found no `no live source yet` placeholder and lens chip titles `lens: risk`, `lens: expansion`, and `lens: program` |

## Gate Receipts

Baseline before Phase 8 edits:

```text
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 make eval
784 passed, 1 skipped, 1 warning
eval/gold/slot_b_quality_status.json is current
eval/gold/slot_b_quality_hard_status.json is current
```

Focused Phase 8 tests:

```text
pytest tests/test_ui_contract.py::TestLedgerEndpoint \
  tests/test_tick.py::test_tick_runs_sweep_writes_provenance_and_preserves_action_tier \
  tests/test_email_drafts.py -q
10 passed, 1 warning in 2.17s
```

Python lint:

```text
.venv/bin/ruff check src eval tests scripts
All checks passed!
```

UI gates:

```text
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 make ui-check
npm run lint: 0 errors, 6 existing React hook warnings
npm run build: Compiled successfully
```

Full eval:

```text
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 make eval
786 passed, 1 skipped, 1 warning in 130.53s (0:02:10)
eval/gold/slot_b_quality_status.json is current
eval/gold/slot_b_quality_hard_status.json is current
```

Tick demo:

```text
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 make tick-demo-csm
artifact: demo_state/tick_demo/tick_demo_csm.json
```

Live API ledger receipt:

```text
POST /sweep
GET /ledger?limit=200
ledger_gap=[]
events=gate.propose,judge.score,slot_b.draft,sweep.fired,value_model
event_count=24
```

Browser receipt against `http://127.0.0.1:8000/ui/`:

```text
title: ultra.csm - operations surface
bodyIncludesNoLiveSource: false
Adoption title: lens: adoption
Risk title: lens: risk
Expansion title: lens: expansion
Program title: lens: program
```

## IF/THEN Branches

1. IF `audit.event_log` has not been migrated, THEN `/ledger` reports the
   expected operational event names as a gap instead of pretending the ledger
   is closed.
2. IF a producer retries the same operational event, THEN the
   `(tenant_id, event_type, source_ref)` uniqueness rule keeps the row
   idempotent.
3. IF Gmail draft creation runs without an audit context, THEN existing
   draft-only behavior is unchanged and no audit row is written.
4. IF a queued re-observation has no prior result, THEN the re-observer reads
   bounded data-plane evidence and records one result row tied to the original
   proposal.
5. IF an operational row has no proposal id, THEN it can still be recorded
   with account/detail/source refs and a nullable `proposal_id`.

## Owner Review Boundary

This phase includes a database migration, so the PR is left open for owner
review under OA-5. No `submit_verdict` was cast, no real customer send was
approved, and no Gmail send endpoint was added.

## Skeptical Reviewer Paragraph

Layer 2 now proves that live serving can operate on persistent state and that
the key operational actions leave a closed audit trail with a bounded
re-observation hook. It does not prove production customer outcomes, retention
causality, or a fully deployed enterprise loop. Gmail remains draft-only unless
the owner approves the staged action, and outcome evidence is limited to the
connected read scopes and synthetic/local verification available in this build.
