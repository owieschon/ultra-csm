# Program Report 12 — Universe v2 WS-Data-Classes

Branch `codex/u2-classes` off synced `main` (tip `e3d6df7`, Program 10's
Universe v2 Foundations). Completes the data-class inventory so the
segmented book (wave 2) and new tenants (wave 3) have every class a
playbook's ground truth depends on: event-level telemetry, meeting
transcripts, a content catalog + one seeded campaign, quarterly surveys,
sales-to-CS handoff notes, and a job-change signal class. Every class is
causal exhaust of the existing bible timeline — no new story beats
invented, only existing ones rendered in a new medium. Entirely offline:
no credentials, no live-org access, no network calls. Committed as six
separate phases (`U2C.1`…`U2C.6`).

## DoD Evidence

| Phase | Result | Evidence |
| --- | --- | --- |
| 1: Telemetry event-level exhaust + fake transport + reconciliation | Complete | New `data_plane/telemetry_events.py`: deterministic login/feature_action/api_call event triples for Pinehill and Meridian only, derived from the SAME scripted `UsageDecline`/`UsageGrowth` mutations `book_simulator.py` already applies — a stable, deterministic rank over each account's asset pool selects which assets are "active" on a given day (nested as the count grows/shrinks, never reshuffled), correctly handling Meridian's over-provisioned `adoption_rate > 1.0` case. `daily_active_assets_from_events`/`adoption_rate_from_events` reproduce the simulator's own values exactly (0% error, comfortably inside the required ±2%) at every bible checkpoint for both accounts — the aggregation-derivation test the universe never had. A local fake HTTP transport (`make telemetry-simulated-live-csm`) serves the same events over the repo's existing `HttpRequest`/`HttpResponse` fake-client pattern; a thin reader consumes them back into the fixture shape. `eval/quantity_battery.py`: a bible-authored canon table of the enriched bodies' quantitative claims (Pinehill's "22 of 50 assets", "214 of 1,880", etc.), each asserted consistent with the simulator/telemetry value for that account/day within a stated tolerance — 3/3 cases, `hard_ok: true`. |
| 2: Meeting transcripts | Complete | New `data_plane/narrative_content/transcripts.py`: structured meeting notes (attendees + summary/decisions/actions) keyed by existing calendar-event `det_id`s, for exactly the seven beats named — Pinehill days 1/57/99, Meridian days 131/178, Trailhead day 175, Pinnacle day 112. Content cross-checked against canon (modules, error strings verbatim, cast voices). New `eval/transcript_battery.py`: error-string cross-reference (now spanning email + ticket + transcript), tier vocabulary check, attendee-consistency vs. the calendar fixture's own attendee list — 4/4 cases, `hard_ok: true`. Dormant until a future consumer reads it, stated explicitly in the module docstring. |
| 3: Content catalog + campaigns + engagement exhaust | Complete | `knowledge/tenants/fleetops/content_catalog.json`: 16 entries, all 8 canon capability keys covered at least once, plus onboarding/methodology entries, fictional canon-consistent titles. New `data_plane/campaigns.py`: one seeded campaign (Route Optimizer adoption, days 60–120, targeting `route_optimization`-entitled accounts with shallow depth) plus deterministic sends/opens/clicks exhaust per account per send, engagement rate derived from each account's existing persona (healthy personas engage, at-risk don't — no invented randomness). Owner Ask below lists the exact catalog ids wave 2 should wire into `playbooks.json`'s `content_refs`. |
| 4: NPS/CSAT surveys | Complete | New `data_plane/surveys.py`: quarterly schedule (days 45/135/225/315) for the six arc accounts + both herrings. Pinehill day-45 is a genuinely frustrated-register detractor citing "the dispatch integration," recovering to promoter by day 315; Quarrystone is non-response every single wave (absence again, consistent with its arc); Trailhead is a promoter with a case-study-consistent verbatim; Pinnacle/Meridian/Aspenridge track their own arc truth; both herrings are mid-range and benign at every wave. New "Survey canon table" in the bible's Class canon appendix, one row per account per wave with arc-consistency reasoning. |
| 5: Sales→CS handoff notes | Complete | `knowledge/tenants/fleetops/handoff_notes/<slug>.json` for all 8 accounts (six arcs + two herrings): why-they-bought, legacy system, success criteria, named stakeholders — all content already existed as bible dossier canon; this phase renders it as agent-readable data. Verbatim-consistency test: `legacy_system` matches the bible dossier string exactly for every account (including the three accounts where canon names none — `null`, not a fabricated system). |
| 6: Job-change signal class | Complete | New `data_plane/relationship_signals.py`: `JobChangeSignal` dataclass (new module, NOT added to `contracts.py`). Two fixture rows, both hanging on existing beats: Derek Vaughn's departure at Pinnacle day 5 (two days after the already-scripted `ChampionGoesQuiet` mutation — the enrichment signal that would beat silence-detection to the punch, well before the day-14 health-band move or the day-110 replacement contact), and a benign red-herring (Mike Lindgren's same-company promotion at Trailhead day 200). `job_change_signals_as_of` reader + 6 tests. Dormant until a lens/enrichment consumer reads it. |

## IF/THEN Branches Taken

- Reproducing `AdoptionSummary.active_assets` from raw events could have
  picked "any N of the account's assets" arbitrarily each day, which
  would make the active set reshuffle day-to-day for no reason (unlike a
  real fleet, which tends to keep the same subset of vehicles online) →
  built a stable deterministic rank over each account's full asset pool
  (`det_id`-derived) and took the top-N by that rank, so the active set
  nests monotonically as the count grows/shrinks — a real property a
  telemetry consumer could depend on, not an artifact of arbitrary
  selection.
- Sizing the asset-id pool off `entitled_assets` would have broken for
  Meridian, whose scripted `UsageGrowth` legitimately drives
  `active_assets` above `entitled_assets` at some checkpoints (real
  over-provisioned usage, matching the pre-existing fixture's own
  `westfield-industrial` row) → sized the pool by scanning the full
  365-day simulated timeline for each account's maximum `active_assets`,
  not by the static entitlement count.
- The megaprompt's Phase 1 wording implied a `description`-field-style
  contract widening was available for canary-style additions (a
  WS-Safety concern, not this workstream's) — not applicable here, no
  contract widening was needed or attempted for any of the six phases;
  `contracts.py` was never touched, per the ownership map.
- Full six-arc coverage for meeting transcripts was in scope only for the
  seven specifically-named beats (not every calendar event across every
  arc) → authored exactly those seven, no more, to avoid inventing
  meeting content the bible doesn't already imply a beat for.

## Consolidated Owner Ask

1. **Content catalog ids for wave 2's `playbooks.json` wiring** (leave
   `playbooks.json` itself alone, per this workstream's ownership map —
   wave 2 wires it): `content-live-map-quickstart` and
   `content-route-optimizer-adoption` /
   `content-route-optimizer-setup-video` are the two most directly
   reusable for the segmented book's tech-touch cohort actions (the
   seeded campaign already targets exactly this content/entitlement
   combination); the full 16-entry catalog spans all 8 canon modules if
   broader tier coverage is needed.
2. **Dormant classes awaiting a consumer:** meeting transcripts
   (`transcripts.py`), the job-change signal class
   (`relationship_signals.py`), and the campaign engagement exhaust
   (`campaigns.py`, beyond what the quantity/transcript batteries already
   check) — none are read by any live lens, sweep, or briefing path yet.
   Each module's own docstring states this explicitly so a future
   consumer doesn't have to rediscover it.
3. **Telemetry event exhaust is Pinehill + Meridian only**, per this
   phase's explicit scope — extending it to the other four arc accounts
   (or the 27 controls) is real future work, not silently assumed covered.

## STOP Conditions

No credentials were read, no live org was touched, no network call was
made anywhere in this program. `signal_extractor.py`, `contracts.py`,
existing `*_comms.py` message schedules/bodies, `synthetic_book.py`'s
account tables, and `eval/week1*` were never touched — verified both by
`git diff` review per phase and by `content-invariance-csm` re-running
byte-identical and unchanged at every one of the six phase boundaries
(no sanctioned regen was needed or used in this workstream, unlike
WS-Safety's sibling program). No test, threshold, or battery assertion
was weakened to pass. `playbooks.json` (Foundations' file, referenced but
not owned here) was never edited. Sentinel grep (`make hygiene`) clean.

## Skeptical Reviewer Paragraph

A skeptical reviewer should weigh three real limits. First, "the data-class
inventory is complete" should not be read as "every class is wired into
production" — five of this program's six new modules (telemetry events,
transcripts, the job-change signal class, and most of the campaign
engagement exhaust) are dormant corpus with zero live consumers, exactly
like Program 8's golden corpus before it. The value delivered here is
that a future consumer starts from real, canon-consistent content instead
of a blank page — not that agent behavior changes today. Second, the
telemetry reconciliation's "±2% tolerance" is satisfied trivially (0%
error) because the events are *derived from* the simulator's own
aggregate, not independently measured against it — this proves the
derivation is self-consistent, not that a hypothetical independently-
authored telemetry stream would agree with the simulator to within 2%.
Third, the NPS survey canon and the quantity-reconciliation canon table
are both hand-authored against the existing bible/enriched-body content;
they are internally consistent by construction and checked by their
respective batteries, but — like every other canon table in this
universe — they are only as trustworthy as the bible-first discipline
that produced them, not independently fact-checked against some external
ground truth that doesn't exist for a fictional company.

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `536 passed, 1 skipped` (up from Program 10's `491 passed, 1 skipped`) |
| `LC_ALL=en_US.UTF-8 make lint` | `All checks passed!` |
| `LC_ALL=en_US.UTF-8 make hygiene` | Exited 0 |
| `git diff --check` | Exited 0 |
| `LC_ALL=en_US.UTF-8 make content-invariance-csm` | `PASS: extractor output is byte-identical to the committed snapshot.` |
| `LC_ALL=en_US.UTF-8 make narrative-battery-csm` | `hard_ok: true`, 8/8 cases |
| `LC_ALL=en_US.UTF-8 make content-battery-csm` | `hard_ok: true`, 5/5 cases |
| `LC_ALL=en_US.UTF-8 make quantity-battery-csm` | `hard_ok: true`, 3/3 cases |
| `LC_ALL=en_US.UTF-8 make transcript-battery-csm` | `hard_ok: true`, 4/4 cases |
| `LC_ALL=en_US.UTF-8 make telemetry-simulated-live-csm` | `all_wire_matches_in_process: true` |
| `LC_ALL=en_US.UTF-8 make status` | `STATUS.md is current` |
