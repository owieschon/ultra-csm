# R0 finding #2 — claude_code transport failures aren't retried

Status: **R0 re-run (post PR #117) FAILED again, on a different item, for a
different reason. Auth is fixed. This is a retry-coverage gap.**

## What happened

`ULTRA_CSM_LLM_TRANSPORT=claude_code python -m eval.run_quality_judge --model
claude-sonnet-5` got through all 63 clean-layer items and 46/64 hard-layer
items (109/127 total) cleanly, then crashed on item 47 (hard, family
`A6S_security_commitment`, id `slot-b-gold-a92be98de078a890`) with:

```
subprocess.TimeoutExpired: Command '[...claude --safe-mode...]' timed out after 30.0 seconds
```

## Root cause

Two things compound:

1. `LIVE_TIMEOUT_S = 30.0` (`src/ultra_csm/agent1/slot_a.py:32`,
   `slot_b.py:40`) is shared across both transports. The `claude_code`
   transport (`src/ultra_csm/llm_transport.py`) shells out to the `claude`
   CLI as a subprocess — real process startup plus auth/session overhead on
   top of model latency, tighter than the budget the direct-API HTTP call
   was presumably tuned for.
2. `_retryable()` in `eval/run_quality_judge.py` only recognizes Anthropic
   SDK exception class names (`APIConnectionError`, `APITimeoutError`,
   `InternalServerError`, `OverloadedError`, `RateLimitError`) plus
   `ValueError`. `subprocess.TimeoutExpired` (what the `claude_code`
   transport actually raises on a slow call) is in neither set, so
   `_retryable()` returns `False` and the single slow call aborts the entire
   127-item run with zero retries, instead of the exponential backoff that
   `MAX_RETRIES = 5` was clearly meant to provide.

The failing item itself is an adversarial injection case (`untrusted_text_fragments`
present, family `A6S_security_commitment`) — plausibly slower to reason
through than average, but that's a latency observation, not the bug. The bug
is that transport-level operational failures (timeout, subprocess crash) from
the `claude_code` transport have no retry path at all.

## What I did not do

Per MP-R hard exception #2, no code/config edits. I did not re-run the full
127-item lane a third time blindly hoping to avoid the same item — that
would be probing for a lucky pass, not verifying fidelity, and R0's own
discipline is to stop and escalate rather than retry into a pass.

## Suggested direction (builder's call, not prescribing the fix)

Either widen `LIVE_TIMEOUT_S` for the `claude_code` transport specifically
(transport-aware timeout, not a single shared constant), or add
`subprocess.TimeoutExpired` / `subprocess.CalledProcessError` to
`_retryable()`'s recognized set (or both — a wider timeout reduces how often
retry is needed; retry coverage handles the residual tail).

## Impact

R0 is still not passed. Auth (finding #1, PR #117) is confirmed fixed —
109/127 items scored successfully through the real subscription transport
before this second, distinct failure. R1(real)/R2/R3/R4 remain gated.
