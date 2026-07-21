# R2 finding #1 — writer transport still used the flat 30s timeout

<!-- sourcebound:purpose -->
Status: **R2's first live run aborted on draw 1/171. Lane stopped per
dual-role discipline; this build-phase fix reuses the Q1 seam. No mid-lane
edits were made.**
<!-- sourcebound:end purpose -->

## What happened

`ULTRA_CSM_LLM_TRANSPORT=claude_code python -m eval.writer_bakeoff
--drop-pp 0.20 --pass-k 3` failed on the very first draw
(`bakeoff-A6C_injection_ignored_control-00`, Haiku 4.5 arm) with
`subprocess.TimeoutExpired ... timed out after 30.0 seconds`, five
consecutive times (the harness's retry ceiling), across two outer
auto-resume attempts. Zero draws completed.

## Root cause

PR #122 (finding #2's fix) made the live timeout transport-aware via
`resolve_timeout_s()` — 120s default for the `claude_code` CLI transport —
but wired it into the JUDGE path only (`eval/judge_anthropic.py`). Its own
PR body flagged the gap: "Did not touch slot_a.py/slot_b.py's own
live-generation transport calls, which share the same LIVE_TIMEOUT_S
pattern but aren't exercised by R0." R2 is the first lane to exercise the
WRITER path (`AnthropicReasonDraftWriter`, `src/ultra_csm/agent1/slot_b.py`),
which still passed the flat `LIVE_TIMEOUT_S = 30.0` straight to
`resolve_message_transport`. The Slot B system prompt is ~5KB and the CLI
adds process startup and auth overhead per call; 30s is not enough headroom
on this path either — exactly finding #2's mechanics, one seam over.

`ULTRA_CSM_LLM_TIMEOUT_S` could not serve as an operator-side workaround:
the writer path never consulted `resolve_timeout_s()`, so the env override
was dead there too — which is why this is a build defect, not an
operational misconfiguration.

## Fix (this PR)

`slot_a.py` and `slot_b.py` transport construction now call
`resolve_timeout_s(LIVE_TIMEOUT_S)`, identical to the judge path. No other
behavior change; injected-transport tests are unaffected (the resolver runs
only when no transport is supplied). Regression tests assert both writer
classes resolve 120s under `claude_code` and honor the env override.

## Impact

R2 re-runs from scratch after this merges (zero completed draws existed, so
nothing is discarded). No results were produced by the aborted lane; no
artifact was committed from it.
