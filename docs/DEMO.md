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

1. Open the hosted demo at its default fixture day, **140**. Select **Review an
   example** to open **Trailhead Logistics**. If the introduction was dismissed,
   select Trailhead from **Book**. The account list and selected review sit side by
   side on desktop. On phones, **Back to queue** returns to the account list.
2. Read **Customer objectives**. The source plan has not reported either objective
   complete. Usage alone does not establish the customer's outcomes. Choose
   **Inspect sources** to open the objective records and their source references.
3. Read the draft to Vanessa Torres. It asks for an objective-status update and
   completion evidence. **Example draft** identifies committed fixture output;
   this walkthrough does not run a live model.
4. Expand **Decision reasoning** to inspect priority factors, the source chain,
   unverified interpretation and internal Product handoff. These records explain
   the proposal; they do not authorize contact.
5. Approve, edit or deny beneath the draft. These hosted actions update browser
   state only. Editing records an instruction; it does not redraft the fixture.
   **Decision receipt** exposes the simulated events. No gate, committer or send
   runs, and reload restores the pending queue. The governed local path requires
   a configured approval identity, payload-bound commitment and a receipt.


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
