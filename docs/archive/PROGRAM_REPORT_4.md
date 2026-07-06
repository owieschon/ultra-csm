# Program Report 4

Branch `claude/rocketlane-program`, commits `6e11859`..`ccabc42` plus this
report's commit, stacked on `claude/live-integration` (Program 3's PR #11).
Program 3 closed with the relational relay path proven live at scale on
corpus B (Salesforce). Program 4 adds Rocketlane as a second live data
source and family of contracts, lights up the value model's fourth
(outcome/TTV) rail with real onboarding evidence, and proves the first
cross-system join between corpus B and corpus C.

## DoD Evidence

| Workstream | Result | Evidence |
| --- | --- | --- |
| R1: contracts, fixtures, source maps | Complete | `OnboardingProject`/`OnboardingPhase`/`OnboardingTask` frozen dataclasses + `OnboardingConnector` Protocol in `contracts.py`, mirroring `CRMDataConnector`. `ROCKETLANE_SOURCE_MAPS` added to `source_maps.py`/`ALL_SOURCE_MAPS`. New source-map coverage test (none existed before this program) asserts every `Onboarding*` field is mapped. `FixtureOnboardingConnector` with 6 adversarial fixture accounts. Parsed against R0's live sample payloads with 2 verified deltas from the spec doc folded into the parser (see Findings). 19 new tests. Commit `6e11859`. |
| R2: TTV bridge | Complete | `derive_ttv_milestones`/`has_activation_gap` (pure functions, R1). Wired into `build_customer_value_model` (`onboarding_milestones=()` default) and Agent 1's `time_to_value.py`/`sweep.py` evidence-grounding checks, both as additive optional parameters — every pre-existing call site and test unchanged. Fixed a latent evidence-mislabeling bug this wiring exposed (`_ttv_base_factors` hardcoded every milestone-gap ref as `telemetry`, even for Rocketlane ids). Proof: an existing fixture account with zero usage signals and zero success plans (`STARK_INSUFFICIENT`) produces no Agent 1 work item today; with a Rocketlane connector wired in, the *unchanged* sweep logic proposes a gated TTV outreach citing real phase/task ids, through a live `ActionGate`. 6 new tests. Commit `41a709c`. |
| R3: seed corpus C | Complete, with a documented scope reduction | `mcp__rocketlane__*` confirmed live (same lane R0 used). 5 of 6 planned datasets seeded as new phases+tasks (tagged `UCSM-P4C-D<n>`) inside the two pre-existing factory projects — no `create_project` tool exists in this environment's MCP surface (verified exhaustively) and REST remains 401-blocked, so no new project/company/`externalReferenceId` could be created. `ground_truth.json` authored before any write; ledger JSONL per response; post-seed counts exact (baseline 10 phases/49 tasks untouched; +5 phases/+7 tasks, all tagged). Two live findings (auto-completion cascade, phase-dueDate recalculation) discovered and corrected into ground truth after observation, never faked before. Commit `ccabc42`. |
| R4: live battery + cross-system beat | Complete for 5/6 datasets | All 5 seeded datasets fetched fresh live, parsed through the real R1 adapters, asserted with exact numbers (milestone/achieved/open-gap/at-risk counts, activation-gap flags, evidence ids) against ground truth — zero mismatches. Cross-system beat: one real corpus B Salesforce account (read live, read-only) joined in-memory to live Rocketlane D2 evidence, driven through Agent 1's unchanged sweep + a real `ActionGate`; the resulting proposal cites `EvidenceRef(source="rocketlane", ...)` with real phase/task ids. 7 new tests (env-gated for the cross-system beat; real account id never committed). Commit `ccabc42`. |

## IF/THEN Branches Taken

- The spec's proposed `OnboardingTask` collided by name with an existing
  dead/reserved `OnboardingTask` dataclass in `contracts.py` (declared,
  never referenced anywhere in `src/` or `tests/`) → replaced it with the
  spec's real shape rather than keep two types with the same name. Not a
  silent deletion: the old type had zero callers, confirmed by grep before
  removing it.
- R0's sample payloads showed `inferredProgress` present in the spec doc's
  field list but the field was absent from the actual `get-project`
  response → re-verified live during R1 with `includeAllFields=true`,
  confirmed genuinely absent (not a capture artifact); parser fail-safe
  defaults to `"none"` rather than raising.
- `get_phases`' search/list shape lacked `project.projectId` entirely (only
  `{phaseId, phaseName}`) → `parse_phase` requires the detail-by-id shape
  and raises on the thin search shape rather than fabricate a `project_id`;
  the connector always detail-fetches.
- Widening Agent 1's evidence-grounding check (previously: an
  `evidence_signal_id` only counted if it matched a known usage-signal id)
  exposed a real, pre-existing bug: `_ttv_base_factors` hardcoded every
  milestone-gap evidence ref as `EvidenceSource="telemetry"` regardless of
  where the id actually came from → fixed by threading an
  `onboarding_evidence_ids` set through `project_ttv_lens`/
  `_ttv_base_factors`; the default (empty set) is byte-identical to
  pre-Program-4 behavior, so this is a bug fix exposed by new wiring, not a
  behavior change to existing paths.
- **R3's precondition check surfaced a real capability gap, not a
  safeguard**: the Rocketlane MCP toolset in this environment has no
  `create_project` tool and no template-instantiation tool (verified via
  exhaustive `ToolSearch`, not assumed from the initial tool list). Per the
  prompt's STOP discipline for "a live safeguard blocking a write," the
  closest analog here — a *missing capability*, not a safeguard to
  override — was not silently worked around by e.g. repurposing
  `create_project_template` as if it created a live project, or writing
  directly via a REST endpoint I have no working credential for. Instead:
  5 of 6 datasets were re-scoped from "new project" to "new phase inside an
  existing project" (still a faithful, live, create-only proof of the same
  contract/parser/bridge code), the 6th (join-set) was dropped entirely,
  and the gap is reported as an explicit owner ask below.
- Two live behaviors (phase auto-completion on task completion; phase
  `dueDate` recalculation from task `dueDate`) were discovered mid-seeding,
  not predicted by the spec doc → `ground_truth.json` was corrected *after*
  observing the real API responses, never adjusted before the write (which
  would have been faking the rail). Both are documented as live findings,
  not product defects — the connector code needed zero changes to handle
  either.
- The cross-system beat was originally planned against D3 (at-risk
  cluster) but D3's activation-gap (task `atRisk` before the phase's due
  date) does not by itself clear Agent 1 sweep's score>0 gate, which keys
  off the existing date-based `open_milestone_gaps` filter → switched to D2
  (a genuine date-overdue open gap) for the end-to-end sweep-to-proposal
  proof, and documented that D3's activation-gap signal is real and
  asserted directly (in the live-battery tests), just not wired into the
  sweep's scoring threshold. Not silently smoothed over.
- One test-authoring mistake surfaced during R4 (D5's expected milestone
  count was authored as 0, assuming "sparse" meant no phase dates; the
  phase actually has real dates, only the task is sparse) → reproduced,
  corrected in the test/ground-truth, re-run green. Not a product bug.

## Consolidated Owner Ask

1. **Rocketlane `create_project` capability.** Neither this environment's
   Rocketlane MCP toolset nor the REST lane (still 401-blocked, root cause
   undiagnosed since R0) can create a new Rocketlane project. This blocked
   the plan's D6 join-set dataset (new projects with `externalReferenceId`
   set to real Salesforce Account Ids) entirely, and forced datasets
   1-2/4-5 to be re-scoped from "new project" to "new phase inside an
   existing project." Two independent fixes would unblock this: (a) add a
   `create_project` (or create-from-template) tool to the Rocketlane MCP
   server's exposed surface, or (b) diagnose and fix
   `ULTRA_CSM_ROCKETLANE_API_KEY`'s 401 — per R0's diagnosis steps: confirm
   header name/format and key-generation location at
   `developer.rocketlane.com/docs/authentication`; check trial/plan gating
   of the REST API, since the org's MCP host is on a distinct subdomain
   from `api.rocketlane.com` (full host in
   `~/ultra-csm-corpus-a-PRIVATE.md`), which may indicate a
   different API cluster.
2. **D3's activation-gap signal isn't wired into Agent 1's sweep scoring.**
   `has_activation_gap()` (RUNNING_LATE progress, `atRisk` task, or
   overdue-with-null-actual) is proven correct and tested directly against
   live data, but Agent 1's sweep only turns a milestone into a scored work
   item through the pre-existing date-based `open_milestone_gaps` filter.
   An at-risk-but-not-yet-overdue Rocketlane milestone (D3's exact shape)
   currently cannot surface a sweep proposal on its own. If the product
   wants "at-risk before due date" to actually trigger a proposal (not just
   a briefing-level flag), that's a deliberate design decision for Agent
   1's scoring logic, not a bug — flagging for an explicit owner call
   rather than silently wiring it in.
3. **Rocketlane's undocumented server-side auto-completion and
   dueDate-recalculation behaviors** (see Findings) are not reflected
   anywhere in `developer.rocketlane.com`'s docs as fetched for the spec.
   Worth a note back to Rocketlane's docs team if this project maintains
   that relationship, though this is outside ultra-csm's scope to fix.

## STOP Conditions

No write to Salesforce/corpus B occurred (the cross-system beat's Salesforce
access was a single read-only SOQL query, matching the prompt's explicit
allowance). No test/threshold was weakened to pass — the one test-authoring
mistake (D5's expected milestone count) was corrected against reality, not
the other way around. No fabricated milestone on connector failure (tested
explicitly: `test_agent1_fails_closed_on_onboarding_connector_outage`). No
credentials or org identifiers appear in any committed file (the sentinel
grep caught and required a rephrase of one comment that literally spelled
out a banned id-prefix pattern while explaining why it was avoided — fixed
before commit). The missing Rocketlane `create_project` capability is
reported as a STOP-driven scope reduction (Consolidated Owner Ask #1),
not routed around with an undocumented API guess or a repurposed tool.

## Skeptical Reviewer Paragraph

A skeptical reviewer should note that R3/R4's live proof is meaningfully
narrower than the plan: 5 datasets living as phases inside 2 pre-existing
projects, not 6 datasets as distinct projects, and the cross-system beat
uses one account, not a batch. This narrowing was forced by a real,
verified tool-availability gap (no `create_project` in this MCP surface,
REST still dead) rather than chosen for convenience — but a reviewer should
still weigh that the join-set dataset's actual mechanism
(`externalReferenceId` set on write) was never exercised at all, only its
in-memory equivalent (an `OnboardingProject.account_id` set directly to a
real Salesforce id in test code). The connector-level TTV bridge logic
(`derive_ttv_milestones`, `has_activation_gap`) is proven correct against
real, live, freshly-fetched API payloads with exact-number assertions —
that part of the program's claim is solid. The Agent-1-wiring layer
(evidence grounding, outcome-rail flip, sweep-level proposal) is proven
correct on one path (the date-overdue gap, D2/D4-shaped) but the
activation-gap path (D3-shaped, RUNNING_LATE/atRisk) is proven correct only
up to `has_activation_gap()`'s own return value — it does not yet reach a
scored sweep proposal, a gap explicitly surfaced as Owner Ask #2 rather
than silently smoothed over by re-scoping the cross-system beat to D2. A
reviewer should also weigh that two of the four "live findings" in this
report (auto-completion cascade, dueDate recalculation) were discovered
because ground truth was corrected reactively after each write, not
because they were anticipated — the program's discipline held (author
before write, correct after observation, never fake), but the spec doc this
program worked from was measurably incomplete about Rocketlane's real
server-side behavior.

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `450 passed, 1 skipped` (cross-system-beat test skips without live env vars) |
| `LC_ALL=en_US.UTF-8 make lint` | `All checks passed!` |
| `LC_ALL=en_US.UTF-8 make hygiene` | Exited 0 |
| `git diff --check` | Exited 0 |
| `LC_ALL=en_US.UTF-8 make relational-battery-csm` | `hard_ok: true`, 20/20 seeds |
| `LC_ALL=en_US.UTF-8 make relay-battery-csm` | 11/11 passed |
| `LC_ALL=en_US.UTF-8 make demo` | Passed; `git status --short` clean after (no artifact drift) |
| `LC_ALL=en_US.UTF-8 make status` | `STATUS.md is current` |
| Live R4 battery (`r4_battery_report.json`) | `"problems": [], "ok": true` across all 5 datasets |
| Cross-system beat (live, with real env vars) | `1 passed`; without env vars, `1 skipped` (verified both ways) |
