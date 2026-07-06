# Program Report 16 — Universe v2 WS-Tenant-Crateworks (Wave 3)

Branch `codex/u2-tenant-crateworks` off synced `main` (tip `da87472`, all of
Wave 0-2 merged: Foundations #18, Safety #19, Week1-Harness #20,
Data-Classes #21, Segmented-Book #22). Crateworks WMS is the HYGIENE
tenant: a homegrown, CSV-export-shaped CRM with no vendor CS platform at
all, authored with deterministic mess (empty fields, casing chaos,
duplicate contacts, free-text enums, stale records) at whole-tenant scale.
The mission is honest degradation, not detection brilliance: map what's
mappable, refuse what isn't, and never let mess become fabricated
confidence. Entirely offline: fixture data and fake transports only, no
credentials, no live-org access, no network calls.

## DoD Evidence

**Degradation-shape numbers, front and center (the dispatch's explicit
ask):** the friction-measurement pass (blanket `not_mappable`, the same
shape as fleetops' `week1_protocol` driver) asked **6** questions against
fleetops' **5**-question baseline — close, not a large gap, because
identity fields (`account_id`/`contact_id`/`opportunity_id`) always
require human confirmation regardless of mess
(`external_book._auto_map_entry` never auto-maps an identity field). The
real degradation signal is in the SHAPE of what auto-mapped: all **7**
auto-mapped fields across the three tables survived at Tier B
(exact-alias, coverage-gated) despite the header casing/whitespace chaos
(`"Account Name "` vs. `acct_id` vs. `AccountId`) — zero fell through to
"other"/heuristic-guess auto-maps. The confirmed-ingest pass (real human
answers to the same questions) typed all 10 accounts / 30 contacts / 10
opportunities with zero hollow records and zero fabricated mappings.
Zero-fabrication sweep: all 10 accounts at 3 checkpoint days (60/100/200,
30 account-day combinations) — every computed signal traces to real
evidence ids, every uncomputable signal (the 9 control accounts, which
have no comms/relationship fixtures at all) correctly returns
`None`/`0.0`, never a fabricated number.

| Phase | Result | Evidence |
| --- | --- | --- |
| 1: Tenant bible | Complete | `docs/TENANT_CRATEWORKS_BIBLE.md`: canon (4-module WMS, solo CSM, no CS platform), 10-account book (1 high/3 mid/6 tech), Arc C1 (fading champion read through the identity mess, `gap` mode), 7 controls, deterministic mess spec. Commit `c6d7b4f`. |
| 2: Fixtures + flat transport | Complete | `src/ultra_csm/data_plane/tenants/crateworks/book.py` (messy flat book, ingested through the existing, unmodified `ingest_relational_book` engine with `mcp_server._apply_contract_intent` applied — the hollow-records guard, reused not reimplemented) and `comms.py` (Arc C1 comms/relationship fixtures + `FakeZendeskClient`, the D4 canary placement). `knowledge/tenants/crateworks/playbooks.json` loads via the already-generic `load_playbooks`. Commit `d6e1a02`. |
| 3: Onboarding run | Complete | `eval/crateworks_onboarding.py`: two-pass driver (friction measurement mirroring `week1_protocol`'s pattern exactly; confirmed ingest reusing the same human-confirmed mapping `book.py`'s data-plane builder uses). Verified: 6 questions, 7/7 Tier B auto-maps, 10/30/10 typed, zero hollow, zero fabricated. Commit `475e0fb`. |
| 4: Batteries + week-1 | Complete | `eval/crateworks_battery.py` (6 cases, `hard_ok: true`); `eval/gold/crateworks_expected_actions.json` (30 rows: 3 Arc C1 `gap` checkpoints + 27 control `none` rows); `eval/expected_actions_gold.py` widened (additive union) to recognize crateworks slugs; `eval/week1_protocol.py` widened with `run_full_protocol_crateworks`; `docs/WEEK1_PROTOCOL.md` crateworks column appended; Makefile targets `crateworks-battery-csm`/`crateworks-onboarding-csm`/`week1-protocol-crateworks-csm` added; hygiene fix (renamed two account slugs + one duplicate-contact name that tripped the repo's residue guard). Commit `2299adc`. |

## IF/THEN Branches Taken

- **Precondition docs partially named wrong** (same pattern as Foundations'
  report): `docs/TENANT_FLEETOPS_BIBLE.md` doesn't exist — the actual
  fleetops bible is `docs/SYNTHETIC_UNIVERSE_BIBLE.md`, used as the
  structural model instead. `docs/LIVE_INTEGRATION_FINDINGS.md` exists but
  documents Program 3's live-corpus D1-D6 hostile-seeding datasets (D2 =
  hostile text, D3 = sparse, D4 = broken joins), not a dedicated
  "tenant-hygiene D2/D3/D4" section in the sense the dispatch described —
  used as the closest equivalent precedent instead of inventing content
  for a section that doesn't exist. `docs/PROGRAM_REPORT_3.md` and
  `docs/FOREIGN_CORPUS_FINDINGS.md` DO exist as named and were read
  directly for the flat `ingest_book`/hostile-data precedent.
- **No `src/ultra_csm/data_plane/tenants/` namespace existed yet** (neither
  fieldstone nor loopway had landed) → this workstream is the first to
  build under CONVENTIONS' prescribed-but-unbuilt namespace; no collision
  risk, additive by construction.
- **The flat book needed a real, confirmed mapping to actually type
  records**, and every attempt to hand-author a `FrozenSourceMapConfig`
  directly (bypassing `propose_source_mapping`) either used the wrong
  field shapes or skipped `mcp_server._apply_contract_intent`'s
  cross-contract demotion (the hollow-records guard) → switched to driving
  every table through the real `propose_external_source_mapping` +
  `_apply_contract_intent` + `freeze_confirmed_source_map` chain, reusing
  the exact machinery the live MCP surface already enforces, rather than a
  second hand-rolled transform that could silently drift from it.
- **Arc C1's day-100 "width 2" claim initially failed** (first
  implementation gave both duplicate `StakeholderRelationship` rows fixed
  future `last_interaction` dates, so `thread_participation_width` read 0
  at day 100, not 2) → caught by direct computation before committing;
  fixed by deriving `last_interaction` from real per-contact activity-day
  history, then re-verified day 60/100/200 all read width=2.0 while
  `reply_latency_trend` correctly reads +3.5h/+16.0h/+7.0h (stretching) at
  the same three days — the bible was corrected to describe precisely what
  the width signal does and does not show (it has no staleness decay; this
  is documented, not routed around) rather than silently asserting a
  property that didn't hold.
- **The full sweep engine cannot run for crateworks at all**
  (`ultra_csm.agent1.sweep._slot_b_inputs_for_account` requires a
  `CSCompany`/`HealthScore`/`AdoptionSummary` triple and fails closed when
  any is missing; crateworks has none, by bible design — no CS platform) →
  Arc C1's checkpoint truths are graded directly against
  `signal_extractor` outputs vs. the gold file instead of through the
  sweep/proposal pipeline, and `week1_protocol`'s crateworks branch loudly
  skips `feedback_persistence`/`economics` (sections that require the
  sweep) with a recorded `skip_reason`, rather than either faking
  sweep-derived numbers or silently reusing fleetops' machinery against a
  data plane it structurally cannot serve. This is treated as a genuine
  finding, not a defect to route around (see Owner Ask #1).
- **`eval/week1_protocol.py` and `eval/expected_actions_gold.py` are not in
  this workstream's ownership map, but the dispatch explicitly required
  `week1-protocol-csm --tenant crateworks` to work and a crateworks gold
  file to validate** → both were widened additively (a new
  `run_full_protocol_crateworks` branch dispatched from `run_full_protocol`
  for the first file; a union of crateworks' known slugs into
  `_KNOWN_ACCOUNT_SLUGS` for the second). fleetops' behavior, tests, and
  measured baseline (5 questions, unchanged report content) were verified
  byte-for-byte unaffected before and after.
- **No existing "canary-battery sweep-list" mechanism was found anywhere
  in the repo** (searched `docs/`, `eval/` for "sweep-list"/"sweep_list" —
  zero hits outside this workstream's own new file) → D4 canary coverage
  for all 10 crateworks accounts is implemented as
  `eval/crateworks_battery.py`'s own `check_canary_presence` case (account
  `account_notes` field + one Dockside-ticket internal note, both verified
  to carry the account's canary token) rather than inventing a new shared
  cross-tenant file outside the ownership map.
- **Hygiene gate failure discovered only at the full-suite gate, not
  earlier**: `make eval` failed `test_active_csm_surface_has_no_source_or_
  wrong_domain_residue` — one of the tenant's original WMS-vertical account
  display names used a real word from a different, non-fictional domain
  this repo must never leak (the repo's wrong-domain residue guard), and
  one authored duplicate-contact first name collided with the repo's
  source-residue guard (a real name this repo must never leak) → renamed
  the two affected account slugs and display names to a different
  warehouse-flavored name (see `docs/TENANT_CRATEWORKS_BIBLE.md` section
  1's current table) and the one contact name to an unrelated one,
  recomputed every downstream deterministic id (gold-file evidence UUIDs,
  battery output) against the new slugs, and re-verified the underlying
  values were unchanged (width=2.0, latency +3.5/+16.0/+7.0h at day
  60/100/200) before re-running the full gate suite green.

## Consolidated Owner Ask

1. **Identity-resolution product gap (Arc C1's core finding).** The
   relationship layer (`StakeholderRelationship`/`thread_participation_width`)
   has no concept of "these two contact records may be the same person" —
   it counts distinct `contact_id`s, full stop. This is by design *not*
   built here (the bible explicitly declines to build an
   identity-resolution engine and instead encodes the honest intermediate
   — escalate with the ambiguity named — as the gold row). If real
   customers exhibit this pattern (an acquired-company domain change, a
   CRM re-key that duplicates a contact), an identity-resolution or
   contact-merge-suggestion capability is a real, un-scoped product need,
   not a bug in this workstream's scope.
2. **The full sweep/proposal pipeline is structurally inapplicable to any
   CRM-only, no-CS-platform tenant** (crateworks today; potentially real
   customers with a similar vendor gap). `_slot_b_inputs_for_account`'s
   fail-closed behavior is correct, but there is currently no lighter-weight
   proposal surface for a tenant whose only signals are CRM+comms-derived
   (`signal_extractor` outputs) — an owner decision is needed on whether a
   reduced-input proposal path is worth building for this vendor-stack
   class, or whether "signal-only, human-escalated" is the permanent
   correct posture for it.
3. **No canary cross-tenant sweep mechanism exists yet.** As tenant count
   grows (fieldstone, loopway still to land), a shared canary-sweep-list
   file that all tenant batteries append a line to (rather than each
   tenant battery re-implementing its own canary-presence check, as this
   workstream did) would reduce duplication — an explicit build decision
   for whoever lands the next tenant wave, not built here (kept within this
   workstream's ownership map).

## STOP Conditions

No stop-the-line violation fired. No frozen contract needed an
unsanctioned widening (`CRMAccount`/`CRMContact`/`CRMOpportunity` were used
exactly as declared; ARR/tier bookkeeping was derived from the existing
`CRMOpportunity.amount_cents` field rather than inventing a `CSCompany` row
for a tenant whose bible says "no CS platform" — a deliberate choice to
avoid misrepresenting the vendor stack, not a workaround for a blocked
path). No battery needed a weakened assertion to pass — the one initial
failure (Arc C1's day-100 width read as 0 instead of 2) was a fixture-
authoring bug, caught and fixed before any commit, never an assertion
loosened to match wrong output. No live credentials or real vendor account
were needed anywhere in this workstream (fixture + fake-transport only,
per CONVENTIONS' live/fixture boundary). Two non-owned files
(`eval/week1_protocol.py`, `eval/expected_actions_gold.py`) required
additive widening to satisfy the dispatch's explicit CLI requirement —
this is disclosed above (IF/THEN) rather than silently done or silently
skipped; fleetops' behavior was verified unchanged before proceeding.

## Skeptical Reviewer Paragraph

A skeptical reviewer should note two things this report does not overstate.
First, the "6 vs. 5 questions" onboarding-friction comparison is a weaker
signal of degradation than the megaprompt's framing might suggest at first
glance — because identity fields never auto-map regardless of source
cleanliness, a genuinely messier source and a clean one can ask nearly the
same number of identity-confirmation questions; the real degradation
evidence here is the auto-mapped-field survival shape (Tier B held despite
casing/whitespace chaos) and the Arc C1 width misread, not the raw
question count, and the report is explicit that the count is reported for
comparison, not gated. Second, and more structurally: this tenant's entire
sweep/proposal-generation pipeline could not be exercised at all (no
CS platform, so `_slot_b_inputs_for_account` returns `None` for every
account) — meaning the battery's "zero fabrication" and "controls
zero-flag" claims are verified against `signal_extractor` outputs and the
conversational-onboarding surface only, never against the full
briefing/proposal artifact a real agent run would produce for this tenant.
That gap is disclosed (Owner Ask #2), but a reader should not conflate
"this tenant's signal layer is honest" with "this tenant's full agent
pipeline has been proven honest end-to-end" — the latter claim cannot be
made here because the pipeline literally does not run for a CRM-only
tenant, which is itself the degradation-mission finding, not a caveat
bolted on afterward.

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make lint` | `All checks passed!` |
| `LC_ALL=en_US.UTF-8 make hygiene` | Exit 0 (0 findings, after the two-account-slug + one-name rename) |
| `LC_ALL=en_US.UTF-8 make eval` | `563 passed, 1 skipped` |
| `LC_ALL=en_US.UTF-8 make crateworks-battery-csm` | `hard_ok: true`, 6/6 cases, `failed_cases: []` |
| `PYTHONPATH=src:. .venv/bin/python -m eval.crateworks_onboarding` | friction: 6 questions, auto_mapped Tier B 7/7; confirmed: typed 10/30/10, `zero_hollow_records: true`, `zero_fabricated_mappings: true` |
| `PYTHONPATH=src:. .venv/bin/python -m eval.week1_protocol --tenant crateworks` | `ok: true`, `onboarding_questions_asked: 6` |
| `PYTHONPATH=src:. .venv/bin/python -m eval.week1_protocol --tenant crateworks --repeatability-check` | `two_runs_identical_modulo_random_uuids_and_timing: true` |
| `PYTHONPATH=src:. .venv/bin/python -m eval.week1_protocol --tenant fleetops` | `ok: true`, `onboarding_questions_asked: 5` (unchanged baseline, regression-verified) |
| `git diff --check` | Exit 0 |
| `git status --short` (post-commit) | Clean |
