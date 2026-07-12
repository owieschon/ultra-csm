# Program Report 75 — F2R foundation audit: world ground-truth integrity

## The hypothesis this program exists to test

Stated here because every finding and amendment below is judged against it:
**does a governance layer (graduation gates + in-loop QA sampling) causally
reduce the rate of defective agent outputs shipped, and at what human-minute
cost?** Same agent, same world seeds, two arms — governance present vs
provably absent from the decision path — compared on sampled-miss rate vs
human-minutes/account. Falsifiable in both directions: a null result
(governance adds minutes, catches nothing) is a publishable outcome by the
program's own rules. Everything else this quarter — world realism, judge
validity, transport fidelity, writer adoption — is instrumentation for making
that single comparison credible. An audit finding matters exactly in
proportion to how it touches this comparison's validity or power.

Trigger: Q4's blocked ablation (`docs/PROGRAM_REPORT_74.md`) exposed anomalies
that warranted a full audit before Q5's freeze. Owner directed: "a defensible
foundation must exist before anything moves forward." Method: (a) empirical
sweeps of the world generator across seeds 1-50 and scales 62-1000, all
deterministic and read-only; (b) a full latent-truth flow trace through
`src/ultra_csm/world/**` and its consumers; (c) a claim inventory of the F2R
plan, the W7R control-arm dispatch, and MP-Q's Q5 freeze protocol, mapping
every committed claim to its grading source. No live LLM calls were spent.

## Findings

### F1 (CRITICAL) — Recorded latent truth is misaligned with the world it describes

`_generate_accounts` shapes each generated account's observables from
`_latent_tuple(config, generation_index)`. `_latent_truth_for_world`
re-derives "the same" latent at `_latent_tuple(config, sorted_position -
anchor_count)` over accounts sorted by `account_id` — a hash-permuted order
(ids are uuid5). The two indices disagree for most accounts:

- Seed 11, scale 62: 25 of 27 generated accounts carry latent truth computed
  at the wrong index; recorded doomed = 14 where the generative truth was 4.
- Seed 7, scale 180: 36 of 170 accounts have `latent.doomed` inconsistent
  with the health band their data was generated from.
- Anchor typing is positional (`index < anchor_count AND id in base_ids`), so
  fixture accounts sorting past position 34 are silently re-typed as
  generated (11 of 35 at seed 11/scale 62) and assigned hash latent unrelated
  to the fixture data that produced their observables.
- `max(0, index - anchor_count)` floors positions 0-34 to latent index 0, so
  ~25 accounts can share one identical latent tuple.

Blast radius: every metric graded against `latent_truth` on generated worlds
is measuring label permutation, not policy or agent quality. The committed
`eval/world_scoreboard.json` oracle block (false_negative_rate 0.6667 at its
seed) is an artifact of this bug. Report 74's terrain counts (0/13
doomed-correlation, 1-doomed-per-world prevalence at scale 62) were computed
against misaligned labels — the subsumption finding stands (it is
formula-level, data-independent) but those specific counts are corrected by
this report's F6.

### F2 — Direct ground-truth label copies in observable, agent-readable data

Three verbatim leaks, all confirmed against source:

1. `generator.py:361` — `HealthScore.drivers = latent["causal_chain"][:3]`:
   latent narrative strings ("champion_disengaged", "product_fit_gap",
   "org_change") copied into an observable field. `agent1/sweep.py:743`
   already reads `health.drivers` for trigger derivation.
2. `generator.py:455` — an observable CTA carries
   `reason="Doomed latent trajectory surfaced"`: the latent label itself,
   as text, in data that flows into LLM drafting evidence
   (`sweep.py:496` -> evidence assembly).
3. `generator.py:162` — `SurfaceDecision.abstained` is conditioned on
   `latent_label == "conflicted"`, and propagates into `world.json` and graph
   decision nodes.

### F3 — Observable-latent coupling is noiseless for generated accounts

`generator.py:287-288`: `health_band = "red" if doomed else "green" if
thriving else "yellow"`; `health_score` takes exactly three constant values
(32.0/88.0/63.0). The observable band IS the latent bit relabeled. Any
doom-detection claim on generated accounts is circular — reading `health.band`
is a perfect detector by construction (once F1 is fixed; before the fix it is
a permuted detector). This does not make drafting-quality evals circular
(they are judge-graded), but it makes the world trivially gameable for any
detection/decision-accuracy story, including the planned red-team arm and any
external benchmark framing.

### F4 — The context graph synthesizes "observations" from latent flags

`graph.py` creates stale facts (`:171-188`), duplicate-contact conflict nodes
(`:205-218`), and mislinked-case conflict nodes (`:219-230`, first disjunct)
conditioned directly on `latent.corruption_flags`. Mislinked cases have no
observable counterpart anywhere in the generated data. Empirically (seed 7,
scale 180): all 10 duplicate_contact conflict nodes point at accounts with NO
observable duplicate contact (empty fact_ids), while the 10 accounts with real
observable duplicates get no conflict node — pure decorrelated latent noise
in a policy-visible surface (a consequence of F1's permutation compounding
the layering error).

### F5 — spine_policy is structurally vacuous (carried from report 74)

Both graph-derived clauses are conjoined with `health.band == "red"`, already
clause 1 of the no-spine arm — `spine_policy` cannot diverge from
`no_spine_ablation` for any input. Now root-caused in context: even a
non-subsumed spine policy would inherit F4's contaminated conflict nodes.

### F6 — Prevalence and power, corrected numbers

With F1 understood, the honest prevalence picture: `doomed_rate=0.12` is the
config intent; generated accounts realize ~0.10-0.125 at scale >= 200
(measured across seeds 1,2,3,5,7,11). Fixture anchors realize doomed only via
book dynamics (0 observed across every seed/scale checked). At scale 62 the
world sits in an anchor-dominated regime with small-n windows: realized
per-seed prevalence ranged 0.016-0.226. Hash quality itself is fine (mean
0.118, no per-seed bias at n=1000). Consequence: any latent-graded comparison
needs scale >= 200 AND a measured-prevalence disclosure; `required_n_per_arm`
(a pass-rate MDD tool) is not a substitute for event-count power on a rare
outcome.

### F7 — The knowability audit gives false assurance

`run_knowability_audit` checks name substrings ("latent"/"truth" in fact
keys) and that agent1 never imports `ultra_csm.world`. It cannot see F2's
verbatim string copies, F3's determinism, or F4's latent-conditioned synthesis
— `hard_ok=True` has been shipping alongside all of them. Structural blindness
(no imports) is not informational blindness.

### F8 — Two governance gaps in the path ahead

1. **Freeze scope**: OA-Q2 freezes "the agent code/config hash" only. No
   document places `src/ultra_csm/world/**`, `WorldConfig` defaults, or
   `knowledge/world_response_config.json` inside the freeze. Post-freeze world
   edits would silently break cross-arm comparability.
2. **Headline grading standard**: the W7R chart's miss rate is graded by the
   W2 QA sampler (governed) and an offline scorer (control) — and W2 does not
   exist yet. What operationally counts as a "miss" is currently defined
   nowhere. The power pre-registration also assumes a nonzero, stable baseline
   miss rate with no stated source.

## What is NOT damaged

- **The quarter's headline claim survives intact.** The W7R
  governed-vs-ungoverned chart grades minutes by verdict-session wall-clock +
  a named attribution model, and miss rate by sampler/offline-scorer — no
  dependency on `latent_truth` anywhere in its spec. F1-F7 do not touch it.
- **All judge-graded quality results stand**: R2 bake-off, OA-Q1 adoption,
  Q4's pass^k (graded on drafting quality, not doom detection). One
  disclosure: Q4's pass^k scenarios drew evidence from world data containing
  F2's leaked strings; this does not change what pass^k measured (contract +
  judge-gated draft quality) but is recorded here for completeness.
- **W1R's response/injection machinery is clean by design** (`respond()`
  exposes only a derived boolean; `injection_event()` takes no latent input)
  — though its latent conditioning currently keys off F1's misaligned rows
  until the fix lands.
- Gold corpora, judge kappas, gates, and thresholds (the rulers) are
  untouched by every finding above.

## Redesigned path forward

**P1 — Corrective BUILD (no design fork; one PR):**
1. Thread each account's latent tuple from generation into
   `_latent_truth_for_world` keyed by `account_id` — never re-rolled by sort
   position; type anchors by identity, not position. Bookkeeping fix:
   observables unchanged, recorded truth becomes true.
2. Remove F2's three label copies (drivers from a fixed observable
   vocabulary derived from the account's actual data; neutral CTA reason
   text; abstained derived from an observable rule or dropped).
3. Regression tests: (a) for every generated account, recorded latent must
   equal the tuple that generated its observables; (b) grep-style guards that
   no latent enum string appears in any observable field.
4. Extend the knowability audit with semantic checks (the F2 string classes,
   abstained provenance) so F7's false assurance cannot recur silently.
5. Regenerate all affected committed artifacts (world_scoreboard.json and
   battery artifacts); post a correction addendum to report 74's terrain
   numbers. **Pre-declared expected outcome of the fix, stated before it is
   built so it cannot read as score inflation:** once labels align, the oracle
   false-negative rate on generated worlds drops to ~0.0 — because F3's
   noiseless health<->doomed coupling makes surfacing trivially complete. The
   corrected numbers will look "too good"; that is the honest disclosure of a
   trivial detection task (F3), not evidence of agent quality, and is exactly
   why latent-graded claims stay gated behind P3.
6. Re-run Q4's pass^k after the fix lands (63 draws, ~$2): its scenarios drew
   evidence containing F2's leaked strings, so the current result is
   "measured on pre-P1 world text." The re-run replaces the W4 scoreboard
   evidence with a post-fix measurement; expected to hold, verified rather
   than assumed.

**P2 — Governance amendments (owner ratification, no code):**
1. Amend the OA-Q2 freeze scope to include `src/ultra_csm/world/**`,
   `WorldConfig` defaults, `knowledge/world_response_config.json`, AND the
   fixture inputs world generation depends on (`build_synthetic_book` /
   `simulate_data` sources under `src/ultra_csm/data_plane/`) in the recorded
   hash — a post-freeze fixture edit would silently change every world.
2. **Separate measurement from intervention in the headline design.** As
   specified, the governed arm's miss rate comes from the in-loop sampler's
   SAMPLE. Power arithmetic says that under-powers the headline: detecting a
   5%->10% miss-rate difference needs ~435 graded items per arm (two-sided
   alpha=0.05, power 0.80; the repo's own pass-rate machinery gives 340 for
   the equivalent 0.95-vs-0.90 framing) — an in-loop sample at plausible
   volumes (~120/arm over 30 days) cannot get there, and the pre-registration
   would correctly emit `insufficient_power_for`. Amendment: the OFFLINE
   scorer grades 100% of released items in BOTH arms after the run (judge
   cost at Q4-measured rates: ~$20-40 for ~600 items/arm — affordable); the
   in-loop sampler remains the governed arm's INTERVENTION only, never the
   chart's measurement. This keeps the causal design identical and makes the
   headline fully powered instead of pre-registered-underpowered.
3. Add to W2's spec: an operational definition of "miss," used identically by
   the in-loop sampler and the offline scorer, plus a measured baseline miss
   rate feeding the power prereg. First empirical prior, from Q4's pass^k run:
   ~4.8% of draws failed the gated bar (3/63) — a real, nonzero defect base
   rate for the governance layer to act on.
4. Standing rule: latent-graded claims run at scale >= 200 with realized
   prevalence disclosed alongside every rate.
5. **Pre-register the decision rule, not just the power.** The power prereg
   commits an MDD; no document commits the test itself. Before day 1 the
   prereg artifact must also pin: primary endpoint (per-item miss rate over
   all released items, both arms, offline-scored), the test (two-proportion,
   two-sided, alpha=0.05 — the repo's `one_sided_two_proportion_p_value`
   exists if a directional test is preferred, but the choice is made NOW),
   the CI method (Wilson, the repo's existing convention), and the secondary
   endpoints (human-minutes measured/modeled, per-day trend) explicitly
   labeled non-confirmatory. Anything not pre-registered is reported as
   exploratory. This closes the forking-paths hole: without it, the
   favorable test could be chosen after seeing the data.
6. **Close the refusal loophole with a co-reported throughput metric.** The
   governed arm's gates can BLOCK releases, so its released-item miss rate
   improves partly by refusing work — taken to the limit, "never release"
   scores a perfect miss rate. The headline must co-report released volume /
   task coverage per arm alongside miss rate and minutes, and the claim
   wording must be "misses per released item at comparable throughput," not
   miss rate alone. Without this the design is gameable by conservatism.
7. **State the unit of inference and analyze accordingly.** Items within an
   arm share one agent trajectory and one world state — they are not
   independent Bernoulli draws, and after the first governance intervention
   the two arms' item mixes diverge (treatment changes the world it acts
   on). The item-level two-proportion test is therefore anti-conservative.
   Pre-register: per-seed aggregation as the primary analysis (n = seeds),
   item-level tests reported with a design-effect caveat, and the claim
   worded as the TOTAL effect of governance (direct catches + downstream
   world-state effects), never as a pure gate-filtering effect.
8. **Stratify the double-labeling and blind the arms.** At a ~5% miss rate,
   30 randomly-drawn gold items contain ~1-2 misses — the second labeler
   would barely sample the class the whole experiment turns on. The >=30
   double-labeled items must oversample scorer-flagged misses (e.g. all
   flagged misses + a matched clean sample). Any human grading or verdict
   session that could touch the comparison must be blind to arm identity.

**P3 — World-realism wave (deferred BUILD, gates only latent-graded claims):**
Noise/lag between latent state and observable symptoms (health as a noisy,
lagged consequence, not a relabel); corruption processes that produce real
observable artifacts (actual mislinked case rows, actual stale records in
data); the graph derived purely from observables; a non-vacuous spine policy;
`world.json` split into observable and oracle-only artifacts; PRD-fitted
rates. This wave gates the re-attempted no-spine ablation, red-team
doom-detection claims, and any external benchmark release. It does NOT gate
the quarter headline, which never grades against latent truth.

**Sequencing:** merge PR #139 (unaffected by these findings) -> P1 -> P2
ratifications -> Q5 shakedown/freeze -> quarter (headline path) with P3
scheduled behind it.

## Resolution plan for the referee objections (P2.6-P2.8 continued)

R-A. **Two-tier run design (resolves the n=3-seeds / unit-of-inference
objection at its root, not just in the analysis).** Confirmatory tier: 8-10
seeds x a shorter window x both arms; primary analysis = paired per-seed
miss-rate deltas (same seed, both arms -> one delta; Wilcoxon signed-rank or
t on n=8-10 pairs), with inter-seed variance measured at shakedown feeding
the seed-level power calculation. Demonstrative tier: ONE full 30-day run for
the narrative artifacts (time-series, drift canaries, shock story) -- showcase,
explicitly non-confirmatory. Binding constraint is honest: governed-arm human
verdict minutes scale with seed count, so n_seeds is chosen at shakedown from
measured minutes/seed, not assumed. Estimated live spend for the confirmatory
tier at Q4-measured rates: low hundreds of dollars; wall-clock parallelizable
across seeds.

R-B. **Counterfactual scoring of blocked items (dissolves the refusal
objection beyond P2.6's throughput co-reporting).** The offline scorer grades
everything the agent PRODUCED, released or gate-blocked, in both arms. This
yields catch precision: what fraction of blocked items were actually
defective. A governance layer that blocks good work to look safe is exposed
directly, not just via a throughput number.

R-C. **Judge-validity bundle (shrinks the same-family-circularity
objection).** (1) Stratified double-labeling per P2.8. (2) Cross-family
judge audit: a second, non-Anthropic model family (chosen per the program's
standing reviewer-selection and subscription-only rules) re-scores the
stratified sample against the same operational miss definition; report
cross-family kappa. High agreement defangs the circularity objection; low agreement is a
published finding adjudicated by the human labels. (3) Judge model id +
version + prompt version pinned and asserted constant across the entire run
(mechanical CI check).

R-D. **Environment-credibility bundle (bounds the self-built-world objection
as far as it can be bounded without production data).** (1) PRD-fitted rates
(already planned). (2) The operational miss taxonomy is DERIVED from an
external source (real CS QA rubric conventions), with the derivation
documented -- so the defect classes governance catches are not authored to
match governance capabilities. (3) The red-team catch-rate arm (planned W-RT)
demonstrates the world is not tuned to be easily catchable. (4) The benchmark
release (planned, content track) invites community replication -- external
validity by others running THEIR agents. The remainder is worn as scope.

R-E. **Shock generalization:** the scripted mid-run shock is placed at a
different day per confirmatory seed (config-level), so the drift-canary story
generalizes across k placements instead of resting on one.

R-F. **Trajectory-noise floor:** 2-3 repeat runs on one seed (both arms),
published as the run-to-run variance floor -- extending finding #3's kappa-band
methodology from judge level to trajectory level. Cheap, and it makes the
per-seed deltas interpretable against a known noise floor.

Irreducible after all of the above, stated plainly: the world is still
self-built (R-D bounds it, community replication tests it, production data
would resolve it); the judge is still an LLM (human labels exist only on
stratified samples); n stays modest by human-minutes budget, not by choice.

## Operational integrity protocol (I-1..I-9)

The design-level protections above do not cover the layer where selective
reporting actually happens in practice: run operations. These rules are part
of the pre-registration, violated = run invalidated.

- **I-1 Stopping rule + monitoring firewall.** Confirmatory run length,
  window, and n_seeds are fixed at prereg (from shakedown calibration). No
  interim analysis of arm-comparative miss rates during the run; operational
  monitoring (process health, quota, crash detection) is firewalled from
  outcome metrics — the monitor scripts read process state and error logs,
  never scores. No early stop on favorable data, no extension on unfavorable.
- **I-2 Seed-failure and exclusion protocol, pre-committed.** An agent
  failure (crash, contract violation, hang) is DATA, never an exclusion. Only
  infrastructure failure external to both arms (host reboot, provider outage)
  permits a seed rerun — both arms rerun together, the event logged before
  any partial results are examined. Exclusions decided by rule, not by
  looking.
- **I-3 Holdout-seed burning.** Any post-freeze change to agent, world,
  judge, or analysis code burns every holdout seed already generated or run:
  the fix is applied, a NEW freeze is countersigned, NEW seeds are generated.
  No "fix the bug and rerun the same seeds" — the old seeds are contaminated
  by having been seen.
- **I-4 Confirmatory/demonstrative firewall.** The headline chart is built
  from confirmatory-tier data only, by artifact path (separate run_id
  namespaces); the 30-day demonstrative run is labeled non-confirmatory in
  every artifact that touches it. A better-looking demonstrative number never
  substitutes into the headline.
- **I-5 Scoring protocol.** Offline scoring runs post-hoc with items from
  both arms SHUFFLED into one batch per seed, arm identity stripped from
  every payload and filename the scorer sees, one scoring session per batch
  (no re-scoring on disagreement with expectations). Arm runs per seed execute
  temporally interleaved (governed/control back-to-back), so provider-side
  drift and cache states cannot systematically favor one arm.
- **I-6 The analysis is inside the freeze.** The confirmatory analysis
  script (paired per-seed deltas, pre-registered test, CI method) is written,
  tested against shakedown data, and committed BEFORE the confirmatory run;
  the headline is produced by executing that committed script on committed
  raw artifacts, and the report carries the one-command reproduction line.
- **I-7 Verdict-standard stability.** The owner's verdict rubric is written
  down before the run; the blind self-consistency check (re-presented decided
  packets) is scheduled at run midpoint AND end, so verdict drift is measured
  during the experiment, not discovered after it.
- **I-8 The improvement loop stays outside the confirmatory window.** W6's
  improvement cycle operates on a post-run fork. Any agent change it produces
  is a NEW experiment under I-3, never a mid-run mutation of a frozen arm.
- **I-9 Provider drift disclosed as unfixable.** Subscription transport
  cannot pin silent provider-side model updates. Mitigations: I-5 temporal
  interleaving (drift hits both arms equally), model id + prompt version
  asserted constant, run dates recorded. Residual risk disclosed in the
  report, not hidden.

## Implementation plan (dependency-ordered; each stage names its verification)

Current build state, honestly: W1R and the Q1-Q4 tooling exist; W7R is an
emitted dispatch, not built; W2 (QA sampler + miss definition + verdict
tooling), W4 (cost architecture), the offline scorer, the chart pipeline, and
the analysis script DO NOT EXIST yet. The plan below is the full path from
here to the headline.

0. **Merge #139 and #140** (owner). Ratify asks 1-6.
1. **P1 corrective BUILD** (one PR): alignment fix + F2 leak removal +
   semantic knowability checks + artifact regeneration. Verify: new
   regression tests green; pre-declared FNR ~0.0 observed; full suite green.
2. **Pass^k re-run post-P1** (~$2, 63 draws). Verify: coverage 1.0; W4
   scoreboard evidence refreshed. Baseline-miss prior updated from its result.
3. **Re-emit amended dispatches** encoding P2.1-P2.8 + R-A..R-F + I-1..I-9:
   W7R-R (arms + two-tier runner + freeze tool + power prereg), W2 spec
   (sampler, operational miss definition derived from the external rubric,
   verdict-session timing capture, verdict rubric doc), W4 (cost), plus a new
   SCORER dispatch (offline scorer + shuffle/blind harness + chart pipeline +
   locked analysis script). Verify: lint + freeze stamps + cold-reader review
   per emitter protocol.
4. **BUILD wave executes those dispatches** (separate sessions/PRs each).
   Verify: each dispatch's own DoD; cross-family judge access is proven
   working HERE (a 5-item smoke test), not discovered broken at scoring time.
5. **Shakedown on throwaway seed 9001** (Q5 as amended): calibrates released
   items/day, human minutes/seed, inter-seed variance (2-3 throwaway seeds),
   baseline miss rate, scorer throughput, and — named surprise pre-empted —
   whether the graduation-gate horizon fits the confirmatory window (if gates
   need >window days to graduate, the window lengthens or the gate config is
   scaled, decided and recorded BEFORE prereg lock).
6. **Prereg lock**: n_seeds, window length, sampling rate, MDD, decision
   rule, exclusion rules, stopping rule — all numbers final, committed, from
   shakedown measurements. Scoring budget check against measured throughput
   (order-of-magnitude at Q4 rates: ~4,000 items across a 10-seed
   confirmatory tier ≈ ~$110 and ~27h wall-clock, parallelizable — scheduled,
   not discovered).
7. **Freeze + countersign (OA-Q2)** — hash scope per P2.1 (agent + world +
   fixtures + judge prompt + analysis code). THEN holdout seeds generated.
8. **Confirmatory tier runs** under I-1/I-2/I-5. Verify: ledger true-negative
   test per seed; artifact completeness per run_id before scoring.
9. **Offline scoring** under I-5, then **execute the locked analysis script**
   (I-6). The output IS the headline, whatever it says.
10. **Demonstrative 30-day run** (I-4), reports, and the content track.

Estimated total live spend for stages 5-10 at Q4-measured rates: low hundreds
of dollars, dominated by scoring; the binding resource is owner
verdict-minutes (measured at stage 5, sets n_seeds at stage 6).

## Residual risks that no amendment above removes

Stated so acceptance of this path is informed, not implied:

1. **Miss ground truth is the judge.** The hypothesis's dependent variable is
   judge-graded. Its validity rests on the existing kappa work plus the
   already-planned double-labeling (>=30 gold items, second human) and the
   blind owner-verdict self-consistency check — the headline claim depends on
   those directly, and they must land before the quarter, not after.
2. **The world stays easy until P3.** Post-P1 the world is honest but its
   detection task is trivial (F3 disclosed, not fixed). The headline
   comparison is about drafting/governance defects, not detection, so it
   survives — but any reviewer probing "how hard is this world?" gets the
   F3 answer until the realism wave lands.
3. **Expected-volume input to the power prereg is a guess until shakedown.**
   The W7R routing residual already owns this; the dry run calibrates it.
   If shakedown volume is far below the assumed ~20 items/day, the 100%-
   offline-scoring amendment still helps but cannot conjure events that
   never happened — the honest fallback is a longer run or a narrower claim.

## Owner asks

1. Ratify the P1/P2/P3 split and sequencing above (specifically: Q5 proceeds
   after P1+P2, with P3 deferred).
2. P2.1 freeze-scope amendment — approve wording before the freeze tool is
   built in W7R Phase 1.
3. P2.2 measurement/intervention separation — this changes the W7R headline
   design (offline scorer grades 100% of both arms; sampler = intervention
   only). It is the difference between a fully-powered headline and a
   pre-registered-underpowered one; needs your explicit sign-off since W7R's
   dispatch text says otherwise.
4. P2.3 — approve that W2's build must pin the operational miss definition
   before the power prereg is treated as meaningful.
5. Decide whether report 74 receives an inline correction note or stands with
   this report as its correction (recommendation: stands; 74's conclusions
   are unchanged, only its terrain counts are superseded).
6. Ratify the R-A two-tier run design (confirmatory seeds + one demonstrative
   30-day run) — it supersedes W7R's single-run framing and re-scopes the
   quarter's cost/timeline; n_seeds is fixed at shakedown from measured
   human-minutes per seed.

## Receipts

- Empirical sweeps: seeds {1,2,3,5,7,11} x scales {62,120,200,400} doomed
  counts; 50-seed window-rate extremes (0.053-0.263 at n=38); 20-seed hash
  bias check at n=1000 (mean 0.1178, stdev 0.0086). All reproducible from
  `generate_world(WorldConfig(seed=s, scale=n))` — deterministic, no LLM.
- Misalignment: verified by mapping generation index vs sorted position per
  account id (25/27 mismatched at seed 11/scale 62; consistency check
  health_red<->doomed mismatches: 4, 12, 5, 16 at seeds 1, 2, 7, 11).
- Source quotes verified at: generator.py:162, 287-288, 361, 455, 501-517;
  graph.py:171-230, 239; sweep.py:496, 743.
- Claim inventory: PLAN_MP_F2R_MEASURED_QUARTER.md, MP_W7R (319 lines), MP_Q
  (Q5 sections) — every committed metric mapped to its grading source; the
  literal token `latent.doomed` appears in none of them; the only
  latent-graded claim in the program is Q4's ablation (already blocked by 74).
