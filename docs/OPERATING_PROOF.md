# Operating Proof

Date: 2026-07-02.

## Claim Boundary

This note proves local operation against the synthetic/simulated tenant only. It does not
prove live-tenant behavior, external writes, or semantic-quality judge validation. The
judge gate is a separate active lane and was not run here.

## Core Gates

Command:

```bash
bash run_verification.sh
```

Observed result: tests, CSM scorecard, CSM regression, lint, and hygiene completed green.
The script skipped the credentialed judge lane by default.

## Operating Surface

Commands executed:

```bash
PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli demo-book --json
PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli demo-sweep --day 60 --deep --json
PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli demo-timeline --deep --json
make demo-loop
```

Observed result: the CLI produced a synthetic book, a deep simulated sweep, timeline
output, and the demo loop artifact at `eval/demo_loop_csm.json`.

MCP tool functions were exercised directly in fixture mode:

```bash
list_accounts
score_account
get_account_brief
run_sweep
list_proposals
submit_verdict
```

Observed result: each tool returned structured computed data or a structured expected
error for the missing-proposal verdict path.

REST API was booted with:

```bash
PYTHONPATH=src:. .venv/bin/python -m uvicorn ultra_csm.api:app --host 127.0.0.1 --port 8017
```

Endpoints exercised:

```bash
GET /health
GET /accounts?day=60&deep=true
GET /accounts/{account_id}/brief?day=60&deep=true
POST /sweep?day=60&deep=true
GET /metrics
```

Observed result: the API returned health state, scored accounts, an account brief with
trajectory data, a sweep result, and metrics including request counts, latency
percentiles, sweep timing, LLM cost totals, and budget state.

## Degradation Ladder

`make demo-loop` exercised the Slot B fallback and the quality circuit breaker. The
artifact carries `claim_boundary.loop_closed_sim=true`, `loop_closed_live=false`,
`degradation_flagged=true`, and `quality_breaker_exercised=true`.

The scorecard includes the loudness gate for fallback behavior, and the red-path test for
unflagged fallback is part of the green core gate above.

## Open Drift

`eval/deep_vs_shallow_detection.json` currently lacks a `claim_boundary`. Because eval
JSON must be generated rather than hand-edited, that drift remains open until the artifact
has a reproducible generation or refresh path.
