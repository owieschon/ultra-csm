# R2 finding #2 — cost telemetry didn't survive the mid-run process kill

Status: **Root cause confirmed and fixed. This corrects a wrong hypothesis
already published in `docs/R2_WRITER_BAKEOFF_RESULT.md` (PR #133) — see
"What I got wrong" below.**

## What happened

PR #133's cost/latency comparison made Sonnet 5 look cheaper and faster
than Haiku 4.5 (the opposite of the dispatch's stated expectation). That
report flagged the numbers as untrustworthy and named a hypothesis:
intermittently missing `usage.input_tokens` in the `claude` CLI's JSON
response.

## What I got wrong, and how I found out

I ran 6 live diagnostic calls against the real `claude` CLI using the
actual Slot B system prompt and real adversarial scenario payloads
(injection families) — `usage` was present in 6/6. That's the wrong
result for the "CLI sometimes omits usage" theory to be the dominant
explanation (an 82/171 ≈ 48% miss rate implied by the reported numbers
would have shown up in 6 tries with ~98% probability). The theory was
plausible-sounding but not what actually happened, and I would not have
caught that without reproducing it rather than trusting the hedge already
written into the PR.

## Actual root cause (confirmed from the code, not inferred)

`eval/writer_bakeoff.py`'s `build_report()` created one `CostTracker()`
per arm, held only in that process's memory:

```python
trackers = {key: CostTracker() for key in CANDIDATE_MODELS}
```

The R2 run was killed mid-flight (finding: `PROGRESS.md`, 2026-07-11 —
the operator session's own `/model` switching tore down the
harness-tracked background process) and relaunched from the on-disk
checkpoint. `run_arm()` correctly skips draws already in the checkpoint
(`continue`) — but that means **no new call, hence no new
`cost_tracker.record()`**, for any draw that had already completed before
the kill. The relaunched process's `CostTracker` started empty. The
Haiku arm's checkpoint had 106/171 draws before the kill; the reported
`total_calls=89` is the count from *only the 65 post-relaunch draws*
(plus retries), not the full 171. The Sonnet arm ran in one continuous
session, so its numbers were complete. **PR #133's comparison measured
two arms over different-sized populations — not a real cost difference
between the models.**

## Fix (this PR)

Telemetry now lives in the checkpoint, not in a live tracker:

- `run_arm()` gives each draw its own `CostTracker()` + `AnthropicReasonDraftWriter`
  (transport is stateless, so this has no behavior cost) and folds that
  draw's `input_tokens`/`output_tokens`/`cost_usd`/`latency_ms` into the
  checkpoint dict before writing it — the checkpoint itself now carries
  the telemetry, so it survives however many kill+resume cycles a run
  goes through.
- `_telemetry_from_draws()` computes the arm's aggregate by summing over
  the full checkpoint (old + new draws), never from a live tracker.
- A `coverage` field (priced draws / total draws) makes a partial-telemetry
  arm self-reporting instead of silently wrong: `cheapest_adopt_eligible`
  in the report is now `null` whenever any eligible arm's `coverage < 1.0`,
  rather than comparing an incomplete population against a complete one.
- `CostTracker.stats()` gained `total_input_tokens`/`total_output_tokens`
  (additive, non-breaking) so per-draw telemetry can read the breakdown it
  needs.

## What this does NOT fix

PR #133's already-committed checkpoints predate this change and have no
per-draw telemetry (`input_tokens: null` on every draw) — this fix cannot
recover that data retroactively. A confirmatory rerun with this fix
applied is required before any cost-based tie-break is trustworthy. The
quality result (`adopt_eligible=True` for both arms, near-identical
`gated_pass_rate`/`pass_k_rate`) is unaffected — that data was always
checkpoint-derived and never depended on the arm-level tracker.

## Regression tests

`tests/test_writer_bakeoff.py`: `_telemetry_from_draws()` sums only
priced draws and reports coverage correctly (including the empty-arm
case); a real `AnthropicReasonDraftWriter` + per-draw `CostTracker`
(stubbed only at the transport boundary) correctly captures telemetry;
and the direct regression for the bug itself — a checkpoint pre-loaded
with full telemetry and zero outstanding draws reports correct aggregate
telemetry with **zero live calls and no tracker at all**, proving the
checkpoint is now the actual source of truth.
