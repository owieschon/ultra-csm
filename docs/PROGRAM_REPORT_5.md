# Program Report 5

Branch `codex/synthetic-universe`, commits `bec6f18`..`12c7b83` plus this
report's commit, stacked on `main` (PRs #11/#12 merged, Program 4's
Rocketlane onboarding rail). Program 5 is the Synthetic Tenant Universe:
six authored narrative arcs on the existing 35-account book, causal-exhaust
artifacts (email/calendar/CRM/Rocketlane) for each, a deterministic
zero-LLM signal extractor, a narrative battery, and a deepened synthetic
org identity. Note on numbering: `docs/PROGRAM_REPORT_3.md` already
belongs to an earlier, unrelated program (relational ingest) still on
`main` -- this report uses the next open number rather than overwrite it.

## DoD Evidence

| Phase | Result | Evidence |
| --- | --- | --- |
| U0: world bible | Complete | `docs/SYNTHETIC_UNIVERSE_BIBLE.md` maps six arcs, two red herrings, and 27 boring controls onto the existing `SCENARIO_TIMELINE`/persona spine, extending it in three small, clearly-marked places (Quarrystone churn-brewing lead-up, Aspenridge silent-decline account, two red-herring cases) rather than inventing a parallel timeline. Commit `bec6f18`. |
| U1: onboarding-stall pilot | Complete, checkpoint approved | Gmail/Calendar-shaped fixtures, a day-offset-aware Rocketlane arc exercising both documented live Rocketlane behaviors, a deterministic signal extractor, and a driver script running the real `run_time_to_value_sweep` at three day_offsets. Commit `cc3de83`. Presented at the mandatory U1 stop; owner approved scaling to U2 with one correction (below). |
| Correction: adoption deltas | Complete | Owner caught that seat-penetration/feature-depth staleness was this program's own authoring gap (no scripted `UsageDecline`/`UsageGrowth` for three arc accounts), not a sweep-scoring bug. Fixed for Pinehill/Pinnacle/Aspenridge, verified against real engine output, not assumed. Also caught and fixed a real authoring bug of my own: an earlier draft of Quarrystone's churn-brewing arc had health band improving (red→yellow) right before the churn, which was backwards -- the account's baseline is already red at day 0, so there was no green-to-red arc to script. Commit `fb568a1`. |
| U2: remaining five arcs | Complete | Single-threaded-risk (Pinnacle), churn-brewing (Quarrystone), silent-decline (Aspenridge), expansion-ready (Meridian), healthy-control (Trailhead) -- comms fixtures for each, verified against `signal_extractor.py`'s four functions at their bible-specified checkpoints. Also fixed a second real gap: the bible's day-160 Quarrystone renewal case was scripted in prose but missing from `_CASE_SCHEDULE`. Commits `efdbcf0`, `a9a6164`. |
| U3: narrative battery | Complete | `eval/narrative_battery.py`, modeled on `eval/relational_battery.py`'s shape (frozen cases, `hard_ok`, byte-identical-across-two-runs determinism) with bible-specified checkpoints instead of random seeds. 8 cases (6 arcs + red herrings + boring controls), all green. `narrative-battery-csm` Makefile target, 4 tests. Commit `621a02d`. |
| U4: deepened synthetic org | Complete | `org_pack.json` bumped to `v2` with four new opinionated sections (constitution, brand_voice, onboarded_definition, expansion_playbooks) -- additive, `load_org_pack()` unchanged. Two companion knowledge docs with per-item provenance/review_status/as_of, each item grounded in and cross-checked against a specific synthetic arc, including two `needs_review` items that honestly flag where the constitution's stated norm and the arc's actual timeline don't quite agree. Commit `12c7b83`. |

## The U1 Checkpoint (mandatory stop-and-show)

Presented: the pilot's artifacts, extractor output, and three briefings
(before/during/after day 20/50/310). Reply-latency stretched +32h during
the stall, relaxed to +10h after; meeting cadence compressed -13d on
recovery; the Rocketlane activation-gap flag flipped True→False across the
arc. One finding surfaced: the sweep's priority score was *higher* after
recovery (82) than during the stall (62). Owner's correction: this was my
own authoring gap (no scripted adoption delta for the arc accounts), not a
sweep-scoring bug, and directed fix-as-you-go for U2 rather than deferral --
especially for silent-decline and single-threaded-risk, where the gap
would have been existential to those arcs' premise. Both fixed and
verified (see Correction commit above and the IF/THEN section).

## IF/THEN Branches Taken

- The engine has an undocumented (from this program's read of the code, not
  from any doc) automatic health-score adjustment: any account not already
  carrying an explicit score-affecting mutation gets its `HealthScore`
  penalized/boosted if `active_assets` moves >20% from its persona
  baseline. An early draft of Aspenridge's silent-decline `UsageDecline`
  (0.15/day for 210+ days) blew straight past this threshold, silently
  flipping the account's band to yellow/red by day 245 -- directly
  contradicting the arc's entire premise ("green-but-quiet"). Caught by
  re-running the actual engine and reading its output, not by re-reading
  the mutation source (the numbers looked plausible on paper). → Resized
  to stay under the threshold (~12% cumulative decline by day 340), and the
  bible now states explicitly that this arc is calibrated against that
  specific engine behavior, not calibrated in the abstract.
- Quarrystone's base fixture data already starts the account `red` at day 0
  (`champion_departed`/`no_successor` in the persona's own baseline
  `_HEALTH` entry, not a scripted event) → an initial draft of the
  churn-brewing extension added a day-180 `HealthBandChange` to yellow,
  which read as an unearned improvement immediately before the day-220
  churn. Removed; the arc's "brewing" signal is now correctly framed as
  absence of remediation on an account that has been visibly flagged the
  entire time, not a health-band transition -- a genuinely distinct failure
  mode from silent-decline (hidden risk) and single-threaded-risk (risk
  that gets remediated).
- Five background sub-agents dispatched in parallel for U2's five comms
  modules hit a systemic recursive-delegation failure this session (agents
  reporting "I've dispatched a background agent" about themselves, or
  spawning phantom sub-agents that never wrote a file, across 4+ rounds of
  resume attempts with zero files produced) → rather than continue fighting
  a broken harness, built the five files directly. Mid-flight, several of
  the originally-dispatched agents self-corrected and produced real,
  independently-verified work (Meridian, Quarrystone, Aspenridge,
  Trailhead) before I finished all five myself -- in each case I read and
  independently re-verified the agent's file (ruff + a live extractor run)
  rather than trusting the agent's own report, and kept whichever version
  was already on disk rather than overwriting good work. Net: 5 files
  built, only 1 (Pinnacle) actually authored end-to-end by me; the other 4
  came from agents that eventually worked, verified independently before
  being counted as done.
- Rocketlane fixtures were built only for Pinehill (the one onboarding-cohort
  account among the six arcs) -- the other five accounts are
  steady_state/expanding/at_risk/renewal, already past onboarding, and
  `contracts.py`'s `OnboardingConnector` is explicitly optional per-tenant
  ("a tenant with no onboarding source configured has no
  `OnboardingConnector` at all"), so building one for them would have been
  fabricated, not causal.
- Red herrings (Cedar Valley, Ironridge Fleet) got a CRM case each (U0) but
  no dedicated email/calendar fixture module in U2 -- the bible's design is
  "looks bad in exactly one artifact class," and for both herrings that
  class is already the case/usage signal already in the spine; adding a
  calm comms module on top would be extra work establishing a "fine"
  baseline the battery doesn't need (absence of any comms module means the
  extractor correctly returns `None`/insufficient-history for those
  channels, which is itself consistent with "nothing else here").

## Consolidated Owner Ask

1. **Boring-controls check design.** The narrative battery's boring-controls
   case checks for *contamination* (program-authored case content leaking
   onto a control account) rather than a raw case-count ceiling -- an
   earlier draft used `>2 cases` as the threshold and false-positived on
   Cypress Field, which legitimately carries 4 pre-existing cases as part
   of its own `at_risk_support` persona, unrelated to this program. The
   current check is more honest but also weaker (it can't catch a *new*
   kind of contamination that happens to reuse an existing subject string).
   If the product wants a stronger boring-controls guarantee later, it
   likely needs per-account baseline snapshots taken before this program's
   changes, diffed against current state -- not built here, flagging for a
   deliberate call.
2. **The extractor's fixed windows (21d reply-latency, 30d meeting-cadence)
   structurally can't produce a signal for the Aspenridge- and
   Quarrystone-shaped cadences** (quarterly business reviews, near-total
   silence) -- every checkpoint for those two arcs reads `None` for those
   two signals, which is correct (fail-closed, not fabricated) but means
   the extractor demonstrates its *restraint* on those arcs rather than its
   *capability*. If a future program wants those two signal families
   exercised positively (not just correctly-absent), the windows would
   need to be configurable per-arc, which the current single-set-of-
   constants design doesn't support.
3. **`docs/PROGRAM_REPORT_3.md` filename collision.** The original dispatch
   named this report `docs/PROGRAM_REPORT_3.md`; that file already belongs
   to a different, completed program on `main`. Used `PROGRAM_REPORT_5.md`
   instead (the next open number after `_4`). Worth fixing the numbering
   convention/dispatch template so this doesn't recur.

## STOP Conditions

No file outside this program's stated ownership was touched (`agent1/`,
`slot_b`, sweep scoring, committers, `mcp_server.py`, README, TOUR all
untouched -- confirmed via `git diff --stat` against `main` before writing
this report). No agent/owner name appears in any committed file (sentinel
grep, zero matches on every commit). All fixture content is fictional,
`*.example` domains only. The two pre-existing tests that broke from the
`pack_version` bump were fixed to match the new, intentional value -- not
weakened or the version silently reverted to avoid touching them. The
narrative battery was never edited to match a wrong system output; every
case that initially failed (the boring-controls false positive) was fixed
by correcting the *check's* logic against a stated reason, with the
original failure and its cause documented above, not silently smoothed
over.

## Skeptical Reviewer Paragraph

A skeptical reviewer should note three real gaps. First, only one of the
six arcs (Pinehill) was run through the actual `run_time_to_value_sweep`
end to end with a live briefing -- the other five were verified at the
extractor/fixture level only, because they don't touch the Rocketlane rail
and re-running the full ephemeral-Postgres sweep for each would have been
expensive across parallel construction; this means the claim "the
briefing surfaces the arc's truth" (bible's stated Phase U3 goal) is
proven for one arc, not six, and the narrative battery's own docstring is
explicit that assertion (b) only applies "for rails the briefing already
consumes" -- which today is just Pinehill's Rocketlane rail. Second, the
extractor's fixed-window design means two of six arcs (Aspenridge,
Quarrystone) produce mostly `None` signals at every checkpoint by
construction (Owner Ask #2) -- correct, but it means roughly a third of
this program's "causal exhaust" is exhaust of *absence*, which is real and
intentional but easy to mistake for missing work if not read closely.
Third, this session hit a genuine, repeated multi-agent delegation failure
(documented in IF/THEN) -- four of the five U2 comms files ultimately came
from background agents rather than direct authorship, and while each was
independently re-verified (ruff + a live extractor run against the exact
bible-specified checkpoints, not just trusting the agent's self-report) by
me before being counted as done, a reviewer should know the provenance mix
isn't uniform across the five files the way it might read from the diff
alone.

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `454 passed, 1 skipped` |
| `LC_ALL=en_US.UTF-8 make lint` | `All checks passed!` |
| `LC_ALL=en_US.UTF-8 make hygiene` | Exited 0 |
| `git diff --check` | Exited 0 |
| `LC_ALL=en_US.UTF-8 make relational-battery-csm` | `hard_ok: true`, 20/20 seeds (pre-existing, unaffected) |
| `LC_ALL=en_US.UTF-8 make narrative-battery-csm` | `hard_ok: true`, 8/8 cases |
| `PYTHONPATH=src:. .venv/bin/python -m eval.u1_pinehill_pilot` | 3/3 checkpoints, briefing + extractor captured to `eval/u1_pinehill_pilot.json` |
| Sentinel grep on every commit's staged diff | Zero matches, every commit |
