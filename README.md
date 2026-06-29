# Ultra CSM

**What it is.** An eval-first proof-of-craft for applying AI to Customer Success: a
deterministic Customer Value Model (the spine) plus a harness that treats the LLM as a
*measured instrument*, not an oracle. It exists to demonstrate the hard parts of putting an
agent near real customers — eval frameworks for non-deterministic AI, fail-closed safety, and
honest claim boundaries — not to be a finished product.

One spine: `CustomerDataPlane → value_model → ActionGate → Agent 1 (Slot B)`. The current agent
is a Time-to-Value accelerator: it reads CRM / CS-platform / product-telemetry data, computes a
customer value model, projects a TTV priority lens, and emits only **gated, proposal-only** CSM
actions — it never sends or self-authorizes.

## Quickstart

**Prerequisites:** Python 3.10+ and PostgreSQL 16 client tooling (`initdb`, `pg_ctl`) on `PATH`.
- macOS: `brew install postgresql@16`, then add `"$(brew --prefix postgresql@16)/bin"` to `PATH`.
- Ubuntu: `sudo apt-get install -y postgresql-16`.

```sh
make setup          # venv + editable install
make scorecard-csm  # offline, no secrets → the 23/23 deterministic CSM scorecard
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

## Where it stands (honest status)

| Area | Status |
|---|---|
| Deterministic spine | **Proven** — `23/23` scorecard, 150 tests on real Postgres, hard security gates green |
| LLM quality judge | **Characterized & stabilized**, not yet human-validated (noise measured, gate N-run-stabilized; human labels are the next gate) |
| Connectors (Salesforce/Gainsight/Rocketlane/Attio) | **Built to the credential boundary**, fixture-tested; not yet run against a live tenant |
| Data | Curated **fixtures**, not production customer data |
| Outcome rail, Risk & Expansion lenses | **Designed, not built** |

Nothing here claims production retention or expansion lift. It demonstrates judgment,
architecture, and measurement discipline — `docs/DECISION_LOG.md` records what is and is not claimed.

## Roadmap (next milestones, in order)

1. **Human-validate the judge** — blind human labels on the hard gold layer plus a second
   independent labeler to establish the human-agreement ceiling, then report judge-vs-human.
2. **Drift-power experiment** — show the judge's residual noise floor is below the generation
   drift it must detect, or scope the "detects quality drift" claim down to what's provable.
3. **One live vertical, end-to-end** — run a real connector (Attio/Salesforce), close the loop on
   live data with monitoring and rollback.
4. **Risk & Expansion lenses** — the two value lenses that move NRR, on the same value model.

The working plan lives in `docs/NEXT_DISPATCH.md`.

## Docs

- **Architecture & data:** `docs/ARCHITECTURE.md`, `docs/CUSTOMER_VALUE_MODEL.md`, `docs/DATA_PLANE.md`
- **Eval & judge:** `docs/DECISION_LOG.md`, `docs/QUALITY_REGRESSION_EVAL_SPEC.md`, `docs/NONDETERMINISM_EVAL_HARDENING_SPEC.md`, `docs/QUALITY_LABELING_PROTOCOL.md`
- **Ops & security:** `docs/OBSERVABILITY.md`, `docs/SECURITY.md`
- **Connectors & roadmap:** `docs/ROCKETLANE_ONBOARDING_CONNECTOR_SPEC.md`, `docs/NEXT_DISPATCH.md`
