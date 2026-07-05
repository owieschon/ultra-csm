# Ultra CSM

**What a morning with it looks like.** One real work item from a live daily run over a 181-account
book (story day 51, `docs/PROGRAM_REPORT_21.md`): Ironhorse Freight Co, deterministic Time-to-Value
score 143 (`milestones_overdue=50`, `days_overdue=40`, `success_plan_overdue=20`), motion
`working_session`, evidence cited to real telemetry/CS-platform sources. That same run resolved 12
work items across 5 distinct motions (`working_session`, `campaign_enroll`, `content_route`,
`personal_email`, `cohort_action`) and ran the validated quality judge over 3 drafts for $0.231
against a $2.00 cap, all `pass=true` — not a mocked demo path, the actual `ucsm tick` sweep. This is
the account triage a CSM opens with: green-but-quiet accounts, stalling onboardings, and
single-threaded relationships surfaced with cited evidence and a drafted next move — not a
health-score dashboard.

**Why you can trust the claim at this scale.** `docs/DEPLOYMENT_READINESS.md` (rendered, never
hand-edited, from committed battery artifacts) is the evidence a skeptical buyer would ask for
first: agents tested from cold start across **four distributionally distinct tenants** (fleetops
180 accounts / fieldstone 12 / crateworks 10 / loopway 400) spanning enterprise-touch to
self-serve scale, over four different vendor-CRM shapes (Salesforce-shaped, HubSpot-shaped, flat
CSV, Attio-shaped), with measured onboarding cost (3-6 questions per tenant, no monotonic
relationship to account count), adversarial-content safety with cross-account canaries, tier-
appropriate action economics, and drift resilience — all batteries `hard_ok: true`, zero ad-hoc
per-tenant rules in code (every tenant resolves through the same `resolve_tenant_tier` +
`load_playbooks` pair). Two of those four tenants — Salesforce and Rocketlane — onboard live: real
read-only CRM fetch and a real, create-only write-back against a seeded corpus B account
(`docs/PROGRAM_REPORT_6.md`), plus real Rocketlane onboarding-phase evidence lighting up the
Time-to-Value rail end-to-end.

**The differentiator: a validated judge, not an impression.** The Slot B drafts the agent proposes
are scored by an LLM judge that was itself measured against human-labeled gold data before being
trusted, and the choice of instrument was revised twice on evidence, not picked once and assumed
final: a single-run comparison first favored Sonnet-terse for stability, but a 5-run modal
aggregation study then found terse@5 fails the hard adversarial layer even after aggregation
(`on_task_relevance` κ 0.479, 3 aggregated false negatives) while `cot@5` clears all six dimensions
(κ ≥ 0.661, zero aggregated false negatives) — so the validated gate judge today is Sonnet 4.6 with
chain-of-thought reasoning, under 5-run aggregation, exactly because that is the arm the
adversarial gold data says is trustworthy, not the one that looked best on a smaller sample
(`docs/DECISION_LOG.md`). The doc also states the judge's own rare, honest disagreement rather than
forcing it to zero — one boundary case (H6b, warm-but-generic drafts) draws 4 accepted hard false
positives, recorded as a defensible disagreement, not chased away with a rubric rewrite. Every draft
stays propose-only — a human approves before anything reaches a customer.

**The receipts.** `docs/LIVE_INTEGRATION_FINDINGS.md` and `docs/PROGRAM_REPORT_6.md` are the live
runs against real Salesforce/Rocketlane orgs; `eval/gold/live_semantic_quality.json` is the judged
output; `eval/scorecard_csm.json` and the regression batteries are the deterministic proof the
spine holds; `docs/DEPLOYMENT_READINESS.md` is the four-tenant table above, rendered not hand-set.
Every artifact here carries a `claim_boundary` — what it does and does not prove — because the
mechanics of *how* this works (a deterministic value model, a proposal-only action gate, a
validated LLM judge) are the objection-handler, not the pitch.

*What this does NOT yet claim:* one verified manual run of the daily operating job proves the
mechanism works end to end for one real day (`docs/OPERATING_PROOF.md`); it does not yet prove
unattended operation across weeks — the standing schedule is built and validated but intentionally
not started, pending the owner's own go-ahead.

One spine: `CustomerDataPlane → value_model → ActionGate → Agent 1 (Slot B)`. The current agent
is a Time-to-Value accelerator: it reads CRM / CS-platform / product-telemetry data, computes a
customer value model, projects a TTV priority lens, and emits only **gated, proposal-only** CSM
actions — it never sends or self-authorizes.
<!-- TRIPWIRE (Demo Slice 3): when the sim closed-loop lands with tier-1 auto-execution, the
     sentence above must change to the graduated-autonomy framing: "acts autonomously exactly as
     far as policy allows; customer-facing actions remain human-gated." Do not let it survive
     Slice 3 as an understatement-turned-inaccuracy. -->


## Architecture: one model, three lenses, one analyst

The naive design is four independent agents, each re-deriving account health. That duplicates the
hard part and fights over boundaries — an account can be a *risk* and an *expansion* case at once.
Instead:

- **One deterministic Customer Value Model** computes account health *once* — four rails (usage,
  penetration, feature-depth, outcome) plus a cross-rail divergence layer. The LLM computes none of
  the health; it only narrates the reason and drafts outreach in two slots.
- **Agents 1–3 are thin lenses** — policies that *project* that one model at different lifecycle
  states, each with its own action and gate. Priority is the model viewed through a lens, not a
  re-derivation.
  - **Agent 1 — Time-to-Value** *(built)*: onboarding/activation stalls → next-best action to first value.
  - **Agent 2 — Risk / Retention** *(deterministic lens built)*: steady-state fragility (single-threaded champion, missing sponsor), renewal proximity.
  - **Agent 3 — Expansion** *(deterministic lens built)*: unrealized value in healthy accounts — low penetration, unused entitlements.
- **Agent 4 — Cohort / Program analyst** *(roadmap)*: population-level, not per-account. Finds
  segment patterns (e.g. "onboarding path Y predicts churn"), feeds the CS manager and Product, and
  *reduces the symptom load* lenses 1–3 chase — Agent 1's outcomes become Agent 4's labels. A flywheel.

Because they're lenses over *one* model, a single account can be in view of several at once without
conflict (a single-threaded account is simultaneously Agent 2's risk and Agent 3's expansion target —
same model fact, two actions). Every customer-facing action from any lens routes through the same
gate: **proposal → human verdict → committer.** The CSM is the actor; the agents triage and draft,
the human decides. Today the shared model, the gate, Agent 1, and the deterministic Risk/Expansion
lenses are built; the cohort analyst and quality-scored lens drafts stay gated. Full spec:
`docs/CUSTOMER_VALUE_MODEL.md`.

## Try it in one minute — no Postgres, no credentials

The read-only conversational surface needs nothing but Python: no database, no system
Postgres install, no `make setup`.

```sh
git clone https://github.com/owieschon/ultra-csm.git && cd ultra-csm
python3 -m venv .venv && .venv/bin/pip install -q -e ".[mcp]"
claude mcp add ultra-csm --env ULTRA_CSM_MCP_READONLY=1 -- \
  "$(pwd)/.venv/bin/python" -m ultra_csm.mcp_server
```

Then, in Claude Code, ask: *"Which accounts are most at risk, and what evidence says
so?"* — answers are grounded in the same deterministic value-model tools the agent
uses over a simulated 35-account book; write tools return a typed refusal enforced in
the server process, not left to the model's judgment. `docs/TOUR.md` has more prompts
and a ten-minute walk through the rest of the system.

## Bring your own book through an MCP host

The relay path is for hosts that already have the user's tools connected. Ultra CSM
does not introspect those tools or own their credentials; the host declares what it can
relay, then passes raw records into the deterministic mapping and scoring boundary.

1. `report_readiness(["crm", "email", "telemetry"])` returns a checklist: CRM is the
   minimum viable book, email enables host-placed drafts, and telemetry fills usage
   rails. With no sources, it routes back to the sim morning.
2. `ingest_book(records, source_descriptor, expected_count)` accumulates chunks,
   requires a loud expected count, records the raw inputs in the MCP session, and
   returns sparsity-evidenced mapping questions.
3. `confirm_book_mappings(confirmations)` accepts `mapped` or `not_mappable`, freezes
   the map, transforms the book, runs the existing value-model read path, and returns
   coverage plus a briefing.

Relay responses carry `provenance: mcp_relay`, `unverified_mapping: true`, `sim:
false`, and `live: false`. Drafts are propose-only data for the host to place in the
user's own tools; Ultra CSM does not send email or write external systems from relay
books.

## Full quickstart (tests, scorecard, connectors)

**Prerequisites:** Python 3.10+ and PostgreSQL 16 client tooling (`initdb`, `pg_ctl`) on `PATH`
— only needed past this point (the spine's regression tests use a real, ephemeral, auto-torn-down
Postgres; the MCP path above does not).
- macOS: `brew install postgresql@16`, then add `"$(brew --prefix postgresql@16)/bin"` to `PATH`.
- Ubuntu: `sudo apt-get install -y postgresql-16`.

```sh
make setup          # venv + editable install (all extras)
make doctor         # preflight: proves your environment can boot the test harness
make scorecard-csm  # offline, no secrets → deterministic CSM scorecard
make eval           # full pytest suite on an ephemeral, auto-torn-down Postgres
make lint hygiene   # ruff lint + repo-residue scan
```

No cloud, no credentials, and no customer data are needed for any of the above. The only
credentialed lanes are the live quality judge and the live connectors (see below).

## What's evaluated — and why they're kept apart

- **The deterministic spine** — exact, offline, zero-tolerance regression. Tenant isolation,
  consent gating, payload-hash binding, and no-authority-minting are enforced in code and proven
  by tests that fail if you break them.
- **The non-deterministic LLM slot** — a quality judge whose run-to-run noise is *measured before
  it is trusted*: blinded adversarial gold sets, an N-run determinism probe, fail-closed N-run
  aggregation, and evidence-based model/prompt selection (`docs/DECISION_LOG.md`).

A non-deterministic instrument must never own a deterministic gate. That boundary is the point.

## Where it stands

| Area | Status |
|---|---|
| Deterministic spine | **Proven** — scorecard hard gates green on real Postgres |
| LLM quality judge | **Validated** under N-run modal aggregation (single-labeler gold, prompt v7): clean layer all six dimensions κ ≥ 0.6 with zero gate errors; adversarial hard layer clears all six aggregated with zero false negatives. `priority_fidelity` and `account_specificity` are deterministic. The claim is derived from versioned evidence artifacts (`eval/judge_validation.py`), never hand-set; a second independent labeler remains open |
| Connectors (Salesforce/Rocketlane live; Gainsight/Attio fixture) | **Salesforce and Rocketlane proven live**: real read-only CRM fetch and a real, create-only write-back against a seeded corpus B account (`docs/PROGRAM_REPORT_6.md`); real onboarding phase/task evidence lights up the TTV rail end-to-end, including a live cross-system beat joining both. Gainsight/Attio remain fixture-tested to the credential boundary — no live org available in this environment |
| Live semantic quality | **Proven** — real Slot B drafts generated over live corpus B accounts, scored by the validated N-run judge (cot@5, prompt v7); derived (never hand-set) via `eval.judge_validation.live_semantic_quality_status` from `eval/gold/live_semantic_quality.json` |
| Data | Curated **fixtures** for the simulated book; two real live tenants for the connector/quality proof above, not production customer data |
| Outcome rail, Risk & Expansion lenses | Outcome rail live-instrumented via the Rocketlane TTV bridge, including a lifecycle-aware fix for onboarding-stage delivery-slippage-only accounts; deterministic Risk and Expansion lenses are built, with draft-quality claims gated on judge validation |
| Oversight evidence | **Rendered from ledgers** — `make oversight-report` writes `demo_state/oversight_report.{json,md}`: verdicts, payload-hash-bound receipts, suppressions, breaker events, quality state, and autonomy provenance, with an explicit "not instrumented" section. An evidence record, not a compliance certification |

Nothing here claims production retention or expansion lift. It demonstrates judgment,
architecture, and measurement discipline — `docs/DECISION_LOG.md` records what is and is not claimed.

## Roadmap (next milestones, in order)

1. **A second independent human labeler** — the judge is validated against a single labeler's
   gold set; a blind second labeler establishes the human-agreement ceiling
   (judge-vs-human1-vs-human2).
2. **Drift-power experiment** — show the judge's residual noise floor is below the generation
   drift it must detect, or scope the "detects quality drift" claim down to what's provable.
3. **Close the loop in simulation** — stateful sim tenant, graduated autonomy (tier-1 internal
   actions auto-execute; customer-facing tiers stay human-gated), committers, and outcome
   re-observation — per `docs/DEMO_EXECUTION_PLAN.md`.
4. **Gmail draft placement, live** — the offline path (draft-never-send, OAuth token refresh,
   create-only) is built and tested; live placement is gated on the owner supplying Gmail OAuth
   credentials.
5. **Risk & Expansion depth** — expand the built deterministic lenses only where the shared value model and evals support it.

The working plan lives in `docs/NEXT_DISPATCH.md`.

## Docs

- **Architecture & data:** `docs/ARCHITECTURE.md`, `docs/CUSTOMER_VALUE_MODEL.md`, `docs/DATA_PLANE.md`
- **Eval & judge:** `docs/DECISION_LOG.md`, `docs/QUALITY_REGRESSION_EVAL_SPEC.md`, `docs/NONDETERMINISM_EVAL_HARDENING_SPEC.md`, `docs/QUALITY_LABELING_PROTOCOL.md`
- **Ops & security:** `docs/OBSERVABILITY.md`, `docs/SECURITY.md`
- **Connectors & roadmap:** `docs/ROCKETLANE_ONBOARDING_CONNECTOR_SPEC.md`, `docs/NEXT_DISPATCH.md`, `docs/DEMO_EXECUTION_PLAN.md` (the binding demo plan)
- **Operating proof:** `docs/PROGRAM_REPORT_21.md`, `docs/PROGRAM_REPORT_24.md`, `docs/OPERATING_PROOF.md` (the daily-run job and the tick motions it depends on)
