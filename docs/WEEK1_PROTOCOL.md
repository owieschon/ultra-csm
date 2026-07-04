# Week-1 Competence Protocol

Universe v2, WS-Week1-Harness (Wave 1). Turns the "week-1 competence" claim
into a measured, re-runnable, **tenant-parameterized** protocol: it runs
against `fleetops` today; waves 3-4 re-run this unchanged (`--tenant
<slug>`) against `fieldstone`, `crateworks`, and `loopway` once their
fixtures land (see `docs/UNIVERSE_V2_CONVENTIONS.md` §1).

```
PYTHONPATH=src:. .venv/bin/python -m eval.week1_protocol --tenant fleetops
# or: make week1-protocol-csm
```

Runs install-day `K` in `{3, 7, 14}` in one invocation by default (or pass
`--install-day K` for a single day). Writes `eval/week1_report_<tenant>.json`.

## Artifact schema

```jsonc
{
  "artifact": "week1_protocol_report",
  "tenant": "fleetops",
  "install_days": [3, 7, 14],
  "claim_boundary": {"sim": true, "live": false, "n_tenants": 1},
  "onboarding_cost": { /* section 1, one measurement for the whole tenant */ },
  "by_install_day": {
    "3": {
      "install_day": 3,
      "cold_start_honesty": { /* section 2 */ },
      "false_alarm_rate": { /* section 3 */ },
      "feedback_persistence": { /* section 4 */ },
      "economics": { /* section 5 */ },
      "ok": true
    },
    "7": { "...": "..." },
    "14": { "...": "..." }
  },
  "repeatability": { /* section 6, only populated with --repeatability-check */ },
  "ok": true
}
```

### 1. `onboarding_cost`

Drives the conversational onboarding path (`ultra_csm.mcp_server.ingest_table`
× N tables + `confirm_book`) over fleetops' CRM book (Account/Contact/
Opportunity), in-process — the same calling convention as
`eval/mcp_relational_demo.py`, not a live stdio subprocess (see IF/THEN
below). Any question the driver has no scripted answer for is answered
`not_mappable` (Program 3's honesty rule: never guess a mapping).

| Field | Meaning |
| --- | --- |
| `questions_asked_count` / `questions_asked` | Human confirmation questions raised, by key. |
| `auto_mapped_by_tier` | Count of auto-mapped fields by provenance tier (`tier_a_source_declared`, `tier_b_exact_alias`, `other`). |
| `confirmations_required` | Same as `questions_asked_count` (kept separate in the schema for clarity at the call site). |
| `wall_clock_seconds` | Driver wall-clock time (excluded from the repeatability comparison — see §6). |
| `baseline_ceiling` | `8` — the fleetops baseline expectation from the megaprompt. |
| `within_ceiling` | `questions_asked_count <= baseline_ceiling`. |

### 2. `cold_start_honesty`

For each arc account (the six narrative-arc accounts with dedicated
comms/relationship/calendar fixtures — see "Scope note" below), computes
all four `signal_extractor` families as-of day K and classifies each as
`computed` or `insufficient_history` (the extractor's own `value is None`
signal — never a heuristic re-derivation). Then walks
`eval/gold/fleetops_expected_actions.json` (loaded via
`eval.expected_actions_gold.load_expected_actions`) for rows due at this K
and asserts:

- **(a) fabrication check**: no `shadow`-mode gold row cites a signal that
  is currently `insufficient_history` at this K (walking evidence status,
  not the label).
- **(b) gap coverage**: a `gap`-mode row whose signal is NOT YET computable
  at this K is correctly recorded as absent (not a defect); this harness's
  wave-1 scope is the honesty precondition, not re-running the full
  briefing/proposal surface per gold row (that overlap is deliberately
  covered by section 3 instead, to avoid asserting the same thing twice).

`ok` is true iff no fabrication problem and no true gap-coverage failure
was found.

### 3. `false_alarm_rate`

Reuses (imports, does not duplicate) `eval.narrative_battery`'s own
`check_boring_controls`/`check_red_herrings` — the 27 controls + 2 herrings
check at day 340 (the bible's own settled-state spot day). Additionally
re-checks the **content-contamination** half of that assertion at
install-day K (a program-authored case subject leaking onto a control has
no day-dependent lifecycle, so it is a real defect at any K). It does
**not** re-assert "herring health band == green" at arbitrary early K,
because `docs/SYNTHETIC_UNIVERSE_BIBLE.md`'s red herring A (`cedar-valley`)
explicitly scripts a pre-renewal wobble that only resolves to green by day
30 — asserting green at K=3/7/14 would be inventing a new property the
fixture was never scripted to satisfy (see IF/THEN below).

### 4. `feedback_persistence`

The most consequential section. Runs `ultra_csm.agent1.run_time_to_value_sweep`
against a real (ephemeral, local) `ActionGate` at day K, picks one
recurring-eligible proposal, records a human `deny` verdict with a reason
via the existing gate machinery, **and** records the rejection in the new
additive `ultra_csm.rejection_ledger.RejectionLedger` (keyed by `(tenant_id,
account_id, factor_name, motion)`). Re-sweeps at day K+1 and checks whether
a work item with the same key recurs; if it does, asserts the ledger
acknowledges the prior rejection for that exact key.

| Field | Meaning |
| --- | --- |
| `rejected_proposal_id` / `rejected_key` | The proposal and (account, factor, motion) key that was denied. |
| `recurred_unchanged` | `true` = DoD failure (the proposal came back with nothing changed and no acknowledgement). |
| `recurrence_detail.ledger_acknowledged` | Whether `RejectionLedger.lookup()` found the prior rejection for the recurring key. |
| `persistence_mechanism_used` | `false` only when no rejectable work item existed at K (nothing to test that day). |

**Wave-1 finding**: the pre-existing gate (`ActionGate.record_verdict`)
marks a denied proposal `status='denied'`, but nothing in
`run_time_to_value_sweep` consults prior verdicts before emitting a new
proposal for the next day — the same (account, factor, motion) ask
reappears unchanged by default. `RejectionLedger` is the minimal additive
fix (see `docs/DECISION_LOG.md`'s 2026-07-04 entry and
`src/ultra_csm/rejection_ledger.py`'s module docstring). It is consulted
by this harness; wiring it into `tick.py`'s daily run loop is future work,
not built in Wave 1 (scope discipline — "do not build more than the
minimal loop").

### 5. `economics`

`cost_usd_per_account_day` by tier (`ultra_csm.value_model.resolve_tenant_tier`
resolves each account's tier from `config/value_model_config.json`'s
`tier_rules`). The deterministic lane always records `$0` per tier (the
fixture Slot B writer has zero cost in `cost_tracker.MODEL_PRICING`) and
asserts the budget table parses:

| Tier | Budget (`cost_usd_per_account_day`) |
| --- | --- |
| `high_touch` | `<= $0.50` |
| `mid_touch` | `<= $0.10` |
| `tech_touch` | `<= $0.02` |

The credentialed lane (Slot B for <=3 accounts, real spend, gated on
`ANTHROPIC_API_KEY`) is **not wired in Wave 1** — see STOP condition in
`docs/PROGRAM_REPORT_13.md`. It SKIPS CLEANLY and loudly
(`credentialed_lane_ran: false` + a printed `SKIP (loud):` line) whether
the key is absent or present, since no live Slot B writer is threaded
through this harness yet.

### 6. `repeatability`

Only populated when the CLI is run with `--repeatability-check`: runs the
full protocol twice and compares canonicalized reports (see
`_canonicalize_for_repeatability` in `eval/week1_protocol.py`). Byte-identity
over the raw artifact is **not achievable** for a schema where
`action_proposal.proposal_id` is `gen_random_uuid()` — repeatability is
defined here as "the same decisions, evidence, counts, and classifications
every run," with `wall_clock_seconds` and the random proposal ids excluded
and the exclusion list recorded in the artifact itself (`excluded_fields`),
never silently.

## Scope note: "every arc account"

The megaprompt's "every extractor signal for every arc account" is read
literally as the six narrative-arc accounts with dedicated comms/
relationship/calendar fixture modules (`pinehill-transport`,
`pinnacle-supply`, `quarrystone-logistics`, `aspenridge-supply`,
`meridian-fleet`, `trailhead-logistics`) — the only accounts the four
`signal_extractor` functions can compute non-`ticket_frequency_window`
signals for. The other 27 controls + 2 herrings have case fixtures only
(`ultra_csm.data_plane.narrative_shared.cases_as_of`); `reply_latency_trend`,
`thread_participation_width`, and `meeting_cadence_shift` have no fixture
to compute from on those accounts — that is a fixture-coverage boundary,
not a cold-start gap, and section 3's false-alarm check already covers
those 29 accounts on the dimension that does apply to them (case-content
contamination).

## Fleetops baseline table (measured 2026-07-04, commit range for this
workstream)

| Metric | K=3 | K=7 | K=14 |
| --- | --- | --- | --- |
| Onboarding questions asked | 5 (constant; onboarding is not K-dependent) | | |
| Onboarding baseline ceiling | 8 | | |
| Cold-start: computed signals (of 24) | 12 | 12 | 12 |
| Cold-start: insufficient_history signals | 12 | 12 | 12 |
| Cold-start honesty `ok` | true | true | true |
| False-alarm `ok` | true | true | true |
| Feedback persistence `ok` | true | true | true |
| Economics: cost_usd_per_account_day (all tiers, deterministic lane) | 0.0 | 0.0 | 0.0 |
| Repeatability (`--repeatability-check`) | true (canonicalized) | -- | -- |

At K=3/7/14, `reply_latency_trend` and `meeting_cadence_shift` are
consistently `insufficient_history` for all six arc accounts (a 21-day
trailing-window signal cannot have two full windows by day 14) —
`thread_participation_width` and `ticket_frequency_window` are computable
from day 0. This 12/12 split is itself the interesting week-1 finding: half
of the four-signal family is honestly silent for the entire first two
weeks, by construction, and the harness proves the system does not
paper over that with a fabricated trend.

Future tenant runs append a column to this table (per-tenant baseline),
matching the fleetops baseline established here.

## Crateworks baseline (measured 2026-07-04, Universe v2 Wave 3,
WS-Tenant-Crateworks)

`--tenant crateworks` runs a DIFFERENT protocol shape than fleetops', not
the same sections re-run against different fixtures — see
`run_full_protocol_crateworks` in `eval/week1_protocol.py`. Crateworks has
no CS platform and no product telemetry vendor
(`docs/TENANT_CRATEWORKS_BIBLE.md` section 0), so
`ultra_csm.agent1.sweep._slot_b_inputs_for_account` fails closed for every
crateworks account — sections 4 (`feedback_persistence`) and the sweep half
of section 5 (`economics`) cannot run for this tenant by construction, not
by omission, and SKIP loudly rather than reusing fleetops' Postgres-gate/
sweep machinery against a data plane it was never built to grade:

- **Section 1 (`onboarding_cost`)** reuses `eval.crateworks_onboarding`'s
  two-pass driver (friction measurement + confirmed ingest) over the messy
  flat book, not fleetops' clean-book driver.
- **Sections 2/3 equivalent (degradation battery)** reuses
  `eval.crateworks_battery.run_battery()` verbatim (Arc C1 checkpoint
  truths, mess-integrity, degradation honesty, controls zero-flag, canary
  presence) rather than re-authoring cold-start-honesty/false-alarm checks
  that don't fit a CRM-only, no-CS-platform tenant's fixture shape.
- **Sections 4/5** loudly skip (`ran: false` + a recorded `skip_reason`),
  per the vendor-stack gap above.
- **Section 6 (repeatability)** works unchanged via `--repeatability-check`.

| Metric | K=3 | K=7 | K=14 |
| --- | --- | --- | --- |
| Onboarding questions asked (friction pass, blanket not_mappable) | 6 (constant; not K-dependent) | | |
| Fleetops baseline ceiling (reported, not gated — bible section 7) | 8 | | |
| Onboarding auto-mapped by tier (Tier A / Tier B / other) | 0 / 7 / 0 (constant) | | |
| Confirmed-ingest typed counts (Account/Contact/Opportunity) | 10 / 30 / 10 (constant) | | |
| Confirmed-ingest zero-hollow-records | true | | |
| Confirmed-ingest zero-fabricated-mappings | true | | |
| Degradation battery `hard_ok` (6 cases) | true | true | true |
| Arc C1 day-100 checkpoint: `thread_participation_width` (uncorrected) | -- | 2.0 | -- |
| Arc C1 day-100 checkpoint: `reply_latency_trend_hours` | -- | +16.0 | -- |
| Repeatability (`--repeatability-check`) | true (canonicalized) | -- | -- |

Interpretation: crateworks' raw friction number (6) sits close to
fleetops' (5) rather than far above it — identity fields always require
human confirmation regardless of mess (`external_book._auto_map_entry`
never auto-maps an identity field), so the mess's real cost shows up
elsewhere: all 7 auto-mapped fields survive at Tier B (exact-alias)
despite the header casing/whitespace chaos, meaning the degradation this
tenant demonstrates is not "the mapper breaks" but "the identity layer
downstream of a clean ingest still cannot tell two duplicate contact rows
apart" (Arc C1's day-100 finding) — the SHAPE of degradation the bible
asks this workstream to measure, not a low-vs-high question count.

## Loopway baseline (measured 2026-07-04, WS-Tenant-Loopway, Wave 3)

`--tenant loopway` dispatches (a minimal, additive 3-line branch in
`run_full_protocol`) to `eval/loopway_week1.py`, which implements
sections 1/2(analog)/3/5/6 against Loopway's own 400-account book and
arcs (`docs/TENANT_LOOPWAY_BIBLE.md`). Section 4 (`feedback_persistence`)
is an honest, stated SKIP — see below.

| Metric | K=3 | K=7 | K=14 |
| --- | --- | --- | --- |
| Onboarding questions asked | 4 (constant; onboarding is a function of schema-shape diversity, not account count or K — 400 accounts, 2 tables (Account/Contact, no Opportunity in this tenant's CRM shape), fewer ambiguous fields than fleetops' 3-table shape) | | |
| Onboarding baseline ceiling | 8 | | |
| Loopway battery (`eval/loopway_battery.py`) `hard_ok` | true (9/9 cases) | true | true |
| Cold-start analog: chat signals computed (of 12 chat accounts) | day-dependent (0 before day 32, growing as L1's 4 chat accounts' scripted questions come due) | | |
| False-alarm `ok` (herring L-H1 silence at day 105, mid-dip) | true | true | true |
| Feedback persistence | SKIP (loud, by design) — see note below | SKIP | SKIP |
| Economics: cost_usd_per_account_day (all tiers, deterministic lane) | 0.0 / 0.0 / 0.0 (high/mid/tech) | | |
| Economics: account_count_by_tier | high=4, mid=20, tech=376 | | |
| Repeatability (`--repeatability-check`) | true (canonicalized) | -- | -- |

**Onboarding cost is the third data point** across the three vendor
dialects this workstream set now spans: fleetops (Salesforce-shaped, 5
questions), loopway (Attio-shaped, 4 questions via
`eval/loopway_attio_simulated_onboarding.py`'s Attio explorer path, 5
ambiguous mapping questions there; the in-process ingest_table/confirm_book
driver above counts 4 for its narrower 2-table Account/Contact shape).
Neither scales with account count — both are a function of schema-shape
ambiguity, confirming Program 14's finding generalizes across vendor
dialects, not just within one.

**Feedback persistence SKIP, stated honestly.**
`ultra_csm.agent1.run_time_to_value_sweep`'s divergence-heuristic value
model (health-band/success-plan/threshold triggers) returns **zero work
items** against Loopway's book — verified empirically, not assumed.
Loopway's tech-touch tail has no `SuccessPlan` rows by design (no named
CSM exists to author one — see the bible's "no named CSMs" canon), so
this sweep engine's trigger surface does not apply to this tenant's
shape. Rather than force-fit fleetops' sweep engine or silently report a
vacuous pass, `eval/loopway_week1.py` records this as an explicit SKIP
with the reason above. A future program wiring a playbook-driven
proposal path for Loopway (per `eval/tier_policy_battery.py`'s Owner
Ask #1, which already disclosed no lens/sweep consumes `playbooks.json`
motions yet) would need its own recurrence-suppression test, not an
extension of this one.
