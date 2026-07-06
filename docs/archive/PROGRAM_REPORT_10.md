# Program Report 10 — Universe v2 Foundations

Branch `codex/u2-foundations` off synced `main` (tip `22a325e`, Program 8's
Universe Deepening). This program makes every cross-cutting decision for
the Universe v2 deployment-readiness test bed concrete — schemas, canon,
small loaders, a conventions doc — so the later data-class, tenant, and
harness workstreams never stop to ask. No live writes, no credentials, no
network calls.

## DoD Evidence

| Phase | Result | Evidence |
| --- | --- | --- |
| Bible amendments | Complete | `docs/SYNTHETIC_UNIVERSE_BIBLE.md` gains a "Grading mode" subsection in each of the six arcs (pinehill=shadow, pinnacle=gap days 3-109/shadow from 110, quarrystone=gap, aspenridge=gap, meridian=shadow, trailhead=none) plus the red-herring pair and the 27 boring controls (both none); a new "Tenant canon (Universe v2)" section (D1 table + vendor-stack axis + namespacing/live-fixture boundary); a "Canary spec" section; a "Reserved perturbation + drift vocabulary" section. Docs-only: `content_invariance_csm` and `narrative-battery-csm` both re-ran green and unmodified. |
| Playbook schema + loader | Complete | `knowledge/tenants/fleetops/playbooks.json` (schema_version 1, fictional: true, 3 service tiers, 6 plays referencing existing `org_pack.json` gap-play factors). `ultra_csm.knowledge.load_playbooks` (fail-closed: unknown tier/motion, undefined tier reference, missing `fictional` all raise `PlaybookError`) plus `PlaybookSet`/`ServiceTier`/`Play` dataclasses. 8 new tests in `tests/test_knowledge.py`. |
| Tier derivation | Complete | `config/value_model_config.json` gains an additive `tier_rules` array (separate from `rules`, so tier derivation cannot perturb existing threshold resolution); `ultra_csm.value_model.resolve_tenant_tier` reuses the exact same most-specific-wins algorithm as `resolve_thresholds` via a shared `_select_most_specific` helper (refactored, behavior-preserving). Verified against three synthetic-book accounts, one per tier: `pinnacle-supply` ($350K) -> high_touch, `pinehill-transport` ($85K) -> mid_touch, `quarrystone-logistics` ($20K) -> tech_touch — all three cross-checked against `synthetic_book.py`'s real `_COMPANY` ARR-cents figures, not assumed. 6 new tests in `tests/test_value_model.py`, including one that asserts existing threshold resolution (`resolve_thresholds`) is byte-identical before/after a `resolve_tenant_tier` call on the same config. |
| Scale-motion action types | Complete | `ultra_csm.governance.csm_actions` gains `campaign_enroll`, `content_route`, `cohort_action` (autonomy tiers 2/2/3, `human_approve`/`human_approve`/`human_approve_with_dual_control`) — the three playbook motions with no existing CSM action-type match. Test parity in `tests/test_csm_actions.py` (4 new tests) mirroring the pre-existing six's coverage pattern. No lens/sweep/precedence/api/tracer consumer required a change (none exhaustively switch over `CSMActionName`, confirmed by direct grep before adding). |
| Ground-truth action schema | Complete | `eval/gold/expected_actions_schema.md` documents the row shape and validation rules; `eval/gold/fleetops_expected_actions.json` seeds 20 rows (18 minimum across the six arcs' checkpoints + 2 red-herring checkpoints), every `evidence_must_include` id computed by calling the real fixture functions (`pinehill_cases_as_of`, `quarrystone_cases_as_of`, etc.) rather than invented. `eval/expected_actions_gold.py` loads and validates (fail-closed on unknown mode, unresolvable account slug, motion outside the canon vocabulary, or a `mode: "none"` row with a non-empty `motion_in`). 5 new tests in `tests/test_expected_actions_gold.py`. |
| Conventions doc | Complete | `docs/UNIVERSE_V2_CONVENTIONS.md` — genericized, repo-committed copy of tenant canon, playbook/tier schema, motion-to-action-type mapping, grading modes, canary spec, economics budgets, and reserved perturbation/drift vocabulary. No dispatch/meta language; later workstreams read this file, not any external plan. |

## IF/THEN Branches Taken

- The dispatch's own D2 language said "Tiers resolve through the EXISTING
  value-model config rule-resolver ... do not build a second resolver," but
  `resolve_thresholds`'s contract is "select one `ConfigRule`'s
  `Thresholds`" — literally adding tier rules into the same `rules` list
  would make them compete with `high_arr_review_default` for threshold
  selection on ties, silently changing existing accounts' resolved
  thresholds → kept tier derivation in a **separate** `tier_rules` list
  using the identical most-specific-wins algorithm (extracted into a
  shared `_select_most_specific` helper used by both functions), so it is
  the same resolver in the sense that matters (one algorithm, one
  implementation) without the side effect of corrupting frozen threshold
  behavior. Verified with a test that resolves the same account's
  thresholds before and after a tier resolution and asserts byte-identical
  output.
- To make "most predicates wins" produce the correct tier ordering (a
  higher ARR band should outrank a lower one, not just tie and fall to
  declaration order), `high_touch_arr`'s match list repeats the
  `mid_touch_arr` predicate before adding the tighter one
  (`arr_cents >= 2_500_000` AND `arr_cents >= 10_000_000`), so it always
  has strictly more matching predicates than `mid_touch_arr` for any
  account that satisfies both → deliberate, verified against all three
  tier boundaries (`9_999_999`, `10_000_000`, `2_499_999`, `2_500_000`) in
  `test_tenant_tier_thresholds_are_final`.
- D2's playbook example named `personal_email`, `working_session`, `qbr`,
  `escalation`, `campaign_enroll`, `content_route`, `cohort_action` as
  motions "mapping onto the action engine's existing action types," which
  presupposes those names already exist as CSM actions → surveyed
  `src/ultra_csm/governance/csm_actions.py` first and confirmed the actual
  taxonomy is six different names (`recommend_next_best_action`,
  `draft_customer_outreach`, `log_crm_activity`,
  `update_cs_platform_record`, `edit_success_plan`,
  `initiate_customer_call`); mapped `personal_email` ->
  `draft_customer_outreach`, `working_session`/`qbr` ->
  `initiate_customer_call`, `escalation` -> `recommend_next_best_action`,
  and added the three genuinely-missing scale motions as new action types
  (explicitly sanctioned by D2's "if not representable, add at most those
  three" clause), recorded in `docs/UNIVERSE_V2_CONVENTIONS.md` §2's
  mapping table.
- `docs/PROGRAM_REPORT_9.md` is named in the "read first" list but does not
  exist on `main` — the Program 9 commit (`27603de`, "anchor-translated
  live re-seed") lives only on the unmerged `codex/live-reseed` branch →
  proceeded reading everything that does exist on `main` (bible, Program
  8's report, contracts, value model, action taxonomy, narrative battery)
  and did not reference or depend on Program 9's unmerged content; not a
  STOP condition (no live credentials, no battery weakening, no
  out-of-ownership file touched).
- The 27 boring controls and 2 red herrings could each get an
  `expected_actions` gold row identical in shape to the six arcs' rows
  (all `mode: "none"`), but 27 near-identical "no signal, no action" rows
  would be low-value duplication of what `eval/narrative_battery.py`'s
  `check_boring_controls` already asserts exhaustively → seeded the two
  red herrings (to exercise the `mode: "none"` path against real,
  distinct-story accounts) but not the 27 controls; recorded as scope
  deliberately not expanded, not silently dropped, in the Owner Ask below.

## Consolidated Owner Ask

1. **The 27 boring-control accounts have no `expected_actions` gold rows.**
   `eval/narrative_battery.py`'s own `check_boring_controls` already
   asserts zero-flag specificity for all 27; a future workstream that
   wants gold-set parity for a downstream grading harness (rather than the
   narrative battery) would need to add them — 27 near-duplicate rows
   were judged not worth authoring speculatively here.
2. **The three new CSM action types (`campaign_enroll`, `content_route`,
   `cohort_action`) are governance-layer only.** No lens (`lens_risk.py`,
   `lens_expansion.py`), `sweep.py`, `precedence.py`, the API, MCP server,
   or `tick.py` has been wired to ever *emit* one of these three — that is
   real work for whichever tenant/data-class workstream needs a tech-touch
   agent to actually propose a `campaign_enroll` action, not something
   this Foundations program should half-wire.
3. **Per-tenant anchor files for `fieldstone`/`crateworks`/`loopway`** are
   explicitly reserved (D5/`UNIVERSE_V2_CONVENTIONS.md` §1) but not built
   — a future decision, not this program's scope.
4. **`golden_corpus` wiring into `slot_b_context()`** remains the same open
   ask Program 8 recorded; untouched here.

## STOP Conditions

No credentials were read, no live org was touched, no network call was
made anywhere in this program. `signal_extractor.py`,
`book_simulator.SCENARIO_TIMELINE`, `data_simulator._CASE_SCHEDULE`,
`synthetic_book.py`, every `*_comms.py` fixture module, and every existing
`ConfigRule`/`Thresholds` entry in `config/value_model_config.json` were
never touched — verified both by `git diff` review and by the
content-invariance/narrative-battery re-runs being byte-identical/unchanged
in case count. No test, threshold, or battery assertion was weakened to
pass. Only additive files and additive fields were introduced (`tier_rules`
is a new top-level key; the three new `CSMActionName` literals are
additions to an existing `Literal`, not a rename of any of the six).
Sentinel grep (`make hygiene`) clean.

## Skeptical Reviewer Paragraph

A skeptical reviewer should weigh three real limits. First, the tier
derivation is verified against exactly three accounts (one per tier,
cleanly inside each band, no boundary-straddling in the *real* book) plus
four synthetic boundary values in a unit test — it has not been resolved
against all 35 synthetic-book accounts, so a reader should not assume
every account's tier has been hand-checked, only that the resolution
*algorithm* is proven correct at the boundaries that matter. Second, the
motion-to-action-type mapping (personal_email/working_session/qbr/
escalation onto four of the six pre-existing action types) is a Foundations
design decision, not a discovery — `working_session` and `qbr` both
resolve to `initiate_customer_call`, which is defensible (both are
meeting-initiation motions at the strictest release tier) but is a real
choice a later workstream could reasonably want split into two action
types if their release-condition needs ever diverge; this report doesn't
claim that split is impossible, only that it wasn't needed by anything
built so far. Third, the three new CSM action types exist in the
governance layer and pass their own parity tests, but zero production code
path emits them yet (Owner Ask #2) — "the taxonomy is extended" should not
be read as "tech-touch accounts can now get scaled actions," which
requires a lens or sweep change nothing here attempted.

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `491 passed, 1 skipped` (up from Program 8's `474 passed, 1 skipped`) |
| `LC_ALL=en_US.UTF-8 make lint` | `All checks passed!` |
| `LC_ALL=en_US.UTF-8 make hygiene` | Exited 0 |
| `git diff --check` | Exited 0 |
| `LC_ALL=en_US.UTF-8 make content-invariance-csm` | `PASS: extractor output is byte-identical to the committed snapshot.` |
| `LC_ALL=en_US.UTF-8 make narrative-battery-csm` | `hard_ok: true`, 8/8 cases |
| `LC_ALL=en_US.UTF-8 make content-battery-csm` | `hard_ok: true`, 5/5 cases |
| `LC_ALL=en_US.UTF-8 make status` | `STATUS.md is current` |
