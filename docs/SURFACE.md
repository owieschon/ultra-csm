# Detected repository surface

<!-- sourcebound:purpose -->
Use this reference when deciding whether a detected Ultra CSM source locator has a direct reader claim or is only tracked by the repository catalog. It keeps catalog coverage distinct from source-specific documentation and exposes the current detected surface behind the Sourcebound receipt.
<!-- sourcebound:end purpose -->

The catalog catches additions, removals, and replacements. It does not assert that every internal symbol needs a reader-facing explanation. `sourcebound verify` reports source-specific coverage as `bound` and the remaining catalog as `cataloged`.

<!-- sourcebound:begin repository-surface -->
| surface | discovered | examples |
| --- | ---: | --- |
| api-symbol | 1559 | `APIMetrics`, `ARRChange`, `AccountAttributionCandidate`, and 1556 more |
| cli-command | 20 | `alarms`, `approve`, `check-in`, and 17 more |
| cli-option | 262 | `--a6-expansion`, `--account`, `--account-slug`, and 259 more |
| make-target | 107 | `action-control-contract`, `action-control-contract-check`, `action-control-sandbox-check`, and 104 more |
| mcp-tool | 18 | `confirm_book`, `confirm_book_mappings`, `get_account_brief`, and 15 more |
| package | 2 | `ultra-csm`, `ultra-csm-ops-surface` |
| package-script | 5 | `build`, `build:e2e`, `dev`, and 2 more |
| runtime-constraint | 1 | `Python >=3.10` |
| schema | 3 | `ActionControlSandboxSession`, `ActionControlVerticalSlice`, `vercel` |
| test-runner | 1 | `test:e2e` |
| test-suite | 146 | `tests/test_account_brief_comms.py`, `tests/test_action_control_contract.py`, `tests/test_action_control_sandbox.py`, and 143 more |

<!-- sourcebound:inventory-sha256 0161762a847a94e66976da567e78c94c35afb0adc946de96a45cd7c174fdcf52 -->
<!-- sourcebound:end repository-surface -->
