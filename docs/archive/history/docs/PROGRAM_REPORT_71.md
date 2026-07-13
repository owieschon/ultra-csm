# Program Report 71 - Public Front Door Curation

MP-C refreshed the public front door into a current, honest description of what
Ultra CSM is: an agentic workspace for scaling CSM work, not a dashboard. The
README now leads with the owner-ratified capability statement, every proof-table
claim is tied to a fresh command or committed artifact, the known limits are
centralized in one doc, and the reviewer demo path walks the real hosted
read-only operations surface.

## What Changed

| Area | Change |
| --- | --- |
| README lead | Replaced generic positioning with the owner-ratified agentic-workspace description: account briefs, prioritized queues, sales-to-CS context, evidence-backed drafts, internal handoff packets, and governed approval proposals. |
| Proof table | Corrected stale judge and drift rows; added current rows for internal handoff, VM-8 outcome integrity, judge scope, and hosted read-only demo. |
| Honest limits | Added `docs/LIMITS.md` as the plain boundary line for synthetic data, scoped judge validation, outcome instrumentation, internal handoff scope, no production send, and monitoring. |
| Demo path | Rewrote `docs/DEMO.md` as a 90-second reviewer walkthrough of the hosted read-only operations surface. |
| Hosted demo UI | Fixed read-only fixture mode so `POST /sweep?day=140` resolves to the static sweep fixture instead of returning 405. |
| Internal handoff visibility | Added a Queue detail card that renders the existing `internal_bridge_decision` target, motion, signal, reason, and CRM evidence. |
| Slack slice | Skipped Wave 2 because OA-C2 was not granted: the token variable exists, but no owner-named demo channel or confirmed `chat:write` grant was supplied. |

## Proof Receipts

| Claim | Receipt |
| --- | --- |
| Deterministic CSM spine | `make scorecard-csm-check` -> `Agent 1 CSM scorecard: 24/24 hard_ok=True`; scorecard/work-queue artifacts current. |
| Judge scope | `.venv/bin/python -m pytest tests/test_judge_validation.py -q` -> 21 passed. |
| Outcome integrity | VM-8 focused tests plus the sweep suppression check -> 4 passed. |
| Internal handoff | `PYTHONPATH=src:. .venv/bin/python -m eval.internal_bridge_validation --prose fixture --check --output /tmp/mpc_internal_bridge_fixture_check.json` -> `routing_core_hard_ok=True`, no routing failures, no confidently-wrong cells, no packet failures. |
| Drift power | `make drift-power-csm` -> `hard_ok=True`; `eval/drift_power_csm.json` expanded hard layer records `n=64` and minimum detectable drop `0.089`. |
| Quality status artifacts | `make quality-gold-status-check-csm quality-gold-hard-status-check-csm` -> both artifacts current. |
| Hosted demo build | `make hosted-readonly-demo` passed; Next lint reported 0 errors and 6 existing React effect warnings; `next build` completed. |
| Hosted read-only guard | `.venv/bin/python -m pytest tests/test_hosted_readonly_demo.py tests/test_internal_bridge.py::test_sweep_work_item_carries_additive_internal_bridge_decision -q` -> 4 passed. |
| Hygiene | `make hygiene` passed after C1, C2, and C3. |

## Demo Verification

The C3 browser pass verified:

- `/ui/` loads with title `ultra·csm — operations surface`.
- The Queue view loads in hosted read-only mode with 10 pending decisions and
  170 accounts covered with no action.
- Trailhead Logistics renders a Product internal handoff with `content route`,
  `feature request cluster`, and CRM evidence `12b20f2f...`.
- The same detail shows a proposed customer draft and a disabled approval rail.
- `/ui/comms-review/` loads.

The hosted fixture manifest records day 140, 181 accounts, 12 work items, 11
proposals, and `write_routes_exported=false`.

## Known Boundaries

- The hosted demo is fixture-backed and static; it is not a live connector
  deployment.
- The UI walkthrough does not directly demonstrate realized outcome states.
  Outcome honesty is proven by VM-8 tests and documented in `docs/LIMITS.md`.
- The MP-B internal handoff claim remains spike-scoped to the validated
  Engineering/Product pair.
- No Slack message was posted. Wave 2 remains available only after an
  owner-named demo channel and `chat:write` grant are supplied.
