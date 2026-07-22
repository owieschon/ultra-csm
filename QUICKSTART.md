# Quickstart

Use this path to install Ultra CSM, verify the local runtime, run the deterministic
proof, and open the fixture-backed operations UI.

## Before you begin

You need:

- Python 3.10 or later;
- PostgreSQL 16 tools, including `initdb` and `pg_ctl`;
- Node 20 and npm for the UI build.

No cloud credentials or customer data are required. Start from the repository root:

```sh
make setup
make doctor
```

`make doctor` verifies the Python environment and boots a throwaway UTF-8 PostgreSQL
cluster. A failed check prints the missing prerequisite and its fix.

## Run the proof

```sh
make scorecard-csm-check
make eval
```

The scorecard command checks the committed 24-case artifact without rewriting it.
`make eval` runs the offline test suite, the scoped quality-gold checks, and the
knowability audit. Both use fixtures and local PostgreSQL.

## Build the static UI and run the local API

```sh
make hosted-readonly-demo
ULTRA_CSM_DEMO_NOAUTH=1 ULTRA_CSM_BIND_HOST=127.0.0.1 PYTHONPATH=src:. \
  .venv/bin/python -m uvicorn ultra_csm.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/ui/`, then follow the
[demo walkthrough](docs/DEMO.md). `make hosted-readonly-demo` builds the static export and checks
its committed fixture bytes; that export contains no write routes. The next command co-hosts it on
the full FastAPI application. `ULTRA_CSM_DEMO_NOAUTH=1` removes authentication only for this
loopback process and does not remove the application's mutation routes. The local API can change
synthetic local state, so keep it on loopback and stop it after the walkthrough.

## Inspect the synthetic book from the terminal

```sh
PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli demo-book --json
PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli demo-sweep --day 60 --deep --json
```

The first command lists the fixture book. The second computes the value model, priority,
and proposed actions for one simulated day.

## Continue by task

| Your next job | Read |
| --- | --- |
| Choose MCP access, data-source, and relay boundaries | [`docs/MCP_MODES.md`](docs/MCP_MODES.md) |
| Exercise connector discovery and mapping | [`docs/CONNECTORS.md`](docs/CONNECTORS.md) |
| Understand the input-to-receipt code path | [`docs/READING_PATH.md`](docs/READING_PATH.md) |
| Inspect boundaries before enabling credentials | [`docs/LIMITS.md`](docs/LIMITS.md) and [`SECURITY.md`](SECURITY.md) |
| Run credentialed or metered maintainer lanes | [`docs/OPERATOR_RUNBOOK.md`](docs/OPERATOR_RUNBOOK.md) |

`make demo` is a maintainer regeneration target. It rewrites several committed evidence
artifacts, so it is not part of this read-only quickstart.

## Bring your own book

For the host-relay workflow returned by `get_next_steps`, continue with
[`docs/MCP_MODES.md#run-the-governed-default-runtime`](docs/MCP_MODES.md#run-the-governed-default-runtime).
