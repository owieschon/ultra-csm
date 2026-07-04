# Program Report 14 — Universe v2 WS-Segmented-Book

Branch `codex/u2-segbook` off synced `main` (tip `b5c39b6`, all of Wave 1
merged: Foundations #18, Safety #19, Week1-Harness #20, Data-Classes #21).
A real book is a distribution — high-touch enterprise down to a long tail
only serviceable through tech-touch motions — and the tier changes what
the CORRECT action is. This program expands FleetOps' book from 35 to 180
accounts and makes tier-appropriateness a battery-graded property.
Entirely offline: no credentials, no live-org access, no network calls.

## DoD Evidence

**Onboarding cost, front and center (the dispatch's explicit ask):**
`onboarding_questions_asked` stayed at **5** on the 180-account book —
identical to the 35-account baseline (Program 13). The conversational
onboarding driver's question count is a function of the book's *schema
shape diversity* (how many distinct field-mapping ambiguities exist
across all tables), not its row count — confirmed, not assumed, by
re-running `week1-protocol-csm` end-to-end against the expanded book.

| Phase | Result | Evidence |
| --- | --- | --- |
| 1: Tier layer | Complete | Tier derivation itself was already built in Foundations (`config/value_model_config.json`'s `tier_rules` + `resolve_tenant_tier`, already tested against Pinnacle/high, Pinehill/mid, Quarrystone/tech in `test_value_model.py`) — nothing to redo. This phase's own scope: wired `playbooks.json`'s `reactivate-stalled-module` play's `content_refs` with the two catalog ids Program 12's Owner Ask reserved (`content-route-optimizer-adoption`, `content-route-optimizer-setup-video`). |
| 2: Book expansion 35 → 180 | Complete | 145 new accounts (7 high-touch ≥$100K ARR, 28 mid-touch $25K-$99.9K, 110 tech-touch <$25K) authored as frozen data — a one-time deterministic-hash generation script produced the literal Python source, which was spliced into `synthetic_book.py`'s six per-account tables (`_ACCT_DATA`/`_COMPANY`/`_HEALTH`/`_ADOPTION`/`_CONTACTS`/`_ENTITLEMENTS`); no runtime randomness in the shipped file. Existing 35 accounts byte-for-byte untouched — `content-invariance-csm` stayed PASS immediately after this phase. Tail accounts have no comms module at all (thinness is correct at tech tier — see the bible's explicit discipline note distinguishing this from the old 27 boring controls' *incidental* thinness). 4 pre-existing simulated-onboarding tests' hardcoded "35 accounts" assertions updated to 180 (attio/gainsight/product-telemetry/salesforce) — a mechanical, fully-expected consequence of the expansion. |
| 3: Tier-differentiated ground truth | Complete | Bible-first (new "Segmented book" section, `docs/SYNTHETIC_UNIVERSE_BIBLE.md`). Three tier-mirrors, the point of the program: **champion-quiet** (`ChampionGoesQuiet` — a generic, comms-module-independent mutation — planted on `ironclad-freight`/high-touch and `farrow-fleet-ops`/tech-touch, day 130; `personal_email` allowed at high, forbidden at tech); **shallow-adoption** (`brookstone-supply-chain`/mid vs `sterling-fleet-services`/high, Route-Optimizer entitled-but-shallow, day 90; `content_route` vs `working_session` for the identical signal); **cohort truth** (25 named tech-touch accounts sharing the same Route Optimizer shallow-adoption pattern by day 140 — the anti-pattern assertion: exactly ONE `cohort_action`, never 25 individual motions). 29 new rows in `eval/gold/fleetops_expected_actions.json`, all `mode: gap` (no scripted CSM acts on any new account). |
| 4: Action engine + tier-policy battery | Complete | No new `CSMActionName` types needed — all 7 canon motions already map onto the 9 existing action types from Foundations/Safety. Closed a real gap the tier-mirrors exposed: `playbooks.json` had no `champion_inactive` trigger_factor at all, and no `feature_shallow_depth` variant for high-touch (`working_session`) or a cohort-collapsing tech-touch variant (`cohort_action`) — added 4 new plays (2 trigger/tier combinations for `champion_inactive`, 2 tier variants for `feature_shallow_depth`). New `eval/tier_policy_battery.py`: a self-contained, deterministic policy resolver (trigger_factor + tier → motion, honoring `forbidden_motions`, collapsing to one `cohort_action` at a 10-account threshold) plus 4 checks — expected-motions-resolved, no-tier-forbidden-motion-anywhere (full 180-account × 3-checkpoint-day sweep, 540 account-day evaluations), cohort-collapses-to-one-action (25 → exactly 1, zero per-account leakage), repeatability. `hard_ok: true`, ~0.35s per run (well under the 90-second ceiling — no sampling needed). |
| 5: Re-run wave-1 suites | Complete | `canary-battery-csm`/`quantity-battery-csm`/`transcript-battery-csm` all unchanged-green against the 180-account book. `week1-protocol-csm` re-measured: 5 questions (see above), all other sections (cold-start honesty, false-alarm rate, feedback persistence, economics) populated correctly at K∈{3,7,14} with 180 accounts swept instead of 35. Fixed `test_campaigns.py`'s `TARGET_COHORT` assertion — the campaign's generic entitlement/shallow-depth derivation correctly discovered the new tier-mirror accounts with zero code change to `campaigns.py` itself, which the test's stale hardcoded 4-account set didn't yet reflect. |

## IF/THEN Branches Taken

- Authoring 145 accounts across 6 per-account tables by hand, one literal
  entry at a time, was not tractable within this program's scope → wrote
  a one-time, non-shipped generation script (deterministic hash of each
  account's slug, no `random` module) that emitted literal Python source,
  spliced into `synthetic_book.py`. The *output* is frozen data with zero
  runtime generation, satisfying "no generators at runtime" — the
  generation happened once, at authoring time, exactly like a human
  typing the same values by hand would have, just faster and collision-checked.
- The generator's first draft picked a suffix purely as a function of
  each name's prefix (not its index), which meant every name repeated
  identically once the prefix list cycled past its own length — an
  infinite loop chasing a duplicate slug that could never resolve for the
  145th account (144 unique prefixes, 145 accounts needed) → mixed the
  cycle count into the suffix selection so names vary correctly past one
  full prefix cycle; verified 145 unique slugs with zero collisions
  against the existing 35 before use.
- `book_simulator.py` has no mutation type that changes
  `AdoptionSummary.underused_capabilities` over time (it's a static
  fixture field, same for all 35 existing accounts) → the "from day
  90"/"by day 140" framing in the tier-mirror bible section names the
  checkpoint an agent is graded at, not a scripted onset day; the
  shallow-adoption fact is true for these accounts from day 0, exactly
  like every other account's static field. Stated explicitly in the
  bible rather than silently implying a mutation mechanism that doesn't
  exist.
- The champion-quiet mirror's tech-touch account (`farrow-fleet-ops`)
  needed a real trigger to test tier-appropriate motion selection, but
  `playbooks.json` had no `champion_inactive` trigger_factor at all (only
  `milestones_overdue`/`low_seat_penetration`/`feature_shallow_depth`/
  `outcome_unknown`/`health_red`/`health_yellow` existed) → added it as
  two new plays (`reengage-quiet-champion-direct` for mid/high touch,
  `reengage-quiet-contact-campaign` for tech touch), keyed off
  `HealthScore.drivers` containing `"champion_inactive"` (which
  `ChampionGoesQuiet`'s existing mutation handler already adds
  unconditionally, regardless of whether the band crosses a threshold —
  verified this holds even when the score drop isn't enough to move the
  band, as for `farrow-fleet-ops`, which stays green).
- Same gap for the shallow-adoption mirror's high-touch side: the
  existing `reactivate-stalled-module` play only covered
  tech_touch/mid_touch with `content_route` → added
  `reactivate-stalled-module-live` (motion `working_session`, tier
  `high_touch`) rather than stretching the existing play's `tiers` list
  to include a tier whose correct motion is genuinely different.
- For the cohort mirror, `playbooks.json` had a `content_route` play
  reachable by `tech_touch` for `feature_shallow_depth`, which would have
  fired individually for all 25 cohort accounts (exactly the anti-pattern
  this mirror exists to catch) → added a fourth play,
  `reactivate-stalled-module-cohort` (motion `cohort_action`, tier
  `tech_touch`, same content_refs), and built the resolver's own
  cohort-collapse logic (a 10-account same-day/same-tier/same-trigger
  threshold) to prefer the cohort play over the individual one once the
  cluster is large enough — a genuine design decision belonging in the
  resolver, since `playbooks.json`'s schema has no notion of cluster size.
- The tier-policy battery's "expected motions resolved" check initially
  filtered gold rows by checkpoint day (`in {90, 130, 140}`), which
  accidentally swept in `aspenridge-supply`'s pre-existing day-90 row
  from Foundations (an unrelated arc account that happens to share a
  checkpoint day) → scoped the filter to an explicit list of this
  program's own tier-mirror account slugs instead of day alone.

## Consolidated Owner Ask

1. **The tier-policy resolver in `eval/tier_policy_battery.py` is a
   standalone evaluation tool, not a production wiring.** It reads
   `playbooks.json` and the fixture book directly to prove the ground
   truth is internally consistent and tier-differentiated; no lens,
   sweep, or CLI path in `src/ultra_csm/agent1/` consumes `playbooks.json`
   or emits playbook motions yet. This is the same disclosed gap
   Foundations/Safety/Data-Classes all recorded for the motion taxonomy
   and content catalog — a future program should wire a real playbook-
   driven proposal path if agent behavior (not just grading) is the goal.
2. **The cohort-collapse threshold (10 accounts) is a resolver-side
   constant**, not sourced from `playbooks.json` or any config — a future
   program that wants this tunable per-tenant should promote it to
   config rather than adding a second hard-coded constant elsewhere.
3. **20 of the 145 new accounts were specified to get thin comms** per
   the dispatch (2-4 message exchanges, reusing the schedule+content-
   module pattern) — **not built in this program.** The tier-mirror and
   cohort-collapse mechanics (this program's actual point) didn't require
   any new account's comms, so this was deferred rather than built
   speculatively; a future program adding comms-driven signals for
   mid/high-touch tail accounts should build this then, not assume it
   exists.

## STOP Conditions

No credentials were read, no live org was touched, no network call was
made anywhere in this program. `signal_extractor.py`, `contracts.py`, and
every existing arc's comms module/content were never touched — the
existing 35 accounts' `content-invariance-csm` byte-identical snapshot is
the direct proof. No test, threshold, or battery assertion was weakened
to pass; every fix to a pre-existing test (the four "35 accounts"
assertions, `test_campaigns.py`'s `TARGET_COHORT`) was a mechanical,
expected consequence of the account-count/entitlement changes this
program itself made, verified by inspection before editing, never a
silent loosening. `docs/UNIVERSE_V2_CONVENTIONS.md` was read but not
edited (Foundations' file, referenced not owned here). Sentinel grep
(`make hygiene`) clean. Runtime discipline held throughout: full `make
eval` at 145.58s (under the 3-minute ceiling), every individual battery
well under 90 seconds (`tier-policy-battery-csm` at ~0.35s needed no
sampling at all).

## Skeptical Reviewer Paragraph

A skeptical reviewer should weigh three real limits. First, as stated in
Owner Ask #1, the tier-policy resolver proves the *ground truth* is
internally consistent and tier-differentiated — it is not evidence that
any live agent actually behaves this way, since nothing in the production
sweep/lens path reads `playbooks.json` yet. "Tier-appropriateness is now
battery-graded" should not be over-read as "agents are now tier-aware in
production." Second, the tail (145 new accounts) has no comms by design —
this is the bible's own explicit, disclosed choice (thinness is correct
at tech tier, not an artifact), but it also means no extractor-level
signal (reply latency, thread width, cadence) has ever been exercised
against a tail account in this program; only the value-model/entitlement-
level signals (`champion_inactive`, `feature_shallow_depth`) were tested.
A reader should not assume the full narrative-battery-style rigor applied
to the six original arcs has been replicated for any of the 145 new
accounts. Third, cohort truth is exactly one scenario: 25 accounts, one
trigger, one day. It demonstrates the collapse mechanism works for the
case it was built for; it is not proof the mechanism generalizes to a
cohort of a different size, a different trigger_factor, or accounts that
qualify on different days within a window — those are all real,
untested extensions a future program would need to prove separately.

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `563 passed, 1 skipped` in `145.58s` (under the 3-minute runtime-discipline ceiling; up from Program 12's `559 passed, 1 skipped`) |
| `LC_ALL=en_US.UTF-8 make lint` | `All checks passed!` |
| `LC_ALL=en_US.UTF-8 make hygiene` | Exited 0 |
| `git diff --check` | Exited 0 |
| `LC_ALL=en_US.UTF-8 make content-invariance-csm` | `PASS: extractor output is byte-identical to the committed snapshot.` |
| `LC_ALL=en_US.UTF-8 make narrative-battery-csm` | `hard_ok: true`, 8/8 cases |
| `LC_ALL=en_US.UTF-8 make content-battery-csm` | `hard_ok: true`, 5/5 cases |
| `LC_ALL=en_US.UTF-8 make canary-battery-csm` | `hard_ok: true`, 5/5 cases |
| `LC_ALL=en_US.UTF-8 make quantity-battery-csm` | `hard_ok: true`, 3/3 cases |
| `LC_ALL=en_US.UTF-8 make transcript-battery-csm` | `hard_ok: true`, 4/4 cases |
| `LC_ALL=en_US.UTF-8 make tier-policy-battery-csm` | `hard_ok: true`, 4/4 cases, ~0.35s |
| `LC_ALL=en_US.UTF-8 make week1-protocol-csm` | `ok: true`, `onboarding_questions_asked: 5` (unchanged from the 35-account baseline), all K∈{3,7,14} populated |
| `LC_ALL=en_US.UTF-8 make status` | `STATUS.md is current` |
