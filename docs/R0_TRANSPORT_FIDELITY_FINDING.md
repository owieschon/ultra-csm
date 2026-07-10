# R0 Finding — claude_code transport cannot authenticate (--bare forces API-key auth)

Status: **R0 FAILED on item 1/63. Lane stopped per MP-R hard exception #1. Not a
kappa/fidelity mismatch — the transport crashes before producing a single score.**

## Root cause

`src/ultra_csm/llm_transport.py:141` passes `--bare` to the `claude` CLI invocation.
Per `claude --help`, `--bare` states explicitly:

> Anthropic auth is strictly ANTHROPIC_API_KEY or apiKeyHelper via --settings
> (OAuth and keychain are never read).

The whole point of the `claude_code` transport is subscription/OAuth auth — MP-R's
own credential posture is "I never read, print, or export ANTHROPIC_API_KEY; I
never switch a lane to the metered API." No API key is set in the operator's
environment by design. `--bare` and subscription auth are mutually exclusive; the
adapter currently asks for both at once.

## Reproduction

```
$ claude --bare --print --output-format json --permission-mode dontAsk \
    --model claude-sonnet-5 --system-prompt "You are a test." "say hi"
{"type":"result","subtype":"success","is_error":true,...,"result":"Not logged in · Please run /login",...}

$ claude --print --output-format json --permission-mode dontAsk \
    --model claude-sonnet-5 --system-prompt "You are a test." "say hi"
{"type":"result","subtype":"success","is_error":false,...,"result":"Hi! 👋 What are we working on today?",...}
```

Same flags, only `--bare` removed: first call fails auth, second succeeds via the
session's own subscription login. This isolates `--bare` as the sole cause.

Full crash from the actual R0 run (`eval.run_quality_judge --model claude-sonnet-5`,
`ULTRA_CSM_LLM_TRANSPORT=claude_code`): `subprocess.CalledProcessError` on the very
first gold item (`slot-b-gold-66ffdc63c9bc7bfe`), raised from
`llm_transport.py:156` inside `LlmTransport.complete`.

## Impact

- R0 cannot pass until this is fixed. R0 gates every other MP-R lane (R1 real /
  R2 / R3 / R4 all depend on the transport). None of them can run.
- The deterministic, non-LLM lanes are unaffected (no transport dependency):
  runbook R1 (`make world`), runbook R3 (knowability auditor challenge), and
  MP-R's own R1 (degenerate-baseline reproduction) can still proceed and are
  covered separately in this PR.

## What I did not do

Per MP-R hard exception #2, I did not edit `llm_transport.py`. This finding is
diagnosis only. The fix (likely: drop `--bare`, or gate it behind an explicit
`ANTHROPIC_API_KEY`-present check, and re-derive what `--bare`'s other benefits
— skip hooks/LSP/plugin-sync/CLAUDE.md discovery — were meant to buy without also
losing OAuth) is the builder's call.
