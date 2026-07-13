# Program Report 70 - Judge Scope Enforcement

Harvest 34 delivered additive judge-scope enforcement. The full judge validation
claim remains false, but the status now exposes which quality dimensions are
validated for narrower scoped gates. `on_task_relevance` remains structurally
excluded because the committed evidence still contains the three hard-layer
aggregate false opens.

## What Changed

| Area | Change |
| --- | --- |
| Judge validation status | `judge_validation_status()` now returns `per_dimension_validated`, `validated_gating_dimensions`, and `excluded_gating_dimensions` alongside the existing `validated` claim. |
| Scoped gate guard | `assert_gating_dimensions(...)` accepts only dimensions present in `validated_gating_dimensions` and raises `UnvalidatedGatingDimension` for excluded, unknown, or empty requests. |
| Failure attribution | Existing clean/hard gate failures are mapped back to dimensions, with structural evidence failures assigned to every dimension so scoped gates fail closed. |
| Full-validation consumers | Existing consumers of `judge_validation_status()["validated"]` remain on the full validation contract. No gold, score, kappa, prompt, model, send, UI, or live-quality behavior was migrated or loosened. |

## Current Derived Scope

| Dimension | Scoped Gate Status | Evidence |
| --- | --- | --- |
| `grounding_fidelity` | validated | Clean and hard kappas remain above the gate, with no hard aggregate false-open attribution. |
| `account_specificity` | validated | Clean and hard kappas remain above the gate, with no hard aggregate false-open attribution. |
| `priority_fidelity` | validated | Clean and hard kappas remain above the gate, with no hard aggregate false-open attribution. |
| `tone_fit` | validated | Clean and hard kappas remain above the gate, with no hard aggregate false-open attribution. |
| `safety_boundary` | validated | Clean and hard kappas remain above the gate, with no hard aggregate false-open attribution. |
| `on_task_relevance` | excluded | Three hard aggregate false opens remain in family `H6b_warm_but_generic`. |

## Proof Cases

| Case | Expected | Observed |
| --- | --- | --- |
| Committed evidence status | Full `validated` remains `False`; five non-`on_task_relevance` dimensions are listed as scoped-gateable. | `test_committed_evidence_exposes_only_validated_scoped_dimensions` passes. |
| Valid scoped request | Requesting the five cleared dimensions succeeds and returns the sorted declared set. | `test_scoped_gate_accepts_only_the_five_validated_dimensions` passes. |
| `on_task_relevance` only | Requesting `on_task_relevance` raises `UnvalidatedGatingDimension`. | `test_scoped_gate_rejects_on_task_relevance_alone` passes. |
| Mixed valid plus `on_task_relevance` | A mixed request still raises; valid dimensions cannot smuggle an excluded dimension through the guard. | `test_scoped_gate_rejects_on_task_relevance_even_when_mixed_with_valid_dims` passes. |
| Derived scope, not literal list | Corrupting `tone_fit` hard evidence removes `tone_fit` from `validated_gating_dimensions`. | `test_validated_gating_dimensions_are_derived_from_current_evidence` passes. |
| Live semantic quality | Live quality remains unproven while the full judge validation claim is false. | Existing live semantic quality tests still pass. |

## Gate Receipts

| Gate | Receipt |
| --- | --- |
| Baseline before coding | `make eval` passed: 825 passed, 1 skipped, 1 warning in 212.99s; Slot B gold checks current. |
| Focused scoped tests | `.venv/bin/python -m pytest tests/test_judge_validation.py -q` -> 21 passed. |
| Adjacent validation consumers | `.venv/bin/python -m pytest tests/test_judge_validation.py tests/test_gold_slot_b_hard.py tests/test_judge_model_migration.py tests/test_drift_power_csm.py -q` -> 37 passed. |
| Lint | `make lint` passed: Ruff reported `All checks passed!`. |
| Hygiene | `make hygiene` passed via `scripts/hygiene_scan.py`. |
| Final eval | `make eval` passed: 830 passed, 1 skipped, 1 warning in 211.54s; Slot B quality and hard status artifacts current. |

## Known Boundaries

- `validated` is still false and still means full judge validation.
- `on_task_relevance` is not usable for scoped gating until future evidence clears
  the hard aggregate false-open failure.
- The scoped guard is additive. Existing score, gold, kappa, prompt, model,
  send, UI, and live semantic quality semantics are unchanged.
