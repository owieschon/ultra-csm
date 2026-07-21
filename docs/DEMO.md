# Customer Action Control Plane demo

<!-- sourcebound:purpose -->
Status: current reviewer walkthrough for the local read-only operations surface.
<!-- sourcebound:end purpose -->

This is not a dashboard. Demo it as a customer action control plane: the system reads
account evidence, decides what needs attention, drafts the next CSM action, routes
internal Product/Engineering handoffs when the evidence supports one, and keeps
customer-facing work behind a human approval gate.

## Build And Serve

From the repo root:

```sh
make hosted-readonly-demo
ULTRA_CSM_DEMO_NOAUTH=1 ULTRA_CSM_BIND_HOST=127.0.0.1 PYTHONPATH=src:. \
  .venv/bin/python -m uvicorn ultra_csm.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/ui/`.

Fresh C3 verification:

- `make hosted-readonly-demo` passed; Next lint reported 0 errors and 6 existing
  React effect warnings, then `next build` completed.
- `http://127.0.0.1:8000/ui/`, `/ui/comms-review/`, and the built CSS asset
  returned HTTP 200.
- `ui/public/demo-api/manifest.json` records day 140, 181 accounts, 12 work
  items, 11 pending proposals, and `write_routes_exported=false`.

## Ninety-Second Walkthrough

1. Start on the Book view.
   Say: this is the account book the agents operate over, not a BI dashboard. It
   shows 181 fixture accounts and a `READ-ONLY DEMO` banner.

2. Click `Queue`.
   The queue shows 10 items needing approval, 170 accounts covered with no action,
   no escalations this sweep, and the audit ledger. This is the CSM worklist the
   agents produced from CRM, CS-platform, telemetry, and comms-shaped evidence.

3. Select `Trailhead Logistics`.
   Show the account brief: lifecycle stage, account sources, priority score, cited
   deterministic factors, reconciliation signals, chosen action, and proposed
   customer draft. The draft is evidence-backed, but it is still only a proposal.

4. Point at `Internal handoff`.
   Trailhead shows a Product handoff: `content route`, `feature request cluster`,
   with CRM evidence `12b20f2f...`. This is the MP-B handoff slice made visible in
   the work item: the system can route a grounded customer signal to Product or
   Engineering without changing the customer-facing approval path.

5. Point at `Decision`.
   The approval rail says the read-only demo has approvals and sends disabled. In the
   live governed path, customer-facing work follows proposal -> human verdict ->
   committer. The agent does not approve its own send.

6. Point at the audit ledger.
   The ledger shows proposal, judge, draft, and value-model events. The read-only
   fixture reports `ledger_gap=[]`, so the visible demo is not hiding missing event
   classes behind a clean screen.

## Outcome Boundary

Do not claim the read-only UI demonstrates realized customer outcomes. The outcome
integrity proof is in code and docs, not this click path:

- `tests/test_value_model.py::test_green_high_usage_account_that_later_churns_does_not_backfill_known_outcome`
- `tests/test_value_model.py::test_closed_won_renewal_is_positive_realized_outcome_evidence`
- `tests/test_value_model.py::test_non_terminal_or_non_renewal_opportunity_does_not_fabricate_known_outcome`
- `tests/test_agent1_sweep.py::test_outcome_unknown_trigger_absent_when_terminal_renewal_outcome_known`
- `docs/PROGRAM_REPORT_69.md`
- `docs/LIMITS.md`

The honest claim: before terminal renewal evidence exists, the value model stays
`not_instrumented` / unverified; after terminal renewal evidence exists, it records
won/lost direction with cited opportunity evidence. The read-only UI walkthrough does
not expose that state directly.

## Demo Boundaries

- Reviewer mode is static and read-only. It serves committed JSON fixtures from
  `ui/public/demo-api/` and exports no write routes.
- The data is synthetic and internally consistent, not production customer proof.
- Salesforce, Rocketlane, Gmail, and persistent-ledger receipts exist in program
  reports, but this demo is fixture-backed.
- Sales-to-CS context exists in the account/knowledge corpus, but the 90-second UI
  path is queue -> account brief -> internal handoff -> governed proposal.
