# BLOCKED - MP-A Phase A6 Owner Labels Required

Dispatch: `/Users/owieschon/ultra-csm-dispatches/MP_A_INTEGRITY_CLOSURE.md`
Worktree: `/Users/owieschon/dev/ultra-csm-mpa-a6`
Branch: `codex/mpa-a6`

## STOP Condition

Phase A6 Step 2 / OA-A1 is now reached: the owner must label the expanded hard-gold
candidate rows blind. Codex must not label any gold case, must not run the judge on
these staged rows before labels exist, and must not choose the judge model.

## Completed Work

- Authored 28 new adversarial hard-layer candidate rows.
- Staging file: `eval/gold/slot_b_quality_hard_a6_expansion.jsonl`
- Held-out stress key: `eval/gold/slot_b_quality_hard_a6_expansion_key.jsonl`
- Labeler-safe instructions: `docs/A6_HARD_GOLD_LABELING_INSTRUCTIONS.md`
- Existing ratified hard layer remains 36 rows and was not edited.
- No human labels were filled by Codex.
- No judge or migration run was executed on the new staged rows.

## Receipts

- `wc -l`: 28 staging rows and 28 key rows.
- Machine check: `labels_present=0`, `key_expected_vectors=0`,
  `key_intended_dims=0`, `safety_focus=28`.
- `make lint`: green.
- `pytest tests/test_gold_slot_b_hard.py -q`: 8 passed.
- `make eval`: 810 passed, 1 skipped; existing gold status checks current.

## Owner Unblock

Fill `human_labels` for every row in
`eval/gold/slot_b_quality_hard_a6_expansion.jsonl`, using only
`docs/A6_HARD_GOLD_LABELING_INSTRUCTIONS.md` while labeling. Do not open the held-out key
or judge outputs during labeling.

After owner labels are complete, resume A6 by validating the labeled staging file,
appending it to the ratified hard layer, re-deriving judge agreement, rerunning the
Sonnet-5-vs-4.6 migration/MCNemar analysis, and stopping again for OA-A2 if the expanded
set changes the model verdict.
