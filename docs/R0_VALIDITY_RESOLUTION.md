# R0 finding #3 resolution — claude_code judge revalidated against ground truth

<!-- clean-docs:purpose -->
Status: **PASS by a rule pre-registered before the run. R0 is resolved as a
claim rescope (owner-directed): the transport meets the same validity gate
the committed judge path met, rather than reproducing a single frozen run's
point estimates. Q3 (writer bake-off OPERATE) is unblocked.**
<!-- clean-docs:end purpose -->

## Why the original R0 bar was retired

Finding #3 (`docs/R0_KAPPA_BAND_FINDING.md`, PR #123): run 3 completed
127/127 items but landed outside the committed `judge_agreement.json` CI
bands — specifically a zero-width `[1.0, 1.0]` clean-layer safety_boundary
band that any single flipped item breaches, and a recomposed (not grown)
hard-layer false-open. Neither transport pins temperature; a
single-run-vs-single-run comparison cannot distinguish transport infidelity
from ordinary judge sampling variance. The owner directed a resolution that
measures against ground truth instead of against another run.

## Method (existing machinery only, frozen before execution)

- cot@N judge compare, `runs_per_case=5`, all 64 hard-layer gold items —
  the exact method that produced the committed `eval/gold/judge_compare.json`
  — executed through `ULTRA_CSM_LLM_TRANSPORT=claude_code` on the
  subscription (no metered API; dispatch §3 non-goal held).
- Loop code: `eval.judge_model_migration.run_candidate_arm` (checkpointed
  N-run scorer already in the repo), driven by an untracked glue script in
  the operator worktree; zero repo code modified for this run.
- Evaluation: `eval.judge_validation.judge_validation_status()` pointed at
  run 3's agreement artifact and this run's compare artifact (side paths;
  the committed evidence artifacts are untouched).
- Pre-registered decision rule (recorded in the operator session ledger
  BEFORE the run started): PASS = `validated_gating_dimensions` contains the
  same five as the committed evidence AND `excluded_gating_dimensions` ⊆
  {on_task_relevance}. FAIL = anything else → finding, stop, owner.

## Result

| Dimension | hard kappa (cot@5 aggregated, claude_code) | gate (0.6) |
| --- | --- | --- |
| grounding_fidelity | 0.627 | pass |
| on_task_relevance | 0.752 (reported; excluded from gating, see below) | pass |
| account_specificity | 1.0 | pass |
| priority_fidelity | 0.9 | pass |
| tone_fit | 0.78 | pass |
| safety_boundary | 0.905 | pass |

- `validated_gating_dimensions` = account_specificity, grounding_fidelity,
  priority_fidelity, safety_boundary, tone_fit — identical to the committed
  API evidence.
- `excluded_gating_dimensions` = on_task_relevance only, for the aggregate
  false-negative floor on the SAME three cases as the committed evidence
  (`slot-b-gold-e4678a581082477b`, `slot-b-gold-e4e25cb08adb7f4a`,
  `slot-b-gold-fbea03fbc73ce874`, all `H6b_warm_but_generic`).
- Clean layer (from run 3's artifact, same evaluation): every dimension's
  kappa ≥ 0.6 (minimum 0.659), zero false negatives.

The exclusion signature reproducing exactly — same dimension, same three
case ids, same family — is evidence the H6b blind spot is a property of the
judge model, not of the transport. The transport carries the judge
faithfully enough to reproduce its known failure.

## Claim rescope (for owner countersign on this PR)

R0's runbook mission line "verify the claude_code transport reproduces the
committed judge path" is resolved as: **the judge, run through the
claude_code transport, meets the same evidence-derived validity gate
(GATE_KAPPA=0.6 per dimension, zero aggregate false negatives, N-run modal
aggregation vs ground truth) that the committed judge path met, with the
identical gating scope.** Rulers untouched: same gate constants, same gold,
same held-out key, same judge prompt (quality-judge-v9), same model
(claude-sonnet-5). Downstream lanes (R2 bake-off, R3/R4) gate on the scope
guard, which is derived from exactly this class of evidence.

## Artifacts

- `eval/gold/judge_compare_claude_code.json` — this run's cot@5 compare
  (side path; committed `judge_compare.json` untouched).
- `eval/gold/judge_agreement_claude_code_run3.json` — run 3's agreement
  artifact, preserved from the Q2 lane (side path; committed
  `judge_agreement.json` untouched).

## Known gap (reported, not hidden)

Token telemetry for this lane was not captured: the judge's scoring path
discards the transport's usage fields, and this run used existing code
unmodified. A telemetry seam for judge lanes is future build work, not a
mid-lane edit.
