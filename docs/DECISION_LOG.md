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

---

## Quality judge: validated under N-run aggregation (supersedes the entry above)

**Context.** The entry above characterized the judge as *stabilized, not validated*, and
picked Sonnet-terse as the gate on single-run evidence. Two things changed: (1)
`account_specificity` and `priority_fidelity` moved from LLM-judged to deterministic
scorers (code matches gold 99/99 offline, κ=1.0 by construction — prompt v6→v7), which
removed the single largest source of hard-layer noise; (2) single-run hard-layer κ on the
36-item adversarial set turned out to swing ±0.15 run-to-run (grounding and on_task each
dipped below 0.6 in roughly 1 of 5 runs while their medians sat well above it) — a
single-run hard gate is a coin flip by construction on a sample this size where these
dimensions rarely fail. That reframes the prior "terse@N is the best gate" decision as
premature: it was chosen on single-run numbers that this measurement now shows are not
individually trustworthy.

**What we measured.** 5-run modal aggregation (`eval/judge_nrun.py`) on both arms,
head-to-head (`eval/compare_judges.py --runs 5`), hard layer n=36:

- **terse@5**: on_task_relevance aggregated κ 0.479 (FAIL), 3 aggregated false negatives.
  Disqualified — it passes bad outputs even after aggregation.
- **cot@5**: all six dimensions aggregated κ ≥ 0.6 (min 0.661 on_task, 0.682 grounding),
  aggregated false negatives = 0, gate repeatability 0.917, 3 indeterminate cases kept in
  the denominator (never hidden). Clean layer (n=63, single-run — clean cases rarely flip):
  all six ≥ 0.832, false_neg = false_pos = 0.

**Decisions.**
1. **The gate flips: cot@N is now the validated hard-layer instrument, not terse@N.**
   The prior decision optimized for single-run accuracy/stability; under aggregation that
   axis stops mattering (aggregation is what buys stability) and cot's lower false-negative
   rate dominates. This does not contradict the "CoT hurts Sonnet" finding above — it was
   true for *single-run* comparisons; aggregation changes which arm wins.
2. **`judge_validated` is derived from evidence artifacts, never hand-set**
   (`eval/judge_validation.py`, recomputes hard κ/false-negatives from the aggregated
   per-case vectors rather than trusting a stored summary). Flipped to `true` on 2026-07-02
   (commit `824f94e`). Claim boundary records the method verbatim: N-run-aggregated
   (5 runs, cot arm), single-labeler gold, prompt v7, claude-sonnet-4-6.
3. **Never re-litigate this gate with a single run.** The ±0.15 single-run swing on a
   36-item rarely-failing hard layer is now measured, not hypothesized — a future prompt
   or model change must be evaluated under the same N-run aggregation, not a one-off call.

**H6b boundary-reach ruling (2026-07-02).** Open question was whether "internal_review,
passive, no concrete ask" (on_task=1) extends to warm-but-generic drafts like "hope
you're doing great, just checking in" — the judge fails these under v7; three H6b hard-key
cases were authored expecting a pass. **Ruling: this is genuinely subjective and
contextual, not a bright-line rule to encode.** No deterministic floor, no rubric
rewrite, and no gold-key change to force agreement. The resulting 4 aggregated hard false
positives (judge stricter than gold, fail-closed direction) are accepted as an honest,
recorded disagreement — not a defect to chase to zero. If a future prompt revision
resolves it, revalidate under the same N-run methodology (decision 3 above); do not
special-case it in the judge prompt.

**Rejection ledger added for feedback persistence (Universe v2 Wave 1, WS-Week1-Harness,
2026-07-04).** `eval/week1_protocol.py`'s feedback-persistence check found that
`ActionGate.record_verdict`'s `deny` status is terminal but nothing consults it before the
next sweep — a denied recurring-eligible proposal reappears unchanged the next day.
Mechanism: `src/ultra_csm/rejection_ledger.py` adds a flat, file-backed
`RejectionLedger` keyed by `(tenant_id, account_id, factor_name, motion)` that a caller
consults after a `deny` verdict and before treating a new sweep's matching work item as a
genuinely new ask, rather than encoding any suppression rule into the sweep itself.

---

## Notion authoring edge: render target, loader-as-oracle, two-tier isolation (Stream 34)

**Context.** A CSM needs a friendlier authoring surface than hand-edited JSON for the
org-agnostic (`org_pack.json`, `golden_corpus/*`, tenant `playbooks.json`) and
account-specific (`content_catalog.json`, `handoff_notes/*.json`) knowledge the agent
already consumes. Adding Notion could have meant a live read path in the runtime, or a
repo-side build step; it could have proven acceptance by editing the loaders to accept a
new shape, or by pointing the unmodified loaders at new output.

**Decisions.**
1. **Render target is `knowledge/_generated/`, never the curated demo artifacts.**
   `scripts/notion_render.py` writes there; `load_org_pack`/`load_playbooks` are pointed at
   the generated path to prove acceptance. The curated `knowledge/org_pack.json` and
   `knowledge/tenants/fleetops/*` stay owned by the fictional-universe bibles, untouched.
   Making the curated artifacts the render target was explicitly rejected — it would
   couple an authoring-tooling change to the demo universe's content, and risk a bad
   render silently corrupting the fixtures every other eval depends on.
2. **Loader-as-oracle: the unmodified existing loader/schema test is the acceptance
   check, never a loader edited to fit the renderer.** Agnostic tier: `load_org_pack` /
   `load_playbooks`, called against `knowledge/_generated/`. Account-specific tier: the
   schema assertions imported (not replicated, not edited) from
   `tests/test_content_catalog.py` / `tests/test_handoff_notes.py`, applied to generated
   output via `tests/test_notion_render.py`. If the render doesn't pass unmodified
   acceptance code, the render is wrong — never the reverse.
3. **Two-tier isolation is enforced by the loader's `_reject_forbidden_keys`, not by
   renderer-side stripping.** The renderer must carry an account-specific fact placed
   into an agnostic field straight through into the emitted JSON and let `load_org_pack`
   raise `OrgPackError`. Silent stripping was rejected: it would hide the author's mistake
   instead of surfacing it, and would require the renderer to maintain its own copy of
   the forbidden-key list, a second source of truth `knowledge.py` doesn't need.
4. **One-directional, build-time only.** Notion → captured payload → rendered JSON →
   committed via PR. No runtime code path reads Notion; `src/ultra_csm/tick.py` and
   `src/ultra_csm/agent1/sweep.py` are verified (negative grep) to never import
   `notion_reader`. A live-read-at-runtime design was rejected as unnecessary scope: the
   agent already has a validated JSON contract; Notion only needed a friendlier way to
   produce files matching it.
5. **Notion API response shapes are grounded in the documented API, not invented.**
   `tests/fixtures/notion/authoring_payload.json` mirrors Notion's documented
   data-source-query (`object: "list"`, `results`, `has_more`, `next_cursor`) and
   block-children response shapes, with doc URLs cited in the fixture's `_doc_refs` and
   in `notion_reader.py`'s module docstring (accessed 2026-07-05). The credential
   env-var name (`ULTRA_CSM_NOTION_TOKEN`, internal-integration Bearer-token pattern) is
   flagged verify-at-runtime — the offline parse/render path does not depend on it.

**What this does NOT prove.** Schema-valid, loader-accepted output is not the same as
semantically faithful output: a rendered exemplar can pass every gate while drifting from
what the CSM actually meant in the source Notion block, and a mislabeled `addresses_gap`
still passes the account-specific schema check. Live Notion auth is untested — no
`NOTION_*` credential exists in `~/ultra-csm-live-creds.env` as of 2026-07-05, so the live
pull is an Owner Ask, not a claimed capability.
