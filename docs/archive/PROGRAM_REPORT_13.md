# Program Report 13 — Universe v2 WS-Week1-Harness (Wave 1)

Branch `codex/u2-week1` off synced `main` (tip `e3d6df7`, Program 10's
Universe v2 Foundations). This workstream turns "week-1 competence" from a
claim into a measured, re-runnable, tenant-parameterized protocol
(`eval/week1_protocol.py`), run against `fleetops` today and unchanged
against every other tenant once waves 3-4 land their fixtures. It also
surfaces and fixes the workstream's most valuable finding: the existing
gate machinery records a human `deny` verdict but nothing consults it
before the next sweep re-proposes the same ask — fixed with a minimal
additive rejection ledger (`src/ultra_csm/rejection_ledger.py`).

## DoD Evidence

| Section | Result | Evidence |
| --- | --- | --- |
| 1. Onboarding cost | Complete | `run_onboarding_cost_driver` drives `ultra_csm.mcp_server.ingest_table`×3 + `confirm_book` over fleetops' Account/Contact/Opportunity book in-process (the `eval/mcp_relational_demo.py` calling convention). Measured: **5 questions asked** (`CRMAccount.account_id`/`owner_id`, `CRMContact.contact_id`, `CRMOpportunity.opportunity_id`/`stage_name`), ceiling 8, `within_ceiling: true`. Matches `docs/PROGRAM_REPORT_3.md`'s corpus-B baseline of 5 exactly (a different book, same measured number — recorded as the fleetops baseline in `docs/WEEK1_PROTOCOL.md`, not asserted as inherited). |
| 2. Cold-start honesty | Complete | For all six narrative-arc accounts (the only accounts with comms/relationship/calendar fixtures), classifies all four `signal_extractor` outputs at K in {3,7,14} as `computed`/`insufficient_history` from the extractor's own `value is None`. Walks `eval/gold/fleetops_expected_actions.json` via `eval.expected_actions_gold.load_expected_actions` for rows due at K; asserts no `shadow`-mode row cites an `insufficient_history` signal (fabrication check) and any `gap`-mode row not yet computable is correctly absent. `ok: true` at every K measured (12/24 signals `computed`, 12/24 `insufficient_history` at K=3/7/14 — `reply_latency_trend`/`meeting_cadence_shift` need a full 21-day trailing window and are honestly silent this early; `thread_participation_width`/`ticket_frequency_window` are computable from day 0). |
| 3. False-alarm rate | Complete | Reuses (imports, does not duplicate) `eval.narrative_battery.check_boring_controls`/`check_red_herrings`. Additionally re-checks the content-contamination half of that assertion at each K (day-independent; a real defect at any K) but deliberately does NOT assert "herring health band == green" at arbitrary early K — `cedar-valley` (red herring A) is scripted in `docs/SYNTHETIC_UNIVERSE_BIBLE.md` to show a pre-renewal wobble that only resolves to green by day 30, so asserting green at K=3/7/14 would invent a property the fixture was never scripted to satisfy. `ok: true` at every K measured. |
| 4. Feedback persistence | Complete | Runs `ultra_csm.agent1.run_time_to_value_sweep` against a real ephemeral-Postgres `ActionGate` at day K; records a human `deny` verdict (existing gate machinery) plus a rejection in the new `RejectionLedger` keyed by `(tenant_id, account_id, factor_name, motion)`; re-sweeps at K+1 and asserts the same key either does not recur, or recurs with the ledger acknowledging the prior rejection. **Wave-1 finding**: the proposal DOES recur unchanged by default — `ActionGate.record_verdict` marks the row `denied` but the sweep never consults verdict history — confirming the megaprompt's predicted gap. `RejectionLedger` (`src/ultra_csm/rejection_ledger.py`, 126 lines) is the minimal additive fix: a flat JSON-file ledger, config/state not a hard-coded rule, consulted by the harness after rejection. 8 unit tests (`tests/test_rejection_ledger.py`) + 2 integration tests against the real gate (`tests/test_week1_protocol.py`). `docs/DECISION_LOG.md` entry added (2 sentences, additive). |
| 5. Economics | Complete | `ultra_csm.value_model.resolve_tenant_tier` derives each account's tier; deterministic lane records `$0.00`/tier (fixture Slot B writer, zero-cost in `cost_tracker.MODEL_PRICING`); budget table (`high_touch<=$0.50`, `mid_touch<=$0.10`, `tech_touch<=$0.02`, per `docs/UNIVERSE_V2_CONVENTIONS.md` D6/§5) parses and is embedded in every artifact. Credentialed lane gated on `ANTHROPIC_API_KEY`; SKIPS CLEANLY and LOUDLY in both the absent and present case in Wave 1 (no live Slot B writer wired into this harness yet — recorded as a STOP condition below, not fabricated). |
| 6. Repeatability | Complete | `--repeatability-check` runs the full protocol twice and compares a canonicalized report (`_canonicalize_for_repeatability`) with `wall_clock_seconds` and the random `proposal_id`/`new_proposal_id` UUIDs (Postgres `gen_random_uuid()` primary keys, `migrations/0004_governance.sql`) excluded — the exclusion list is recorded in the artifact's `repeatability.excluded_fields`, never silent. Raw byte-identity over `proposal_id` is architecturally impossible for this schema; canonicalized-identical measured `true`. |
| Harness itself | Complete | `eval/week1_protocol.py` (~600 lines), `make week1-protocol-csm` target, `docs/WEEK1_PROTOCOL.md` (schema + fleetops baseline table), 17 new tests (`tests/test_rejection_ledger.py` ×8, `tests/test_week1_protocol.py` ×9), all passing. |

## IF/THEN Branches Taken

- The megaprompt named a live driver at
  `~/ultra-csm-corpus-runs/phase3-live-battery-20260703/drive_phase3.py`
  and told me to check whether it exists before relying on it. It exists
  (208 lines) and is a genuine artifact, but it drives a live Salesforce
  org over stdio JSON-RPC subprocess calls, ground-truthed against a
  specific seeded corpus (`~/ultra-csm-corpus-runs/seed-2e-20260703/ground_truth.json`)
  — neither portable nor offline. → Ported the *pattern* (one
  `ingest_table` call per table, honest `not_mappable` for any unscripted
  question, one `confirm_book`), not the file itself, using the closer
  and already-in-repo `eval/mcp_relational_demo.py`'s in-process calling
  convention (`ultra_csm.mcp_server.ingest_table(...)` called directly,
  no subprocess) against fleetops' own synthetic book. `docs/PROGRAM_REPORT_3.md`
  exists on this branch and was read in full for the "5 questions on
  corpus B" precedent; the number transferred to a different book almost
  exactly (5 questions measured here too), recorded as the new baseline,
  not assumed to be portable a priori.
- `ultra_csm.mcp_server` boots its own module-level ephemeral Postgres
  cluster at import time unless `ULTRA_CSM_MCP_READONLY=1` is set. Tried
  setting that env var to avoid a second cluster boot alongside the
  harness's own `boot_seeded_cluster` call → `ingest_table`/`confirm_book`
  are blanket-refused in read-only mode (a policy gate, not a real DB
  dependency — they only touch in-process `_relational_books` state).
  Reverted: accepted the (harmless, ~1s) double-cluster-boot cost rather
  than fight an access-mode policy this workstream doesn't own; recorded
  here rather than silently worked around.
- Section 3's false-alarm check initially additionally asserted "every
  control/herring's health band is green/unset at install-day K" (mirroring
  `check_red_herrings`' day-340 assertion at K instead). This failed
  immediately: `cedar-valley` (red herring A) is scripted in
  `docs/SYNTHETIC_UNIVERSE_BIBLE.md` to show `yellow` band from day 0
  through ~day 20, resolving to `green` only at day 30 (`HealthBandChange`
  day-30 beat) — a real, intentional pre-renewal wobble, not a defect. →
  Removed that assertion; kept only the day-independent content-
  contamination half of the check, and documented the reasoning in both
  this report and `docs/WEEK1_PROTOCOL.md` so a future reader doesn't
  re-introduce the same over-assertion. This is exactly the anti-Goodhart
  failure `eval/narrative_battery.py`'s own docstring warns against (never
  edit a check to match the fixture without a bible change explaining why
  the world changed) — here the fix was to correct my own new check, not
  the fixture, since the fixture was never wrong.
- `action_proposal.proposal_id`/`action_verdict.human_principal_id` are
  `uuid` columns (`migrations/0004_governance.sql`); my first pass used
  plain strings (`"week1-protocol-3"`, `"week1-reviewer"`) → switched to
  `uuid5`-derived deterministic ids (matching `tick.py`'s
  `TICK_TENANT_ID`/`TICK_SEED_ACTOR_ID` pattern) and a second seeded
  principal with `ROLE_ORDER_CONFIRM_AUTHORITY` for the human-reviewer
  role (matching `tests/_govhelpers.py`'s `setup_roster` convention of a
  distinct `authority` principal for verdicts), rather than inventing a
  new id shape.
- Section 6 (repeatability) as literally specified ("two consecutive full
  protocol runs byte-identical") is not achievable for this schema:
  `action_proposal.proposal_id` is `gen_random_uuid()`, freshly randomized
  by Postgres on every run, and `wall_clock_seconds` is a timing
  measurement. → Implemented repeatability as byte-identity over a
  canonicalized report with exactly those two field classes excluded, the
  exclusion list embedded in the artifact (`repeatability.excluded_fields`),
  and both raw (uncanonicalized) artifacts still written to disk for
  inspection. This is a narrower, honest definition than the megaprompt's
  literal wording; flagged here rather than silently redefining "byte-
  identical" without saying so.
- The megaprompt's "if the current machinery cannot express 'rejected with
  reason, don't re-propose' ... implement the MINIMAL additive
  persistence" branch fired: confirmed via direct test (section 4) that a
  denied recurring-eligible proposal reappears unchanged the next sweep.
  → Built `RejectionLedger` as a flat JSON-file ledger consulted by the
  harness (not wired into `tick.py`'s production sweep loop — that
  integration is explicitly out of scope, "do not build more than the
  minimal loop," and is recorded as an Owner Ask below).

## Consolidated Owner Ask

1. **`RejectionLedger` is not wired into `tick.py`'s daily sweep loop.**
   This workstream proved the gap and built the minimal persistence
   primitive (`src/ultra_csm/rejection_ledger.py`) and demonstrated it in
   the harness; actually consulting it inside `run_time_to_value_sweep` or
   `tick.run_tick_with_config` before emitting a proposal is real product
   work for whichever workstream owns the sweep/tick production path, not
   something this eval-harness workstream should half-wire.
2. **The credentialed economics lane (Slot B, real cost, <=3 accounts) has
   no live Slot B writer threaded into this harness.** Section 5's
   deterministic $0 lane and budget-table plumbing are complete and
   tested; a future workstream with `ANTHROPIC_API_KEY` access and a
   mandate to spend real money needs to wire a live `ReasonDraftWriter`
   into `run_economics` — deliberately not attempted here without an
   explicit spend authorization.
3. **Waves 3-4 re-running this protocol against `fieldstone`/`crateworks`/
   `loopway`** will hit `run_full_protocol`'s `NotImplementedError` guard
   (only `fleetops` fixtures exist as of Wave 1) — this is intentional
   (the harness is tenant-parameterized in its CLI/API surface, but the
   fixture data for the other three tenants doesn't exist yet per
   `docs/UNIVERSE_V2_CONVENTIONS.md` §1's "reserved for a future decision,
   not built now"). No action needed until those fixtures land; the guard
   is there so a premature `--tenant fieldstone` run fails loudly instead
   of silently running fleetops' book under a different label.

## STOP Conditions

No live credentials were read, no live vendor account was touched, no
network call was made anywhere in this workstream. No fixture, extractor,
contract, knowledge pack, or existing battery was edited — verified by
`git diff` review (only `eval/week1_protocol.py`, `docs/WEEK1_PROTOCOL.md`,
`src/ultra_csm/rejection_ledger.py`, two new test files, `Makefile`, and
one additive `docs/DECISION_LOG.md` entry are new/changed) and by
`content-invariance-csm` and `narrative-battery-csm` both re-running
green and byte-identical/unchanged in case count. No test, threshold, or
battery assertion was weakened to make anything pass — the one place a
new assertion would have failed (section 3's over-broad health-band check)
was removed for being wrong about what the fixture promises, not weakened
to dodge a real failure; the change is explained in IF/THEN above. The one
credentialed lane (section 5) is gated on `ANTHROPIC_API_KEY` and skips
loudly whether the key is present or absent, per instructions. Sentinel
grep (`make hygiene`) clean.

## Skeptical Reviewer Paragraph

A skeptical reviewer should weigh several real limits. **N(tenants) = 1
until wave 3.** Every number in this report and in
`docs/WEEK1_PROTOCOL.md`'s baseline table is fleetops-only; the harness's
tenant-parameterization is proven only by its `--tenant` CLI flag and a
`NotImplementedError` guard, not by a second tenant's fixtures actually
running through it — "tenant-parameterized from day one" is an
architectural property demonstrated by code structure, not yet an
empirical one. **Sections 1, 2, 3, and 6 are fully deterministic-lane
(offline, ephemeral-local-Postgres, zero external network calls, zero
LLM spend)**; section 4 (feedback persistence) is also deterministic but
depends on a real (locally ephemeral) Postgres cluster and the fixture
Slot B writer, not a fake in-memory gate — the megaprompt's mention of
"fake clients" is satisfied at the LLM-writer layer (fixture, zero cost)
but not at the governance-DB layer, where this harness reuses the
project's own `boot_seeded_cluster` convention rather than inventing an
in-memory `ActionGate` double. Section 5's credentialed lane never ran in
this report — every cost number here is the deterministic $0 lane; no
real Slot B spend was measured, so the budget assertions are proven to
parse and load correctly but not proven against a real dollar figure.
Section 2's "gap coverage" check is intentionally narrower than a full
re-run of the CSM briefing/proposal surface per gold row (that would
duplicate section 3's job); a reader should not conclude every `gap`-mode
gold row was end-to-end graded here, only that the signal-availability
precondition for grading it was checked. Finally, the rejection-ledger
finding (section 4) was measured on exactly one recurring-eligible
proposal per K in this report's run — the property ("a rejected proposal
does not recur unchanged") is demonstrated, not exhaustively swept across
every possible account/factor/motion combination in the book.

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `508 passed, 1 skipped` (up from Program 10's `491 passed, 1 skipped`; +17 new tests) |
| `LC_ALL=en_US.UTF-8 make lint` | `All checks passed!` |
| `LC_ALL=en_US.UTF-8 make hygiene` | Exited 0 |
| `git diff --check` | Exited 0 |
| `LC_ALL=en_US.UTF-8 make content-invariance-csm` | `PASS: extractor output is byte-identical to the committed snapshot.` |
| `LC_ALL=en_US.UTF-8 make narrative-battery-csm` | `hard_ok: true`, 8/8 cases |
| `LC_ALL=en_US.UTF-8 make week1-protocol-csm` | `"ok": true` for K in {3, 7, 14}; onboarding_questions_asked: 5 |
| `LC_ALL=en_US.UTF-8 python -m eval.week1_protocol --tenant fleetops --install-day 3 --repeatability-check` | `"ok": true`, `two_runs_identical_modulo_random_uuids_and_timing: true` |
| `LC_ALL=en_US.UTF-8 make status` | `STATUS.md is current` |
