# Security

<!-- clean-docs:purpose -->
Ultra CSM's security posture is enforced in code, tested in CI, and, where persistent state is involved, backed by database constraints or row-level security. The claim is not "no risk"; the claim is that the remaining risk is named and bounded.
<!-- clean-docs:end purpose -->

## Enforced Properties

| Property | Enforcement | Database backstop | Evidence |
| --- | --- | --- | --- |
| Tenant containment | Data-plane reads, sweep execution, API paths, and connector serving all carry tenant scope. | Persistent event/audit tables use tenant-scoped RLS. | `docs/PROGRAM_REPORT_58.md`, `tests/test_cross_tenant_rls.py` |
| Human approval for customer-facing actions | Customer outreach stays as a pending proposal until a human principal records a verdict. | Tier >=2 approvals reject agent-kind self-approval and bind verdicts to proposal payload hashes. | `docs/PROGRAM_REPORT_40.md`, `docs/PROGRAM_REPORT_60.md` |
| Consent gate | Draft outreach requires a consented contact and fails closed when consent is missing. | Proposal/verdict persistence preserves payload and consent references for audit. | `eval/scorecard_csm.json`, `tests/test_api.py` |
| Payload binding | `ActionGate` canonicalizes proposal payloads and stores/verifies SHA-256 bindings before verdict outcomes can authorize work. | Verdict rows carry the approved payload hash. | `docs/PROGRAM_REPORT_58.md`, `tests/test_action_gate_machine.py` |
| No authority minting | Platform session context creates proposals with explicit principal, tenant, cause, and clock context. | Governance checks prevent lower-authority principals from creating effective higher-authority approvals. | `docs/PROGRAM_REPORT_40.md` |
| Untrusted content handling | Hostile source text is treated as evidence data, not instruction. URI scheme guards reject unsafe draft links. | Customer-facing execution remains behind the same gate. | `docs/archive/PROGRAM_REPORT_61.md`, `docs/PROGRAM_REPORT_65.md` |
| Data handling | Logs scrub secrets, PII-shaped values, and customer content before JSON emission. Live ingestion is bounded by retention posture. | Persistent stores keep audit facts and hashes, not OAuth tokens or raw customer-content logs. | `docs/DATA_HANDLING.md`, `docs/PROGRAM_REPORT_54.md` |
| Operating monitor | Daily job, missed-run alarm, cost alarm, and Sentry envelope/check-in paths are implemented. | Durable operating and audit logs survive restart. | `docs/archive/PROGRAM_REPORT_59.md`, `docs/PROGRAM_REPORT_65.md` |

## Residual Risks

- **No real customer send yet.** Phase 10 stopped correctly at owner approval. The staged burner proposal is ready, but no `submit_verdict` approval or Gmail send has occurred.
- **No second blind labeler yet.** Judge validation is single-labeler and clearly marked that way.
- **No live Sentry ingestion proof yet.** Alarm and envelope behavior are tested with fake transports; no `SENTRY_DSN`/`SENTRY_AUTH_TOKEN` was found on disk.
- **No production customer outcome proof.** The repo proves mechanism, safety, and measurement discipline against connected dev/trial/burner orgs and fixtures. Retention or expansion lift requires a real customer deployment.
- **Local developer UI audit exposure.** `ui/` uses a static export for served paths. `next dev` is a local developer-only path and is not the served production path.

## Dependency And Scan Notes

The repository has two dependency surfaces: Python for the agent/API and npm for `ui/`.

The last documented Endor scan found no dependency, secret, or known-vulnerability findings, and reported SAST items that are dispositioned in `docs/archive/PROGRAM_REPORT_39.md`. The npm audit disposition for the static-export UI is also historical: advisories that require a running Next server do not apply to the served FastAPI static-file path.

CI continues to run the Endor security scan job. When Endor is not configured, the job records the skip explicitly rather than pretending a scan ran.

## Reporting A Vulnerability

Use GitHub private vulnerability reporting on this repository's Security tab. Do not file public issues containing exploit details, secrets, tenant identifiers, or customer content.
