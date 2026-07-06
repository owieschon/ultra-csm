# Ultra CSM

Ultra CSM is a customer-success decision engine: it reads CRM, project, product, and comms evidence; scores customer value deterministically; and drafts CSM actions that stay behind a human approval gate.

It now runs against connected live orgs on persistent state, with Risk and Expansion lenses wired into the same daily loop as Time-to-Value. It does not claim production-customer retention lift, a real customer send, or second-human judge agreement.

## What Is Proven

| Area | Current evidence | Boundary |
| --- | --- | --- |
| Deterministic spine | `make scorecard-csm` renders `eval/scorecard_csm.json` with `hard_ok=true`, 24/24 hard gates passing. Tenant isolation, consent, payload binding, and no-authority-minting are tested against the real gate path. | Offline and fixture-backed unless a row below says live. |
| Live connectors | Salesforce, Rocketlane, and Gmail burner scopes are wired for the live program; earlier live connector receipts are in `docs/LIVE_INTEGRATION_FINDINGS.md`, with the full live-build serving story in `docs/PROGRAM_REPORT_58.md` and `docs/PROGRAM_REPORT_65.md`. | Connected dev/trial/burner orgs, not production customers. |
| Persistent operation | Phase 9 loaded `com.ultracsm.operating-daily`, ran through the scheduled path, and wrote durable audit rows. Layer 3 reported 3 file-ledger entries spanning 2026-07-05 to 2026-07-06 and 230 persistent DB audit rows. | Proves the operating mechanism and accumulated local ledger; not weeks of unattended production operation. |
| Customer-facing loop | Phase 10 staged one burner-scoped `draft_customer_outreach` proposal with payload hash `065c48c96d0cee6aab4896f0f3a9103e863393f2109dc4eea5df5dcd2af4c232`, then stopped. | The owner must approve with `submit_verdict`; the system did not approve or send. |
| Safety under live adversarial input | Phase 11 seeded one hostile burner email, ran ingestion and drafting, and captured `hard_ok=true`; the draft ignored the injected instruction and no approval/send occurred. | Burner mailbox only. |
| Judge quality | The gate judge is Sonnet 5 after a paired migration screen returned `adopt=true`; validation derives `validated=true` from artifacts, not hand-written prose. | Single-labeler gold set. No second blind labeler yet. |
| Drift power | `eval/drift_power_csm.json` has `hard_ok=true`, catches all eight bad variants, and scopes the current minimum detectable overall-pass-rate drop to about 46.9 percentage points. | Smaller drift needs more independent examples. |
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

- Fixture mode is the default. Live data-plane reads require explicitly setting `ULTRA_CSM_DATA_PLANE_MODE=live` with the relevant tenant-scoped connector credentials.
- Persistent application state requires `ULTRA_CSM_DATABASE_URL`. Without it, local gates use fixture data and ephemeral Postgres harnesses such as `make eval`.
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
4. Real production customer deployment and retention outcomes.
