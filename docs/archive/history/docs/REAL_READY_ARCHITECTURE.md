# Real-Ready Architecture & Onboarding

<!-- sourcebound:purpose -->
Status: synthesis spec. Research inputs came from R1-R10 in `REAL_READY_RESEARCH_DISPATCH`.
Date: 2026-06-28.
<!-- sourcebound:end purpose -->

Current implementation status:

- Shared connector catalog/readiness contracts are built in
  `src/ultra_csm/data_plane/connector_catalog.py` and
  `src/ultra_csm/data_plane/readiness.py`.
- Credential-boundary smoke commands are built through `ucsm connectors smoke <connector>`.
  Without credentials they report exact missing env vars and open no network connection; with
  credentials they execute read-only documented endpoint checks.
- Credential-boundary schema explorers are built through `ucsm connectors explore <connector>`.
  They produce normalized schema snapshots for Salesforce, Attio, Gainsight, Rocketlane, and
  telemetry using documented read-only discovery surfaces.
- Explorer-to-mapping is built through `mapping_proposal`. A successful schema discovery now
  feeds a reviewable source-map proposal with `mapped`, `ambiguous_confirm`, and
  `missing_to_unknown` coverage states.
- Salesforce recorded-shape transforms are built for Account, Contact, Case, and
  Opportunity query pages in `src/ultra_csm/data_plane/adapters/salesforce.py`.
- Source maps carry minimal field privacy metadata for mapping/readiness boundaries.
- Full live clients, credential storage, human confirmation UI, and runtime adapter wiring remain
  planned until each connector lands its own adapter slice.

## Goal

Build real integration code to the credential boundary without pretending we have live
tenants. The core contract is:

- adapters are verified against recorded real API/schema shapes;
- live mode is unlocked by user-provided credentials and a read-only smoke pull;
- missing or partial sources become `unknown`, never inferred evidence;
- runtime evidence transformation is deterministic;
- LLM assistance is allowed only during onboarding authoring, and only after human
  confirmation freezes the result into config;
- feedback and reporting learn from what happened without silently changing authority.

## Architecture

Use ports and adapters around the existing data-plane contracts.

- Fixture adapters: deterministic, socket-free, CI/eval/demo only.
- Real adapters: auth, pagination, retries, rate limits, incremental sync, source-map
  transforms, and smoke checks.
- One per-source mode switch: `fixture`, `live`, `disabled`.
- Mixed mode is valid: each rail reports its own readiness and degradation state.

The core CSM agent continues to consume typed evidence only. No adapter, committer,
schema explorer, or knowledge layer can set priority, consent, recipient, or authority.

## Integration Adapters

First real adapters:

- Salesforce CRM via OAuth + REST/SOQL. Use Describe APIs for schema, REST query for MVP,
  CDC or timestamp polling for incremental sync, and Task writeback only behind approval.
- Attio CRM via OAuth or workspace API key. Use companies/people as portable account/contact
  concepts, notes/tasks/meetings/calls as timeline evidence, and object/list attributes as
  schema-discovery input. Attio is a strong first live adapter because it is easier to
  credential than enterprise CRM and its custom object model stresses the source-map
  explorer.
- Gainsight CS via REST access key or M2M OAuth. Use Company, CTA, Success Plan, and
  tenant-configured adoption/scorecard outputs; tenant-specific health models require
  schema discovery before mapping.
- Rocketlane onboarding via REST API key. Use projects/phases/tasks/custom fields and
  webhooks for onboarding execution evidence.
- Product telemetry via OTLP/Collector or recorded metric exports. Entitlements and value
  semantics remain configured sources unless a tenant provides a system of record.

Every adapter ships with recorded response fixtures, transform tests, auth failure tests,
pagination/rate-limit tests, and a live smoke command skipped when credentials are absent.
The executable catalog is the first gate: a connector is not ready to implement until it
declares official documentation, credential variables, discovery surfaces, recorded shape
fixtures, and a shared smoke command.

Attio is held to the same standard as Salesforce, not treated as a looser demo path. The
Attio MVP can honestly map people and companies; cases, opportunities, ARR, industry, owner,
role, and consent are tenant-schema mappings unless discovery confirms the fields. That is
a real-ready constraint, not a defect.

Sentiment is a signal type, not a fixed integration. The explorer first looks for sentiment
in CRM/CS timelines: notes, call summaries, NPS/CSAT, scorecard drivers, CTA reasons,
conversation exports, custom sentiment fields, or similar source-backed records. Add a
direct conversation adapter only when the signal is unavailable in the systems of record,
the source exposes a stable API, the signal improves a built factor, and the tenant accepts
the additional data boundary. Missing sentiment leaves sentiment factors `unknown`.

## Identity Resolution

Replace shared fixture IDs with a tenant-scoped canonical identity service.

- Internal key: `ultra_account_id`.
- Vendor-local links: Salesforce Account/Contact IDs, Gainsight Company GSIDs, Rocketlane
  project/customer/external refs, product customer IDs.
- Resolution states: `exactly_one`, `none`, `ambiguous`; internal review may also mark
  `conflicted` or `review_required`.
- Deterministic joins use configured external IDs and exact verified relationships.
- Domains and fuzzy name matches create review candidates, not automatic links.
- No tie-breaking by ARR, renewal date, health score, or recency.

Missing links degrade the affected source to `unknown`; they never fabricate cross-system
evidence.

## Ingestion

Pipeline:

1. Raw immutable landing with request metadata, headers, timestamps, payload hash, and
   credential/config version.
2. Versioned source-map transform.
3. Typed DTO validation.
4. Evidence materialization with provenance/freshness.
5. Readiness updates.

Cursors are tenant/source/object scoped. Failed transforms do not advance durable cursors.
Backfills land raw pages first, then transform in bounded windows. Duplicate webhooks or
events collapse by idempotency key.

Freshness states: `fresh`, `stale`, `unknown`, `failed`, `not_connected`.

## Org Knowledge

Add one active `OrgKnowledgePack` per tenant:

- value propositions;
- approved terminology;
- compact voice/tone rules;
- gap-to-play map;
- value-prop-to-stakeholder map;
- templates;
- source references and validation report.

Raw imported docs are staging material, not runtime knowledge. A human-reviewed pack is
selected deterministically into Slot B as `org_context`. Slot B may use it for language and
draft quality, but operational claims still require evidence IDs.

Required evals: ablation quality, authority invariance, citation, conflict handling,
hostile import, unknown discipline, version regression, and no retrieval calls on the
scored path.

## Preferences And Config

Generalize the current criteria resolver into versioned domains:

- value thresholds;
- segment thresholds;
- consent policy;
- channel policy;
- autonomy policy;
- action release policy.

Each domain has one base rule, allowed fields, validation invariants, most-specific
resolution, and recorded provenance. Unknown fields, missing base rules, unsafe loosening,
unknown consent, disconnected channels, and missing approvers fail closed.

Defaults let fixture/offline mode run immediately. Owner input is required for live
credentials, consent interpretation, outbound channels, sender identities, approvers,
custom source-field mappings, and product-specific knowledge.

## Interface And Committers

Build the smallest operator surface first: a Python CLI.

- `ucsm proposals list`
- `ucsm proposals show <proposal_id>`
- `ucsm proposals approve|reject|edit <proposal_id>`

The interface records verdicts only. It does not send, post, write back, or initiate calls.

Committers are separate ports activated by config:

- email;
- Slack/internal message;
- CRM writeback;
- CS-platform update;
- source-native task/comment update.

Every committer loads an approved verdict, recomputes payload hash, verifies gate binding,
checks consent/channel policy, uses an idempotency key, supports dry-run, and writes an
external-side-effect audit event. Vendor acceptance is not treated as delivery unless the
vendor proves delivery.

## Readiness

Per source state:

- `fixture_verified`;
- `shape_verified_pending_live_creds`;
- `live_auth_verified`;
- `live_schema_verified`;
- `live_smoke_verified`;
- `degraded`;
- `disabled`.

The readiness report must answer what is connected, what is shape-verified only, what is
live-verified, what is missing, which rails are degraded, which actions remain blocked, and
which admin action improves readiness.

Health checks split into service liveness, app readiness, and per-source health. Expensive
smoke pulls run on onboarding, config changes, credential rotation, scheduled review, or an
explicit operator command.

## Schema Discovery And Auto-Mapping

After credentials are connected, a schema explorer discovers the schema and emits a
source-map proposal. This proposal is operationalized as connector output, not only a
printed report; confirmation and runtime adapter wiring are separate steps.

Introspection surfaces:

- Salesforce Describe Global and sObject Describe.
- Gainsight data-management metadata and tenant-specific scorecard/measure metadata.
- Rocketlane fields API plus project/task/phase metadata.
- Telemetry metric/event catalog from Collector config, warehouse schema, or recorded OTLP
  samples.

Mapping boundary:

- deterministic for known standard fields, exact aliases, type compatibility, and coverage;
- LLM-assisted suggestions only for custom/ambiguous fields and tenant-specific names;
- human confirmation freezes a mapping into deterministic config;
- runtime mapping and transformation never call an LLM.

Discovery has three layers:

- field to typed shape: mostly deterministic from Describe-style metadata;
- field to semantic role: suggestion plus human confirmation for which field is the health
  signal, activation event, renewal date, segment, or outcome;
- value semantics: mandatory human confirmation for direction and ordering when a value can
  drive a factor. A tenant score of `5`, a green label, or a tier value is never assumed to
  mean good or bad without confirmation.

Coverage states:

- `mapped`;
- `ambiguous_confirm`;
- `missing_to_unknown`.

Any config rule that references an ambiguous field fails config freeze until a human confirms
it. Missing fields degrade to unknown and are listed in the coverage report. Schema drift
changes the snapshot hash, so a frozen config can be compared against the schema it was
confirmed from.

Sample values sent into mapping suggestion must be redacted. Source-map field metadata carries
privacy class and LLM-allowance flags so readiness reports and mapping prompts can include
field names, counts, and hashes without leaking contact data, customer content, or secrets.

## Feedback And Learning

Close the loop from proposal to verdict to execution to re-observation.

Feedback creates suggestions, not authority changes. Repeated approvals, rejections, edits,
and post-action observations may propose:

- value-model threshold changes;
- source-map review;
- org-knowledge pack updates;
- gap-to-play changes;
- report metric changes;
- eval-case promotion.

Each suggestion carries source proposal/verdict IDs, pre/post evidence hashes, config
versions, source-map versions, org-knowledge version, observation window, freshness state,
blast radius, rollback pointer, and required evals. Approval creates a new versioned
artifact. Denial writes nothing. Revision writes exactly the human-approved payload.

Outcome feedback is observational. Reports may say a gap closed after an action, or that no
movement was observed within the configured window. They may not claim causation, ROI, risk
reduction, or renewal save from correlation alone.

## Reporting

Add a report layer after consume/process. It reads computed model outputs, lens projections,
proposal state, readiness, source freshness, and provenance. It does not gather evidence,
score accounts, infer health, or change priority.

Report packets:

- `CsmWorkQueueSummary`;
- `ManagerBookView`;
- `BookHealthSnapshot`;
- `TrendSeries`;
- `DivergenceAggregation`;
- `ReadinessCoverageRollup`;
- `DigestPacket`;
- `EbrPrepPacket`.

All counts, rates, rankings, trends, cohorts, freshness states, and divergence patterns are
deterministic. Optional LLM narration may summarize the packet, but cannot introduce new
metrics, causal claims, account health, recommended actions, or source facts.

The manager view is cross-book and operational: queue load, readiness gaps, repeated
divergence patterns, action throughput, coaching signals, and calibration candidates. It
separates customer risk from observability debt. EBR prep can summarize approved evidence,
but cannot turn usage into a claimed business outcome.

## Build Sequence

1. Merge the simplification cut.
2. Add readiness state/report schema and per-source mode config.
3. Add the source-map schema and recorded-shape fixture harness.
4. Build one credential-accessible vertical first: Attio or Salesforce CRM read-only smoke,
   schema discovery, source-map confirmation, typed transform, readiness report.
5. Add org knowledge pack selection to Slot B with authority-invariance evals.
6. Add the CLI proposal review surface.
7. Add one dry-run committer, then one live committer behind gate + consent policy.
8. Expand adapters source by source.
9. Add feedback/outcome instrumentation.
10. Add deterministic report packets and manager/CSM views.

## Definition Of Done

- A real adapter is built only when it passes recorded-shape tests and exposes a credentialed
  read-only smoke command.
- A source-map is built only when transforms are executable, versioned, and covered by tests.
- A live source is claimed only after `live_smoke_verified`.
- Missing connections produce `unknown`, not substitute evidence.
- LLM-assisted mapping is never runtime authority.
- The operator can approve/reject/edit proposals without the deleted console.
- Learning suggests changes for human review; it never silently tunes runtime authority.
- Reports are deterministic packets first; narration is optional and bounded.
