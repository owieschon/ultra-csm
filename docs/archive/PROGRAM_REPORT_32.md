# Program Report 32 — Harvest 16: Wire the dormant person layer into the live sweep

Branch `codex/person-signal-wiring` off synced `main` (e936a74). The
system already modeled people -- `StakeholderRelationship`, `JobChangeSignal`,
per-contact `CommunicationSignal`, and a `value_model_bridge` with real
per-user seat/concentration data -- but none of it drove the live agent.
This wires the dormant person layer into the live account-level sweep as
additive, deterministic account factors with person-cited evidence, and
replaces naive first-consenting recipient selection with role-graph-driven
resolution. This WIRES the dormant layer into the existing account-level
priority/evidence path; it does not introduce person-level scoring or
queueing (the account stays the unit of action), and the four factors'
thresholds (window days, points) are authored defaults, not validated
against real CSM judgment. Front-end surfacing of this data is Harvest 15
(report 27), out of scope here.

## Tripwires

Ledger count: 5/8 (threshold 8, no STOP). All five are disk-vs-dispatch
corrections or a diff-budget note, not behavior risks:

1. Dispatch guessed `role_type`; disk field is `relationship_type`
   (`contracts.py:261`).
2. Dispatch implied the synthetic book already carries person data; it did
   not (`FixtureCustomerData` had no stakeholder/job-change fields at all)
   -- the largest real correction, changing the shape of Phase 1's work
   from "add a fetch" to "extend the shared fixture book, then fetch."
3. Dispatch said "config rule-list entries for new factors"; the config's
   `rules` are threshold *profiles* (`Thresholds` is a strict-kwargs frozen
   dataclass), so the additive form is new `Thresholds` fields + matching
   JSON keys in both existing rules, not new rule entries.
4. `JobChangeSignal`'s type field is `change_type`, not a generic field
   name.
5. Diff budget: real diff vs the branch point (`git diff e936a74 --stat`,
   not the moved `main` HEAD -- another PR merged during this session) is
   **17 files / 1,265 insertions(+), 11 deletions(-)** -- one file over the
   16-file budget, well under the 1,600-line budget. Two of the 17 are
   generated artifacts (this program's own battery JSON receipt, and a
   pre-existing test's determinism-check regeneration of
   `mcp_operator_transcript.json` picking up the new additive
   `recipient_resolution` field). Recorded, not absorbed silently.

## SIGNAL -> SOURCE -> SINK map (verified against disk, not the dispatch's guesses)

| Factor | Source | Sink | Firing case |
| --- | --- | --- | --- |
| `champion_departed` | `JobChangeSignal.change_type=="departure"` (`relationship_signals.py`) for a contact with `StakeholderRelationship.relationship_type=="champion"` (`contracts.py:253`), within `champion_departed_window_days` | `person_factors.champion_departed` -> `value_model._champion_departed_factor` -> `build_customer_value_model`'s divergence list | pinnacle-supply: Derek Vaughn is champion (`pinnacle_comms.py:167`) with a day-5 departure signal (`relationship_signals.py:61`) -- both records pre-existed; no new fixture needed |
| `single_threaded_risk` (real graph) | Engaged-contact count from `StakeholderRelationship.last_interaction` recency (`person_factors.engaged_contact_count`), replacing the account-level person-grain-`UsageSignal` proxy INPUT | `value_model._single_threaded_risk`, graph-when-available / proxy-fallback | quarrystone-logistics: a single frozen champion row that never gains a second (`quarrystone_comms.py:171`) |
| `new_stakeholder_unengaged` | `StakeholderRelationship` of role admin/executive_sponsor added within `new_stakeholder_window_days` with no matching `CommunicationSignal` | `person_factors.new_stakeholder_unengaged` -> `value_model._new_stakeholder_unengaged_factor` | **No fixture anywhere had an admin/executive_sponsor row** -- new bible arc authored on oakmont-logistics (see Sanctioned Exception below) |
| `usage_concentration` | Top-user share of person-grain `UsageSignal` >= `concentration_ceiling`, via the promoted `person_factors.top_user_share` helper | `value_model._usage_concentration_factor`; same helper now also used by `value_model_bridge.py`'s single-threaded-risk block (one computation, not two) | pinnacle-supply's existing person-grain usage signal (`synthetic_book.py:1519`) |
| Recipient resolution | `StakeholderRelationship.relationship_type` + per-person `CRMContact.consent_to_contact` | `recipient_resolver.resolve_recipient(motion, stakeholders, contacts)`, replacing `agent1/sweep.py`'s first-consenting pick in `_work_item_for_account` | pinnacle-supply: a `working_session` motion resolves to Derek (champion) even when listed second in the contacts tuple -- proves the graph overrides position-based fallback |

## The data-plane gap (the actual size of Phase 1)

`FixtureCustomerData` (`data_plane/fixtures.py:62`) carried no
`stakeholder_relationships`/`job_change_signals` fields, and
`build_synthetic_book()`/`simulate_book()` never assembled the existing
per-tenant `*_stakeholder_relationships(as_of_day)` readers or
`relationship_signals.SIGNALS` into the book the sweep runs against --
that is the actual mechanism of the dormancy this dispatch closes. Fixed
additively: two new defaulted-empty fields on `FixtureCustomerData` (every
pre-existing construction site unaffected); `build_synthetic_book()`
populates them at day 0 via a function-local import (the per-tenant comms
modules reach `data_simulator -> synthetic_book` at module scope, so a
module-level import here would cycle); `simulate_book(base, day_offset)`
recomputes them at the target day (the readers are themselves
`as_of_day`-parameterized -- day-relative state, same category as the
existing contacts/cases recompute, not something to accumulate).
`FixtureCRMDataConnector` gains `list_stakeholders`/`list_job_changes`
(NOT part of the `CRMDataConnector` Protocol -- structural typing means
`SimCRMDataConnector`/`FieldstoneCRMDataConnector`, which don't implement
them, are unaffected; the sweep's `_person_layer_inputs` reaches them via
`getattr(..., None)` and degrades to an empty tuple for any connector that
lacks them).

**Shared-fixture surface touched (flagging prominently per instruction):**
this is the one part of this program that touches shared fixture-assembly
code other in-flight worktrees branch from (`FixtureCustomerData`,
`build_synthetic_book()`, `simulate_book()`). The change is strictly
additive -- two new fields, both defaulted to `()`, zero existing field
renamed or reordered, zero existing fixture row's value changed. Verified:
`make eval` is 645/1 (identical to the pre-change baseline) immediately
after this extension lands, before any factor logic is added.

## Zero-drift proof

- Baseline (`e936a74`, before any change): `make eval` = **645 passed, 1
  skipped** (`/tmp/baseline_eval_32.txt`).
- After the fixture-book extension alone: 645/1, identical.
- After the four factors + sweep wiring: 645/1, identical (one iteration
  required a mechanical fix -- `tests/test_value_model.py`'s `_thresholds()`
  helper constructs `Thresholds` directly and needed the six new required
  fields added with the same values as the config JSON; this is
  construction-site plumbing, not an assertion change).
- After recipient resolution: **658 passed** (645 + 13 new
  `tests/test_recipient_resolver.py` tests), 1 skipped, zero pre-existing
  assertion changed.
- Final (`docs/PROGRAM_REPORT_32.md` cut): `make eval` = 658 passed, 1
  skipped, 131s.
- `single_threaded_risk`'s specific zero-drift claim, the one the dispatch
  flagged as a STOP-condition risk: `tests/test_value_model.py::
  test_single_threaded_risk_requires_person_grain_usage` asserts
  `factor.evidence[0].source_id == "person-signal-1"` (a `UsageSignal` id).
  This test passes no `stakeholders` (every pre-existing caller's
  behavior), so it takes the untouched proxy branch and reproduces this
  exact evidence -- confirmed passing, unchanged, both before and after
  the swap. `eval/person_factor_battery.py`'s
  `check_proxy_fallback_zero_drift` case re-proves this independently
  against the public `build_customer_value_model` API (belt-and-suspenders
  on top of the unit test).
- `tier-policy-battery-csm` / `tier-gating-battery-csm` /
  `narrative-battery-csm`: all `hard_ok: true`, unchanged (narrative
  battery's `check_boring_controls` in particular confirms oakmont's new
  stakeholder row didn't perturb the boring-control invariant it only
  checks for case-content contamination).
- `make hygiene`: exit 0 (one initial catch -- a meta-residue phrase this
  report's own instructions flag as a tell tripped the scanner in a
  bible-doc sentence; reworded, re-ran clean).
- `make lint status`: clean; `git diff --check`: exit 0.

## Person factors' fired evidence (person-cited, sampled)

```
champion_departed   (pinnacle-supply, day 10): value=5.0
  evidence: crm/<job-change-signal-id>  field=change_type       observed_at=2026-06-25T23:00:00Z
  evidence: crm/<contact-id>            field=relationship_type observed_at=2026-06-22T04:00:00Z

single_threaded_risk (quarrystone-logistics, day 30, real-graph branch): value=1.0
  threshold_name=min_threaded_persons (NOT concentration_ceiling -- confirms the
  real-graph branch fired, not a silent fallback to the telemetry proxy)
  evidence: crm/<contact-id> field=last_interaction observed_at=2026-06-21T07:00:00Z

new_stakeholder_unengaged (oakmont-logistics, day 90): value=1.0
  evidence: crm/<contact-id> field=relationship_type (Priya Subramaniam, admin,
  appeared day 70, no CommunicationSignal ever)
  Boundary verified: fires day 70-100 inclusive, silent day 69 and day 101+.

usage_concentration (pinnacle-supply, day 10): value=1.0
  evidence: telemetry/<signal-id> field=person_active_days observed_at=2026-06-21T00:00:00Z
```

Full samples: `eval/person_factor_battery.json` (checked in).

## Recipient resolution: mapping + one resolved example

Per dispatch Decisions (ratified, restated here only for the report's own
completeness, not re-litigated): `working_session`/`qbr` -> champion or
executive_sponsor; `escalation` -> executive_sponsor; `personal_email` ->
champion else primary (the fallback); `content_route` -> `end_user` role.
`campaign_enroll`/`cohort_action` are not named in the dispatch's mapping
and fall through to the fallback (an IF/THEN, not an invention).
Per-person consent reuses `CRMContact.consent_to_contact` unchanged. No
eligible consenting person for the resolved role falls back to the
original first-consenting behavior -- verified by construction
(`recipient_resolver._first_consenting_fallback` is the pre-Harvest-16
logic, called verbatim) and by 13 new unit tests
(`pytest -k recipient` -> 14 passed).

**Resolved example:** pinnacle-supply, motion `working_session`, contacts
`(Other, Derek)` in that order. Pre-Harvest-16 first-consenting would
return `Other` (first in the tuple). `resolve_recipient` returns `Derek`
(the `champion`-role stakeholder), resolution=`"role_graph"` -- proving
the role graph actively overrides position, not just passively agreeing
with it. `CSMWorkItem` gains an additive `recipient_resolution` field
(`"role_graph"` or `"first_consenting_fallback"`) recording which path
fired per the dispatch's "record it" instruction.

The no-auto-pick identity gate (`_escalation_item`, ambiguous-identity
path) is untouched -- it has no single recipient to resolve and was never
in this program's scope.

## Person-data safety note

Hygiene/canary discipline extended to the new fixture (oakmont-logistics'
new contact, Priya Subramaniam, is fictional tenant data in the same
`*.example` domain convention as every other fixture person). `make
hygiene` exit 0. The identity gate remains untouched and unweakened:
person data does not change how it resolves ambiguous identity, and it
was never in this program's scope (an earlier bible-doc draft stated this
using a meta-residue phrase the scanner flags; fixed by stating the
constraint plainly instead).

## Owner Asks

- **`content_route`'s full person-cohort mapping is implemented but not
  fully wired.** The dispatch's ratified mapping says content_route
  routes to "the entitled end_users (may be many -- the person-cohort
  case)." `recipient_resolver.resolve_content_route_recipients` implements
  this (returns all consenting end_user-role contacts), but `CSMWorkItem`
  (`agent1/sweep.py`) has no multi-recipient slot -- it is single-`contact`
  by design, matching the single `ProposalRef`/`_propose_outreach` shape.
  `resolve_recipient` (the function actually wired into the sweep) treats
  `content_route` as single-pick (first consenting `end_user`) for this
  reason. Giving `content_route` its full multi-recipient behavior is a
  `CSMWorkItem`-shape change, out of this dispatch's scope (which replaces
  the existing pick, not the work-item shape) -- flagging for whoever owns
  the next content_route-specific work.
- **Lens forward-compat**, recorded now per the dispatch's instruction so
  the lens-registry dispatch inherits it without re-deriving: RISK lens =
  `champion_departed`, `single_threaded_risk` (real-graph branch),
  `new_stakeholder_unengaged`; ADOPTION lens = `usage_concentration`.
- **Diff-budget file count** (Tripwire 5 above): 17 files vs the dispatch's
  16-file budget. Flagging rather than trimming a file to hit the number --
  the overage is one file, driven by two generated-artifact files
  (the battery's own JSON receipt and a pre-existing test's regenerated
  transcript), not scope creep in hand-authored logic.
- **Branch is behind current `main`.** Another program (Harvest 13, PR
  #46) merged to `main` during this session, landing after this branch's
  base (`e936a74`). `git merge-tree` shows a clean merge except for
  `STATUS.md` (auto-generated by `scripts/render_status.py`, trivially
  regenerable, no hand-authored conflict). Left un-rebased per the merge
  policy's own "leave the PR open with the reason" default and the
  explicit instruction to land this at an opened, not auto-merged, PR for
  a manual look at the fixture-book diff -- rebasing now would re-run
  every eval cycle against a moving target mid-review.

## Receipts appendix (K4)

- Baseline: `/tmp/baseline_eval_32.txt` (645 passed, 1 skipped, in the
  worktree's own isolated `.venv` -- `.venv/bin/python` did not exist in a
  fresh worktree; `make setup` built one so tests import the worktree's
  `src/`, not the shared checkout's editable install).
- `eval/person_factor_battery.json`: `hard_ok: true`, 6 cases (checked in).
- `eval/tier_policy_battery.json`, `eval/tier_gating_battery.json`,
  `eval/narrative_battery.json`: all `hard_ok: true`, unchanged.
- Commits (branch `codex/person-signal-wiring`, off `e936a74`):
  1. `fd619ff` -- Person factors: champion-departed, single-threaded,
     new-stakeholder, concentration (additive); fixture-book extension.
  2. `e95bddb` -- Bible arc: new-stakeholder-unengaged on oakmont-logistics
     (sanctioned fixture exception).
  3. `29452c7` -- eval/person_factor_battery.py +
     person-factor-battery-csm Makefile target.
  4. `5de88db` -- Recipient resolution: role-graph-driven, consent-checked
     (replaces first-consenting).
  5. `8c95877` -- Consolidate value_model_bridge's concentration calc onto
     the promoted helper (DoD-row-4 gap caught and closed).
- Diff vs branch point: `git diff e936a74 --stat` -> 17 files changed,
  1265 insertions(+), 11 deletions(-).
