# Data Handling

<!-- clean-docs:purpose -->
Status: active pre-live-ingestion posture.
<!-- clean-docs:end purpose -->

Ultra CSM stores only the evidence needed to explain, govern, and audit customer-success
work. Live connector reads must happen through confirmed tenant scope and must not put raw
customer content or secrets into logs.

## Stored Data

- CRM, CS, telemetry, and comms evidence: account records, contacts, milestones, usage
  signals, cases, success plans, communication metadata, snippets, internal notes, and
  confirmed call transcript signals used by the value model and brief surfaces.
- Proposals and verdicts: action proposal payloads, payload hashes, verdict outcomes, and
  the append-only ledger needed to prove who authorized what and when.
- Connector mapping state: human-confirmed Slack channel and Notion meeting-note mappings
  to accounts and contacts. Unconfirmed candidates remain review inputs, not autonomous
  truth.
- Delivery artifacts: approved customer outreach payloads and committer idempotency keys
  needed to prove a send was exactly the human-approved content and was not duplicated.

## Retention

- Append-only governance ledger: retained indefinitely for audit and earned-autonomy
  evidence unless the owner performs a documented tenant deletion.
- Proposal, verdict, and idempotency rows: retained with the ledger because payload hash
  binding and duplicate-send prevention depend on the historical record.
- Raw comms-derived content stored as evidence: retained only while needed for active
  account explanation, validation, and audit. Before production tenant onboarding, set a
  tenant-specific retention schedule and deletion job; until then, live ingestion remains
  limited to the owner-approved dev/trial/burner orgs.
- Logs: operational logs are for diagnostics, not evidence storage. They must never be
  the retention home for email bodies, Slack text, transcripts, OAuth tokens, API keys, or
  bearer tokens.

## Scrubbing

Structured JSON logging runs through `ultra_csm.logging_config.JSONFormatter`, which
recursively scrubs log messages and `extra` fields:

- secret-bearing fields such as authorization headers, API keys, access tokens, refresh
  tokens, client secrets, passwords, and token-like assignments are replaced with
  `[redacted-secret]`;
- customer-content fields such as `body`, `content`, `text`, `transcript`,
  `customer_draft`, and derived `*_body`/`*_content` fields are replaced with
  `[redacted-content]`;
- email addresses in messages or structured fields are replaced with `[redacted-email]`.

The scrubbing boundary is intentionally central. API, MCP, tick, and live ingestion paths
inherit it when they call `setup_logging`, and tests assert that seeded PII, customer
content, and secret tokens do not appear in rendered log records.

## Operating Limits

- Do not log raw connector responses, email bodies, Slack message text, Notion transcript
  bodies, OAuth refresh responses, or authorization headers.
- Do not print secret values in CLI output, PR text, reports, or chat. Use environment
  variable names and hashes/counts only.
- Customer-facing sends still require a human `submit_verdict`; logging scrubbers are a
  backstop, not authorization.
