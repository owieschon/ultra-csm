# Ultra CSM

Ultra CSM is an eval-first customer-success agent proof. The repo is focused on
one spine: `CustomerDataPlane -> value_model -> ActionGate -> Agent 1 Slot B`.

The current agent is a Time-to-Value accelerator. It reads deterministic CRM,
CS-platform, and product-telemetry fixtures, computes a customer value model,
projects a TTV priority lens, and emits only gated CSM action proposals.

Two things are evaluated separately, and keeping them apart is the point: the
**deterministic spine** (exact, offline, zero-tolerance regression) and the
**non-deterministic LLM slot** (a quality judge whose run-to-run noise is measured
before it is trusted).

## Verified state — deterministic spine

- `make scorecard-csm` writes `eval/scorecard_csm.json`. Current: `23/23`, hard gates green.
- `make regression-csm` compares the deterministic Agent 1 spine against
  `eval/baseline_csm.json` and writes `eval/regression_csm.json`.
- `make eval` runs the CSM pytest suite.
- `make hygiene` scans active CSM surfaces for repo residue.

## Quality eval — the non-deterministic LLM slot

Slot B's `reason`/`customer_draft` output is graded by an LLM quality judge across six
dimensions (grounding, on-task relevance, account specificity, priority fidelity, tone,
safety). The harness treats the judge as a measurement instrument and characterizes it
before trusting it:

- **Blinded gold sets** — a clean corpus plus an adversarial *hard* layer of trap
  families (fluent-but-wrong, soft-injection-comply, wrong-register, boundary cases),
  with the answer key held out under opaque ids.
- **Non-determinism is measured, not assumed** — `eval/determinism_probe.py` runs each
  case N times and reports the judge's own gate-repeatability and per-dimension noise.
- **N-run aggregation** (`eval/judge_nrun.py`) — fail-closed on safety, majority vote on
  the rest, with genuinely indeterminate cases surfaced rather than hidden.
- **Model and prompt are chosen from evidence**, recorded in `docs/DECISION_LOG.md`.

These lanes are credential-gated (need `ANTHROPIC_API_KEY`) and are not in CI:
`make judge-agreement-csm` and `make quality-regression-csm`. The judge's noise floor is
measured and the gate is stabilized by N-run aggregation; human validation against a blind
second labeler is the next milestone (see `docs/DECISION_LOG.md`) — deliberately not claimed
until earned.

## Setup

Prerequisites:

- Python 3.10 or newer.
- PostgreSQL 16 local tooling: `initdb` and `pg_ctl`.

```sh
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"

make hygiene
make scorecard-csm
make regression-csm
make eval
```

The default proof is offline and credential-free. `make regression-csm-live` is
credential-gated and exists only for live Slot B drift capture.

## Active Docs

- `docs/ARCHITECTURE.md`
- `docs/CUSTOMER_VALUE_MODEL.md`
- `docs/DATA_PLANE.md`
- `docs/DECISION_LOG.md`
- `docs/QUALITY_REGRESSION_EVAL_SPEC.md`
- `docs/NONDETERMINISM_EVAL_HARDENING_SPEC.md`
- `docs/QUALITY_LABELING_PROTOCOL.md`
- `docs/OBSERVABILITY.md`
- `docs/SECURITY.md`
- `docs/ROCKETLANE_ONBOARDING_CONNECTOR_SPEC.md`
- `docs/NEXT_DISPATCH.md`
- `docs/prompts/agent1_slot_b_reason_draft_v1.md`
