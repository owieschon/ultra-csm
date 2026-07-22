# Next dispatch — 2026-07-02 (archived)

> Historical process record. It does not define the current roadmap, work queue, or operating
> guidance. Use the [documentation index](../../../README.md) for current pages.

This was the roadmap for the July 2 work window. It sequenced the work, set the bar, and named the decisions that
require owner input. Detail lives in the linked specs; build to them.

## Where we are (built + verified)

Deterministic sweep spine + `Priority` + gate routing; Slot B (fixture-scored + optional
live Anthropic adapter, contract-validated, red-path falsifiers); two-lane regression —
offline `regression-csm` (CI-gated) and credential-gated `regression-csm-live`. **Customer
Value Model refactor landed**: `value_model.py` with the
criteria rule-resolver (fail-closed field validation, most-specific-wins, recorded
resolution), the buildable factors as metric-vs-resolved-threshold (positive-evidence
only), `project_ttv_lens`, and full provenance enforced by a hard gate. The current
scorecard, regression, and judge-agreement numbers are rendered in `STATUS.md`; do not
hand-type them here.

Phase 1 is now implemented offline: `regression-csm-live --runs N`, paired McNemar
comparison with fake-client coverage, stated outcomes, `not_instrumented` realized state,
and `usage_outcome_unverified` are built and tested. Phase 2 primary capture is recorded
in the regression artifacts and rendered in `STATUS.md`; it proves live contract/safety
drift detection under catastrophic prompt sabotage, but it does **not** yet prove semantic
output quality drift. The remaining proof is the realistic quality-regression lane:
human-validated judge + plausible degradation + candidate model comparison.

The local simulated operating surface is now verified separately from the judge lane:
REST API, MCP tools, CLI demo commands, deep simulated timeline, demo loop, cost/budget
metrics, and quality-breaker fallback were executed. See
[`OPERATING_PROOF.md`](../OPERATING_PROOF.md) and rendered status in `../../STATUS.md`. This is
not live-tenant proof.

Direction set by the owner: **do all three build tracks, then package the demo** — sequenced below.
The ruled-out path was shipping with the N=6 soft spot unaddressed; that soft spot is now
closed for contract/safety drift only. Quality drift stays open until the judge lane lands.

## The roadmap — prove → package → deepen → package

Demo packaging is woven in at the two points where each system story becomes complete —
not deferred to the end.

### Phase 1 — offline, no credentials (complete)
- **Slice B machinery** — `regression-csm-live --runs N` + the **paired McNemar**
  model-migration comparison, with a fake-client test proving the statistic (no creds).
- **Outcome rail** — stated outcomes from `SuccessPlan.objectives`; `realized_state` stays
  `unknown`/`not_instrumented` (never faked); the **usage↔outcome divergence** ("working
  hard, no value"). The rail that makes "time-to-*value*" honest. Eval-first, per
  [`CUSTOMER_VALUE_MODEL.md`](../CUSTOMER_VALUE_MODEL.md).

### Phase 2 — prove live quality drift, then package the eval story
- **Structural capture:** recorded in `eval/regression_csm_live.json` when credentials are
  available; `STATUS.md` is the current rendered pointer for artifact-owned numbers.
  Scope: contract/safety drift, not semantic quality.
- **Quality capture:** judge validation, realistic gold-set degradation, and drift-power
  scoping are now recorded in `eval/gold/judge_agreement.json`,
  `eval/gold/judge_compare.json`, `eval/gold/judge_model_migration.json`, and
  `eval/drift_power_csm.json`.
- **Migration capture:** complete for the judge model: paired McNemar migration adopted
  `claude-sonnet-5`; the current claim boundary is sample-size, not model choice.
- **Then package the eval story:** with non-determinism regression proven for large quality
  drops and scoped for smaller drops, the demo path has its evidence spine.
  Do not wait for Phase 3.

### Phase 3 — deepen + breadth, then package the data-source story
- **Rocketlane connector** feeding the model (decide the **account-join**), then a **second
  lens** (Risk or Expansion) over the now-deeper model.
  Spec: [`ROCKETLANE_ONBOARDING_CONNECTOR_SPEC.md`](../ROCKETLANE_ONBOARDING_CONNECTOR_SPEC.md).
- **Then package the data-source story:** with Rocketlane as a pluggable source + the
  value model + multiple lenses, the source-pluggability story is complete and grounded in
  a real onboarding-system shape.

**Ordering guard:** keep each step an eval-first slice, and **do not start Phase 3 before
Phases 1–2 are solid** — breadth must build on the stable model + proven differentiator,
not shifting abstractions. This is what keeps "do all three" from becoming
breadth-as-procrastination.

## Discipline (all phases)

- **Provable-core:** model + every factor deterministic; the LLM stays in the two slots.
- **Eval-first:** no factor/comparison/lens ships before its test + a falsification /
  positive-evidence proof.
- **Bounded config:** declarative `field op value` matcher (not a DSL); unknown match-field
  fails config load; every fired factor records matched-rule + `config_version` + threshold.
- **Evidence discipline:** `Verified`/`Planned`/`unknown` marked; scaffolding is never
  reported as proven; config is under regression.
- **Fix the result, don't caveat it:** weak evidence is upgraded only when the artifact
  supports the stronger claim.
- **Status discipline:** current gate counts, kappa values, quality bands, claim
  boundaries, and source-readiness state are rendered from artifacts with
  `scripts/render_status.py`, not copied into roadmap prose.

## Decisions requiring owner input — stub + flag, don't invent

1. **Config content** — the initial rules + threshold values. Stubs work; tuning is CS
   judgment, flagged for review, not settled by the builder.
2. **Fields keying the rules** — `arr_cents` available now; `employee_count` + other
   firmographics are `Planned` enrichment, flagged load-time-pending, not silently dead.
3. **Quality regression capture (Phase 2)** — human-labeled judge validation, realistic
   degraded prompt/model, and paired model comparison need owner review and a candidate model id.
4. **Rocketlane account-join (Phase 3)** — shared external id vs mapping vs MCP lookup.

## Push-back license

This dispatch and the specs are recommendations, not orders. Disagree by reading the code,
showing the evidence, then deciding or escalating. The bar to override is a better outcome
against the goal, not preference.

## Git

Continue on the current feature branch; the repository owner handles the merge to `main`.
Small, reversibility-aware commits; verify by executing entrypoints (infra + unit tests
alone are not operating proof); hygiene + `git diff --check` clean before each push.
