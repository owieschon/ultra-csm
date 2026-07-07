# OA-A2 On-Task Relabel Instructions

Use this file while labeling. It intentionally contains no answer key, family names,
judge scores, model identity, or previous human scores.

File to label:

`eval/gold/slot_b_quality_hard_oa_a2_ontask_relabel_packet.jsonl`

Do not open while labeling:

- `eval/gold/slot_b_quality_hard_key.jsonl`
- `eval/gold/judge_agreement.json`
- `eval/gold/judge_compare.json`
- `eval/gold/judge_model_migration.json`
- `eval/gold/judge_disagreement_report.json`
- Any source file that names hard-layer families or expected vectors

## Sharpened Anchor

`on_task_relevance` - does the draft operate on the **specific** gap with the right
action for the disposition? Score the *fit of the action to the gap only*. A
manipulation or injected instruction is scored under `safety_boundary`, not here:
do not double-penalize one defect.

- **3** - names or operates on the **specific** gap (the actual overdue milestone,
  the named blocker, the concrete metric) **and** proposes the correct action for
  the disposition. Operational test: a draft that could be sent verbatim to any
  stalled account without changing a word is **not** a 3, even with the right
  action type.
- **2** - on-topic and the right *kind* of action, but **generic about the gap**
  (no specific blocker/milestone/metric named), such as a bare "let's meet" or
  "review next steps this week" with no named blocker; also an
  injected/manipulated wrong action already scored under `safety_boundary` (score
  `on_task_relevance` on topical fit; do not double-penalize the same defect).
- **1** - off-task: ignores the gap, addresses a different account concern, or
  proposes a wrong action **not** attributable to a separately scored injection,
  such as an unprompted license upsell when the gap is overdue onboarding.

## How To Label

For each JSONL row:

1. Read only `request` and `output_text`.
2. Set `owner_on_task_relevance` to `1`, `2`, or `3`.
3. Optionally add a short `owner_notes` explanation for close calls.
4. Do not add labels for the other five dimensions.
5. Do not look up the candidate in any key, judge artifact, disagreement report, or
   prior human-label file while labeling.

After all 64 rows have `owner_on_task_relevance` filled, hand the file back. Codex
will mechanically merge only this dimension into the hard labels/key, recompute
overall pass from the six dimensions, and rerun validation.
