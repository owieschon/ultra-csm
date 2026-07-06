# Program Report 56 — Master Live Build Phase 6: Live Lens Loop

Branch `codex/master-live-phase6` off `origin/main`
(`a69bdac`, PR #83 merged). This report captures Phase 6 of
`MASTER_LIVE_BUILD.md`: Risk, Expansion, Slot A, cohort/program rollups,
precedence, and rejection-ledger state are now wired into the tick/live-loop
artifact path.

## Scope

| Area | Change |
| --- | --- |
| Default triggers | `config/trigger_config.json` now includes `weekly_risk_sweep` and `weekly_expansion_sweep` book schedules next to `daily_ttv` |
| Tick loop | Fired Risk/Expansion runs are converted into the same work-queue artifact family as TTV, with cited evidence and proposal references |
| Precedence | Tick derives `FindingPacket` and `ActionPacket` objects from actual fired runs, evaluates `precedence-v1`, and writes visible findings, active actions, held actions, and ledger events |
| Rejection ledger | Tick consults `RejectionLedger` for every account/factor/motion work item and annotates recurrence keys in the work queue |
| Cohort/program layer | Tick builds cohort rollup packets from fired trigger/action records, so manager packets carry observed trigger and action throughput from the same loop |
| Slot A | The sweep calls `CaseNoteClassifier.classify(...)` on real case-note subjects and surfaces outputs as a work-item sidecar without changing the ratified priority/evidence spine |
| Batteries | Fixed stale `tier_gating_battery` unpack to match `_account_tier_and_motion`'s widened `(tier, motion, triggers)` return while preserving the same guard assertion |

## Gate Receipts

Focused tests:

```text
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 .venv/bin/python -m pytest tests/test_agent1_sweep.py tests/test_triggers.py tests/test_tick.py tests/test_regression_csm.py -q
46 passed in 7.15s
```

Lint:

```text
make lint
All checks passed!
```

Named Phase 6 batteries:

```text
make narrative-battery-csm canary-battery-csm tier-policy-battery-csm
narrative hard_ok=true; canary hard_ok=true; tier-policy hard_ok=true

make tier-gating-battery-csm
tier-gating hard_ok=true
```

Full eval:

```text
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 make eval
779 passed, 1 skipped, 1 warning in 129.06s (0:02:09)
eval/gold/slot_b_quality_status.json is current
eval/gold/slot_b_quality_hard_status.json is current
```

Production Slot A call-site grep:

```text
rg -n "\.classify\(" src/ultra_csm eval tests
src/ultra_csm/agent1/sweep.py:464:        outputs.append(classifier.classify(request))
```

## Tick Demo Receipts

`make tick-demo-csm` wrote `demo_state/tick_demo/tick_demo_csm.json` and the
per-day work queues. Day 0 proves Risk and Expansion entered the live loop:

```text
day 0: weekly_expansion_sweep fired for book
day 0: weekly_risk_sweep fired for book
```

Day-0 work queue evidence:

```text
expansion  weekly_expansion_sweep  98  crm          994f6508-9670-558a-b545-77092477f898  opportunity_type
risk       weekly_risk_sweep       98  cs_platform  f8504037-dc1a-50e4-bdd9-7900b1379444  health_score
```

Day-0 loop integration counts from `tick_work_queue_20260621.json`:

```text
precedence_findings=109
precedence_actions=98
held_actions=57
active_actions=41
rejection_ledger_checked=207
cohort_packet_count=14
```

Cohort work remains visible in the same tick artifact family:

```text
Cohort collapse: feature_shallow_depth affects 26 tech_touch accounts via play 'reactivate-stalled-module-cohort' -- one cohort_action covers all, not 26 individual motions.  26
```

## IF/THEN Branches

1. IF a Risk trigger fires, THEN tick calls `run_risk_lens`, records cited
   evidence, emits risk findings, and uses those findings as precedence
   blockers for customer-facing Expansion actions.
2. IF an Expansion trigger fires, THEN tick calls `run_expansion_lens`, records
   cited evidence, creates action packets, and marks conflicting customer
   actions held rather than hiding either finding.
3. IF a work item has `(tenant, account, factor, motion)` matching a prior
   rejection, THEN the tick artifact marks that recurrence with the matched
   rejection record; no hard-coded account rule is introduced.
4. IF Slot A classifies case-note text, THEN the output is visible as a
   sidecar only; it does not mutate priority score or evidence ids until that
   scoring contract is separately ratified.

## Skeptical Reviewer Paragraph

This phase proves the dormant lenses and manager layers execute in the same
daily loop and produce inspectable artifacts with evidence, precedence holds,
rejection-ledger checks, and cohort packets. It does not claim a real
production customer deployment or a retention outcome. It also does not
self-approve or send any customer-facing action: proposals remain pending and
precedence-held actions stay held for human review.

