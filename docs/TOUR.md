# Ultra CSM tour

Use this tour to move from the fixture-backed interface to the implementation and its
negative tests without detouring through build reports.

## 1. Inspect the operations surface

Open the [hosted read-only demo](https://ultra-csm.vercel.app/) or build it locally:

```sh
make setup
make hosted-readonly-demo
ULTRA_CSM_DEMO_NOAUTH=1 ULTRA_CSM_BIND_HOST=127.0.0.1 PYTHONPATH=src:. \
  .venv/bin/python -m uvicorn ultra_csm.api:app --host 127.0.0.1 --port 8000
```

Follow [`DEMO.md`](DEMO.md). The UI separates deterministic priority, a labeled fixture
draft, the pending proposal, and the disabled decision boundary.

## 2. Trace one action through code

Read the four files in [`READING_PATH.md`](READING_PATH.md). They show evidence assembly,
bounded drafting, proposal creation, a verdict from the configured identity, hash
verification, simulated commit,
and the attacks against that sequence.

## 3. Run the local proof

```sh
make doctor
make scorecard-csm-check
make eval
make lint hygiene
```

These gates need no customer data or cloud credentials. The scorecard checks the
committed 24-case artifact; the test suite boots a temporary PostgreSQL 16 cluster.

## 4. Choose an integration boundary

- [`MCP_MODES.md`](MCP_MODES.md) separates MCP access flags, data-plane selection,
  governed native tools, and host-relayed books.
- [`CONNECTORS.md`](CONNECTORS.md) separates request-shape dry runs, simulated onboarding,
  and tenant-specific live readiness.
- [`LIMITS.md`](LIMITS.md) states the evidence still missing for live sends, monitoring,
  judge validation, and production outcomes.

Program reports record how individual slices were built. They are provenance, not the
current path through the system.
