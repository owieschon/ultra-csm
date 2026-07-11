# Action Control sandbox

The sandbox is a no-login synthetic laboratory for one bounded Trailhead
Logistics draft. It is not a production action endpoint and cannot select a
tenant, account, recipient, permission, action type, or outbound target.

## What executes

`POST /demo/action-control/sandbox/evaluate` accepts at most four commands. The
server opens a fresh database connection, starts a transaction, replays the
entire command log through the production `ActionGate` and the sandbox-only
`RollbackSandboxCommitter`, verifies the temporary JSONL outbox, constructs the
response, rolls back, removes the temporary directory, and only then returns.

The permitted graph is:

```text
pending_human_decision
  -> approve_exact | revise_and_approve -> approved_payload_bound
  -> deny -> denied_terminal

approved_payload_bound -> commit_simulated -> simulated_committed
simulated_committed -> retry_same_commit (state unchanged; duplicate proof added)
simulated_committed -> probe_tamper -> refused_payload_mismatch
```

Reset is client-side: generate a new `run_id` and evaluate an empty command
log. There is no durable sandbox session to delete.

The response schema is frozen at
`docs/contracts/action-control.sandbox-session.v1.schema.json`. A canonical
`state_sha256` binds each response. For a non-empty log, the server replays all
commands before the final command and requires that prefix to produce the
submitted `expected_state_sha256`; otherwise evaluation fails with
`COMMAND_PREFIX_MISMATCH`.

That check proves command-prefix integrity inside the submitted replay. It is
not compare-and-swap and does not serialize forks across separate requests.
The server stores no public session: two independent requests may reuse the
same `run_id`, prefix, and digest and validly branch into approve and deny.
The browser aborts superseded fetches and ignores late responses locally so a
slower response cannot overwrite a newer screen, but that client behavior is
not a server-side concurrency claim.

## Idempotency and tampering

The first simulated commit must produce one physically verified outbox row.
`retry_same_commit` calls the same committer again and must return
`committed=false` with the same key while the row count remains one.

`probe_tamper` changes only the synthetic draft body and calls the committer
with that altered proposal. The production payload-binding guard must raise
`PAYLOAD_HASH_MISMATCH`; the first receipt remains and no second row appears.

## Error privacy and caching

Request validation returns the stable `INVALID_SANDBOX_REQUEST` code and only
server-declared field paths. It never returns Pydantic's rejected `input`, the
draft, attacker-selected keys, or validation messages. Unexpected exceptions
return only `SANDBOX_INTERNAL_ERROR`; exception text is not sent to the client.

Every response from the sandbox-only app, including validation, transition,
not-found, and unexpected-error responses, carries `Cache-Control: no-store`.
Database rollback and temporary-directory removal run in the evaluator's
`finally`/context cleanup even if the committer fails after writing its
temporary outbox.

## Hosting boundary

The Vercel application remains a static, no-write export. When
`NEXT_PUBLIC_ACTION_CONTROL_SANDBOX_API` is absent, `/ui/action-control/`
renders the frozen executable V1 proof and explicitly says that its controls
are unavailable. It does not simulate successful clicks in the browser.

Real hosted interactivity requires deploying
`ultra_csm.action_control_sandbox_api:app` as a separate service and setting an
exact `ULTRA_CSM_SANDBOX_ALLOWED_ORIGINS` allowlist. That minimal app exposes
only health, OpenAPI metadata, and the sandbox evaluator; it does not expose
the production proposal, connector, or mapping routes.

The reproducible separate-project bundle and operator procedure are documented
in [`HOSTED_ACTION_CONTROL_RUNBOOK.md`](HOSTED_ACTION_CONTROL_RUNBOOK.md). The
repository does not provision or claim a live sandbox until those external
steps and post-deploy checks have receipts.

The public ingress should additionally enforce request-rate and concurrency
limits. The application bounds each JSON body to 16 KiB, each draft to 800
characters, and each log to four commands.
