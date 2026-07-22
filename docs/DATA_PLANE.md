# Ultra CSM data plane

Use this page to understand the tenant-scoped evidence contracts that feed the value
model and the mapping boundary between fixture, simulated, and live connector data.

Ultra CSM starts by defining the systems the agent is allowed to read and, later, write
through a gate:

- Salesforce-backed CRM context: account, contact, case, opportunity, activity.
- Gainsight-backed CS context: company, health score, CTA, success plan, adoption
  summary.
- Product telemetry: entitlements, usage signals, and time-to-value milestones.

The contracts live in `src/ultra_csm/data_plane/contracts.py`. The deterministic
offline fixtures live in `src/ultra_csm/data_plane/fixtures.py`.
The vendor traceability layer lives in
`src/ultra_csm/data_plane/source_maps.py`.

## Design Decisions

- Keep raw product telemetry separate from CS-platform summaries. Gainsight may
  ingest or expose usage/adoption context, but Ultra CSM should not assume the CS
  platform is the original telemetry source.
- Make all connectors tenant-scoped by construction. The fixture implementation
  is pure, deterministic, and socket-free.
- Keep connector writes explicit and idempotent. Future agents must place CRM or
  CS-platform mutations behind the existing action gate.
- Preserve 0/1/many identity resolution. Ambiguous account resolution never
  auto-picks; it is an escalation/clarification condition.
- Keep `EvidenceRef` in the data-plane contracts so Agent 1, the value model,
  and scorecards use the same grounded fact pointer.
- Treat fixture data as eval/training substrate, not customer-outcome evidence.
- Ground Salesforce and Gainsight fields in official object/API documentation.
  Internal field names can be Pythonic, but the source map must identify the
  vendor object, API field, documentation URL, and whether the field is standard
  or an explicit extension.

## Fixture layers

The repository contains more than one fixture scale:

- `data_plane/fixtures.py` provides the small contract and scorecard scenarios used by
  focused tests;
- `data_plane/synthetic_book.py` and `data_plane/book_simulator.py` build the larger
  deterministic book used by the hosted demo and time-series exercises;
- `data_plane/tenants/` contains separate synthetic tenant shapes for normalized and
  flat CRM onboarding paths.

All fixture contacts use synthetic identities and `.example` addresses. Counts shown in
the UI come from `ui/public/demo-api/manifest.json`; do not infer them from the small
contract fixture.

## Source Mapping

`source_maps.py` is the contract between Ultra CSM's internal names and the
vendor APIs:

- Salesforce maps cover Account, Contact, Case, Opportunity, and activity
  write-back fields from Salesforce object/REST documentation.
- Gainsight maps cover Company, scorecard/current score, CTA, Success Plan, and
  Adoption Explorer rollup fields from Gainsight API and object documentation.
- Product telemetry remains a separate adapter boundary. CS-platform adoption
  rollups may summarize telemetry, but the raw telemetry connector is still the
  source for usage signals and time-to-value evidence.

## Operating Boundary

Agent 1 consumes this data plane directly:

- trigger: lifecycle plus activation gap,
- inputs: CRM account/contact, health/CTA/success plan, telemetry milestones and
  usage signals,
- output: grounded next-best action plus gated customer draft,
- safety: no customer outbound or CRM mutation without an action-gate verdict.

The Agent 1 proposal taxonomy lives in `src/ultra_csm/governance/csm_actions.py`.
It defines the only CSM action names Agent 1 may emit, with autonomy tier,
required permission, and release condition for each action. Unknown action names
fail closed.
