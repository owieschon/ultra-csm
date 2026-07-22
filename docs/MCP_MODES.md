# MCP access and data boundaries

Use this page to choose MCP tool authority, data sources, and relay behavior without
mistaking one setting for a complete server mode.

## Choose each axis

Access flags and data-plane mode are separate controls. Relay ingestion is a capability
of the default governed runtime, not a third mutually exclusive mode.

| Axis | Setting | Consequence |
| --- | --- | --- |
| Access | `ULTRA_CSM_MCP_READONLY=1` | Skips PostgreSQL and refuses every state-changing MCP tool. Read sources still depend on the data-plane setting. |
| Access | `ULTRA_CSM_DEMO_OPERATOR=1` | Uses synthetic data, runs the governed proposal loop, disables relay-state tools, and writes local simulation state. |
| Access | neither flag | Boots the governed runtime and exposes native sweep/verdict tools plus relay ingestion. It can mutate its governance database. |
| Data | `ULTRA_CSM_DATA_PLANE_MODE=fixture` or unset | Uses deterministic fixture-backed reads. |
| Data | `ULTRA_CSM_DATA_PLANE_MODE=live` | Uses configured live connectors and may make network reads. Missing required Salesforce configuration fails closed. |
| Relay | default access only | Accepts host-supplied records into in-memory mapping sessions and returns propose-only draft artifacts. Native governed tools remain available on the same server. |

`ULTRA_CSM_MCP_READONLY` and `ULTRA_CSM_DEMO_OPERATOR` are mutually exclusive. Read-only
means no server-side mutation; it does not mean no network unless the data plane is
also pinned to fixtures.

## Start the fixture-backed reader

Pin both access and data source when you need a socket-free, no-database reader:

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[mcp]"
ULTRA_CSM_MCP_READONLY=1 ULTRA_CSM_DATA_PLANE_MODE=fixture \
  PYTHONPATH=src:. .venv/bin/python -m ultra_csm.mcp_server
```

Point an MCP host at that command. `score_account`, `list_accounts`, account briefs,
holds, trajectories, proposal reads, and next-step guidance remain available. Sweep,
verdict, relay-ingest, mapping-confirmation, and draft-rendering tools refuse.

Capture the deterministic fixture transcript with:

```sh
make mcp-readonly-demo-csm
```

The target writes `demo_state/mcp_readonly_transcript.json`, including the tool calls that
ground each answer.

## Run the simulated operator

```sh
ULTRA_CSM_DEMO_OPERATOR=1 \
  PYTHONPATH=src:. .venv/bin/python -m ultra_csm.mcp_server
```

This setting boots governance state, seeds a synthetic sweep, and enables verdict tools.
It uses a code-minted demo approval principal, so a verdict demonstrates the gate
mechanics rather than independent human review. An approved outreach proposal can write
simulation artifacts under `demo_state/mcp_operator/`:

- `tenant_state.json` for mutable synthetic tenant state;
- `outbox.jsonl` for simulated outbound messages;
- `commit_audit.jsonl` for simulated commit receipts.

No live email is sent. `render_email_draft` returns an artifact marked
`draft_never_send: true`; it does not create a message in an email provider.

Capture the deterministic operator transcript with:

```sh
make mcp-operator-demo-csm
```

The target writes `eval/mcp_operator_transcript.json`.

## Run the governed default runtime

Start without either access flag to use native sweep and verdict tools or to ingest a
book relayed by the host. The server boots persistent PostgreSQL when configured and an
ephemeral cluster otherwise. Authorizing verdicts require a configured bearer token
unless the separate loopback-only `ULTRA_CSM_DEMO_NOAUTH=1` escape hatch is enabled.

Relay work follows this sequence:

1. Call `report_readiness(["crm", "email", "telemetry"])`. This records a host
   declaration; the server cannot inspect the host's tool inventory. CRM is the minimum
   useful input.
2. Call `ingest_book(records, source_descriptor, expected_count)`. The required count
   makes truncation and partial ingestion visible.
3. Ask the operator the returned mapping questions, then call
   `confirm_book_mappings({"confirmations": ...})` with `mapped` or `not_mappable` for
   every field.

Relay responses remain labeled `provenance: mcp_relay`, `unverified_mapping: true`,
`sim: false`, and `live: false`. Relay-generated actions are propose-only, but that
boundary does not disable the server's separate native verdict tools. The server can
return draft content for a host to place; it does not claim that the host placed or sent
it.

Capture the synthetic relay transcript with:

```sh
make mcp-relay-demo-csm
```

The target writes `eval/mcp_relay_transcript.json`.

### Normalized multi-table CRMs

For separate account, contact, and opportunity tables, call
`ingest_table(book_id, table_name, contract, records, expected_count, field_metadata)`
for each table, then `confirm_book(book_id, confirmations)`. Source-declared schema
metadata supplies foreign keys; orphaned child records are rejected and counted.

```sh
make mcp-relational-demo-csm
```

The target writes `eval/mcp_relational_transcript.json`.
