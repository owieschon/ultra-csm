# Program Report 19 — Density Expansion (four arcs, bible-first)

Branch `codex/density-expansion` off synced `main` (includes report 24's
tick-motion-adoption, PR #31, and Act 1's golden corpus, PR #32). Program 8
proved the safe expansion workflow on one arc (Trailhead, 21→27) and
explicitly deferred the rest. This program executes that deferred work for
the remaining four scored arcs — Pinehill, Aspenridge, Pinnacle, Meridian
(Quarrystone and Trailhead are excluded per the dispatch's pre-ratified
decisions: Quarrystone's silence *is* its story, Trailhead is already
expanded).

Fixture fence (Wave D, report 24): this program's four arcs live in
`comms_fixtures.py` / `pinnacle_comms.py` / `aspenridge_comms.py` /
`meridian_comms.py` / their `narrative_content/*.py` modules — disjoint
files from report 24's fleetops fixture change
(`quietvale-trucking`, `synthetic_book.py`'s account table). Verified at
runtime before any edit: `build_synthetic_book()` → **181 accounts**
(the 180→181 addition from report 24, confirmed present, treated as
settled baseline — not touched, not reverted).

## Phase 1 — Derivation sheet (per-arc checkpoint tables)

Method: for each arc, list every `eval/narrative_battery.py` assertion
that reads a comms-derived signal at that arc's bible checkpoints, compute
the extractor's trailing-window boundaries by hand (`reply_latency_trend`
window=21d, `meeting_cadence_shift` window=30d, `ticket_frequency_window`
window=90d — all from `signal_extractor.py`), and place new message pairs
either (a) strictly outside every checkpoint's trailing windows (Program
8's preferred, safest option) or (b) inside a window with the resulting
arithmetic re-verified by hand against the assertion's actual tolerance
(never its exact value, since none of these five assertions require an
exact value — see per-arc notes).

Baseline values captured empirically before any edit (receipts: direct
Python invocation of each `*_comms.py` + `signal_extractor.py` against
the unmodified worktree at commit 8a86806):

| Arc | Checkpoint | Signal | Baseline value |
| --- | --- | --- | --- |
| Pinehill | day 20 | latency | `None` (insufficient history) |
| Pinehill | day 50 | latency | `115.5` (recent 133.5h vs prior 18.0h) |
| Pinehill | day 50 | tickets | `2.0` |
| Pinehill | day 310 | latency | `10.0` (recent 16.0h vs prior 6.0h) |
| Pinnacle | day 10 | width | `1.0`, strengths `{Derek: weak}` |
| Pinnacle | day 120 | width | `2.0`, strengths `{Derek: weak, Monica: weak}` |
| Pinnacle | day 250 | width | `2.0`, strengths `{Derek: weak, Monica: strong}` |
| Aspenridge | day 90/200/340 | tickets | `0.0` (all three) |
| Meridian | day 20 | width/cadence | `2.0` / `None` |
| Meridian | day 170 | width/cadence | `2.0` / `-2.5` (recent gap 1.0d vs prior 3.5d) |
| Meridian | day 280 | width/cadence | `2.0` / `0.0` (recent gap 1.0d vs prior 1.0d) |

### Aspenridge — derivation (simplest; no exact-value assertions touch comms)

`check_silent_decline` asserts only `tickets==0` at day 90/200/340 (band
and adoption-rate assertions are driven by `book_simulator.py`'s
`UsageDecline`, untouched by this program) and `band=="green"`. Adding
benign email pairs never adds a `CRMCase`, so `tickets` stays `0` at every
checkpoint regardless of where new messages land — **this arc has zero
placement risk from the battery's perspective**. Current: 10 messages (5
QBR pairs, day 1/91/181/271/361). Target ~2-3x → **24 messages** (+14):
add one recap-FYI pair shortly after each existing QBR (day 5, 95, 185,
275, 365→ use 363 to stay ≤365) plus two extra scheduling-logistics pairs
(day 45, 135) between QBRs, all same-day fast replies matching the arc's
established "calm, prompt, one contact" cadence. No new participant
(Christine Yoder only, per the dispatch's no-new-participants rule).

### Pinnacle — derivation

`check_single_threaded_risk` asserts width (1/2/2) and strength
(`strong` present at day250) at day 10/120/250. Width is presence-based
(any message ⇒ active relationship as of that day); strength is **day-gated
only** (`strength = "strong" if as_of_day>=240 else "moderate" if
as_of_day>=135 else "weak"`, verified by direct inspection of
`pinnacle_comms.py:159` — independent of message count or reply latency).
Derek's arc-defining fact ("champion goes quiet day 3, never replies
again") is a MUST-NOT-TOUCH: no new Derek message may be added at any day
≥3. Monica's thread (day 110 onward) is free: any additional Monica↔CSM
pairs after day 110 leave width/strength unchanged. Current: 12 messages
(1 Derek pair pre-day-3 + 5 Monica pairs day110-245). Target ~2-3x →
**26 messages** (+14): add 7 new Monica pairs at day 118, 145, 160, 185,
200, 225, 238 (all safely after day 110, before day 240 so none cross the
strong-strength gate boundary prematurely — though the gate is day-based
regardless, keeping additions inside the existing 110-245 span matches
"front-loaded" and avoids inventing a new late-arc beat).

### Pinehill — derivation (exact-value territory; Program 8's stall latencies)

`check_onboarding_stall` asserts (day50/"during"): `latency > 15` (not an
exact value — wide tolerance) and `tickets >= 2`; (day310/"after"): zero
Rocketlane activation gaps (unrelated to comms). Window arithmetic by
hand: `reply_latency_trend` window=21d. Day 20's windows are
recent=(-1,20], prior=(-22,-1] — prior is structurally empty (sim starts
day 0), so `latency=None` is guaranteed regardless of any addition ≤20,
**as long as no new message pre-dates day 1** (none will). Day 50's
windows: recent=(29,50], prior=(8,29]. Day 310's windows: recent=(289,310],
prior=(268,289]; ticket window (90d) for day310 is (220,310].
**Safe zone**: days 51-219 inclusive fall inside NONE of the three
checkpoints' latency (21d×2) or ticket (90d) trailing windows — verified
by direct interval arithmetic, not assumed. Current: 19 messages (8 stall
pairs day1-87, 1 solo safety-extension message day41, 5 recovery pairs
day275-306). Target ~2-3x → **29 messages** (+10, 5 pairs): place all five
new pairs in the day51-219 safe zone — day 100, 130, 160, 190, 205 (mid-
onboarding "quiet stretch" recap/FYI exchanges, matching the arc's
established Marcus-verbose/Dennis-terse voice) — touching zero checkpoint
arithmetic. Re-verified after authoring (Phase 2 gate): `latency`,
`tickets` at day20/50/310 all unchanged from baseline table above.

### Meridian — derivation

`check_expansion_ready` asserts width==2 at day170/280 (Sarah appears day
10, both threads presence-based ⇒ unaffected by added density) and
cadence `<=0` at day170 (recent gap ≤ prior gap — currently -2.5, wide
tolerance since 0 is the boundary, not an exact value). `meeting_cadence_shift`
reads *calendar* events only, not email messages — this arc's density
expansion is entirely new **email** pairs on the two existing threads
(Alicia fleet-ops, Sarah facilities); no new calendar events are added, so
cadence arithmetic is untouched by construction, no placement math needed
for that signal. Width likewise untouched (both contacts already present
throughout the relevant range). Current: 52 messages (26 Alicia + 26
Sarah). Target ~2x (Meridian explicitly targets the low end per the
dispatch's decisions) → **104 messages** (+52, 26 new pairs, 13 per
thread): interleave one additional FYI/scheduling pair between each
existing exchange gap on both threads, keeping the existing subject-arc
shape (kickoff → usage growth → expansion scoping → close → post-close →
year-end) intact and adding no new participant.

## Gate (Phase 1)

`test -f docs/PROGRAM_REPORT_19.md` → present, contains the four per-arc
derivation tables above. PASS.

## Phase 2 — Per-arc expansion (execution log)

All four arcs executed in the derivation sheet's stated order (Aspenridge,
Pinnacle, Pinehill, Meridian — simplest first), one commit per arc, each
containing (a) the bible density subsection, (b) the schedule tuple +
content-module additions, (c) a sanctioned snapshot regen (Pinehill needed
none — see below), (d) any legitimate re-derivation disclosed inline.

| Arc | Commit | Before → after | Gates |
| --- | --- | --- | --- |
| Aspenridge | `6ffa80c` | 10 → 24 | narrative hard_ok:true 8/8; content hard_ok:true 5/5; invariance PASS (post-regen; only evidence timestamps moved, zero value drift) |
| Pinnacle | `8441002` | 12 → 26 | narrative hard_ok:true 8/8; content hard_ok:true 5/5; invariance PASS (post-regen; one *unasserted* latency value moved 0.0→1.0, disclosed in bible) |
| Pinehill | `181e9d3` | 19 → 29 | narrative hard_ok:true 8/8; content hard_ok:true 5/5; invariance PASS with **zero diff** — the day51-219 safe-zone placement needed no regen at all, confirming the derivation held exactly |
| Meridian | `4942aec` | 52 → 104 | narrative hard_ok:true 8/8; content hard_ok:true 5/5; invariance PASS (post-regen; two *unasserted* latency values moved, disclosed in bible) |

Total: +90 messages across four arcs (114 → 183 total messages across all
six scored arcs, Trailhead's 27 and Quarrystone's 2 unchanged). Every
addition is bible-first: the density subsection for each arc was written
before the corresponding code commit, in the same commit, per the K14-
compatible sanctioned-exception protocol.

Sample bodies (three per arc, read directly for the residual — prose
quality is gate-unverified, this is the human glance the routing table
calls for):

**Aspenridge** (day 45, Marcus→Christine): "No urgent items, just checking
in on scheduling -- want to keep the Q2 review on the calendar for the
usual week, or is there a better slot with your team's spring routing
changes?"

**Pinnacle** (day 160, Priya→Monica): "Checking in ahead of our next sync
-- anything you want added to the agenda on the Fuel Analytics adoption
front?"

**Pinehill** (day 130, Marcus→Dennis): "Quick FYI -- Grace's team is still
monitoring the ack-timeout fix from a few weeks back, no new incidents
since. Will flag immediately if anything changes."

**Meridian** (day 90, Priya→Alicia): "Checking in ahead of the Q3 planning
conversation -- anything you want added to the agenda?"; (day 85, Priya→
Sarah): "Checking in ahead of the budget conversation -- anything you
need from us before then?"

## Phase 3 — Full verification

| Check | Command | Observed result |
| --- | --- | --- |
| Suite | `LC_ALL=en_US.UTF-8 make eval` | `606 passed, 1 skipped` — same count as the pre-program baseline (this program adds fixture content, not new tests) |
| Lint | `make lint` | `All checks passed!` |
| Hygiene | `make hygiene` | exit 0 |
| Narrative | `make narrative-battery-csm` | `hard_ok: true`, 8/8 |
| Content | `make content-battery-csm` | `hard_ok: true`, 5/5 |
| Invariance | `python3 -m eval.content_invariance_check --check` | PASS (post all four regens) |
| Canary | `make canary-battery-csm` | `hard_ok: true`, 6/6 |
| Tier policy | `make tier-policy-battery-csm` | `hard_ok: true`, 4/4 |
| Quantity/transcript | `make quantity-battery-csm transcript-battery-csm` | both `hard_ok: true` (3/3, 4/4) |
| Drift check | `git diff --check` | exit 0 |
| Status | `make status` | `STATUS.md is current` |
| Density delta | `git log --oneline` | 4 arc commits (`6ffa80c`, `8441002`, `181e9d3`, `4942aec`) plus the D1 derivation commit (`187c422`) |

Diff budget: 11 files changed (`docs/SYNTHETIC_UNIVERSE_BIBLE.md`,
`docs/PROGRAM_REPORT_19.md`, four `*_comms.py`, four
`narrative_content/*_content.py`, `eval/content_invariance_snapshot.json`),
844 insertions / 12 deletions across the whole program — within the
15-file/1,200-line budget. Zero IF/THEN tripwires fired (well under the
8-item threshold — the only fork-like decisions were the two legitimate,
disclosed latency re-derivations, both pre-covered by Program 8's
anti-Goodhart disclosure norm, not genuine forks).

## IF/THEN Branches Taken

- Two arcs (Pinnacle, Meridian) produced a changed `reply_latency_trend`
  value in the invariance snapshot after their density commit, even
  though `check_single_threaded_risk`/`check_expansion_ready` never assert
  `latency` for these arcs → verified this is unasserted by direct
  inspection of `eval/narrative_battery.py` before treating it as safe,
  disclosed both moves inline in the bible's density subsections (per
  Program 8's anti-Goodhart norm) rather than silently letting the
  snapshot diff be the only record.
- Pinehill's safe-zone placement (day51-219) turned out to require *zero*
  snapshot regeneration at all (the three checkpoint days' trailing
  windows never touch that range) → rather than force a no-op regen to
  satisfy "one sanctioned regen per arc phase" literally, left the
  snapshot untouched for this arc's commit and stated why; the sanctioned-
  exception count (four regens allowed) is a ceiling, not a quota, and
  three of four arcs used it.

## Consolidated Owner Ask

1. **Live catch-up seeding run for this program's new messages.** This
   program is offline-only by design (fixtures only, no credentials, no
   live-org access). Verified at runtime before writing this ask: the
   live drip-seeder (`~/ultra-csm-corpus-runs/live-reseed-20260704/drip_seed.py`,
   installed by Program 9, `docs/LIVE_INTEGRATION_FINDINGS.md`) reads
   `anchor.json`'s `seeded_through_day` and only ever seeds messages where
   `seeded_through_day < story_day <= current_story_day` (lines 146/161) —
   strictly forward-looking, one-way advance, never backward. The current
   `anchor.json` (`seeded_through_day: 50`, anchor_date 2026-05-15) means
   most of this program's new messages (placed at story days 5-288 across
   the four arcs, many below the already-advanced `seeded_through_day`)
   will **never** be picked up by the daily drip job once it advances past
   them. A small, explicitly-authorized one-time catch-up seeding run
   (append the 90 new messages at their correct historical dates, then
   resume the normal forward drip) is needed before the live mailbox
   matches the enriched fixtures — not done here, recorded as this
   program's required live-integration follow-up per the dispatch's own
   instruction.
2. **Prose-quality/believability of the new filler content is
   gate-unverified.** No battery reads email body text for tone or
   naturalness (by design — the extractors are metadata-only). The three
   sample bodies per arc above are a human glance, not an automated proof
   that all 90 new messages read equally well; a reviewer should spot-
   check a larger sample before treating this as demo-ready prose.

## STOP Conditions

None fired. No credential or live-system access was used anywhere in this
program (verified: every command run was local — pytest, the battery
modules, `git`, no network call). No battery/threshold/expected value was
edited to pass (K14) — every gate passed on the first attempt per arc, no
retries needed. The fleetops fixture fence held: `synthetic_book.py`,
`quietvale-trucking`, and the 181-account book table were never touched
(verified: `git diff --stat` for this program's commits shows zero
changes to `synthetic_book.py` or any file under `tenants/`).
`signal_extractor.py`, `contracts.py`, `quarrystone_comms.py`,
`trailhead_comms.py` were never touched (ownership map honored).

## Skeptical Reviewer Paragraph

A skeptical reviewer should weigh three limits. First, filler prose
quality is gate-unverified — density (message count) is proven and
checkpoint-safe by hand-derivation and battery, but "reads like a real
onboarding thread" is asserted only by this report's 3-sample-per-arc
human glance, not by any automated check; a reader should not conflate
"density expanded" with "content quality independently verified." Second,
two of four arcs (Pinnacle, Meridian) shifted an *unasserted*
`reply_latency_trend` value in the invariance snapshot — this is
disclosed and verified harmless against the actual battery assertions,
but a reader relying on "byte-identical snapshot" as a blanket invariant
should know two of four arcs' snapshots did change, just not in a scored
dimension. Third, this program is fixture-only; the live mailbox now
diverges further from the fixtures than before (90 more messages exist
in fixtures than in the live org), and that gap will not self-heal via
the existing drip job without the catch-up run named in Owner Ask #1 —
a reader should not assume the live demo environment reflects this
program's density increase until that run happens.

## Receipts Appendix

- Worktree: `~/dev/ultra-csm-density-expansion`, branch `codex/density-expansion`.
- Base: `8a86806` (main, includes PR #31 report-24 tick-motion-adoption,
  PR #32 Act 1 golden-corpus).
- Fixture fence check: `build_synthetic_book()` → 181 accounts (report
  24's addition confirmed present, untouched throughout this program).
- Commits: `187c422` (D1 derivation sheet), `6ffa80c` (D2.1 Aspenridge),
  `8441002` (D2.2 Pinnacle), `181e9d3` (D2.3 Pinehill), `4942aec` (D2.4
  Meridian).
- `git log --oneline -6`:
  ```
  4942aec Density D2.4: meridian-fleet +52 messages (bible-first)
  181e9d3 Density D2.3: pinehill-transport +10 messages (bible-first)
  8441002 Density D2.2: pinnacle-supply +14 messages (bible-first)
  6ffa80c Density D2.1: aspenridge-supply +14 messages (bible-first)
  187c422 Density D1: derivation sheet
  8a86806 Harvest 7: Act 1 -- golden corpus into Slot B + judge-on-live (Wave C) (#32)
  ```
- Full DoD table results: see Phase 3 section above, all rows PASS.
