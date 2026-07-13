# R0 finding #3 — third run completes cleanly, but lands outside the committed kappa/false-open bar

<!-- clean-docs:purpose -->
Status: **R0's third run (post PR #122's timeout/retry fix) ran all 127/127 gold
items with zero crashes — the retry-coverage fix works. But per-dimension kappa
and false-open comparison against the committed `judge_agreement.json`
(direct-API lane) trips two conditions this dispatch names as hard stops.
Not committing a `transport_fidelity: pass` artifact. Lane stopped per MP-Q
hard exception #3.**
<!-- clean-docs:end purpose -->

## What happened

```
ULTRA_CSM_LLM_TRANSPORT=claude_code python -m eval.run_quality_judge --model claude-sonnet-5
```

completed cleanly through all 63 clean-layer and 64 hard-layer items — including
item 47 (`A6S_security_commitment`, id `slot-b-gold-a92be98de078a890`), the exact
item that aborted the second run per finding #2. No `subprocess.TimeoutExpired`,
no crash. `model_id`/`judge_prompt_version` match the committed lane
(`claude-sonnet-5` / `quality-judge-v9`).

Comparing this run's report against the committed `eval/gold/judge_agreement.json`:

| layer | dimension | committed kappa | committed CI95 | this run |
|---|---|---|---|---|
| clean | grounding_fidelity | 0.696 | [0.516, 0.863] | 0.659 — in band |
| clean | on_task_relevance | 0.855 | [0.753, 0.933] | 0.842 — in band |
| clean | tone_fit | 0.886 | [0.795, 0.951] | 0.803 — in band |
| clean | **safety_boundary** | 1.0 | **[1.0, 1.0]** | **0.98 — out of band** |
| hard | grounding_fidelity | 0.708 | [0.524, 0.86] | 0.584 — in band |
| hard | on_task_relevance | 0.707 | [0.472, 0.879] | 0.789 — in band |
| hard | tone_fit | 0.771 | [0.56, 0.896] | 0.786 — in band |
| hard | safety_boundary | 0.937 | [0.838, 1.0] | 0.905 — in band |

And false-opens (`overall_pass` judge-vs-reference mismatches):

| layer | committed fp/fn | this run fp/fn |
|---|---|---|
| clean | 0 / 0 | 0 / 0 |
| hard | 0 / 2 | **1** / 1 |

Two conditions this dispatch names as hard stops, both tripped:

1. **A kappa outside its band** (MP-Q §0 hard exception #3): `clean_layer.safety_boundary`
   at 0.98 vs a committed band of exactly `[1.0, 1.0]`.
2. **A new aggregate false-open** (MP-Q §1/Q2's own PASS bar): hard-layer `fp`
   went from 0 (committed) to 1 (this run).

## Analysis (not a decision — flagging for the owner)

- The `[1.0, 1.0]` band is a degenerate, zero-width interval — the committed
  clean-layer safety_boundary run happened to have zero judge/human
  disagreement across 63 items, so its own bootstrap CI collapses to a point.
  Any live rerun with even one dimension-adjacent disagreement will fail this
  specific check by construction, independent of transport. That doesn't make
  the check wrong — it's exactly the kind of "looks fine, but formally out of
  band" signal this dispatch's hard exceptions exist to surface rather than
  let me wave through.
- The hard-layer false-open recomposed rather than growing net-new bad news in
  isolation: comparing `by_family` breakdowns, the committed run's two false
  negatives lived partly in `H6b_warm_but_generic` (`pass_match` 1/3), which
  this run resolved to 2/3; a new mismatch appeared in `H1_terse_correct`
  (`pass_match` 4/4 → 3/4), which is where the new `fp` most likely sits. Total
  hard-layer mismatches are unchanged (2 in both runs) — the composition moved.
- `eval/judge_anthropic.py`'s own docstring already documents that omitting
  `temperature` does not make the live judge deterministic — it is
  run-to-run variable by design (that's what `judge_nrun` /
  `determinism_probe` exist to characterize). A single-run kappa/false-open
  comparison against a single committed snapshot cannot distinguish
  "claude_code transport is unfaithful to the direct-API judge" from
  "ordinary run-to-run judge variance, sampled once." This run does not
  provide enough evidence to tell those apart.

## What I did not do

Per MP-Q's dual-role discipline and hard exception #3, I did not re-run R0 a
fourth time hoping for an in-band result — that is exactly the "probing for a
lucky pass" anti-pattern finding #2 already named and rejected. I did not
adjust, widen, or reinterpret the committed CI bands or the false-open bar to
make this run pass. I did not overwrite the committed `eval/gold/judge_agreement.json`
with this run's numbers (this run's full report is quoted above in this
finding; precedent from findings #1/#2 is that a finding-only PR touches only
the finding doc). I did not identify the exact candidate id behind the new
`H1_terse_correct` false positive — doing so would require re-instrumenting
the run to retain per-item raw judge output (it isn't persisted today) and
running again, which is itself a build-then-operate cycle, not something to
do mid-finding.

## Suggested direction (builder's call, not prescribing the fix)

- Before trusting the `claude_code` transport for R2 (Q3's writer bake-off)
  and beyond, characterize its run-to-run variance directly: run
  `judge_nrun`/`determinism_probe` (or N repeated R0 passes) on both
  transports and compare variance bands, rather than one run against one
  committed snapshot from a different transport.
- Separately, the clean-layer `safety_boundary` `[1.0, 1.0]` band is
  untestable in the strict sense for any transport once genuine model
  sampling is involved — worth deciding whether that dimension's band should
  be a tolerance (e.g. n-1 exact matches) rather than a point, independent of
  this run.
- Per-item raw judge scores (not just aggregates) would make future findings
  like this one traceable to a specific candidate id without a re-run.

## Impact

R0 has completed without crashing for the first time (finding #2 fixed), but
has not yet produced a report inside this dispatch's own pass bar. R2/R3/R4
remain gated on R0 passing; OA-Q1/OA-Q3 decisions about trusting the
`claude_code` transport for the writer bake-off and beyond should account for
this until a variance-aware characterization exists.
