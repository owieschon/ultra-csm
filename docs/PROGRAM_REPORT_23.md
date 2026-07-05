# Program Report 23 — Harvest 5: Motion-Path Wiring

Six consecutive Universe v2 reports (10, 12, 14, 16, 17, 18) disclosed the
same gap: `playbooks.json`, `load_playbooks()`, `resolve_tenant_tier()`,
and the three scale-motion CSM action types were correctly built and
battery-validated but had ZERO production call sites. This program
promotes the proven standalone resolver algorithm (independently
duplicated in `eval/tier_policy_battery.py` and `eval/loopway_battery.py`)
into `src/ultra_csm/motion_resolver.py`, threads a new `motion` field
through the real sweep pipeline, adds the tier-forbidden-motion guard,
and wires cohort collapse into the real per-tenant pipeline — across five
phases (Motion M1-M4 + this report), branch `codex/motion-path-wiring`,
worktree-isolated from the shared main checkout per Harvest 1's discovery
that `~/dev/ultra-csm` is shared with concurrent sessions.

## DoD Evidence

| Check | Command | Result |
| --- | --- | --- |
| Zero-drift suite | `LC_ALL=en_US.UTF-8 make eval` | `589 passed, 1 skipped` — identical to the Phase 0 baseline (`/tmp/baseline_eval.txt`), zero changed pre-existing assertions |
| All tenant batteries | `make narrative-battery-csm content-battery-csm canary-battery-csm fieldstone-battery-csm crateworks-battery-csm loopway-battery-csm` | all `hard_ok: true` |
| Tier policy (real pipeline) | `make tier-policy-battery-csm` | `hard_ok: true` — `check_cohort_collapses_to_one_action` now runs a real ActionGate+Postgres sweep + `collapse_cohorts`, not the standalone resolver; result unchanged (`cohort_size: 25`, `cohort_items_found: 1`) |
| Tier gating (new) | `make tier-gating-battery-csm` | `hard_ok: true` — zero forbidden-motion emissions across all 4 tenants (static) + fleetops/loopway (dynamic) + a real fleetops sweep (dynamic, vacuous coverage disclosed below) |
| Perturbation/drift unchanged | `make perturbation-battery-csm drift-battery-csm` | both `hard_ok: true` |
| Lint/hygiene | `make lint hygiene` | `All checks passed!` / exit 0 |
| Clean diff | `git diff --check` | exit 0 |
| Status | `make status` | `STATUS.md is current` |

Also run as belt-and-suspenders: `make content-invariance-csm` →
`PASS: extractor output is byte-identical to the committed snapshot`
(this program never touches content extraction, but it shares the
`make eval`/`make status` surface, so it was checked anyway).

## IF/THEN Branches Taken

- **`tenant_id` ≠ a playbooks.json tenant slug (a real discovery this
  dispatch's design depends on).** `run_time_to_value_sweep`'s `tenant_id` param is the
  data-plane/CRM identity (`"ultra-demo"`, `DEFAULT_TENANT`); no existing
  caller anywhere in `src/` passes a knowledge-tenant slug like
  `"fleetops"` there — confirmed by grep. Naively auto-loading
  `load_playbooks(tenant_id)` would have `FileNotFoundError`'d (silently
  falling back to `motion=None`) for every real caller, defeating the
  wiring entirely. THEN: added a separate, explicit
  `playbook_tenant_slug` param, opt-in only, decoupled from `tenant_id`.
  No existing caller passes it, so `motion` stays `None` everywhere
  unchanged — structural zero-drift, not just empirically observed.
- **Fleetops' own trigger coverage is narrower than its playbooks.json.**
  `playbooks.json` defines 6 `trigger_factor` values; only 2
  (`champion_inactive`, `feature_shallow_depth`) have ANY live detection
  logic anywhere in this codebase (in `eval/tier_policy_battery.py`'s
  own `_account_triggers`, which this program's sweep-side detector
  mirrors verbatim). THEN: reused exactly that detection rather than
  inventing detectors for the other 4 (`health_red`/`health_yellow`/
  `low_seat_penetration`/`milestones_overdue`/`outcome_unknown`) — that
  would be new bible-grounded fixture/content work outside this
  dispatch's ownership map. Disclosed as Owner Ask #1 below, not
  silently worked around.
- **`tick.py`'s tenant-parameterization STOP condition did not fire.**
  Verified `tick.py`'s entire pipeline is hardwired to `DEFAULT_TENANT =
  "ultra-demo"`, and fleetops' own book (`build_synthetic_book()`) tags
  its accounts with that SAME tenant identity — "fleetops" is a
  playbooks/tier config layer on top of the same fixture book `tick.py`
  already drives. loopway/fieldstone/crateworks each have fully separate
  fixture trees and no `tick.py`-equivalent daily driver at all. Since
  Phase 4's own gate (`make tier-policy-battery-csm`) is fleetops-only,
  no new tenant loop was ever needed — the dispatch's own hedge ("if
  tick.py has no tenant-parameterization... surface it") resolved to
  "not applicable here" on inspection, not a blocker.
- **`eval/tier_gating_battery.py`'s 3-case design (not one dynamic sweep
  everywhere).** `fieldstone`/`crateworks` have no `CSCompany`/
  `HealthScore`/`AdoptionSummary` records, so `run_time_to_value_sweep`
  cannot construct a single `CSMWorkItem` for them (fails closed,
  unchanged, confirmed via `_slot_b_inputs_for_account`'s own
  None-check) — a dynamic per-account sweep is structurally impossible
  for 2 of the 4 tenants. THEN: composed a STATIC config-consistency
  check (`no_play_targets_a_forbidden_tier`, needs only
  `load_playbooks`, covers all 4 tenants and is actually a STRONGER
  property — it holds for every possible account a tenant could ever
  seed) with the two existing tenants' DYNAMIC per-account checks
  (reused by import, not duplicated) and one real ActionGate+Postgres
  sweep for fleetops.
- **`account_resolution="ambiguous"` reused for cohort work items, not a
  new field.** `CSMWorkItem.account_resolution` (`ResolutionState`) has
  no value shaped like "many known accounts, deliberately batched" —
  only `exactly_one`/`ambiguous`/`none`. Verified (grep) that NOTHING in
  `src/` currently branches on this field's value before choosing to
  reuse `"ambiguous"` (structurally the only fit: `account_id=None` +
  `candidate_account_ids=<many>`) rather than adding a new value to the
  shared `ResolutionState` type in `data_plane/contracts.py`, which is
  outside this dispatch's ownership map.
- **`tier_gating_battery.py`'s real-sweep case (case 3) is vacuous as
  authored, and this is disclosed IN THE ARTIFACT, not just prose.**
  Across fleetops' 180-account book at all 3 checkpoint days, only
  accounts with fired priority evidence ever reach `sweep.work_items`,
  and zero of those are BOTH `tech_touch` AND have a consenting contact
  (the one `tech_touch` account with real evidence lacks one).
  `detail["vacuous_pass"]` states this plainly in the JSON artifact.
  This is a gap in the SCRIPTED FIXTURE DATA, not a code defect, and
  fixture/content modules are outside this dispatch's ownership map —
  flagged as Owner Ask #3, not silently patched around by weakening the
  assertion.
- **Self-caught regression, fixed same dispatch.** Phase 3's lint
  cleanup removed `COHORT_THRESHOLD`'s "unused" import from
  `tier_policy_battery.py`, which broke `tests/test_tier_policy_battery.py`
  (imports it directly from that module — ruff cannot see cross-file
  re-export usage). Caught by `make eval` before this report was
  written (should have been caught immediately after the Phase 3 lint
  fix, by re-running full `make eval` rather than just the battery
  scripts — noted for future dispatches). Fixed with a `# noqa: F401` +
  comment naming the consumer, matching this codebase's existing noqa
  precedent (grepped first, not invented).
- **Report number 23 verified collision-free before use.** Checked no
  `docs/PROGRAM_REPORT_19-23.md` exist on `main`, and that the only
  other open branch (`codex/harvest-retro`, PR #28) reserves 19-23 in
  its own bumped `AGENT_PROFILE.md` without claiming any of them for
  itself (it claims 20).

## Consolidated Owner Ask

1. **Fleetops' playbooks.json defines 6 trigger_factor values; only 2
   have live detection anywhere.** `health_red`/`health_yellow`/
   `low_seat_penetration`/`milestones_overdue`/`outcome_unknown` are
   gradeable (gold rows exist) but nothing ever fires them outside a
   gold-row context. A future dispatch should build bible-grounded
   detectors for these (fixture/content work this dispatch does not own)
   to get full motion coverage rather than the current 2-of-6.
2. **No existing production caller passes `playbook_tenant_slug` yet.**
   The wiring is real, correct, and proven (this report's receipts), but
   `api.py`/`mcp_server.py`/`tick.py`/`week1_protocol.py` all still call
   sweep without it, so `motion` stays `None` in every live path today.
   Recommend a small follow-up wiring `tick.py`'s live daily tick call
   (`run_tick_with_config`, the `run_time_to_value_sweep` call around
   line 218) to pass `playbook_tenant_slug="fleetops"` and invoke
   `collapse_cohorts` after its `for fired in evaluation.fired` loop —
   deliberately NOT done in this dispatch since Phase 4's own gate only
   required proving the mechanism works, not adopting it in the live
   loop, and touching that loop's control flow risked exceeding "minimal
   additive."
3. **`tier_gating_battery.py`'s real-sweep case (case 3) passes
   vacuously today** — fleetops has no account that is simultaneously
   `tech_touch`, has fired evidence, and has a consenting contact. Either
   author a new scripted arc account meeting this combination (bible
   content — an Owner decision, not this dispatch's to make) or treat
   cases 1+2 (static + composed-dynamic) as this program's real coverage
   of the tier-forbidden-motion property and accept case 3 as a
   forward-looking placeholder.
4. **Loopway's own sweep-level wiring was not built.** Case 3's real
   ActionGate+Postgres proof is fleetops-only; loopway has the same
   dynamic per-account trigger derivation (`loopway_battery.py`'s
   `_account_triggers`) but no equivalent real-sweep wiring or proof in
   this dispatch.
5. **A dedicated `ResolutionState` value for "known cohort, not
   ambiguous identity"** would be a small, clean follow-up — touches
   `data_plane/contracts.py`'s shared type, outside this dispatch's
   ownership map, so not done here; `"ambiguous"` reuse is disclosed
   above and carries no known behavioral risk today (zero consumers
   branch on it).
6. **`RejectionLedger`→`tick.py` wiring (Report 13's Owner Ask) remains
   explicitly out of scope**, unchanged, not touched by this dispatch.
7. Carried over from Harvest 1: **branch protection /
   `allow_auto_merge` one-time repo setup is still not configured** —
   this dispatch's PR will be left open per K11 rather than merged
   directly (verified below).

## STOP Conditions

No STOP conditions fired. No pre-existing battery/test assertion's VALUE
changed (verified: `tier_policy_battery.json`/`loopway_battery.json`
diffed byte-identical to pre-refactor after Phase 1; `make eval`'s count
matches the Phase 0 baseline exactly after every phase). The
cohort-collapse threshold was confirmed empirically, not guessed:
`COHORT_THRESHOLD = 10` (unchanged, promoted verbatim from
`eval/tier_policy_battery.py`), and the bible's 25-account tier-mirror-3
cohort clears it with margin, proven both by the standalone resolver
(pre-existing) and the real pipeline (this dispatch, `cohort_items_found:
1`). `tick.py`'s tenant-parameterization question was investigated and
resolved as not-applicable (see IF/THEN above), not a blocker requiring
owner input.

## Skeptical Reviewer Paragraph

A reviewer should weigh three real limits, stated plainly rather than
left implicit behind passing gates. First, this proves the MECHANISM is
wired — a real `CSMWorkItem` now carries a real `motion` resolved via the
same algorithm the battery already proved, the tier-forbidden-motion
guard genuinely narrows `customer_contact_allowed` in the real sweep path
for any account that reaches it, and cohort collapse genuinely runs
through the real pipeline (non-vacuous, 25→1 confirmed) — it does NOT
prove the RIGHT motion is chosen in every case a real deployment would
meet; only that `playbooks.json`'s constraints are now enforced rather
than merely graded, exactly as this dispatch's own report contract
requires stating. Second, of fleetops' 180 accounts, motion resolution
today is live for only the subset whose trigger is `feature_shallow_depth`
or `champion_inactive` — the majority of accounts (those needing
`health_red`/`health_yellow`/etc.) resolve to `motion=None`, which is
correct-by-construction given the ownership map's boundaries but should
not be read as "most accounts now get a motion." Third, and most
important: the tier-forbidden-motion guard's dynamic, real-sweep proof
(`tier_gating_battery.py`'s case 3) is VACUOUS as seeded today — it did
not find a single tech-touch account with both fired evidence and a
consenting contact to exercise against, and says so in its own JSON
artifact (`vacuous_pass`) rather than hiding behind a bare `ok: true`.
The STATIC (all-four-tenant config-consistency) and composed-DYNAMIC
(fleetops/loopway per-account, reused from the pre-existing batteries)
cases are what actually carry this program's proof of the
tier-forbidden-motion property today; case 3 is real, correct,
zero-risk-of-false-negative machinery waiting for fixture data that
would let it demonstrate something, not evidence in itself yet.

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `589 passed, 1 skipped` (Phase 0 baseline: `589 passed, 1 skipped` — identical) |
| `make tier-policy-battery-csm` | `hard_ok: true`, 4/4 cases, `cohort_items_found: 1` (real pipeline) |
| `make tier-gating-battery-csm` | `hard_ok: true`, 3/3 cases; case 3 `accounts_checked: 0` disclosed via `vacuous_pass` |
| `make narrative-battery-csm content-battery-csm canary-battery-csm fieldstone-battery-csm crateworks-battery-csm loopway-battery-csm` | all `hard_ok: true` |
| `make perturbation-battery-csm drift-battery-csm` | both `hard_ok: true` |
| `make content-invariance-csm` | `PASS: extractor output is byte-identical` |
| `make lint` | `All checks passed!` |
| `make hygiene` | exit 0 |
| `git diff --check` | exit 0 |
| `make status` | `STATUS.md is current` |
| `git status --short` (post-DoD-run) | clean |

## Receipts appendix

- Baseline: `/tmp/baseline_eval.txt` — `589 passed, 1 skipped, 1 warning in 117.18s` (captured in-worktree, Phase 0, before any commit on this branch).
- Commits this program: `fd214f4` (Motion M1: promote resolver), `c909e2a` (Motion M2: thread motion field), `4bf8caa` (regenerate `mcp_operator_transcript.json` fallout), `abf3d47` (Motion M3: tier-forbidden-motion guard + `tier_gating_battery.py`), `abe03b8` (Motion M4: cohort collapse wired for real).
- Diff budget: 11 files changed, 808 insertions / 107 deletions (915 total) across all 5 commits — within the dispatch's 14-file / 1,000-line budget.
- Byte-identical artifact diffs (Phase 1, zero-drift proof): `eval/tier_policy_battery.json`, `eval/loopway_battery.json` diffed against pre-refactor copies in `/tmp` — no differences.
- Real-pipeline cohort proof (Phase 4): `eval/tier_policy_battery.json`'s `cohort-collapses-to-one-action` case — `cohort_size: 25`, `cohort_items_found: 1`, `real_pipeline: true`.
- Tier-gating static coverage (Phase 3): `eval/tier_gating_battery.json`'s `no-play-targets-a-forbidden-tier` case — fleetops (10 plays), loopway (7), fieldstone (3), crateworks (3), 0 violations each.
- Vacuous-coverage disclosure (Phase 3): `eval/tier_gating_battery.json`'s `real-sweep-guard-fleetops` case — `accounts_checked: 0`, `accounts_swept_per_day: {90: 180, 130: 180, 140: 180}`, `vacuous_pass` field states the gap plainly.
- 5 sampled tail-account motions (residual glance, non-gold-row fleetops accounts, day 140, direct `_account_tier_and_motion` call): `f16ceec8-... | tier=high_touch | motion=working_session`; `ae0a5970-... | tier=mid_touch | motion=content_route`; `081b380c-... | tier=mid_touch | motion=None`; `162a9085-... | tier=mid_touch | motion=None`; `865e1e03-... | tier=mid_touch | motion=content_route`.
- 5 sampled known tier-mirror gold accounts (day 140, same call): resolved to `personal_email`, `working_session`, `content_route`, `campaign_enroll`, `content_route` — the SAME `feature_shallow_depth` trigger correctly resolving to different tier-appropriate motions, confirming `tier_policy_battery.py`'s own docstring claim ("a real book is a distribution, and the tier changes what the CORRECT action is") now holds through the real production path, not just the standalone resolver.
- Before/after `motion_resolver.py` promotion: before, `eval/tier_policy_battery.py::resolve_motions_for_day(day)` and `eval/loopway_battery.py::resolve_motions_for_day(day)` each independently implemented the identical group/match/collapse loop inline. After, both delegate to `ultra_csm.motion_resolver.resolve_motions(tier_by_account_id, triggers_by_account_id, playbooks, *, cohort_threshold=10, slug_by_account_id=None) -> {"per_account": ..., "cohort_actions": ...}` — one function, three call sites (both batteries, `sweep.py`'s per-account and whole-book cohort-collapse paths).
- Files owned and touched, verified via `git status --short` before every commit: `src/ultra_csm/motion_resolver.py` (new), `src/ultra_csm/agent1/sweep.py`, `src/ultra_csm/agent1/__init__.py`, `src/ultra_csm/governance/csm_actions.py`, `eval/tier_policy_battery.py`, `eval/loopway_battery.py`, `eval/tier_gating_battery.py` (new), `eval/tier_gating_battery.json` (new), `eval/tier_policy_battery.json`, `eval/loopway_battery.json`, `eval/mcp_operator_transcript.json`, `Makefile` — no others. `value_model.py`, `config/value_model_config.json`, any tenant `playbooks.json`, and `tick.py`'s existing tenant-dispatch logic were read but not edited, per the ownership map's MUST NOT TOUCH list.
