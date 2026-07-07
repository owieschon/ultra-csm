# BLOCKED - MP-A Phase A6 Owner On-Task Relabel Required

Dispatch: `/Users/owieschon/ultra-csm-dispatches/MP_A_INTEGRITY_CLOSURE.md`
Worktree: `/Users/owieschon/dev/ultra-csm-mpa-a6`
Branch: `codex/mpa-a6`

## STOP Condition

OA-A2 Option 3 / Definition A has been ratified. Codex has applied the scoped
on-task anchor and prompt sharpening, bumped the judge prompt to v9, and prepared
the blind relabel packet. Codex must now STOP until the owner labels
`on_task_relevance` for the full hard layer.

Codex must not choose a production judge model, must not relabel any gold case,
must not edit any human label, and must not edit the 0.6 gate or v8 judge
artifacts to force a pass.

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
- Owner ratified OA-A2 Option 3 / Definition A.
- Updated the `on_task_relevance` anchor in the labeling protocol, labeler anchor
  source, judge prompt, and `default_rubric()` description.
- Applied the two judge-prompt operational rules and bumped `JUDGE_PROMPT_VERSION`
  from `quality-judge-v8` to `quality-judge-v9`.
- Prepared blind relabel instructions: `docs/OA_A2_ONTASK_RELABEL_INSTRUCTIONS.md`.
- Prepared blind relabel packet:
  `eval/gold/slot_b_quality_hard_oa_a2_ontask_relabel_packet.jsonl`.

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
- The shipped prompt is now `quality-judge-v9`; the old v8 judge artifacts should
  fail closed until owner relabel and live rerun regenerate v9 evidence.
- Expected failing gate: `tests/test_judge_validation.py::test_validates_from_committed_evidence_artifacts`
  and `tests/test_judge_validation.py::test_live_semantic_quality_committed_artifact_is_proven`
  now fail because the source-of-truth judge validation is false.

## Owner Unblock

Fill `owner_on_task_relevance` with `1`, `2`, or `3` for every row in
`eval/gold/slot_b_quality_hard_oa_a2_ontask_relabel_packet.jsonl`, using only
`request`, `output_text`, and the sharpened anchor in
`docs/OA_A2_ONTASK_RELABEL_INSTRUCTIONS.md`.

After the relabel packet is returned, Codex may mechanically merge only
`on_task_relevance` into the hard labels/key, recompute overall pass, rerun
`judge_validation_status()` and the migration, and record whichever outcome
results.
