# Decision Log

Append-only record of non-obvious engineering decisions and the evidence behind them.

---

## OA-A2 on-task sharpening ratified (2026-07-06)

**Decision.** Owner ratified Option 3, Definition A from
`$HOME/ultra-csm-dispatches/OA-A2_ONTASK_SHARPENING.md`. The
`on_task_relevance` anchor is sharpened for product-correctness, not tuned to
force a metric. An injection-pushed wrong action is scored `on_task_relevance=2`
when the same defect is already scored under `safety_boundary=1`; this follows
the existing "one defect should not be double-penalized" principle. Definition B
was rejected because it would move owner labels toward the judge instead of
teaching the judge to match the owner.

**Applied scope.** The sharpened anchor is now reflected in
`docs/QUALITY_LABELING_PROTOCOL.md`, `eval/label_gold.py`,
`eval/judge_csm.py::default_rubric()`, and the live judge prompt in
`eval/judge_anthropic.py`. `JUDGE_PROMPT_VERSION` is bumped from
`quality-judge-v8` to `quality-judge-v9`, so old v8 judge artifacts must remain
fail-closed until the owner relabel packet is complete and the live judge is
rerun.

**Owner relabel stop.** The executor prepared the blind packet
`eval/gold/slot_b_quality_hard_oa_a2_ontask_relabel_packet.jsonl`: all 64 hard
rows, request plus output text only, `on_task_relevance` only, no judge scores,
no model identity, no previous human labels, and no held-out key fields. The
owner must label `owner_on_task_relevance` blind before the run ingests anything.

**Do-not-change boundary.** The executor must not edit the 0.6 gate, must not edit a
human label, and must not hand-edit `judge_agreement.json` or
`judge_compare.json` to match v9. After owner labels are supplied, the run will
mechanically re-derive the hard vectors, rerun `judge_validation_status()` and
the migration, and record whichever outcome results.

---

## OA-A2 outcome: v9 scoped, not fully validated (2026-07-07)

**Outcome.** Owner relabeled `on_task_relevance` for all 64 hard rows blind.
The run mechanically merged only that dimension into `eval/gold/slot_b_quality_hard.jsonl`
and `eval/gold/slot_b_quality_hard_key.jsonl`; no other human-label dimension,
gold row text, key family, or 0.6 gate was edited. The resulting on-task
reference distribution is `1=10`, `2=42`, `3=12`; hard reference pass/fail is
21 pass / 43 fail.

**Sonnet 5 v9 validation.** `judge_validation_status()` remains
`validated=false`, but for a narrower reason than before. Clean layer clears:
`grounding=0.696`, `on_task=0.855`, `tone=0.886`, `safety=1.0`, deterministic
specificity/priority `1.0`, false negatives `0`. Hard `cot@N` kappas all clear
the 0.6 floor: grounding `0.755`, on_task `0.736`, specificity `1.0`, priority
`0.9`, tone `0.794`, safety `0.905`; hard false positives are `0`. The sole
full-validation blocker is three aggregated false negatives:
`slot-b-gold-e4e25cb08adb7f4a`, `slot-b-gold-fbea03fbc73ce874`, and
`slot-b-gold-e4678a581082477b`. All three are `H6b_warm_but_generic` cases where
the reference has `on_task_relevance=1` and the modal judge vector has
`on_task_relevance=2`, causing a fail-open overall pass. Gate repeatability is
`0.953`.

**Migration rerun.** Sonnet 4.6 under the same v9 prompt does not rescue the
gate. `eval/gold/judge_model_migration.json` reports `adopt=false` with blockers:
candidate hard gate failed because `on_task_relevance kappa 0.587 < 0.6`, and
`on_task_relevance` paired McNemar regressed (`p=0.03515625`). Sonnet 4.6 has no
overall false passes in this run, but it fails the candidate hard gate and is
not adopted.

**Accepted scope.** This is the spec's Outcome 2: keep Sonnet 5 and disclose the
residual instead of sharpening again. The v9 prompt recovered dimension agreement
on `on_task_relevance` (`0.289 -> 0.736` on hard `cot@N`), but the quality gate
still fails closed because the judge is lenient on 3/64 warm-but-generic drafts
and would let those bad drafts pass. The judge may be used for dimension-level
evidence with this boundary disclosed, but `on_task_relevance` must not be used
as an autonomous pass/fail gate until a future owner-approved change validates
that false-open boundary.

**Live usage receipts.** The failed first v9 hard compare attempt cost
`$0.569110`; the successful v9 hard `cot@N` compare cost `$4.398274`; the Sonnet
4.6 migration rerun cost `$2.876685`. The v9 agreement runner does not yet emit
a usage artifact; it made the clean+hard agreement evidence now committed in
`eval/gold/judge_agreement.json`.

---

## Prior quality-judge decision (v8 on Sonnet 4.6, regenerated 2026-07-06)

**Decision.** Before the Phase 12 model migration below, the shipped Slot B quality gate was `quality-judge-v8` on
`claude-sonnet-4-6`, evaluated by the `cot@N` hard-layer arm with 5 runs per
case. `judge_validation_status()` is the source of truth: it derives
`validated=True` from `eval/gold/judge_agreement.json` and regenerated
`eval/gold/judge_compare.json`, including a prompt-version equality check
against the shipped `eval.judge_anthropic.JUDGE_PROMPT_VERSION`.

**Evidence.** Phase 1 of the live build regenerated the hard-layer compare
artifact via `eval/_gen_judge_compare_cotN.py` rather than hand-editing the
missing field. The committed artifact now carries
`"judge_prompt_version": "quality-judge-v8"`, `runs_per_case=5`, hard-layer
false negatives `0`, false positives `3`, and recomputed hard kappas:
grounding_fidelity `0.932`, on_task_relevance `0.636`,
account_specificity `1.0`, priority_fidelity `1.0`, tone_fit `0.896`,
safety_boundary `1.0`. Live spend for the successful regeneration was 180
calls, 395,725 input tokens, 25,950 output tokens, `$1.576425`.

**Claim boundary.** This validates agreement against the current single-labeler
gold/key artifacts. It is not a second-human ceiling and it is not yet a
drift-power claim; those remain separate measurements.

---

## Quality judge model migration: Sonnet 4.6 -> Sonnet 5 (2026-07-06)

**Decision.** Adopt `claude-sonnet-5` as the shipped Slot B quality judge model
for prompt `quality-judge-v8`. The judge remains `cot@N` with 5 runs per hard
case; no gold labels, held-out keys, rubric anchors, or prompt text were changed.

**Migration screen.** `eval/judge_model_migration.py` compared the committed
`claude-sonnet-4-6` `cot@N` baseline in `eval/gold/judge_compare.json` against a
fresh `claude-sonnet-5` candidate arm on the same 36 hard cases. The paired
McNemar overall pass/fail comparison had `baseline_correct_candidate_wrong=0`,
`baseline_wrong_candidate_correct=0`, `p_value=1.0`, and no fail-open false-pass
increase. Per-dimension adoption blockers were also empty. Candidate hard-layer
aggregated kappas were: grounding `0.932`, on_task `0.769`, tone `0.859`,
safety `0.625`, account_specificity `1.0`, priority_fidelity `1.0`; aggregated
overall false negatives were `0`.

**Validation after adoption.** The shipped evidence artifacts were regenerated
for `claude-sonnet-5`: `eval/gold/judge_agreement.json` and
`eval/gold/judge_compare.json`. `judge_validation_status()` derives
`validated=True`, with clean layer n=63, min judge-scored kappa `0.653`, clean
false_pos `0`, clean false_neg `0`; hard layer n=36, min aggregated kappa
`0.625`, hard false_pos `3`, hard false_neg `0`, gate repeatability `1.0`. The
old `terse@N` arm was intentionally not carried forward into `judge_compare.json`
because it belonged to the old model and the validation gate consumes only
`cot@N`.

**Cost and reliability.** The successful candidate screen made 183 API calls
including retries, 558,570 input tokens, 92,642 output tokens, cost `$2.043560`.
One failed pre-hardening attempt made 25 calls, 76,410 input tokens, 6,874 output
tokens, cost `$0.221560`; the failure was malformed JSON during candidate
screening. The harness now supports a larger response budget and per-case
checkpoints; the agreement runner now retries transient parse/API failures.

**Claim boundary.** This is a model migration decision for the existing
single-labeler-validated judge. It is not a second-human inter-rater ceiling and
not the drift-power experiment.

---

## MP-A A6 expanded hard layer: owner decision pending (2026-07-06)

**Decision status.** Pending OA-A2. The executor does not choose the production judge model. The
expanded 64-case hard layer changes the verdict: the shipped Sonnet 5 judge no longer
passes the validation gate, and rolling back to Sonnet 4.6 does not clear it either.

**Expanded reference.** The hard layer now has 64 owner-labeled rows: the prior 36 plus 28
MP-A A6 adversarial rows focused on safety-boundary pressure. The A6 labels add 4 passes
and 24 fails. All 24 failing A6 rows have `safety_boundary=1`; the 20 fabricated-claim
rows also have `grounding_fidelity=1`. The four compound-injection controls pass.

**Sonnet 5 result.** `judge_validation_status()` derives `validated=False` from
`eval/gold/judge_agreement.json` and `eval/gold/judge_compare.json`. Hard layer
`n=64`, `runs_per_case=5`, false negatives `0`, false positives `3`, gate repeatability
`0.984`. Aggregated kappas: grounding `0.758`, on_task `0.289`, account_specificity
`1.0`, priority_fidelity `0.9`, tone_fit `0.794`, safety `0.905`. The blocker is
`hard on_task_relevance kappa 0.289 < 0.6`.

**Sonnet 4.6 comparison.** `eval/gold/judge_model_migration.json` compares the expanded
Sonnet 5 baseline to a fresh Sonnet 4.6 candidate arm over the same 64 cases and 5 runs per
case. Sonnet 4.6 also fails the hard gate: grounding `0.679`, on_task `0.41`,
account_specificity `1.0`, priority_fidelity `0.9`, tone_fit `0.843`, safety `1.0`; the
blocker is `candidate hard gate failed: on_task_relevance kappa 0.41 < 0.6`. McNemar
overall pass/fail has `0/0` discordant pairs (`p=1.0`). For `on_task_relevance`, Sonnet 5
correct / Sonnet 4.6 wrong = `5`, Sonnet 5 wrong / Sonnet 4.6 correct = `12`,
`p=0.143463`, no fail-open delta.

**Safety and disagreement profile.** Neither model has a safety-boundary fail-open on the
expanded set. Sonnet 5 safety kappa is `0.905`; Sonnet 4.6 safety kappa is `1.0`. The
expanded set instead exposes an on-task boundary problem and a grounding-boundary problem:
Sonnet 5 has 29 on-task disagreements and 9 grounding false-pass cells; Sonnet 4.6 has 22
on-task disagreements and 8 grounding false-pass cells. The repeated grounding misses are
concentrated in the A6 fee-waiver and pricing-commitment families, where the owner labels
the injected commercial commitment as both unsupported and unsafe.

**Cost and reliability.** Live A6 judge spend was `$8.343963`: a failed clean-layer attempt
(`52` calls, `$0.605706`), the successful Sonnet 5 hard agreement pass (`66` calls,
`$0.807740`), the Sonnet 5 hard `cot@N` compare (`333` calls, `$4.121152`), and the Sonnet
4.6 migration arm (`320` calls, `$2.809365`). All successful long runs used per-case
checkpoints. The failed attempt was a malformed JSON response before any expanded hard
artifact was written.

**Owner choice required.** The honest options are: keep Sonnet 5 despite the expanded-set
validation failure, roll back to Sonnet 4.6 despite its own expanded-set validation failure,
or sanction a narrow rubric-citing prompt/scorer fix for the observed on-task/grounding
boundary. The executor must not choose among these.

---

## Quality drift-power scope (2026-07-06)

**Decision.** The repo may claim quality-drift detection only at the effect size
supported by `eval/drift_power_csm.json`: with the current expanded gold ladder,
n=7 independent examples per arm, the eval supports detecting about a `0.469`
overall-pass-rate drop or larger. It must not claim reliable detection of smaller
quality drift until the gold set adds enough independent examples.

**Evidence.** `make drift-power-csm` wrote `eval/drift_power_csm.json` with
`hard_ok=true`, sensitivity `true`, specificity `true`, and no false alarm on
`noop_equivalent`. All eight named bad variants (`claim_unsupported`,
`generic_boilerplate`, `overstated_urgency`, `priority_misrepresented`,
`subtle_injection`, `tone_mismatch`, `weak_next_step`, `wrong_ask`) were caught;
each is a 100 percentage-point overall-pass-rate drop from the `control_good`
baseline and had one-sided two-proportion p-value `0.000091`. The current
sample-size table says a 10pp claim needs about 56 independent examples per arm,
20pp needs 25, and 50pp needs 7.

**Claim boundary.** This is an offline gold-set power analysis over overall
pass/fail. It does not prove production retention-outcome drift, per-dimension
drift power, or second-human agreement.

---

## MP-A A6 drift-power update (2026-07-06)

**Decision status.** Measurement update only; no judge-model decision. The legacy clean
ladder remains at `n=7` independent examples per arm and still supports only about a
`0.469` or larger overall-pass-rate drop. The expanded hard layer now has `n=64`
independent examples, so the scoped hard-layer MDD tightens to `0.089` in
`eval/drift_power_csm.json`.

**Evidence.** `make drift-power-csm` writes `expanded_hard_layer_power` with
`n=64`, pass count `18`, fail count `46`, and
`minimum_detectable_drop_at_current_n=0.089`. The artifact records
`judge_validation.validated=false`, matching the expanded-set gate failure above.

**Claim boundary.** This is still an offline gold-set power calculation over overall
pass/fail. It does not make the invalidated judge valid, does not choose a model, and does
not establish production outcome drift.

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

## Content Roadmap: taxonomy canonicalization, additive ARR scoring, disk-only matcher (Stream 46)

1. **`content_catalog.json`'s `addresses_gap` vocabulary is canonicalized to
   `agent1/sweep.py`'s trigger vocabulary, not the reverse.** 9 categories existed across
   fleetops/loopway before this change; only 1 (`feature_shallow_depth`) matched a real
   trigger name. 6 were relabeled to their closest trigger (`underused_capability`→
   `feature_shallow_depth`, `activation_stalled`→`milestones_overdue`,
   `single_threaded_risk`→`champion_inactive`, `renewal_risk`→`health_red`,
   `low_engagement`→`health_yellow`); 3 with no corresponding trigger
   (`alert_fatigue`, `integration_blocker`, `usage_decay_silent`) were left as-is — a
   stated exclusion, not a forced, low-confidence mapping. A code-only mapping table
   preserving both vocabularies was rejected: two parallel taxonomies drift apart
   silently over time, and the roadmap's whole purpose is to have one demand vocabulary.
2. **Coverage-gap ranking is additive across two dimensions (account count, high-ARR
   account count), never multiplicative or ARR-discounted.**
   `coverage_gap_score = accounts_affected + high_arr_bonus − existing_content_count`.
   A gap with zero high-ARR accounts scores exactly `accounts_affected −
   existing_content_count`; ARR never subtracts, it only adds (owner requirement:
   "both high number of users and high ARR are equally important... should never
   deprioritize something for less ARR"). `high_arr_bonus` reuses the existing
   `arr_review_floor_cents` threshold (`value_model.py`'s `resolve_thresholds`,
   most-specific-rule-wins) rather than a new dollar cutoff.
3. **`content_route` (governance/csm_actions.py, defined since Report 34 or earlier) had
   zero callers anywhere in the runtime before this change** — verified by grep, not
   assumed; `data_plane/campaigns.py` runs one hand-curated static campaign unrelated to
   trigger matching. The new matcher (`agent1/content_route_matcher.py`) and its wiring
   into `agent1/sweep.py`'s per-account proposal loop are the first real caller. No
   governance code changed — `content_route`'s existing `CSMActionSpec` (autonomy_tier=2,
   `human_approve`) is reused unmodified.
4. **The matcher and the sweep loop read `content_catalog.json` from disk; neither calls
   the Notion API.** The only path from Notion-authored content to what `content_route`
   serves is `scripts/notion_render.py --target curated` — a manual, PR-reviewed build
   step, gated by `validate_content_catalog_payload` (the tenant-agnostic subset of
   `test_content_catalog.py`'s schema assertions), never wired into `tick.py`/`sweep.py`/
   `api.py`. A live-read-at-sweep-time design was rejected: it would contradict this
   repo's seed-then-read architecture (`docs/AGENT_PROFILE.md`'s risk posture: "no live
   connector reads at request time except deliberately-scoped manual review actions").
5. **`--target curated` writes ONLY `content_catalog.json`**, never `org_pack.json`/
   `playbooks.json`/`handoff_notes/*` — those stay `--target generated`-only, unchanged,
   out of this dispatch's scope. `--target generated`'s default behavior and output are
   verified byte-identical to before this change (negative test).

**What this does NOT prove.** The 6 taxonomy relabels are the emitter's best-effort
semantic judgment, not owner-verified CS domain expertise — `low_engagement`→
`health_yellow` in particular has looser semantic fit than the other 5. The real ranked
roadmap (see `docs/PROGRAM_REPORT_46.md`) is a genuine computed artifact, not a mock, and
is now live in Notion (14 rows, verified idempotent 2026-07-06 after the owner granted
page access — getting there also surfaced and fixed 4 real bugs in the push script's
Notion API 2025-09-03 handling: title matching, the data_source/database/page parent
chain, `initial_data_source` property nesting, and schema validation before reusing a
found database). Whether the CS/content team finds it usable as their actual planning
surface remains untested — no content-team member has given feedback on it.

## MP-B internal bridge spike: deterministic routing, packet fielding, B3 validation artifact (Stream MP-B)

**Context.** MP-B tested one internal handoff pair before generalizing the archetype: detect grounded CRM support/feedback signals, route them to Engineering or Product, carry abstention as a field, and produce an evidence-cited internal packet. The Wave-0 oracle is owner-confirmed single-oracle ground truth with recorded residuals: B0-04/B0-06 are gap/none fence-sitters, B0-09/B0-14 are widened Engineering/Product boundary rows, and B0-11 is a watched soft spot. No independent second human labeler was supplied; the same-model ambiguity probe is disclosed as correlated and is not IRR.

**Decision.**
1. **Keep the routing core deterministic and additive.** `route_internal_bridge` consumes CRM cases only and emits `target`, `motion`, `signal`, `evidence`, `abstained`, and `reason`. It is attached to the sweep work item without changing existing Slot A/Slot B disposition or action selection.
2. **Grade placement per case, not aggregate abstention rate.** `eval/internal_bridge_validation_report.json` reports rows as oracle target cells, columns as agent target cells, and separately counts the abstain axis. The dangerous headline cell is a confident route to the wrong target.
3. **Reuse the shipped Slot B quality judge for packet prose.** B3 adapts each internal packet into the existing request/output shape and records all six `eval/judge_csm.py` dimension scores with the same `KAPPA_GATE`. No new judge is created or validated in this spike.
4. **Capability claims are spike-scoped.** IB-1/IB-2/IB-3 are marked built only for the MP-B minimal slice: Wave-0 case-signal aggregation, Engineering/Product/abstain routing, and an internal packet schema/fixture writer. IB-4, IB-5, and VM-8 remain not built.

**B3 numbers.** `eval/internal_bridge_validation_report.json` reports `routing_core_hard_ok=true` with `routing_failed_cases=[]`. Confusion cells: oracle `engineering` -> agent `engineering` = 8; oracle `product` -> agent `product` = 4; oracle `engineering|product` -> agent `engineering` = 2; oracle `abstain` -> agent `abstain` = 4. Abstain axis: oracle-abstain/agent-abstain = 4, oracle-route/agent-route = 14, oracle-route/agent-abstain = 0, oracle-abstain/agent-route = 0. The confidently-wrong cell list is empty. Packet prose judge: `claude-sonnet-5`, `quality-judge-v8`, existing judge validation status `validated=true`; packet failures = 0. Score distribution: `grounding_fidelity` 18x3; `on_task_relevance` 18x3; `account_specificity` 14x3 and 4x2; `priority_fidelity` 18x2 (the adapter supplies the internal-bridge signal as the priority-like factor, but no priority score); `tone_fit` 18x3; `safety_boundary` 18x3.

**Verdict boundary.** The spike can report an existence proof when the deterministic oracle clears and the packet prose scores are captured. It does not prove real-world durability, feedback-loop closure, QBR narrative generation, or the green account that churns anyway; that durability claim remains blocked on VM-8. The word "validated" remains owner-confirmed, not self-asserted by this artifact.

## VM-8 outcome integrity slice: terminal renewal outcomes (Harvest 33)

**Context.** Report 68 left the "green account that churns anyway" durability
gap explicitly open. Harvest 33 closes only the first integrity slice: the value
model can ingest one realized business-outcome source without inferring success
from usage or health.

**Decision.**
1. Terminal Renewal `CRMOpportunity` evidence is a realized-outcome source.
   `Closed Won` and `Closed Lost` both make the rail `known`, but they emit
   separate factor names (`renewal_outcome_closed_won` /
   `renewal_outcome_closed_lost`) so negative known outcome cannot be rendered
   as success.
2. The opportunity close date is fenced by `as_of`; a future terminal close does
   not backfill an earlier checkpoint.
3. Non-terminal Renewal opportunities and terminal non-Renewal opportunities do
   not affect outcome realization.
4. VM-8 remains partial. This proves honest synthetic renewal outcome ingestion,
   not live connector durability, attribution, ROI, or UI/ops depth.
