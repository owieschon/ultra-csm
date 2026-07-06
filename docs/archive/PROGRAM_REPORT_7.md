# Program Report 7

Branch `claude/live-narrative-seeding` off synced `main` (includes merged
PR #13, the Synthetic Tenant Universe). Program 6 (close-the-loops, PR
pending as of this report) proved the pipeline correct on thin live CRM
data and lit up the quality/action loops; Program 13 built rich six-arc
narrative content entirely offline. This program seeds that same authored
content into the real live orgs and reads it back through the unmodified
product code path, closing the gap between "rich but simulated" and "real
but thin" that both left open independently.

## DoD Evidence

| Workstream | Result | Evidence |
| --- | --- | --- |
| Baseline (read-only) | Complete | Salesforce (54 accounts/578 contacts/118 opps/28 leads/31 cases, factory+prior-program totals reconcile exactly), Rocketlane (2 factory projects, 7+8=15 pre-existing phases), Gmail (6 baseline INBOX messages) snapshotted before any write. `~/ultra-csm-corpus-runs/live-narrative-seeding-20260704/00_*.json`. |
| Scope rescoping (3 hard walls found) | Complete, documented | Salesforce `Case.CreatedDate` confirmed not writable (live 400, `INVALID_FIELD_FOR_INSERT_UPDATE`) and no live `CRMCase` parser exists anywhere (Program 3's D5); health/adoption/usage signals are fixture-only architecture-wide (no live CS-platform/telemetry connector exists anywhere in this codebase); Rocketlane has no project-creation tool, MCP or REST (same wall as Program 4). Live scope narrowed to Rocketlane (Pinehill) + Gmail (all six arcs) *before* writing anything, not discovered mid-write. |
| Gmail seeding | Complete, 113/113 messages | `det_jitter_minutes` added to `platform/seed.py` (extends `det_uuid`'s exact hash pattern) for deterministic non-round timestamps. All six arcs' full email history (Pinehill 18, Aspenridge 10, Meridian 50, Pinnacle 12, Quarrystone 2, Trailhead 21 — 113 total) seeded via IMAP `APPEND` with a custom `INTERNALDATE`, content imported directly from the real comms fixture modules (ported, not re-transcribed). Ledger: `gmail-seed-ledger.jsonl`, one line per message, flushed immediately. |
| Rocketlane seeding | Complete for Pinehill | Kickoff phase+task created with real planned dates (2026-06-22/28), then completed — the known auto-completion cascade fired, stamping actual dates to the write day. Legacy Dispatch Integration phase+2 tasks created (one `atRisk=true`), left genuinely open — the known `dueDate`-recalculation quirk fired, landing at day-90 as the fixture's own post-day-32 state. No historical dates faked; the seeded state is the arc's honest current truth. |
| Live-read wiring (Gmail) | Complete | `src/ultra_csm/data_plane/live_gmail_reader.py`: reads real IMAP messages into the exact Gmail `users.threads.get` shape the fixtures produce. Each of the six arcs' `*_communication_signals` functions gained a minimal, backward-compatible optional `thread=`/`threads=` parameter (defaults unchanged) — zero duplication of the existing, already-tested extraction logic. `make eval` unchanged at 454 passed after the six signature edits. |
| Live battery | Complete | Live-read Pinehill signals through the unmodified `reply_latency_trend`: 32.9h during the stall vs. the fixture's known 32.0h; 9.8h after recovery vs. 10.0h — within the deterministic jitter's own tolerance. Rocketlane `has_activation_gap`: Kickoff `False`, Legacy Dispatch Integration `True` — both match the fixture's "during" truth. Signal/message counts exact for all six arcs. `~/ultra-csm-corpus-runs/live-narrative-seeding-20260704/live_battery_report.json`: `"problems": [], "ok": true`. |

## IF/THEN Branches Taken

- A live probe (`CreatedDate` insert attempt) failed with a 400, not a
  silent success → confirmed zero record was created (`SELECT COUNT()`
  before/after both 0) before concluding Cases were out of scope, rather
  than assuming from the error message alone.
- Rocketlane's `get_projects` showed only the 2 factory projects, not
  Program 4's expected seeded content → read Program 4's own findings doc
  in full before assuming a regression; confirmed Program 4 phases live
  *inside* those same 2 projects (its own precedent), not as separate
  projects — this program's new content follows the identical pattern.
- The first live Gmail dry-run sample showed a message authored for "hour
  9" rendering at UTC midnight → traced to `narrative_shared.rfc3339`
  storing `hour` as an offset-from-9, not an absolute hour; fixed by adding
  a flat +9h correction when reconstructing the RFC822 `Date:` header, then
  re-verified against a second sample before seeding for real.
- Post-write verification (not just the write succeeding) caught that 97 of
  113 messages had `INTERNALDATE` silently reset to "now" — messages dated
  after the real-world seeding date, which Gmail's IMAP `APPEND` evidently
  refuses to backdate into. Verified this was cosmetic, not corrupting, by
  grepping the actual extraction code (`headers["Date"]`, never
  `internalDate`) before deciding whether to delete and redo anything.
  Nothing was deleted; the finding is documented instead.
- Rocketlane's known auto-completion/dueDate-recalculation quirks (Program
  4) meant no *historical* completion date could ever be set directly (only
  "now" or null) → rather than attempt to force a fake historical
  checkpoint, the seeded phases represent the arc's honest **current**
  state (Kickoff done, Integration open+at-risk), which happens to be
  exactly the "during the stall" truth the story needs.

## Consolidated Owner Ask

1. Same as Program 4's open ask: Rocketlane `create_project` (or a fixed
   REST key) would let future work seed dedicated projects per arc/account
   instead of phases inside the two shared factory projects.
2. `ULTRA_CSM_CALENDAR_OAUTH_REFRESH_TOKEN` was never set up (the Google
   Cloud OAuth flow for Gmail-API/Calendar-API access was scoped but not
   completed) — Calendar seeding for any arc remains untouched pending this.
3. A durable fix for the future-dating wall, if a fully "the whole 365-day
   arc is live" demo is wanted later: re-anchor the synthetic universe's
   `SEED_DATE` to be relative to *run time* (e.g. `today - N days`) rather
   than a fixed calendar date, so a live-seeding run further in the future
   doesn't shrink the genuinely-backdatable window even further. This is a
   real design change to `synthetic_book.py`/`book_simulator.py`'s
   foundational timeline, not something to make unilaterally inside a
   seeding program — flagged for an explicit decision.

## STOP Conditions

No Salesforce writes occurred (Case backdating and CRMCase-connector gaps
ruled it out before any create call). No Calendar writes were attempted
(credential absent, confirmed by direct check, not assumed). No test,
threshold, or battery assertion was weakened — all six comms-module
signature changes are additive/backward-compatible, confirmed by the full
suite passing unchanged (454, same as before this program) before and after.
Nothing was deleted or updated in the live org (create-only throughout,
including the 97 future-dated messages — left in place once confirmed
harmless, not silently removed). No credentials or org identifiers appear
in any committed file (sentinel grep clean on the staged diff).

## Skeptical Reviewer Paragraph

A skeptical reviewer should weigh that this program's live-seeding scope is
real but narrower than "all six arcs, fully live" might suggest at a
glance: three of four content channels (Salesforce Cases, Calendar, and
every arc's core health/usage signal) are either mechanically blocked in
this environment or architecturally unbuilt anywhere in this codebase, not
partially built here. What's genuinely live — Rocketlane for one arc,
Gmail for all six — is proven with exact-number, unmodified-code-path
verification, which is the right bar; but a reader should not come away
believing the whole synthetic universe now "lives" in the org. The
future-dating finding is also worth real scrutiny: 86% of seeded messages
carry an incorrect native Gmail receive-timestamp, and while the content-
level correctness is verified (Date headers, and the extraction code's
actual read path), a reviewer should independently confirm that no future
live-read path is added later that accidentally keys off `INTERNALDATE`
instead of the Date header, which would silently reintroduce the exact
problem this report identifies as harmless today.

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `454 passed, 1 skipped` |
| `LC_ALL=en_US.UTF-8 make lint` | `All checks passed!` |
| `LC_ALL=en_US.UTF-8 make hygiene` | Exited 0 |
| `git diff --check` | Exited 0 |
| `LC_ALL=en_US.UTF-8 make relational-battery-csm` | `hard_ok: true`, 20/20 seeds |
| `LC_ALL=en_US.UTF-8 make relay-battery-csm` | 11/11 passed |
| `LC_ALL=en_US.UTF-8 make narrative-battery-csm` | `hard_ok: true`, 8/8 cases |
| `LC_ALL=en_US.UTF-8 make demo` | Passed; `git status --short` clean after (no artifact drift) |
| Live battery (`live_battery_report.json`) | `"problems": [], "ok": true` |
| Live Rocketlane read (`get_phases`/`get_tasks`, live) | Kickoff completed, Integration open+at-risk, exactly as seeded |
