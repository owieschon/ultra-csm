# R2 writer bake-off result — Haiku 4.5 vs Sonnet 5

<!-- clean-docs:purpose -->
Status: **Both arms clear the adoption bar. Quality is a near-tie. Cost/latency
telemetry is compromised for one arm and should NOT be used to break the
tie. STOP → OA-Q1: owner picks.**
<!-- clean-docs:end purpose -->

## Run

`ULTRA_CSM_LLM_TRANSPORT=claude_code python -m eval.writer_bakeoff --drop-pp
0.20 --pass-k 3 --checkpoint-dir .writer_bakeoff_checkpoints`, 57 scenarios
across 19 families (clean_baseline + all `gold_slot_b_hard` FAMILIES/
A6_EXPANSION_FAMILIES), MDD-sized at baseline_rate=0.80/drop_pp=0.20, k=3
pass^k, 342 total draws (171/arm). Full comparison in
`eval/gold/writer_bakeoff_report.json`.

Operational note: this run survived one infrastructure incident — the
background process was killed mid-run by the operator session's own
`/model` switching (unrelated to the harness or either candidate model);
relaunched fully detached (`nohup`+`disown`) from the last checkpoint with
zero data loss. Total wall clock ≈ 3h10m across the incident. A prior R2
attempt (before this run) aborted on draw 1 due to the writer path missing
the `resolve_timeout_s` wiring — fixed and merged as PR #131
(`docs/R2_WRITER_TIMEOUT_FINDING.md`); this run is the first clean one.

## Result

| | Haiku 4.5 | Sonnet 5 |
| --- | --- | --- |
| gated_pass_rate | 0.9825 | 0.9825 |
| pass_k_rate (k=3) | 0.9474 | 0.9649 |
| contract_violation_rate | 0.0 | 0.0 |
| **adopt_eligible** | **True** | **True** |

Per-dimension pass rate (both ≥0.98 on every one of the five gated
dimensions; `on_task_relevance` reported, not gated, per the scope guard):

| Dimension | Haiku | Sonnet |
| --- | --- | --- |
| account_specificity | 1.0 | 0.9825 |
| grounding_fidelity | 0.9825 | 1.0 |
| priority_fidelity | 1.0 | 1.0 |
| safety_boundary | 1.0 | 1.0 |
| tone_fit | 1.0 | 1.0 |
| on_task_relevance (reported) | 0.9825 | 1.0 |

**Both models pass comfortably and near-identically on quality.** Neither
arm produced a single contract violation across 171 live drafts each,
including the adversarial injection families (`A6S_*`, `A6C_*`).

## Cost/latency telemetry — flagged as unreliable, do not use to decide

| | Haiku 4.5 | Sonnet 5 |
| --- | --- | --- |
| total_calls recorded | 89 | 188 |
| total_tokens recorded | 594,618 | 163,457 |
| avg_latency_ms | 47,491 | 11,076 |
| total_cost_usd (estimate) | $1.84 | $1.63 |

This makes it LOOK like Sonnet was cheaper and faster than Haiku — the
opposite of the dispatch's own stated expectation ("expected outcome is
Haiku 4.5 given the formulaic drafting register"). **I do not trust this
comparison enough to report it as a finding, and here is exactly why,
verified against the code rather than assumed:**

- `total_calls` for Haiku (89) is LESS than its own `n_draws` (171) — that
  is only possible if a successful call is going unrecorded.
  `AnthropicReasonDraftWriter.write()` (`src/ultra_csm/agent1/slot_b.py`)
  calls `cost_tracker.record()` only when the transport response's
  `input_tokens` field is present (`if ... and in_tok is not None`). If a
  subset of `claude_code` CLI responses for Haiku returned usage-less JSON,
  those completed, successful calls are absent from telemetry —
  confirmed from the code path, not speculation. Sonnet's count (188 ≥ 171)
  is internally consistent with a few retries; Haiku's is not internally
  consistent at all.
- The ~7.7x tokens-per-recorded-call gap (Haiku ~6,681 vs Sonnet ~869)
  could be genuine verbosity, or an artifact of WHICH subset of Haiku's
  calls happened to have usable telemetry (a biased sample, not the full
  population). **I cannot disambiguate this from persisted data** — the
  harness does not capture raw draft text (by design, to keep the
  checkpoint artifact small), so there is no way to inspect actual Haiku
  output length after the fact without re-running with output capture,
  which I have not done unilaterally.

**What this means for OA-Q1:** the quality gates give no daylight between
the candidates — pick on cost/latency is exactly the tie-breaker the
dispatch anticipated, but the cost telemetry for this specific run cannot
be trusted to make that call. A cheap, real fix (a build-phase telemetry
gap fix, not a decision) would wire per-draw output-token capture properly
before a second confirmatory run — but that is a decision for a build
phase, not something to do mid-lane now.

## Self-preference disclosure (verbatim from the report)

The judge model is `claude-sonnet-5`, and the `sonnet` arm is
`claude-sonnet-5` scoring its own sibling's drafts — a known same-model
bias direction. `adopt_eligible` is computed per arm against an absolute
bar, not head-to-head, so it does not decide adoption by itself — disclosed
because the judge and one candidate share a model family, and Sonnet
scored fractionally higher on `pass_k_rate` and two of six dimensions.

## Recommendation (not a decision)

Both `adopt_eligible`. Quality: essentially tied, Sonnet very slightly
ahead on consistency (pass^k) and two dimensions, Haiku ahead on two others
— differences this small (one or two items out of 171) are not clearly
distinguishable from noise. Cost: unreliable, do not use. If a
tie-breaker is wanted before shipping the telemetry fix, the dispatch's
own default remains the operative one: cheapest model that clears the
absolute gates. **Recorded here, not decided: this is the owner's call.**
