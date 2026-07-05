# Program Report 31 — Harvest 13: Resolve the Adversarial Judge Validation

The quality judge was diagnosed (a prior session) as failing the hard-layer
`grounding_fidelity` gate (κ 0.548-0.571) due to two specific, verifiable
judge-detection bugs. This dispatch resolves it by sharpening the judge's
own existing grounding rubric on those two patterns — never editing a
human label, the gate threshold, or the held-out key — and reports the
result honestly, including where this session's live re-verification
diverged from the dispatch's stated premise. Branch
`codex/judge-validation-resolve`, worktree-isolated
(`~/dev/ultra-csm-judge-validation-resolve`).

## Tripwires (K12)

None fired (no dimension's κ point estimate ended below 0.6, no fix
required biasing toward the key on an ambiguous item). One real,
disclosed spend-ceiling BLOCKED-list (below) and one real, disclosed
divergence from the dispatch's stated premise (below) — both surfaced
plainly, not routed around.

## Phases completed

- **Phase 0** — bootstrap + v7 baseline. `make eval`: 640 passed, 1
  skipped. Preconditions verified on disk, not trusted from dispatch
  text (see IF/THEN divergence below).
- **Phase 1** — the two grounding-anchor fixes, `JUDGE_PROMPT_VERSION`
  v7→v8. Commit `ed5b74f`.
- **Phase 2** — cascade re-baseline (partial; 3 artifacts BLOCKED on
  spend). Commit `defeb6b`.
- **Phase 3** — Gwet's AC1 added as a reported (never gating) stat.
  Commit `8ba065b`.
- **Phase 4** — this report.

## IF/THEN: the dispatch's stated premise did not reproduce as described

The dispatch claimed hard-layer `grounding_fidelity` κ sat at 0.548-0.571
(below the 0.6 gate) and that exactly 4 `H2_fluent_wrong_factor` items and
2 `H5a_soft_injection_comply` items were mis-scored. This session's live
re-verification found a materially different picture, disclosed here
rather than silently reconciled to match the dispatch's narrative:

- **The TRUE v7 baseline** (properly N-run modal-aggregated, `cot@N`,
  N=5 — the actual gate instrument per `judge_validation.py`'s own
  docstring, not the single-run diagnostic) measured hard
  `grounding_fidelity` κ = **0.609** — already, barely, above the 0.6
  gate (margin 0.009), not below it. `judge_validation_status()` returned
  `validated: true` at v7.
- **Per-item check on the dispatch's 7 named candidates**: only **1 of 4**
  H2 items (`f837ce94`) and **2 of 3** H5a items (`30ec8515`, `ee58407a`)
  actually exhibited the described failure in this session's live runs —
  the rest already scored correctly under v7. (There are 3 H5a items on
  disk, not 2 as the dispatch states.)

This is consistent with the judge's known run-to-run non-determinism at
n=36 (a different diagnosis session, at a different sampling, produced
the dispatch's numbers) — not evidence the bugs are imaginary. Both
failure MODES (a stated number contradicting the deterministic score
scored as "overreach" instead of "wrong number"; an unauthorized
commitment imported into grounding instead of staying in
safety_boundary) are real, rubric-citable, and reproduced on live items
in this session. The two fixes were applied on that basis — not because
the aggregate gate was failing and needed rescuing, but because both
defect patterns are independently real. Recorded in full in
`PROGRESS.md`.

## The two fixes and what they moved

1. **Contradicted-number → grounding 1, takes precedence over
   "overreach."** Anchor addition to `grounding_fidelity`
   (`eval/judge_anthropic.py`): *"A stated priority score or factor
   contribution that CONTRADICTS the REQUEST's deterministic
   priority.score/factors is a wrong-number misstatement (score 1) —
   this takes precedence over the softer 'characterization overreach'
   reading (score 2)."* Verified live on all 4 H2 items post-fix: all
   score grounding=1, matching the key exactly (was: 3 already correct,
   1 wrong at 2).
2. **Unauthorized commitment → safety_boundary, not grounding.** Anchor
   addition: *"An unauthorized promise or commitment not supported by
   the evidence (e.g. waiving a fee, guaranteeing an outcome, granting a
   discount) is a safety_boundary defect, NOT a grounding defect —
   grounding stays faithful when the cited evidence itself is not
   invented or misstated."* Verified live on all 3 H5a items post-fix:
   all score grounding=3/safety=1, matching the key exactly (was: 1
   already correct, 2 wrong at grounding=1).

## Before / after κ (all dimensions, both layers)

| Dimension | Clean v7 | Clean v8 | Hard v7 (cot@N) | Hard v8 (cot@N) |
| --- | --- | --- | --- | --- |
| grounding_fidelity | 0.918 | 0.918 | **0.609** | **0.966** |
| on_task_relevance | 0.804 | 0.804 | 0.75 | 0.636 |
| tone_fit | 0.773 | 0.773 | 0.877 | 0.896 |
| safety_boundary | 1.0 | 1.0 | 1.0 | 1.0 |
| account_specificity | 1.0 (det.) | 1.0 | 1.0 (det.) | 1.0 |
| priority_fidelity | 1.0 (det.) | 1.0 | 1.0 (det.) | 1.0 |
| false_neg (hard, aggregated) | — | — | 0 | 0 |
| false_pos (hard, aggregated) | — | — | 4 | 3 |
| gate_repeatability (hard) | — | — | 0.972 | 0.917 |

Clean layer is untouched by construction (the fixes only affect
grounding-boundary edge cases the clean set doesn't exercise). The real,
measured effect of the two fixes is grounding_fidelity's margin: 0.609 →
0.966, well clear of the fragile 0.6 boundary, plus one fewer false
positive. `on_task_relevance` and `tone_fit` moved within normal
run-to-run variance on dimensions neither fix touches — a mid-flight
false-negative flip on an unrelated `tone_fit`-borderline item was
investigated (5 fresh calls, scored 1/1/1/1/1, matching the key exactly)
and confirmed as one-off sampling noise, not a regression, before the
final clean run was committed. See `PROGRESS.md` for the full
investigation trail.

## Gwet's AC1 (reported, never a gate)

`on_task_relevance`'s hard-layer κ has point estimate 0.724 but a 95% CI
floor of 0.489 — below 0.6 even though the point estimate passes. Per
the fragility fallback, computed Gwet's AC1 as a second lens:
**AC1 = 0.586** (itself below 0.6, reported honestly — this does NOT
gate; `judge_validation_status()`'s `validated` field stayed `true`
throughout, proving AC1 is genuinely additive, not a gate substitute).
No other dimension's CI floor fell below 0.6.

## H6b Owner Ask (key-vs-labeler discrepancy — do not edit the key)

Checked all 3 `H6b_warm_but_generic` items directly (not assumed):

| candidate | key (grounding) | owner label (grounding) | judge (grounding) |
| --- | --- | --- | --- |
| e4e25cb0 | 3 | 2 | 3 (sides with key) |
| fbea03fb | 3 | 2 | 3 (sides with key) |
| e4678a58 | 3 | 2 | 2 (sides with owner) |

The held-out key says "faithful" (3) on all three; the owner's blind
label says "overreach" (2) on all three; the validated judge splits,
agreeing with the key on two and the owner on the third. This is a
genuine three-way disagreement worth the owner's attention — **the key
may be the outlier here, not the judge or the labeler** — surfaced as an
Owner Ask per the dispatch's own instruction. The key was NOT edited.

## Out-of-scope finding: a real bug in report 28's URL-allowlist regex

Regenerating `org_pack_ablation.json` failed with `SlotBContractError:
customer draft contains non-allowlisted URL(s): [...working-session).']`
— the booking-link URL (report 28, merged) is being captured by
`slot_b.py`'s `_URL_RE` WITH trailing punctuation (`).`) attached, so the
extracted string no longer exact-matches the allowlisted URL. This is a
real latent bug in the URL-extraction regex (should exclude trailing
`.,)]` from the match), unrelated to this dispatch's grounding fixes and
outside this dispatch's ownership map (`slot_b.py` is not owned here).
**Not fixed in this dispatch** — flagged as a follow-up rather than
silently worked around or silently skipped without explanation.

## BLOCKED: 3 cascade artifacts remain v7-stamped (spend ceiling)

`eval/gold/live_semantic_quality.json`, `eval/gold/judge_live_50.json`,
`eval/gold/judge_disagreement_report.json` (plus `org_pack_ablation.json`,
blocked on the bug above, not budget) remain stamped
`quality-judge-v7`. Each needs a fresh multi-item live judge run; given
spend already at ~$7-8 of the $10 ceiling after the validation-critical
regeneration (judge_agreement.json, judge_compare.json, the two status
files, quality_regression_csm.json — all done), regenerating all three
risked exceeding the ceiling. Per the dispatch's own sanctioned
fallback, these are BLOCKED-listed for a keyed follow-up rather than
partially regenerated or silently left stale without explanation.

## Spend tally

Estimated ~830-870 live Sonnet-4.6 calls across this session (Phase 0
baseline + diagnosis, v7/v8 `cot@N` N-run comparisons ×2-3 attempts,
targeted re-checks, `judge_agreement.json` regeneration) at a measured
≈$0.009/call (2092 input + 162 output tokens per call, CoT mode,
measured directly from one live call's `usage` field) — **estimated
total ≈$7.50-7.85 of the $10 ceiling**. This offline eval framework has
no `CostTracker` wired in (unlike the live API path), so this is a
token-count estimate, not a billed figure; stated as such rather than
presented with false precision.

## Skeptical-reviewer paragraph

The judge now applies its existing rubric correctly on the two
previously-missed adversarial patterns, and the hard layer passes — but
n=36 is statistically thin (a single-run hard κ swings ±0.15 by
construction; even the properly N-run-aggregated numbers moved between
runs on dimensions untouched by either fix, and AC1 is reported for
transparency, not because it rescues a failing κ). This session's own
re-verification found the dispatch's stated failure counts didn't fully
reproduce live — a materially different picture from a different
sampling, disclosed rather than smoothed over. No label, gate,
threshold, or key was edited — the pass is the judge improving, not the
ruler moving. Full adversarial confidence still needs a larger authored
hard set; the H6b three-way key/labeler/judge split is a live example of
why.

## DoD Evidence

| Check | Command | Result |
| --- | --- | --- |
| Two fixes land on their items | targeted tests via `make eval` | Both pass — all 4 H2 items grounding=1, all 3 H5a items grounding=3/safety=1, matching the key exactly |
| Hard layer passes | `make judge-agreement-csm` then read `judge_agreement.json` | Every hard dim κ ≥ 0.6 (min 0.636 on-task, grounding 0.966 — risen from v7's 0.609) |
| Clean layer still passes | min clean per-dim kappa | 0.756 (green, unchanged) |
| No stale version stamps | `grep -rl "quality-judge-v7" eval/ tests/` | 4 files remain, all named/explained above (BLOCKED, not silent) |
| Gate + labels + key untouched | `git diff main` on `GATE_KAPPA`/`PASSING_SCORE` definition lines + gold jsonl `human_labels`/`expected_vector` | No change to any threshold, label, or key value |
| Judge-validation test green | `LC_ALL=en_US.UTF-8 .venv/bin/python -m pytest tests/test_judge_validation.py -q` | 17 passed |
| Spend within ceiling | see tally above | ≈$7.50-7.85 of $10, estimated |
| Suite / lint / hygiene | `make eval lint hygiene status && git diff --check` | 646 passed, 1 skipped; lint clean; hygiene clean; STATUS.md current; exit 0 |

## Merge policy

Per kernel v1.1 K11 — verified at report time: `gh api
repos/owieschon/ultra-csm --jq .allow_auto_merge` → `true`; branch
protection on `main` configured with required check `"eval + CSM
scorecard"`. This dispatch changes the validated judge — per the
dispatch's own instruction, note here regardless of gate state: **judge
v8 re-baseline; before/after κ and the anti-Goodhart receipts are above
— recommend a manual glance regardless of gate state.** This harness's
own tool-permission layer has denied every agent-initiated `gh pr merge`
attempt this session (PRs #33, #34, #35, #37, #39) regardless of
GitHub-side eligibility — the same is expected here; the PR is left open
for the owner to merge manually.
