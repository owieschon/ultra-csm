# BLOCKED: Content Roadmap live Notion push (Phase 3, one sub-item only)

Named distinctly from `BLOCKED.md` (a pre-existing, since-resolved file inherited from
the Act2 Gmail write-back merge on `main` — a different dispatch/report, not touched
here; out of this dispatch's ownership map).

Everything else in this dispatch (Phases 0-2, 4-7) is green, committed, and unblocked.
This file covers exactly one sub-item: `scripts/content_roadmap_push.py`'s live
create/upsert against a real "Content Roadmap" Notion database.

## What

`content_roadmap_push.py` cannot locate a parent page to create the "Content Roadmap"
database under (Decision 8 of `19_CONTENT_ROADMAP.md`), and cannot find the existing
"Content Catalog"/"Org Pack" databases either.

## Why

The `ULTRA_CSM_NOTION_TOKEN` credential in `~/ultra-csm-live-creds.env` authenticates
successfully but has **zero pages or databases shared with it**. This is a different
Notion integration than the one used interactively (via the session's Notion MCP
connection) to create the "Org Pack" and "Content Catalog" databases earlier in the same
session — those two access paths are not the same credential, and the static token has
never been granted access to anything in the workspace.

## Evidence (3 distinct approaches, same root cause each time — K5's bar for "stop
retrying, this needs the owner" is met)

1. `POST /v1/search` with `filter: {"value": "database", "property": "object"}` →
   `400 validation_error`: `"body.filter.value should be \`data_source\` or \`page\`"`
   (Notion API version `2025-09-03` renamed this filter value — fixed).
2. `POST /v1/search` with `filter: {"value": "data_source"}`, `query: "Catalog"` →
   `200`, 0 results, no auth error.
3. `POST /v1/search` with no body at all (fully unfiltered) → `200`, 0 results, no auth
   error. A valid, authenticating token with zero visible pages/databases.

## What was tried

- Three distinct search-query shapes (above) — all return the same "zero access" result,
  not a query-construction problem.
- Confirmed the token itself is not malformed: length 50, prefix `ntn_...` (a normal
  Notion internal-integration secret shape), correctly unwrapped from the `<...>`
  bracket-wrapping already known to affect credentials in this file (same fix applied to
  the Rocketlane/Notion tokens earlier in the parent session).

## Fix (owner-only)

In Notion's UI, open the page/workspace section containing the "Content Catalog"/"Org
Pack" databases (or wherever the new "Content Roadmap" database should live) →
"..." menu → "Connections" → add the integration backing `ULTRA_CSM_NOTION_TOKEN`. Once
shared, re-run:

```
PYTHONPATH=src:. .venv/bin/python scripts/content_roadmap_push.py
PYTHONPATH=src:. .venv/bin/python scripts/content_roadmap_push.py   # idempotency check
```

and confirm the second run's output shows `rows_updated` equal to the first run's
`rows_created`, with `rows_created: 0` — the DoD row this file's blocker is standing in
for.

## What's still green without this

- `content_roadmap_push.py --dry-run` — fully offline, computes and prints the real
  ranked roadmap (see `docs/PROGRAM_REPORT_46.md`'s DoD evidence table).
- All write-mechanics tests (5, `tests/test_content_roadmap_push.py`) — idempotent-upsert
  logic, the Decision-6 proof that `Status` is never touched on update, and the
  bracket-unwrap helper — all mocked, all green, no live call.
- The aggregation (`content_roadmap.py`) and the `content_route` matcher/sweep wiring
  are fully independent of this blocker and are both live and tested end-to-end.

## Separate, unrelated note for whoever picks this branch up next

`ps aux` at the time this was written showed a concurrent `make eval` running in
`~/dev/ultra-csm-sweep-observability-asof` (dispatch `21_SWEEP_OBSERVABILITY_AND_MOTION_ASOF`,
report 38) — which also edits `agent1/sweep.py`, the same file Phase 5 of this dispatch
edited. `00_HARVEST_PLAN.md`'s registry already fences this (both entries note the
overlap). Before merging either branch, re-check whether the other has already merged
and rebase rather than force a manual resolution — this is not a blocker on THIS
dispatch's own work, just a real, live sequencing risk to flag rather than silently
merge past.
