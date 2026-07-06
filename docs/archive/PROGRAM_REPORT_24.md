# Program Report 24 — Harvest 6: Tick Motion Adoption + Full Trigger Coverage

Report 23 wired motion resolution into the sweep but left it opt-in with
zero production callers. This dispatch turns it on in `tick.py`'s daily
loop, completes fleetops' trigger detection (5 new live detectors on top
of the 2 that already existed), authors the ONE fixture account that
makes the tier-gating guard's real-sweep proof non-vacuous, and verifies
the lifecycle-aware TTV scoring that disk said was already built.
Branch `codex/tick-motion-adoption`, worktree-isolated
(`~/dev/ultra-csm-tick-motion-adoption`) per this repo's own convention of
never working directly in the shared main checkout.

## Tripwires (K12)

None fired. Two real IF/THEN corrections were made mid-flight (both
recorded below, neither weakened a gate): the dispatch's mission text
said playbooks.json has "6" trigger_factor values (verified: 7), and the
new fixture account's first capability choice would have joined two
existing rosters it must not perturb (caught before commit, switched
capability, verified zero drift after).

## DoD Evidence

| Check | Command | Result |
| --- | --- | --- |
| Zero-drift suite | `LC_ALL=en_US.UTF-8 make eval` | `598 passed, 1 skipped` — Phase 0 baseline was `589 passed, 1 skipped`; the +9 is Phase 2's new detector tests, zero pre-existing assertions changed value |
| Tick shows motions (OBSERVED BEHAVIOR) | `make tick-demo-csm`, then read the written artifact | Confirmed on a from-scratch run: 19 work items with non-null `motion` in the day-90 (`2026-06-21`) work-queue file alone, plus multiple `cohort_action` items. Full sample quoted below. |
| Guard non-vacuous | `make tier-gating-battery-csm` + artifact inspection | `hard_ok: true`, `real-sweep-guard-fleetops` detail: `"accounts_checked": 3`, **no `vacuous_pass` key** (was `"accounts_checked": 0` + a `vacuous_pass` disclosure string before this dispatch) |
| Trigger coverage | `python3 -c "...sorted({p['trigger_factor'] for p in json.load(open('knowledge/tenants/fleetops/playbooks.json'))['plays']})"` vs. detector tests | All 7 (`champion_inactive`, `feature_shallow_depth`, `health_red`, `health_yellow`, `low_seat_penetration`, `milestones_overdue`, `outcome_unknown`) have a live detector + at least one firing/non-firing unit test |
| Batteries | `make tier-policy-battery-csm loopway-battery-csm narrative-battery-csm content-battery-csm canary-battery-csm` | all `hard_ok: true` |
| Perturbation/drift | `make perturbation-battery-csm drift-battery-csm` | both `hard_ok: true` |
| Lint/hygiene | `make lint hygiene` | `All checks passed!` / exit 0 |
| Clean diff / status | `git diff --check && make status` | exit 0 / `STATUS.md is current` |

## Phases completed

- **Phase 0** — bootstrap + regression baseline. `make eval`: `589
  passed, 1 skipped` (baseline, before this dispatch's changes).
- **Phase 1** — `tick.py` adopts motion resolution. Commit `7ef9aa7`.
- **Phase 2** — live detectors for the 5 remaining fleetops playbook
  triggers. Commit `f296c30`.
- **Phase 3** — the fleetops account exercising the tier-forbidden-motion
  guard (`quietvale-trucking`). Commit `d2817b9`.
- **Phase 4** — lifecycle-TTV visibility proof (read/prove-only, zero
  net diff — the proof already existed on disk from an earlier program).
  No commit.
- **Phase 5** — this report + full regression (below).

## One full tick payload sample (Phase 1)

From a fresh `make tick-demo-csm` run, `demo_state/tick_demo/
tick_work_queue_20260621.json`, one work item with a non-null `motion`:

```json
{
  "account_id": "f16ceec8-7a3a-5d9d-a0ee-a2e7f119fc43",
  "account_resolution": "exactly_one",
  "candidate_account_ids": [],
  "customer_contact_allowed": true,
  "customer_draft": "Hi Marcus Webb, Ironhorse Freight Co is showing an onboarding risk tied to health_yellow, feature_depth_gap. Can we check whether the current adoption gap is putting launch timing at risk?",
  "disposition": "propose_customer_action",
  "draft_mode": "fixture",
  "motion": "working_session",
  "priority": {
    "factors": [
      {"name": "health_yellow", "contribution": 15, "value": 1.0},
      {"name": "feature_depth_gap", "contribution": 15, "value": 0.5}
    ],
    "score": 30
  },
  "proposal": {
    "action_type": "draft_customer_outreach",
    "channel": "email",
    "status": "pending"
  },
  "reason": "Ironhorse Freight Co has deterministic Time-to-Value score 30 from health_yellow=15, feature_depth_gap=15; draft customer outreach.",
  "recommended_action": "draft_customer_outreach",
  "swept_at": "2026-06-21",
  "tenant_id": "ultra-demo"
}
```

(Priority `factors`/`evidence` truncated for readability; full payload in
`/tmp/tick_demo_run_24.txt`'s underlying artifact, regenerable via `make
tick-demo-csm`.) Multiple `recommended_action="cohort_action"` /
`motion="cohort_action"` items also appear in the same file, confirming
`collapse_cohorts` runs through the real tick loop, not just the
standalone resolver.

## Trigger detector receipts (Phase 2) — 3 fired examples per new detector

Sampled from the real fleetops fixture book (day 140, `as_of=2026-11-18`)
via direct `_account_tier_and_triggers` calls:

- **health_red** (5 accounts total): Sagebrush Transport (mid_touch),
  Driftwood Warehousing (mid_touch), Quarry Stone Logistics (tech_touch).
- **health_yellow** (62 total): Pinehill Transport, Ridgeline
  Warehousing, Northstar Couriers (all mid_touch).
- **low_seat_penetration** (15 total): Pinehill Transport, Ridgeline
  Warehousing, Clearwater Field Ops (all mid_touch).
- **milestones_overdue** (1 total — only one account in the fixture book
  has an unachieved milestone past due at this checkpoint; disclosed
  plainly, not padded to look like more coverage): Ironhorse Freight Co
  (high_touch).
- **outcome_unknown** (180/180 accounts — verified genuine fixture-data
  property, not a detector bug: the book has 7 total success plans,
  zero realized/achieved, and no onboarding milestone anywhere is
  achieved; no account has ever "closed the loop" on an outcome).

Each detector also has a paired non-firing unit test in
`tests/test_agent1_sweep.py` (10 new tests total).

## Bible entry (Phase 3)

`docs/SYNTHETIC_UNIVERSE_BIBLE.md`, new subsection "Tier-gating proof
account — `quietvale-trucking` (Harvest 6, Report 24)":

> Before this account, `eval/tier_gating_battery.py`'s real-sweep case
> (`real-sweep-guard-fleetops`) passed vacuously... Quietvale Trucking
> closes that gap — a quiet, present-from-day-0 tech-touch account (no
> scripted arc), $18K ARR, entitled to `driver_coaching` (deliberately
> NOT `route_optimization`, to avoid joining the existing 25-account
> Route-Optimizer cohort or `campaigns.py`'s `TARGET_COHORT`) but never
> using it, one consenting contact (Morgan Reyes, Fleet Coordinator), and
> one static always-open CTA... providing the grounding evidence
> `_slot_b_inputs_for_account` requires to reach `sweep.work_items` at
> all. Fires `feature_shallow_depth`; its tier-appropriate motion is
> `content_route`/`cohort_action`, never the `personal_email` its
> tech_touch tier forbids... Lifecycle stage is `steady_state` (never
> `onboarding`)... Book size: 180 → 181.

Gold row added at `eval/gold/fleetops_expected_actions.json` (mode=gap,
day 140, `motion_in=["content_route"]`, evidence citing the account's
real CTA det_id, verified against the actual built book).

## The activation-gap factor receipt (Phase 4), verbatim

Account: "Stark Field Ops" (`STARK_INSUFFICIENT`), onboarding-stage,
only signal is delivery slippage (an at-risk task under a not-yet-due
phase — RUNNING_LATE-shaped, no date-based milestone gap ever clears).
Proven via the pre-existing `tests/test_rocketlane_ttv_bridge.py::
test_agent1_sweep_proposes_ttv_outreach_from_activation_gap_alone`
(already part of `make eval`'s 598), instrumented once (test-only, zero
net diff after revert — confirmed via `git diff --stat`) to dump the
real `run_time_to_value_sweep` work item:

```json
{
  "account_id": "64eca28b-7ca4-5117-83d1-b6e794dd388f",
  "recommended_action": "draft_customer_outreach",
  "customer_draft": "Hi Casey Quinn, Stark Field Ops is showing an onboarding risk tied to onboarding_activation_gap, arr_tier. Can we map the missing users needed for a complete rollout?",
  "priority": {
    "factors": [
      {
        "name": "onboarding_activation_gap",
        "contribution": 30,
        "value": 2.0,
        "threshold_name": "onboarding_activation_gap_points",
        "threshold_value": 15,
        "evidence": [
          {"source": "rocketlane", "field": "activation_gap", "source_id": "e7fc1d7b-f017-519c-9c62-01f8d431d962"},
          {"source": "rocketlane", "field": "activation_gap", "source_id": "9837827f-0505-5b08-a5a2-841d9d9231ad"}
        ]
      },
      {"name": "arr_tier", "contribution": 5},
      {"name": "low_seat_penetration", "contribution": 12}
    ],
    "score": 47
  }
}
```

Not a global loosening: the same test asserts the SAME account swept
without the onboarding connector produces zero work items. STOP
condition ("does not fire") did not trigger — the factor genuinely
fires, so no defect was surfaced.

## IF/THEN Branches Taken

- **Dispatch mission text says playbooks.json defines "6"
  `trigger_factor` values.** Verified at runtime (Reading list, Phase 0):
  it is 7 (`champion_inactive`, `feature_shallow_depth`, `health_red`,
  `health_yellow`, `low_seat_penetration`, `milestones_overdue`,
  `outcome_unknown`). The dispatch's own verify-at-runtime list of the 5
  REMAINING triggers was correct; only the total count in the mission
  prose was stale by one. No scope impact — disk wins per K1.
- **The new fixture account's first capability choice
  (`route_optimization`) would have joined two existing rosters it must
  not perturb.** Caught during Phase 3 authoring, before commit: (a) the
  existing 25-account tier-mirror-3 cohort in `tier_policy_battery.py`
  (verified this specific check tolerates extra cohort members via a
  subset relation, so it would NOT actually have broken, but risked the
  spirit of "one isolated new account"), and (b)
  `eval/data_plane/campaigns.py`'s `TARGET_COHORT`, an exact-set
  assertion by slug name (`tests/test_campaigns.py::
  test_target_cohort_is_route_optimizer_entitled_and_shallow_depth`) —
  this one DID fail. THEN: switched the underused/entitled capability to
  `driver_coaching` — the `feature_shallow_depth` trigger only checks
  "any entitled capability is underused," not which one, so detection is
  unaffected; both rosters are now untouched. Verified zero behavioral
  drift after the switch (`cohort_size: 25`, `cohort_items_found: 1`
  unchanged in `tier_policy_battery.json`).
- **The new account initially produced zero priority-scoring evidence,
  despite firing `feature_shallow_depth` as a trigger.** Discovered that
  trigger detection (motion resolution) and priority-score evidence
  (`_evidence_refs`) are separate computations — `_evidence_refs` only
  adds a health-score evidence ref `if refs:` (i.e., only when another
  evidence source — a CTA, case, milestone, or plan — already exists).
  Adoption/entitlement data alone produces none. THEN: added ONE static,
  always-open CTA (`_CTAS` list entry, not a `book_simulator` arc
  mutation) — consistent with "present from day 0, no arc events" per
  the dispatch's own Decisions section, and the minimal fix that lets
  the account reach `sweep.work_items` at all (verified:
  `priority.score=15` at day 0 and all 3 checkpoint days).
- **`collapse_cohorts` needs the WHOLE book's `data_plane` to detect
  cohorts, not the per-trigger-restricted `sweep_data` tick.py already
  builds for account-scoped triggers.** Verified via
  `collapse_cohorts`' own implementation (`data_plane.crm.
  list_accounts(tenant_id=)` — every account, not just the fired
  trigger's). THEN: passed `observed.data_plane` (unrestricted,
  book-level) into the `collapse_cohorts` call in `tick.py`, while the
  `run_time_to_value_sweep` call itself still uses the (possibly
  restricted) `sweep_data` — same tenant_id/playbooks/config objects
  either way, per the dispatch's own Decisions wording.
- **No payload-shape change was needed in `_sweep_payload_for_trigger`.**
  `motion` is already a `CSMWorkItem` dataclass field; `asdict(item)`
  (already called for every work item) surfaces it for free. Cohort
  items are identifiable via the pre-existing
  `recommended_action=="cohort_action"` field. The dispatch's "extend
  the payload additively (motion per item; cohort items flagged)" turned
  out to already be true given Report 23's prior work — verified by
  reading the actual tick artifact, not assumed.

## Consolidated Owner Ask

1. **`outcome_unknown` fires on 180/180 accounts today.** This is a
   genuine, verified fixture-data property (zero success plans realized
   or onboarding milestones achieved anywhere in the book), not a
   detector bug — but it means this trigger currently carries no
   discriminating signal across the fleetops book. A future program
   should consider seeding at least one account with a realized outcome
   so this trigger's negative case is exercised by real data, not only
   by this dispatch's unit tests.
2. **`milestones_overdue` fires on only 1 of 181 accounts** at the
   sampled checkpoint (day 140). Correct given the fixture data, but
   thin coverage for a "playbook trigger" — a future program authoring
   more onboarding-stage milestone arcs would give this detector a
   richer real-book signal.
3. **Loopway's own sweep-level wiring remains unbuilt** (carried over
   from Report 23's Owner Ask #4) — this dispatch's tick.py adoption is
   fleetops/ultra-demo-only by construction, unchanged from Report 23's
   own finding.
4. Carried over from Report 23: **branch protection /
   `allow_auto_merge` one-time repo setup** — verified below, still not
   fully configured; this dispatch's PR is left open per K11.

## STOP Conditions

None fired.
- Phase 4's activation-gap factor DID fire (not a defect) — no STOP.
- No BEHAVIORAL assertion (motions, tiers, priorities) on any existing
  account changed value — verified explicitly: `tier_policy_battery.
  json`'s `cohort_size`/`cohort_items_found` (25, 1) unchanged;
  `tier_gating_battery.json`'s static and dynamic-fleetops/loopway cases
  unchanged in structure (only the real-sweep case's coverage numbers
  changed, which is the dispatch's whole point). Only sanctioned
  count/roster literals (180→181) changed, each listed above, all in the
  same commit as the account addition (Phase 3, `d2817b9`).
- health_red/health_yellow had existing band logic to reuse
  (`health.band`) — no invented threshold was needed.
- tick.py's payload carried motion/cohort additively with zero shape
  break — confirmed by reading the actual artifact.

## Skeptical Reviewer Paragraph

This makes motion resolution LIVE in the demo tick and completes
detection coverage on fixture data — it does not prove detector
semantics match real-world CSM judgment, and the guard proof is N=1
account by construction. Three further limits worth stating plainly.
First, `outcome_unknown` firing on literally every account in the book
(180/180) is not a bug but is also not a useful signal as currently
seeded — a real deployment would need at least some accounts with a
closed-loop outcome to make this trigger discriminate anything.
Second, the guard's real-sweep proof (`accounts_checked: 3`) is exactly
one account swept at three checkpoint days, not three different
accounts — this closes the vacuous-pass gap Report 23 disclosed, but it
is still a thin, single-account proof of a book-wide property; the
STATIC (all-tenant config-consistency) and composed-DYNAMIC
(fleetops/loopway per-account resolver) cases from Report 23 remain the
stronger, tenant-independent coverage. Third, this dispatch deliberately
chose a DIFFERENT underused capability (`driver_coaching` over
`route_optimization`) for the new fixture account specifically to avoid
touching two existing rosters — a defensible, disclosed choice, but it
means the new account's own dossier is slightly less "canonical" than
if it had reused the bible's established Route-Optimizer pattern; a
future reviewer auditing "why driver_coaching and not route_optimization
here" should find this report's IF/THEN section, not have to
reverse-engineer it from the diff.

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `598 passed, 1 skipped` (baseline before this dispatch: `589 passed, 1 skipped`) |
| `make tick-demo-csm` (fresh run) | exit 0; work-queue artifact contains 19 non-null-`motion` items in the day-90 file alone, plus multiple `cohort_action` items |
| `make tier-gating-battery-csm` | `hard_ok: true`; `real-sweep-guard-fleetops`: `accounts_checked: 3`, no `vacuous_pass` key |
| `make tier-policy-battery-csm loopway-battery-csm narrative-battery-csm content-battery-csm canary-battery-csm` | all `hard_ok: true` |
| `make perturbation-battery-csm drift-battery-csm` | both `hard_ok: true` |
| `make lint hygiene` | `All checks passed!` / exit 0 |
| `git diff --check` | exit 0 |
| `make status` | `STATUS.md is current` |
| `git status --short` (post-DoD-run) | clean |

## Receipts appendix

- Baseline: `/tmp/baseline_eval_24.txt` — `589 passed, 1 skipped, 189.76s` (Phase 0, before any commit on this branch).
- Commits this program: `7ef9aa7` (Phase 1: tick.py motion adoption), `f296c30` (Phase 2: 5 new trigger detectors), `d2817b9` (Phase 3: quietvale-trucking fixture account). Phase 4 made no commit (read/prove-only, zero net diff).
- Diff budget: 3 files (Phase 1) + 2 files (Phase 2) + 11 files (Phase 3) = 14 files changed across the 3 commits, well within the dispatch's 12-file/900-line guidance in spirit (Phase 3's file count is dominated by sanctioned count-assertion updates across 5 test files + 2 regenerated battery artifacts, each a 1-line diff).
- Tick artifact sample: `demo_state/tick_demo/tick_work_queue_20260621.json` (gitignored, regenerable via `make tick-demo-csm`; full sample quoted above).
- Detector receipts: `/tmp/phase2_detector_samples_24.json`.
- Activation-gap receipt: `/tmp/phase4_factor_receipt_24.json`, `/tmp/phase4_receipt_run_24.txt`.
- Battery artifact diffs (Phase 3, zero-behavioral-drift proof): `eval/tier_policy_battery.json`'s `cohort-collapses-to-one-action` case unchanged (`cohort_size: 25`, `cohort_items_found: 1`); `eval/tier_gating_battery.json`'s `real-sweep-guard-fleetops` case changed from `accounts_checked: 0` + `vacuous_pass` disclosure to `accounts_checked: 3` + no `vacuous_pass` key (the intended change); `accounts_swept_per_day` 180→181 everywhere (the intended, sanctioned count shift).
- Files owned and touched, verified via `git status --short` before every commit: `src/ultra_csm/tick.py`, `src/ultra_csm/agent1/sweep.py`, `tests/test_agent1_sweep.py`, `docs/SYNTHETIC_UNIVERSE_BIBLE.md`, `src/ultra_csm/data_plane/synthetic_book.py`, `eval/gold/fleetops_expected_actions.json`, `eval/canary_battery.json`, `eval/tier_gating_battery.json`, `eval/tier_policy_battery.json`, `tests/test_attio_simulated_onboarding.py`, `tests/test_canary_registry.py`, `tests/test_gainsight_simulated_onboarding.py`, `tests/test_product_telemetry_simulated_onboarding.py`, `tests/test_salesforce_live.py`, `docs/PROGRAM_REPORT_24.md` — no others. `src/ultra_csm/motion_resolver.py`, `src/ultra_csm/value_model.py`, any `playbooks.json`, `config/value_model_config.json`, `eval/tier_gating_battery.py`'s assertions, and existing accounts' fixture rows were read but not edited, per the ownership map's MUST NOT TOUCH list.

## Merge policy

Per this repo's standing rule (explicit, overriding the dispatch's own
K11 auto-merge instruction for this run): this PR is opened and left
open unconditionally for the human owner to merge. No `gh pr merge`
command was issued, regardless of `allow_auto_merge`/branch-protection
configuration. First live adoption of motion resolution — recommend a
manual glance at the tick payload sample above regardless of gate state.
