# Detected repository surface

<!-- clean-docs:purpose -->
Use this reference when deciding whether a detected Ultra CSM source locator has a direct reader claim or is only tracked by the repository catalog. It keeps catalog coverage distinct from source-specific documentation and exposes the current detected surface behind the clean-docs receipt.
<!-- clean-docs:end purpose -->

The catalog catches additions, removals, and replacements. It does not assert that every internal symbol needs a reader-facing explanation. `clean-docs verify` reports source-specific coverage as `bound` and the remaining catalog as `cataloged`.

<!-- clean-docs:begin repository-surface -->
| surface | discovered | examples |
| --- | ---: | --- |
| api-symbol | 1555 | `APIMetrics`, `ARRChange`, `AccountAttributionCandidate`, and 1552 more |
| cli-command | 20 | `alarms`, `approve`, `check-in`, and 17 more |
| cli-option | 261 | `--a6-expansion`, `--account`, `--account-slug`, and 258 more |
| mcp-tool | 18 | `confirm_book`, `confirm_book_mappings`, `get_account_brief`, and 15 more |
| package | 2 | `ultra-csm`, `ultra-csm-ops-surface` |
| package-script | 5 | `build`, `build:e2e`, `dev`, and 2 more |
| runtime-constraint | 1 | `Python >=3.10` |
| schema | 3 | `ActionControlSandboxSession`, `ActionControlVerticalSlice`, `vercel` |
| test-runner | 1 | `test:e2e` |
| test-suite | 143 | `tests/test_account_brief_comms.py`, `tests/test_action_control_contract.py`, `tests/test_action_control_sandbox.py`, and 140 more |

<!-- clean-docs:inventory-sha256 b8c782dde2179f954021b75ca6a27a8af7a0c98e0488fc616a92bf05e4b1fda8 -->
<!-- clean-docs:end repository-surface -->
