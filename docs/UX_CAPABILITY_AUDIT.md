# UI/UX Capability Audit

This audit maps what the codebase can already do to how the current UI brings it to life, and where the UX should go next.

The product should not become a dashboard or a relationship-intelligence workspace. The strongest product shape is a governed agent-work system: agents assemble account context, detect work, route it, draft packets, and keep every customer-facing or cross-functional action behind human authority.

## Current Product Spine

The shipped UI already has the right bones:

- `ui/app/page.tsx` defines a two-mode app: `BookView` and `QueueView`, with `ActionRail` only present when working the queue.
- `ui/components/BookView.tsx` renders the CSM's book by service tier and distinguishes hot, handled, internal-review, and quiet accounts.
- `ui/components/QueueView.tsx` turns sweep output into pending and resolved work lanes.
- `ui/components/QueueDetail.tsx` renders account sources, priority factors, reconciliation, internal handoff, chosen motion, recipient, and draft.
- `ui/components/ActionRail.tsx` owns approve, edit, deny, and audit-ledger visibility.
- `ui/app/comms-review/page.tsx` is a separate manual review surface for Slack/Notion attribution.

The issue is not absence. The issue is hierarchy. The current UI often presents major capabilities as account-detail sections or drawers, so the product reads like account inspection plus approval buttons. The codebase is more interesting than that: it can already produce typed CSM work.

## Capability Map

| Capability | Code source | Current UI expression | UX gap | Recommended module |
| --- | --- | --- | --- | --- |
| Book sweep and work generation | `src/ultra_csm/agent1/sweep.py`, `POST /sweep` in `src/ultra_csm/api.py` | Book summary and queue lanes | Work items are visually treated as account rows, not as agent-produced work artifacts | **Agent Work Queue**: lane by work type and decision state, not just pending/resolved |
| Deterministic value model | `src/ultra_csm/value_model.py`, `src/ultra_csm/_api_helpers.py` | Priority score and expandable factors | The four rails and divergence layer are mostly implicit | **Evidence Receipt**: compact score receipt that names rails, divergences, and thresholds |
| Time-to-value lens | `run_time_to_value_sweep(...)`, `project_ttv_lens(...)` | Reasons, factors, draft body | Lens identity is submerged; user sees generic account priority | **Lens Badge + Why Now**: "TTV agent found onboarding stall" with rule/evidence receipt |
| Risk and expansion factors | `src/ultra_csm/agent1/lens_risk.py`, `src/ultra_csm/agent1/lens_expansion.py`, `reconciliation_agent.py` | Reconciliation deterministic signals | They appear as secondary reconciliation rows, not as possible agent views | **Secondary Lens Signals**: "also seen by Risk/Expansion" without creating new dashboards |
| Governance proposal lifecycle | `src/ultra_csm/governance/gate.py`, `/proposals`, `/proposals/{id}/verdict` | Right rail decision controls and ledger | The approval gate is visible but not central enough to the work item | **Governed Work Packet**: proposal id, action type, autonomy tier, permission, payload hash, status |
| CSM action taxonomy | `src/ultra_csm/governance/csm_actions.py` | Mostly hidden behind `action_type`, motion, and buttons | The system can do more than draft email, but the UI makes email feel like the only native output | **Action Type Switchboard**: outreach, CRM log, CS record update, success plan edit, call initiation, campaign enroll, content route, cohort action |
| Human revise loop | `src/ultra_csm/proposal_revise.py`, `ActionRail.tsx` | Edit instruction textarea | Edit is UI-visible only for customer outreach and not framed as agent iteration | **Revise as Workflow Step**: original draft -> human instruction -> superseding proposal -> audit |
| Committers and writeback | `src/ultra_csm/committers.py`, `src/ultra_csm/data_plane/gmail_writeback.py`, `salesforce_writeback.py` | Hidden in backend; read-only demo disables writes | User cannot see what would be written where | **Commit Preview**: outbox/CRM/Gmail/Salesforce target, dry-run receipt, idempotency key |
| Internal bridge | `src/ultra_csm/internal_bridge/routing.py`, `packet.py` | Small `Internal handoff` card inside account detail | This is a major cross-functional capability but it looks like a side note | **Internal Handoff Packet**: Engineering/Product target, signal, cited cases, packet body, owner approval state |
| Sales handoff context | Present as account/opportunity/renewal data in briefs and governance payloads; README names it | Not a first-class surface | Sales handoff is real product value, but not represented as a distinct packet | **Sales Handoff Packet**: renewal risk, open cases, customer pain, suggested AE/CSM motion, evidence, gate |
| Account brief | `_build_account_brief(...)`, `AccountBriefResponse` | Source drawers plus identity header | Rich brief data exists, but the detail starts with sources rather than "the work to do" | **Packet Brief Sidebar**: account facts only in service of the selected work item |
| Comms evidence | `comms_mapping.py`, Gmail/Notion/Slack readers, brief comms fields | Comms drawer and `/comms-review` page | Comms are inspectable but not used as a visible evidence chain for a packet | **Source Evidence Stack**: show comms rows cited by the current work item, not all comms first |
| Comms mapping review | `/comms/pending-mappings/*`, `ui/app/comms-review/page.tsx` | Separate sparse page | Useful, but disconnected from main workflow | **Setup/Integrity Task**: appears in agent work queue as "confirm source attribution" |
| Trajectory | `/accounts/{id}/trajectory`, brief `trajectory` field, `snapshot_store.py` | Not surfaced in main detail | Trend exists but is invisible in demo surface | **Trajectory Receipt**: tiny sparkline or state pill: improving/stable/declining, with points on expand |
| Outcome integrity | VM-8 in `value_model.py`, reports/tests | Factor row `usage_outcome_unverified`; outcome rail otherwise quiet | The product's honesty about outcome is important but visually underplayed | **Outcome Truth Block**: known won/lost, unknown, or not instrumented; never infer success from usage |
| Reconciliation agent | `src/ultra_csm/reconciliation_agent.py`, `ReconciliationSection.tsx` | Section below priority factors | Strong safety distinction exists, but its job is not obvious | **Reported vs Experienced Check**: a named verification step inside the work packet |
| Digest | `/digest` in `api.py`, `cohort_packets.py` | No UI route | Manager/day-start rollup exists but not used | **Morning Brief / Manager Rollup**: optional top-level view after queue, not a dashboard replacement |
| Cohort packets | `src/ultra_csm/cohort_packets.py` | Only via digest payload | Population-level value is hidden | **Cohort Insight Packet**: observed pattern, affected accounts, proposed next governance action |
| Delegation and precedence | `/queue/delegation`, `src/ultra_csm/agent1/precedence.py` | Not surfaced | The system can hold actions, but the UI only shows approve disabled/error after click | **Held Work Lane**: explicit blocked/held items with blocking refs and release criteria |
| Observability and cost | `/metrics`, `api_metrics.py`, `cost_tracker.py`, `operating_monitor.py` | Not surfaced | Operational reliability is proven but invisible | **Ops Health Strip**: last sweep, cost budget, degraded item count, ledger gaps, source mode |
| MCP read-only/operator mode | `src/ultra_csm/mcp_server.py` | Outside UI | Conversational surface is powerful but separate | **Companion Mode Note**: not a UI module now; document as alternate interface, not blend into app |
| Eval and judge scope | `eval/`, `docs/PROGRAM_REPORT_70.md`, judge tests | Only README/docs | Crucial trust story but not a CSM runtime concern | **Evidence of Reliability Page**: product/proof page, not inside the CSM work queue |

## What The UI Should Become

Use one primary object: **agent work item**.

The work item has typed modules:

1. **Work Header**
   - Account
   - Agent/lens that produced it
   - Work type: CSM action, route decision, internal handoff, sales handoff, setup/integrity, cohort packet
   - Required human authority
   - Status: pending, held, revised, approved, denied, committed

2. **Action Packet**
   - Proposed action in plain language
   - Draft body or writeback target
   - Recipient or internal target
   - Consent/permission status
   - "What will happen if approved"

3. **Evidence Receipt**
   - Priority factors
   - Value-model rails and divergence facts
   - Source IDs
   - Trajectory/outcome state when available
   - Reported-vs-experienced reconciliation

4. **Governance Rail**
   - Proposal id
   - Autonomy tier
   - Required permission
   - Payload hash
   - Approve/edit/deny
   - Blockers and precedence holds
   - Audit history

5. **Context Drawer**
   - Comms, cases, telemetry, success plan, opportunities, stakeholders
   - These are supporting facts, not the main product surface

This keeps stakeholder data in the system without making stakeholder intelligence the product.

## Recommended Navigation

Keep the app small:

- **Book**: portfolio coverage and quiet/hot state.
- **Work**: the main operating surface; queue + selected work packet + governance rail.
- **Integrity**: source mapping, held work, ledger gaps, source readiness.
- **Proof**: optional demo/proof page for reliability receipts, not daily workflow.

Avoid:

- A "dashboard" first screen.
- A relationship map as the anchor.
- Separate pages for every source system.
- A manager analytics surface before the agent-work system is clear.

## Current UI Assessment

| Surface | Keep | Change |
| --- | --- | --- |
| Book view | Service-tier grouping, quiet/hot/handled distinction, "Work the queue" CTA | Make it read as coverage status, not the primary product |
| Queue lanes | Fast operator density, pending/resolved split | Add typed lanes: customer action, internal handoff, sales handoff, held/setup |
| Account detail | Evidence expansion, source honesty, two-register labels | Reframe as selected work packet; demote generic source drawers |
| Action rail | Approval/edit/deny, audit ledger, read-only demo state | Add proposal contract details, blockers, commit preview, and revision chain |
| Reconciliation | Deterministic vs hypothesis distinction | Integrate as verification step inside evidence receipt |
| Comms review | Honest manual mapping review | Bring into integrity work queue rather than a hidden page |

## Implementation Sequence

### Slice 1: Rename The Mental Model

Low code risk. No new backend.

- Rename queue headers/copy from "account queue" to "agent work".
- In `QueueLanes`, group by `recommended_action`, `motion`, `internal_bridge_decision`, and `proposal.status`.
- In `QueueDetail`, put "proposed work" above "account sources".
- Keep all existing drawers intact.

### Slice 2: Work Packet Detail

Moderate UI refactor, still existing data only.

- Add a `WorkPacketHeader` component.
- Add an `EvidenceReceipt` component fed by `item.priority`, `item.evidence`, `brief.trajectory`, and reconciliation.
- Add an `ActionPreview` component for customer drafts, internal handoffs, and sales handoff placeholder packets.
- Move source drawers below the packet as context.

### Slice 3: Governance Rail Upgrade

Uses existing proposal/ledger data.

- Show autonomy tier and required permission from `proposal`.
- Show payload hash if available from `/proposals`.
- Show "what approval commits" for draft/customer outreach, CRM activity, and internal-only actions.
- Show precedence hold details from `/queue/delegation`.
- Show revise chain when a superseding proposal exists.

### Slice 4: Sales And Internal Packets

Small backend shaping may be needed.

- Promote `internal_bridge_decision` from card to packet.
- Add a derived sales handoff packet when renewal/opportunity/cases justify it.
- Use customer/opportunity/case evidence already in `AccountBriefResponse`.
- Keep relationship data as supporting context only.

### Slice 5: Integrity And Morning Brief

Use existing endpoints, but keep them secondary.

- Fold `/comms-review` into an "Integrity" view.
- Add source-readiness, mapping tasks, ledger gaps, and last sweep health.
- Add Morning Brief from `/digest` only after Work view is crisp.

## Design Boundary Against Centralize

Allowed:

- Mention stakeholders when they are needed for a proposed action.
- Cite contacts as evidence for consent, recipient choice, or single-threading risk.
- Show engagement recency as a receipt.

Not allowed as the product center:

- Relationship graph.
- "Who matters" surface.
- Warm path discovery.
- Multithreading as the main workflow.
- Stakeholder-priority intelligence as the differentiator.

Ultra CSM's differentiator is that agents produce governed CSM work. Relationship data is an input, not the product.

## Best Next Design Direction

Build a single **Agent Work** surface:

```text
Book coverage -> Agent Work Queue -> Work Packet -> Approval / Audit
                                  -> Evidence Receipt
                                  -> Source Context
```

That lets every capability in the codebase come alive without turning the app into a dashboard or a Centralize clone.

