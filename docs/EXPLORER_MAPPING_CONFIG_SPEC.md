# Explorer Mapping And Config Spec

<!-- clean-docs:purpose -->
Status: first operational slice built. Date: 2026-06-28.
<!-- clean-docs:end purpose -->

## Purpose

The connector explorer must do more than print a schema. It must turn a discovered
schema into a reviewable source-map proposal the agent can later consume deterministically.

The operating chain is:

`discover schema` -> `propose field mapping` -> `confirm semantic/value mappings` ->
`freeze deterministic config` -> `runtime consumes only confirmed config`.

## Built

- `run_explorer(...)` now attaches a `mapping_proposal` when schema discovery succeeds.
- `propose_source_mapping(snapshot)` maps known standard fields from the recorded source-map
  catalog and connector-specific aliases.
- `ambiguous_confirm` is used for custom, tenant-specific, semantic-role, and value-direction
  mappings that cannot be safely assumed.
- `missing_to_unknown` is used when a required field/object is absent; the mapper never fills
  gaps with invented defaults.
- `freeze_confirmed_source_map(...)` refuses unresolved `ambiguous_confirm` entries and returns
  a versioned, hash-addressed config from confirmed mappings.
- CLI JSON includes the mapping proposal; human-readable explorer output summarizes mapped,
  confirm, and unknown counts.

## Confirmation Rules

- Standard fields can map deterministically when object, field, and type shape are compatible.
- Custom and tenant-specific fields may be suggested, but they do not enter runtime config until
  confirmed.
- Value direction and ordering require human confirmation whenever the value can influence a
  score, rank, health interpretation, or action priority.
- Sample values are not required for this offline slice and are not sent to a model.
- Any future LLM assistance is config-time only. The confirmed mapping becomes deterministic
  config; runtime never calls an LLM to interpret field meaning.

## Connector Coverage

- Salesforce: Describe-discovered standard fields map through the Salesforce source maps.
- Gainsight: tenant metadata maps through the Gainsight source maps; health/score direction is
  confirmation-gated.
- Attio: company/person object attributes map through connector-specific aliases; missing
  enterprise CRM fields remain unknown or confirmation-gated.
- Rocketlane: task/project discovery maps onboarding milestone fields where present.
- Product telemetry: declared OTLP attributes map to telemetry contracts; absent value/time
  fields remain unknown until the telemetry catalog or adapter exposes them.

## Done Bar

- Tests prove standard fields auto-map.
- Tests prove custom semantic fields are flagged for confirmation instead of guessed.
- Tests prove value direction is not silently assumed.
- Tests prove unresolved semantic mappings cannot be frozen into config.
- Tests prove partial schemas produce an honest coverage report.
