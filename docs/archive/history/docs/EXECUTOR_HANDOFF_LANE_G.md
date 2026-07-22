# Executor handoff addendum — Lane G (2026-07-02, archived)

> Historical process record. It does not define current implementation or operating guidance.
> Use the [documentation index](../../../README.md) for current pages.

This was an addendum to `EXECUTOR_HANDOFF.md` (rev 2), with the same §X triggers and one-shot
autonomy contract. Owner-ratified direction: **grow the capability surface without
breaking the safety case.** The governing rule for every task here: a new capability
enters ONLY through the existing registries (action taxonomy + tiers + gate; enumerated,
measured LLM surfaces; declarative config) — anything that would bypass them is out of
scope by definition (§X trigger 6).

Context: Lane E rev 2 has landed (lenses, precedence core, held-actions lane, cohort
packets), triggers and explorer mapping exist. All prerequisites below are on the branch.

---

## G1 — The conversational layer via MCP (do FIRST; mostly demo, minimal build)

**Thesis:** the correct chat interface is NOT conversation inside the governed core — it
is any MCP host acting as the conversational agent over read-only tools. Multi-turn,
memory, and natural language all live in the HOST, outside the trust boundary. The
governed system stays deterministic.

Build steps:
1. **Read-only tool audit.** Enumerate every MCP tool; classify read vs state-changing.
   Add a **read-only access mode**: a conversational token (or `ULTRA_CSM_MCP_READONLY=1`
   for the stdio demo) under which verdict/sweep-triggering tools are absent or refuse.
   Red-path test: the read-only mode structurally cannot approve, verdict, or trigger a
   sweep — the tools error or are not registered, and a test proves it.
2. **Fill read gaps with thin tools** IF (and only if) the demo questions below can't be
   answered from existing tools: candidates are `get_hold_status(account)` (blocking
   refs, held_since, release conditions) and `get_trajectory(account)`. Smallest
   possible additions; deterministic reads over existing data; no new computation.
3. **The demo beat** (script + captured transcript artifact, `claim_boundary: sim`):
   connect an MCP host in read-only mode and ask, live: "Which accounts need me today
   and why?" · "Why is the expansion for <account> on hold?" · "What changed for
   <account> in the last 60 days?" · "Show me what the agent did autonomously this
   week." Every answer must trace to tool outputs (the host narrates; the tools ground).
   Transcript saved under `demo_state/`; a doc section lists which tool calls grounded
   which answer.

**Decision criteria:** IF a demo question needs data no read tool exposes → add the thin
tool (step 2), never widen an existing tool's authority. IF the host confabulates beyond
tool outputs in the transcript → note it in the artifact (that's the host's behavior,
outside our boundary — the artifact documents where our guarantee ends).

**DoD:** read-only mode tested red-path; transcript artifact captured with tool-call
grounding map; QUICKSTART gains a "talk to your book" section (connect any MCP host,
read-only token). No change to gate, tiers, or write paths.

## G2 — Slot A: the classifier slot (trip-wire MET — the corpus now exists)

The §0b condition ("build only when a real corpus proves rules can't classify") is
satisfied by the deep-data layer: free-text case notes and communication signals that no
deterministic rule can read. ONE classification task in this lane (the old discipline
holds): **case-note → `blocker | noise | unknown`.**

- Mirror Slot B's architecture exactly: `agent1/slot_a.py` — fixture classifier
  (deterministic keyword map, CI), live classifier (cred-gated), boundary validator
  (output ∈ enum; cited case id exists and belongs to the account; anything else →
  `unknown`). Versioned prompt file. NO tools, one account, no cross-account visibility.
- Output enters evidence as
  `{case_id, classification, source: "slot_a", model_id, prompt_version}`; the
  deterministic factor logic MAY consume `blocker`-classified cases where it currently
  uses status heuristics — behind a config flag so the change is regression-visible.
- Eval battery FIRST: clear-blocker → blocker; clear-noise → noise; ambiguous →
  `unknown` (never guessed — hard gate `slot_a_unknown_discipline`); injection-in-note →
  classification unaffected, no instruction followed; fixture/live parity on clear
  cases; unsafe foil (a classifier that guesses on ambiguity) fails.
- **Do NOT** add a second classification task (titles→roles etc.) in this lane; note it
  as the next candidate instead.

**DoD:** battery green offline; live path cred-gated; scorecard gains the
unknown-discipline hard gate; `unknown` rate reported in the artifact; factor
consumption flag documented + re-baselined if enabled.

## G3 — Draft iteration (ride the gate's existing `revise` verdict)

The gate already has `approve | deny | revise` with `revised_payload`. Wire the loop the
honest way:
- A `revise` verdict carrying an edit instruction (e.g. "shorter, warmer, drop the
  metric") triggers ONE bounded re-invocation of Slot B: same evidence, same authority
  fields, plus the instruction as a constrained input field (contract validator
  unchanged — the edit cannot add facts, recipients, or commitments; test that a hostile
  edit instruction like "promise a discount" yields a contract-valid draft with no
  commitment, or a refusal).
- The re-run produces a NEW proposal superseding the old (hash discipline — never mutate
  the old payload). **Max ONE automatic re-run per revise verdict**; a second revise on
  the new proposal is another human action; there is no autonomous loop.
- Every (rejected draft, edit instruction, accepted draft) triple is recorded as a
  **preference pair artifact** in the verdict stream — this is gold-set fuel; label it
  as unreviewed preference data, not gold.

**DoD:** revise → superseding proposal round-trip tested incl. hostile-edit red-path;
loop bound enforced by test; preference pairs recorded with provenance; no gate schema
changes.

## G4 — Earned autonomy (measured graduation, owner-ratified, never auto-applied)

Make the "autonomy is earned" claim real:
- `scripts/autonomy_report.py` (or eval module): deterministic per-action-type stats
  from the verdict ledger — N, approve rate, revise rate, rejection reasons, window.
- IF an action type sustains the configured bar (e.g. approve-rate ≥ 0.99 over N ≥ 50 in
  window W — values live in config, stubbed + flagged for owner tuning) → emit a
  **promotion proposal artifact** (action type, evidence, proposed tier change).
  Symmetrically, a rejection spike emits a demotion proposal.
- **The system NEVER applies a tier change.** The artifact is a recommendation; the
  owner edits config; the config change re-baselines regression like any other. Unsafe
  foil: any code path that mutates tier config from the report must fail a test.
- On sim data this demonstrates the MECHANISM (`claim_boundary: sim` — verdict history
  from the demo loop is synthetic); say so in the artifact.

**DoD:** report deterministic + reproducible; promotion/demotion artifacts with full
evidence; auto-apply foil fails closed; config bar documented as owner-tunable stubs.

## Still deferred — conditions restated (do not build in this lane)

- **Evidence-on-demand for slots** — trips only if judge results show drafts failing
  from grounding starvation with the org pack active.
- **RAG over unstructured docs** — trips when a real tenant corpus exists that curation
  cannot cover.
- **Enrichment agents** (external research → typed evidence) — real-tenant era;
  evidence-only provenance lane when it comes.
- **Free tool-calling loops / model-selected effectors / autonomous multi-step
  planning** — never; these dissolve the provable-core claim that is the product.

## Position, ownership, sequence

- **G1 first** (near-free, demo-visible; depends only on the existing MCP server).
  Then **G2 → G3 → G4** — strictly after the current lanes (A–F) are merged and green;
  each is its own eval-first slice with the universal DoD and a push at every stable
  point.
- Files owned: G1 — `mcp_server.py` (read-mode diff + thin tools), demo script/docs;
  G2 — NEW `agent1/slot_a.py` + prompt + battery; G3 — Slot B re-invocation seam +
  verdict-stream artifact module + tests; G4 — NEW report script + artifact + tests.
  Judge-lane files remain owned by the other agent; untouched.
- §X check-in triggers inherit unchanged; the one addition: **any task here that seems
  to need a write-capable tool exposed to the conversational host is automatically §X**
  — that boundary moves only by owner decision.
