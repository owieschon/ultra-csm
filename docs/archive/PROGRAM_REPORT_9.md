# Program Report 9 — Live Re-seed with Anchor Translation

Branch `codex/live-reseed` off synced `main` (PR #16, Program 8, merged
first — a hard preflight gate, since the seeder reads the enriched bodies
from the fixtures on main). Executed per the orchestrator dispatch
(orchestrator ran preflight, join gates, and all commits; parallel
subagent lanes did the survey/build work; every live write was
dry-run-manifested and reviewed before executing). Run artifacts:
`~/ultra-csm-corpus-runs/live-reseed-20260704/` (never committed).

## The SEED_DATE decision (resolved)

`SEED_DATE = 2026-06-21` is untouched and stays untouched — determinism
of every committed artifact was non-negotiable. Re-anchoring happens only
at the seeding boundary: a frozen `anchor.json` (anchor_date 2026-05-15 =
run date − 50, mode "unfolding") maps fixture day-offsets to real
calendar dates, computed once and never re-derived from "today" again.
Story day 50 — the bible's own "during the stall" Pinehill checkpoint —
therefore *is* the day the backfill ran, and each real day advances the
story by one. Verified premise: every extractor is translation-invariant
(hour-deltas, day-gaps, as_of-relative windows), proven live by the same
latency value emerging from two different calendars (see DoD).

## DoD Evidence

| Workstream | Result | Evidence |
| --- | --- | --- |
| Preflight | Complete | PR #16 confirmed merged before start; main green (474); baseline snapshot (INBOX 119, old-tag 113, Calendar 0, Rocketlane 17 phases = Program 7's exact end state); creds present by name/length only. `00_baseline.json`. |
| A1: anchor module | Complete | `anchor.py` + `test_anchor.py` (run dir): 3 hand-computed translation examples verified, all 32 day≤50 messages proven to land in the real past, per-arc counts derived from fixtures (8/2/2/6/2/12), 161 full-year calendar events. |
| A2: OOO guard | Complete, committed (`Reseed R1`) | `live_gmail_reader` now excludes RFC 3834 `Auto-Submitted` messages. 6 new tests (480 total, was 474), including a signal-level demonstration that an unguarded OOO deflates `reply_latency_trend`. All gates re-run by the orchestrator directly, not trusted from the lane's self-report. |
| A3: Rocketlane REST diagnosis | Complete — verdict DOWN | 401 `NOT_AUTHORIZED` on `GET /projects`, persisting across a 60s retry and an independent curl retry (which also ruled out a local Python SSL-trust issue as the cause). Lane B3 (capability probe) skipped per the dispatch's conditional. Owner ask carried forward. |
| B1: Gmail backfill | Complete, 32/32 | All six arcs' day≤50 messages, enriched bodies, tag `UCSM-NARR2`, anchor-translated dates (earliest 2026-05-15, latest 2026-06-29 — all past). Dry-run manifest reviewed before write; ledgered per message. Post-write: INBOX 119→151, tag count exactly 32. |
| B2: Calendar seed | Complete, 159/159 | Full 365-day year (future events are realistic; the extractor filters by as_of), OAuth, `sendUpdates="none"`, no attendees (conservative — even `.example` invitees not attempted), tag in summary + extendedProperties. A mid-run Google rate limit (403) after 47 events was handled by making the seeder ledger-resumable with backoff + pacing — no duplicates (159 ledger lines, 159 live events). 2 cancelled fixture events skipped, disclosed (create-only forbids create-then-cancel; cadence extraction reads confirmed events only). |
| C1: drip-seeder | Complete, running | `drip_seed.py` + `com.ultracsm.narrative-drip` launchd (daily 07:00). Idempotent via ledger union (backfill + drip), advances `seeded_through_day`, logs a loud day-100 reminder for the Rocketlane task completion it cannot perform itself. Install verified with unload/load + manual kickstart producing the correct no-op ("current_story_day=50 <= seeded_through=50"). |
| C2: noise layer | Complete, 3/3 | Dennis Gruber OOO (2 min after the day-22 outbound, `Auto-Submitted: auto-replied`, quotes the tagged subject — the deliberate live test-case for A2), untagged newsletter, untagged Rocketlane-style notification. Live-mailbox-only; nothing mirrored into fixtures. |
| Live battery v2 | Complete, 18/18 checks, `"problems": []` | Pinehill latency 32.9h (live, anchor calendar) vs 32.0h (fixture, seed calendar) within the jitter tolerance; per-arc counts exact (fixture-derived at check time, never hardcoded); INTERNALDATE 33/33 correct (vs Program 7's 16/113); body round-trip byte-identical after CRLF normalization, one message per arc, all six arcs; OOO triple-assert (in mailbox / out of extracted thread / latency intact); Calendar 159 live = 159 expected-after-skip. `live_battery_v2_report.json`. |

## IF/THEN Branches Taken

- The general-purpose subagent lanes twice responded by spawning a
  further nested background agent and idling instead of doing the work
  (Lane A1's first attempt produced zero files; a retry with an explicit
  "do this yourself" instruction still nested). The orchestrator
  re-verified every lane's deliverables directly on disk rather than
  trusting completion summaries — which caught the empty first A1 — and
  built the higher-stakes live-write lanes (B1/B2/C1/C2) itself rather
  than risk the same failure mode on irreversible actions. A separate
  investigation task was spawned for the delegation bug itself.
- Lane A3's original brief asked for the key's first4/last4 for identity
  comparison; the auto-mode classifier blocked that as credential
  materialization → re-dispatched without any partial-value output,
  losing the key-identity comparison but keeping the fact that actually
  decides the lane's verdict (the live 401). Not routed around.
- Lane A1's retry agent found the dispatch's own worked arithmetic
  example was off by one day (2026-07-13 − 37d = 2026-06-06, not 06-05)
  and asserted the mathematically correct value rather than the
  dispatch's — the right precedence, recorded here.
- Google Calendar rate-limited the batch insert at 47/159 → the seeder
  was made ledger-resumable (skip already-ledgered, exponential backoff,
  0.3s pacing) and resumed to completion; the ledger prevented any
  duplicate event. No update/delete was involved at any point.
- Installing the launchd drip job was blocked by the auto-mode classifier
  as unauthorized persistence (a standing, unattended daily writer into a
  real mailbox exceeds what "execute the dispatch" authorizes on its
  own). Stopped, surfaced with the exact trade-offs, and the owner
  explicitly selected "Authorize the launchd job now" — only then loaded.
- The battery's first run failed on two bugs in the battery script
  itself (fixture as_of computed on the wrong calendar; per-arc grouping
  key mismatch with anchor.py's hyphenated thread labels) → fixed in the
  battery, never by adjusting an expectation: the live numbers were
  already correct.
- Python 3.14's system/venv SSL trust store failed CERTIFICATE_VERIFY on
  the Rocketlane retry → re-verified via curl (system trust store) so the
  DOWN verdict rests on a clean 401, not a local TLS artifact.

## Consolidated Owner Ask

1. **Rocketlane REST key** (carried from Programs 4/7): the env-file key
   401s; the key that worked on 2026-07-03 either was never saved to the
   env file or has been invalidated. Needs the Rocketlane console
   (Settings → API) to generate/save a fresh key. Unblocks: the
   `POST /projects` capability probe, per-arc projects, and the day-100
   scripted task completion the drip job will remind about (~2026-08-23).
2. **A live calendar reader** (`live_calendar_reader` mirroring
   `live_gmail_reader`) so `meeting_cadence_shift` can consume the 159
   live events; the battery records the day-50 Pinehill target (0.0).
3. **The agent's own daily cadence**: the world now advances every
   morning; the agent still only looks when run manually. Wiring the
   daily tick/briefing on top of the unfolding world is the next
   milestone of the standing 30-day plan.

## STOP Conditions

Create-only throughout (Program 7's old-tag seed left inert under
`UCSM-NARR`; the rate-limit recovery re-created nothing). No credential
value ever printed (names/lengths only; the one lane brief that asked for
a partial slice was blocked and re-dispatched without it). Two auto-mode
classifier blocks honored, not routed around (credential slice;
launchd persistence — the latter resolved by explicit owner choice). No
fixture, extractor, contract, threshold, or battery expectation changed
to make anything pass; the one repo code change (OOO guard) is additive
and its 6 tests were the only test-count delta. No update/delete against
any live system.

## Skeptical Reviewer Paragraph

A reviewer should weigh: (1) only days 0–50 of the email story are live —
the remaining 315 days arrive at one real day per story day, so any
"whole year live" reading is wrong; the full mailbox exists only in
fixture form until the drip delivers it. (2) The drip-seeder has run
exactly once, as an installer-verified no-op; "the story unfolds daily"
is a design with one data point until several mornings pass — the first
real content delivery is story day 60 on 2026-07-14. (3) The OOO live
proof is one message on one arc; the offline tests generalize it, but
live coverage is N=1. (4) Meridian/Pinnacle live verification is
count-exact but not per-contact-latency-exact (merged-domain
simplification, same as Program 7). (5) The 32.9-vs-32.0 latency match is
within the deterministic jitter's designed tolerance, not byte-equality —
correct by construction, but a reader should know "matches" means ≤1.0h
here. (6) Rocketlane gained nothing this program: its state is
Program 7's, and the REST path is still dead.

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `480 passed, 1 skipped` |
| `LC_ALL=en_US.UTF-8 make lint` | `All checks passed!` |
| `LC_ALL=en_US.UTF-8 make hygiene` | Exited 0 |
| `git diff --check` | Exited 0 |
| `LC_ALL=en_US.UTF-8 make content-invariance-csm` | byte-identical PASS |
| `LC_ALL=en_US.UTF-8 make narrative-battery-csm` | `hard_ok: true`, 8/8 |
| `LC_ALL=en_US.UTF-8 make content-battery-csm` | `hard_ok: true`, 5/5 |
| `LC_ALL=en_US.UTF-8 make relational-battery-csm` | `hard_ok: true`, 20/20 |
| `LC_ALL=en_US.UTF-8 make relay-battery-csm` | 11/11 |
| Live battery v2 (credentialed, run dir) | 18/18 checks, `"problems": []` |
| launchd job | loaded; manual kickstart = correct no-op |
