# CI/CD

<!-- sourcebound:purpose -->
`.github/workflows/ci.yml` runs the offline-safe gates for this repo:
<!-- sourcebound:end purpose -->

| Job | Lane | What it does | Secrets |
| --- | --- | --- | --- |
| `eval` | offline proof | installs Ultra CSM, verifies the frozen Action Control contract and rollback-isolated sandbox contract, then runs eval, hygiene, scorecard, and regression gates | none |
| `ui-check` | interface contract | lints and builds the static UI, then exercises evidence, decision-control reachability, WCAG A/AA, and the synthetic Action Control flow at desktop and mobile viewports | none |
| `endor` | optional security | runs the Endor security lane only when `ENDOR_ENABLED=true` | `ENDOR_TOKEN`, `ENDOR_NAMESPACE` |

## Endor evidence states

Set the repository variable `ENDOR_ENABLED` to `true` only when both
`ENDOR_TOKEN` and `ENDOR_NAMESPACE` are configured. The selected job validates
that pair before checkout or scanning.

| Job state | Meaning |
| --- | --- |
| passed | The selected job completed its Endor scan successfully. |
| failed | The selected job failed, including an enabled job with incomplete configuration. |
| not configured | `ENDOR_ENABLED` is absent or not `true`, so GitHub selects no Endor job and no scan runs. |
| unverified | Local static checks prove the workflow structure, but no public GitHub Actions run has verified scheduler behavior. |

A skipped job is not a passed scan and is not a security result.

The offline proof is intentionally conservative: no cloud services, no customer
data, and no live vendor credentials. `make scorecard-csm` is the Agent 1
CSM-native deterministic scorecard; `make regression-csm` is the exact-spine plus
seeded distributional regression.

For current architecture and execution scope, read:

- `docs/ARCHITECTURE.md`
- `docs/DATA_PLANE.md`
- `docs/DECISION_LOG.md`
