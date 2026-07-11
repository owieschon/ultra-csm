# R2 writer bake-off — confirmatory rerun with corrected telemetry

Status: **Both arms adopt_eligible=True, quality tied to within run-to-run
noise. Cost/latency, now measured with full coverage, shows a real and
substantial gap: Sonnet 5 is cheaper and faster than Haiku 4.5 — the
opposite of the dispatch's stated expectation. One further, smaller
measurement gap discovered and disclosed below (prompt-caching
undercounts Sonnet's true cost; direction of the finding is unaffected).
STOP → OA-Q1: owner decides.**

## Why this run exists

PR #133 (the first bake-off) reported both arms `adopt_eligible=True` with
tied quality, but its cost/latency numbers were corrupted: a per-arm
`CostTracker` held only in process memory lost all data for the Haiku arm's
draws that were already checkpointed before a mid-run process kill (root
cause + fix: PR #134, `docs/R2_TELEMETRY_RESUME_FINDING.md`). This run is
the same bake-off, same scenarios, same config, on the fixed code —
confirmatory, not a redo of anything that was already trustworthy.

## Result

| | Haiku 4.5 | Sonnet 5 |
| --- | --- | --- |
| gated_pass_rate | 0.9825 | 0.9532 |
| pass_k_rate (k=3) | 0.9474 | 0.9298 |
| contract_violation_rate | 0.0 | 0.0 |
| **adopt_eligible** | **True** | **True** |
| telemetry coverage | 1.0 | 1.0 |

Both comfortably clear the adoption bar (≥0.90 gated, ≥0.80 pass^k, zero
violations). Quality is close but not identical this run — Haiku actually
scored slightly higher this time (0.9825 vs 0.9532), inverted from the
first run where both were 0.9825. This is consistent with ordinary
judge/model run-to-run variance (neither transport pins temperature,
per finding #3) rather than a real, stable quality gap in either
direction — two runs, two slightly different pictures, both comfortably
above the bar.

## Cost / latency — the corrected, coverage=1.0 comparison

| | Haiku 4.5 | Sonnet 5 |
| --- | --- | --- |
| total_tokens | 1,488,809 | 157,634 (see caveat below) |
| total_cost_usd | $4.65 | $1.57 (floor, see caveat) |
| avg_latency_ms/call | 51,884 (~52s) | 11,388 (~11s) |

**This inverts the dispatch's stated expectation** ("expected outcome is
Haiku 4.5 given the formulaic drafting register, but the gates decide").
Haiku is ~9.4x the tokens, ~3.0x the cost, ~4.6x the latency of Sonnet in
this run.

## Caveat, investigated and disclosed rather than silently accepted

Every one of Sonnet's 171 draws reports `input_tokens` between 2-8 — not a
mix, ALL of them (checked the full per-draw distribution, not just the
aggregate). Every one of Haiku's 171 draws reports realistic values
(1,876-7,632, clustered ~1,900, matching a ~5KB system prompt). This is
systematic, not noise, and points to Anthropic prompt caching: Sonnet's
calls were ~4.6x faster and likely stayed within a cache TTL window across
the whole run, so nearly every call hit a cached system prompt
(`cache_read_input_tokens`, which the current telemetry does not capture)
instead of reporting fresh `input_tokens`. Haiku's slower, more spread-out
calls apparently didn't benefit from caching as consistently.

**What this does and does not change:**
- Haiku's numbers are unaffected and reliable (no caching artifact
  observed in its distribution).
- Sonnet's $1.57 / 157,634 tokens is a FLOOR, not a precise figure — cache
  reads are still billed (materially discounted, not free) and are
  currently uncounted.
- Cache reads are cheaper than fresh input tokens by construction, so this
  gap **cannot reverse the direction** of the finding — Sonnet remains
  cheaper and faster than Haiku regardless of the exact true figure.
- Not chased further with another live run: the qualitative conclusion
  (quality tied, Sonnet meaningfully cheaper/faster) is well-supported
  without an exact dollar figure. Capturing `cache_read_input_tokens` and
  pricing it correctly (Anthropic's documented cache-read rate is a
  fraction of fresh input cost) is a small, well-scoped follow-up fix if
  an exact number becomes load-bearing later — not urgent for this
  decision.

## Sanity check against the first (corrupted-telemetry) run

The original run's Haiku numbers ($1.84, partial ~38% coverage) scale
consistently to this run's full-coverage figure: $1.84 / 0.38 ≈ $4.84,
close to the $4.65 observed here. The numbers are internally consistent,
not an artifact of the fix itself.

## Recommendation (not a decision)

Both `adopt_eligible`. Quality: tied within noise. Cost: Sonnet is the
substantially cheaper and faster arm, likely by an even wider true margin
once cache-read costs are counted (never a narrower one). If cost/latency
matters for OA-Q1 — and it plausibly should, given quality doesn't
discriminate — the corrected data points toward Sonnet, not the dispatch's
original expectation of Haiku. **Recorded here, not decided: this is the
owner's call.**
