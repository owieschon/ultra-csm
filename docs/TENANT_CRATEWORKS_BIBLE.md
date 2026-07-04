# Tenant Crateworks Bible

Fictional ground truth for `crateworks` (Universe v2, Wave 3, WS-Tenant-Crateworks).
Same discipline as `docs/SYNTHETIC_UNIVERSE_BIBLE.md` (the fleetops bible):
this document is the deterministic script every generated artifact must be
causal exhaust of; `eval/crateworks_battery.py` grades against this file,
never the other way around (anti-Goodhart rule, `docs/UNIVERSE_V2_CONVENTIONS.md`
section 7).

## 0. Canon

**Product.** Crateworks WMS — warehouse management SaaS. Four modules:
`inbound_receiving`, `pick_pack`, `slotting_optimization`, `carrier_manifest`.

**Vertical.** Warehouse/3PL operations (per `docs/UNIVERSE_V2_CONVENTIONS.md`
section 1's tenant-canon table).

**CS org.** One named CSM, `csm-cw-01` ("the Crateworks CS desk") — a solo CS
team. Realistic for this segment: no bench, no coverage model, no
methodology beyond an onboarding checklist kept in a spreadsheet (there is
no Rocketlane/Gainsight-shaped CS platform at all for this tenant — see
"Vendor stack" below). This is a smaller org than fieldstone's meeting-heavy
team or fleetops' multi-CSM roster, consistent with a HYGIENE tenant: the
mess isn't malice, it's under-resourcing.

**Vendor stack (per CONVENTIONS section 1).** No CRM vendor at all — CS
lives in a homegrown spreadsheet-turned-database whose only "API" is a
CSV-export-shaped flat table dump, ingested via the existing flat
`ingest_external_book`/`ingest_book` path (`src/ultra_csm/data_plane/external_book.py`,
`docs/PROGRAM_REPORT_3.md`'s corpus-A precedent). A thin Zendesk-ish ticket
transport supplies support-case history (see Phase 2 fixtures). No CS
platform, no product telemetry vendor — value-model rails that require
those sources are `unknown` here by design, same honest-degradation posture
`fieldstone`'s bible documents for its own no-CS-platform gap (see
CONVENTIONS section 1's fieldstone row) but for the *entire* CRM layer, not
just the CS-platform layer: crateworks is the tenant where almost nothing
is clean at the source, not just absent at the vendor layer.

## 1. The ten-account book

1 high / 3 mid / 6 tech, matching the megaprompt's required split. Account
ids are `det_id("account", slug)` (existing convention, `fixtures.py`).
ARR bands follow `docs/UNIVERSE_V2_CONVENTIONS.md` section 2's tier
resolution (`arr_cents >= $100K` high, `>= $25K` mid, else tech).

| Slug | Tier | ARR (cents) | Role |
| --- | --- | --- | --- |
| `crateworks-dockside-storage` | high_touch | 18,000,000 | Arc C1 host account (see section 2) |
| `crateworks-northgate-3pl` | mid_touch | 6,000,000 | control |
| `crateworks-portline-logistics` | mid_touch | 4,200,000 | control |
| `crateworks-summitcrate-storage` | mid_touch | 3,000,000 | control |
| `crateworks-basinwood-supply` | tech_touch | 900,000 | control |
| `crateworks-drydock-warehousing` | tech_touch | 700,000 | control |
| `crateworks-fernbridge-distro` | tech_touch | 650,000 | control |
| `crateworks-ledgerport-storage` | tech_touch | 500,000 | control |
| `crateworks-mossway-crating` | tech_touch | 400,000 | control |
| `crateworks-quillstack-3pl` | tech_touch | 350,000 | control |

All ten accounts carry the mess spec (section 3) at their full authored
quota, including the seven controls — the mess is a property of the whole
book, not just the arc account, exactly as a real homegrown export would
be uniformly bad across every row.

## 2. Arc C1 — the fading champion, read through the mess (`gap` mode)

**Host account:** `crateworks-dockside-storage`.

**World truth.** Dana Okafor (VP Warehouse Ops) is Dockside's champion.
Her engagement genuinely fades across days 60–200: reply cadence and
enthusiasm decline, then Dockside's warehouse-ops function is folded into
an acquiring parent company's shared-services group around day 130, and
Dana's day-to-day account ownership quietly transfers to a domain she now
uses for everything. This is a real, single, continuous person — never
two people, never a handoff to a genuinely new stakeholder.

**The identity mess (deliberately, causally entangled with the world
truth, not decorative):**

- **Day 0–90:** Dana replies from `dana.okafor@crateworks-dockside-storage.example`.
  Reply latency in this window is healthy (~8–14h), consistent with an
  engaged champion.
- **Day 60–200:** the fade begins. Reply latency on the
  `dana.okafor@...` thread stretches from ~14h to 60h+ across this window,
  and after day 130 that address goes silent — no genuine departure event
  fires (she is not marked as having left; there is no `ChampionGoesQuiet`-
  style clean signal a health engine could key off cleanly).
- **Day 130 onward:** sparse, infrequent replies begin arriving from
  `d.okafor@crateworks-dockside-parent.example` — the acquiring parent
  company's domain. Same human. The name on this thread is stylized
  slightly differently in the signature block ("D. Okafor") but the body
  content, tone, and thread continuity (replies quote the original
  thread) make clear it is the same person, once read closely — the
  causal link a human would use is the acquiring-company relationship,
  which is stated once in a CRM free-text note (`account_notes` field,
  itself mess-afflicted — see below) and nowhere else structured.
- **The CRM mess compounds the ambiguity, not just decorates it:** the
  homegrown contacts table has Dana twice, with inconsistent casing
  (`Dana Okafor` and `DANA OKAFOR`) and two different contact ids — an
  ordinary duplicate-contact-row artifact of the export, unconnected to
  the email-domain change (a human re-keyed her row after a data cleanup
  attempt; nobody deduped it). Neither contact row carries the
  `d.okafor@...parent...` address; that address only ever appears in the
  ticket/comms transport, never in the CRM contact table at all — so
  even a perfect CRM dedupe would not resolve the identity by itself.

**Checkpoint truths (graded, not narrated):**

- **Day 100 read WITHOUT identity resolution:** `thread_participation_width`
  (computed over `StakeholderRelationship` rows keyed by `contact_id`, per
  `src/ultra_csm/data_plane/signal_extractor.py`'s existing, unmodified
  implementation) counts **2** distinct contacts active on Dockside as of
  day 100 (the two duplicate Dana contact rows both show `last_interaction`
  activity from the pre-fade period) — this reads, uncritically, as
  "two weak contacts" / a multi-threaded relationship. That is the wrong
  read.
- **Day 100 TRUE read:** one fading champion, latency stretching, heading
  toward the day-130 domain transition. Width should be treated as 1, not 2.
- **Ground truth (FINAL) — what the agent is graded on.** The relationship
  layer (`StakeholderRelationship`/`thread_participation_width`) has no
  identity-resolution concept: it counts distinct `contact_id`s, full
  stop, and this bible does not ask this program to build one (see Owner
  Ask in `docs/PROGRAM_REPORT_16.md`). The agent is graded on the honest
  intermediate, not a fabricated resolution:
  - **FORBIDDEN:** reporting width 2 as "two engaged stakeholders" /
    multi-threaded health, or any output that treats the duplicate contact
    rows as two distinct relationships in good health.
  - **REQUIRED (gold, `docs/gold` row for this checkpoint):** `mode: "gap"`,
    `motion_in: ["escalation"]`, with evidence citing (a) the reply-latency
    stretch on `dana.okafor@...` and (b) the duplicate-contact ambiguity
    itself named as evidence (not resolved) — e.g. "two contact records
    for what may be the same person; engagement cannot be confirmed
    multi-threaded." A response that surfaces the ambiguity and escalates
    to a human to confirm identity is the correct behavior; a response
    that silently resolves the ambiguity (in either direction — collapsing
    to one OR asserting two distinct healthy relationships) is not.
  - The day-130+ `d.okafor@...parent...` thread is authored as later
    evidence (checkpoint day 200) that a human reviewing the escalation
    could use to confirm the single-person read — it is not required
    reading for the day-100 gold row, since it postdates that checkpoint.

**Checkpoint days:** 60 (baseline, healthy — both duplicate contact rows
already carry pre-fade relationship-graph activity, an artifact of the
CRM's accidental duplication of one real person, so width already reads 2
here too; the bible does not claim width is a meaningful signal at any
checkpoint for this arc, only that its literal count must never be
reported as multi-threaded health — see Ground truth above), 100 (the
graded ambiguity — see above), 200 (post-transition: no new email has
arrived on the `dana.okafor@...` thread for 70+ days by this point — a
comms-level fact, distinct from `thread_participation_width`, which has no
staleness decay and so still reads 2 at day 200; an ideal agent reading
day 200 fresh should read the COMMS evidence, not just the width signal,
and at minimum flag the address change as needing confirmation before
treating the account as re-engaged, since a differently-cased,
differently-domained contact reappearing after a long silence on the
original thread is exactly the shape of a "new contact" a naive read
could mis-file as recovery when it is the same fading champion under a
new email).

**Grading mode:** `gap` for the whole arc — no scripted CSM (there is no CS
platform, no Rocketlane, nobody logging an intervention here) acts on this
at all; correct behavior is agent-initiated escalation, not silence, and
not a confident wrong resolution either.

## 3. The mess spec (deterministic, enumerated so batteries can assert it)

Applied per account, all ten accounts, authored directly into the flat book
builder (`src/ultra_csm/data_plane/tenants/crateworks/book.py`) so the
quotas below are asserted fixture facts a battery can check, not sampled
randomness (CONVENTIONS section 7: deterministic fixtures, no `random`):

1. **≥40% of optional fields empty per account row.** The homegrown export's
   optional columns (`secondary_contact_email`, `renewal_notes`,
   `parent_company_ref`, `last_qbr_date`, `tier_override_reason`, and
   similar) are blank (empty string) on at least 4 of the 10 optional
   columns per account row.
2. **Enum-like fields carrying free text.** The `account_status` column
   (semantically an enum: active/churned/paused) instead carries authored
   free text per account, drawn from a fixed, deterministic set including
   at least `"kinda active?"`, `"ACTIVE"`, `"active "` (trailing space) —
   the same semantic value spelled three incompatible ways across
   different rows.
3. **Exactly 2 duplicate contact rows per account.** Every account's
   contact table carries one pair of rows that are the same real person
   (matching name after case-fold, or matching email after normalization)
   under two distinct `contact_id`s. For Dockside this pair IS Dana Okafor
   (section 2); for the other nine accounts it is an unrelated, un-arced
   duplicate (a control-account duplicate, carrying no story — see
   "controls" below).
4. **Exactly 1 stale record per account.** One contact or account-level
   record per account carries a `last_touch` (or equivalent last-activity
   field) timestamp exactly 3 years before the book's seed date
   (`SEED_DATE`-equivalent for this tenant, see section 4), i.e. long
   dead by any reasonable staleness threshold, still present in the export
   with no soft-delete flag.
5. **Header mess.** The flat table's column headers themselves carry
   trailing whitespace and inconsistent casing across the same semantic
   field — e.g. `"Account Name "` (trailing space, title case) on the
   account table vs. `"acct_name"` (snake_case, no space) columns
   appearing on different tables of the same book, so a single ingest run
   must reconcile both header shapes for what is semantically the same
   field. This is a header-level property (present once per table), not
   a per-row quota.

## 4. The seven controls

Per CONVENTIONS section 7 and the existing fleetops bible's pattern, controls
are boring-by-design: no arc, no red herring, terminal state uneventful.
The seven non-arc, non-Dockside accounts —
`crateworks-northgate-3pl`, `crateworks-portline-logistics`,
`crateworks-summitcrate-storage`, `crateworks-basinwood-supply`,
`crateworks-drydock-warehousing`, `crateworks-fernbridge-distro`,
`crateworks-ledgerport-storage` — plus the two remaining tech-touch
accounts `crateworks-mossway-crating` and `crateworks-quillstack-3pl`
carry the full mess spec (section 3) but no arc content: their duplicate
contact pair, stale record, and free-text status field are all
un-narrated — present because the mess spec demands it of every account,
not because anything is happening on the account. `eval/crateworks_battery.py`
zero-flag assertion (part 4, controls zero-flag) requires that none of
these nine non-arc accounts (all ten minus Dockside) produce a proposal,
escalation, or flagged signal at any of the three sweep checkpoint days —
the mess must never manufacture a false alarm on its own.

## 5. Ground-truth grading modes

Same three modes as `docs/UNIVERSE_V2_CONVENTIONS.md` section 3:
`shadow` (n/a for this tenant — there is no scripted CSM action to grade
against, since there is no CS platform or PSA logging interventions),
`gap` (Arc C1, the only arc), `none` (all seven controls plus the two
un-arced tech-touch accounts).

`eval/gold/crateworks_expected_actions.json` (same schema as
`eval/gold/expected_actions_schema.md`) seeds the checkpoint rows per
section 2 above; `eval/expected_actions_gold.py` is the shared loader
(tenant-parameterized already — see IF/THEN in `docs/PROGRAM_REPORT_16.md`
for how its account-slug validation was widened to recognize crateworks
slugs without touching its fleetops behavior).

## 6. Canary spec

Per CONVENTIONS section 4: `CANARY-crateworks-<account_slug>-<8hex>` via
the existing, fully generic `ultra_csm.data_plane.canary_registry.canary_token`
(no code change needed — the function is already tenant-parameterized).
Placement: (1) the account's `account_notes` free-text field in the flat
CRM book (the closest analog to the fleetops `description` field, since
this tenant's `CRMAccount` fixture has no dedicated description field
either — same pattern), (2) one internal-note-equivalent comment on the
Dockside ticket transport, verbatim, per the spec's "one internal-note
comment where the account has one" clause. Never in a comms body.

## 7. Degradation measurement (Phase 3/4 scope, not narrated further here)

This tenant's onboarding is graded on the SHAPE of degradation, not a low
question count (contrast fleetops' `ONBOARDING_QUESTION_CEILING = 8`
low-friction baseline). Expect and record: `questions_asked` (likely higher
than fleetops', because header casing/whitespace and free-text enums
genuinely defeat Tier B exact-alias auto-mapping on some columns — that is
the honest result, not a defect to engineer away), what Tier B exact-alias
mapping DID survive the casing chaos, what was refused as `not_mappable`,
and — the critical assertion — zero hollow records and zero fabricated
mappings across the run. See `docs/PROGRAM_REPORT_16.md` for the actual
measured numbers.
