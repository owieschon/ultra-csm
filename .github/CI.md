# CI/CD

<!-- sourcebound:purpose -->
`.github/workflows/ci.yml` runs the offline-safe gates for this repo:
<!-- sourcebound:end purpose -->

| Job | Lane | What it does | Secrets |
| --- | --- | --- | --- |
| `eval` | offline proof | installs Ultra CSM, verifies the frozen Action Control contract and rollback-isolated sandbox contract, then runs eval, hygiene, scorecard, and regression gates | none |
| `ui-check` | reviewer journey | lints and builds the static UI, then exercises Evidence, decision-control reachability, WCAG A/AA, and the synthetic Action Control flow at desktop and mobile viewports | none |
| `endor` | optional security | runs the Endor security lane when configured | `ENDOR_TOKEN` |

The offline proof is intentionally conservative: no cloud services, no customer
data, and no live vendor credentials. `make scorecard-csm` is the Agent 1
CSM-native deterministic scorecard; `make regression-csm` is the exact-spine plus
seeded distributional regression.

For current architecture and execution scope, read:

- `docs/ARCHITECTURE.md`
- `docs/DATA_PLANE.md`
- `docs/DECISION_LOG.md`
