# Program Report 65 — MASTER_LIVE_BUILD Layer 3

Layer 3 moved Ultra CSM from "wired" to "running, measured, and honestly
bounded." It loaded the daily job, prepared the human-gated close-loop send,
proved adversarial safety against a live burner mailbox seed, migrated the
judge to Sonnet 5, scoped drift-power, and recorded the second-labeler skip
without manufacturing evidence.

## DoD Evidence

| Phase | Gate | Receipt |
| --- | --- | --- |
| Phase 9 sustained operation | LaunchAgent loaded, scheduled path wrote durable ledger, restart durability proved | PR #87 merge `1c60e9f`; `launchctl list` showed `com.ultracsm.operating-daily`; persistent DB retained `sweep.fired` after restart |
| Phase 9 monitoring | Sentry seam and alarm logic built; live Sentry DSN absent | Fake-transport tests green; missed-run alarm `{"alarms":["missed_run"],"sent":0,"sentry_configured":false}`; cost alarm `{"alarms":["cost_budget"],"sent":0,"sentry_configured":false}`; OA-4 remains open |
| Phase 10 close-loop prep | One burner-scoped pending proposal staged and stopped at OA-2 | PR #88 merge `19b7e45`; manifest `/Users/owieschon/ultra-csm-operating-runs/phase10/phase10_send_manifest.json`; proposal `241762ea-c0c6-4535-b04d-633140f9bc9b`; payload SHA `065c48c96d0cee6aab4896f0f3a9103e863393f2109dc4eea5df5dcd2af4c232`; `gmail_send_performed=false` |
| Phase 10 approval boundary | No self-approval and no send | Manifest `status=STOP_OWNER_APPROVAL_REQUIRED`; `owner_verdict_recorded=false`; ledger send count `0 -> 0` |
| Phase 11 live adversarial fire | Hostile burner message seeded and ignored by Slot B | PR #89 merge `123d54a`; `live_adversarial_drill.json`: `hard_ok=true`, `matching_messages=1`, `mailbox_seeded=true`, `draft_ignored_injection=true`, `contract_validator_passed=true` |
| Phase 11 safety boundary | No approval/send/verdict | Drill claim boundary: `submit_verdict_called=false`, `customer_send_performed=false`; one IMAP APPEND to the burner inbox only |
| Phase 12 judge migration | Paired migration adopted Sonnet 5 and revalidated | PR #90 merge `9eadfd1`; `eval/gold/judge_model_migration.json` `adopt=true`; overall McNemar `0/0`, `p_value=1.0`; `judge_validation_status()` `validated=true`, model `claude-sonnet-5`, failures `[]` |
| Phase 13 drift-power | Quality-drift claim scoped to current power | PR #91 merge `b37087b`; `eval/drift_power_csm.json` `hard_ok=true`, MDD `0.469`, all eight bad variants caught, `noop_equivalent` quiet |
| Phase 14 second labeler | Clean skip per OA-3 | PR #92 merge `12b3106`; no second labeler supplied; no inter-rater kappa fabricated |

## Operating Ledger

| Ledger | Span / Count | Receipt |
| --- | --- | --- |
| File operating log | 3 entries spanning dates `2026-07-05` to `2026-07-06`, story days 51-52 | `/Users/owieschon/ultra-csm-operating-runs/operating_log.jsonl` |
| Tick ledgers | `/2026-07-05/tick_state/tick_ledger.jsonl` 1 row; `/2026-07-06/tick_state/tick_ledger.jsonl` 2 rows | out-of-repo operating run directory |
| Persistent DB audit log | 230 rows: `value_model=207`, `slot_b.draft=11`, `judge.score=11`, `sweep.fired=1` | `psql "$ULTRA_CSM_DATABASE_ADMIN_URL" -Atc ... audit.event_log` |
| Fixture audit timestamp span | `2026-06-07 08:00:00-04` to `2026-06-07 08:00:00-04` | expected because the Phase 9 tick used fixed fixture/story time; operating log dates capture real run dates |

## Verification Table

| PR | Local gate | CI |
| --- | --- | --- |
| #87 Phase 9 | `make eval` 779 passed/1 skipped before owner merge; monitor/launchd tests green | eval + CSM scorecard 4m36s, UI 27s, Endor 5s |
| #88 Phase 10 | `make eval` 795 passed/1 skipped; focused prep tests 2 passed | eval + CSM scorecard green; merged |
| #89 Phase 11 | `make eval` 801 passed/1 skipped; adversarial battery `hard_ok=true` | eval + CSM scorecard 4m25s, UI 32s, Endor 5s |
| #90 Phase 12 | `make eval` 803 passed/1 skipped; judge migration `adopt=true` | eval + CSM scorecard 4m35s, UI 29s, Endor 4s |
| #91 Phase 13 | `make eval` 806 passed/1 skipped; drift power `hard_ok=true` | eval + CSM scorecard 4m36s, UI 28s, Endor 6s |
| #92 Phase 14 | docs-only skip report; `git diff --check` clean | eval + CSM scorecard 4m31s, UI 29s, Endor 5s |

## IF/THEN Branches

1. IF no `SENTRY_DSN` exists on disk, THEN Phase 9 proves the monitoring seam
   with fake transports and leaves OA-4 open instead of inventing a Sentry
   receipt.
2. IF Phase 10 reaches approval, THEN the build stops at OA-2. It staged the
   pending proposal and manifest; the owner must cast `submit_verdict`.
3. IF live adversarial input needs a real mailbox surface, THEN use the burner
   account only and record that the mailbox write was one hostile test IMAP
   APPEND, not a customer send.
4. IF the candidate judge wins the migration screen, THEN regenerate the formal
   validation artifacts before changing `JUDGE_MODEL_ID`. Phase 12 did this.
5. IF the current gold ladder only supports large-drop detection, THEN scope
   the drift claim to the measured MDD instead of saying "detects drift" broadly.
6. IF no second blind labeler exists, THEN skip Phase 14 and state the
   single-labeler ceiling.

## Owner Asks

- **OA-2 remains open:** proposal `241762ea-c0c6-4535-b04d-633140f9bc9b`
  is pending for owner approval; no system-side approval was cast or is allowed.
- **OA-3 remains unavailable:** no second labeler; Phase 14 skipped cleanly.
- **OA-4 remains open:** no `SENTRY_DSN` or `SENTRY_AUTH_TOKEN` was found, so
  live Sentry induced-error delivery is not proven.

## STOP Conditions

- Phase 10 stopped at OA-2 by design. No customer-facing approval/send occurred.
- Phase 14 skipped by design because no second labeler was supplied.

## Skeptical Reviewer

Layer 3 proves unattended local operation on persistent state, a loaded daily
job, durable audit events, a fully staged human-gated burner send, live
adversarial non-compliance, a current-model validated judge, and a quantified
drift-power boundary. It does **not** prove a real customer send, live Sentry
delivery, second-human judge ceiling, production retention lift, or real
production customers. Those would require the owner actions and external
deployments named above.

## Receipts Appendix

- Phase reports: `docs/PROGRAM_REPORT_59.md` through `docs/PROGRAM_REPORT_64.md`.
- Send manifest: `/Users/owieschon/ultra-csm-operating-runs/phase10/phase10_send_manifest.json`.
- Live adversarial drill: `/Users/owieschon/ultra-csm-operating-runs/phase11/live_adversarial_drill.json`.
- Judge migration: `eval/gold/judge_model_migration.json`.
- Drift power: `eval/drift_power_csm.json`.
- Operating logs: `/Users/owieschon/ultra-csm-operating-runs/operating_log.jsonl`.
