# OA-Q1 — Writer adoption decision

<!-- sourcebound:purpose -->
Status: **DECIDED. Adopted: claude-sonnet-5 (transport: claude_code, subscription).**
Owner ratified 2026-07-11.
<!-- sourcebound:end purpose -->

## Decision

`claude-sonnet-5` is the adopted Slot B writer for the quarter, over
`claude-haiku-4-5`. Both candidates cleared the pre-committed absolute
adoption bar (`gated_pass_rate >= 0.90`, `pass_k_rate >= 0.80`,
`contract_violation_rate == 0.0`) in the confirmatory R2 bake-off (PR
#136, `docs/R2_WRITER_BAKEOFF_RESULT_CONFIRMED.md`), so the decision is a
tie-break, not a gate failure on either side.

## Basis

- **Quality**: not discriminating. Haiku and Sonnet each cleared the bar
  in both R2 runs; which one scored marginally higher flipped between runs
  (tied 0.9825/0.9825 in the first run, Haiku ahead 0.9825/0.9532 in the
  confirmatory run) — consistent with ordinary judge/model run-to-run
  variance (neither transport pins temperature), not a stable quality gap
  in either direction.
- **Cost/latency, on the cleanest available signal**: output-token volume
  is measured identically in both arms (no caching artifact touches
  output tokens, only input). Haiku emitted 1,081,143 output tokens vs
  Sonnet's 157,254 (~6.9x) for the same 171 scenarios. Priced at each
  model's own output rate, Haiku's output alone costs ~$4.32 vs Sonnet's
  ~$1.57 — Haiku is more expensive per-task despite being the
  cheaper-per-token model, purely from verbosity.
- **Worst-case bound on the caching caveat**: Sonnet's measured
  `input_tokens` are artifactually low (prompt-caching hit consistently
  across its faster, more tightly-clustered calls — see
  `docs/R2_WRITER_BAKEOFF_RESULT_CONFIRMED.md`'s caveat). Even under the
  worst case — zero cache benefit, full fresh input on every Sonnet call
  (~400K tokens x $2/MTok =~ $0.80 additional) — Sonnet lands around
  $2.37 total, still meaningfully below Haiku's $4.65. The adoption
  direction survives the worst-case accounting.
- **Latency**: ~11.4s/call (Sonnet) vs ~51.9s/call (Haiku), ~4.6x —
  operationally material for a quarter running daily ticks.

## Self-preference disclosure

The judge model is `claude-sonnet-5`, and the adopted writer is also
`claude-sonnet-5` — a known same-model bias direction, disclosed per the
dispatch's own requirement. Weighed against it: in the confirmatory run,
Haiku scored HIGHER on quality (0.9825 vs Sonnet's 0.9532) — a judge
mechanically favoring its own sibling would not produce that result. The
adoption bar was designed as an absolute, per-arm bar specifically so
self-preference could not decide eligibility; it did not decide this
tie-break either, since quality was not the deciding factor (cost/latency
was).

## Rejected alternative, and why

**Building the cache-aware telemetry fix and running a third bake-off
before deciding** was considered and rejected as the wrong next step, not
as insufficiently rigorous. The direction (Sonnet cheaper) is already
bounded analytically above without a third run: the worst-case accounting
does not reverse it. A third ~4.5-hour live run would add a third,
independently-noisy quality data point (quality has already flipped once
across two runs) without providing new decision-relevant information — a
rerun that cannot change the outcome is delay dressed as rigor, not
rigor. The cache-telemetry fix remains queued (see W4 condition below),
just not gating this decision.

## Condition attached to this adoption

The cost/latency figures above, while sufficient to decide the tie-break,
are not exact — Sonnet's real cost is somewhere between $1.57 (floor) and
~$2.37 (worst case). **Before W4 (the quarter's cost architecture)
pre-registers a token/cost envelope, the cache-read telemetry gap should
be closed** (capture and price `cache_read_input_tokens`, per
`docs/R2_TELEMETRY_RESUME_FINDING.md`'s follow-up note) so the envelope is
built on a precise number, not a bounded range. This does not block Q4.

## Recorded per dispatch instruction

- Adopted `model_id`: `claude-sonnet-5`
- Transport: `claude_code` (subscription)
- Both arms' full results remain committed (PRs #133, #134, #136) — an
  honest comparison, not a beauty contest, regardless of this decision.
