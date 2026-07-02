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
