# Quickstart

Start from a fresh clone of this repository, then run the local fixture/sim path from
the repo root. No live tenant credentials are required for this path.

## Set Up

```sh
make setup
make doctor
```

`make doctor` is a preflight that verifies Python, the Postgres 16 tooling, and —
the real proof — that a throwaway UTF-8 cluster boots and tears down on your
machine. Every FAIL line names its exact fix. If doctor passes, everything below
will run.

## Run The Offline Demo Gates

```sh
make demo
```

This runs the deterministic CSM scorecard and offline regression. It proves fixture/sim
behavior only. It also regenerates the Slot A scorecard, earned-autonomy report, the
Attio/Gainsight/product-telemetry simulated onboarding artifacts, and the read-only MCP
transcript.

## Inspect The Synthetic Book

```sh
PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli demo-book --json
```

```sh
PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli demo-sweep --day 60 --deep --json
```

## Exercise Connector Readiness Without Network Calls

```sh
ULTRA_CSM_ROCKETLANE_API_KEY=dummy \
  PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli connectors smoke rocketlane_onboarding --dry-run
```

```sh
ULTRA_CSM_ATTIO_ACCESS_TOKEN=dummy \
  PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli connectors explore attio_crm --dry-run
```

Dry-run connector commands verify configured request shapes only. Replace the dummy env
vars with real connector credentials and omit `--dry-run` when you are ready to test your
own tenant; the repository does not claim live-tenant proof.

The local Attio-, Gainsight-, and product-telemetry-shaped onboarding paths can also be
exercised without live credentials against the simulated customer book:

```sh
make attio-simulated-onboarding-csm
make gainsight-simulated-onboarding-csm
make product-telemetry-simulated-onboarding-csm
```

Each writes an artifact (`eval/attio_simulated_onboarding.json`,
`eval/gainsight_simulated_onboarding.json`,
`eval/product_telemetry_simulated_onboarding.json`) that freezes the confirmed mapping
over fixture data while preserving the live-credential boundary. The three connectors
degrade differently and honestly: Attio maps nearly everything with one unknown field;
Gainsight resolves Company/CTA/SuccessPlan but reports HealthScore and AdoptionSummary as
unknown because its metadata-describe surface doesn't expose a matching object for either
without tenant-specific Scorecard/Adoption Explorer configuration; product telemetry
resolves identity/join fields from OTel resource attributes but reports per-datapoint
value fields as unknown, since those live in the metric payload itself and need a live
sample capture, not just attribute introspection.

## Render Current Status

```sh
PYTHONPATH=src:. .venv/bin/python scripts/render_status.py
```

`STATUS.md` is generated from local artifacts. If it reports a missing readiness artifact,
that means no live source-readiness run has been captured in this checkout.

## Source Mapping Confirmation

Schema exploration already produces a mapping proposal. Deterministic standard fields map
automatically; ambiguous custom fields and value-direction fields must be confirmed before
they can become frozen runtime config. Confirmed mappings are frozen with:

```sh
PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli connectors confirm \
  proposal.json confirmations.json --output config/source-map.json
```

The fail-closed loader and command path are covered by:

```sh
PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_connector_explorer.py -q
```

## Talk To The Book In Read-Only Mode

Use MCP as a conversational shell over read-only tools. Multi-turn memory and wording live
in the host; this process only exposes deterministic reads when read-only mode is enabled.

The one-command path — register it with Claude Code from the repo root and start asking
questions ("Which accounts are most at risk and why?", "What's holding the Sagebrush
expansion action?"):

```sh
claude mcp add ultra-csm --env ULTRA_CSM_MCP_READONLY=1 -- \
  "$(pwd)/.venv/bin/python" -m ultra_csm.mcp_server
```

Or run the stdio server directly for any other MCP host:

```sh
ULTRA_CSM_MCP_READONLY=1 \
  PYTHONPATH=src:. .venv/bin/python -m ultra_csm.mcp_server
```

The read-only mode refuses sweep and verdict tools. Capture the fixture transcript with:

```sh
make mcp-readonly-demo-csm
```

The transcript is written to `demo_state/mcp_readonly_transcript.json` and maps each demo
answer to the tool calls that grounded it.

## Oversight evidence pack

Render the oversight ledgers (verdicts, receipts, suppressions, breaker events,
quality state, autonomy provenance) into one evidence artifact:

```sh
make oversight-report
```

Outputs `demo_state/oversight_report.json` and `demo_state/oversight_report.md`.
Every claim carries its ledger row refs; evidence classes with no persisted
source are listed under "Not instrumented" instead of being implied. It is an
evidence record, not a compliance assessment.
