# MP-A Phase A6 OA-A2 Outcome

Dispatch: `/Users/owieschon/ultra-csm-dispatches/MP_A_INTEGRITY_CLOSURE.md`
Worktree: `/Users/owieschon/dev/ultra-csm-mpa-a6`
Branch: `codex/mpa-a6`

## Outcome

OA-A2 Option 3 / Definition A was ratified, the owner supplied blind
`on_task_relevance` relabels for the full 64-row hard layer, and Codex
mechanically merged only that dimension.

Codex must not choose a production judge model, must not relabel any gold case,
must not edit any human label, and must not edit the 0.6 gate to force a pass.
Those boundaries were preserved.

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
- Owner relabeled all 64 rows: `on_task_relevance` distribution is 1 -> 10,
  2 -> 42, 3 -> 12.
- Mechanically merged only `on_task_relevance` into the hard labels/key and
  recomputed overall pass.
- Re-ran Sonnet 5 v9 agreement and hard `cot@N` compare.
- Re-ran Sonnet 4.6 migration against the v9 Sonnet 5 baseline.

## Receipts

- `quality-gold-hard-status-csm`: 64/64 labeled, blind=true,
  ready_for_judge_validation=true.
- Sonnet 5 v9 `judge_validation_status()`: validated=false because of three
  hard aggregated false negatives in `H6b_warm_but_generic`:
  `slot-b-gold-e4e25cb08adb7f4a`, `slot-b-gold-fbea03fbc73ce874`,
  `slot-b-gold-e4678a581082477b`.
- Sonnet 5 v9 hard kappas all clear: grounding 0.755, on_task 0.736,
  account_specificity 1.0, priority_fidelity 0.9, tone_fit 0.794, safety 0.905.
- Sonnet 5 v9 hard false positives: 0; hard false negatives: 3; gate
  repeatability: 0.953.
- Sonnet 4.6 v9 migration candidate also fails: on_task_relevance kappa
  0.587 < 0.6 and on_task paired McNemar regressed.
- `eval/drift_power_csm.json`: expanded hard-layer n=64, MDD 0.089.
- Live spend: $8.343963, below the $15 ceiling.
- Additional OA-A2 live spend: failed v9 compare attempt $0.569110, successful
  v9 compare $4.398274, Sonnet 4.6 migration rerun $2.876685. The v9 agreement
  runner did not emit usage.

## Claim Boundary

This is OA-A2 Outcome 2. Keep Sonnet 5, but do not claim full autonomous judge
validation. The v9 prompt recovered `on_task_relevance` dimension agreement
(`0.289 -> 0.736` on hard `cot@N`), but the quality gate still fails closed
because the judge is lenient on 3/64 warm-but-generic drafts and would let those
bad drafts pass. Do not sharpen again just to clear those three rows. Use the
judge only with that boundary disclosed, and do not use `on_task_relevance` as an
autonomous pass/fail gate until a future owner-approved change validates the
false-open boundary.
