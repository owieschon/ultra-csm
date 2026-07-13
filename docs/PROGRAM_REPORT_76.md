# Program Report 76 — F2R design: 12-lens adversarial sweep

Trigger: the owner observed that each successive review pass on report 75 kept
finding more flaws, and directed a full sweep for both integrity
issues and missed opportunities before the experimental design is frozen.

Method: 12 independent finder lenses (8 integrity, 4 opportunity) over report
75 + the F2R/W7R/Q5 dispatches + the world/eval code, each told what report 75
already documents so it hunts only beyond it; semantic dedup; an adversarial
verification pass (every critical/major integrity finding got two independent
verifiers — one prompted to refute, one to rate materiality; either refutation
kills it; opportunities screened for cost/novelty); then a completeness critic
on the sweep itself. 117 agents, 0 errors.

Result: 92 raw -> 76 unique -> **55 confirmed, 21 refuted**. Confirmed split:
34 integrity (14 high-materiality), 21 opportunity. No live LLM calls against
the product; sweep cost is agent tokens only.

## Verdict on report 75's foundation

Report 75's design is a valid causal pilot in shape, but this sweep shows it
is **not yet freezable**: at least five confirmed findings would either let a
false headline ship or block the run mechanically, and one class of finding
shows the design as specified tests a weaker hypothesis than the same
apparatus could. The corrective work is real but bounded — no finding
overturns the core two-arm causal logic or the "headline never grades against
latent truth" property. The single most important finding is strategic, not a
defect: **the bundled treatment cannot tell us the thing worth knowing** (C-F1
below).

## The one that changes the experiment (read first)

**S1 — Bundled treatment tests the uninteresting hypothesis.** The two arms
are governance (graduation gates + in-loop human QA sampling) vs.
provably-nothing. "Governance beats nothing" is the a-priori-expected result
and the weakest possible claim. The question an eval-literate reviewer or a
buyer actually asks is the *marginal* value of expensive human QA minutes over
near-zero-cost automated gates — which the current design structurally cannot
measure, because it changes both components at once. A third arm (gates-only,
no human sampler) or a 2x2 makes the human-QA marginal effect the headline and
costs one more arm of the cheaper component. This is the highest-value change
in the sweep and it is an owner decision (Owner Ask A).

**S2 — The cheapest power fix is already 80% built and inert.** `WorldConfig`
declares `field_missingness_rate=0.12`, `stale_observation_rate=0.15`,
`contradictory_source_rate=0.05` (added by W1R for the calibration story) and
`_data_quality_flags` rolls them per account — but they mutate nothing the
agent observes, so the drafting task stays trivial (F3) and the defect base
rate stays ~4.8%. Wiring these three rates into the request-build path (no
world redesign, no ruler touched) raises defect prevalence and buys more power
than any statistical amendment in P2 — the sweep estimates ~3.4x. This
directly counters the deck-stacking risk in S3. Owner decision (Owner Ask B):
activate before freeze, or accept a low-power confirmatory tier.

**S3 — Deferring P3 quietly stacks the deck against the hypothesis, and the
freeze makes it one-way.** An easy world produces few hard cases -> few misses
-> a smaller detectable governance effect -> a null result is more likely for
reasons unrelated to governance's true value. P2.1 puts world config inside
the freeze hash and I-3 burns holdout seeds on any post-freeze change, so once
frozen the difficulty cannot be corrected mid-quarter. The zero-cost window to
set difficulty is now, and it is unscheduled. (Interacts with S2: S2 is the
fix, this is why it must happen pre-freeze.)

## Confirmed findings by cluster

Each cluster names a disposition: **FOLD** (mechanical, encode into the
re-emitted dispatches / P1 build with no owner fork), **DECIDE** (genuine
owner fork), **DEFER** (real but post-freeze / lower priority).

### A. Statistical foundation — DISPOSITION: FOLD (one new deliverable)
- **[high] Power machinery is one-sided, item-level, iid-Bernoulli; no
  seed-level paired power function exists or is scheduled**, yet stage 6 must
  lock n_seeds from one. The report's 340-vs-435 sentence misattributes the
  gap to "framing" — it is entirely one-sided-vs-two-sided (verified:
  `required_n_per_arm(0.95,0.90)=340` identical under both framings; two-sided
  classical n=434). Fix: re-emitted dispatch must lift W7R's "never
  reimplement / MUST NOT TOUCH power machinery" constraint and name a paired
  per-seed power function as a committed, tested deliverable before stage 6;
  correct the sentence.
- **[high] "Fully powered" claim uses the item-level arithmetic the same
  report calls anti-conservative.** Under the pinned per-seed primary
  analysis, power depends on n_seeds and inter-seed delta variance, unknown
  until shakedown. Reword P2.2/Ask 3: the amendment delivers full
  ascertainment, not established power; state a seed-level MDD in pp and
  standardized units.
- [med] Variance from 2-3 throwaway seeds (df=1-2) treated as a planning
  constant for n_seeds — add an uncertainty inflation / sensitivity band.
- [med] R-B catch-precision metric has no expected-count, no comparator, no
  pre-committed interpretation.
- [med] Compound headline ("misses at comparable throughput" + minutes) has no
  equivalence margin and no multiplicity/alpha-spending plan across
  co-primaries.

### B. Measurement validity — DISPOSITION: mostly FOLD, two DECIDE
- **[high] The headline scorer shares a judge family with the governed arm's
  intervention**, so the gate removes exactly the defects the judge can see:
  part of the measured delta is guaranteed by construction. R-C's cross-family
  audit has no pre-committed agreement threshold, no headline consequence if
  it fails, and no full-corpus sensitivity re-score. FOLD: pin threshold
  (state if it is the 0.6 weighted-kappa convention), pin the
  failure-consequence rule, add a full-corpus cross-family sensitivity score.
- **[high] The independent second human labeler has twice failed to
  materialize** (reports 65, 68: "no second labeler") and no stage acquires
  one. DECIDE (Owner Ask C): name a labeler + 5-item pilot before shakedown,
  OR pre-commit the fallback now — headline narrows to "judge-scored miss
  rate," single-labeler caveat stated, at prereg lock.
- **[high] The "external CS-QA rubric" anchoring the miss taxonomy does not
  exist** anywhere in the program; stage 3 consumes it. DECIDE/FOLD: insert a
  stage-2.5 deliverable naming the specific rubric with citation + a
  rubric-class -> defect-class -> judge-dimension mapping, owner-ratified;
  mark rubric classes impossible in synthetic drafts out-of-scope.
- **[high] Both halves of the human-minutes axis are unprotected**: measured
  minutes are self-timed by the incentive-bearing owner (reactivity, n=1, no
  packet-exposure-only-in-session rule); the modeled-minutes attribution model
  sits outside the prereg with no validation. FOLD: lock the attribution
  formula pre-shakedown; add a timing-integrity rule (packets first openable
  only inside the timing harness); state the n=1 construct caveat.
- **[high] Judge-validity audits sample only where the scorer already
  flagged** — scorer false negatives are structurally invisible. FOLD: add an
  unconditioned random slice of released items, cross-family + human scored
  blind to the primary scorer, sized to bound the FN rate.
- [major-opp] Miss definition has no severity tiers (safety_boundary ==
  tone_fit in the headline); real CS-QA rubrics are tiered. FOLD into the
  taxonomy derivation.
- [med] Blocked-item counterfactual scoring is apples-to-apples only if the
  miss definition is computable from artifacts a blocked item still has
  (no world response was ever generated for it) — pin which fields the
  definition may use.
- [med] Blind self-consistency check has no k, spacing, agreement metric, or
  pass bar. [med] Scorer prompt is calibrated pre-freeze on arm-identified
  shakedown data. [med] "Grades 100% of released items" has no unscorable-item
  (judge error/timeout) protocol — pin the denominator rule.

### C. Causal identification — DISPOSITION: FOLD (isolation is buildable)
- **[high] Arm isolation at the shared platform Postgres is unspecified** —
  tick/gate/committers/ledger/reobserver all read/write one DB scoped only by
  tenant_id; the zero-governance-nodes DoD checks node counts, not DB
  disjointness. FOLD: each (seed, arm) gets its own DB or run_id-derived
  tenant; add a negative DoD row proving cross-arm query isolation.
- **[high] Verdict-latency -> simulated-time is undefined** — if the sim clock
  pauses while verdicts pend, governance's release-delay cost is erased
  (biases toward governed); if days pass, the governed arm's world diverges
  from control. FOLD: pre-register a fixed verdict SLA of k simulated days,
  identical across arms/tiers, owner wall-clock recorded separately as cost.
- [med] Fixed arm order in I-5 interleaving confounds arm with position and
  provider drift — randomize or counterbalance order per seed.
- [critic] Agent retry/regeneration on gate rejection (`slot_b.py`
  `LIVE_MAX_RETRIES`, best-of-N) gives the governed arm more compute per
  released item — a mechanism confound the node-count DoD cannot see. FOLD:
  pin whether blocked items are re-attempted and hold attempts/compute equal
  or measure it.
- [critic] Owner learning curve is a within-run confound on BOTH axes (minutes
  fall, catch quality rises with run position); interacts with fixed arm
  order. FOLD: randomize seed/item presentation order; state the caveat.

### D. Provenance & anti-gaming — DISPOSITION: FOLD (all mechanical)
- **[high] No external commitment device**: prereg, freeze, countersign all
  bottom out in git commits on a repo the measured party controls; author
  dates are forgeable. FOLD: push the prereg (endpoints, decision rule,
  seed-derivation, exclusion list, analysis-script SHA) to a GPG-signed
  annotated tag + a GitHub Release (server-side created_at), before the run.
- **[high] Checkpoint/resume has no provenance guard** — `run_arm` skips draws
  by (scenario_id, draw_index) only; the P1.6 pass^k re-run against a
  surviving checkpoint would silently return pre-P1 (leaked-string) results.
  FOLD: embed model/judge-version/transport/pass_k/world-hash/scenario-hash in
  the checkpoint header; refuse resume on mismatch; require a clean dir for
  the re-run.
- **[high] I-6's "committed raw artifacts" is impossible as specced** — all
  run artifacts and the COUNTERSIGN live under gitignored `build/`; run_id
  dirs are overwritable; the I-4 firewall is a naming convention in an
  untracked tree. FOLD: runner exits nonzero if run_id dir exists; writes a
  SHA256 manifest appended to a git-committed append-only ledger; scorer and
  analysis read committed inputs.
- **[high] The countersign is an untracked file the operator can author
  itself, and `generate_world()` is a pure importable function** bypassing the
  CLI exit-2 gate. FOLD: derive holdout seeds as HMAC(owner-entered secret, i)
  via the /blind flow so worlds cannot exist before the owner acts; record
  countersign as an owner-signed commit.
- **[high] Holdout seed selection is undefined while per-seed world intel is
  already published** (report 75 sweeps seeds 1-50) — an experimenter can pick
  favorable holdouts and pass every check. FOLD: seed_i =
  SHA256(countersign_hash || i) mod RANGE, with an exclusion list of every
  seed ever swept/characterized (>=1-50, 9001).
- [med] Rulers/grading standards (`eval/gold/**`, `judge_agreement.json`,
  thresholds) are outside the freeze hash — add them. [med] No committed
  blinding manifest to re-attach arm identity post-scoring. [med] The replay
  identity criterion is authored by the run being judged. [med] Committed eval
  artifacts carry no generating-commit provenance.

### E. Plan & scope gaps — DISPOSITION: FOLD + one DECIDE
- **[major-opp] Stages 3/4 omit W3 (cadence engine) and the graduation-gate
  build** that W7R's own preconditions hard-STOP on, plus the graduation-config
  owner ratification. FOLD into the plan.
- **[major-opp] Owner unavailability is an unmitigated SPOF** for stages 5/8/10
  and uncovered by I-2 (not "infrastructure external to both arms"). DECIDE
  (Owner Ask D): pre-commit a pause-and-resume policy for owner-out periods
  that doesn't contaminate timing/latency.
- **[critic] P1's stage-1 verification is vacuous**: F3 forces oracle FNR ~0.0
  regardless of whether the F1 bug is fixed, so "observe FNR ~0.0" cannot
  detect the surviving positional bug at `generator.py:548-549`
  (`data_quality_flags`/`latent_outcome` still keyed by sort index — verified).
  FOLD: P1 fix must cover 548-549; stage-1 verify must be a direct
  per-account generation-index-vs-recorded-latent equality assertion, not an
  FNR observation.
- [major/med] Contract violations are silently retried best-of-5, so the R2
  adoption bar's `contract_violation_rate==0.0` was measured after hidden
  retries — disclose; decide if the bar should see pre-retry violations.
- [moderate-opp] No wall-clock budget for stages 1-7; ~6 sequential owner
  gates compressible to 3-4; stage-4 internal serialization unnamed.
- [med] generator.py:548-549 (folded above). [med] Anchor latent truth graded
  on day-180 sim while anchor observables are unsimulated day-0.

### F. Missed opportunities — DISPOSITION: DECIDE which to take
- **[major] Cost-per-prevented-miss** — the hypothesis's own ratio — is not in
  P2.5's pre-registered endpoints, so the forking-paths rule would forbid
  quoting it. FOLD into the prereg (free arithmetic).
- **[major] Per-dimension / per-family miss decomposition** collapses to one
  binary though the judge scores 6 dimensions and the rollup code exists. FOLD
  into the scorer/chart schema.
- **[major] Zero positioning against published literature** the program
  re-derives: AI Control trusted-monitoring protocol evaluation (Greenblatt et
  al.), LLM-judge self-preference, judge-reliability methodology. FOLD into
  reports/content.
- **[major] The 74/75 negative-findings arc — the strongest external artifact
  — is absent from the publication plan.** FOLD into W-CT.
- [moderate] Second-writer replication (machinery exists, `model_id` is a
  constructor param) would upgrade the claim from "for sonnet" to
  "across models" — DECIDE (adds cost).
- [moderate] time-to-detection, defect-exposure-days, judge-drift sentinel:
  all near-free from committed artifacts — FOLD the cheap ones.
- [moderate] Name the methodology (internal pilot / matched-pairs /
  fixed-sample) to preempt "homebrew stats" — FOLD.
- [moderate] Over-engineering: R-F both-arm repeats, I-7 midpoint check, and
  R-E confirmatory-seed shocks are the three lowest-value protocol items and
  spend the binding resource (owner minutes) — DECIDE whether to cut.

### G. Legal / residue — DISPOSITION: FOLD as publication precondition
- [critic] The derived miss taxonomy's source-rubric licensing/attribution is
  unaddressed, and the public benchmark + 74/75 arc would ship from a repo that
  historically carried F2's verbatim latent strings and company-adjacent
  fixtures — a residue-scrub + license review is a hard precondition for any
  public artifact and appears nowhere.

## What the panel refuted (21) — not carried forward

Representative kills: "three conflicting pinned primary analyses" (P2.5 and
P2.7 are consistent once read as test-choice vs unit-of-inference); "Wilson on
clustered data anti-conservative" (already implied by the per-seed primary);
"graduation makes treatment time-varying" (that is the intervention, not a
confound); several stratified-double-labeling-infeasible variants (subsumed by
the confirmed second-labeler finding). Full refutation reasons are in the run
journal.

## Completeness critic — 5 angles all 12 lenses under-weighted

1. The human-minutes axis is measured on the least-representative human
   possible — the builder (also miss-definition and rubric author): zero
   bearing on the buyer persona (slower, unfamiliar, catches different
   classes).
2. Owner learning curve confounds both axes with run position (folded to C).
3. Stage-1 verify is vacuously green (folded to E).
4. Agent retry-on-rejection is an unmodeled treatment component (folded to C).
5. Legal/residue on the publication track (cluster G).

## Owner asks (this report) — RATIFIED 2026-07-11

The three design forks (A/B/C) were decided on the "most rigorous that stays
powered / highest chance of a substantive result" basis; D/E/F take the
recommended defaults absent objection. This section is the ratified design
basis the stage-3 dispatch re-emission builds to.

- **A (design — RATIFIED: three-arm).** Arms are `control` / `gates_only` /
  `governed`. Primary contrast `governed − gates_only` = the marginal value of
  human QA sampling over near-zero-cost automated gates (the substantive,
  non-obvious result); secondary `gates_only − control` = automated-gate
  effect. Rejected: two-arm (can only claim "governance vs nothing," a-priori
  expected) and 2×2 (two sampler arms exceed the single-owner verdict-minute
  budget; an underpowered 2×2 is less rigorous than a powered 3-arm). Cost vs
  the old two-arm design: +1 arm of `gates_only`, which consumes ZERO owner
  verdict-minutes, so the binding resource is unchanged. Downstream folds:
  the two pre-registered contrasts require an alpha-allocation rule in the
  prereg (P2.5 extended); the per-seed paired analysis now spans three arms
  with `governed − gates_only` as the paired primary delta.
- **B (world difficulty — RATIFIED: activate + calibrate before freeze).**
  Wire the three declared-but-inert `WorldConfig` rates (`field_missingness`,
  `stale_observation`, `contradictory_source`) into the agent-observable
  request-build path, and calibrate them at shakedown to a PRE-REGISTERED
  target defect prevalence (working target ~15–20%, final value locked at
  stage 6 from shakedown measurement). Difficulty becomes a committed design
  parameter, not an accident. Must land before the P2.1 freeze (I-3 burns
  holdout seeds on any post-freeze change). No ruler touched. This is the
  power fix (est. ~3.4×) and the counter to the deck-stacking-toward-null risk.
- **C (validity chain — RATIFIED: human-free primary, labeler as optional
  upgrade).** The judge-validity chain does NOT gate on a scarce second human
  labeler (a dependency unmet in reports 65 and 68). Primary inter-rater
  evidence: cross-family judge agreement (real inter-rater reliability, no
  scarce human), with a pinned agreement threshold and a pre-committed
  headline-consequence rule if it fails (finding B, cluster B). Plus owner
  labels on a stratified sample AND an unconditioned false-negative slice
  (finding B, cluster B — catches scorer blind spots). A named human labeler
  remains an opportunistic upgrade that never gates the run. This is the
  strengthened fallback, not the bare "narrow to judge-scored."
- **D (continuity — default taken):** pre-commit an owner-unavailability
  pause-and-resume policy that suspends the sim clock and the verdict SLA
  together for owner-out periods, so a pause contaminates neither the
  release-latency measure nor the minutes measure. Logged, symmetric across
  arms.
- **E (scope — default taken):** add to the plan the paired per-seed power
  function (committed + tested before stage 6), the W3 + graduation-gate build
  + graduation-config ratification (stages 3/4), and the residue/license
  review as a publication precondition (cluster G); cut the three lowest-value
  protocol items (R-F both-arm repeats, I-7 midpoint self-consistency check,
  R-E confirmatory-seed shocks) to preserve owner verdict-minutes.
- **F (disposition — default taken):** the ~30 FOLD items are encoded into the
  re-emitted dispatches without further per-item approval (corrective, not
  forks). The stage-3 re-emission is diffed against reports 75 AND 76 by a
  cold reviewer to catch spec drift (finding E).

## Sequencing impact

The FOLD items (~30) are absorbed when the dispatches are re-emitted at plan
stage 3 — no schedule change, but that re-emission must now happen against
this report plus report 75, and a cold reviewer diffs the emitted dispatches
against both (finding E, spec-drift). The DECIDE items are now ratified
(A/B/C above), so stage 3 is unblocked once PR #140 merges: the re-emission
produces a three-arm W7R-R, a W2 spec (sampler + gate + externally-derived
tiered miss taxonomy + timing harness + verdict rubric), a W3 build, W4, and a
SCORER dispatch (offline scorer grading 100% of released AND blocked items in
all three arms, blind/shuffled, cross-family audit, locked analysis script
with the paired per-seed power function and the two-contrast alpha rule).
The one net-new schedule item is the difficulty-calibration step folded into
shakedown (Owner Ask B) and the seed-level power function as a stage-6
prerequisite (Owner Ask E).

## Receipts

- Sweep: 117 agents, 92 raw / 76 unique / 55 confirmed / 21 refuted; run
  journal at
  `.../subagents/workflows/wf_2f5ba164-5d4/journal.jsonl` (one result line per
  agent with full return value).
- Self-verified against source this session: `generator.py:548-549` positional
  bug (confirmed); `required_n_per_arm(0.95,0.90)=340` vs two-sided 434
  (confirmed); `WorldConfig` dirty-data rates present and inert (confirmed via
  the prevalence sweeps in report 75).
