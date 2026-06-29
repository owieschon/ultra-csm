# Decision Log

Append-only record of non-obvious engineering decisions and the evidence behind them.

---

## Quality judge: model and prompt selection for the Slot B gate

**Context.** The Slot B quality judge scores six dimensions (1/2/3) and a draft passes
iff every dimension >= 2, so the pass/fail gate rides the 1-vs-2 boundary of each
dimension. We needed a judge trustworthy enough to power a semantic-quality
non-determinism regression — which is only meaningful if the judge's own run-to-run
noise floor is below the drift it claims to detect.

**What we measured.** Against the 36-case adversarial hard gold layer (designer key with
per-case traps + `intended_failing_dimensions`):

- **The judge is non-deterministic run-to-run, even with no temperature.** A 20x
  determinism probe on Opus 4.8 over six boundary archetypes: corpus vector-repeatability
  0.167; two cases flip the gate (`H_control` p=0.15, `H4a_boundary_two` p=0.65). Single-run
  A/B comparisons of prompt edits are therefore confounded by instrument noise — proven, not
  asserted. (`eval/gold/determinism_probe.json`.)
- **Reasoning-before-score (G-Eval / CoT) helps Opus.** Under 3-run aggregation (fail-closed
  safety + modal vote), Opus terse -> Opus CoT moved gate false-negatives 2 -> 0 and tripled
  exact-vector agreement (3 -> 9), without inflating false positives. (`eval/gold/judge_compare.json`.)
- **The cheaper model is the better gate judge.** Sonnet 4.6 terse@N gave false_neg=0,
  false_pos=3 (all three are `H3a`, a debatable-key case, not judge error), gate-repeatability
  1.0, zero indeterminate. A 20x Sonnet probe confirms **zero gate flips** across all six
  boundary archetypes (vector-repeatability 0.5) — it stably gets `H_control` and `H4a` right
  where Opus flipped them. (`eval/gold/judge_compare_sonnet.json`, `eval/gold/determinism_probe_sonnet.json`.)
- **CoT is not a universal good — its value is model-dependent.** CoT rescued noisy Opus but
  *degraded* already-stable Sonnet (added a false positive, added 3 indeterminate cases,
  dropped repeatability 1.0 -> 0.917). Reasoning gave Sonnet room to overthink the clean control.

**Decisions.**
1. **Gate judge = Sonnet 4.6, terse, N-run aggregated** (fail-closed safety, modal vote per
   other dimension, indeterminate cases surfaced not hidden). It is the most accurate, most
   stable, and cheapest option for the binary gate.
2. **Do not adopt CoT for the gate.** It only helps when the base model is noisy; on the
   chosen model it hurts. Keep Opus-CoT in reserve only if a future need for higher
   *magnitude* (per-dimension) fidelity is established by the drift-power experiment — not before.
3. **Keep the 1/2/3 ordinal as the magnitude signal; compute the gate as a derived binary
   predicate in code.** Forcing a binary model output converts middling cases into coin flips
   that worsen boundary variance.
4. **Three `H3a` "false positives" are pending human adjudication, not judge fixes.** The
   judge consistently fails a peppy-hype draft to an at-risk account; the key says pass. The
   key is the suspect. Resolved by a blind human, never by the judge.
5. **Primary metric is the per-dimension 1-vs-2 confusion (false-pass / false-fail) with
   Wilson CIs, NOT weighted Cohen's kappa.** This is a deliberate supersession, not a moved
   goalpost: the original protocol set a kappa >= 0.6/dim bar, but kappa is the wrong
   instrument for a *binary gate* at n=36 — it is prevalence-distorted (safety is ~always-pass
   so kappa is trivially high; specificity is paradox-deflated to ~0.2) and its CI (~+-0.25)
   is wider than the 0.6 line it would test. The current kappa artifact (`judge_agreement.json`)
   genuinely sits at ~0.19-0.25 and is reported as a CI'd *secondary*, never hidden. The gate
   the product actually consumes is the confusion-count, which is what we optimize and report.

**Still open (not claimed yet).** Human-validated reference + a second-labeler agreement
ceiling; the drift-power experiment showing the judge's residual noise floor is below the
generation drift it must detect. Until those, we claim a *characterized and stabilized*
judge, not a *validated* one.

**Known limitations.**
- The `H6a_wrong_register` hard case currently shares example phrasing with the judge
  rubric's `tone_fit` guidance, so that one family measures recognition more than
  generalization. A generalization variant (rubric describes the category abstractly;
  gold supplies disjoint instances) is pending; it requires a fresh live re-measurement.
- The agreement numbers above are a single session's snapshot (Opus N=3/N=20, Sonnet
  N=3/N=20). They are reproducible via `make judge-agreement-csm` but are not pinned in
  the repo, since the live judge is credential-gated and not CI-reproducible.
