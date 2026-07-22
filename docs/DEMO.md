# Operations UI walkthrough

Use this walkthrough to inspect the fixture-backed customer-action path without
mistaking a static demo interaction for a production approval, send, or outcome.

The [hosted build](https://ultra-csm.vercel.app/) serves committed synthetic fixtures and
exports no write routes. To build that static export and co-host it with the full local API:

```sh
make hosted-readonly-demo
ULTRA_CSM_DEMO_NOAUTH=1 ULTRA_CSM_BIND_HOST=127.0.0.1 PYTHONPATH=src:. \
  .venv/bin/python -m uvicorn ultra_csm.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/ui/`.

The static export is read-only. The loopback FastAPI process is not: `ULTRA_CSM_DEMO_NOAUTH=1`
disables authentication but does not remove the full application's mutation routes. It can change
only the configured local data, so keep it bound to loopback and stop it after the walkthrough.

## Inspect the fixture contract

Before quoting counts, read them from the committed fixtures:

```sh
jq '{day, account_count, work_item_count, proposal_count, write_routes_exported}' \
  ui/public/demo-api/manifest.json
jq '{pending: ([.work_items[] | select(.proposal.status == "pending")] | length),
     escalations: (.escalations | length)}' \
  ui/public/demo-api/sweep-day-140.json
```

`make hosted-readonly-demo` fails if those fixture bytes are stale. The manifest's
`write_routes_exported` field must remain `false`.

## Follow one action

1. Start on **Book**. The page lists the synthetic account universe and labels the
   surface `READ-ONLY DEMO`.
2. Open **Queue**. The queue separates pending proposals, resolved work, and accounts
   covered with no action. Treat the displayed counts as fixture facts, not product
   outcomes.
3. Select **Trailhead Logistics**. Inspect the tenant-scoped sources, deterministic
   priority factors, selected action, cited evidence, and fixture-generated draft. The
   work item records `draft_mode: fixture`; this path does not demonstrate a live model
   call.
4. Inspect **Internal handoff**. The fixture routes a cited feature-request signal to
   Product without changing the customer-facing approval path.
5. Inspect **Decision**. The hosted build disables approvals and sends. The governed
   local path requires a proposal, a verdict from a configured approval identity, a
   payload-bound committer, and a receipt.
6. Inspect the audit ledger. The fixture exposes proposal, judge, draft, and value-model
   events instead of hiding missing event classes behind a clean screen.

## What this path proves

- The static operations UI renders a deterministic, internally consistent fixture.
- The queue and account views preserve evidence references and distinguish deterministic
  priority from a draft.
- The hosted export contains no write routes.
- The interface states where an operator decision would enter the governed local path.

## What it does not prove

- It does not demonstrate a live model call, live connector access, or a production
  customer action.
- It does not approve or send the displayed draft.
- It does not demonstrate retention, expansion, or other realized customer outcomes.

Outcome integrity is tested below the UI. Before terminal renewal evidence exists, the
value model keeps the outcome unverified; a terminal renewal records won or lost direction
with cited opportunity evidence. See `tests/test_value_model.py`,
`tests/test_agent1_sweep.py`, and [`LIMITS.md`](LIMITS.md).

For an interactive local sandbox that writes only to temporary state, see
[`ACTION_CONTROL_SANDBOX.md`](ACTION_CONTROL_SANDBOX.md).
