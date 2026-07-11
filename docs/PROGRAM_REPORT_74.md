# Program Report 74 — Q4 finding: no-spine ablation is not executable against the current world

Dispatch: `~/ultra-csm-dispatches/MP_Q_QUARTER_RUNWAY.md`, phase Q4 ("no-spine
ablation + pass^k, R3/R4"). BUILD PR: [#138](https://github.com/owieschon/ultra-csm/pull/138)
(merged, `b3c0a7e`). This report is the R3 finding, discovered while sizing the
live OPERATE run for R3 -- before any live LLM call was made.

## Status

**Q4's ablation (R3) is BLOCKED, not run. Q4's pass^k (R4) proceeds
single-arm.** Caught at $0 live spend by pre-run sizing checks, per the
standing rule (this session, 2026-07-11): investigate anomalies before
publishing, never spend live budget to "see what happens" once a structural
problem is suspected.

## Finding: `spine_policy` cannot diverge from `no_spine_ablation`

`src/ultra_csm/world/baselines.py`'s two named policies:

```python
"no_spine_ablation": lambda account_id: (
    health_by_id[account_id].band == "red"
    or adoption_by_id[account_id].adoption_rate < 0.45
),
"spine_policy": lambda account_id: (
    health_by_id[account_id].band == "red"
    or adoption_by_id[account_id].adoption_rate < 0.45
    or (open_cases_by_id.get(account_id, 0) > 0 and health_by_id[account_id].band == "red")
    or (account_id in conflict_ids and decisions_by_id[account_id].surfaced
        and health_by_id[account_id].band == "red")
),
```

Both of `spine_policy`'s extra disjuncts require `health.band == "red"`, which
is already `no_spine_ablation`'s first disjunct. A disjunct that requires a
condition already covered by an earlier disjunct in the same OR-chain can
never change the chain's truth value, for any input. This is not seed- or
scale-dependent -- it is a property of the formula. Verified both
symbolically and empirically: at the dispatch's stated world seed 1,
power-sized scale 62 (`eval.no_spine_ablation.power_sized_scale()`), the two
policies surface the identical 24 of 62 accounts, 0 discordant pairs,
McNemar `p_value=1.0`.

## Finding: fixing the formula would not fix the experiment

The natural fix -- make the spine-augmented clauses fire independently of
`health.band == "red"` -- was considered and rejected after checking what the
spine's *observable* signal actually contains (`src/ultra_csm/world/graph.py`):

- **Stale-fact synthesis reads latent truth, not an independent observation.**
  `build_context_graph` fabricates a stale `health.band` fact directly from
  `latent.corruption_flags` (`"stale_field" in latent.corruption_flags`). A
  policy that consults this is conditioning on ground truth through an
  intermediary -- the spine arm would be unfairly informed relative to the
  snapshot arm, not fairly augmented. Same issue for the `duplicate_contact`
  conflict type (also gated on a corruption flag).
- **The one honestly-observable spine-only signal is doom-uncorrelated at
  this scale.** Restricting to signal a policy could legitimately use without
  reading `latent.*` (open cases, `surface_conflict` conflict nodes which
  trigger on `health=="green" and case_count>0 and decision.surfaced`):
  13 accounts show this signal without already triggering the snapshot
  policy, at world seed 1, scale 62. **0 of those 13 are doomed.** Seed 7 at
  the same scale: 5 such accounts, 1 doomed (the only doomed account in that
  world). Neither seed shows spine-only signal reliably predicting outcome at
  this scale -- there is no honestly-observable augmentation to write yet
  that would make the ablation non-degenerate, not just non-tautological.

## Finding: the outcome variable is under-powered regardless

World seed 1, scale 62: **1 doomed account total** (of 62). Seed 7, same
scale: also 1. The MDD sizing in `eval.no_spine_ablation.power_sized_scale`
(`required_n_per_arm(0.80, 0.60)`, i.e. detecting a 20pp *accuracy* drop) does
not correspond to statistical power over such a low-prevalence outcome --
the measured 0.629 accuracy at n=62 is arithmetic fallout of ~1 TP / ~23 FP /
~38 TN, not a meaningful policy-quality signal at any definition of "spine."
Scaling `--scale` up does not by itself fix this (doomed-rate is a property
of `WorldConfig`'s corruption-process parameters, not sample size), and
scaling up doesn't touch findings 1-2 above regardless.

## Why this isn't a code bug to silently patch

Redefining what "spine" means, or rebalancing the world's doom-generating
process so spine-visible signal actually precedes it, is a real design
decision about the experiment's construct validity -- not a bugfix. It also
duplicates work already named and scoped elsewhere: MP-W1R's Owner Ask #2
(dirty-data/injection layers generated at the world level but not yet wired
into the observable evidence path) is precisely the missing terrain this
ablation needs. Per K2/`/autonomy`, this is an owner decision, not one to
resolve unilaterally inside Q4 -- surfaced here rather than papered over with
a manufactured-to-diverge policy tweak (considered and rejected: it would
trade a visible tautology for an invisible one, since the treatment arm would
be shaped by the goal of producing a difference rather than derived from what
a spine is actually for).

## What still lands this quarter

Q4's other deliverable, pass^k (R4), is unaffected by the above -- it tests
whether the OA-Q1 adopted writer (`claude-sonnet-5`) reliably clears the
gated-pass bar on *world-generated* scenarios (not the curated gold
families R2 used), which is real, in-scope, and cheap (21 world-surfaced,
world-actionable accounts x k=3 = 63 draws, ~1/5 the size of one R2 arm).
Run single-arm (both policies would draft the identical account set, so a
second arm adds cost with zero new information) -- see
`docs/R4_PASS_K_WORLD_SURFACED.md` for the result.

## Recommendation, not a decision

Re-attempt the ablation after: (a) D3/D4 wiring lands (W1R Owner Ask #2) so
spine-only signal is genuinely observable and decorrelated from the snapshot
signal by construction, not by corruption-flag leakage, and (b) the world's
doom-generating process is checked for enough prevalence at the intended
scale to power a comparison. Both are pre-existing backlog items, not new
scope invented for this report.

## Receipts

- Sizing check commands (read-only, no live calls, reproducible):
  `eval.no_spine_ablation.build_world(62)` at seed 1 and seed 7, then
  `ultra_csm.world.baselines.build_policy_table` + `build_context_graph`
  inspected directly (see this report's finding sections for exact figures).
- No commits from this investigation touch ruler files, gold corpora, or
  already-merged product code beyond PR #138 (already merged, BUILD only).
