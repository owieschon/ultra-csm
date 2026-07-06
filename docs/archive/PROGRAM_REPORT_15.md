# Program Report 15 — Universe v2 WS-Tenant-Fieldstone (Wave 3)

Branch `codex/u2-tenant-fieldstone` off synced `main` (tip `da87472`, all
of Wave 0-2 merged: Foundations, Safety, Data-Classes, Week1-Harness,
Segmented-Book). Fieldstone Service Cloud is the NORMS tenant: field-
service management SaaS for HVAC/plumbing contractors, HubSpot-shaped
CRM, no CS platform at all, and a communication culture where every
FleetOps-tuned absolute threshold is wrong. This program's job was to
prove the agent's grading substrate generalizes past a single tenant's
assumptions, not merely to add a second fixture set.

**Lead finding 1 — F1 healthy, not flagged.** `masonry-home-services`
(Arc F1) carries ~38-42h reply latency and a strict quarterly meeting
cadence all year — both of which FleetOps' own `narrative_battery.py`
(`check_healthy_control`, `latency > 10` already suspicious) would read
as alarming. Against a **baseline-relative** classifier
(`ultra_csm.data_plane.tenants.fieldstone.baselines.classify_delta`,
config-sourced floor `flag_delta_floor=20.0`), the account reads
zero-flag at every checkpoint (day 60/180/300) — verified directly, not
asserted: `eval/fieldstone_battery.py`'s
`check_arc_f1_healthy_despite_absolutes` passes, and the day-180 computed
delta is `-0.5h` (37.5h trailing-21d mean vs. 38.0h prior). The
discriminating proof: `culvert-mechanical` (Arc F2) shows the **identical**
`-0.5h` delta at its own day-80 checkpoint — statistically
indistinguishable from Masonry's healthy state — yet by day 140 that same
account's delta has become `+26.0h` (104.0h vs. 78.0h prior), crossing the
configured floor and correctly flagging. Same signal family, same
absolute-level starting point, opposite correct verdicts, discriminated
purely by trajectory. This is the tenant's whole purpose, proven, not
asserted.

**Lead finding 2 — onboarding question count on a HubSpot-shaped source.**
fieldstone's 2-table HubSpot-shaped book (Account/Contact, associations
not lookup fields) needs **3** conversational-onboarding questions via the
real `ingest_table`/`confirm_book` MCP path, vs. fleetops' Salesforce-
shaped 3-table book's **5**. The Tier-A pluggability test the dispatch
named is proven directly:
`eval/hubspot_simulated_onboarding.py`'s `tier_a_association_capture_proven`
flag is `true` — a new, additive HubSpot associations-schema parser
(`explorer.py`'s `_parse_hubspot_associations_schema`, reading HubSpot's
separate `crm/v4/associations/.../labels` endpoint) captures the
contact→company FK graph into `DiscoveredField.references` the same way
Salesforce's `referenceTo` already does, closing a gap that (as discovered
during this program) exists for Attio too — Attio's own
`_parse_attio_attributes` still does not capture its `record-reference`
attributes' target object, left as-is per this program's ownership scope.

## DoD Evidence

| Item | Result | Evidence |
| --- | --- | --- |
| Precondition check | Pass | `docs/UNIVERSE_V2_CONVENTIONS.md`, `eval/tier_policy_battery.py`, `knowledge/tenants/fleetops/playbooks.json` (10 content_refs wired) all present on branch tip `da87472` before any work began. |
| Phase 1: Tenant bible | Complete | `docs/TENANT_FIELDSTONE_BIBLE.md` (264 lines): 5 product modules, 3-person cast, 12-account book (2 high/4 mid/6 tech per D2), Arc F1 (`none` mode), Arc F2 (`none`→`gap` at day 90), 1 herring, 9 boring controls, No-CS-platform discipline, canary spec. Checkpoint numbers corrected against the actual computed fixture output after an initial draft used estimated (not computed) deltas. |
| Phase 2: Fixtures | Complete | `src/ultra_csm/data_plane/tenants/fieldstone/{book,comms,canary,case_verbatims,baselines}.py` + `knowledge/tenants/fieldstone/{playbooks.json,norms_baselines.json}`. `eval/fieldstone_battery.py`: 6/6 cases, `hard_ok: true`. |
| Phase 2: HARD RULE knob | Complete | `tenants/fieldstone/baselines.py`'s `classify_delta` + `knowledge/tenants/fieldstone/norms_baselines.json` (`flag_delta_floor=20.0`) — a tenant-CONFIG-sourced baseline-relative threshold, tested in isolation (`check_baseline_config_loads`: fail-closed on missing history and unconfigured metrics), never touching `config/value_model_config.json`/`ultra_csm/value_model.py`. |
| Phase 3: HubSpot transport | Complete | Additive `hubspot_crm` `ConnectorSpec`/`ConnectorId`/explorer builder+parsers (zero edits to any existing connector's spec/parser); `tenants/fieldstone/hubspot_transport.py`'s `FakeHubSpotClient`; `eval/hubspot_simulated_onboarding.py` end-to-end (discovery→mapping→confirm→freeze→readiness), `tier_a_association_capture_proven: true`. |
| Phase 3: onboarding question count | Complete | `tenants/fieldstone/onboarding.py`'s `run_fieldstone_onboarding_cost_driver`: 3 questions, 1 Tier-A auto-map (the association-derived reference), 5 Tier-B auto-maps. |
| Phase 4: Batteries + week-1 | Complete | `eval/gold/fieldstone_expected_actions.json` (17 rows, all bible checkpoints). `eval/week1_protocol.py --tenant fieldstone` runs end to end (`ok: true`); `docs/WEEK1_PROTOCOL.md`'s new Fieldstone baseline table. `feedback_persistence`/`economics` honestly `not_applicable` (see IF/THEN). |
| Canaries | Complete | All 12 fieldstone accounts carry their D4 token (`check_fieldstone_canary_integrity`); the one internal-note verbatim on `culvert-mechanical`'s case verified present; `eval/canary_battery.py`'s sweep list extended by exactly one line. |
| `make eval` | Pass | `563 passed, 1 skipped` in `99.54s` (well under the 3-minute runtime-discipline ceiling). |
| `make lint` | Pass | `All checks passed!` |
| `make hygiene` | Pass | Exit 0 (after renaming a fieldstone CSM character that collided with the repo's own residue sentinel — see IF/THEN). |
| `make content-invariance-csm` | Pass | `PASS: extractor output is byte-identical to the committed snapshot` — zero fleetops fixtures touched. |
| `make narrative-battery-csm` / `content-battery-csm` / `canary-battery-csm` / `tier-policy-battery-csm` | Pass, unchanged-green | 8/8, 5/5, 6/6 (was 5/5 — additive fieldstone case), 4/4. |
| `make fieldstone-battery-csm` | Pass | 6/6 cases, `hard_ok: true`. |
| `week1-protocol-csm` (fleetops) | Pass, unchanged | `ok: true`, `onboarding_questions_asked: 5` (identical to Wave 1/2 baseline). |
| `week1-protocol-fieldstone-csm` | Pass | `ok: true`, `onboarding_questions_asked: 3`. |
| `make status` | Pass | `STATUS.md is current`. |

## IF/THEN Branches Taken

- The megaprompt named "8 boring controls" as a rough figure; the 12-
  account book's own D2 tier math (2 high + 4 mid + 6 tech) requires 9
  boring-control accounts once the herring (1 mid) and both arcs (2 high)
  are subtracted from the 4-mid/6-tech remainder → authored 9 boring
  controls, stated the arithmetic explicitly in the bible rather than
  force-fitting 8 accounts into a 12-account book whose tier distribution
  is itself a frozen D2 requirement.
- Fieldstone has no CS platform at all (bible canon), but
  `CustomerDataPlane.cs` is a required (non-Optional) field on the shared,
  frozen `contracts.py` dataclass → built `FieldstoneCSPlatformConnector`
  implementing the full protocol with every method returning the honest
  absence value the protocol's own type signatures already support
  (`None`/`[]`), rather than widening the frozen `CustomerDataPlane`
  contract to make `cs` itself `Optional` — the smaller, more conformant
  change, verified against `value_model.py`'s own `_penetration_rail`/
  `_feature_depth_rail`, which already treat `adoption is None` honestly
  for an unrelated reason (adoption may legitimately be absent for
  fleetops too).
- The dispatch's HARD RULE demanded "risk = delta from tenant baseline"
  be expressible as tenant CONFIG, with a minimal additive resolver knob
  if code was needed → discovered `signal_extractor.reply_latency_trend`
  already computes a delta (trailing-21d mean vs. prior-21d mean), so no
  change to that shared, frozen extractor was needed at all; the actual
  gap was a flag/no-flag decision layer, built as
  `tenants/fieldstone/baselines.py::classify_delta`, reading a NEW
  fieldstone-scoped config file (`norms_baselines.json`) rather than
  widening `knowledge.PlaybookSet`'s schema or touching
  `config/value_model_config.json` — the minimal knob, isolated to this
  tenant's own ownership.
- Building a fully-registered `hubspot_crm` connector (spec + explorer +
  parsers) required editing `connector_catalog.py`/`readiness.py`/
  `explorer.py` — three files outside the strict ownership map → the
  dispatch explicitly sanctions this ("if the EXPLORER's metadata capture
  doesn't handle it, extend it additively — this is sanctioned; the exact
  pluggability test"), so proceeded, scoped to purely additive new
  entries (`HUBSPOT_CRM_SPEC`, a new `ConnectorId` literal member, new
  parser functions) with zero edits to any existing connector's spec,
  parser, or behavior — verified by the full test suite staying green
  before and after.
- That registration tripped a hardcoded `CONNECTOR_SPECS` set-equality
  assertion in `tests/test_connector_readiness.py` (outside ownership) →
  mechanical, expected fix (added the one new entry), the same class of
  fix Program 14's own report recorded for its own additions; re-verified
  the full suite green immediately after.
- Investigating HubSpot's Tier-A gap surfaced that Attio's own
  `_parse_attio_attributes` also does not capture its `record-reference`
  attribute's target object (confirmed by reading
  `attio_simulated_onboarding.py`'s `_attribute()` helper: no
  `target_object` in the describe response's `type` field) → left
  Attio's parser untouched. Fixing that is a real, disclosed gap for a
  future program, not silently bundled into this one (it is not this
  tenant's contract, and "fix every adjacent gap you notice" is scope
  creep this protocol explicitly forbids).
- `week1_protocol.py`'s existing `feedback_persistence`/`economics`
  sections require a `TimeToValueAccelerator`-compatible data plane
  (`build_evidence` returns `None` whenever `company`/`health`/`adoption`
  is `None` — read directly from that class's own source, not assumed) →
  rather than fabricate a CS-platform presence fieldstone's bible
  explicitly says does not exist, these two sections report
  `not_applicable` with a stated reason for this tenant. The three
  sections that ARE honestly computable (onboarding cost, cold-start
  honesty, false-alarm rate) are wired and green. Recorded in the
  Consolidated Owner Ask below as future work, not silently skipped.
- `eval/expected_actions_gold.py`'s account-slug allowlist and 18-row
  coverage floor were hardcoded to fleetops' own book/bible scale → made
  both additively per-tenant (a `dict[str, frozenset[str]]` /
  `dict[str, int]` keyed by tenant), with fleetops' exact original values
  preserved unchanged and fieldstone's floor (17) derived from its own,
  smaller bible's real checkpoint count (2 arcs × their own checkpoints +
  1 herring × 3 + 9 boring controls × 1 spot-day row = 17) — never
  weakened to make a case pass, the floor IS the real row count for a
  book at this scale.
- `eval/canary_battery.py`'s existing checks are hardcoded to fleetops'
  `TENANT`/`observe_sim_state`/`DEFAULT_TENANT` sim machinery, which
  fieldstone's fixtures don't run through → rather than rewrite those
  checks to be tenant-parameterized (a much larger scope than "the
  sweep-list line"), added one new, separate, fieldstone-scoped check
  function (`check_fieldstone_canary_integrity`) and a single new line in
  the `CASES` tuple — literally the sweep-list line the dispatch
  sanctioned, nothing more.
- A fictional CSM cast character's first-draft name collided with the
  repo's own hygiene-scan residue sentinel → renamed (now "Grant
  Bellamy" in the bible and fixtures) before committing; `make hygiene`
  clean afterward.
- The bible's first-draft checkpoint numbers (delta values, absolute
  latency levels) were authored as plausible estimates before the comms
  fixtures existed → after building the fixtures, ran the real
  `reply_latency_trend` computation, found several estimates didn't match
  (trailing-21-day windowing behaves differently than hand-estimation),
  and corrected the bible's prose to the actual computed values rather
  than adjusting fixture data to match invented numbers — the bible now
  states verified facts, not authored-then-hoped-for ones.

## Consolidated Owner Ask

1. **`feedback_persistence`/`economics` are not built for fieldstone.**
   `week1.py`'s `NOT_APPLICABLE_REASON` documents why: fieldstone has no
   CS platform, and the existing DB-seeded governance/sweep path
   (`run_time_to_value_sweep` and everything downstream of
   `TimeToValueAccelerator.build_evidence`) hard-requires one. A future
   program that wants these two sections real for fieldstone needs either
   a CS-platform-independent sweep path, or a decision that fieldstone's
   "TTV" signal is sourced differently (e.g. from
   `signal_extractor`/`baselines.classify_delta` directly, bypassing
   `build_customer_value_model` entirely) — a real design decision, not
   built speculatively here.
2. **Attio's Tier-A association-capture gap is real and undisclosed
   until this program.** `_parse_attio_attributes` does not populate
   `DiscoveredField.references` for `record-reference` attributes, even
   though the sample records DO carry `target_object`. A future program
   touching the Attio explorer path should close this — it is the exact
   same class of gap this program closed for HubSpot, just not this
   program's tenant to fix.
3. **The baseline-delta floor (20.0h) is a single global constant per
   metric, not per-account.** `norms_baselines.json` currently expresses
   one floor for the whole tenant; Arc F1 and Arc F2 both happen to share
   a baseline band (~37-40h) so one floor discriminates both correctly.
   A tenant whose accounts have genuinely different baseline levels
   (rather than different trajectories from a shared level) would need a
   per-account or per-tier floor — not built here since fieldstone's own
   bible didn't require it, but worth naming for `crateworks`/`loopway`.
4. **The HubSpot connector's `recorded_shapes` reference
   `tests/fixtures/connectors/hubspot/*.json` paths that don't exist on
   disk** — confirmed this matches Attio's own precedent
   (`company_records_query.json` also doesn't exist) and that
   `fixture_path` is purely declarative metadata never read at runtime.
   A future program formalizing the connector fixture convention should
   either create these files for all vendors or drop the field.

## STOP Conditions

No credentials were read, no live org was touched, no network call was
made anywhere in this program — every transport is a `FakeHubSpotClient`/
in-process fixture. No test, threshold, or battery assertion was weakened
to pass; every fix to a pre-existing test
(`tests/test_connector_readiness.py`'s `CONNECTOR_SPECS` set,
`tests/test_canary_battery.py`'s case count,
`tests/test_expected_actions_gold.py`'s error-message match) was a
mechanical, expected consequence of this program's own additive changes,
inspected before editing, never a silent loosening. Zero fleetops
fixtures, comms modules, or content were touched —
`content-invariance-csm`'s byte-identical snapshot and the unchanged
fleetops `week1-protocol-csm`/`onboarding_questions_asked: 5` are the
direct proof. `docs/UNIVERSE_V2_CONVENTIONS.md` was read but not edited
(Foundations' file, referenced not owned here). Sentinel grep (`make
hygiene`) clean after the one fictional-name correction. No frozen
contract was widened without disclosure: `CustomerDataPlane`,
`CRMAccount`, and every existing `ConnectorSpec` are byte-identical to
before this program; the three shared files touched for the HubSpot
pluggability test (`connector_catalog.py`, `readiness.py`, `explorer.py`)
received only new, additive entries, verified by running the full
pre-existing connector/readiness/explorer test suite before and after.
Runtime discipline held: full `make eval` at 99.54s, well under the
3-minute ceiling, no sampling needed anywhere.

## Skeptical Reviewer Paragraph

A skeptical reviewer should weigh four real limits. First, the "risk =
delta from baseline" proof rests on exactly one signal family
(`reply_latency_trend_hours`) and one pair of accounts (Masonry/Culvert-
Mechanical) — it demonstrates the mechanism works for the case it was
built for, not that every signal family in this repo (meeting cadence,
ticket frequency, thread width) has been proven baseline-relative for
this tenant; `meeting_cadence_shift` in particular returned
`insufficient_history` at every fieldstone checkpoint tested, meaning the
"quarterly cadence is healthy" claim is asserted by fixture design
(zero cadence-shift signal ever fires) rather than proven by a computed,
non-trivial delta the way the latency claim is. Second, this program's
`feedback_persistence`/`economics` gap (Consolidated Owner Ask #1) means
fieldstone's week-1 protocol is honestly incomplete, not just
differently-scoped from fleetops' — a reader should not treat
`week1-protocol-fieldstone-csm`'s `ok: true` as equivalent evidence to
fleetops' full six-section report. Third, the HubSpot pluggability proof
is a single endpoint, single object-pair test
(`contacts`→`companies`) — it proves the explorer CAN capture an
associations-schema FK, not that every HubSpot association shape (self-
referencing associations, multi-label associations, custom object
associations) is handled; a real HubSpot integration would need more
coverage than this fixture exercises. Fourth, the baseline-delta floor
(20.0h) was chosen to cleanly separate this bible's two specific
scripted trajectories (a flat ~0h delta vs. a growing +26h delta) — it
has not been stress-tested against an account whose delta lands near the
floor, so its robustness as a general threshold (rather than a
demonstration-sized one) is unverified.

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `563 passed, 1 skipped` in `99.54s` |
| `LC_ALL=en_US.UTF-8 make lint` | `All checks passed!` |
| `LC_ALL=en_US.UTF-8 make hygiene` | Exited 0 |
| `LC_ALL=en_US.UTF-8 make content-invariance-csm` | `PASS: extractor output is byte-identical to the committed snapshot.` |
| `LC_ALL=en_US.UTF-8 make narrative-battery-csm` | `hard_ok: true`, 8/8 cases (unchanged) |
| `LC_ALL=en_US.UTF-8 make content-battery-csm` | `hard_ok: true`, 5/5 cases (unchanged) |
| `LC_ALL=en_US.UTF-8 make canary-battery-csm` | `hard_ok: true`, 6/6 cases (was 5/5 — additive fieldstone case) |
| `LC_ALL=en_US.UTF-8 make tier-policy-battery-csm` | `hard_ok: true`, 4/4 cases (unchanged) |
| `LC_ALL=en_US.UTF-8 make quantity-battery-csm` | `hard_ok: true`, 3/3 cases (unchanged) |
| `LC_ALL=en_US.UTF-8 make transcript-battery-csm` | `hard_ok: true`, 4/4 cases (unchanged) |
| `LC_ALL=en_US.UTF-8 make fieldstone-battery-csm` | `hard_ok: true`, 6/6 cases |
| `LC_ALL=en_US.UTF-8 make hubspot-simulated-onboarding-csm` | `tier_a_association_capture_proven: true`, `live_tenant_proven: false` |
| `LC_ALL=en_US.UTF-8 make week1-protocol-csm` (fleetops) | `ok: true`, `onboarding_questions_asked: 5` (unchanged from Wave 1/2 baseline) |
| `LC_ALL=en_US.UTF-8 make week1-protocol-fieldstone-csm` | `ok: true`, `onboarding_questions_asked: 3` |
| `LC_ALL=en_US.UTF-8 make status` | `STATUS.md is current` |
