# CI/CD

`.github/workflows/ci.yml` runs the offline-safe gates for this repo:

| Job | Lane | What it does | Secrets |
| --- | --- | --- | --- |
| `eval` | offline proof | installs Ultra CSM, then runs `make eval`, `make hygiene`, `make scorecard-csm`, and `make regression-csm` | none |
| `endor` | optional security | runs the Endor security lane when configured | `ENDOR_TOKEN` |

The offline proof is intentionally conservative: no cloud services, no customer
data, and no live vendor credentials. `make scorecard-csm` is the Agent 1
CSM-native deterministic scorecard; `make regression-csm` is the exact-spine plus
seeded distributional regression.

For current architecture and execution scope, read:

- `docs/ARCHITECTURE.md`
- `docs/DATA_PLANE.md`
- `docs/DECISION_LOG.md`
