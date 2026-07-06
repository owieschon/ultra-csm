# Program Report 55 — Master Live Build Phase 5: Persistent State

Branch `codex/master-live-phase5` off synced `origin/main`
(`0f24213`, PR #79 merged). This report captures Phase 5 of
`MASTER_LIVE_BUILD.md`: a persistent Postgres option for served/runtime paths,
idempotent migrations, and restart durability while keeping `make eval`
hermetic on the default ephemeral harness.

## Scope

The persistent path is opt-in by environment:

| Env var | Purpose |
| --- | --- |
| `ULTRA_CSM_DATABASE_URL` | Runtime DSN, expected to connect as `app_runtime` |
| `ULTRA_CSM_DATABASE_ADMIN_URL` | Optional admin/bootstrap DSN for migrations and base seed |

When `ULTRA_CSM_DATABASE_URL` is absent, API, MCP, tests, and eval keep the
existing throwaway `EphemeralCluster` behavior. When it is present, API, MCP,
and the non-dry-run tick CLI use the persistent runtime connection and still
call `assert_rls_safe_role` before any product work.

## Implementation

| Area | Change |
| --- | --- |
| Migration runner | `apply_migrations` now records `public.schema_migration(filename, checksum_sha256, applied_at)` and skips already-applied files with matching checksums |
| Runtime wiring | New `ultra_csm.platform.runtime` centralizes persistent env parsing, idempotent bootstrap, and guarded app-runtime connection |
| API boot | `lifespan` chooses persistent env path or the old ephemeral path |
| MCP boot | Non-read-only `_boot` chooses persistent env path or the old ephemeral path |
| Tick daily path | `run_tick_cli(..., dry_run=False)` uses persistent state when `ULTRA_CSM_DATABASE_URL` is set |
| Tests | `tests/test_persistent_runtime.py` covers migration replay, API restart durability, and persistent cross-tenant RLS |

## Gate Receipts

Focused persistent proof:

```text
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 .venv/bin/python -m pytest tests/test_persistent_runtime.py -q
...                                                                      [100%]
3 passed, 1 warning in 2.91s
```

Nearby default-path regression:

```text
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 .venv/bin/python -m pytest tests/test_api.py tests/test_cross_tenant_rls.py tests/test_persistent_runtime.py -q
................................................                         [100%]
48 passed, 1 warning in 5.69s
```

Lint:

```text
make lint
.venv/bin/python -m ruff check src eval tests scripts
All checks passed!
```

Full eval on the default ephemeral harness:

```text
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 make eval
777 passed, 1 skipped, 1 warning in 129.57s (0:02:09)
eval/gold/slot_b_quality_status.json is current
eval/gold/slot_b_quality_hard_status.json is current
```

## Durability Proof

`tests/test_persistent_runtime.py::test_persistent_api_restart_keeps_proposal_verdict_and_ledger`
boots the FastAPI app with `ULTRA_CSM_DATABASE_URL` and
`ULTRA_CSM_DATABASE_ADMIN_URL` pointed at the same local Postgres instance,
writes a proposal through `POST /sweep`, records a local test verdict through
`POST /proposals/{proposal_id}/verdict`, shuts the API process context down,
boots a second API context against the same DSN, and confirms `/ledger` still
contains both events:

```text
{(proposal_id, "gate.propose"), (proposal_id, "gate.deny")}
```

That is the Phase 5 write -> restart -> row present proof, observed through the
product ledger endpoint rather than a private table-only assertion.

## RLS Proof

`tests/test_persistent_runtime.py::test_persistent_runtime_enforces_cross_tenant_rls`
runs migrations through the persistent admin DSN, opens the runtime DSN as
`app_runtime`, calls `assert_rls_safe_role`, writes one `principal` row under
tenant `acme-csm`, then performs the same unfiltered lookup from `acme-csm` and
`summit-csm` sessions. The observed counts are:

```text
same_tenant_count == 1
cross_tenant_count == 0
```

No RLS policy, role, or FORCE-RLS setting was weakened for the persistent path.

## IF/THEN Branches

1. IF `ULTRA_CSM_DATABASE_URL` is absent, THEN all existing default harnesses
   must keep using `EphemeralCluster`; Phase 5 therefore gates persistent state
   behind env vars instead of changing global test setup.
2. IF a persistent database has no admin DSN configured, THEN the app treats it
   as already prepared and connects only as `app_runtime`; missing schema fails
   clearly at runtime instead of granting the runtime role migration power.
3. IF historical migration text differs from the checksum recorded in
   `public.schema_migration`, THEN boot fails closed; immutable migrations must
   not be silently replayed or overwritten.

## Skeptical Reviewer Paragraph

This phase proves the product can run against a durable Postgres DSN without
giving up the `app_runtime`/FORCE-RLS guard, and it proves proposal/verdict
ledger rows survive an API restart. It does not claim a real production
customer deployment, a multi-day operating ledger, or a live customer send.
Those are later phases. It also does not self-approve any customer-facing
proposal: the verdict used in the durability test is local test traffic against
a temporary database.

## Receipts Appendix

- New proof file: `tests/test_persistent_runtime.py`.
- Runtime helper: `src/ultra_csm/platform/runtime.py`.
- Migration idempotency table: `public.schema_migration`.
- Persistent env names only: `ULTRA_CSM_DATABASE_URL`,
  `ULTRA_CSM_DATABASE_ADMIN_URL`.
- Owner-merge policy applies: this is DB/isolation substrate work and the PR
  stays open for review under OA-5.
