# Security

Use this page to identify Ultra CSM's enforced trust boundaries, their executable
evidence, and the risks that remain outside those boundaries.

Controls are enforced in code, tested in CI, and, where persistent state is involved,
backed by database constraints or row-level security. This is not a claim of zero risk.

## Enforced Properties

| Property | Enforcement | Database backstop | Evidence |
| --- | --- | --- | --- |
| Tenant containment | Data-plane reads, sweep execution, API paths, and connector serving carry tenant scope. | Persistent tenant tables use forced row-level security for the runtime role. | `migrations/0002_rls.sql`, `tests/test_cross_tenant_rls.py` |
| Configured approval identity | Customer outreach stays pending until a bearer token maps to a principal stored as human-kind and distinct from the proposing actor. The software does not establish who holds the token. | Tier 2 and higher approvals reject agent-kind and proposing-actor principals, then bind verdicts to proposal payload hashes. | `src/ultra_csm/_api_helpers.py`, `src/ultra_csm/governance/gate.py`, `tests/test_action_gate_machine.py` |
| Consent gate | Customer outreach requires a consented contact and fails closed when consent is absent. | A database trigger independently checks the proposal's contact and account references. | `migrations/0009_safety_backstops.sql`, `tests/test_action_gate_machine.py`, `tests/test_api.py` |
| Payload binding | `ActionGate` canonicalizes proposal payloads and verifies SHA-256 bindings before a committer may execute. | Proposal and verdict triggers require the current payload and approved hash to agree. | `migrations/0009_safety_backstops.sql`, `migrations/0011_action_gate_integrity.sql`, `tests/test_action_gate_machine.py` |
| No authority minting | Proposals carry principal, tenant, cause, and clock context; permissions are looked up from role grants. | Token mapping, stored principal kind, required permission, and current verdict remain code and database checks rather than model output. | `src/ultra_csm/governance/authorizer.py`, `src/ultra_csm/governance/gate.py` |
| Untrusted content handling | Source text remains evidence data; URI guards reject unsafe draft links. | Customer-facing execution remains behind consent, verdict, and payload-binding checks. | `tests/test_agent1_slot_b.py`, `tests/test_action_gate_machine.py` |
| Data handling | Structured logs scrub secrets, email addresses, and customer-content fields. | Persistent stores keep governed evidence and audit records; secrets remain environment inputs. | [`docs/DATA_HANDLING.md`](docs/DATA_HANDLING.md), `tests/test_logging_config.py` |
| Operating monitor | Daily-run, missed-run, cost-alarm, and Sentry envelope paths are implemented. | Monitor tests use fake transports; a live receipt requires operator configuration. | `src/ultra_csm/operating_monitor.py`, `tests/test_operating_monitor.py` |

## Residual Risks

- **No production customer-send receipt.** Bounded Gmail and Salesforce committers exist,
  but the repository includes no receipt for an approved production customer send.
- **Approval identity is a configured trust anchor.** `ULTRA_CSM_API_TOKENS` maps bearer
  tokens to display names and human-kind principals; the software cannot prove that a
  person holds a token. Local `ULTRA_CSM_DEMO_NOAUTH=1` mints a labeled stand-in and is
  restricted to a loopback bind.
- **No second blind labeler yet.** Judge validation is single-labeler and clearly marked that way.
- **No live Sentry ingestion receipt.** Alarm and envelope behavior are tested with fake
  transports. A live check-in requires an operator-supplied `SENTRY_DSN`.
- **No production customer outcome proof.** Tests and scoped connector receipts cover
  mechanism and refusal behavior. Retention or expansion lift requires a real customer
  deployment.
- **Local developer UI audit exposure.** `ui/` uses a static export for served paths. `next dev` is a local developer-only path and is not the served production path.

## Dependency And Scan Notes

The repository has two dependency surfaces: Python for the agent/API and npm for `ui/`.

CI defines an Endor dependency, secret, and SAST scan when `ENDOR_TOKEN` is configured.
The result of that workflow run is the current receipt. Without the token, CI emits an
explicit skip notice and makes no scan claim. Run `make security-scan` locally for the
repository-history secret gate.

## Reporting A Vulnerability

Use GitHub private vulnerability reporting on this repository's Security tab. Do not file public issues containing exploit details, secrets, tenant identifiers, or customer content.
