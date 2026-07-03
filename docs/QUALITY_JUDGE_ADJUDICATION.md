# Quality Judge Adjudication

Status: iteration-2 decision record for the Slot B quality judge. The purpose is to keep
the judge-validation path evidence-driven: audit result, bucket counts, owner decisions,
and the exact implementation response.

## Fresh Audit

The second blind agreed-cell audit passed `10/10` under the tightened rubric. That means
the agreed-cell baseline is calibrated well enough to proceed with the disagreement
review. The first audit result (`8/10`) was classified as rubric ambiguity and led to the
grounding-vs-safety clarification.

## Disagreement Buckets

The adjudication covered `261` disagreeing cells.

| Bucket | Count | Meaning |
|---|---:|---|
| Label error | 8 | Human label cell contradicts the clarified anchor. |
| Rubric ambiguity | 76 | Anchor text did not define the scoring boundary tightly enough. |
| Judge systematic error | 135 | Judge applied a repeatable but wrong scoring rule. |
| Dimension conflation | 42 | Judge imported one dimension's defect into another dimension. |
| Candidate rendering defect | 0 | Generated candidate text rendered the intended defect. |

## Ratified Decisions

### D1: Grounding Scope

`grounding_fidelity` means truthfulness only. It asks whether the output fabricates,
misstates, or overstates evidence-backed facts. It does not score whether the output says
enough. Evidence-detail thoroughness belongs to `account_specificity`.

### D2: Priority Scoring

`priority_fidelity` is deterministic in the agreement harness. The typed request already
contains the score and factors, so the judge should not decide whether rendered text names
the correct score and factor names. The deterministic scorer uses this boundary:

- `3`: reason states the deterministic score and real factor names.
- `2`: reason states the score or correct risk theme without factor names.
- `1`: reason contradicts or misrepresents the score/factors.

### D3: Specificity And Tone

`account_specificity=3` requires at least one account-specific operational detail beyond
inserted names: the actual blocker, capability, metric, or evidence-backed situation.
Name-only personalization is `2`; interchangeable boilerplate is `1`.

`tone_fit=3` means professional-direct: no sales pitch, no over-casual phrasing, no
bureaucratic or legalese stiffness. Minor register drift is `2`. A draft that would
embarrass or undermine the CSM is `1`.

## Iteration 2 Changes

- Updated the human protocol and tap-through anchors.
- Updated the judge prompt to import the ratified definitions.
- Removed `priority_fidelity` from the model-scored dimensions and filled it with a
  deterministic scorer.
- Added the non-conflation rule: one defect, one dimension.
- Re-ran agreement and diagnosis under `quality-judge-v3`.

## Iteration 2 Results

The revision did not validate the semantic judge. That is the expected stopping point
before any third prompt iteration.

`make judge-agreement-csm`:

| Layer | Min judge-scored kappa | Exact vectors | False positives | False negatives | Deterministic priority kappa |
|---|---:|---:|---:|---:|---:|
| Clean | 0.081 | 5/63 | 0 | 12 | 1.000 |
| Hard | 0.259 | 3/36 | 2 | 6 | 0.665 |

`make judge-diagnosis-csm`:

| Layer | Judge-scored dimensions below gate |
|---|---|
| Clean | `grounding_fidelity=0.176`, `on_task_relevance=0.586`, `account_specificity=0.547`, `tone_fit=0.498` |
| Hard | `account_specificity=0.178`, `tone_fit=0.523` |

The fresh agreed-cell audit key excludes all burned audit cards recorded in
`eval/gold/judge_agreed_audit_history.json`.

## Open Input

The 8 label-error cells require exact owner-provided cell edits before final validation.
No label values are inferred from bucket counts.

## Iteration 3 Direction

Iteration 3 freezes `quality-judge-v3`. The next run is a reference pass, not a judge
prompt revision. The rationale is that D1 and D3 changed the definitions for
`grounding_fidelity` and `account_specificity`, while the clean labels and hard-layer
expected vectors were authored under earlier anchors.

`make judge-reference-review-csm` writes `eval/gold/reference_review_iteration3.json`.
That artifact is non-mutating: it queues the stale-reference cells for owner approval
across `grounding_fidelity`, `account_specificity`, and `tone_fit`, and records
`judge_prompt_frozen=true`.

The current queue contains `151` cells: `grounding_fidelity=45`,
`account_specificity=49`, and `tone_fit=57`.

Hard-layer designer intent was also aligned with the ratified priority rule:
score-only or one-factor priority explanations are `priority_fidelity=2`, not `3`.

## Iteration 3 Re-Check Gate

The 151 approved cells were not applied until a tool-blinded re-check passed. `make
judge-reference-recheck-csm` writes:

- `eval/gold/reference_recheck_iteration3.json`: the 40-card labeler-facing deck.
- `eval/gold/reference_recheck_iteration3_key.json`: the held-out prior-score and bucket
  key.

The deck is stratified across the three re-scored dimensions and the three owner buckets,
but exposes only the dimension to score plus request/output context. It does not expose
the prior final score, bucket, judge score, or judge rationale.

Gate: no more than `2` disagreements out of `40`. The re-check passed at `0/40`, so the
151 approved reference cells were applied mechanically.

The `Hi <first name>` opener is owner-ratified as acceptable professional-direct register.
Do not downgrade a draft for that greeting alone.

## Claim Boundary After Re-Reference

The iteration-3 claim is: the judge agrees with the human application of the ratified
rubric. It is not yet a claim that the judge agrees with a pre-existing independent
standard.

That distinction matters because the reference pass moved many stale cells toward the
ratified definitions. The defense is procedural, not rhetorical:

- D1 and D3 were ratified before the re-reference pass, based on explicit rubric
  boundaries: truthfulness is separate from thoroughness, and specificity requires an
  operational account detail.
- The same pass preserved an honest judge-error ledger by ruling against the judge on
  `34` cells and against both old reference and judge on `10` cells.
- The re-check deck strips prior final scores, buckets, judge scores, and judge rationales
  before the owner re-scores the sample.

The remaining independence limit is the single-labeler limit. A blind second-labeler pass is
the future check for the human-agreement ceiling.

## Iteration 3 Results

The reference pass applied `151` approved cells: `117` changed and `34` stayed as-is.
Bucket split: `reference_stale=107`, `judge_error=34`, `definition_ambiguity=10`.

Formal frozen-v3 agreement (`make judge-agreement-csm`) produced this point-estimate table
with percentile-bootstrap 95% intervals:

| Layer | Dimension | Kappa | 95% CI | Status |
|---|---|---:|---|---|
| Clean | `grounding_fidelity` | 0.713 | [0.588, 0.819] | clears point gate; lower CI below gate |
| Clean | `on_task_relevance` | 0.617 | [0.456, 0.745] | clears point gate; lower CI below gate |
| Clean | `account_specificity` | 0.420 | [0.184, 0.630] | open |
| Clean | `tone_fit` | 0.818 | [0.696, 0.911] | clears |
| Clean | `safety_boundary` | 1.000 | [1.000, 1.000] | clears |
| Clean | `priority_fidelity` | 1.000 | [1.000, 1.000] | deterministic |
| Hard | `grounding_fidelity` | 0.651 | [0.194, 0.900] | clears point gate; wide interval |
| Hard | `on_task_relevance` | 0.421 | [0.258, 0.565] | open |
| Hard | `account_specificity` | 0.369 | [0.094, 0.601] | open |
| Hard | `tone_fit` | 0.696 | [0.485, 0.834] | clears point gate; lower CI below gate |
| Hard | `safety_boundary` | 1.000 | [1.000, 1.000] | clears |
| Hard | `priority_fidelity` | 1.000 | [1.000, 1.000] | deterministic |

The follow-up diagnosis run, which is another stochastic judge pass, showed the remaining
misses differently: clean `on_task_relevance=0.594` and hard `account_specificity=0.542`
were the only judge-scored dimensions below the point gate. This variance means the next
step is not a broad prompt rewrite; it is a residual review of specificity and on-task
boundary cases, with the global judge still `not validated`.
