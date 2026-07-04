# Program Report 17 — Universe v2 WS-Tenant-Loopway (Wave 3)

Branch `codex/u2-tenant-loopway` off synced `main` (tip `da87472`, all of
Wave 0-2 merged: Foundations #18, Safety #19, Data-Classes #21,
Week1-Harness #20, Segmented-Book #22). Loopway is the SCALE/PLG tenant:
~400 accounts, ≥90% tech-touch, campaign-dominant motions, Attio-shaped
CRM, product-analytics-heavy telemetry, Intercom-ish support chat, and
critically: **no named CSMs**. Entirely offline: no credentials, no live
org access, no network calls.

**Lead finding — cohort singularity.** Arc L1 scripts 60 tech-touch
accounts signing up in a day-30-45 wave; 35 never activate the driver
app by day 75. The correct agent behavior is exactly ONE `cohort_action`
enrolling the 35 in an activation-nurture campaign — never 35 individual
drafts. `eval/loopway_battery.py`'s `check_l1_cohort_singularity` proves
this holds: `cohort_actions_found: 1`, zero per-account motion leaks on
any of the 35, and the 25-account contrast group (which activated fine
inside the same wave) correctly receives no action of any kind. Arc L3
repeats the same claim independently at a different trigger (silent usage
decay, not shallow adoption) and a tighter cohort size (20 vs. 35): one
win-back `cohort_action`, zero leaks, usage genuinely reads zero by day
200 (not merely "trending toward zero").

**Tail false-alarm number.** The sampled forbidden-motion sweep covers
every one of the 98 named arc accounts plus the fixed 40-account tail
sample (`synthetic_book.PLAIN_TAIL_SAMPLE_40`) — 162 accounts — at each
of the three arc checkpoint days (75, 120, 200): **486 account-day
evaluations, zero forbidden-motion hits.** No tech-touch account (376 of
400, ≥90% of the book) ever receives `personal_email`/`working_session`/
`qbr`; no mid-touch account ever receives `working_session`/`qbr`
(Loopway's own, stricter-than-fleetops mid-touch rule — see IF/THEN).

**Onboarding question count at 400 accounts (third data point).** Two
independent onboarding-cost measurements were taken: (1)
`eval/loopway_attio_simulated_onboarding.py`, the Attio-shaped explorer/
source-map path (the tenant's actual CRM vendor dialect) — **5**
confirmation questions, identical to fleetops' Salesforce-shaped
baseline. (2) `eval/loopway_week1.py`'s in-process `ingest_table`/
`confirm_book` driver over a narrower 2-table (Account/Contact, no
Opportunity — this tenant's CRM shape has none) — **4** questions.
Neither scales with the 400-account row count; both are a function of
schema-shape ambiguity, confirming Program 14's fleetops-only finding
(question count tracks schema diversity, not row count) generalizes
across vendor dialects, not just within one book.

## DoD Evidence

| Phase | Result | Evidence |
| --- | --- | --- |
| 1: Tenant bible | Complete | `docs/TENANT_LOOPWAY_BIBLE.md` — canon (4 modules, no named CSMs, 2-person growth team), the 400-account book generation rule (deterministic stem×suffix tail, hand-authored 4 high/20 mid), `knowledge/tenants/loopway/playbooks.json` (tech-touch forbids all personal motions; mid-touch additionally forbids `working_session`/`qbr` — stricter than fleetops, see IF/THEN) + `content_catalog.json`, arcs L1/L2/L3/L-H1 (all `gap` mode), chat class (`chat_fixtures.py`, 12 accounts) with the sanctioned additive widening of `CommunicationSignal.channel` to include `"chat"`. |
| 2: Fixtures + Attio transport | Complete | `src/ultra_csm/data_plane/tenants/loopway/synthetic_book.py` (400 accounts, zero runtime randomness, lazy/cached via `narrative_shared.py` — 12ms cold build, mirrors `narrative_shared.base_synthetic_book`); `campaigns.py` (L1 activation-nurture + L3 win-back cohort campaigns, engagement exhaust); `event_telemetry.py` (per-arc usage curves for the 98 named accounts — full exhaust ONLY for L1/L2/L3/herring, well under the ~120-account ceiling); `attio_transport.py` + `eval/loopway_attio_simulated_onboarding.py` (fake Attio-shaped transport, third vendor dialect after fleetops-Salesforce; 5 onboarding questions recorded). |
| 3: Batteries + week-1 + economics | Complete | `eval/loopway_battery.py` — 9 checks, `hard_ok: true`, **~0.3s runtime** (no sampling shortcuts even needed at that speed, though the bible's sampling discipline — 98 named + 40-tail — is followed throughout for future-proofing against slower checks). `eval/gold/loopway_expected_actions.json` — 98 rows, own loopway-scoped validator (see IF/THEN: `eval/expected_actions_gold.py`'s account-slug allowlist is hardcoded to fleetops). Canaries: 64 accounts (24 named + fixed 40-tail sample, not all 400 — documented deviation, see below). `week1-protocol-loopway-csm` completes end-to-end via a minimal 3-line additive dispatch branch in `eval/week1_protocol.py` (all Loopway-specific logic lives in `eval/loopway_week1.py`, within this workstream's ownership map) — sections 1/2-analog/3/5/6 populated; section 4 (`feedback_persistence`) is an honest, stated SKIP (see IF/THEN — `run_time_to_value_sweep` returns zero work items against this tenant's book by design). `docs/WEEK1_PROTOCOL.md` gains its Loopway baseline column. |

## IF/THEN Branches Taken

- The dispatch's mid-touch tier table (via `docs/UNIVERSE_V2_CONVENTIONS.md`
  §2, mirroring fleetops) omits `working_session`/`qbr` from mid-touch's
  *allowed* list but fleetops never explicitly *forbids* them there → this
  tenant's `playbooks.json` explicitly forbids both at `mid_touch` (the
  dispatch's own instruction: "even mid-touch forbids `working_session`") —
  additively extended to also forbid `qbr` for the same stated reason
  (Loopway's 2-person growth team genuinely cannot staff either motion
  below the 4 high-touch relationships). Recorded in the bible's "Playbook"
  section as a deliberate deviation from fleetops' table, not a silent copy.
- `docs/SYNTHETIC_UNIVERSE_BIBLE.md`'s tier-mirror precedent
  (`eval/tier_policy_battery.py`) and this tenant's own arcs both need a
  cohort-collapse threshold → reused the existing precedent's constant
  (`COHORT_THRESHOLD = 10`) rather than inventing a second value; Loopway's
  L1 (35) and L3 (20) cohorts both clear it comfortably, and L2 (3 accounts,
  correctly *not* collapsed — escalation stays per-account) sits safely
  below it, verified explicitly by `check_l2_pql_escalation`'s
  not-collapsed assertion.
- `CommunicationSignal.channel` is a closed `Literal["email", "call",
  "meeting"]` that excludes `"chat"` → grepped every consumer
  (`signal_extractor.py`, all five existing tenants' `*_comms.py` modules)
  and confirmed none exhaustively switches over `.channel`'s value →
  additively widened to `Literal["email", "call", "meeting", "chat"]`,
  sanctioned by `docs/UNIVERSE_V2_CONVENTIONS.md` §7 and the dispatch's own
  instruction for exactly this case. Recorded in the contract's own
  docstring, the bible, and here.
- `eval/expected_actions_gold.py`'s `load_expected_actions` validates
  `account_slug` against `_KNOWN_ACCOUNT_SLUGS`, hardcoded from fleetops'
  own `_ACCT_DATA` — not reusable for Loopway's slug space without editing
  a file outside this workstream's ownership map → wrote a Loopway-scoped
  gold loader (`load_loopway_gold`, inside `eval/loopway_battery.py`,
  which IS owned) applying the identical validation discipline (fail-closed
  on unknown mode/motion, non-empty `motion_in` for non-"none" rows) scoped
  to Loopway's own known slugs, rather than widening the shared loader's
  allowlist or duplicating its full schema logic.
- `eval/canary_battery.py`'s checks (`check_canary_integrity`,
  `check_cross_account_contamination`, etc.) are deeply fleetops-specific
  (`observe_sim_state`, `build_reason_draft_request_for_account`,
  `DEFAULT_TENANT`) and that file is NOT in this workstream's ownership map
  (only "the canary-battery sweep-list line" is) → built Loopway's own
  canary registry (`canary_registry.py`, mirroring the existing module's
  exact pattern: a dormant slug-keyed sibling table, never a `CRMAccount`
  contract widening) and its own integrity check inside
  `eval/loopway_battery.py`; added exactly one additive comment block to
  `eval/canary_battery.py` pointing a reader to the sibling registry,
  touching zero existing check logic or assertions (verified: that file's
  own battery still reports `5/5 hard_ok: true`, unchanged, after the edit).
- Given 400 accounts, planting a canary on every one would add fixture
  bulk with zero additional assertion value (the integrity check's logic
  is identical whether the account list is 64 or 400) → canaries planted
  on 24 named accounts (4 high + 20 mid) + a fixed 40-account tail sample
  only — the same "sampled, not exhaustive" discipline this tenant applies
  everywhere else. Stated as a deviation in the bible's "Canary spec"
  section and here, not silently narrowed.
- `eval/week1_protocol.py`'s `run_full_protocol` hard-rejects (raises) any
  `tenant != "fleetops"`, and its Section 4
  (`feedback_persistence`) drives `ultra_csm.agent1.run_time_to_value_sweep`
  against a real ephemeral-Postgres `ActionGate` and fleetops' own
  divergence-heuristic value model (health-band/success-plan/threshold
  triggers) → verified empirically (ran it directly against Loopway's
  `CustomerDataPlane`) that this sweep engine returns **zero work items**
  against Loopway's book: it has no `SuccessPlan` rows by design (no named
  CSM exists to author one). Rather than force-fit that engine or widen
  `week1_protocol.py`'s internals (outside this workstream's ownership
  map beyond "additive Makefile targets"), added a minimal 3-line additive
  dispatch branch delegating `tenant="loopway"` to `eval/loopway_week1.py`
  (fully owned), which implements sections 1/2-analog/3/5/6 for this
  tenant's own arcs and records section 4 as an honest, stated SKIP with
  the verified reason — never a fabricated pass, never silently dropped.
- Loopway's fixture set has no dedicated relationship/calendar comms
  module the way fleetops' six narrative arcs do (no
  `reply_latency_trend`/`thread_participation_width`/
  `meeting_cadence_shift` signal exists for this tenant — chat replaces
  email as the support channel entirely) → `eval/loopway_week1.py`'s
  Section 2 is stated explicitly as an "analog," not the same signal
  family, computing chat-signal availability (present/absent by K) instead
  — the honest substitute for a signal family this tenant's fixture shape
  genuinely does not have, rather than silently reporting the fleetops
  signal names as `insufficient_history` (which would misrepresent a
  fixture-coverage boundary as a cold-start finding).
- The one-time tail-name generator's first pass produced small
  transcription mismatches between hand-typed bible prose and the
  generator's authoritative output (e.g. `pathfynd-express` vs. the
  generator's actual `pathfynd-freight` at the same tail index) → treated
  the generator's output as ground truth and corrected the bible's arc
  slug lists to match it exactly, rather than the reverse (code/artifacts
  on disk outrank hand-authored prose, per this task's own operating
  rule).
- One originally-chosen industry tag and one company name (both built
  from the same wrong-domain word this program is now careful not to
  repeat verbatim) tripped `tests/test_hygiene_scan.py`'s wrong-domain
  residue guard -- that exact word is reserved for a different sim
  tenant's domain → renamed both to a delivery-flavored equivalent
  across the book; `make hygiene` and the full suite went green
  immediately after, with zero other residue findings.

## Consolidated Owner Ask

1. **`eval/loopway_battery.py`'s policy resolver is a standalone
   evaluation tool, not a production wiring** — identical disclosure to
   `eval/tier_policy_battery.py`'s own Owner Ask #1. It reads
   `playbooks.json` and Loopway's fixture book directly to prove the
   ground truth is internally consistent and tier-differentiated at 400
   accounts; no lens/sweep/CLI path in `src/ultra_csm/agent1/` consumes
   `playbooks.json` or emits playbook motions for Loopway (or any tenant)
   yet. A future program wiring a real playbook-driven proposal path
   would need this, and would also need to resolve the Section 4 gap
   below at the same time (a real sweep engine that DOES trigger on
   Loopway's shape would make feedback-persistence testable here).
2. **Feedback persistence (week1 Section 4) has no engine that applies to
   Loopway's fixture shape.** `run_time_to_value_sweep`'s divergence
   heuristics need `SuccessPlan` rows this tenant has none of by design.
   A future program should NOT extend that engine to fabricate a
   Loopway-facing success-plan proxy — a genuinely PLG tenant does not
   have success plans — but should instead design a recurrence-suppression
   test against whatever proposal surface eventually consumes
   `playbooks.json` motions (per Owner Ask #1), keyed the same way
   (account, factor, motion) but against cohort-level and campaign-shaped
   proposals, which is a materially different shape than fleetops' per-
   account proposal recurrence test.
3. **The 40-account tail sample and the 64-account canary sample are both
   the FIRST N accounts by generated index**, not a hash-based or
   stratified sample. This was sufficient for this program (the tail is
   internally homogeneous by construction — no arc lives in the plain
   tail by definition), but a future perturbation/drift program (Wave 4,
   per `docs/UNIVERSE_V2_CONVENTIONS.md` §6) introducing tail
   heterogeneity should re-derive the sample selection rule rather than
   assume "first 40" stays representative once the tail is no longer
   uniform.

## STOP Conditions

No credentials were read, no live org was touched, no network call was
made anywhere in this program. `eval/canary_battery.py`'s own checks were
never touched beyond one additive comment block (verified: `5/5 hard_ok:
true`, unchanged). `eval/week1_protocol.py`'s fleetops path (sections
1-6, the Postgres-backed `ActionGate`/`run_time_to_value_sweep` machinery)
was never touched beyond the 3-line additive dispatch branch — verified by
re-running `week1-protocol-csm` (fleetops) after all Loopway changes:
`ok: true`, `onboarding_questions_asked: 5`, unchanged from Program 13's
baseline. `docs/UNIVERSE_V2_CONVENTIONS.md` was read but not edited
(Foundations' file, referenced not owned here). No test, threshold, or
battery assertion was weakened to pass — the one battery failure hit
during development (`l3-cohort-singularity` expecting exactly-zero usage
at day 200 when the first-draft decay curve only reached zero at day 210)
was fixed by correcting the fixture's own decay curve to match the
bible's stated "by day 200" checkpoint, verified against the bible text
before editing, never by loosening the assertion. Sentinel grep (`make
hygiene`) clean after fixing the one wrong-domain residue finding
(a reserved word from a different sim tenant's domain, caught by the
pre-existing hygiene scanner, not introduced by this program's own
assertions). Runtime discipline held
throughout: full `make eval` at 96.43s (under the 3-minute ceiling, and
faster than Program 14's 145.58s baseline since Loopway's battery adds
negligible pytest surface — its own logic is exercised via its dedicated
Makefile target, not `tests/`); every individual battery well under the
90-second ceiling (`loopway-battery-csm` at ~0.3s;
`week1-protocol-loopway-csm` at ~1.7s).

## Skeptical Reviewer Paragraph

A skeptical reviewer should weigh four real limits, naming the specific
sampling strategies used. First, the tier-policy-style resolver in
`eval/loopway_battery.py` proves the *ground truth* is internally
consistent and tier-differentiated at 400 accounts — it is not evidence
that any live agent behaves this way in production, since nothing in the
production sweep/lens path reads `playbooks.json` for any tenant yet (the
same disclosed gap every prior Universe v2 workstream has recorded).
Second, the sampling strategy itself: every battery check samples the 98
named arc accounts (60 in L1, 3 in L2, 20 in L3, 15 in the herring) plus a
FIXED 40-account slice of the 278-account plain tail — the first 40 by
generated index, never a hash-based or randomized sample — for a total
162-account, 486-account-day forbidden-motion sweep. This is a real,
stated bound: the untested 238 plain-tail accounts (278 minus the 40
sampled) are homogeneous by construction (no arc, no distinguishing
trigger fact), so the sampling risk is low today, but a reader should not
generalize "zero forbidden motions across 486 account-days" to "zero
forbidden motions across all 1200 possible account-days" without that
caveat. Third, the canary sampling deviation: only 64 of 400 accounts
(24 named + the same fixed 40-tail sample) carry a safety canary, a
documented narrowing from "every account" for fixture-bulk reasons — the
canary integrity check's assertions are logically identical at 64 or 400
accounts, but a reader auditing safety coverage specifically should know
the other 336 tail accounts carry no canary token at all, so a leak
specific to one of them (as opposed to the mechanism generally) could not
be caught by this battery. Fourth, week1 Section 4 (feedback persistence)
is an honest SKIP for Loopway, not a pass — the claim "week-1 competence
holds for Loopway" should be read as five of six sections, with the sixth
explicitly out of scope because the underlying sweep engine's trigger
surface doesn't apply to a tenant with no success plans, not because it
was untested by oversight.

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `563 passed, 1 skipped` in `96.43s` (under the 3-minute runtime-discipline ceiling) |
| `LC_ALL=en_US.UTF-8 make lint` | `All checks passed!` |
| `LC_ALL=en_US.UTF-8 make hygiene` | Exited 0 |
| `git diff --check` | Exited 0 |
| `LC_ALL=en_US.UTF-8 make content-invariance-csm` | `PASS: extractor output is byte-identical to the committed snapshot.` |
| `LC_ALL=en_US.UTF-8 make narrative-battery-csm` | `hard_ok: true`, 8/8 cases |
| `LC_ALL=en_US.UTF-8 make content-battery-csm` | `hard_ok: true`, 5/5 cases |
| `LC_ALL=en_US.UTF-8 make canary-battery-csm` | `hard_ok: true`, 5/5 cases (unchanged) |
| `LC_ALL=en_US.UTF-8 make quantity-battery-csm` | `hard_ok: true`, 3/3 cases |
| `LC_ALL=en_US.UTF-8 make transcript-battery-csm` | `hard_ok: true`, 4/4 cases |
| `LC_ALL=en_US.UTF-8 make tier-policy-battery-csm` | `hard_ok: true`, 4/4 cases |
| `LC_ALL=en_US.UTF-8 make loopway-battery-csm` | `hard_ok: true`, 9/9 cases, ~0.3s |
| `LC_ALL=en_US.UTF-8 make loopway-attio-simulated-onboarding-csm` | `fixture_state: fixture_verified`, `ambiguous_question_count: 5`, `live_tenant_proven: false` |
| `LC_ALL=en_US.UTF-8 make week1-protocol-csm` | `ok: true`, `onboarding_questions_asked: 5` (fleetops, unchanged from Program 13/14 baseline) |
| `LC_ALL=en_US.UTF-8 make week1-protocol-loopway-csm` | `ok: true`, `onboarding_questions_asked: 4`, ~1.7s |
| `PYTHONPATH=src:. .venv/bin/python -m eval.week1_protocol --tenant loopway --repeatability-check` | `two_runs_identical_modulo_random_uuids_and_timing: true` |
| `LC_ALL=en_US.UTF-8 make status` | `STATUS.md is current` |
