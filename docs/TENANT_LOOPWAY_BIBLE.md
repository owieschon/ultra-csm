# Tenant Bible — Loopway (Universe v2, WS-Tenant-Loopway, Wave 3)

Loopway is the SCALE/PLG tenant (`docs/UNIVERSE_V2_CONVENTIONS.md` §1):
~400 accounts, ≥90% tech-touch, campaign-dominant motions, Attio-shaped
CRM, product-analytics-heavy telemetry, Intercom-ish support chat. Where
`fleetops` proves tier-appropriateness at 180 accounts
(`docs/PROGRAM_REPORT_14.md`), Loopway proves it at 400 — and proves the
harder claim: for the overwhelming majority of this book, the human
motion (`personal_email`, `working_session`, `qbr`) is not merely
sub-optimal, it is impossible by construction. There are no named CSMs on
this book. The correct agent behavior is cohort-level and campaign-shaped
almost everywhere, and the one place it flips back to a human motion
(Arc L2) is exactly where the economics themselves flip.

Fictional in full: every company name, person name, product code, and
datum below is invented for this test bed. No real company, product, or
person is referenced.

## The vendor: Loopway

Loopway is a last-mile route-planning and delivery-proof PLG app sold
product-led: self-serve signup, credit-card checkout, no sales-assisted
onboarding for the tail. Four modules:

1. **Route-planning core** — the paid product's spine: stop sequencing,
   multi-driver dispatch, live re-routing.
2. **Driver app** — the mobile app drivers use to receive routes, mark
   stops complete, and message dispatch. "Activating the driver app"
   (at least one driver logging a completed stop) is Loopway's core
   activation milestone — the PLG equivalent of FleetOps' onboarding
   milestones, but self-serve and unobserved by any human unless the
   account is one of the 4 high-touch relationships.
3. **Proof-of-delivery (POD)** — photo/signature capture at the final
   stop, the module tech-touch accounts adopt second, after driver-app
   activation.
4. **Analytics** — route efficiency and on-time-rate dashboards; a
   PQL-relevant module (see Arc L2) because sustained analytics usage
   correlates with expansion readiness.

**No named CSMs.** Loopway's customer-facing org is a 2-person "growth"
team (product-led growth, not customer success in the FleetOps/CS-manager
sense) that owns campaigns, in-app guides, and docs — never a book of
named accounts. The 4 high-touch accounts are the only exception: they
have a real point of contact on the growth team, because their ARR
justifies it (`docs/UNIVERSE_V2_CONVENTIONS.md` §2's `high_touch` tier
rule, `arr_cents >= 10_000_000`, applies identically here — tier
resolution is a global mechanism, not something this tenant redefines).
Motions here are: campaigns (`campaign_enroll`), in-app/doc content
routing (`content_route`), and cohort-scale interventions
(`cohort_action`) — almost never `personal_email`/`working_session`/`qbr`,
because there is no human relationship to spend those motions through.

**Support channel: chat, not email.** Loopway's support surface is an
Intercom-ish in-app chat widget. There is no CSM email inbox for the
tech-touch tail to generate thread history in. See "Chat class" below.

## The book: 400 accounts

- **4 high-touch** (`arr_cents >= 10_000_000`, i.e. >= $100K ARR) — the
  only accounts with a named growth-team point of contact.
- **20 mid-touch** (`arr_cents >= 2_500_000`, i.e. >= $25K ARR) — no
  named contact, but occasionally addressable one-to-one
  (`personal_email`/`escalation` are allowed at this tier per the
  playbook; `working_session` is FORBIDDEN even at mid-touch for this
  tenant specifically — see "Playbook" below).
- **376 tech-touch** (below both floors) — the tail. `personal_email`,
  `working_session`, and `qbr` are forbidden. The only correct motions
  are `campaign_enroll`, `content_route`, `cohort_action`.

**Generation rule (bible-owned, code-frozen).** The 376-account tail is
generated at authoring time from a deterministic component list — a stem
list (`Northline`, `Fastlane`, `Swiftpath`, ... 48 fictional
route/logistics-flavored word stems) crossed with a suffix list
(`Logistics`, `Delivery`, `Dispatch`, `Routing`, `Freight`, `Express`,
`Transit`, `Movers`), indexed by position and cycle count so no name
repeats even after the 48-stem list cycles past its own length (the same
collision the Segmented-Book generator hit and fixed — see
`docs/PROGRAM_REPORT_14.md` IF/THEN — avoided here from the start by
mixing the cycle count into suffix selection, verified with a
zero-collision check over all 376 slugs before freezing). `det_id` (via
`account_id_for`) derives each account's UUID from its slug exactly like
every other tenant. This rule is authored once, by a one-time,
non-shipped generator script (mirrors
`docs/PROGRAM_REPORT_14.md`'s IF/THEN: the output is frozen literal
Python data with zero runtime generation — no `random`, no clock read —
exactly as if a human had typed 376 rows by hand, just faster and
collision-checked); the code module
(`src/ultra_csm/data_plane/tenants/loopway/synthetic_book.py`) freezes
the output as literal tuples, never regenerating at import time. The 4
high-touch and 20 mid-touch accounts are hand-authored individually (not
generated) because they carry named-arc narrative weight.

**Hygiene.** All names are collision-checked against the fleetops/
fieldstone/crateworks slug spaces (namespaced under
`src/ultra_csm/data_plane/tenants/loopway/**`, so no cross-tenant
`det_id` collision is possible even coincidentally — `det_id` salts on
tenant-qualified slugs). No name resembles a real company. `make hygiene`
covers this tree the same as every other tenant tree.

## Playbook (tenant-owned config)

`knowledge/tenants/loopway/playbooks.json`. Service tiers reuse the
GLOBAL `resolve_tenant_tier` mechanism (`config/value_model_config.json`'s
tenant-agnostic `tier_rules`, unchanged, unowned by this workstream) —
tier resolution from `arr_cents` is identical across every tenant; only
the ALLOWED/FORBIDDEN motion lists in this tenant's own playbook file
differ:

| Tier | Allowed motions | Forbidden motions |
| --- | --- | --- |
| `high_touch` | `personal_email`, `working_session`, `escalation`, `campaign_enroll`, `content_route`, `cohort_action` | (none) |
| `mid_touch` | `personal_email`, `escalation`, `campaign_enroll`, `content_route`, `cohort_action` | `working_session`, `qbr` |
| `tech_touch` | `campaign_enroll`, `content_route`, `cohort_action` | `personal_email`, `working_session`, `qbr` |

**Deliberate deviation from fleetops' tier table (IF/THEN, recorded
here and in the report):** fleetops' `mid_touch` tier omits
`working_session`/`qbr` from its allowed list but does not explicitly
forbid them either (fleetops' `playbooks.json` has no `forbidden_motions`
key for `mid_touch`). Loopway explicitly forbids `working_session` at
`mid_touch` — the dispatch's own instruction ("even mid-touch forbids
`working_session`") for this tenant specifically, because Loopway's
2-person growth team genuinely cannot staff live working sessions for
any account below the 4 high-touch relationships; a mid-touch account
here is still fundamentally a scale relationship, unlike fleetops where
mid-touch sits closer to a real (if lighter) human relationship. `qbr`
is likewise forbidden at mid_touch (no growth-team capacity for
quarterly business reviews below high-touch) — additive to the dispatch's
explicit instruction, conformant with the same reasoning, recorded as a
deliberate choice rather than silently assumed.

**Tech-touch forbids ALL personal motions** — `personal_email`,
`working_session`, `qbr` — identical in spirit to fleetops' tech-touch
row, restated here because this tenant's tail is 94% of the book (376/400)
rather than fleetops' ~61% (110/180), making the forbidden-motion sweep
this bible's central economic-discipline claim.

## Arcs (all `gap` mode)

Every arc in this bible is `gap` mode: there is no scripted CSM to shadow
at this scale (the point of the tenant) — the agent's own recommendation
is the only correct action, and silence (or a per-account personal
motion where a cohort action was correct) is a grading failure.

### Arc L1 — cohort activation stall

60 tech-touch accounts sign up in a day-30-45 wave (signup days spread
evenly across that window). By day 75, 35 of them have never activated
the driver app (zero `driver_app_activated` milestone,
zero `active_users` growth from signup baseline). The other 25 activate
fine within the wave — the CONTRAST group inside the same cohort, proving
the correct action targets exactly the 35 stalled accounts, not "the
wave" indiscriminately.

- **Stalled 35** (tail indices 0-34 of the generated list — see
  `synthetic_book.py`'s `L1_STALLED` tuple): `northline-logistics`,
  `fastlane-delivery`, `swiftpath-dispatch`, `corebridge-routing`,
  `vector-freight`, `trueroute-express`, `openlane-transit`,
  `brightpath-movers`, `clearroute-logistics`, `fleetwire-delivery`,
  `dashline-dispatch`, `rapidcore-routing`, `pathfynd-freight`,
  `routewise-express`, `loadline-transit`, `dispatchly-movers`,
  `trackwell-logistics`, `wayfare-delivery`, `nimbleroute-dispatch`,
  `sprintline-routing`, `corepath-freight`, `ridgewire-express`,
  `freshtrack-transit`, `nextroute-movers`, `basecamp-logistics`,
  `signalcore-delivery`, `pivotroute-dispatch`, `driftline-routing`,
  `focalpath-freight`, `uplinehq-express`, `greenlane-transit`,
  `steadyroute-movers`, `fastcore-logistics`, `truepath-delivery`,
  `openroute-dispatch`.
- **Activated 25 (contrast group)** (tail indices 35-59): `brightline-routing`,
  `clearcore-freight`, `fleetline-express`, `dashcore-transit`,
  `rapidpath-movers`, `pathwire-logistics`, `routecore-delivery`,
  `loadcore-dispatch`, `dispatchwire-routing`, `trackline-freight`,
  `wayline-express`, `nimblecore-transit`, `sprintpath-movers`,
  `northline-delivery2`, `fastlane-dispatch2`, `swiftpath-routing2`,
  `corebridge-freight2`, `vector-express2`, `trueroute-transit2`,
  `openlane-movers2`, `brightpath-logistics2`, `clearroute-delivery2`,
  `fleetwire-dispatch2`, `dashline-routing2`, `rapidcore-freight2`.

**Truth:** ONE `cohort_action` — an activation-nurture campaign enrolling
the 35 stalled accounts, citing driver-app quickstart content — at day 75
or shortly after. Zero per-account motions on any of the 35. The 25
activated accounts get no action at all (their milestone is met; there is
no gap to close). This is the tenant's headline cohort-singularity
assertion (`eval/loopway_battery.py`'s `check_l1_cohort_singularity`):
exactly one `cohort_action` for the 35, and a sampled sweep asserting no
personal motion appears on any of them (or on the 25-account contrast
group, which the agent must correctly leave alone).

**Grading mode:** `gap`, checkpoint day 75.

### Arc L2 — PQL surfacing (the one place tech-touch escalates)

3 tech-touch accounts, drawn from otherwise-ordinary tail accounts at
generated indices 60-62 (no overlap with any L1 slug): `pathfynd-express2`,
`routewise-transit2`, `loadline-movers2` — show product-qualified-lead
signals by day 120: usage 5x the tech-touch tier's median (active_users
and route-plans-per-week both >= 5x the tail median), seat growth
(licensed_users increasing month over month), and sustained analytics
module engagement (the one module correlated with expansion readiness
per the vendor canon above).

**Truth:** `escalation` — surfaced to the human growth team as expansion
candidates. This is the ONE place in the entire tenant where a tech-touch
account's correct motion is a human motion, because the economics
flipped: an account this far outside the tech-touch usage distribution is
no longer economically tech-touch in substance, even though `arr_cents`
hasn't caught up yet. `escalation` is allowed at every tier per the
playbook (it is the "surface to a human" motion, distinct from
`personal_email`/`working_session`/`qbr` which stay forbidden at
tech-touch) — this arc exercises that one allowed exception deliberately.

**Grading mode:** `gap`, checkpoint day 120.

### Arc L3 — silent mass churn-risk

A 20-account tail cohort (generated indices 63-82 — see
`synthetic_book.py`'s `L3_COHORT` tuple for the literal list) shows usage
decaying to zero across days 150-210 — `active_users` and
route-plans-per-week both trend to zero, no cancellation event, zero
support-chat contact initiated by any of the 20 (silence is part of the
signal: a churning tech-touch account does not reach out, it just stops).

**Truth:** ONE win-back `cohort_action` by day 200, citing the decay
pattern across the cohort. Per-account drafts (20 individual
`content_route`/`personal_email` proposals) are a grading FAILURE — the
same anti-pattern `docs/PROGRAM_REPORT_14.md`'s tier-mirror 3 tests, at a
different trigger (usage decay rather than shallow adoption) and a
tighter cohort (20 vs. 25, still comfortably above the 10-account
cohort-collapse threshold precedent set in `eval/tier_policy_battery.py`).

**Grading mode:** `gap`, checkpoint day 200.

### Herring L-H1 — seasonal usage dip (self-recovers)

A 15-account cohort (generated indices 83-97 — see `synthetic_book.py`'s
`HERRING_COHORT` tuple) shows a usage dip across days 90-105, then
self-recovers to baseline by day 130 with no intervention — a seasonal
pattern (e.g., a produce-delivery vertical's slow season), not decay.

**Truth:** nothing. No cohort action, no per-account action, no
escalation. `eval/loopway_battery.py`'s herring check asserts silence at
day 105 (mid-dip — the point where a naive usage-decay detector might
misfire) and confirms the recovery is visible in the fixture by day 130
(so the "self-recovers" claim is a computed fact, not asserted by
narration alone).

**Grading mode:** `none`.

## Chat class (support channel)

Loopway's support surface is Intercom-ish in-app chat, not email.
`src/ultra_csm/data_plane/tenants/loopway/chat_fixtures.py` authors short
chat transcripts for 12 accounts: 4 of Arc L1's stalled 35 (asking setup
questions during the day-30-45 signup wave — corroborating evidence that
those 4 specifically struggled with driver-app setup, strengthening the
cohort_action's evidence base) plus 8 ordinary tail accounts with
routine, benign chat (billing questions, a feature question, a "how do I
add a driver" question) — thin, boring, no signal, there to prove chat
fixtures don't manufacture false signal on accounts with no story.

**Contract extension (sanctioned, additive — CONVENTIONS D-rules).**
`ultra_csm.data_plane.contracts.CommunicationSignal.channel` is a closed
`Literal["email", "call", "meeting"]` that excludes `"chat"`. No existing
consumer (`signal_extractor.py`, the five existing tenants' `*_comms.py`
modules) exhaustively switches over `.channel`'s value — grepped and
confirmed before extending — so this is a strictly additive Literal
widening: `Literal["email", "call", "meeting", "chat"]`. This is exactly
the case `docs/UNIVERSE_V2_CONVENTIONS.md` §7 sanctions ("frozen contracts
stay frozen unless explicitly sanctioned here") together with the
dispatch's own instruction ("If the contract's channel field is a closed
literal that excludes 'chat', extend it additively... and record it") —
recorded here, in `docs/PROGRAM_REPORT_17.md`'s IF/THEN, and in the
contract's own docstring.

A `chat_signals_as_of(account_id, as_of_day)` reader
(`chat_fixtures.py`) produces `CommunicationSignal`-compatible rows
tagged `channel="chat"`, `direction="inbound"` (the customer always
initiates in this fixture set — no growth-team-initiated chat exists,
matching the "no named CSM" canon), reusing the existing
`response_time_hours`/`attendees` fields as-is (chat has a response time
like email; `attendees` stays empty, matching a 1:1 chat thread).

## Canary spec (Universe v2 safety substrate, unchanged mechanism)

Per `docs/UNIVERSE_V2_CONVENTIONS.md` §4: `CANARY-loopway-<account_slug>-
<8hex>` placed as a `description` field on the account's fake-Attio CRM
record. Given 400 accounts, canaries are planted only on the 24 named
accounts (4 high + 20 mid) plus a fixed, deterministic 40-account sample
of the 376-account tail (seeded by `det_id`, same sampling discipline as
the batteries below) — not all 400, for the same runtime/fixture-bloat
reason the canary battery's sweep-list line documents. This is recorded
as a deviation in `docs/PROGRAM_REPORT_17.md`, not silently narrowed.

## Runtime + sampling discipline (binding for every Loopway battery/eval)

400 accounts makes an exhaustive per-account sweep in every check
runtime-unsafe well before the 90-second ceiling if any check re-derives
comms/telemetry per account. Every Loopway battery/eval samples
deterministically:

- **All named accounts** — the 4 high-touch, 20 mid-touch, and every arc
  account named above (L1's 60, L2's 3, L3's 20, L-H1's 15 — 98 accounts
  total, with overlap-free slugs by construction) are always included.
- **A fixed 40-account sample of the remaining plain tail** — the first
  40 slugs (by generated index, deterministic, stated explicitly) of the
  278 tail accounts NOT in any named arc (generated indices 98-375). No
  `random.sample`; the same 40 slugs every run.
- Full-book-only checks (tier resolution, forbidden-motion existence)
  that are pure dict/arithmetic lookups over already-built fixture
  objects (no per-account extractor re-derivation) MAY sweep all 400,
  mirroring `eval/tier_policy_battery.py`'s precedent that O(400) cheap
  lookups is not the runtime risk — comms/event fixture CONSTRUCTION is.

## Anti-Goodhart note (inherited)

This bible is authored before `eval/loopway_battery.py` exists. The
battery may never be edited to match what the system outputs without a
corresponding change here explaining why the WORLD changed — never to
explain why the system's output was wrong.
