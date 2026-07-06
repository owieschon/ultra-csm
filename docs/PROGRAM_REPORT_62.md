# Program Report 62 — MASTER_LIVE_BUILD Phase 12

Phase 12 migrated the Slot B quality judge from `claude-sonnet-4-6` to
`claude-sonnet-5` only after the paired migration screen and the full validation
artifacts cleared.

## DoD Evidence

| Gate | Evidence | Result |
| --- | --- | --- |
| Paired migration screen runs | `PYTHONPATH=src:. .venv/bin/python -m eval.judge_model_migration --candidate-model claude-sonnet-5 ...` | `adopt=True`; overall McNemar `0/0`, `p_value=1.0`; no blockers |
| Candidate hard-layer validation | `eval/gold/judge_model_migration.json` | aggregated kappas: grounding `0.932`, on_task `0.769`, tone `0.859`, safety `0.625`, deterministic dims `1.0`; false-open overall ids `[]` |
| Adopted judge re-validates | `PYTHONPATH=src:. .venv/bin/python -m eval.run_quality_judge --model claude-sonnet-5 --max-tokens 1400 --output eval/gold/judge_agreement.json` + regenerated `eval/gold/judge_compare.json` | clean n=63 min judge kappa `0.653`, false_pos `0`, false_neg `0`; hard n=36 min aggregated kappa `0.625`, false_pos `3`, false_neg `0`, repeatability `1.0` |
| Source-of-truth status derives green | `PYTHONPATH=src:. .venv/bin/python - <<'PY' ... judge_validation_status() ... PY` | `validated: true`, `model_id: claude-sonnet-5`, `failures: []` |
| Model config updated | `src/ultra_csm/agent1/slot_b.py` | `JUDGE_MODEL_ID = "claude-sonnet-5"` |
| Cost estimates know new model | `src/ultra_csm/cost_tracker.py` | `claude-sonnet-5: (2.00, 10.00)` |
| Offline focused gates | pytest + ruff | `26 passed`; ruff `All checks passed!` |
| Full eval | `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 make eval` | `803 passed, 1 skipped, 1 warning in 132.24s` |

## IF/THEN Branches

1. IF the existing paired-McNemar lane was writer-migration only, THEN add a
   judge-specific migration script instead of bending writer artifacts into a
   judge decision. That is `eval/judge_model_migration.py`.
2. IF the first Sonnet 5 screen failed on malformed JSON after retries, THEN
   increase the candidate response budget and add per-case checkpointing. The
   successful run used those controls; the failed attempt cost is reported.
3. IF the candidate won the migration screen, THEN regenerate the shipped
   validation artifacts before changing `JUDGE_MODEL_ID`. Done.
4. IF the old `terse@N` arm belonged to Sonnet 4.6, THEN do not carry it into
   the new Sonnet 5 `judge_compare.json`; `judge_validation_status()` consumes
   only `cot@N`.

## Owner Asks

None for Phase 12. No `submit_verdict`, approval, customer send, secret print,
gold-label edit, threshold edit, or prompt edit occurred.

## STOP Conditions

None. The malformed JSON failure was handled as a retryable environment/model
output issue, then resolved by harness reliability controls.

## Skeptical Reviewer

This proves Sonnet 5 is non-regressed against the current single-labeler gold
and hard-key artifacts under the repo's N-run judge gate. It does not provide a
second human labeler ceiling, and it does not prove drift-detection power; those
remain Phase 14 and Phase 13 respectively.

## Receipts

- Migration artifact: `eval/gold/judge_model_migration.json`.
- Validation artifacts: `eval/gold/judge_agreement.json`,
  `eval/gold/judge_compare.json`.
- Status artifacts: `eval/gold/slot_b_quality_status.json`,
  `eval/gold/slot_b_quality_hard_status.json`.
- Decision log: `docs/DECISION_LOG.md`.
- Successful migration usage: 183 calls, 558,570 input tokens, 92,642 output
  tokens, `$2.043560`.
- Failed pre-hardening attempt usage: 25 calls, 76,410 input tokens, 6,874
  output tokens, `$0.221560`.
