# Quickstart

<!-- clean-docs:purpose -->
Start from a fresh clone of this repository, then run the local fixture/sim path from
the repo root. No live tenant credentials are required for this path.
<!-- clean-docs:end purpose -->
<!-- clean-docs:allow doc-length reason="The offline setup and connector-readiness path is one runnable onboarding task" -->
<!-- clean-docs:allow section-length reason="The connector-readiness exercise is one ordered verification sequence" -->

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
<!-- clean-docs:allow section-length reason="The Exercise Connector Readiness Without Network Calls reference keeps its ordered evidence and constraints together" -->

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
make salesforce-simulated-onboarding-csm
```

Each writes an artifact (`eval/attio_simulated_onboarding.json`,
`eval/gainsight_simulated_onboarding.json`,
`eval/product_telemetry_simulated_onboarding.json`, and
`eval/salesforce_simulated_onboarding.json`) that freezes the confirmed mapping
over fixture data while preserving the live-credential boundary. The three connectors
degrade differently and honestly: Attio maps nearly everything with one unknown field;
Gainsight resolves Company/CTA/SuccessPlan but reports HealthScore and AdoptionSummary as
unknown because its metadata-describe surface doesn't expose a matching object for either
without tenant-specific Scorecard/Adoption Explorer configuration; product telemetry
resolves identity/join fields from OTel resource attributes but reports per-datapoint
value fields as unknown, since those live in the metric payload itself and need a live
sample capture, not just attribute introspection. Salesforce proves the read-only
Describe -> source-map proposal -> confirmation -> freeze -> bounded SOQL pagination ->
typed CRM contract path over a fake transport; live tenant proof still requires
Salesforce credentials.

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
Read-only mode never boots Postgres — no database, no `initdb`/`pg_ctl`, no `make setup`
even: `python3 -m venv .venv && .venv/bin/pip install -e ".[mcp]"` is enough (list_proposals
is the only read-only tool that would otherwise touch the DB, and it always sees zero rows
in read-only mode since nothing but run_sweep — disabled here — ever writes a proposal).

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

## Run The Sim Operator Morning

Use MCP as a local operator demo over the same approval gate and simulated outbox:

```sh
ULTRA_CSM_DEMO_OPERATOR=1 \
  PYTHONPATH=src:. .venv/bin/python -m ultra_csm.mcp_server
```

In this mode, start with `get_morning_briefing`, inspect `list_proposals`, revise a draft
with `submit_verdict(..., verdict="revise", edit_instruction="Make this more concise.")`,
then approve the superseding proposal. Approved customer outreach writes only to
`demo_state/mcp_operator/outbox.jsonl`; no live email is sent. The mode also refuses
no-consent outreach and held expansion actions with typed errors.
After approval, `render_email_draft` returns a placement-ready artifact with
`draft_never_send: true`, the approved `payload_sha256`, and explicit host placement
instructions. It creates no live email by itself.

Capture the deterministic transcript with:

```sh
make mcp-operator-demo-csm
```

The committed transcript is written to `eval/mcp_operator_transcript.json`.

## Bring Your Own Book

When your MCP host already has CRM, email, or telemetry tools connected, run the relay
path without `ULTRA_CSM_MCP_READONLY` and without `ULTRA_CSM_DEMO_OPERATOR`.

1. Call `report_readiness(["crm", "email", "telemetry"])`. The server cannot inspect
   host tools, so this is a host declaration. CRM is the minimum viable book; email
   enables host-placed drafts; telemetry fills usage/adoption rails. If nothing is
   connected, the response routes back to the sim morning.
2. Call `ingest_book(records, source_descriptor, expected_count)`. `expected_count` is
   required. Large books can be chunked with the same `session_id`; count mismatch is a
   refusal, and oversized payloads report truncation loudly.
3. Ask the user the returned confirmation questions, then call
   `confirm_book_mappings({"confirmations": ...})` with `verdict: "mapped"` or
   `verdict: "not_mappable"` per field.

Every relay response is labeled `provenance: mcp_relay`, `unverified_mapping: true`,
`sim: false`, and `live: false`. Relay actions are propose-only: the server may return
draft content for the host to place in the user's own email client, but Ultra CSM sends
nothing and has no commit/receipt path for relay books.
When the host marks a relay draft proposal as approved, `render_email_draft` can turn
that approved payload into the same draft-never-send placement artifact.

Capture the deterministic synthetic relay transcript with:

```sh
make mcp-relay-demo-csm
```

The committed transcript is written to `eval/mcp_relay_transcript.json`.

### Normalized multi-table CRMs

A normalized CRM (separate Account/Contact/Opportunity tables, like a Salesforce
org) relays each table with `ingest_table(book_id, table_name, contract, records,
expected_count, field_metadata)` and then joins them with `confirm_book(book_id,
confirmations)`. Declare what each table's records ARE via `contract`; pass the
source's declared schema (e.g. a Salesforce describe's `referenceTo`) as
`field_metadata` so foreign keys map from source-declared facts instead of
guesses. Auto-mapping handles source-declared references and exact standard
aliases; only identity picks and value-direction questions come back to the
user — five questions for a fully-described three-table book. Orphaned child
records are rejected and counted, never attached to a fabricated parent.

Capture the deterministic relational onboarding transcript with:

```sh
make mcp-relational-demo-csm
```

The committed transcript is written to `eval/mcp_relational_transcript.json`.

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
