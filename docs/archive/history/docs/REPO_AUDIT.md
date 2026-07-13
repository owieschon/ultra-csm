# Ultra CSM Repo Audit

Status: working reference for future implementation work.

This document is not a replacement for the product docs. It is a developer map
of how this repository is actually shaped today, which parts appear active, and
which practices are strong enough that new work should follow them instead of
inventing a parallel approach.

## Executive Summary

Ultra CSM is an eval-first Python application with a static Next.js operations
surface layered on top. The active architecture is:

```text
CustomerDataPlane
  -> deterministic CustomerValueModel
  -> thin Agent 1 lens/policy
  -> ActionGate proposal/verdict state machine
  -> optional committers / UI / MCP / API surfaces
```

The repo is opinionated in a few important ways:

- Deterministic logic owns scoring, priority, routing, tenant isolation, and
  approval posture.
- LLM work is intentionally narrow: mostly Slot B reason/draft generation, with
  strict contract validation around it.
- Customer-affecting side effects are always proposals first, not direct writes.
- Offline fixtures and eval batteries are first-class product assets, not test
  scaffolding.
- The frontend is a thin operator surface over the FastAPI API, and the hosted
  demo is a static export backed by committed JSON fixtures.

If a future change fights those shapes, it is probably diverging from the repo.

## What Looks Authoritative

When orienting yourself, trust these first:

- `README.md`: current product posture and proof table.
- `docs/ARCHITECTURE.md`: current high-level spine.
- `docs/CUSTOMER_VALUE_MODEL.md`: the most important architectural decision in
  the repo, namely one shared value model plus thin lenses.
- `docs/DATA_PLANE.md`: integration-first contract boundary.
- `docs/DECISION_LOG.md`: append-only record of non-obvious decisions and live
  evidence updates.
- `Makefile`: the most reliable index of supported workflows, demos, and eval
  lanes.

The repo also has a large number of program reports under `docs/`. Those matter
because this project treats proof artifacts as part of the product story.

## Repo Shape

At a high level:

- `src/ultra_csm/`: main Python application and domain logic.
- `tests/`: pytest suite for API, governance, data plane, eval rules, and
  batteries.
- `eval/`: executable scoring, regression, judge, and battery scripts.
- `ui/`: Next.js 16 static-export operations surface.
- `migrations/`: SQL schema, RLS, provenance, governance, and audit tables.
- `config/`: deterministic policy/config JSON.
- `knowledge/`: curated org/product voice, playbooks, and exemplar content.
- `scripts/`: doctor, hygiene, export, oversight, and operating scripts.
- `docs/`: proof, architecture, limits, deployment, and decision history.

A useful mental model is that this repo has three equal-weight artifacts:

1. Product code in `src/`.
2. Proof and regression code in `tests/` and `eval/`.
3. Claims and operating receipts in `docs/`.

## Active Backend Architecture

### 1. Data plane first

The backend is built around explicit contracts in
`src/ultra_csm/data_plane/contracts.py`.

Patterns worth preserving:

- Integration schemas are defined before agent behavior.
- Connectors are tenant-scoped by construction.
- Identity resolution preserves `0/1/many`; ambiguous account resolution does
  not auto-pick.
- `EvidenceRef` is shared across layers so scoring, drafts, and proofs point to
  the same fact shape.
- Raw telemetry stays distinct from CS-platform rollups even when the latter
  summarizes it.

The `data_plane` package is not small utility code. It is a major product seam
containing:

- fixture connectors and synthetic tenants,
- live connector adapters,
- schema/source-map tooling,
- onboarding/Rocketlane paths,
- comms ingestion helpers,
- readiness and explorer tooling.

When adding a new source, start here instead of threading raw payloads through
agent code.

### 2. Deterministic value model is the center of gravity

`src/ultra_csm/value_model.py` is the core of the current architecture.

Important conventions:

- The value model is deterministic and config-driven.
- Thresholds come from `config/value_model_config.json`, not hard-coded prompt
  logic.
- Priority factors are structured objects with evidence, config version, rule
  name, and threshold metadata.
- Missing evidence degrades to honest unknown states; it does not synthesize
  risk.
- Lens projections sit on top of the shared model instead of recalculating
  health independently.

This is the repo's strongest anti-reinvention pattern: compute shared health
once, then project it through policies.

### 3. Agent 1 is a thin policy layer, not a parallel scoring system

The active agent surface lives under `src/ultra_csm/agent1/`.

The main roles are:

- `time_to_value.py`: assembles evidence and decides whether outreach is even
  allowed.
- `sweep.py`: builds the work queue across accounts.
- `slot_b.py`: turns deterministic findings into a human-readable reason and
  optional draft.
- `slot_a.py`, `precedence.py`, `lens_*`, `revise.py`: additive routing,
  classification, and bounded revision layers.

Patterns worth copying:

- Agent code consumes the value model and data plane; it should not define a
  second scoring ontology.
- Disposition, priority, contact permissibility, and governance posture are
  determined before any LLM text generation.
- Slot B is isolated behind typed request/output contracts and validators.
- Fixture writers exist for deterministic offline verification.

### 4. Governance is a hard boundary, not a UI convention

The strongest safety seam is `src/ultra_csm/governance/`.

`gate.py` and related modules establish:

- proposal-first customer actions,
- approve/deny/revise verdicts,
- payload hashing for anti-TOCTOU protection,
- separation between human verdicts and executable authority,
- fail-closed handling for unknown actions and unsafe approval paths.

This is reinforced at the database level through migrations, RLS, and gate
checks. Do not bypass it with convenience write paths.

### 5. Platform/database layer is deliberate and security-heavy

`src/ultra_csm/platform/` contains more than bootstrapping. It defines:

- migrations,
- transaction/session identity propagation,
- guarded persistent runtime database connection,
- seed behavior,
- ephemeral Postgres support for tests/eval.

`platform/db.py::session()` is especially important. It is the single seam that
stamps identity into Postgres transaction-local settings for both RLS and
provenance triggers. New DB code should flow through that seam instead of
opening ad hoc cursors.

## Serving Surfaces

### FastAPI API

`src/ultra_csm/api.py` is the primary served app surface.

Notable traits:

- boots either an ephemeral cluster or a configured persistent runtime DB,
- seeds deterministic state,
- exposes account, sweep, proposal, comms, ledger, and reconciliation paths,
- mounts the built static UI for same-origin demo/prod serving,
- carries auth/demo-mode branching explicitly.

This file is large because it is an assembly surface. Favor pushing reusable
logic down into modules rather than adding more endpoint-local business rules.

### MCP server

`src/ultra_csm/mcp_server.py` is not a toy adapter. It is a second serious
surface over the same core system with its own access modes:

- operator,
- demo operator,
- read-only.

It reuses the same data plane, value model, governance, and draft logic. If a
feature belongs in both API and MCP, prefer shared helpers instead of copy/paste
behavior.

### Next.js operations surface

`ui/` is a thin operator shell, not a second backend.

Important facts:

- Next.js 16 with React 19.
- `next.config.mjs` uses `output: "export"` and `basePath: "/ui"`.
- `ui/lib/api.ts` is a typed fetch wrapper over FastAPI.
- In dev, Next talks to `localhost:8000`.
- In demo/prod, FastAPI serves the static export same-origin.
- Hosted demo mode swaps live API requests for committed fixture JSON under
  `ui/public/demo-api/`.

The UI follows a deliberate visual system defined centrally in
`ui/app/globals.css`. Components mostly consume API state and render operator
workflows; they do not own core business rules.

## Config And Knowledge Model

This repo externalizes more policy than many codebases. That is intentional.

### Config JSON

Current active config files:

- `config/value_model_config.json`
- `config/precedence_config.json`
- `config/trigger_config.json`
- `config/autonomy_policy.json`

Use these when a change is truly policy/config. Do not hard-code adjustable
thresholds or precedence rules in agent code if the repo already models them as
config.

### Knowledge artifacts

`knowledge/` is curated product/org content, not generic prompt stuffing.

Examples:

- org pack voice and terminology,
- playbooks,
- exemplar corpora,
- escalation field notes.

This content shapes safe asks, booking links, phrasing, and gap plays. When
changing customer-facing tone or recommended motions, check `knowledge/` before
editing prompt logic.

## Database And Safety Posture

The SQL migrations tell a clear story:

- schema first,
- then RLS,
- then provenance,
- then governance,
- then human-ness gate checks,
- then comms/source mapping,
- then safety backstops,
- then audit logging.

The active database design is not generic CRUD storage. It is a controlled audit
system where identity, tenant scope, and approval state are part of the product.

Practical implication:

- If a feature touches writes, approvals, or customer-facing actions, read the
  migrations and governance modules first.

## Testing, Eval, And Proof Practices

This repo is unusually heavy on evaluation, and that is part of the intended
architecture.

Current tracked scale at audit time:

- about 134 Python source files under `src/`
- about 119 pytest files under `tests/`
- about 86 Python eval scripts under `eval/`
- about 129 markdown docs under `docs/`

Practices that appear foundational:

- fixture-first offline verification,
- eval batteries for specific capabilities and failure classes,
- distinction between CI-safe offline lanes and credential-gated live lanes,
- explicit proof artifacts checked into the repo when they underpin claims,
- deterministic fixture writers and falsifier paths for unsafe LLM behavior,
- separate drift-power and judge-validation discipline.

The Makefile is the clearest expression of this culture:

- `make doctor`
- `make scorecard-csm`
- `make eval`
- `make lint`
- `make hygiene`
- many named batteries and demo lanes

When adding product behavior, expect to add or update:

- a pytest,
- possibly an eval battery or scorecard check,
- sometimes a docs/program report or decision-log note if the claim surface
  changes.

## Strong Working Conventions

These patterns repeat enough that they should be treated as repo norms.

### Compute once, project many

Do not create separate health models for separate lenses if the shared value
model can express the underlying signal.

### Positive evidence only

Unknowns remain unknown. Missing data should not quietly become a risk signal.

### Proposal before side effect

Customer-facing or state-mutating actions go through the action gate.

### Config and content over magic constants

Thresholds, precedence, org voice, and approved asks are frequently externalized
into JSON or knowledge artifacts.

### Fixture and live paths are both first-class

New logic should usually have:

- an offline deterministic path for tests/evals,
- a clearly bounded live path if needed,
- honest claim boundaries between them.

### Proof matters as much as implementation

Docs and eval artifacts are treated as evidence, not marketing copy. Changes to
claims should be traceable.

## Where To Put New Work

Use this as a quick routing guide.

- New source/connector contract or fixture: `src/ultra_csm/data_plane/`
- New deterministic health factor or threshold logic: `src/ultra_csm/value_model.py`
  plus `config/value_model_config.json`
- New Time-to-Value or lens behavior: `src/ultra_csm/agent1/`
- New approval/write safety rule: `src/ultra_csm/governance/` and possibly
  `migrations/`
- New served endpoint: `src/ultra_csm/api.py` with helper extraction if logic is
  reusable
- New MCP capability: `src/ultra_csm/mcp_server.py` plus shared lower-layer code
- New operator UI behavior: `ui/components/`, `ui/lib/`, and minimal page wiring
- New org tone/playbook/customer ask: `knowledge/`
- New policy/threshold/precedence change: `config/`
- New regression or proof: `tests/`, `eval/`, and possibly `docs/DECISION_LOG.md`

## Things Not To Mistake For Architecture

These can easily mislead a new contributor:

- Ignored/generated directories like `.venv/`, `.next/`, `build/`,
  `demo_state/`, and `__pycache__/`.
- Local empty package directories under `src/ultra_csm/*` that contain only
  ignored cache residue. They are not authoritative module boundaries; trust
  `git ls-files` and tracked source files instead.
- Historical reports in `docs/archive/` that may describe superseded shapes.
- Live-judge or environment-specific outputs that are intentionally ignored by
  `.gitignore`.

## Likely Change Risks

The easiest ways to diverge from the repo are:

- adding prompt logic where deterministic code/config already exists,
- bypassing the action gate for convenience,
- mixing live connector assumptions into offline fixture paths,
- putting adjustable policy in code instead of `config/` or `knowledge/`,
- changing product claims without updating the evidence trail,
- treating the UI as the source of truth instead of the API/core model,
- creating a new scoring stack per feature instead of extending the value model.

## Practical Workflow For Future Work

When starting a non-trivial change:

1. Read `README.md`, `docs/ARCHITECTURE.md`, and the relevant focused doc.
2. Check `Makefile` for an existing lane before inventing a new script.
3. Find the existing deterministic seam first: data plane, value model, lens,
   governance, or UI.
4. Reuse config or knowledge artifacts if the change is policy/content-shaped.
5. Add proof at the same altitude as the change: test, eval, docs, or decision
   log.
6. Keep live and offline claims separated.

## Bottom Line

Ultra CSM is not organized as "an AI app with some tests around it." It is
organized as a deterministic CSM operating core with narrow LLM slots, strong
governance, explicit evidence contracts, and a heavy proof harness. Future work
should extend that spine, not route around it.
