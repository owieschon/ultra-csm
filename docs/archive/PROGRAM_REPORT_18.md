# Program Report 18 — Universe v2 WS-Perturbation-Drift (Wave 4, final)

Branch `codex/u2-perturb` off synced `main` (all of Waves 0-3 merged:
Foundations #18, Safety #19, Week1-Harness #20, Data-Classes #21,
Segmented-Book #22, Crateworks #24, Loopway #25, Fieldstone #26).
Hand-authored tenants catch judgment failures; this program catches
CALIBRATION failures — thresholds and assumptions that only held because
every tenant's numbers sat where the bible authors put them — and adds
the time dimension nobody tests: the tenant changing under the agent
mid-flight. This is the final stream of the Universe v2 master plan; its
capstone renders the whole effort's evidence into one table.

## DoD Evidence

**Covariance-table lead result: all six perturbation cells and all five
drift checks passed on the first implementation attempt** — no sanctioned
minimal fixes were required anywhere in this program (unlike prior
programs' typical pattern of one or two real bugs surfacing). The one
genuine adjustment was a magnitude tuning, not a bug fix: see IF/THEN.

| Phase | Result | Evidence |
| --- | --- | --- |
| 1: Perturbation library | Complete | `eval/perturbation/perturb.py`: five pure functions, one per D7 axis (`latency_scale` + a recent-window variant, `volume_scale`, `hygiene_drop`, `schema_rename`, `arr_shift`), each deterministic (`det_id`-derived selection, never `random`/`now()`), each documented with its invariant. 14 unit tests on a toy book (`tests/test_perturbation.py`), not touching any real tenant fixture. |
| 2: Perturbation battery | Complete | `eval/perturbation_battery.py`: 6 named cells, `hard_ok: true`, ~2s runtime (well under the 10-minute budget), byte-identical across two runs. `latency-uniform-no-new-flags` (Trailhead x3 uniform, trend stays within the healthy `<=10h` tolerance), `latency-recent-window-flags-real-stretch` (same account, windowed-only scale, trend crosses the tolerance — the direct contrast to cell 1), `volume-down-degrades-honestly` (thinned to 10%, degrades to `insufficient_history`, never fabricated), `hygiene-drop-no-crash` (30% optional-field nulling on Trailhead contacts, no exception, evidence of the drop recorded), `schema-rename-asks-or-refuses` (10 fields renamed across the real Account/Contact/Opportunity onboarding tables, verified against the actual `ingest_table` mapping layer — no field silently kept its old meaning), `arr-shift-moves-tier-and-forbidden-motions` (`aspenridge-supply` -60% ARR crosses mid_touch → tech_touch, `forbidden_motions` set moves with it). |
| 3: Drift events | Complete | Bible-first (`docs/SYNTHETIC_UNIVERSE_BIBLE.md`'s new "Drift events" section, written before the code). Two new `book_simulator.py` mutation types, both D7-reserved names: `SchemaFieldRename` (day 120, tenant-wide marker — renames `Account.Industry`→`Vertical` and `Contact.Title`→`JobTitle` in the raw onboarding source records, never in any `FixtureCustomerData` row) and `JunkContactImport` (day 150, 40 junk contacts across the six existing arc accounts — a real `contacts_list` append, `det_id`-keyed). `eval/drift_battery.py`: 5 checks, `hard_ok: true`, byte-identical across two runs (~20s each) — schema-rename before/at/after (day 115 unrenamed; day 125/155 surface a new confirmation question or refuse), junk-contacts-present-after-day150 (0 before, 40 total after, verified per-account), width-signals-unaffected-by-junk-import (true by construction — width reads `StakeholderRelationship` fixtures, never the raw `CRMContact` table — verified directly), narrative-battery-still-green-post-drift (8/8, unchanged), content-invariance-isolation (byte-identical). |
| 4: Capstone | Complete | `docs/DEPLOYMENT_READINESS.md`, auto-rendered by `scripts/render_deployment_readiness.py` (mirrors `scripts/render_status.py`'s discipline exactly — every cell reads a committed JSON artifact; a missing/unreadable artifact renders as an explicit failure cell, never silently omitted). Zero missing cells: 11 battery rows, 4 onboarding-cost rows, 6 perturbation cells, 5 drift checks, all `true`. `make deployment-readiness` (write + `--check` staleness gate, same pattern as `make status`). |

## IF/THEN Branches Taken

- Cell 2 (`latency-recent-window-flags-real-stretch`) initially used the
  same x3 magnitude as cell 1's uniform scale, on the theory that the
  SAME multiplier applied two different ways (uniform vs. windowed) would
  make the cleanest contrast pair → measured first: Trailhead's baseline
  trend is so close to zero (0.5h) that x3 on the recent window alone
  only reached 9.5h, just under `check_healthy_control`'s own `<=10h`
  tolerance — a coin-flip near the same threshold cell 1 checks from the
  other side, not a clean pass. Used k=6 for this cell instead (still
  deterministic, still documented in the code), which crosses the
  tolerance unambiguously (trend > 10h). Recorded in the code comment,
  not silently changed.
- `SchemaFieldRename`'s `account_slug="*"` marker (not a real account)
  would have `KeyError`'d at `simulate_book`'s unconditional
  `acct_id = _id[mutation.account_slug]` lookup → added an explicit
  early `continue` for this mutation type before that lookup runs, with
  a comment explaining it's a marker-only event with no
  `FixtureCustomerData` mutation of its own.
- The dispatch's Phase 2 grid table names "schema_rename (10 fields)" as
  a perturbation-battery cell distinct from Phase 3's narrative
  `SchemaFieldRename` drift event (2 fields, scripted at day 120) → kept
  them genuinely separate: the perturbation battery's cell renames 10
  fields as a stress test of the mapping layer in isolation (no bible
  narrative attached), while the drift event renames exactly 2 fields
  Program 3's recorded mapping actually maps, with a scripted day and
  before/at/after checkpoints. Sharing the same `schema_rename` function
  from the perturbation library is intentional reuse; the two are not
  the same test.
- `make eval`'s runtime grew to ~3:08-3:32 across this program's three
  commits (pytest running `eval.drift_battery.run_battery()`, which boots
  an ephemeral Postgres cluster per call, ~20s each) → consolidated
  `tests/test_drift_battery.py` from two separate tests (hard_ok check +
  repeatability check, 4 total battery calls) into one test with two
  calls, cutting ~18s. No explicit global `make eval` ceiling is stated
  in this dispatch (unlike Segmented-Book's explicit 3-minute rule for
  the 180-account expansion specifically) — the observed ~3:08 is
  reported honestly here rather than chased against an unstated target.
- The dispatch's PR-policy line reads: "Open PR with EARNED AUTO-MERGE:
  if this run had zero STOP events, no unresolved BLOCKED items, and
  every gate passed without weakening, run `gh pr merge --auto --merge`."
  This run genuinely qualifies (see STOP Conditions below) — but this
  session's user has repeatedly, explicitly confirmed a standing policy
  of being asked before any PR merge, at every prior wave boundary, with
  no stated exception for an "earned" case → the PR is opened normally,
  and the user is asked whether to invoke the dispatch's earned-auto-merge
  clause or hold for manual review, rather than the agent silently
  auto-merging a policy the user hasn't been asked to confirm applies
  here too. This reconciliation is between two written instructions
  (this dispatch vs. the session's standing user policy); resolving it
  by asking, not by picking one instruction over the other silently, is
  itself the STOP-adjacent judgment call being recorded.

## Consolidated Owner Ask

1. **Perturbation coverage is a fixed 6-cell grid on fleetops only, not a
   tenant x axis x magnitude cross-product.** The dispatch explicitly
   scopes it this way for runtime reasons; a future program wanting
   perturbation resilience proven against fieldstone/crateworks/loopway's
   own calibration (not just fleetops') would need its own grid, reusing
   `eval/perturbation/perturb.py`'s functions (they operate on generic
   `CommunicationSignal`/`CRMContact`/`CSCompany` tuples, not
   fleetops-specific types, so no new library code should be needed).
2. **Drift covers exactly 2 event types** (schema rename, junk contact
   import), scripted against fleetops only. The D7-reserved vocabulary
   names 5 perturbation axes and these 2 drift events as the full Wave 4
   scope — this is not a claim that these are the only ways a real tenant
   drifts over time, only the two the master plan named.
3. **No tenant has ever had a live agent actually consume
   `playbooks.json` motions in production** — this remains the same
   disclosed gap every prior Wave 1-3 report recorded (Foundations,
   Safety, Data-Classes, Segmented-Book, and all three tenant reports).
   `eval/tier_policy_battery.py` and this program's
   `DEPLOYMENT_READINESS.md` prove the ground truth is internally
   consistent and tier-differentiated across all four tenants — not that
   any agent is wired to read it yet.

## STOP Conditions

No credentials were read, no live org was touched, no network call was
made anywhere in this program (the ephemeral Postgres cluster the
onboarding-driver/drift-battery checks boot is fully local and
deterministic, the same pattern every prior week-1-protocol run in this
repo already uses). `docs/UNIVERSE_V2_CONVENTIONS.md`, every tenant's
fixtures/thresholds/gold files, and every existing battery this program
doesn't own were never touched — verified both by `git diff` review per
phase and by all nine pre-existing batteries (narrative, content, canary,
quantity, transcript, tier-policy, fieldstone, crateworks, loopway)
re-running unchanged-green after every one of this program's four
phases. No test, threshold, or battery assertion was weakened to pass.
Zero STOP events fired: no frozen contract needed an unsanctioned
widening, no battery could only pass by weakening an assertion, nothing
required live credentials. Sentinel grep (`make hygiene`) clean.

## Skeptical Reviewer Paragraph

A skeptical reviewer should weigh three real limits. First, all six
perturbation cells passed without a single sanctioned minimal fix —
a reader should not conclude the system has zero calibration bugs; it
means the six SPECIFIC calibration failure modes this grid was built to
catch (absolute-hours thresholds, window-logic fabrication, null-handling
brittleness, stale-mapping assumptions, hard-coded tier/ARR assumptions)
did not exist at the points this grid samples, on fleetops. A
differently-shaped grid, or the same grid run against fieldstone/
crateworks/loopway's own calibration, could still surface something this
run didn't touch (Owner Ask #1). Second, drift covers exactly two event
types on one tenant — "drift resilience is proven" should be read as "the
two named D7 drift events are proven, on fleetops," not as a general
claim that any conceivable mid-timeline tenant change is handled; a
schema rename mid-onboarding and a junk-contact import are real but
narrow slices of what "the tenant changes under the agent" could mean.
Third, `docs/DEPLOYMENT_READINESS.md`'s "zero ad-hoc per-tenant rules"
claim is true of the ACTION-ECONOMICS layer specifically (every tenant's
tier resolution and forbidden-motions set flow through the same
Foundations-built resolver) — it is not a claim that every other layer
(comms fixtures, mess-quota specs, chat classes) is equally uniform
across tenants; those are deliberately DIFFERENT per tenant by design
(that is the whole point of hand-authoring four distinct tenants), and a
reader should not conflate "no ad-hoc action-economics" with "the
tenants are otherwise interchangeable."

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `583 passed, 1 skipped` in `188.58s` (up from Program 14's `563 passed, 1 skipped`; no explicit ceiling stated for this dispatch, reported honestly) |
| `LC_ALL=en_US.UTF-8 make lint` | `All checks passed!` |
| `LC_ALL=en_US.UTF-8 make hygiene` | Exited 0 |
| `git diff --check` | Exited 0 |
| `LC_ALL=en_US.UTF-8 make content-invariance-csm` | `PASS: extractor output is byte-identical to the committed snapshot.` |
| `LC_ALL=en_US.UTF-8 make narrative-battery-csm` | `hard_ok: true`, 8/8 cases |
| `LC_ALL=en_US.UTF-8 make content-battery-csm` | `hard_ok: true`, 5/5 cases |
| `LC_ALL=en_US.UTF-8 make canary-battery-csm` | `hard_ok: true`, 6/6 cases |
| `LC_ALL=en_US.UTF-8 make quantity-battery-csm` | `hard_ok: true`, 3/3 cases |
| `LC_ALL=en_US.UTF-8 make transcript-battery-csm` | `hard_ok: true`, 4/4 cases |
| `LC_ALL=en_US.UTF-8 make tier-policy-battery-csm` | `hard_ok: true`, 4/4 cases |
| `LC_ALL=en_US.UTF-8 make fieldstone-battery-csm` | `hard_ok: true`, 6/6 cases |
| `LC_ALL=en_US.UTF-8 make crateworks-battery-csm` | `hard_ok: true`, 6/6 cases |
| `LC_ALL=en_US.UTF-8 make loopway-battery-csm` | `hard_ok: true`, 9/9 cases |
| `LC_ALL=en_US.UTF-8 make perturbation-battery-csm` | `hard_ok: true`, 6/6 cases, ~2s, byte-identical across two runs |
| `LC_ALL=en_US.UTF-8 make drift-battery-csm` | `hard_ok: true`, 5/5 cases, ~20s, byte-identical across two runs |
| `LC_ALL=en_US.UTF-8 make deployment-readiness` | `docs/DEPLOYMENT_READINESS.md is current`, zero missing/unreadable cells, summary `all true` |
| `LC_ALL=en_US.UTF-8 make status` | `STATUS.md is current` |
