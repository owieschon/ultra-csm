# Ultra-CSM: Capability Map & Dependency Graph

<!-- sourcebound:purpose -->
Use this preserved 2026-07-21 capability snapshot only to trace prior roadmap assumptions. Its
status cells are not current; use the [canonical architecture](../../ARCHITECTURE.md), current
tests, and source for present behavior.
<!-- sourcebound:end purpose -->
<!-- sourcebound:allow doc-length reason="The capability-to-evidence lookup is one canonical reference" -->
<!-- sourcebound:allow near-duplicate reason="This lookup repeats only the labels needed to map into the linked architecture" -->
## Domains

Nine domains. Each is an independently ownable, testable surface.

D1 Value Model
D2 Data Plane
D3 Lenses (TTV, Risk, Expansion)
D4 Governance
D5 Operating Layer
D6 Internal Bridge
D7 Knowledge Base
D8 Cohort Analyst
D9 Eval & Observability

## D1: Value Model

VM-1: Four-rail health scoring (usage, penetration, feature-depth, outcome) — Built (outcome rail is partial: stated objectives, success-plan/Rocketlane realization, and synthetic renewal outcome evidence). Depends on D2 data plane outputs.
VM-2: Configurable thresholds by account tier — Built.
VM-3: Diagnostic divergence detection (cross-rail contradictions) — Built. Depends on VM-1.
VM-4: TTV priority projection — Built. Depends on VM-1, VM-3.
VM-5: Lifecycle state classification (onboarding, adopted, expanding, renewing, at-risk) — Partially built (TTV only). Depends on VM-1.
VM-6: Snapshot persistence (store value model output per evaluation) — Not built. Depends on VM-1, D2 database.
VM-7: Trajectory computation (compare snapshots over time windows) — Not built. Depends on VM-6.
VM-8: Outcome rail instrumentation (connect business metrics to stated objectives) — Partially built (Slice 0/1 only: terminal Renewal `CRMOpportunity` evidence can mark outcome known with won/lost direction; broader business metrics, attribution, and UI/ops depth remain unbuilt). Depends on D2 connectors, VM-1.
VM-9: Trend-based factor generation (decline_slope, activation_window_days) — Not built. Depends on VM-7.

## D2: Data Plane

DP-1: Typed contract interfaces (CRM, CS Platform, Product Telemetry) — Built.
DP-2: Fixture implementations with adversarial cases — Built. Depends on DP-1.
DP-3: Connector readiness lifecycle (spec to smoke to discover to map to freeze) — Built.
DP-4: Schema explorer with confidence-scored field mapping — Built. Depends on DP-3.
DP-5: Salesforce adapter (JSON-to-dataclass parsers) — Partially built (parsers only, no HTTP client). Depends on DP-1.
DP-6: Salesforce live connector (OAuth, SOQL, pagination, rate limiting) — Not built. Depends on DP-5.
DP-7: Attio live connector — Not built. Depends on DP-1.
DP-8: Gainsight live connector (health, CTAs, success plans, renewal center, education) — Not built. Depends on DP-1.
DP-9: Rocketlane live connector (milestones, tasks, timeline) — Not built. Depends on DP-1.
DP-10: Relationship intelligence live connector (stakeholder map, multi-threading, engagement) — Not built. Depends on DP-1.
DP-11: Product telemetry connector (usage events, feature activation, sessions) — Not built. Depends on DP-1.
DP-12: Billing connector (plan, consumption, invoices, payment status) — Not built. Depends on DP-1.
DP-13: Calendar connector (meeting events, attendees, frequency) — Not built.
DP-14: Email connector (threads, response times, sentiment signals) — Not built.
DP-15: Support connector (tickets, CSAT, resolution patterns) — Not built. Depends on DP-1.

## D3: Lenses

L-1: Lens protocol (projection function, filter chain, drafting slot, governance tier) — Established by Agent 1 pattern. Depends on D1, D4.
L-2: Time-to-Value lens (detect onboarding stalls, propose interventions) — Built. Depends on D1, D2, D4, L-1.
L-3: Account sweep (batch iterate book, resolve identity, build evidence, score, propose) — Built. Depends on L-2, D2.
L-4: Slot B writer (reason + draft generation, evidence grounding, contract validation) — Built. Depends on L-1.
L-5: Risk/Retention lens (trajectory, engagement, renewal proximity, champion risk) — Not built. Depends on D1, VM-7, D2, D4, L-1.
L-6: Expansion lens (consumption vs entitlement, unrealized value, sustained health) — Not built. Depends on D1, VM-7, D2, D4, L-1.
L-7: Multi-lens account view (same account seen through multiple lenses without conflict) — Not built. Depends on L-5, L-6.
L-8: Lens-specific drafting prompts (different tone/framing per lens) — Not built (single Slot B prompt today). Depends on L-4.

## D4: Governance

G-1: Action proposal lifecycle (propose to verdict to execute) — Built.
G-2: Payload binding (SHA-256 anti-TOCTOU) — Built. Depends on G-1.
G-3: RBAC with separation of duties (two-layer: app + DB trigger) — Built.
G-4: CSM action taxonomy (6 actions, 3 autonomy tiers, release conditions) — Built.
G-5: Fixture verdict source for deterministic eval — Built. Depends on G-1.
G-6: Live verdict source (API/UI for CSM to review and approve proposals) — Not built. Depends on G-1.
G-7: Proposal expiration (time-bound pending proposals) — Not built. Depends on G-1.
G-8: Autonomy graduation (track approval/modification/outcome rates, propose tier changes) — Not built. Depends on G-1, D8 cohort analyst.
G-9: Policy evaluation from policy tables (tables exist, no app code reads them) — Not built. Depends on G-1.

## D5: Operating Layer

OL-1: Daily digest (prioritized list of accounts, proposals, commitments, meetings) — Not built. Depends on D1, D3, OL-5, OL-3.
OL-2: Account brief generation (health, changes, stakeholders, commitments, risks, talking points) — Not built. Depends on D1, D2, VM-7, OL-5.
OL-3: Calendar integration (meeting prep, attendee tracking, frequency shift detection) — Not built. Depends on DP-13.
OL-4: Inbox intelligence (classify, prioritize, extract action items, link to account context) — Not built. Depends on DP-14, D1.
OL-5: Commitment tracker (extract from interactions, track status, surface due dates, detect completion) — Not built.
OL-6: Activity auto-logging (CRM activity records from observed events) — Not built. Depends on D2 CRM connector (write path).
OL-7: Call summarization (post-meeting summary, action items, sentiment) — Not built.
OL-8: CSM reflection prompting (end-of-day/week retrospective capture) — Not built. Depends on OL-5.

## D6: Internal Bridge

IB-1: Feedback aggregation (cross-account pattern detection weighted by ARR, health, renewal) — Built (spike-scoped MP-B minimal slice: Wave-0 CRM case signals only, not full ARR/health/renewal weighting). Depends on D1, D2, OL-5.
IB-2: Structured routing (tag, weight, route to Product/Engineering/Marketing/Sales) — Built (spike-scoped MP-B minimal slice: deterministic Engineering/Product/abstain routing over the Wave-0 oracle). Depends on IB-1.
IB-3: Internal draft generation (feedback summaries, competitive updates, exec briefs) — Built (spike-scoped MP-B minimal slice: internal bridge packet schema and fixture writer only). Depends on IB-1, D3.
IB-4: Feedback loop closure (feature shipped to identify waiting accounts to propose outreach) — Not built. Depends on IB-1, D2, D3.
IB-5: QBR/renewal narrative generation — Not built. Depends on D1, VM-7, D2, OL-5.

## D7: Knowledge Base

KB-1: Article data model (structured records with provenance, category, review status) — Not built.
KB-2: Article storage and retrieval (indexed, searchable by situation type) — Not built. Depends on KB-1.
KB-3: Playbook authoring workflow (human-authored, versioned, reviewed) — Not built. Depends on KB-1.
KB-4: Slot B integration (relevant playbooks included in evidence bundle) — Not built. Depends on KB-2, L-4.
KB-5: Retrieval quality monitoring (escalation rate per article, stale detection) — Not built. Depends on KB-2.
KB-6: Cohort analyst proposal ingestion (analyst proposes, human approves, article enters corpus) — Not built. Depends on KB-1, D8.

## D8: Cohort Analyst

CA-1: Snapshot store query (population-level analysis over stored snapshots) — Not built. Depends on VM-6.
CA-2: Intervention effectiveness analysis (which actions correlate with health recovery) — Not built. Depends on OL-5, VM-7.
CA-3: Churn signal discovery (which patterns preceded churn, earliest detection point) — Not built. Depends on VM-7, OL-5.
CA-4: Onboarding pattern analysis (which sequences predict fastest TTV) — Not built. Depends on VM-7, L-2.
CA-5: Expansion pattern analysis (what precedes expansion in successful accounts) — Not built. Depends on VM-7, L-6.
CA-6: System self-diagnosis (false positive rates, modification rates, premature autonomy detection) — Not built. Depends on G-1, OL-5.
CA-7: Proposal generation (new rules, thresholds, playbooks to governance gate for CS leader approval) — Not built. Depends on CA-1 through CA-6, G-1.
CA-8: Product discoverability signal (repeated self-service questions to product team feedback) — Not built. Depends on KB-5, IB-2.

## D9: Eval and Observability

EV-1: Deterministic scorecard with unsafe foils — Built.
EV-2: Quality judge (Sonnet 5, N-run aggregation, determinism probes, drift-power scoped) — Built.
EV-3: Regression system (offline + live lanes, Wilson confidence intervals) — Built.
EV-4: Observability protocols (Tracer, Meter with NoOp defaults) — Built.
EV-5: Live OTel export adapter — Not built. Depends on EV-4.
EV-6: Per-lens eval batteries (scorecard + unsafe foils for Risk, Expansion) — Not built. Depends on L-5, L-6, EV-1.
EV-7: Autonomy health monitoring (outcome quality by action type, drift detection) — Not built. Depends on G-8, OL-5.

## Phased Roadmap

Phase 0 (done): VM-1 through VM-4, DP-1 through DP-4, L-1 through L-4, G-1 through G-5, EV-1 through EV-4.

Phase 1 — First real data, first real output: Salesforce live connector (DP-5 completion, DP-6), snapshot persistence (VM-6), basic trajectory (VM-7), account brief generation (OL-2), live verdict source (G-6). Definition of done: connect to a real Salesforce instance, compute health scores for a real book of business, generate account briefs, present proposals a CSM can approve or reject.

Phase 2 — The CSM's daily workflow: daily digest (OL-1), commitment tracker (OL-5), Gainsight connector (DP-8), Rocketlane connector (DP-9), Risk/Retention lens (L-5, L-8), Risk lens eval battery (EV-6), calendar integration (DP-13, OL-3). Definition of done: the CSM starts their day with the digest, walks into meetings with briefs, has commitments tracked automatically, and the Risk lens detects at-risk accounts with real data.

Phase 3 — Growth and cross-functional value: Expansion lens (L-6, L-7, L-8, EV-6), relationship intelligence connector (DP-10), knowledge base foundation (KB-1 through KB-4), internal bridge feedback aggregation (IB-1, IB-2), QBR narrative generation (IB-5), outcome rail instrumentation (VM-8). Definition of done: the system identifies expansion opportunities with evidence, provides playbook context for Slot B, aggregates feedback weighted by revenue impact, and generates QBR narratives.

Phase 4 — The flywheel: cohort analyst intervention effectiveness (CA-1, CA-2), churn signal discovery (CA-3), onboarding and expansion patterns (CA-4, CA-5), system self-diagnosis (CA-6), cohort to knowledge base pipeline (CA-7, KB-6), feedback loop closure (IB-4), autonomy graduation (G-8, G-9, EV-7), CSM reflection and retrospective (OL-8). Definition of done: the system discovers population-level patterns, proposes improvements through governance, the knowledge base grows from cohort findings, and autonomy for proven action types can be graduated.

Phase 5 — Full operating layer: inbox intelligence (DP-14, OL-4), call summarization (OL-7), activity auto-logging (OL-6), internal bridge full routing and drafting (IB-3), product discoverability signal (CA-8), live OTel export (EV-5), additional connectors Attio billing support (DP-7, DP-12, DP-15). Definition of done: the CSM's inbox is classified, calls are summarized, CRM activities are logged automatically, and internal teams receive structured intelligence.
