# Real-Ready Architecture & Onboarding — Research Dispatch

Status: research dispatch. Each workstream produces a SPEC, not code. The specs compose
into one durable architecture + onboarding flow.
Date: 2026-06-27.

## The vision

A user onboards by **connecting their systems, their data, their org-specific knowledge,
and their preferences** — and the agent just works. No creds exist today (no Salesforce,
Gainsight, Rocketlane, or OTel access), so the target is: **build everything real, right up
to the credential boundary.** The only thing standing between fixtures-mode and live-mode
should be the user plugging in their connection + config.

## The honest definition of "as far as we can" (read this first)

We do **not** have real tenants to test against, so avoid untestable adapter skeletons —
the exact failure the last audit found. The discipline:

- **Real to the credential boundary.** Adapter code (auth, HTTP/SDK/MCP client, pagination,
  rate limits, retries, fail-closed errors, and the source-map *transformation*) is written
  and **unit-tested against recorded real API response shapes** (captured from official docs
  / sandbox examples / OpenAPI specs) — not hand-waved, not faked. The single missing piece
  is live credentials.
- **A test the user runs at onboarding** confirms the live wiring: connect creds → a
  read-only smoke pull → "we reached your system and mapped N records." Until then the
  adapter is "verified against real shapes, pending live creds" — `Planned-live`, never
  claimed as live.
- **Provable-core preserved.** Real data still becomes *typed evidence* feeding the
  deterministic spine. The source-maps become operational transformation code, not
  decorative documentation. No new LLM authority.
- **Honest graceful degradation.** Connect only Gainsight → the agent runs on Gainsight
  signals, marks telemetry/Rocketlane `unknown`, and **never fabricates** the missing rails.
  Partial connection is a first-class, supported state — built on the positive-evidence-only
  discipline already in the value model.

## The architectural frame (what every workstream serves)

- **Ports & adapters (hexagonal).** Every external dependency sits behind a Protocol with a
  **fixture impl (built) + a real impl (to build), selected by config/creds.** The agent
  core never knows which is active. Onboarding swaps the adapter, not the core. (The data
  plane already has the ports + fixtures; this makes the real side exist.)
- **One switch, two modes.** Fixtures = demo/eval/CI (offline, deterministic). Real =
  live tenant. Identical shapes; the switch is config.
- **Modular by construction.** A new source / channel / knowledge type = implement a port,
  zero core change.
- **Frictionless = sane defaults + progressive disclosure.** It runs on defaults; the user
  overrides only what they care about. Never "configure everything before anything works."

## The fan-out (each = one research agent → one spec)

Right-size the count; these are the workstreams, not a fixed agent count. Several already
have partial research in-repo (Rocketlane connector spec; Gainsight scorecards/rules) — use
them as inputs, don't redo.

**R1 — Integration adapters (per system).** For Salesforce, Gainsight, Rocketlane, and
product-telemetry/OTel: the real **auth** model (OAuth scopes / API key), the **API surface**
covering the fields the data plane needs, **SDK vs REST vs MCP** trade-offs, **pagination /
rate limits / retries**, **incremental sync** (CDC / webhooks / `updatedAt` cursors),
**fail-closed** error handling, and exactly how the **source-map transforms a real payload
→ the typed shape**. Output: a per-system adapter spec behind the existing Protocol, each
flagged for whether it's testable without enterprise creds (e.g. Salesforce Dev Edition,
public sandboxes) and what recorded-shape fixtures to capture.
- **CRM is a port with multiple real adapters.** Include **Attio** alongside Salesforce —
  two real CRM adapters concretely prove the modular-port thesis, and Attio is far more
  credential-accessible than enterprise SF (likely the *first* genuinely-testable real
  adapter) and its highly-custom data model is the ideal stress test for the R8 explorer.
- **Signal source ≠ a fixed integration.** Some signals (meeting/call **sentiment**, e.g.
  Granola/Gong) usually arrive *already synced into the CRM/CS timeline* — so the explorer
  should **discover where a signal lives**, not presume a dedicated integration. Add a
  direct adapter only when the signal exists nowhere else and is worth it. (This resolves the
  `sentiment_health_divergence` factor's open "source unconfirmed" question.)

**R2 — Cross-system identity resolution (the account-join).** The open decision. Research
how mature CS/RevOps stacks join SF ↔ Gainsight ↔ Rocketlane ↔ product (external IDs,
shared keys, deterministic vs fuzzy matching, a resolution service). Output: a modular
identity-resolution layer that replaces the fixtures' coincidental shared-UUID.

**R3 — Data sync & ingestion.** Webhooks vs polling vs batch per source; the refresh cadence
(a design exists — per-source by signal velocity); incremental cursors; the normalization
pipeline that turns source-maps into executable transforms; freshness/provenance; storage;
the fixture↔live switch. Output: a durable sync/ingestion architecture.

**R4 — Org-knowledge onboarding.** How a user supplies product value-props, terminology,
voice/tone, the gap→play map, and the value-prop→stakeholder map with **minimal friction**
(structured templates? import-from-existing-docs? a guided wizard?); versioning; and how it
**assembles into the LLM system prompt(s)** without RAG-sprawl. Output: the org-knowledge
layer + its onboarding UX (this is the `agent_wikis/ttv-accelerator/` we designed,
generalized; it's what makes Slot B's output *good* instead of boilerplate).

**R5 — Preferences & configuration onboarding.** Frictionless config: sane defaults +
progressive override; extend the **criteria-resolver** (already built) for thresholds/segment
rules; consent policy, channels, autonomy tiers; validation. Output: a preferences onboarding
spec + schema.

**R6 — Interface & action committers.** The minimal CSM **interface** for view-queue +
approve/edit/reject (CLI/TUI/API — NOT the deleted Next.js console; lightweight, no JS deps);
the modular **action-committer** port (email / Slack / CRM-writeback) activated by config,
which is the missing piece that actually *sends* an approved proposal; how both compose with
the existing gate. Output: interface + committer architecture.

**R7 — Onboarding orchestration & readiness (the meta-layer).** How it all composes into
"connect → works": secrets/config management, the fixture↔live switch, a **readiness/coverage
report** (what's connected, what's missing, what's degraded), graceful partial operation, and
B2B-SaaS agent onboarding patterns. Output: the onboarding orchestration spec + the
"real-to-the-credential-boundary, honest about the rest" contract.

**R8 — Schema discovery & auto-mapping (the explorer).** On credential auth, each adapter
runs a **schema explorer** that introspects the source's available objects/fields and
**auto-proposes the source-map**, so the agent self-configures instead of requiring a
hand-written mapping. Research the introspection surface per source (Salesforce **Describe
API** — objects/fields/types incl. custom; Gainsight objects + the **tenant-specific
scorecard measures**, which differ per tenant so discovery is *required*, not optional;
Rocketlane **custom-fields API** + documented objects; telemetry metric/event taxonomy /
OTel semantic conventions), how discovered fields match the agent's typed concepts, and —
the key decision to ground — **where an LLM is warranted vs not**:

- **Hybrid mapping.** *Deterministic* for standard/known fields + type-compatibility +
  required-coverage checks. *LLM-assisted suggestion* only for **custom/ambiguous fields and
  tenant-specific names** (interpret field name + sample values → propose the typed concept).
- **LLM at config-time only.** The explorer's LLM call runs at onboarding to *propose* a
  mapping; a human **confirms**; the confirmed mapping **freezes into deterministic config**.
  **The runtime stays LLM-free and deterministic** — the LLM is a config-authoring assistant,
  never a runtime authority. (Same pattern as Slot A's title→role normalization and the §0b
  RAG trip-wire: curated/deterministic first, LLM for the residual, human-confirmed.)

Discovery is **three layers**, not one — and the meaning, not just the shape, is the point:
1. **Field → typed shape** (schema + type — mostly deterministic from Describe-style APIs).
2. **Field → semantic role in the value model** ("this is *the* health signal / the
   activation event / the segment field / the renewal date") — LLM-suggest from field name +
   sample values, human-confirm.
3. **Value semantics** (what each value *means*: which direction is good, the ordering — is a
   `5` best or worst; is "green" healthy or this tenant's worst tier; what does `Tier 1`
   mean) — LLM-suggest from sample values + distribution, but **value direction/ordering is a
   MANDATORY human-confirm** for anything that sets a factor's direction. Getting this wrong
   silently *inverts* the agent (recommends backwards), so it is never auto-accepted.

So the autodetect-vs-manual answer: layers 1–2 are suggest-and-confirm; layer 3 *direction*
is always human-confirmed. Sample values used for inference may contain customer PII — see
guard 7.

Output: the explorer spec + the auto-proposed source-map + a **coverage report**
(`mapped` / `ambiguous-confirm` / `missing → rail unknown`) that feeds R5 (config) and R7
(readiness). Threads into R1 (adapters expose the introspection call). Must be eval-able:
test the explorer against **recorded real schemas** — does it auto-map standard fields, and
correctly flag custom ones for confirmation rather than silently guessing?

**R9 — Feedback & learning loop (the missing half — closes the loop on usefulness).** Today
the agent recommends and nothing learns. Research two loops:
- **Verdict feedback:** the gate already records approve/reject/edit. Research how *repeated*
  rejections/edits surface as "your thresholds or mapping may be wrong" and feed
  **human-confirmed** config tuning — never silent auto-tuning of authority.
- **Outcome feedback:** did the action move the milestone / resolve the risk / land the
  renewal? Research instrumenting the `realized_outcome` rail by **re-observing the account
  after an action** (did the gap close?). This is what lets the system prove its value and
  improve — real outcomes, not benchmark-only evidence.
Discipline: learning *suggests* changes a human confirms; the spine stays deterministic;
outcome attribution is honest (correlation, not claimed causation — leakage discipline).
Output: feedback-capture schema + the tuning loop + the realized-outcome instrumentation.

**R10 — Reporting & the manager layer (consume/process → REPORT).** We built the per-account
work queue (the IC's "do this") and skipped *report*. Research the reporting surface:
book-health summary, trends over time, the **second user — the CS manager** — and their
**cross-CSM / book-level view**, plus the digest and EBR-prep material. Where divergence
patterns aggregate across the book, that is the Agent-4 calibration finding. Same split as
everything: deterministic aggregates, LLM *narrates*. Output: the reporting layer + the
manager-view spec.

## The synthesis target

The workstreams compose into **one** durable doc — *Real-Ready Architecture & Onboarding* —
defining: the ports + the fixture↔real switch; the onboarding flow (connect systems → data →
knowledge → preferences); graceful degradation; and a build sequence that goes adapter-by-
adapter to the credential boundary, each eval-first and verified against recorded real shapes.
The per-agent priority/value docs become consumers of this; this is the integration spine.

## Discipline guards (do not violate)

1. **No untestable skeleton.** Every adapter ships with tests against recorded real API
   shapes. "Built" means verified-to-the-credential-boundary, not "the class exists."
2. **Provable-core intact.** Real data → typed evidence → deterministic spine. Source-maps
   become executable transforms. No LLM authority added.
3. **Honest partial state.** Missing connection → `unknown`, never fabricated. Readiness
   report tells the truth about coverage.
4. **Research → spec → eval-first build.** Each workstream is a spec first; building follows
   the same eval-first discipline as everything else.
5. **Frictionless, not feature-complete.** Optimize the *connect-and-go* path; defaults
   everywhere; the user adds only what's theirs.
6. **LLM at config-time only (the explorer boundary).** Any LLM use in discovery/mapping is
   a *suggestion* an authoring human confirms; the confirmed result freezes into deterministic
   config. The runtime spine stays LLM-free. Never silently auto-map an ambiguous field —
   surface it for confirmation.
7. **PII / data boundary (cross-cutting).** Real customer data — including PII — now crosses
   into the system and into the LLM. Define what may reach the model (minimize/redact
   identifiers not needed for the task), data residency, retention, deletion, and what's
   stored vs ephemeral. This guard binds **R1** (ingestion), **R4** (knowledge), **R6**
   (committer/send), and **R8** (sample values used for mapping inference can contain PII).
   Default: minimize what crosses the LLM boundary; for enterprise B2B this is table-stakes —
   its absence kills deals, handling it well is a credibility signal.

## Sequencing

This is the architecture for the roadmap's Phase 2/3. It is **research (read-only) +
new specs**, so it can run in parallel with — or right after — the simplification cut without
touching the code being deleted. Build follows once the simplification lands and the specs
exist. The first *buildable* slice will be whichever adapter is testable without enterprise
creds (likely Salesforce Dev Edition) + the org-knowledge layer + the CLI interface + one
committer — the thin vertical that closes the loop on something real.
