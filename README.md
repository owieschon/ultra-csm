# Ultra CSM

**What it is.** An eval-first functional prototype for scaling the traditional SaaS Customer Success function with agents: a
deterministic Customer Value Model (the spine) plus a harness that treats the LLM as a
*measured instrument*, not an oracle. An evolving framework for understanding the hard parts of involving agents
in customer-facing work (eval frameworks for non-deterministic AI, fail-closed safety, and
honest claim boundaries), not a finished product.

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
| Connectors (Salesforce/Gainsight/Rocketlane/Attio) | **Built to the credential boundary**, fixture-tested; not yet run against a live tenant |
| Data | Curated **fixtures**, not production customer data |
| Outcome rail, Risk & Expansion lenses | Outcome rail partially instrumented; deterministic Risk and Expansion lenses are built, with draft-quality claims gated on judge validation |
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
4. **Live verticals, end-to-end** *(credential-gated, post-demo)* — run real connectors
   (Rocketlane, Gainsight, OTel, Attio/Salesforce) against a live tenant, with monitoring and rollback.
5. **Risk & Expansion depth** — expand the built deterministic lenses only where the shared value model and evals support it.

The working plan lives in `docs/NEXT_DISPATCH.md`.

## Docs

- **Architecture & data:** `docs/ARCHITECTURE.md`, `docs/CUSTOMER_VALUE_MODEL.md`, `docs/DATA_PLANE.md`
- **Eval & judge:** `docs/DECISION_LOG.md`, `docs/QUALITY_REGRESSION_EVAL_SPEC.md`, `docs/NONDETERMINISM_EVAL_HARDENING_SPEC.md`, `docs/QUALITY_LABELING_PROTOCOL.md`
- **Ops & security:** `docs/OBSERVABILITY.md`, `docs/SECURITY.md`
- **Connectors & roadmap:** `docs/ROCKETLANE_ONBOARDING_CONNECTOR_SPEC.md`, `docs/NEXT_DISPATCH.md`, `docs/DEMO_EXECUTION_PLAN.md` (the binding demo plan)
