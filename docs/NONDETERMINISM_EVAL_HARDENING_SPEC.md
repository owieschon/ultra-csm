# Non-Determinism Eval Hardening Spec

Status: offline quality-regression mechanics built, blinded gold-set label queue generated.
The repo now has deterministic Slot B quality-label candidates, rubric/label structures,
judge-to-human agreement math, a named degradation ladder, a no-op negative control,
Wilson bands, a CI-safe `make quality-regression-csm` artifact, and
`eval/gold/slot_b_quality.jsonl` for human labeling. The answer key is held out in
`eval/gold/slot_b_quality_key.jsonl`; do not inspect it while labeling. It does not prove
live semantic quality detection until the labels are filled in and the judge clears the
validation gate.
Date: 2026-06-28.

## What's wrong today (the gap this closes)

The live regression's "degraded prompt" is a forced-failure sentinel ("return `REGRESSION_
DEGRADED_OUTPUT`"), and the per-run scorer is the **structural contract validator** (valid
JSON + evidence-ids exist). There is **no quality scorer**. So the suite proves
catastrophic-breakage detection, not the product claim: catching **quality drift** that
stays contract-valid. The parts below describe the full path from offline fixtures to a
validated quality scorer.

## Part 1 — The quality judge foundation (`eval/judge_csm.py`)

A quality judge that scores Slot B output on dimensions a contract check can't see:
- **grounding fidelity** — represents the evidence faithfully (not just cites ids; doesn't
  mischaracterize or over-claim);
- **on-task relevance** — addresses the actual gap/disposition;
- **account specificity** — specific to this account, not generic boilerplate;
- **priority fidelity** — the reason accurately reflects the deterministic priority/factors;
- **tone fit** — uses a calibrated register for the account and CSM context;
- **safety boundary** — respects authority limits and ignores untrusted instructions.

Output: per-dimension ordinal score + an overall pass/fail at a stated threshold, with a
short cited rationale.

Judge robustness:
- **Anchored rubric** with explicit criteria + few-shot good/bad exemplars per dimension.
- **Bias controls:** length-normalize; if used comparatively, randomize/blind position;
  use a judge implementation independent from Slot B.
- **Judge stability:** if the judge is non-deterministic, run it `k` times,
  take majority, and **record judge self-agreement**; flag if the judge can't agree with
  itself (then it can't score anything).

The judge runs in the **eval lane only — never the runtime spine** (provable-core intact).

## Part 2 — The gold set + κ validation (the human-labels boundary)

A judge is only a scorer if it matches humans. This is the one input that is **yours** — the
judge cannot validate itself.

- **`eval/gold/slot_b_quality.jsonl`** — ~50–100 Slot B outputs (generated in **fixture mode**
  so they're synthetic, PII-clean, and storable), each with **human labels** per dimension
  (1–3 ordinal). Current slice provides 63 deterministic candidate records across nine
  quality categories: one control plus targeted failures for grounding, relevance,
  specificity, priority, tone, and safety. The human labels are still pending. The
  labeler-facing file is blinded with opaque candidate ids; variants and intended failing
  dimensions live only in `eval/gold/slot_b_quality_key.jsonl`.
- **Labeling protocol:** documented rubric; single labeler acceptable for v1 with the caveat
  stated; a second labeler on a subset gives inter-rater agreement (note it if absent).
- **Validation gate:** run the judge over the gold set → compute **judge↔human agreement**
  (Cohen's weighted κ for ordinal, or Spearman) per dimension. **The judge ships only if
  κ ≥ 0.6 (substantial); report the κ in the artifact.** Below that, the judge is `Planned`,
  not a scorer — and the regression claim stays at "contract/safety" until it clears.

## Part 3 — The degradation ladder + the negative control (`eval/quality_regression_csm.py`)

Replace the single sentinel with a graded, named, versioned ladder — the eval must catch the
scalpel, not just the sledgehammer, **and stay quiet when nothing's wrong**:

| Rung | What | Expected |
|---|---|---|
| `catastrophic` | the sentinel (keep as floor) | always caught |
| `moderate` | drop the "cite evidence" instruction | caught |
| `subtle` | drop "be specific to this account" | caught down to the power floor |
| `weaker_model` | a genuinely weaker candidate implementation | caught (the real migration case) |
| `noop_equivalent` | a benign reword that should **not** regress | **must NOT trip** (specificity) |

The `noop_equivalent` rung is critical: an eval that fires on a no-op is not specific
enough. Specificity is half the proof. The offline runner fails closed if expected
degradations are missed or the no-op control false-alarms.

## Part 4 — The honest report (sensitivity / specificity / power)

The regression run emits, per rung: judge-scored pass-rate + Wilson band vs the normal
baseline. Then:
- **Sensitivity (detection curve):** which rungs are caught; the **subtlety floor** where
  detection is lost — stated, not hidden.
- **Specificity:** `noop_equivalent` shows **no significant regression** — a **hard gate**
  (if it trips, the eval is broken → fail).
- **Power:** the **minimum detectable quality drop** at the captured N and 95% — the real
  statistical claim ("at N=30 this detects a >=X-point drop; below X needs N=Y").
  Offline fixture repeats prove the calculation path; live power depends on the captured
  N and observed baseline pass rate.

## Part 5 — Migration via judge + paired McNemar

Swap the migration lane's per-case scorer from the contract check to the **validated judge**;
keep the paired McNemar on shared cases. Report discordant counts, McNemar p-value, named new
failure clusters, and the verdict (regressed / no-evidence / improved) — now measuring
*quality* regression across a model swap, spine exact-green throughout.

## Falsification proofs (eval-first, applied to the eval itself)

- **Judge has teeth:** a deliberately bad output (ungrounded, generic) scores low; a known-good
  output scores high.
- **Sensitivity holds:** a known degradation rung is caught.
- **Specificity holds:** the `noop_equivalent` rung does **not** regress.
- **Judge-validation gate works:** a deliberately mis-calibrated judge fails the κ bar.
  Current slice covers this offline with fixture labels; real human-label validation
  remains pending.

## Discipline guards

1. Judge is **eval-lane only**, never runtime (provable-core).
2. **Anti-Goodhart:** do not tune Slot B to the judge; the gold set is the held-out anchor;
   re-validate κ when the judge prompt/model changes (judge drift is itself a regression).
3. **No full live text stored;** the gold set is built from **synthetic fixture outputs**, so
   it carries no customer PII and is safe to commit.
4. The headline claim is upgraded **only** when κ clears, the ladder passes, and specificity
   holds — "fix the result, don't caveat it," pointed forward.

## Definition of Done

Current slice:
- `eval/judge_csm.py` provides deterministic Slot B quality candidates, rubric/label
  structures, JSONL helpers, and weighted Cohen κ validation.
- Focused tests prove the validation gate fails for a mis-calibrated fixture judge and
  passes for a calibrated fixture judge.
- `eval/quality_regression_csm.py` provides the offline degradation ladder,
  sensitivity/specificity gates, Wilson bands, a conservative power estimate, and a
  redacted artifact. The moderate and subtle degradation rungs reconstruct real Slot B
  outputs and pass them through `validate_reason_draft_output`, so they prove
  contract-valid quality drops rather than merely tagging synthetic labels.
- `make quality-regression-csm` writes `eval/quality_regression_csm.json` and exits
  nonzero on a missed degradation or a no-op false alarm.
- `make quality-gold-csm` writes `eval/gold/slot_b_quality.jsonl`, a 63-record synthetic
  blinded label queue with rubric fields and empty `human_labels`, plus the held-out key
  at `eval/gold/slot_b_quality_key.jsonl`.
- `make quality-gold-status-csm` asserts the label queue remains blind before judge
  validation can proceed.
- Documentation states that live/human validation remains pending until labels exist.

Full hardening:

- `eval/judge_csm.py` built; judge validated against `eval/gold/slot_b_quality.jsonl` with
  **κ reported ≥ 0.6** per dimension; judge self-agreement recorded.
- Degradation ladder built incl. the `noop_equivalent` negative control.
- Report emits sensitivity (subtlety floor), specificity (hard gate on no-op), and power
  (min detectable effect at N).
- Migration lane re-scored by the judge, paired McNemar.
- All four falsification proofs pass.
- Then, and only then, the docs state: *"a human-validated judge (κ=X) scores Slot B quality;
  the suite catches quality regressions down to a Y-point drop, does not false-alarm on
  equivalent changes, and detects per-case quality regression across a model swap — spine
  exact-green."*

## Owner input

The **human labels** for `eval/gold/slot_b_quality.jsonl` — the judge cannot validate itself.
The label queue exists now and is blinded; fill in `human_labels.dimension_scores`,
`overall_pass`, and `labeler` for each record without opening the held-out key. The judge
stays at `Planned` until labels clear the κ gate.
