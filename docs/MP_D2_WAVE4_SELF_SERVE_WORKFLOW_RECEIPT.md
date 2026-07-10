# MP-D2 Wave 4 Self-Serve Workflow Receipt

## Scope

OA-D3 owner decision: prove `self_serve_activation`.

Promoted:

- `workflow_core.py` as an execution-envelope invariant harness
- `workflow_playbooks.py` as the workflow contract registry
- `self_serve_activation.py` as the one proven vertical
- `self_serve_activation_store.py` on a generic `workflow_packet` table
- `/integrations/self-serve/signup` trigger route
- `/self-serve/activation/packets` read routes
- `/workflow-playbooks` registry route
- `eval.self_serve_workflow_eval` deterministic eval

Deferred/dormant:

- `enterprise_closed_won_onboarding`
- `account_adoption_regression`

They remain in the registry as `validation_status="dormant_unvalidated"`.
They are not shipped as validated and are not executed by this wave.

## Survey

The workflow layer consumes existing organs rather than replacing them:

- identity is explicit: `exactly_one`, `ambiguous`, or `none`
- evidence is source-backed through data-plane connectors and receipts
- decisions carry source ids and limitations in `WorkflowDecisionTrace`
- customer-affecting outputs remain behind `ActionGate`
- internal recommendations use existing `recommend_next_best_action`
- customer outreach proposals use existing `draft_customer_outreach`
- idempotency is explicit in the envelope and packet persistence
- UI/API registry exposes validation status instead of implying all workflows
  are equally proven

The promoted layer is an invariant envelope, not a second motion/value model.

## Deterministic Oracle

`make self-serve-workflow-eval` proves six non-contested behavior scenarios:

- team workspace reaches first value only when the configured first-value
  milestone completes
- completed-step count does not imply first value
- CRM interest in self-serve becomes sales-assisted enterprise interest, not a
  self-serve CRM connection action
- missing telemetry abstains and blocks activation judgment
- personal email domains suppress organization outreach
- all available sources are reviewed when present: telemetry, entitlement,
  adoption, customer email, call transcript, internal note, contact, and
  resolved organization

## Gates

- `python3 -m compileall -q src/ultra_csm/workflow_core.py src/ultra_csm/workflow_playbooks.py src/ultra_csm/self_serve_activation.py src/ultra_csm/self_serve_activation_store.py eval/self_serve_workflow_eval.py`
  -> `compile_ok`
- `python3 -m pytest tests/test_workflow_core.py tests/test_workflow_playbooks.py tests/test_self_serve_activation_workflow.py tests/test_work_packet_eval.py tests/test_work_packets.py -q`
  -> `30 passed`
- `python3 -m ruff check src eval tests scripts`
  -> `All checks passed!`
- `make PYTHON=python3 work-packet-eval`
  -> `packet_count: 6`, `findings: []`, `passed: true`
- `make PYTHON=python3 self-serve-workflow-eval`
  -> `scenario_count: 6`, `passed: true`
- `make PYTHON=python3 eval`
  -> `861 passed, 1 skipped`; Slot B gold status files current

Generated drift from `eval/mcp_operator_transcript.json` was restored and is
not part of this wave.
