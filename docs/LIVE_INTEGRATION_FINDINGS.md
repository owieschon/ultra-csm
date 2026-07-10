# Live Integration Findings — Program 3, Phase 3

Battery matrix for the live conversational-onboarding path
(`ingest_table`/`confirm_book`/`ingest_book`) against corpus B, run over a
live stdio MCP server session. All records were seeded by this program in
Phase 2E (`~/ultra-csm-corpus-runs/seed-2e-20260703/`, tagged `UCSM-P3E`,
create-only). Assertions are exact numbers against the seed ledger's ground
truth — not tolerances. Run artifacts:
`~/ultra-csm-corpus-runs/phase3-live-battery-20260703/`.

## Battery matrix

| Dataset | Path | Typed (Account/Contact/Opp) | FK orphans (Contact/Opp) | Injection markers | Replay deterministic |
| --- | --- | --- | --- | --- | --- |
| D1 volume | `ingest_table`×3 + `confirm_book` | 8 / 16 / 12 (exact) | 0 / 0 (exact) | 0 (exact) | Yes |
| D2 hostile text | `ingest_table`×3 + `confirm_book` | 4 / 6 / 4 (exact) | 0 / 0 (exact) | 14 / 14 (exact) | Yes |
| D3 sparse | `ingest_table`×3 + `confirm_book` | 5 / 8 / 5 (exact) | 0 / 0 (exact) | 0 (exact) | Yes |
| D4 broken joins | `ingest_table`×3 + `confirm_book` | 4 / 4 / 3 (exact) | 4 / 3 (exact) | 0 (exact) | Yes |
| D5 unmapped (Lead) | `ingest_book` | 0 accounts typed (exact) | n/a | n/a | n/a |
| D5 unmapped (Case) | `ingest_book` | 0 accounts typed (exact) | n/a | n/a | n/a |
| D6 volume-at-scale | `ingest_table`×3 + `confirm_book` | 20 / 500 / 60 (Contact truncated from 520) | 0 / 0 (exact) | 0 (exact) | Yes |

Every number above is the live response compared against
`ground_truth.json`, authored before any record was created. Zero
mismatches on the final run (`phase3_battery_report.json`: `"problems": []`,
`"ok": true`).

## What each dataset proved

- **D1 (volume):** the relational join holds at 8 accounts / 16 contacts /
  12 opportunities with zero orphans — the FK-join path scales past a
  single-digit book without degrading.
- **D2 (hostile text):** emoji, RTL Arabic, Japanese, embedded quotes/
  backslashes, JSON-lookalike strings, and zero-width characters in `Name`
  all typed correctly with exact counts; the injection sentence appears on
  every one of the 14 records carrying it (4 accounts + 6 contacts + 4
  opportunities) and the marker count matches exactly. The injected text
  never appears anywhere in the `confirm_book` response (asserted by
  substring search on the full serialized payload) — `Description` has no
  internal-field mapping on any of the three contracts, so the content
  never reaches mapped output at all; the marker count is a raw-record scan,
  independent of mapping.
- **D3 (sparse):** every optional field absent (no `Industry`, `Email`,
  `Amount`, `Type`). `CRMAccount.industry` correctly demanded human
  confirmation rather than auto-mapping — zero non-empty rows means zero
  auto-map evidence, and the system asked rather than guessed. All records
  still typed with exact counts.
- **D4 (broken joins):** half of D4's contacts (4/8) and half its
  opportunities (3/6) point at accounts from a different dataset (D1) —
  valid org ids, but outside D4's book when ingested alone. All 7 orphaned
  correctly (4 contact + 3 opportunity), rejected with
  `unresolved_parent_identity`, never attached to a fabricated parent. Zero
  false positives (no D4-internal child was misclassified as orphaned) and
  zero false negatives (no external-parent child slipped through as joined).
- **D5 (unmapped shapes):** Lead and Case have no source contract in this
  connector (`CRMAccount`/`CRMContact`/`CRMOpportunity` only). Relayed
  through the flat `ingest_book` path, zero accounts typed on both — no
  identity field ever auto-mapped (`auto_mapped_identity_count: 0` on both),
  confirming the system does not guess an account out of Lead/Case shapes
  it has no contract for.
- **D6 (volume-at-scale):** 20 accounts, 520 contacts (round-robin linked,
  the one table sized to exceed the relay), 60 opportunities. `ingest_table`
  on Contact reports `truncated: true`, `dropped_record_count: 20` (520 sent
  − 500 cap); `confirm_book` types `CRMContact` at exactly 500, never 520 —
  the first live exercise of `DEFAULT_MAX_RECORDS` against a real fetched
  dataset rather than a synthetic oversized payload. Account and Opportunity,
  both under the cap, type at their full seeded counts with zero truncation.
  Replay deterministic (`replay_sha256` identical across two `confirm_book`
  calls). Seed additive to Phase 2E — a new run directory and ledger, D1-D5's
  ledger/ground truth untouched (see `~/ultra-csm-corpus-runs/seed-2e-d6-20260703/`).

## Defect protocol outcome

Zero product defects surfaced by this battery. Two live findings did
surface, both handled without touching `src/`:

1. **Org-native duplicate-detection rule** (documented in
   `SALESFORCE_ONESHOT_FINDINGS.md`): the standard Contact fuzzy-duplicate
   rule blocked bulk same-`FirstName`-similar-`LastName` creates during
   seeding. Fixed by authoring distinct first names — a seeding-time
   workaround, not a product change, since ultra-csm never writes Contact
   records itself.
2. **Driver assumption gap, not a product gap:** the initial battery driver
   hardcoded confirmation answers assuming `Industry` always auto-maps
   (true for D1, where every account has a value). D2/D3/D4 correctly
   demanded human confirmation for `Industry` because those datasets have
   zero non-empty values for it — exactly the auto-map coverage threshold
   (Tier B requires ≥80% non-empty rows) doing its job. The driver was
   fixed to answer any unforeseen question `not_mappable` rather than
   assume; no test, no src file, and no confirmation logic changed.
3. **Org-native duplicate-detection rule, again, on D6:** despite every D6
   Contact having a globally-unique `FirstName` in this run, the org's fuzzy
   Contact-matching rule still blocked the second create batch — the
   matcher's `LastName` similarity check appears insensitive to the numeric
   suffix on the shared `UCSM-P3E-D6-C####` tag. Because D6 drives the REST
   API directly (unlike D1-D5's per-record MCP-tool creates, which expose no
   header control), the fix available here was Salesforce's own documented
   override, `Sforce-Duplicate-Rule-Header: allowSave=true`, applied only to
   the remaining D6 batches — a save-time override of a single write call,
   not an update/delete and not an org configuration change, so it does not
   depart from the program's create-only rule. A seeding-time workaround,
   not a product change.

## Regression trio (same commit as this battery)

| Command | Result |
| --- | --- |
| `make eval` | `418 passed, 1 warning` |
| `make relational-battery-csm` | `hard_ok: true`, `seeds: 20` |
| `make relay-battery-csm` | `passed: 11 / 11` |
| `make demo` | Passed; artifacts byte-unchanged (`git status --short` clean after run) |

## Scope not covered

- **D6 volume-at-scale** — done; see the D6 row above and the "What each
  dataset proved" note. Was deferred pending populated
  `~/ultra-csm-live-creds.env` for REST-composite batch creation; that
  credential is now populated and the `>500`-row cap has been exercised live.
- Update/delete paths were not exercised against corpus B; the program's
  standing rule is create-only writes against this org (see Defect protocol
  outcome, item 3, for the one save-time override D6 needed and why it
  doesn't depart from this rule).

# Live Integration Findings — Program 4, Rocketlane (corpus C)

Battery matrix for the live Rocketlane onboarding path
(`derive_ttv_milestones` over `parse_phase`/`parse_task`) against corpus C
(the Rocketlane trial org; see
`$HOME/ultra-csm-corpus-a-PRIVATE.md` for org identity, never
committed here). All records were seeded by
this program via the `mcp__rocketlane__*` MCP lane (2026-07-03, tagged
`UCSM-P4C`, create-only). Assertions are exact numbers against
`ground_truth.json`'s ground truth — not tolerances. Run artifacts:
`~/ultra-csm-corpus-runs/rocketlane-seed-20260703/`.

**Scope note (read before the matrix):** the Rocketlane MCP toolset
available in this environment has no `create_project` tool and no
template-instantiation tool (verified exhaustively — only `create_phase`,
`create_task`, `create_time_entry`, and `create_project_template` exist on
the write surface; the REST lane, which does document `POST /projects`,
remains 401-blocked, root cause undiagnosed same as R0). Every dataset
below is therefore a new **phase** (+ nested tasks) inside one of the two
pre-existing factory projects, not a distinct new project. The plan's
project-level join-set dataset (new projects with `externalReferenceId` set
to real Salesforce Account Ids) was not attempted — see the owner ask in
`docs/PROGRAM_REPORT_4.md`.

## Battery matrix

| Dataset | Host project | Milestone count | Achieved | Open gap | At-risk tasks | Activation-gap flag |
| --- | --- | --- | --- | --- | --- | --- |
| D1 healthy | Acme | 1 (exact) | 1 (exact) | 0 (exact) | 0 (exact) | False (exact) |
| D2 slipping | Modert | 1 (exact) | 0 (exact) | 1 (exact) | 0 (exact) | True (exact) |
| D3 at-risk cluster | Acme | 1 (exact) | 0 (exact) | 0 (exact) | 2 (exact) | True (exact) |
| D4 completed | Modert | 1 (exact) | 1 (exact) | 0 (exact) | 0 (exact) | False (exact) |
| D5 sparse | Acme | 1 (exact) | 0 (exact) | 0 (exact) | 0 (exact) | False (exact) |
| D6 join-set | — | not attempted | — | — | — | — |

Every number above is the live response (fetched fresh via
`get_phases`/`get_tasks`, 2026-07-03) parsed through the real R1 adapters
and compared against `ground_truth.json`, authored before any record was
created. Zero mismatches on the final run
(`r4_battery_report.json`: `"problems": []`, `"ok": true`).

## What each dataset proved

- **D1 (healthy):** a phase whose sole task is marked Completed produces an
  achieved `TimeToValueMilestone` — the outcome/TTV rail's "known" state,
  proven against a real API response, not a fixture.
- **D2 (slipping):** a phase past its due date with no actual date produces
  an open gap under Agent 1's existing, unchanged date-based filter — the
  same code path that already handled telemetry-sourced gaps now correctly
  handles Rocketlane-sourced ones.
- **D3 (at-risk cluster):** 2 of 3 tasks under a not-yet-overdue phase are
  `atRisk=true`. `has_activation_gap()` correctly returns `True` from the
  task-risk trigger alone, independent of the date-overdue trigger — proving
  the spec's three-way OR (`RUNNING_LATE` progress, `atRisk` task, or
  overdue-with-null-actual) is real, not just documented. This activation
  gap does not by itself clear Agent 1's sweep score threshold (which keys
  off the date-based `open_milestone_gaps` filter) — a scope note, not a
  defect; see `docs/PROGRAM_REPORT_4.md`.
- **D4 (completed):** all task/phase actuals set — an achieved milestone,
  the second exact-count confirmation.
- **D5 (sparse):** a task created with only `taskName`+`project` (no
  dates), exercising the connector's optional-field handling. The *phase*
  still carries real dates, so one milestone is correctly emitted — sparse
  at the task grain, not the phase grain.
- **D6 (join-set):** not attempted — see the scope note above.

## Live findings

1. **Auto-completion cascade (D1, D4):** completing a phase's only/last open
   task auto-completes the phase and sets both `startDateActual` and
   `dueDateActual` to the write date (server "now"), not any
   caller-supplied value. Not documented in the spec doc; discovered live
   during seeding. `ground_truth.json` was corrected after observing this
   (never faked before the write). No product code change — the connector
   correctly reads whatever the API returns.
2. **Phase `dueDate` recalculation (D2, D3):** creating a task under a phase
   recalculates the phase's `dueDate` to the task's `dueDate`, overriding
   whatever `dueDate` was passed to `create_phase`. Also undocumented in the
   spec doc; corrected into ground truth after observation. Both datasets'
   intended semantics (overdue for D2, far-future for D3) survived the
   recalculation.
3. **`inferredProgress` absent from live payloads (R1, re-confirmed R3/R4):**
   even with `includeAllFields=true`, `get-project` responses for both
   factory projects never include an `inferredProgress` key. The parser's
   fail-safe default (`"none"`) handled this correctly throughout.
4. **`get_phases` search vs. detail shape (R1):** the search/list shape
   returns only `{phaseId, phaseName}` — no `project`, no dates. Only the
   detail-by-id shape (`get_phases(phaseId=...)`) carries `project.projectId`
   and dates. `parse_phase` requires the detail shape and raises on the thin
   search shape; the live seeding/battery code always fetched detail.

## Cross-system beat

One real corpus B (Salesforce) account, read live via a single read-only
SOQL query (`WHERE Name LIKE 'UCSM-P3E-D1%'`), joined in-memory to D2's live
Rocketlane evidence and driven through Agent 1's unchanged sweep logic with
a real `ActionGate`. The proposal's priority factors cite
`EvidenceRef(source="rocketlane", ...)` entries whose `source_id`s are the
real live Rocketlane phase/task ids — proving a cross-system TTV proposal
with per-source claim boundaries intact. Salesforce was never written to.
Test: `tests/test_rocketlane_cross_system_beat.py` (env-gated; the real
account id is never committed — see the test's docstring).

## Regression trio (same commit as this battery)

| Command | Result |
| --- | --- |
| `make eval` | `450 passed, 1 skipped` (the cross-system-beat test skips without live env vars) |
| `make relational-battery-csm` | `hard_ok: true`, `seeds: 20` |
| `make relay-battery-csm` | `passed: 11 / 11` |
| `make demo` | Passed; `git status --short` clean after run |

## Scope not covered

- **D6 join-set** — not attempted. Requires a new Rocketlane project per
  Salesforce account with `externalReferenceId` set; no tool to create a
  new project exists in this environment's MCP surface, and the REST lane
  is 401-blocked. See the Consolidated Owner Ask in
  `docs/PROGRAM_REPORT_4.md`.
- Update/delete paths beyond the two `update_task` status changes on
  records created this run were not exercised — the program's standing
  rule is create-only.

# Live Integration Findings — Program 7, Live Narrative Seeding

The Synthetic Tenant Universe (six arcs, PR #13) built rich causal-exhaust
fixtures — email/calendar/ticket/Rocketlane content authored to tell each
arc's story — entirely offline. This program seeds that same content into
the real, live orgs, and reads it back through the unmodified product code
path (the same `*_communication_signals` extraction functions and Rocketlane
`derive_ttv_milestones`/`has_activation_gap` bridge the fixture-based U1
pilot proved), to close the gap between "rich but simulated" and "real but
thin" that Programs 3/4/synthetic-universe each left open on their own.

## What "live" honestly covers, and what it does not

Three real, hard walls were found and are why this program's live scope is
narrower than "all six arcs, every channel, live":

1. **Salesforce `Case.CreatedDate` is not writable in this org** (a live
   `INVALID_FIELD_FOR_INSERT_UPDATE` 400 on a direct probe — this needs a
   special "Set Audit Fields upon Record Creation" permission this org's
   connected app does not have). Combined with Program 3's D5 finding that
   this connector has no live `CRMCase` parser at all, seeding Cases here
   would create undated, unread clutter with zero proof value. Skipped.
2. **Health-band/adoption-rate/usage signals are fixture-only architecture-
   wide.** No live CS-platform/telemetry connector exists anywhere in this
   codebase (already disclosed in Program-6's `live_semantic_quality`
   claim_boundary). Several arcs' core signal (Aspenridge's usage decline,
   Meridian's usage growth) is inherently this kind of data. Not buildable
   within this program's scope.
3. **No Rocketlane project-creation tool exists, MCP or REST** — the exact
   wall Program 4 hit. New Rocketlane content is new phases/tasks inside
   the existing Acme project, not a dedicated new project per arc.

What genuinely went live: **Rocketlane** (Pinehill's onboarding-stall
phases/tasks) and **Gmail** (all six arcs' full email history, 113
messages, via IMAP `APPEND` with a custom `INTERNALDATE`).

## The future-dating wall (Gmail), and why the seeded data is still correct

The six arcs' scripted timeline runs from `SEED_DATE` (2026-06-21) out to
day 365 (~2027-06-21) — but the real calendar date this program ran on was
2026-07-04. Only the first ~13 days of each arc's timeline are genuinely in
the past; the rest is, from *this* moment's perspective, in the future.
Gmail's IMAP `APPEND` silently substitutes the current server time for any
requested `INTERNALDATE` in the future rather than erroring — caught only
by post-write verification (97 of 113 messages showed today's date instead
of their intended historical date). This is a hard, correct constraint of
any real mail system (a message cannot be "received" before it exists), not
a bug to route around.

It does not corrupt the seeded data's usefulness: `reply_latency_trend` and
every other extraction function reads the message's `Date:` **header**
content, never `INTERNALDATE` — confirmed by grep before deciding whether to
delete and redo anything. All 113 messages' Date headers are correct,
verified by direct IMAP fetch. The only real-world effect is cosmetic: a
human scrolling the mailbox's native "received" sort order would see these
messages clustered oddly rather than spread across the story's timeline;
the product's own live-read path is unaffected.

## Live-read wiring (Workstream 4)

`src/ultra_csm/data_plane/live_gmail_reader.py`: reads real IMAP messages
into the exact Gmail `users.threads.get` shape the fixture comms modules
already produce. Rather than duplicating the six arcs' extraction logic,
each `*_communication_signals` function gained a minimal, backward-
compatible optional `thread=`/`threads=` parameter (defaults to the fixture
call unchanged) — the same well-tested extraction code now drives off live
data with zero duplication.

## Battery matrix — live read-back vs. the known fixture ground truth

| Check | Live result | Fixture ground truth (u1_pinehill_pilot.json) |
| --- | --- | --- |
| Pinehill reply-latency trend @ day 50 ("during") | 32.9h | 32.0h |
| Pinehill reply-latency trend @ day 310 ("after") | 9.8h | 10.0h |
| Rocketlane Kickoff activation gap | `False` (completed) | `False` |
| Rocketlane Legacy Dispatch Integration activation gap | `True` (at-risk task) | `True` |
| Quarrystone signal count | 2 (exact) | 2 |
| Aspenridge signal count | 10 (exact) | 10 |
| Pinnacle signal count | 12 (exact) | 12 |
| Meridian raw message count | 50 (exact) | 50 |
| Trailhead reply-latency @ two checkpoints | -0.8h, insufficient-history | flat/low, matching control |

Live numbers land within ~1 hour of the fixture-derived ground truth (the
deterministic minute/second jitter added at seed time accounts for the
difference) — the same story, read through the real product surface
instead of a fixture. Full run artifact:
`~/ultra-csm-corpus-runs/live-narrative-seeding-20260704/live_battery_report.json`
(`"problems": []`, `"ok": true`).

## Rocketlane live quirks, exercised again and handled without faking history

Both quirks Program 4 discovered fired again exactly as documented:
completing Kickoff's one task auto-completed the phase, stamping actual
dates to the write day (2026-07-03/04 — a few days after its June 28
planned due date, a realistic "completed a bit late," not a nonsensical
value); creating tasks under Legacy Dispatch Integration recalculated the
phase's `dueDate` to the last-created task's `dueDate` (day 90). Rather than
fight these quirks to fake a specific historical checkpoint (mechanically
impossible — actual/completion dates can only be "now" or null, never a
chosen past value, the same root constraint as Gmail's), the seeded
Rocketlane state represents the arc's **current live truth**: Kickoff done,
Legacy Dispatch Integration genuinely open with an at-risk task — which
*is* the "during the stall" activation-gap-true state, achieved honestly.

## Regression trio (same commit as this battery)

| Command | Result |
| --- | --- |
| `make eval` | `454 passed, 1 skipped` |
| `make relational-battery-csm` | `hard_ok: true`, `seeds: 20` |
| `make relay-battery-csm` | `passed: 11 / 11` |
| `make narrative-battery-csm` | `hard_ok: true`, `cases: 8`, `failed_cases: []` |
| `make demo` | Passed; `git status --short` clean after run |

## Scope not covered

- Salesforce Cases and Calendar events for any arc (see the three walls
  above) — Calendar additionally blocked on a missing credential
  (`ULTRA_CSM_CALENDAR_OAUTH_REFRESH_TOKEN` was never set up).
- Live-read wiring was built and proven for Gmail only; Rocketlane's live
  read path already existed from Program 4.
- Meridian and Pinnacle's live-read verification in this run checked raw
  message/signal counts rather than full per-contact latency-trend
  comparison (their extraction functions attribute signals across two
  contacts sharing one email domain, which the generic live reader merges
  into one thread) — a real, disclosed simplification, not a silent gap.

# Live Integration Findings — Program 9, Anchor-Translated Re-seed

Program 8 enriched all six arcs' content offline; Program 7's live seed
still carried the old one-line-snippet bodies and a fixed calendar that
put most of the story in the unreachable future. This program re-seeded
the live world under **anchor translation**: `SEED_DATE` stays 2026-06-21
in code forever; a frozen, run-directory `anchor.json` maps story day 0 to
a real calendar date (anchor = seed-run date − 50, so story day 50 = the
day the backfill ran — the bible's own "during the stall" checkpoint for
Pinehill). All seeding tooling translates at the boundary; no fixture, no
battery, no test changed a single date. Run artifacts:
`~/ultra-csm-corpus-runs/live-reseed-20260704/`.

## What the anchor design bought, verified live

| Claim | Program 7 result | Program 9 result |
| --- | --- | --- |
| Gmail `INTERNALDATE` matches the `Date:` header | 16/113 correct (future-dated APPENDs silently reset to "now") | **33/33 correct** — the day≤50 backfill is entirely past-dated, and drip-seeded messages land on their real day by construction |
| Email bodies | one-line snippets | full enriched bodies; per-arc round-trip byte-identical after CRLF normalization, all six arcs |
| Reply-latency fidelity (Pinehill, day 50) | 32.9h vs fixture 32.0h | **32.9h vs fixture 32.0h** — same value, now computed across two calendars (live as_of = anchor+50, fixture as_of = seed+50), proving the extractors' translation invariance live |
| Per-arc message counts | exact | exact (8/2/2/6/2/12 = 32), derived from the fixtures at check time, never hardcoded |
| Calendar | not seeded (credential missing) | **159 events live, full 365-day year** (Calendar has no date wall; future meetings are realistic). 2 cancelled fixture events skipped — create-only forbids the create-then-cancel dance, and `meeting_cadence_shift` only reads confirmed events anyway |

## The OOO guard, proven end to end

New in this program (commit `Reseed R1`): `live_gmail_reader` excludes
messages carrying an RFC 3834 `Auto-Submitted` header (value ≠ `no`). The
threat is concrete: a real out-of-office auto-reply quotes the tagged
subject and comes from the contact's real domain, so it passes the
tag+domain search and would register as a near-instant customer reply,
deflating `reply_latency_trend` and hiding a genuine responsiveness-risk
signal. The live proof is a deliberately seeded OOO from the Pinehill
champion, 2 minutes after the CSM's day-22 outbound: the battery asserts
it (a) exists in the raw mailbox, (b) is absent from the extracted
thread, and (c) leaves Pinehill's day-50 latency at 32.9h — without the
guard, that number would have collapsed toward zero. Six unit tests
cover the guard offline, including a demonstration that the unguarded
reading is deflated.

## Noise layer (live-mailbox-only, never in fixtures)

Three distractor artifacts seeded alongside the signal: the OOO above, a
fictional "FleetOps Platform Digest" newsletter (untagged sender — the
tag filter must and does exclude it), and a Rocketlane-style transactional
notification referencing Pinehill's real seeded Kickoff phase. Fixtures
stay 100% signal by design; the mailbox no longer does — which is what
makes the reader's filtering a tested claim instead of an untested one.

## The drip-seeder (the story now unfolds in real time)

`drip_seed.py` + `com.ultracsm.narrative-drip` (launchd, daily 07:00,
owner-authorized explicitly after an auto-mode safety stop — a standing
job that writes to a live mailbox is not something "execute the dispatch"
covers on its own). Each morning it computes the current story day from
the frozen anchor and appends exactly the messages that have come due —
idempotent via ledger, resumable, clean no-op verified via a manual
`launchctl kickstart` on install day (story day 50, nothing new due).
Next scheduled beats: story day 60 (Pinehill's "third integration issue"
email) lands 2026-07-14; the day-80–87 escalation window lands
2026-08-03–10; Monica Reeves first emails from Pinnacle on 2026-09-02.
At story day 100 the job logs a loud reminder that Pinehill's Rocketlane
"Validate dispatch event delivery" task should be completed live that day
(it cannot do this itself; see below).

## Rocketlane REST: still down, re-diagnosed

The key in `~/ultra-csm-live-creds.env` returns 401 `NOT_AUTHORIZED` on
`GET /projects`, persisting across a 60s retry and a curl retry (ruling
out the local Python cert issue that surfaced separately). The fresh key
verified working on 2026-07-03 either was never written to the env file
or has been invalidated — undiagnosable further without the owner's
Rocketlane console. The capability probe (`POST /projects`) and any
per-arc project seeding remain blocked; carried forward as the same open
ask from Programs 4 and 7.

## Scope not covered

- Salesforce Cases: unchanged walls (CreatedDate not writable, no live
  CRMCase parser) — case evidence reaches the agent via the fixture
  adapter on the same story clock.
- A live calendar reader (mirroring `live_gmail_reader`) is not built;
  the battery records the fixture's day-50 Pinehill cadence value (0.0,
  steady) as the target a future reader must reproduce.
- Meridian/Pinnacle per-contact latency comparison: same disclosed
  merged-thread simplification as Program 7; counts are exact.
