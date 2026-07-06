# Program Report 63 — MASTER_LIVE_BUILD Phase 13

Phase 13 converts the validated judge claim into a scoped drift-power claim.
The result is honest and bounded: the current expanded gold ladder detects large
overall quality drops, not subtle production drift.

## DoD Evidence

| Gate | Evidence | Result |
| --- | --- | --- |
| Drift-power artifact exists | `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 make drift-power-csm` | `hard_ok=True`, `mdd=0.469`, sensitivity `True`, specificity `True` |
| Named degradation rungs caught | `eval/drift_power_csm.json` | all eight bad variants caught; each had drop `1.0`, p-value `0.000091`, achieved power `1.0` |
| No-op negative control quiet | `eval/drift_power_csm.json` | `noop_equivalent` drop `0.0`, p-value `1.0`, detected `False` |
| Claim scoped to sample size | `eval/drift_power_csm.json` | current n=7 independent examples per arm supports about a `0.469` or larger overall-pass-rate drop; 10pp needs about 56 per arm, 20pp needs 25, 50pp needs 7 |
| Docs scoped | `README.md`, `docs/QUALITY_REGRESSION_EVAL_SPEC.md`, `docs/CUSTOMER_VALUE_MODEL.md`, `docs/CAPABILITY_MAP.md`, `docs/DECISION_LOG.md` | no broad "detects quality drift" claim without the n/effect-size boundary |
| Offline focused gates | pytest + ruff | `3 passed`; ruff `All checks passed!` |
| Full eval | `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 make eval` | `806 passed, 1 skipped, 1 warning in 132.45s` |

## IF/THEN Branches

1. IF the expanded gold set's all-cases baseline had only 7/63 overall pass,
   THEN use the `control_good` variant as the baseline arm and every labeled bad
   variant as the degradation ladder. This preserves the intended gold-set
   structure instead of pretending the mixed adversarial set is a production
   baseline.
2. IF every named bad variant is a 100pp overall-pass-rate drop, THEN the
   artifact states that this proves large-drop detection only. It does not imply
   subtle drift detection.
3. IF a doc says or implies broad quality-drift detection, THEN scope it to the
   current artifact's n/effect-size boundary.

## Owner Asks

None for Phase 13. Phase 14 remains blocked/skipped by OA-3: no second labeler
is currently lined up.

## STOP Conditions

None. No labels, gold keys, judge prompts, thresholds, or gates were edited.

## Skeptical Reviewer

This is a power analysis over the committed synthetic gold set and overall
pass/fail. It does not prove production retention outcomes, per-dimension power,
or fine-grained semantic drift. The artifact says the next honest step for
smaller-drop claims is more independent examples per arm.

## Receipts

- Artifact: `eval/drift_power_csm.json`.
- Script: `eval/drift_power_csm.py`.
- Tests: `tests/test_drift_power_csm.py`.
- Decision: `docs/DECISION_LOG.md`.
- Command: `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 make drift-power-csm`.
