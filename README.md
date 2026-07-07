# Ultra CSM

Ultra CSM is an agentic workspace for scaling the CSM function. It gives CSM
teams account briefs, prioritized work queues, sales-to-CS handoff context,
evidence-backed outreach drafts, internal Engineering/Product handoff packets,
and governed approval proposals. Underneath, agents read CRM, project, product,
telemetry, and comms evidence to identify onboarding stalls, retention risks,
expansion opportunities, outcome gaps, and product/engineering escalation
signals; customer-facing sends stay behind a human approval gate.

Start with the proof table below, then read [Honest Limits](docs/LIMITS.md) for
the boundary line: what is proven, what is scoped, and what is still unproven.

## What Is Proven

| Area | Current evidence | Boundary |
| --- | --- | --- |
| Deterministic spine | `make scorecard-csm-check` reports `Agent 1 CSM scorecard: 24/24 hard_ok=True` and confirms the scorecard/work-queue artifacts are current. The scorecard covers identity, evidence, consent, payload binding, unsafe drafts, tenant isolation, and the real gate path. | Offline and fixture-backed unless a row below says live. |
| Live connectors | Salesforce, Rocketlane, and Gmail burner scopes were exercised during the live program; the serving and ledger receipts are in `docs/PROGRAM_REPORT_58.md` and `docs/PROGRAM_REPORT_65.md`. | Connected dev/trial/burner orgs, not production customers. |
| Persistent operation | Phase 9 loaded `com.ultracsm.operating-daily`, ran through the scheduled path, and wrote durable audit rows. Layer 3 reported 3 file-ledger entries spanning 2026-07-05 to 2026-07-06 and 230 persistent DB audit rows. | Proves the operating mechanism and accumulated local ledger; not weeks of unattended production operation. |
| Customer-facing loop | Phase 10 staged one burner-scoped `draft_customer_outreach` proposal with payload hash `065c48c96d0cee6aab4896f0f3a9103e863393f2109dc4eea5df5dcd2af4c232`, then stopped. | The owner must approve with `submit_verdict`; the system did not approve or send. |
| Internal handoff | `eval/internal_bridge_validation_report.json` records one Engineering/Product handoff pair with `routing_core_hard_ok=true`, 18 cases, no routing failures, and zero confidently-wrong cells; `docs/PROGRAM_REPORT_68.md` records the single-oracle boundary. | Proves one spike-scoped handoff pair, not all internal-bridge archetypes. |
| Outcome integrity | VM-8 proof tests pass for a green/high-usage account that later churns: before close, outcome stays `not_instrumented`; after close, terminal renewal evidence becomes `known` with explicit won/lost direction. | Synthetic renewal opportunity evidence only; broader outcome instrumentation is still partial. |
| Judge scope | `tests/test_judge_validation.py` passes 21 tests. The full judge claim remains `validated=false`; five dimensions are scoped-gateable, and `on_task_relevance` is excluded by `assert_gating_dimensions(...)`. | Single-labeler gold set. No second blind human labeler yet. |
| Drift power | `make drift-power-csm` reports `hard_ok=True`; the expanded hard layer in `eval/drift_power_csm.json` records `n=64` and minimum detectable overall-pass-rate drop `0.089`. | Smaller drift needs more independent examples; this is quality-drift power, not production outcome drift. |
| Hosted read-only demo | `docs/PROGRAM_REPORT_67.md` records a static Vercel-ready demo backed by committed JSON fixtures in `ui/public/demo-api/`, with hosted write routes disabled. | Safe distribution surface only; not a live connector deployment. |
| Monitoring | Sentry envelope/check-in code and missed-run/cost alarms are tested with fake transports. | No live Sentry DSN/token was found, so live Sentry ingestion is not proven. |

## How It Works

One deterministic `CustomerDataPlane -> value_model -> ActionGate` spine sits under every lens.

- **Time-to-Value** finds onboarding and activation stalls.
- **Risk / Retention** finds steady-state fragility such as single-threading and renewal proximity.
- **Expansion** finds unrealized value in healthy accounts.
- **Cohort / Program** remains population-level roadmap work.

The LLM does not own health scoring, consent, authorization, payload binding, or tenant containment. It narrates evidence and drafts proposed actions. Every customer-facing action follows the same path: proposal -> human verdict -> committer.

## Run It Locally

Read-only conversational path, no database and no credentials:

```sh
git clone https://github.com/owieschon/ultra-csm.git && cd ultra-csm
python3 -m venv .venv && .venv/bin/pip install -q -e ".[mcp]"
claude mcp add ultra-csm --env ULTRA_CSM_MCP_READONLY=1 -- \
  "$(pwd)/.venv/bin/python" -m ultra_csm.mcp_server
```

Then ask: "Which accounts are most at risk, and what evidence says so?" Write tools return typed refusals in read-only mode.

Full local gates:

```sh
make setup
make doctor
make scorecard-csm
make eval
make lint hygiene
```

`make eval` uses an ephemeral Postgres cluster and tears it down. No cloud credentials or customer data are needed for the offline gates.

## Live And Credentialed Lanes

Credentialed lanes are intentionally separate from offline verification:

- Live connector reads/writes use explicit tenant-scoped credentials.
- Live judge runs spend model budget and write regenerated artifacts.
- Customer-facing sends are owner-gated and never self-approved.
- The Gmail live-send path is staged only for the burner allowlist until a human approves.

## Hosted Read-Only Demo

The optional hosted demo is static: Vercel builds `ui/out`, serves committed JSON fixtures from `ui/public/demo-api/`, and disables all approvals, edits, sends, and comms confirmations. It is a safe distribution surface for the fixture-backed operations UI, not a live connector deployment. See `docs/PROGRAM_REPORT_67.md`.

## Docs

- Start with `docs/README.md` for the curated docs map.
- The three live-build layer reports are `docs/PROGRAM_REPORT_54.md`, `docs/PROGRAM_REPORT_58.md`, and `docs/PROGRAM_REPORT_65.md`.
- The human-approval stop is `docs/PROGRAM_REPORT_60.md`.
- Security posture is in `SECURITY.md`.
- Historical process reports live under `docs/archive/`.

## Still Open

1. Owner approval for the staged Phase 10 burner send.
2. A second blind human labeler for inter-rater kappa.
3. A live Sentry DSN/token to prove real Sentry ingestion.
4. Broader outcome instrumentation beyond the synthetic terminal-renewal slice.
5. Real production customer deployment and retention outcomes.
