# Synthetic Universe Bible

Fictional ground truth for the 35-account synthetic book. This is not a blind
human gold set — it is the deterministic script every generated artifact must
be causal exhaust of. If an artifact for account X were shuffled onto account
Y, the narrative battery (`eval/narrative_battery.py`, Phase U3) must fail:
X's evidence should not support Y's story and vice versa.

## Spine

The spine is `src/ultra_csm/data_plane/book_simulator.py`'s `SCENARIO_TIMELINE`
(365-day, `SEED_DATE = 2026-06-21`) plus `data_simulator.py`'s
`_ACCOUNT_PERSONA` map and `_CASE_SCHEDULE`. Six of the accounts below already
carry a scripted arc in that spine — this bible names the arc, states the
briefing-level truth an ideal agent should reach, and lists the day offsets
and evidence ids new artifact layers (email, calendar, CRMCase, Rocketlane,
extractor output) must hang beats on. Where the existing spine under-scripts
an arc, this bible extends `SCENARIO_TIMELINE` / `_CASE_SCHEDULE` with new,
clearly-marked entries rather than inventing a second timeline. Every new
entry is additive: existing mutations, existing tests, and existing
`hard_ok` batteries are untouched.

Evidence ids follow the existing `det_id(*parts)` (fixtures.py) /
`det_rocketlane_id(*parts)` (rocketlane_fixtures.py) convention:
`det_id("email", account_id, thread_slug, day_offset)`,
`det_id("event", account_id, event_slug, day_offset)`,
`det_id("case", account_id, subject_slug)`,
`det_rocketlane_id("phase"|"task", slug)`. This bible states the parts;
Phase U1/U2 fixture code computes the actual UUID5 strings.

## The six arcs

### 1. Onboarding-stall — `pinehill-transport` (PILOT ACCOUNT, Phase U1)

Persona: `stalled_onboarding` (`data_simulator.py:256`). Industry: logistics,
CSM `csm-102`.

Existing spine beats:
- Day 0 — `CRMCase` "Integration with legacy dispatch system failing" (High,
  `integration`, resolves ~day 45, csat 2.5) — `_CASE_SCHEDULE`.
- Day 7 — `MilestoneCompleted("pinehill-transport", "activate_50pct_assets", 7)`.
- Day 30 — `CRMCase` "Integration timeout errors persist" (High, resolves
  ~day 60, csat 2.0).
- Day 35 — `MilestoneCompleted("pinehill-transport", "configure_routing", 35)`.
- Day 80 — `CRMCase` "Legacy dispatch connector still dropping events"
  (Medium, resolves ~day 100, csat 3.0).
- Day 300 — `LifecycleChange(..., "steady_state")` +
  `HealthBandChange(..., "green", ("onboarding_complete", "stable_adoption"))`.

New artifact layers (U1) hang beats at three checkpoints:
- **Before (day 5)**: kickoff cadence still weekly, champion responsive
  (reply latency ~4h), Rocketlane "Kickoff" phase on track, no red flags.
  Milestone `activate_50pct_assets` not yet due.
- **During (day 50)**: two dispatch-integration cases already fired (day 0,
  day 30), champion reply latency stretching (4h → 30h+), calendar cadence
  weekly → biweekly, Rocketlane "Legacy Integration" phase `due_date` passed
  with `due_date_actual = null` (activation gap per
  `rocketlane_fixtures.has_activation_gap`), a third case about to fire
  (day 80).
- **After (day 310)**: post-recovery. Case day-80 long resolved, Rocketlane
  phase completed (dates consistent with the two live Rocketlane behaviors:
  phase `due_date_actual` = the write-day, not any earlier target), cadence
  back to weekly, `LifecycleChange`→`steady_state` and `HealthBandChange`→
  `green` already fired in the spine.

Briefing-level truth: the account is not churn risk — it is a **stalled
activation** caused by one recurring technical blocker (legacy dispatch
integration), not disengagement (case CSATs are mediocre, not hostile;
champion never goes silent, just slower). An ideal agent at day 50 should
name the blocker and the milestone at risk (`configure_routing` was hit on
time at day 35, but the *next* dependent milestone is what's actually
stuck), not generic "at risk" language. Evidence: the three
`integration`-topic cases (`det_id("case", pinehill_id, "legacy-dispatch-...")`),
the Rocketlane phase/task ids for "Legacy Integration", and the extractor's
reply-latency-trend signal for the champion contact.

### 2. Single-threaded-risk — `pinnacle-supply`

Persona: `at_risk_champion`. Industry: logistics, CSM `csm-101`.

Existing spine beats: Day 3 `ChampionGoesQuiet`; day 14
`HealthBandChange(..., "yellow", ("champion_inactive", "single_threaded_risk"))`;
day 110 `NewContactAppears("Monica Reeves", "VP Supply Chain Operations")`;
day 130 `HealthBandChange(..., "yellow", ("new_champion_engaged", "recovery_in_progress"))`
+ `CSATDecline`; day 240 `HealthBandChange(..., "green", ("new_champion_active", "recovery_complete"))`.

Checkpoints: day 10 (single point of failure exposed — one contact, gone
quiet, zero other stakeholder relationships), day 120 (second contact
surfaced but not yet the champion of record — thread width 2 but weak),
day 250 (recovered, thread width restored, StakeholderRelationship strength
`strong` for Monica Reeves).

Briefing-level truth: risk was structural (a one-person relationship graph),
not usage or product-driven — usage/health telemetry lag the real signal by
~11 days (champion quiet day 3, health band doesn't move until day 14). An
ideal agent should be able to flag the risk from communication/relationship
signals *before* the health band does. Evidence: `StakeholderRelationship`
rows (multi_thread_depth 1→2), email thread gap for the original champion,
`NewContactAppears`-sourced calendar invite for Monica Reeves' first meeting.

### 3. Churn-brewing — `quarrystone-logistics`

Persona: `at_risk_champion`. Industry: logistics, CSM `csm-104`. Existing
spine only has the terminal beat: day 220 `StatusChange(..., "Churned")` +
`HealthBandChange(..., "red", ("churned", "champion_never_replaced"))`. The
persona comment (`data_simulator.py`) states the champion departed at day 0
and was never replaced — that lead-up is currently un-scripted. **Extension**:
add to `SCENARIO_TIMELINE` (new entries, clearly commented as bible-driven):
`ChampionGoesQuiet("quarrystone-logistics", 0)`,
`TicketSpike("quarrystone-logistics", 160, 2)`,
`HealthBandChange("quarrystone-logistics", 180, "yellow", ("champion_unreplaced", "renewal_conversation_stalled"))`.
Add to `_CASE_SCHEDULE`: a day-160 case "Renewal terms discussion — no
response" (Medium, `renewal`, unresolved, csat `None`).

Checkpoints: day 30 (early — champion already quiet since day 0, but nothing
else has fired yet; this is the account's own version of red herring #1's
setup, except here it is real), day 190 (yellow band, unresolved renewal
case, zero calendar activity in 60 days), day 225 (post-churn, for contrast).

Briefing-level truth: the brewing signal is **absence** — no replacement
contact ever surfaces (compare to Pinnacle, where one does), zero calendar
events after day 0, and the day-160 renewal case goes unanswered. The
account was salvageable through day ~180 (single missing action: get a
replacement contact) but not after. Evidence: zero
`StakeholderRelationship` rows post day-0, the day-160 case id, the
absence of calendar `events.list` entries in the extractor's cadence window
day 130–190.

### 4. Silent-decline (green-but-quiet) — `aspenridge-supply`

Persona: `stable`. Industry: logistics, CSM `csm-102`. Existing spine: no
entries — a clean slate (deliberately not `redwood-fleet`, which is part of
the summer-dip cohort that gets a scripted `UsageGrowth` recovery at day
160–230; layering a permanent decline on top of a scripted recovery for the
same account would make the two beats fight instead of telling one story).
**Extension**: add `UsageDecline("aspenridge-supply", 90, 0.12, 0.15, end_day=300)`
— a slow, continuous decline with no accompanying `HealthBandChange` at any
point in the 365 days (this account's band stays at its green baseline for
the full simulation; that gap is the point of the arc).

Checkpoints: day 90 (pre-decline baseline), day 200 (usage genuinely down
~35% cumulative from baseline, band still green, zero cases, zero CTAs —
nothing in the CRM/CS-platform view looks wrong), day 340 (decline
continued, still green).

Briefing-level truth: this account IS at risk — sustained usage decline with
no case, no CTA, no health-band change to surface it. A briefing that only
reads `HealthScore`/`CTA` will call it fine; one that reads
`UsageSignal` trend + calendar cadence should not. This is the arc that
tests whether the briefing over-trusts the health band. Evidence: the
`UsageSignal` time series for `daily_active_assets` showing the two-stage
decline, and the extractor's meeting-cadence-shift signal (assume quarterly
business reviews continue on schedule — the account isn't disengaged from
the CSM relationship, just from the product).

### 5. Expansion-ready — `meridian-fleet`

Persona: `expanding`. Industry: fleet_management, CSM `csm-101`. Existing
spine: day 10 `NewContactAppears("Sarah Chen", "Facilities Manager")`; day 14
`UsageGrowth(0.15, 0.1, end_day=180)`; day 180 `ARRChange(36_000_000)`
(from $28M — see `synthetic_book.py` `_COMPANY` base); day 270
`UsageGrowth(0.4, 0.6, end_day=330)` (year-end).

Checkpoints: day 20 (new department stakeholder just onboarded, usage
climbing), day 170 (usage sustained high, ARR expansion about to close),
day 280 (expansion closed, year-end uptick in progress).

Briefing-level truth: multi-threaded growth (two departments, both active)
converging on a real expansion event already in the spine — the ARR change
at day 180 is the confirmation, not a prediction. An ideal agent at day 170
should flag expansion-readiness using the *pre*-day-180 signals (usage
growth + new stakeholder), not just restate the ARR change after it fires.
Evidence: Sarah Chen's `StakeholderRelationship` row, the `UsageSignal`
growth trend, calendar cadence increasing (weekly → 2x/week) in the run-up
to day 180.

### 6. Healthy-control — `trailhead-logistics`

Persona: `exemplary`. Industry: logistics, CSM `csm-101`. Existing spine:
day 80 `HealthBandChange(..., "green", ("exemplary_adoption", "strong_champion", "advocacy_active"))`;
day 100–150 mild `UsageDecline` (seasonal, recovers); day 165
`HealthBandChange(..., "green", (..., "case_study_published"))`; day 270–330
`UsageGrowth` (year-end).

Checkpoints: day 60, day 180, day 300 — chosen off-beat from the mild summer
dip specifically so this account reads as unambiguously fine at every
checkpoint (the point of a control is to be boring, not to straddle a
beat).

Briefing-level truth: no risk, no expansion trigger, no onboarding gap —
steady exemplary adoption throughout. This is the baseline every other
arc's briefing is judged against.

## Red herrings

Both look concerning in exactly one artifact class; every other artifact
class (and world truth) says the account was never actually at risk. A
narrative battery that can't tell these apart from the real arcs above is
not reading causally.

### Red herring A — `cedar-valley` (looks bad in usage telemetry only)

Existing spine: day 5 `UsageDecline(0.2, 0.3, end_day=30)`; day 30
`HealthBandChange(..., "green", ("renewed", "stabilizing"))` — the band
never leaves green; the "wobble" is a pre-renewal usage dip that resolves
itself, not an intervention. Add one CRMCase to `_CASE_SCHEDULE`: day 8,
"Requesting updated MSA redline for renewal paperwork" (Low, `renewal_admin`,
resolves day 25, csat 4.5) — routine renewal admin, not a support fire.
Rocketlane: no onboarding project (already steady-state). Checkpoint: day
18 — usage telemetry alone reads as an early risk signal; CRM case + the
day-30 renewal-closed beat (already scripted) say this was renewal
paperwork friction the whole time. World truth: never at risk.

### Red herring B — `ironridge-fleet` (looks bad in one CRM case only)

Currently unscripted (persona `stable`, no `SCENARIO_TIMELINE` entries, no
`_CASE_SCHEDULE` entries). Add one case: day 40, "Integration webhook
returning 500 errors intermittently" (High priority — the subject line
alone reads as a real integration failure like Pinehill's) resolving in 2
days with csat 5.0 (`resolve_after_days=2`). Add nothing else — usage stays
flat-normal for a `stable` persona, calendar cadence unchanged, no health
band ever moves. Checkpoint: day 42 — the case subject/priority alone
pattern-matches the Pinehill onboarding-stall signature; the fast
resolution + untouched usage/calendar say otherwise. World truth: a
same-day glitch, fixed same-week, never at risk.

## Boring controls (27 accounts)

Deliberately load no story beyond their existing persona baseline: the
specificity test for the whole battery — a briefing/extractor that flags
any of these at any checkpoint is over-triggering. From `synthetic_book.py`'s
`_ACCT_DATA`, every account not named above:

`ironhorse-freight`, `ridgeline-warehousing`, `northstar-couriers`,
`clearwater-field-ops`, `summit-industrial` (onboarding cohort, all
`fast_onboarding`/`normal_onboarding`, no risk beats); `crestline-distribution`,
`redwood-fleet`, `bison-transport`, `copperfield-warehousing`, `cascade-field`,
`timberline-logistics`, `falcon-delivery`, `mesa-industrial`,
`stonebridge-fleet`, `prairie-wind`, `granite-peak`,
`hawkstone-industries` (steady-state cohort — several of these carry mild
existing recovery arcs in the spine, e.g. Redwood/Bison's summer dip and
Hawkstone's leadership-change crisis; they are controls in the sense that no
*new* artifact layer is authored for them, not that the spine is silent —
the battery must not flag them worse than their own already-resolved spine
beats say); `oakmont-logistics`, `blueridge-transport`, `westfield-industrial`
(expanding cohort, no new layer); `sagebrush-transport`, `driftwood-warehousing`,
`cypress-field` (at-risk cohort with existing churn/recovery beats, no new
layer); `harborview-fleet`, `windmill-transport` (renewal cohort, no new
layer); `riverstone-logistics`, `dustbowl-freight` (already churned at day
0, no new layer).

## Battery assertion summary (Phase U3 preview)

For each of the 6 arcs' checkpoints: extractor surfaces the scripted signal
with correct evidence ids/values; briefing/sweep (for Rocketlane-rail
arcs — Pinehill today, others as future rails land) surfaces the arc's
truth. For the 2 red herrings and the 27 boring controls, at every
checkpoint: zero flags from the extractor beyond the single artifact class
each herring is designed to trip, and zero flags at all for controls.

## Anti-Goodhart note

This bible is authored once, before any extractor or battery code exists.
The battery may never be edited to match what the system actually outputs
without a corresponding change to this bible explaining why the *world*
changed (a new beat, a corrected date) — never to explain why the system's
output changed.
