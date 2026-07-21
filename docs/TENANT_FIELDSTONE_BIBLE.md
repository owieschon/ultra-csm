# Tenant Fieldstone Bible — the NORMS tenant

<!-- sourcebound:purpose -->
Fictional ground truth for `fieldstone`'s 12-account book. Same discipline
as `docs/SYNTHETIC_UNIVERSE_BIBLE.md` (fleetops): this bible is authored
before any fixture or battery code exists, and every generated artifact
must be causal exhaust of it. If an artifact for account X were shuffled
onto account Y, `eval/fieldstone_battery.py` must fail: X's evidence should
not support Y's story and vice versa. See `docs/UNIVERSE_V2_CONVENTIONS.md`
section 1 for `fieldstone`'s row in the tenant canon and D5 namespacing.
<!-- sourcebound:end purpose -->
<!-- sourcebound:allow doc-length reason="This file is the canonical Fieldstone fixture dataset" -->
<!-- sourcebound:allow section-length reason="Each tenant arc keeps its timeline and evidence together" -->

## Product canon

**Fieldstone Service Cloud** — field-service management SaaS for
HVAC/plumbing contractors. Five product modules (invented for this
tenant):

1. **Job Scheduling** — dispatch board, technician calendars, recurring
   job templates.
2. **Technician Dispatch** — real-time routing/assignment of field techs
   to open jobs.
3. **Quote-to-Invoice** — estimate generation through invoicing/payment
   collection.
4. **Customer Portal** — homeowner/property-manager self-service booking
   and job-status visibility.
5. **Parts Inventory** — truck-stock and warehouse parts tracking tied to
   job completion.

**Cast:**
- CSM `fs-csm-201` (Priya Anand) — high/mid-touch accounts.
- CSM `fs-csm-202` (Grant Bellamy) — mid/tech-touch accounts.
- Implementation Engineer `fs-ie-301` (Devon Cole) — onboarding delivery
  for high-touch accounts only (Fieldstone's cast is smaller than
  fleetops': no dedicated Rocketlane-style onboarding platform exists for
  this tenant — onboarding is HubSpot deal-stage-tracked, see Phase 3).

**Methodology name:** "Steady-State Service" — Fieldstone's own internal
name for its CS motion, reflecting the tenant's actual communication
culture (see "The norms" below): quarterly business reviews, not monthly;
meetings carry the relationship, not email threads.

## The norms (why this tenant exists)

Fieldstone's contractor customers are busy in the field, not at a desk.
Healthy communication for this tenant looks structurally different from
FleetOps':

- **Reply latency ~40 hours is HEALTHY**, not a red flag. A contractor
  owner checks email between jobs, typically once a day, sometimes every
  other day. FleetOps' `check_healthy_control` asserts `latency > 10`
  hours is already suspicious for its tenant; that exact assertion would
  misfire constantly here.
- **Quarterly meeting cadence is HEALTHY.** Fieldstone customers don't
  want a weekly sync — the relationship is carried by a QBR-style call
  every ~90 days, not high-frequency touch.
- **Meetings carry the relationship, sparse email is normal.** Each arc
  account gets roughly 6-10 email messages across the full year (vs.
  fleetops' pilot accounts, which run 15-20+ messages for a single arc) —
  by design, not thinness-as-artifact (the segmented-book bible's own
  discipline note about the difference between "correct thinness" and
  "artifact thinness" applies here too, at the account level rather than
  the tier level).
- **No CS platform exists for this tenant at all.** Fieldstone runs a
  HubSpot-shaped CRM (deals, associations, native tickets, lifecycle
  stages) and nothing else — no Gainsight-shaped health-score/CTA/
  adoption-summary source. Any code path that assumes a CS platform
  always exists (a health band, a CTA list, an adoption summary) must
  degrade to an honest `unknown`/`None` for this tenant, never fabricate
  one. See "No-CS-platform discipline" below.

**The tenant's entire purpose (Universe v2 D1 canon):** any absolute
communication threshold or Gainsight-shaped assumption hiding in the agent
fails here. A FleetOps-tuned reader would misclassify Fieldstone's
healthiest account as at-risk. Grading Fieldstone correctly requires
reading risk as a **delta from the account's own baseline**, not an
absolute value against a FleetOps-tuned threshold.

## No-CS-platform discipline

`CustomerDataPlane.cs` is a required field on the shared dataclass
(`contracts.py`) — Fieldstone cannot omit it the way
`onboarding: OnboardingConnector | None = None` supports omission. Instead,
`tenants/fieldstone/data_plane.py`'s `FieldstoneCSPlatformConnector`
implements the full `CSPlatformConnector` protocol but every method
returns the honest absence value the protocol already supports for a
"nothing here" answer:

- `get_company` → `None` (protocol already allows `CSCompany | None`).
- `get_health_score` → `None` (protocol already allows `HealthScore | None`).
- `list_ctas` / `list_success_plans` → `[]` (protocol already returns
  lists, empty is a legal, honest answer).
- `get_adoption_summary` → `None`.

No new "unknown" sentinel type is invented — the existing Optional/empty-
list vocabulary in `contracts.py` already expresses "nothing here," and
every existing consumer of these methods (e.g.
`value_model.build_customer_value_model`, which accepts
`adoption: AdoptionSummary | None`) was already written to treat `None`
honestly, not to assume presence. This is confirmed, not assumed: see
`_penetration_rail`/`_feature_depth_rail` in `value_model.py`, both of
which already branch on `adoption is None` and return a `RailState=
"unknown"` (penetration) or empty-factor (feature depth) result — exactly
the "never fabricate" behavior this tenant needs, already built for a
different reason (adoption may be legitimately absent even for fleetops
accounts) and now proven to generalize.

## The 12-account book

Same D2 thresholds as fleetops (`arr_cents >= 10_000_000` high,
`>= 2_500_000` mid, else tech): 2 high-touch, 4 mid-touch, 6 tech-touch.

| Slug | Name | ARR (cents) | Tier | Role |
| --- | --- | --- | --- | --- |
| `masonry-home-services` | Masonry Home Services | 14,500,000 | high | Arc F1 (norms proof) |
| `culvert-mechanical` | Culvert Mechanical | 11,200,000 | high | Arc F2 (real risk under slow norms) |
| `wrenhouse-hvac` | Wrenhouse HVAC | 6,800,000 | mid | Herring F-H1 |
| `shale-plumbing-group` | Shale Plumbing Group | 4,900,000 | mid | Boring control |
| `tanbark-mechanical` | Tanbark Mechanical | 3,600,000 | mid | Boring control |
| `cobblestone-hvac-co` | Cobblestone HVAC Co | 2,700,000 | mid | Boring control |
| `driftstone-plumbing` | Driftstone Plumbing | 1,900,000 | tech | Boring control |
| `quarrybed-mechanical` | Quarrybed Mechanical | 1,400,000 | tech | Boring control |
| `slaterock-home-services` | Slaterock Home Services | 980,000 | tech | Boring control |
| `graybrick-hvac` | Graybrick HVAC | 720,000 | tech | Boring control |
| `fieldstone-mortar-co` | Fieldstone Mortar Co | 510,000 | tech | Boring control |
| `hearthstone-plumbing` | Hearthstone Plumbing | 340,000 | tech | Boring control |

All fictional; account domains are `*.example` per repo hygiene
conventions. `det_id(*parts)` conventions namespaced with the tenant slug:
`det_id("fieldstone", "account", slug)`, etc. — see D5.

## Arc F1 — the norms proof (`masonry-home-services`)
<!-- sourcebound:allow section-length reason="The Arc F1 — the norms proof (`masonry-home-services`) reference keeps its ordered evidence and constraints together" -->

**Grading mode: `none`.** The correct read at every checkpoint is "no
action." This account is FleetOps-alarming and Fieldstone-healthy at the
same time — that contradiction is the entire point.

Timeline (day offsets from `SEED_DATE = 2026-06-21`, same seed convention
as fleetops):
- Champion: Renata Vaughn (owner-operator). One email thread, ~8 messages
  across the year, reply latency holding steady at 38-42 hours throughout
  — never trending, never a delta signal (this is the "flat baseline"
  case, not merely "high but declining").
- Calendar: one confirmed meeting roughly every 90 days (days 15, 105,
  195, 285) — a genuine quarterly cadence, never weekly, never trending
  wider (there is no "before" state to widen from; 90-day gaps are the
  baseline from day 1).
- Cases: zero. No support pressure at all across the year.
- No CS-platform health band exists for this tenant (see discipline
  above) — there is nothing to read as "green," and no code path may
  invent one.

**Checkpoint truths (verified against `signal_extractor.reply_latency_trend`
computed over the actual fixture, not estimated):**
- **Day 60**: latency trend `None` — insufficient reply history in one or
  both trailing 21-day windows this early (sparse, quarterly-adjacent
  messaging means the two-full-window precondition isn't met yet) —
  fail-closed, not a defect. Cadence shift: insufficient history (only
  one confirmed meeting by day 60, `meeting_cadence_shift` needs two
  gaps). Zero risk flags either way.
- **Day 180**: latency trend computable: delta -0.5h (37.5h trailing-21d
  mean vs. 38.0h prior-21d mean) — a flat, near-zero delta, exactly the
  "no risk" signature. Zero risk flags.
- **Day 300**: latency stays flat throughout (same 37-42h band every
  exchange all year); zero cases ever. Zero risk flags.

Briefing-level truth: this account is not a signal of anything. An ideal
agent reading it with FleetOps' absolute thresholds (`latency > 10h`,
frequent-meeting expectation) would misfire loudly; an ideal agent reading
it against Fieldstone's own norms (delta-from-baseline, not absolute)
correctly reports nothing to do.

## Arc F2 — real risk under slow norms (`culvert-mechanical`)
<!-- sourcebound:allow section-length reason="The Arc F2 — real risk under slow norms (`culvert-mechanical`) reference keeps its ordered evidence and constraints together" -->

**Grading mode: `none` through day 89, `gap` from day 90 onward.** The
scripted CSM never acts (there is no scripted CSM action in this fixture
layer at all, consistent with the dispatch's "gap" semantics: the agent's
recommendation is the only correct action).

Timeline:
- Champion: Marcus Oduya (ops manager). One email thread.
- Days 1-89: reply latency holding at the account's own healthy baseline,
  36-38 hours (statistically indistinguishable from Masonry's baseline —
  this account's "before" state IS a Fieldstone-normal account; verified:
  at day 80 the computed trend is delta -0.5h, 37.5h trailing-21d mean vs.
  38.0h prior-21d mean — the identical delta Masonry shows at day 180).
- Days 90-150: latency stretches steadily — 77h (day 95), 78h (day 103),
  102h (day 123), 102h (day 130), 132h (day 140) — a real delta from the
  account's OWN ~37h baseline, not merely "high in absolute terms" (which
  would also have to indict Masonry, whose own absolute band overlaps
  Culvert-Mechanical's pre-day-90 numbers exactly). Verified: at day 140
  the computed trend is delta +26h (104.0h trailing-21d mean vs. 78.0h
  prior-21d mean) atop an absolute level already well above the tenant's
  ~37-40h healthy band.
- One case opens day 100 (quote-to-invoice billing dispute, unresolved
  through day 150) — support pressure compounding the comms signal.
- Calendar: the day-90 quarterly meeting (due ~day 105 per the account's
  own cadence) is never scheduled — a missed beat against the account's
  own established rhythm, not an absolute "too few meetings" judgment.

**Checkpoint truths (verified against the actual fixture):**
- **Day 80**: latency delta -0.5h (37.5h vs 38.0h prior window) — matching
  baseline exactly. NO FLAG — this is this tenant's (and this account's
  own) normal, exactly like Masonry. Grading mode `none` here: any flag
  at day 80 is a false alarm.
- **Day 140**: latency delta +26h (104.0h trailing-21d mean vs 78.0h
  prior-21d mean), computed the same way
  `signal_extractor.reply_latency_trend` already computes deltas, atop an
  absolute level (100h+) far outside the tenant's healthy band; the
  day-100 case is still open 40 days later; and the day-90 quarterly
  meeting never happened. Grading mode `gap`: a correct agent must flag
  this by day 140; silence is a failure. The flag's evidence must cite
  the DELTA and the account's own baseline (not a bare "over 40 hours,"
  which would also indict Masonry) — the missing quarterly meeting, and
  the open case.

Briefing-level truth: this is the tenant's proof that "risk = delta from
tenant baseline" is a real, gradeable distinction, not a rhetorical one —
Masonry's day-180 delta (-0.5h) and Culvert-Mechanical's own day-80 delta
(-0.5h) are computed identically from the same signal family, and only
one of the two accounts later develops a real, large delta. The correct
discriminator is trajectory, not level.

## Herring F-H1 — the loud-looking non-event (`wrenhouse-hvac`)

**Grading mode: `none`.** One case: a P1-labeled "Customer portal down for
all users" ticket, opened day 45, resolved same day (4 hours) — loud
subject line, zero actual duration or recurrence. Everything else about
the account (latency ~40h flat, quarterly cadence, no other cases) reads
exactly like a Fieldstone boring control. `eval/fieldstone_battery.py`
must assert zero flags at every checkpoint — the same "specificity is a
hard assertion" discipline as fleetops' `cedar-valley`/`ironridge-fleet`
herrings.

## Boring controls (9)

`shale-plumbing-group`, `tanbark-mechanical`, `cobblestone-hvac-co`,
`driftstone-plumbing`, `quarrybed-mechanical`, `slaterock-home-services`,
`graybrick-hvac`, `fieldstone-mortar-co`, `hearthstone-plumbing`. Each:
flat ~40h latency (or no email thread at all for the smallest tech-touch
accounts, consistent with the segmented-book bible's "thinness is correct
at tech tier" discipline — a tech-touch Fieldstone account may have zero
email fixture, same as fleetops' tail), quarterly-or-absent meeting
cadence, zero or one case with no drama, zero risk flags at any
checkpoint. Together with Arc F1 (2 high-touch: `masonry-home-services`,
`culvert-mechanical`), Herring F-H1 (`wrenhouse-hvac`, mid-touch), and the
remaining boring-control mid-touch accounts (`shale-plumbing-group`,
`tanbark-mechanical`, `cobblestone-hvac-co`), the 12-account book resolves
to exactly 2 high-touch / 4 mid-touch / 6 tech-touch per D2.

## Canary spec

Per D4: `CANARY-fieldstone-<account_slug>-<8hex>`, placed (1) on each
account's `description`-equivalent field (Fieldstone's canary registry,
mirroring `canary_registry.py`'s pattern but namespaced), and (2) one
internal-note comment verbatim on `culvert-mechanical`'s day-100 case
(the one case fixture with an internal-note channel available). Never in
an email body. Same assertion as fleetops: no agent-produced artifact may
contain any canary token, including the account's own.

## Grading-mode summary

| Account | Mode | Checkpoints |
| --- | --- | --- |
| `masonry-home-services` (F1) | `none` | 60, 180, 300 |
| `culvert-mechanical` (F2) | `none` (day 80), `gap` (day 140) | 80, 140 |
| `wrenhouse-hvac` (F-H1) | `none` | 60, 180, 300 |
| 9 boring controls | `none` | 300 (spot day) |

## Anti-Goodhart note

Same discipline as the fleetops bible: this document is authored once,
before `eval/fieldstone_battery.py` exists. The battery may be edited to
add cases or correct an assertion against a bible change — never to match
whatever the system currently outputs.
