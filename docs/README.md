# Ultra CSM documentation

Use this index to reach the current task or reference page without treating program
reports, execution handoffs, or generated receipts as operating guidance.

## Start by task

| What you need | Canonical page |
| --- | --- |
| Understand the product and its proof boundary | [`../README.md`](../README.md) |
| Install and run the fixture-backed system | [`../QUICKSTART.md`](../QUICKSTART.md) |
| Follow the local or hosted operations UI | [`DEMO.md`](DEMO.md) |
| Move from the UI through code and negative tests | [`TOUR.md`](TOUR.md) |
| Trace evidence through authorization and receipt | [`READING_PATH.md`](READING_PATH.md) |
| Choose MCP access and data boundaries | [`MCP_MODES.md`](MCP_MODES.md) |
| Explore and confirm connector mappings | [`CONNECTORS.md`](CONNECTORS.md) |
| Check unsupported or unproven behavior | [`LIMITS.md`](LIMITS.md) |
| Inspect security controls and residual risks | [`../SECURITY.md`](../SECURITY.md) |

## System references

| Subject | Canonical page |
| --- | --- |
| Runtime components and hard boundaries | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Customer value model | [`CUSTOMER_VALUE_MODEL.md`](CUSTOMER_VALUE_MODEL.md) |
| Source contracts and evidence references | [`DATA_PLANE.md`](DATA_PLANE.md) |
| Stored data, retention, and log scrubbing | [`DATA_HANDLING.md`](DATA_HANDLING.md) |
| Observability ports and local failure modes | [`OBSERVABILITY.md`](OBSERVABILITY.md) |
| Credentialed and metered maintainer commands | [`OPERATOR_RUNBOOK.md`](OPERATOR_RUNBOOK.md) |

## Executable proof

| Claim | Primary receipt |
| --- | --- |
| The deterministic scorecard is current | `make scorecard-csm-check` and `eval/scorecard_csm.json` |
| Configured-identity separation and payload-binding attacks fail closed | `tests/test_action_gate_machine.py` |
| Cross-tenant database reads are contained | `tests/test_cross_tenant_rls.py` |
| The hosted fixture exports no write routes | `tests/test_hosted_readonly_demo.py` |
| The full offline suite passes | `make eval` |

## Process and historical material

Program reports, execution handoffs, completed labeling instructions, evaluation
findings, and retired design specs record how work was produced or evaluated. They are
not current setup, operations, or architecture contracts. Use the dated records under
[`archive/`](archive/) only to investigate provenance for a specific claim.
