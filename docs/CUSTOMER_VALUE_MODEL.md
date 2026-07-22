# Customer Value Model & Agent Roadmap

<!-- sourcebound:purpose -->
Status: architecture + forward spec. Supersedes the "four independent agents" framing.
Per-agent priority factors are **projections** of the model defined here.
<!-- sourcebound:end purpose -->
<!-- sourcebound:allow doc-length reason="The scoring formula, outcome states, and guardrails form one canonical model reference" -->
<!-- sourcebound:allow near-duplicate reason="This formula reference repeats only the architecture context needed to interpret scores" -->

## Where we are now (built + verified)

- Deterministic sweep spine: identity resolve → evidence → gap detect → **priority** →
  disposition → gated proposal → `SweepResult`. CSM scorecard hard gates are green.
- **Slot B** (reason/draft): fixture-scored + optional live Anthropic adapter; contract
  validator at the boundary; red-path falsifiers.
- In-memory snapshot persistence and trajectory computation feed deterministic Time-to-Value,
  Risk, and Expansion lenses. The scheduler dispatches all three; the API, UI, CLI, and MCP
  surfaces accept governed proposal verdicts.
- **Two-lane regression (447d7a4 + live capture):** `regression-csm` (offline,
  CI-gated) = exact spine regression vs `baseline_csm.json` + seeded
  **distributional** fixture proving the Slot B band/cluster machinery (planted
  degraded distribution exits red, spine stays green); `regression-csm-live`
  (credential-gated, **not** CI) captured a structural contract/safety artifact:
  normal prompt 90/90, sentinel-degraded prompt 48/90, Wilson bands disjoint,
  deterministic spine exact-green, named failure clusters, and no full generated text
  stored. This is not yet a semantic quality-drift proof.

**Open / next work:** realistic quality degradation, human-labeled judge validation,
model-migration comparison, durable snapshot persistence, broader realized-outcome sources, and
the value-model dimensions that still lack source evidence.

## The reframe (core decision)

**Not four independent agents. One shared, deterministic Customer Value Model (the spine)
+ thin action lenses (policies) over it.** The signals (divergence, penetration,
value-loop gaps, outcome) cut across lifecycle stages; separate agents would each
re-derive the same health. Provable-core wants exactly this shape: a rich deterministic
model, a thin LLM/action layer.

- **Lenses** = what you *do* about the model at a given state (formerly "Agent 1/2/3").
- **Agent 4** stays genuinely separate: it is population-level, not per-account.

## The model — four rails

Health/success is a function of all four. The first three are **leading indicators**; the
fourth is the thing that actually matters.

1. **Usage** — activity. *(built, in evidence)*
2. **Penetration** — three axes:
   - **Width** — active users vs entitled seats, and vs org size.
   - **Seniority** — champion ↔ exec ↔ IC (depth of buy-in).
   - **Value-loop coverage** — the principled replacement for "function/department."
     See below.
3. **Feature depth** — capabilities used vs entitled (density), not just whether used.
4. **Outcome** — the realized business result. First-class, partly deferred. **Usage ≠
   outcome.** "Outcome unknown" is a *tracked state*, never inferred from usage.

### Penetration done right: value-loop completeness (not department counts)

"Function" is **not** the customer's org chart. It is a **role relative to a value
proposition.** Each product decomposes into value props (jobs-to-be-done with a measurable
outcome); each value prop needs a canonical stakeholder set to realize and *sustain* it:
**economic sponsor** (defends renewal), **admin/technical owner** (keeps it alive),
**operator(s)** (daily usage), **beneficiary** (whose metric it moves).

- **Coverage** = per value prop the customer bought, is the required stakeholder set filled
  with *active* people?
- **Stickiness** = the number of **independently self-sustaining value loops** (full
  stakeholder set + realized outcome). Three complete loops are sticky; "in five
  departments" with no complete loop is **fragile**.
- The **shape** (`value_prop → required_role_archetypes → measurable_outcome`) is universal
  and lives in the model. The **content** (this product's value props, roles, outcome
  metrics) is a **curated, product-specific artifact** in the agent wiki — never a
  hard-coded department enum, never RAG.

## The diagnostic divergence layer

Cross-rail contradictions are the highest-value signals — a usage-only view is blind to
all of them. Each is deterministic, lifecycle-gated, and fires only on **positive
evidence** (missing data never fabricates a signal).

| Divergence | Read |
|---|---|
| usage ↔ Gainsight health | health green + light usage = blind spot (`health_usage_divergence`) |
| **usage ↔ outcome** | high usage + low/unknown outcome = heavy activity without demonstrated value |
| outcome ↔ usage (inverse) | high outcome + low usage = *efficient value* — do NOT flag as risk |
| penetration ↔ usage | high usage + single-threaded = champion-loss fragility |
| value-loop incompleteness | sponsor missing → renewal risk; operator missing → shelfware; admin missing → config decay |
| value-loop coverage ↔ outcomes-bought | which promised value props are unrealized, and with which missing stakeholder |
| Rocketlane ↔ health | implementation late + health green = earliest blind spot |

## Provable-core: model deterministic, LLM thin

- The model, all rails, all factors, all divergences = **deterministic spine** (auditable,
  reproducible under `H_reproducible`, eval-able). The LLM computes none of it.
- LLM lives only in the two slots:
  - **Slot A (classify where a rule genuinely can't)** — first real candidate:
    **title → value-role normalization** behind a curated taxonomy with a mandatory
    `unknown`. Build the taxonomy first; let the residual trip Slot A.
  - **Slot B (narrate/draft)** — built.
- **Curated content** (value-prop map, title→role taxonomy, gap→play) lives versioned in
  the agent wiki. Not hard-coded, not RAG (per the §0b trip-wires in the build plan).

## The lenses (eval-first policies over the model)

Thin policies that consume the same model at different trigger-states. Each is an
eval-first slice with its own action-taxonomy binding + gate. **None re-gather evidence or
re-derive health.**

- **Lens 1 — Time-to-Value** (onboarding/activation gaps). *Built and fixture-verified.*
- **Lens 2 — Risk / Retention** (steady-state divergences, value-loop fragility, renewal
  proximity). *Built and fixture-verified; no churn-probability claim.*
- **Lens 3 — Expansion** (low penetration/feature-depth in a large org, unrealized value
  props). *Built and fixture-verified; customer action remains precedence-gated.*

The per-account **priority is a projection of the model through a lens** — not the model
itself. This is the structural change: stop adding factors to a per-agent score; compute
the model once, project per lens.

## Population analysis

Deterministic cohort rollups and governed cohort-action packets are built over fixture data and
appear in the manager rollup. They group the same source-bound account evidence by declared segment
axes; they do not prove causal impact, use live customer outcomes, or validate an LLM-generated
recommendation. Those remain separate promotion gates.

### Friction to content planning

A **friction** signal asks where customers struggle, while the value rails ask whether they receive
value. The fixture-backed roadmap ranks seven declared struggle triggers across two synthetic
tenants and can preview or explicitly push rows without overwriting a human-set status.

Three boundaries remain:

1. An operator must classify each pattern as a documentation gap, product defect, or expectation
   and sequencing gap. The tool does not route that judgment automatically.
2. The roadmap recommends a plan; it does not author or publish content.
3. Outcome remeasurement is unbuilt. Until each recommendation carries a later friction delta, the
   roadmap is a prioritization artifact rather than a closed learning loop.

## Grounding — buildable now vs Planned

| Dimension / factor | Source | Status |
|---|---|---|
| Usage | telemetry usage signals | **Built** |
| Penetration width (vs seats) | `Entitlement` + `AdoptionSummary.active/licensed_users` | **Built** |
| Penetration vs org size | firmographic employee-count enrichment | **Planned** |
| Seniority / value-role coverage | person-usage ↔ `CRMContact.title/role` join + title→role taxonomy | **Buildable (data-quality dependent)**; Slot A trip-wire |
| Value-loop completeness | value-prop map (curated) + stakeholder-presence join | **Needs the curated map** |
| Feature depth | `Entitlement.capability` vs used / `underused_capabilities` | **Partly built** |
| Outcome — stated | `SuccessPlan.objectives` | **Built** |
| Outcome — realized | outcome telemetry (instrumented per product) or QBR | **Planned**; `not_instrumented` / `unknown` tracked, never faked |
| Usage ↔ outcome verification | `AdoptionSummary` + `SuccessPlan.objectives` | **Built** for high activity + stated objectives + no realized outcome source; no realized outcome claim |
| Sentiment divergence | NPS/CSAT (Gainsight) or ticket tone (SF) | **Planned** (source unconfirmed) |

## Eval / regression discipline carries to the model

The model is the thing under regression; as rails/factors are added, the baseline grows.
- Every new factor/divergence ships **eval-first** with a falsification proof, **weight-
  robust ordering assertions** (total-dominance fixtures), reproducibility, and the
  **positive-evidence-only** guard (a fixture proving missing data yields *no* signal).
- Offline `regression-csm` (built) gates the deterministic model exactly. The LLM-slot
  drift artifact lives in `eval/regression_csm_live.json` (captured, credential-gated,
  not CI).
- The captured live artifact now uses `N=30` per case. Normal prompt passed 90/90
  with Wilson band [0.9591, 1.0]; degraded prompt passed 48/90 with band
  [0.431, 0.6329]. The bands are disjoint and the degraded lane records named
  failure clusters (`missing_evidence_citation`, `live_slot_contract_error`,
  `invalid_json`). The degraded prompt is a sentinel-output sabotage probe, so this proves
  contract/safety drift detection, not semantic quality drift. The validated quality
  judge and model-migration runs are now separate evidence artifacts, and
  `eval/drift_power_csm.json` scopes the current quality-drift claim to about a 46.9
  percentage-point or larger overall-pass-rate drop at n=7 independent examples per arm.

## Forward sequence (the roadmap)

1. **Refactor priority → the Customer Value Model.** Built for the deterministic model,
   Agent 1 projection, penetration width, feature depth, and the first divergence factors.
   Remaining consolidation: fold the legacy TTV base factors into the model rails when the
   data contracts are ready.
2. **Outcome rail (partial).** Built for `SuccessPlan.objectives` as *stated* outcomes,
   `not_instrumented` realized state, and `usage_outcome_unverified` when activity is high
   but no realized outcome source exists. Planned: product-specific telemetry or QBR-backed
   realized outcome.
3. **Value-loop coverage.** Author the curated value-prop map (agent wiki); build
   stakeholder-presence coverage + the title→role taxonomy; evaluate whether **Slot A**
   graduates.
4. **Deepen the three built lenses** as new value-model evidence lands, without re-deriving the
   shared model or widening their current claim boundaries.
5. **Model-migration live comparison.** Re-run `regression-csm-live` for a candidate model
   at a larger `--runs` value and compare pass-rate bands/failure clusters while
   the deterministic spine remains exact-green.
6. **Rocketlane connector** as a pluggable onboarding source feeding the model + resolve
   the **account-join** decision.
7. **Deepen population analysis** only after its fixture-backed rollups gain a declared causal
   question, live outcome evidence, and a leakage-resistant evaluation.

## Open decisions / Planned dependencies

- Account-join strategy (Rocketlane has no companies REST resource).
- Sentiment source (NPS/CSAT vs ticket tone).
- Firmographic + technographic enrichment (org size; tech stack).
- Outcome instrumentation per product (which value metrics are measurable vs QBR-only).
- Authorship of the value-prop map (curated, product-specific).
- Slot A graduation (only if the title→role residual is material after the taxonomy).
- Judge model + human-labeled validation set for `reason_quality`.

## Definitions of done

- **A dimension/factor is built** when: it computes deterministically from cited evidence,
  fires only on positive evidence, has weight-robust ordering tests + a falsification case,
  and is reproducible.
- **A lens is built** when: it projects the model through its trigger-state + action
  taxonomy, every customer-affecting action is a gated proposal, and it adds **no** new
  evidence-gathering or health logic (it consumes the model).
- **Structural live regression is proven** when the live contract/safety artifact exists.
  Current artifact: `eval/regression_csm_live.json` (normal prompt 90/90, sentinel-degraded
  prompt 48/90, disjoint Wilson bands, deterministic spine exact-green). **Quality drift is
  not proven yet**; it requires realistic degradation plus a human-validated judge.
  Model-migration comparison remains a follow-on proof with a candidate model id.
