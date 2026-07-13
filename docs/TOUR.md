# Ultra CSM Tour

<!-- clean-docs:purpose -->
This tour follows the current proof shape: local read-only use first, then the live-build receipts that show what has been wired and run.
<!-- clean-docs:end purpose -->

## 1. Ask The Book

```sh
python3 -m venv .venv
.venv/bin/pip install -q -e ".[mcp]"
claude mcp add ultra-csm --env ULTRA_CSM_MCP_READONLY=1 -- \
  "$(pwd)/.venv/bin/python" -m ultra_csm.mcp_server
```

Ask which accounts are most at risk, which accounts are ready for expansion, or why a proposal is held. Read-only mode never writes proposals, never sends email, and returns typed refusals for write tools.

## 2. Run The Local Gates

```sh
make setup
make doctor
make scorecard-csm
make eval
make lint hygiene
```

These prove the deterministic spine and test suite without cloud credentials or customer data. `make eval` boots an ephemeral Postgres cluster, applies migrations, runs the suite, and tears the cluster down.

## 3. Read The Live-Build Receipts

| Receipt | What It Proves |
| --- | --- |
| `docs/PROGRAM_REPORT_54.md` | Layer 1: judge validation fixed, UI dead ends closed, data handling posture added. |
| `docs/PROGRAM_REPORT_58.md` | Layer 2: persistent state, live serving, audit ledger, re-observation seam, and lens chips wired. |
| `docs/PROGRAM_REPORT_65.md` | Layer 3: daily job loaded, durable ledger accumulating, live adversarial drill, Sonnet 5 judge migration, drift-power scope, and clean Phase 14 skip. |
| `docs/PROGRAM_REPORT_60.md` | Human approval stop: a burner outreach proposal is staged, but owner approval is required before any send. |
| `docs/PROGRAM_REPORT.md` | Hollow-number correction: relay mapping now prefers loud unknowns over fabricated records. |
| `docs/PROGRAM_REPORT_40.md` | Governance hardening: agent-kind self-approval cannot authorize tier >=2 customer-facing work. |

Historical process reports live in `docs/archive/`.

## 4. Understand The Boundaries

- Connected live orgs are the Salesforce dev org, Rocketlane trial, and Gmail burner account.
- The staged Phase 10 proposal has not been approved or sent.
- The judge is validated against a single-labeler gold set; no second labeler has been supplied.
- Sentry alarm payloads are tested, but live Sentry ingestion is still waiting on a configured DSN/token.
- No claim is made about production-customer retention or expansion lift.
