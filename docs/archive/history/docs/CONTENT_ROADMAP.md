# ADR: Content Roadmap

<!-- sourcebound:purpose -->
Use this page when you need to understand ADR: Content Roadmap before changing this repository. Without the documented scope and constraints, a change can rely on behavior the project does not promise; after reading, you can work from the stated contract.
<!-- sourcebound:end purpose -->
## Status

Accepted. Stream 46 (Content Roadmap, Wave Harvest-29).

## Context

`agent1/sweep.py` already computes, per account, which of 7 struggle triggers are
firing (`champion_inactive`, `feature_shallow_depth`, `health_red`, `health_yellow`,
`milestones_overdue`, `low_seat_penetration`, `outcome_unknown`) — real telemetry/CS-
platform signal, not guesswork. Separately, `content_catalog.json` (fleetops, loopway)
already tags enablement content with an `addresses_gap` category. Neither side talked to
the other: nothing aggregated struggle-trigger frequency into a prioritized authoring
roadmap, and — verified by grep before this dispatch — `content_route` (a fully-defined,
gated `CSMActionSpec` since Report 34 or earlier) had **zero callers anywhere in the
runtime**. `data_plane/campaigns.py` runs exactly one hand-curated static campaign,
unrelated to trigger matching.

## Decision

Two halves, both built this dispatch:

**1. Aggregate demand → Notion roadmap.** `content_roadmap.py` walks fleetops's and
loopway's real books (the only two tenants with both CS-platform data and a
`content_catalog.json` — fieldstone/crateworks have neither), reuses
`agent1.sweep._account_tier_and_triggers` (never re-derives trigger logic), and scores
each `(tenant, gap)` pair:

```
coverage_gap_score = accounts_affected + high_arr_bonus - existing_content_count
```

Both `accounts_affected` and `high_arr_bonus` are strictly additive — a gap with zero
high-ARR accounts scores exactly `accounts_affected - existing_content_count`, never
less. `scripts/content_roadmap_push.py` pushes the ranked table to a new "Content
Roadmap" Notion database, idempotently: re-running it updates only the 4 numeric columns
for an existing `(Tenant, Gap)` row; `Status` is set once on creation and never
overwritten by a re-run (a human-owned tracking field).

**2. Close the loop: `content_route`'s first real caller.** `agent1/content_route_matcher.py`
is a pure function — given an account's fired triggers and its tenant's
`content_catalog.json`, return matching entries. `agent1/sweep.py`'s per-account proposal
loop calls it: when `draft_customer_outreach` did not already claim the account this pass
and a catalog entry matches, the work item becomes a `content_route` proposal through the
**existing, unmodified** governance gate (`autonomy_tier=2`, `human_approve`) — no new
governance code, a new caller of it.

## Why the matcher reads disk, not Notion, at sweep time

```
CSM authors/edits content_catalog rows in Notion
  -> notion_render.py --target curated  (human-invoked, PR-reviewed)
  -> validate_content_catalog_payload   (tenant-agnostic subset of
                                          test_content_catalog.py's schema)
  -> knowledge/tenants/<tenant>/content_catalog.json   (the REAL, served path)
  -> agent1/content_route_matcher.load_tenant_content_catalog reads it on the next sweep
```

A live-Notion-at-sweep-time design was rejected outright: this repo's architecture is
seed-then-read (`docs/AGENT_PROFILE.md`'s risk posture: "no live connector reads at
request time except deliberately-scoped manual review actions"). `--target curated`
writes **only** `content_catalog.json` — `org_pack.json`/`playbooks.json`/
`handoff_notes/*` stay `--target generated`-only, per `docs/NOTION_AUTHORING_EDGE.md`'s
existing one-directional/loader-as-oracle boundary, untouched by this dispatch.

## Taxonomy canonicalization

`content_catalog.json`'s `addresses_gap` values (9 across both tenants) predated this
dispatch and used a different vocabulary than the 7 real triggers — only
`feature_shallow_depth` matched exactly. 6 were relabeled to their closest trigger; 3
with no corresponding trigger today (`alert_fatigue`, `integration_blocker`,
`usage_decay_silent`) were left as-is, a stated exclusion — the roadmap cannot
demand-match them until a future dispatch adds a trigger that detects that pattern. See
`docs/DECISION_LOG.md`'s Stream 46 entry for the exact mapping table.

## What this does not prove

The 6 taxonomy relabels are the emitter's best-effort semantic judgment, not
owner-verified CS domain expertise. The real ranked roadmap (`docs/PROGRAM_REPORT_46.md`)
is a genuine computed artifact from fleetops's and loopway's actual books, not a mock,
and (as of 2026-07-06) it is live in Notion — 14 real rows, verified idempotent across
two pushes — but whether a CS/content team finds it a usable planning surface is
untested; no content-team member has given feedback on it. `content_route`'s proposal still
requires a real human `human_approve` verdict before anything reaches a customer — the
same residual every other customer-facing action in this repo already carries.
