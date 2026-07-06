# BLOCKED - MP-A Phase A6 Owner Model Decision Required

Dispatch: `/Users/owieschon/ultra-csm-dispatches/MP_A_INTEGRITY_CLOSURE.md`
Worktree: `/Users/owieschon/dev/ultra-csm-mpa-a6`
Branch: `codex/mpa-a6`

## STOP Condition

Phase A6 Step 5 / OA-A2 is now reached: the owner must decide the judge model path.
Codex must not choose the production judge model, must not relabel any gold case, and
must not edit the 0.6 gate to force a pass.

## Completed Work

- Authored 28 new adversarial hard-layer candidate rows.
- Staging file: `eval/gold/slot_b_quality_hard_a6_expansion.jsonl`
- Held-out stress key: `eval/gold/slot_b_quality_hard_a6_expansion_key.jsonl`
- Labeler-safe instructions: `docs/A6_HARD_GOLD_LABELING_INSTRUCTIONS.md`
- Owner blind labels were supplied and mechanically validated: 28 rows, 4 pass, 24 fail.
- Ratified hard layer is now 64 rows in `eval/gold/slot_b_quality_hard.jsonl`.
- Ratified hard key is now 64 rows in `eval/gold/slot_b_quality_hard_key.jsonl`, with
  the A6 expected vectors derived mechanically from owner `human_labels`.
- Re-ran Sonnet 5 expanded hard agreement and `cot@N` compare.
- Re-ran Sonnet 5 vs Sonnet 4.6 migration comparison at 64 cases / 5 runs per case.
- Re-ran drift-power with expanded hard-layer power included.

## Receipts

- `quality-gold-hard-status-csm`: 64/64 labeled, blind=true,
  ready_for_judge_validation=true.
- Sonnet 5 `judge_validation_status()`: validated=false; blocker
  `hard on_task_relevance kappa 0.289 < 0.6`.
- Sonnet 5 expanded hard kappas: grounding 0.758, on_task 0.289,
  account_specificity 1.0, priority_fidelity 0.9, tone_fit 0.794, safety 0.905.
- Sonnet 4.6 migration candidate also fails: on_task_relevance kappa 0.41 < 0.6.
- McNemar overall pass/fail: 0/0 discordant pairs, p=1.0.
- Safety fail-open: 0 for both Sonnet 5 and Sonnet 4.6.
- `eval/drift_power_csm.json`: expanded hard-layer n=64, MDD 0.089.
- Live spend: $8.343963, below the $15 ceiling.
- Expected failing gate: `tests/test_judge_validation.py::test_validates_from_committed_evidence_artifacts`
  and `tests/test_judge_validation.py::test_live_semantic_quality_committed_artifact_is_proven`
  now fail because the source-of-truth judge validation is false.

## Owner Unblock

Choose one of:

1. Keep Sonnet 5 despite expanded-set validation=false.
2. Roll back to Sonnet 4.6 despite its own expanded-set validation=false.
3. Sanction a narrow rubric-citing prompt/scorer fix for the observed on-task/grounding
   boundary, then rerun the cited verification.

After the owner decision, resume A6 by recording the decision in `docs/DECISION_LOG.md`,
making only the owner-approved model/prompt/scorer change if any, and rerunning the relevant
validation gates.
