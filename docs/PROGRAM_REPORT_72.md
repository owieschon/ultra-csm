# Program Report 72: Backend-Governed CSM Work Packets

Date: 2026-07-07
Branch: `codex/work-packet-architecture`
Work item: `owieschon-cvs`

## Summary

This slice implements the MP-D work-packet architecture: every visible operator item and every swept account now has a backend-generated `CSMWorkPacket` with diagnostic hypotheses, evidence chain, recommended action, contact plan, prepared artifacts, backend-governed CTAs, ActionGate metadata, bucket trace, coverage trace, and feedback hooks.

The operator workbench now consumes those packets instead of deriving the primary action surface from UI heuristics. The readonly hosted demo remains non-executing: approval-like actions are represented as governed CTAs with ActionGate linkage, but the UI cannot perform external writes.

## What Changed

- Added `src/ultra_csm/work_packets.py` as the typed packet contract and deterministic planner.
- Extended Agent 1 sweep output with `work_packet` per work item plus `coverage_packets` for non-visible swept accounts.
- Extended `/sweep` API responses with coverage packets.
- Replaced hardcoded ActionRail commands with backend `allowed_ctas`.
- Migrated queue lanes and detail panes to packet identity, primary next step, evidence chain, bucket trace, coverage trace, and feedback hooks.
- Added packet eval gate at `make work-packet-eval`.
- Added focused backend/API/UI-contract tests for packet schema, action consistency, ActionGate alignment, Ironhorse, coverage, bucket traces, and feedback taxonomy.
- Regenerated hosted readonly demo API fixtures.

## Architecture

Before this slice, the UI had to infer operator action from legacy work-item fields and proposals. That created room for contradictions like a `working_session` motion paired with generic customer outreach, or a CTA rail that offered actions the backend had not explicitly allowed.

After this slice, the backend owns the operator contract:

- `diagnostic_hypotheses`: what the system believes is happening and how confident it is.
- `recommended_action`: the canonical next job, owner role, urgency, and rationale.
- `contact_plan`: who to contact and why.
- `prepared_artifacts`: drafts or outlines the operator can inspect/copy.
- `allowed_ctas`: exact UI actions allowed for the packet, including disabled execution states.
- `governance`: ActionGate and readonly execution boundary metadata.
- `evidence_chain`: source-by-source support for the recommendation.
- `bucket_trace`: why the account landed in its queue bucket.
- `coverage_trace`: how the account was considered across the whole book.
- `feedback_hooks`: structured operator correction categories.

## Ironhorse Proof Case

The Ironhorse packet now resolves the known contradiction:

- Account id: `f16ceec8-7a3a-5d9d-a0ee-a2e7f119fc43`
- Packet job type: `customer_outreach`
- Lane: `needs_judgment`
- Primary next step: "Ask Marcus Webb to resolve 50% asset activation plus gps hardware compatibility issue with older vehicles and reset the activation plan"
- Primary contact: `Marcus Webb`
- Prepared draft: "Hi Marcus Webb, Ironhorse Freight Co is blocked on 50% asset activation plus gps hardware compatibility issue with older vehicles. Can we confirm the owner, decide the next technical step, and reset the activation date?"
- CTAs: `inspect`, `preview`, `copy`, `approve`, `leave_feedback`

The eval gate reports `ironhorse_flagship_pass: true` and `generic_primary_action_rate: 0.0`.

## Operator Workbench

The workbench now shows packet-governed lanes:

- Needs judgment
- Prepared work
- Whole book

The detail pane opens with packet identity and action brief, then shows evidence, "Why this bucket?", coverage, and feedback affordances. Coverage-only rows can be selected and inspected, so non-visible accounts are not silent disappearances.

The ActionRail reads `allowed_ctas` from the packet. In readonly demo mode, execution CTAs remain visibly governed but non-executing, with the audit ledger and governance boundary kept in view.

## Governance

The packet contract keeps readonly demo behavior explicit:

- `can_execute_from_ui: false`
- `external_write_policy: no_external_writes`
- `requires_action_gate: true` for approval-class work
- CTA metadata carries `action_gate_proposal_id` when a proposal exists
- No UI path sends external customer communication

The packet eval checks both `cta_gate_alignment` and `readonly_no_external_execution`.

## Coverage And Trust

Final hosted export:

- Swept accounts: 181
- Visible work items: 12
- Coverage packets: 169
- Total packets evaluated: 181

Every packet has a bucket trace and coverage trace. Suppressed/monitoring accounts remain explainable through coverage packets rather than being invisible.

## Feedback Loops

Packet feedback hooks cover:

- `wrong_diagnosis`
- `wrong_contact`
- `wrong_action`
- `missing_evidence`
- `wrong_bucket`
- `stale_data`
- `product_feedback_candidate`
- `education_resource_candidate`
- `dismiss_monitor`

Feedback CTAs are readonly-local in this slice and do not execute external writes. Product and education recommendations are generated only when customer-experience evidence supports that route.

## Verification

Passed:

- `python3 -m pytest tests/test_work_packets.py tests/test_ui_contract.py tests/test_agent1_sweep.py -q`
  - 42 passed
- `python3 -m ruff check src/ultra_csm/work_packets.py src/ultra_csm/agent1/sweep.py tests/test_work_packets.py eval/work_packet_eval.py`
  - All checks passed
- `make ui-check`
  - lint completed with 6 warnings
  - Next.js build passed
- `make hosted-readonly-demo`
  - demo export, lint, and readonly build passed
- `make work-packet-eval`
  - `packet_schema_complete: true`
  - `primary_next_step_present: true`
  - `evidence_chain_present_for_confident_packets: true`
  - `no_motion_action_contradiction: true`
  - `cta_gate_alignment: true`
  - `readonly_no_external_execution: true`
  - `bucket_trace_present: true`
  - `coverage_trace_present: true`
  - `ironhorse_flagship_pass: true`
  - `generic_primary_action_rate: 0.0`
  - `ui_machine_text_primary_surface: 0`

Browser verification used the local Next.js dev server at `127.0.0.1:3001/ui` with Google Chrome through Playwright. Mobile page-level overflow check passed at 390px viewport width.

## Screenshots

- `docs/work-packet-screenshots/desktop-queue.png`
- `docs/work-packet-screenshots/desktop-selected-ironhorse.png`
- `docs/work-packet-screenshots/mobile-queue.png`
- `docs/work-packet-screenshots/mobile-selected-ironhorse.png`
- `docs/work-packet-screenshots/mobile-why-this-bucket.png`
- `docs/work-packet-screenshots/mobile-evidence.png`
- `docs/work-packet-screenshots/mobile-cta-preview.png`
- `docs/work-packet-screenshots/mobile-whole-book-coverage.png`

## Residuals Filed

- `owieschon-ocn`: Resolve existing React hook lint warnings.
- `owieschon-20w`: Audit UI npm dependency findings.

## Known Residual Risk

The UI lint warnings are existing React `set-state-in-effect` warnings, not packet-contract failures. `npm ci` also reports two moderate audit findings. Both are now tracked in Beads and should be handled as follow-up hygiene work.

Live external execution remains intentionally out of scope for this readonly demo slice. The implementation proves governed ActionGate alignment and non-executing CTAs, not customer-send execution.
