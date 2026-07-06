# Program Report 46 — Content Roadmap (Stream 46, Wave Harvest-29)

Dispatch: `~/ultra-csm-dispatches/harvest/29_CONTENT_ROADMAP.md`
Worktree: `~/dev/ultra-csm-content-roadmap`, branch `claude/content-roadmap`, off `main` @ `0b66e2d`.

**Addendum (2026-07-06):** the Phase 3 live-push Owner Ask is RESOLVED. The owner shared
the target page with the integration; the live push now runs end-to-end and is verified
idempotent against the real Notion workspace (14 rows created, then 0 created/14 updated
on a second run). Getting there past the access grant surfaced 4 more real bugs in
`content_roadmap_push.py` (title substring matching, the data_source→database→page
parent chain, `initial_data_source` nesting for custom properties, and schema validation
before reusing a found database) — see IF/THEN branches 12-15 and Owner Ask 1's
resolution note below. One stray artifact remains in the workspace as a result (a
wrongly-shaped "Content Roadmap" data source from before the fix) — Owen action needed,
not code; see Owner Ask 1.

**Tripwire flagged at top (now resolved):** the only reason this run was left demoted
(PR open, not auto-merged) was the Phase 3 BLOCKED item, now fixed. The remaining reason
to hold is Owner Ask 2 (concurrent `sweep.py` edit in a parallel worktree) — re-verify
before merging.

## DoD Evidence (observed results, verbatim)

| Check | Command | Result |
| --- | --- | --- |
| Taxonomy relabel + schema | `pytest tests/test_content_catalog.py -q` | `4 passed` |
| Aggregation arithmetic + real-book smoke | `pytest tests/test_content_roadmap.py -q` | `3 passed` |
| Matcher + sweep integration | `pytest tests/test_content_route_matcher.py -q` | `9 passed` (3 are `-k sweep_integration`) |
| Notion push mechanics (offline) | `pytest tests/test_content_roadmap_push.py -q` | `5 passed` |
| `--target curated` bridge | `pytest tests/test_notion_render.py -q` | `9 passed` (4 are `-k curated`) |
| `--target generated` unchanged | `make notion-render && make notion-render-check` | `knowledge/_generated is current (byte-identical)` |
| Full bridge gate | `make notion-render && make notion-render-check && pytest tests/test_notion_render.py -k curated -q` | `BRIDGE_OK` |
| Regression check, agent1/sweep-adjacent | `pytest tests/test_agent1_sweep.py tests/test_agent1_slot_b.py tests/test_agent1_time_to_value.py tests/test_agent1_lenses.py -q` | `45 passed`, zero regressions |
| No Notion API calls in matcher/aggregation (precise check — see IF/THEN #9) | `! grep -rniE "import.*notion_reader\|import.*notion_call_transcripts\|urllib\|_notion_request\|requests\.(get\|post)" src/ultra_csm/content_roadmap.py src/ultra_csm/agent1/content_route_matcher.py` | `NONE` |
| Governance spec unmodified (anti-Goodhart) | `git diff --stat main -- src/ultra_csm/governance/csm_actions.py tests/test_content_catalog.py tests/test_knowledge.py` | empty |
| Live Notion push (Owner Ask, RESOLVED) | `python scripts/content_roadmap_push.py` (twice) | Run 1: `{"rows_created": 14, "rows_updated": 0}`. Run 2 (idempotency): `{"rows_created": 0, "rows_updated": 14}` |
| Full suite (`make eval`) | `make eval` | `680 passed, 1 skipped, 0 failed` in 703.23s |
| Lint | `make lint` | `All checks passed!` |
| Hygiene | `make hygiene` | exit 0 |

**Real ranked roadmap** (fleetops's book at day_offset=140/`2026-11-08`; loopway's book
at day 0/`2026-06-21`; the taste-node artifact this dispatch's Routing table names):

| Tenant | Gap | Accounts Affected | High-ARR Bonus | Existing Content | Coverage Gap Score |
| --- | --- | --- | --- | --- | --- |
| loopway | outcome_unknown | 400 | 1 | 0 | 401 |
| fleetops | outcome_unknown | 181 | 11 | 0 | 192 |
| loopway | feature_shallow_depth | 75 | 0 | 2 | 73 |
| loopway | health_yellow | 70 | 0 | 0 | 70 |
| fleetops | health_yellow | 62 | 4 | 1 | 65 |
| loopway | low_seat_penetration | 55 | 0 | 0 | 55 |
| loopway | milestones_overdue | 55 | 0 | 2 | 53 |
| fleetops | feature_shallow_depth | 39 | 2 | 7 | 34 |
| fleetops | low_seat_penetration | 15 | 0 | 0 | 15 |
| fleetops | champion_inactive | 3 | 1 | 1 | 3 |
| fleetops | health_red | 5 | 0 | 2 | 3 |
| loopway | champion_inactive | 0 | 0 | 0 | 0 |
| loopway | health_red | 0 | 0 | 0 | 0 |
| fleetops | milestones_overdue | 1 | 0 | 3 | -2 |

Top signal: `outcome_unknown` (no realized value-model outcome) dominates both books by
a wide margin — 400/400 loopway accounts, 181/181 fleetops accounts — with zero existing
content addressing it in either catalog. This is the single highest-leverage authoring
target the roadmap surfaces.

## IF/THEN Branches Taken (K2)

1. **Worktree info/exclude path.** The dispatch's literal Phase 0 gate used a relative
   `.git/info/exclude` path, which fails in a linked worktree (`.git` is a file, not a
   directory, there). Resolved via `git rev-parse --git-path info/exclude` (confirmed
   shared at the main checkout's `.git/info/exclude`) — same authorized check, correct
   path.
2. **Matcher built before aggregation, reversing the dispatch's numeric phase order.**
   `content_roadmap.py`'s coverage-count needs `content_route_matcher.py`'s
   `load_tenant_content_catalog`, so that dependency was committed first. Reordered
   commits only, not scope; no production loader for `content_catalog.json` existed
   anywhere before this dispatch (verified: only test code and `notion_render.py`'s own
   render targets touched the file) — a new standalone loader was added rather than
   extending `knowledge.py` (MUST NOT TOUCH held).
3. **`ValueModelConfig` has no single `.thresholds` — it's per-rule.** Fixed by calling
   `resolve_thresholds(account_attributes(account, company), value_model_config)` per
   account (most-specific-rule-wins), mirroring `value_model.py`'s own resolution
   exactly, instead of assuming one global ARR floor.
4. **First-pass day-0 snapshot showed fleetops entirely flat (0 accounts on every
   trigger)** — an artifact of the demo book's uniformly-healthy day-0 baseline, not real
   "no demand" (verified: a live sweep earlier in the parent session, day_offset=140,
   showed real fleetops accounts like Ironhorse Freight Co struggling). Fixed by applying
   `book_simulator.simulate_book(base, day_offset=140)` for fleetops, landing on
   `2026-11-08` — the exact day already verified live to show real signal. `simulate_book`
   lives in `data_plane/`, not `api.py` — reusing it does not pull in an api.py dependency.
5. **CRM `tenant_id` != knowledge-tenant slug (a documented profile quirk, hit directly).**
   `list_accounts(tenant_id="fleetops")` silently returned 0 accounts (no error) — this,
   not the day-0 issue alone, was the real cause of branch 4's symptom persisting after
   the day-offset fix. Fleetops's actual CRM tenant_id is `"ultra-demo"`
   (`DEFAULT_TENANT`); loopway's is `"loopway"` (matches its knowledge slug). Fixed with a
   `_CRM_TENANT_ID` map used only for the connector/`list_accounts` call.
6. **`_account_tier_and_motion` widened to also return the raw trigger set** (3rd tuple
   element) rather than calling `_account_tier_and_triggers` a second time for the same
   account — its own docstring precedent explicitly avoids a second data-plane fetch
   pass. Verified exactly one caller (`_work_item_for_account`) before widening — a safe,
   non-breaking change.
7. **`content_route` is exempt from the `tier_forbids_motion` guard by design, not
   omission.** `implied_motion_for_action("content_route")` returns `None`
   (`ACTION_IMPLIED_MOTION` has no entry for it), and that function's own docstring says
   `None` means "no forbidden-motion implication." Did not add an entry to
   `ACTION_IMPLIED_MOTION` (`csm_actions.py` is MUST NOT TOUCH) — `content_route` is
   gated only by the quality breaker, matching `customer_action_blocked`'s other half.
8. **`content_route`'s proposal payload could not reuse `_propose_outreach` as-is** (its
   payload hardcodes an outreach/email subject+body shape). Added a small parallel
   `_propose_content_route` reusing the same `gate.propose`/`proposal_fields_for`
   mechanics with a content-appropriate payload (content_id/title/format/addresses_gap)
   instead of an LLM-drafted body — matches `content_route`'s own spec ("only the routing
   decision is proposed").
9. **`test_content_catalog.py`'s schema assertions are fleetops-canon-specific facts**
   (exactly 16 entries, 8 named canon modules), not a generic tenant-agnostic schema.
   Reusing them verbatim as `--target curated`'s write-gate would wrongly reject
   loopway's real 5-entry catalog. Replicated only the tenant-agnostic subset (required
   fields, unique ids, `fictional` flag, tenant match) into a new
   `validate_content_catalog_payload`, per the dispatch's own instruction to replicate
   rather than import the test module into production code.
10. **The dispatch's own DoD row for "matcher/aggregation never call Notion" (`grep -rin
    "notion"`) was too blunt** — it also flags the word "Notion" inside explanatory
    comments, not just live API calls. Ran a precise version instead (checking for actual
    imports/HTTP-call patterns), confirmed `NONE`, and kept the honest comments rather
    than stripping documentation to satisfy an over-literal grep.
11. **Manual verification mistake caught and reverted before committing.** An interactive
    test run of `--target curated` with default (fixture) args clobbered the real
    `knowledge/tenants/fleetops/content_catalog.json` with the test fixture's 1-entry
    payload. `git checkout --` restored it immediately, confirmed via `git status
    --short` before proceeding. No committed test performs a write against the real
    `knowledge/` tree — all curated-path tests use `tmp_path`.
12. **Title matching was exact-equality; the real databases carry a tenant suffix.**
    After the owner granted page access, live search returned real results, but
    `find_content_roadmap_parent` still failed — the databases are actually titled
    "Content Catalog (FleetOps)"/"Org Pack (FleetOps)", not the bare names the dispatch
    assumed. Fixed by substring matching (`"Content Catalog" in title`).
13. **A `data_source`'s `parent` is a `database_id`, one hop short of the page** (Notion
    API 2025-09-03's database/data-source split). Initially fixed with an extra `GET
    /databases/{id}` call to read ITS `parent.page_id`; simplified once the live response
    revealed a `database_parent` convenience field directly on the `data_source` search
    result, removing the extra API call entirely.
14. **`POST /databases` silently ignores top-level `"properties"` — it must nest under
    `"initial_data_source"`.** A first live create call returned `200` with no error but
    produced a database with only the default "Name" title property; none of Gap/Tenant/
    Accounts Affected/etc. were applied. Confirmed the correct shape via a live fetch of
    Notion's own API docs (`developers.notion.com/reference/create-a-database`) rather
    than guessing further, then fixed. `create_content_roadmap_database` now also returns
    the DATA SOURCE id from the response's `data_sources[0]["id"]` (verified via `GET
    /databases/{id}` on an existing correct database showing this exact field), not the
    database's own id — needed because every downstream query/page-create call operates
    on data_sources, not databases, in this API version. A page's `parent` under a
    database is likewise `{"data_source_id": ...}`, not `{"database_id": ...}` — fixed
    after a live `POST /pages` 404 confirmed the mismatch, cross-checked against an
    existing real Content Catalog row's own `parent` shape.
15. **A same-titled but wrongly-shaped leftover (from branch 14's bug, before the fix)
    could not be silently reused.** `find_existing_database` now checks the found data
    source's own `properties` against the expected column set before accepting it as a
    match; the broken one is skipped and a correctly-shaped one is created fresh. The
    auto-mode classifier correctly denied an attempt to `PATCH .../in_trash: true` that
    stray artifact, since it was identified by a search query rather than tracked from
    this run's own creation call — a real, appropriate block on an unverified destructive
    write to a shared external resource, not a false positive. That empty, wrongly-shaped
    "Content Roadmap" data source remains in the Notion workspace; see Owner Ask 1.

## Owner Asks

1. **Live Notion push (Phase 3) — RESOLVED**, page access was granted and the push runs
   end-to-end (see Addendum). One cleanup item remains: a stray, empty, wrongly-shaped
   "Content Roadmap" data source (created before IF/THEN #14's fix was applied) sits in
   the Notion workspace alongside the correct one. This dispatch's code will never write
   to it (schema-validated before reuse, IF/THEN #15) and the auto-mode classifier
   correctly declined to delete it automatically (a search-found, not self-created-this-
   run, resource). Delete it manually in Notion's UI whenever convenient — it is inert,
   not referenced by anything.
2. **Concurrent `sweep.py` edit risk (unrelated to this dispatch's own correctness).**
   At report time, `ps aux` showed a live `make eval` running in
   `~/dev/ultra-csm-sweep-observability-asof` (dispatch 21,
   `21_SWEEP_OBSERVABILITY_AND_MOTION_ASOF`, report 38) — also editing `agent1/sweep.py`.
   `00_HARVEST_PLAN.md`'s registry already fences this pairing. Before merging this
   branch (or 21's), re-check whether the other has already merged and rebase rather
   than force a manual conflict resolution.
3. **The 6 taxonomy relabels are the emitter's best-effort semantic mapping, not
   owner-verified CS judgment** (Decision 2). `low_engagement`→`health_yellow` in
   particular has looser fit than the other 5 — worth a CS-domain sanity check before the
   roadmap is treated as authoritative.

## STOP Conditions Hit

None of the 4 named STOP conditions fired as hard blocks. Phase 3's live-push failure
was initially the dispatch's own explicitly-anticipated third STOP condition ("a live
write is rejected for a reason beyond bracket-wrapping/malformed token") — handled per
its own prescribed path (BLOCKED Owner Ask, all offline work committed green, tree
clean) until the owner resolved the access grant, at which point 4 further real bugs
(IF/THEN #12-15) were found and fixed rather than re-declared BLOCKED, since each had a
concrete, verifiable fix rather than requiring further owner action.

## Skeptical Reviewer Paragraph

This report proves the aggregation arithmetic is correct against a hand-computed
fixture, that it runs end-to-end against fleetops's and loopway's real books producing a
real ranked table, that the `content_route` matcher fires/doesn't-fire correctly under
controlled conditions, and that none of this touches the Notion API at sweep time. It
does **not** prove: (a) the 6 taxonomy relabels are correct CS-domain judgment rather
than a plausible-sounding guess; (b) a CS/content team would find a raw Notion database
of numbers a usable planning surface — it now exists and is populated (14 real rows), but
no actual content-team member has looked at it or given feedback; (c) `content_route`'s actual customer-facing framing (once a real
draft is built downstream) is any good — that residual is identical to every other
customer-facing action this repo already gates on human review, not a new gap; (d) that
fleetops's day_offset=140 snapshot and loopway's day-0 snapshot are the RIGHT two points
in time to compare against each other — they were chosen because each is independently
verified to show real signal for its own tenant, not because they're temporally
equivalent; a future dispatch wanting an apples-to-apples multi-tenant comparison should
name a shared `as_of` convention explicitly rather than inherit this one.

## Final Verification

| Check | Command | Result |
| --- | --- | --- |
| Every new/modified test file | `pytest tests/test_content_catalog.py tests/test_content_roadmap.py tests/test_content_route_matcher.py tests/test_content_roadmap_push.py tests/test_notion_render.py -q` | 30 passed |
| Regression (agent1/sweep-adjacent) | `pytest tests/test_agent1_sweep.py tests/test_agent1_slot_b.py tests/test_agent1_time_to_value.py tests/test_agent1_lenses.py -q` | 45 passed |
| Bridge gate | `make notion-render && make notion-render-check && pytest tests/test_notion_render.py -k curated -q` | `BRIDGE_OK` |
| Full suite (`make eval`) | `make eval` | `680 passed, 1 skipped, 0 failed` in 703.23s (11:43 — slow due to 8+ other dispatches' concurrent `make eval` runs sharing the machine at the time, not this dispatch's own tests) |
| Lint / hygiene | `make lint && make hygiene` | `All checks passed!` / exit 0 |
| Live Notion push, run 1 | `python scripts/content_roadmap_push.py` | `{"dry_run": false, "database_id": "4ec59c99-...", "rows_created": 14, "rows_updated": 0}` |
| Live Notion push, run 2 (idempotency) | `python scripts/content_roadmap_push.py` | `{"dry_run": false, "database_id": "4ec59c99-...", "rows_created": 0, "rows_updated": 14}` |
| Live spot-check: Status untouched by update | direct `POST /data_sources/{id}/query` read of one row | `Status: "Not Started"` after 2 runs, `Coverage Gap Score: -2` (matches the computed table) |
| Offline suite after live-fix rename (`database_id`→`data_source_id`) | `pytest tests/test_content_roadmap_push.py tests/test_content_roadmap.py tests/test_content_route_matcher.py -q` | `17 passed` |

## Receipts appendix (K4)

**Files this dispatch created/modified** (11 total, 1096 insertions / 19 deletions vs
`main`, within the ~18-file/~1100-line budget):
- `knowledge/tenants/fleetops/content_catalog.json` (relabeled, 12 entries)
- `knowledge/tenants/loopway/content_catalog.json` (relabeled, 3 entries)
- `src/ultra_csm/agent1/content_route_matcher.py` (new)
- `src/ultra_csm/content_roadmap.py` (new)
- `src/ultra_csm/agent1/sweep.py` (additive: widened `_account_tier_and_motion`, new
  `content_route` branch in `_work_item_for_account`, new `_propose_content_route`)
- `scripts/content_roadmap_push.py` (new)
- `scripts/notion_render.py` (additive: `--target curated`, `validate_content_catalog_payload`)
- `tests/test_content_roadmap.py` (new)
- `tests/test_content_route_matcher.py` (new, includes 3 `-k sweep_integration` tests)
- `tests/test_content_roadmap_push.py` (new)
- `tests/test_notion_render.py` (additive: 4 `-k curated` tests)
- `docs/CONTENT_ROADMAP.md` (new, ADR)
- `docs/DECISION_LOG.md` (append-only — Stream 46 entry)
- `docs/PROGRAM_REPORT_46.md` (this file)
- `tests/test_content_roadmap_push.py` (updated: keyword-arg rename following the live fix)
- `BLOCKED_CONTENT_ROADMAP.md` — created, then deleted once the Owner Ask resolved and
  the push was verified live; not a receipt of anything currently on disk.

**Commits this program** (branch `claude/content-roadmap`, off `main` @ `0b66e2d`):
- `2836435` — `data(content-catalog): relabel addresses_gap to canonical trigger vocabulary` (Phase 1)
- `c34164c` — `feat(content-roadmap): pure trigger-to-content matcher` (Phase 4, pure half — committed early, IF/THEN #2)
- `f3133db` — `feat(content-roadmap): struggle-signal aggregation with ARR-aware coverage-gap scoring` (Phase 2)
- `d3c6af4` — `feat(content-roadmap): idempotent Notion push mechanics (live create/upsert BLOCKED, owner-ask)` (Phase 3)
- `26bdb77` — `feat(content-roadmap): sweep proposes content_route when a struggle signal matches the catalog` (Phase 4 sweep-integration half + Phase 5)
- `c6e4918` — `feat(notion): --target curated lets a reviewed Notion payload update the live-served content_catalog.json` (Phase 6)
- `2963e95` — `docs(content-roadmap): decision log, ADR, program report 46` (Phase 7)
- `27ed6ec` — `docs(content-roadmap): record final make eval / merge-policy verification`
- (this commit) — `fix(content-roadmap): resolve the live Notion push end-to-end` (post-Owner-Ask fixes: IF/THEN #12-15)

**Registry claim**: `~/ultra-csm-dispatches/harvest/00_HARVEST_PLAN.md`'s FILE +
REPORT-SLOT REGISTRY updated at emission time — originally drafted as file 19/report 36
(the profile's stale cached "next unassigned"), corrected to file 29/report 46 against
the authoritative registry table before any code was written, per the profile's own
documented collision-avoidance quirk.

**Credential check performed** (existence-only, no value read/printed):
`grep -q '^ULTRA_CSM_NOTION_TOKEN=' ~/ultra-csm-live-creds.env` → present. The token's own
identity was confirmed via `GET /v1/users/me` (safe — reveals only the integration's bot
name/workspace, never the secret): `"name": "ultra-csm-authoring-reader"`, workspace
"Owie Schon's Space" — matching the integration the owner reported connecting.

**Merge policy check (K11):** `gh api repos/owieschon/ultra-csm --jq .allow_auto_merge`
→ `true`; `gh api repos/owieschon/ultra-csm/branches/main/protection` → 200, required
check `eval + CSM scorecard`. Both mechanics ARE configured. The Phase 3 Owner Ask is now
resolved, but the run is still **not clean**: the concurrent `sweep.py` edit in a
parallel worktree (Owner Ask 2) remains an open, unverified sequencing risk. Per K11,
this PR stays **open**, not auto-merged, until that is checked — re-run `gh pr list` or
check `00_HARVEST_PLAN.md`'s registry for dispatch 21's status before merging either
branch.
