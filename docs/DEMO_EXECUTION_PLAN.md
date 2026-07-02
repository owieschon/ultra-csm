# Demo Execution Plan — five slices to the highest-fidelity product demo

Status: the binding execution plan for the demo storyline. Written for implementers:
every step has a reuse inventory, explicit decision criteria (IF/THEN), and a
command-verifiable Definition of Done. Constraint: **simulated systems only** — no live
credentials exist; the loop closes inside a stateful simulated tenant, honestly labeled.
Date: 2026-06-28. Reuse inventory verified against `main` on this date — **re-verify at
execution time; the repo moves fast.**

---

## START HERE — dispatch state as of 2026-07-02

**Judge status** (artifact: `eval/gold/judge_agreement.json`, judge frozen at
`quality-judge-v3`, reference = human-approved definitive labels, 40-card blind re-check
passed 0/40): cleared by point estimate — `grounding_fidelity`, `tone_fit`, clean-layer
`on_task_relevance`, `safety_boundary`, and deterministic `priority_fidelity`. **Still
open:** `account_specificity` (clean 0.42 / hard 0.369) and hard-layer `on_task_relevance`
(0.421). **The Slice-1 iteration budget is exhausted → all further judge/label/rubric
changes are OWNER-GATED. Do not tune the judge, edit labels, or change anchors. The open
dimensions wait for the owner's decision.**

**Unblocked work (proceed without the owner):**
- Slice 2 non-ablation parts: org-knowledge pack + loader + wiring + authority-invariance
  evals (§3). The judge-scored ablation waits for the judge.
- Slice 3 in full, including the degradation ladder (§4, esp. §4.7).
- Slice 4 once Slice 3's sim tenant exists (§5).
- Slice 5's `render_status.py` may land early (§6).

**Companion docs:** `docs/SYSTEM_ARCHITECTURE.md` is a narrative architecture companion,
not the binding execution spec. This file remains the execution plan.

**Doc successor map** (four session docs were consolidated and no longer exist; if you hit
a stale reference, resolve it here): `AGENT1_BUILD_PLAN` → `CUSTOMER_VALUE_MODEL.md`
(provable-core/slots) + this plan; `AGENT1_PRIORITY_FACTORS` → `value_model.py` +
`CUSTOMER_VALUE_MODEL.md` (divergence layer); `SIMPLIFICATION_PLAN` → executed (the cut
landed); `LIVE_REGRESSION_STRENGTHENING_SPEC` → `QUALITY_REGRESSION_EVAL_SPEC.md`.

---

## §0 — Executor protocol (read first, follow always)

1. **Verify before building.** This repo was cloned from another project and heavily
   adapted. Before writing ANY new file or function, run the slice's "Already built"
   verification commands. If the thing exists, extend it. Creating a parallel second
   implementation of an existing capability is a defect, not progress.
2. **Never hand-edit artifact JSONs** (`eval/*.json`, `eval/gold/*`). Artifacts are
   produced only by their make targets. Never hand-type a metric into a doc — quote the
   artifact or use the render script (Slice 5).
3. **Eval-first.** Each slice ships its eval cases and falsification proof BEFORE or WITH
   the feature. A feature without a red-path test is not done.
4. **Provable-core invariant (hard rule).** The LLM runs ONLY in: Slot A, Slot B, the
   eval-lane judge, and config-time explorer mapping. IF a task seems to need an LLM call
   anywhere else → STOP and escalate. Never add an LLM to priority, disposition, gate,
   committer, or the value model.
5. **Claim discipline.** Every new artifact carries a `claim_boundary` object stating what
   it proves and what it does not. Sim-closed-loop results are labeled `sim` — never
   presented as live-tenant results.
6. **Universal DoD (applies to every slice, in addition to its own):**
   ```
   make hygiene                 # exits 0
   make eval                    # all tests pass
   make scorecard-csm           # hard_ok=True
   make regression-csm          # green (re-baseline ONLY when a deterministic change is intended; say so in the commit)
   git diff --check             # clean
   ```
7. **Escalate, don't improvise, when:** a decision matches the Escalation Table (§8); a
   DoD cannot be met after 3 attempts; two architecturally plausible paths exist and the
   plan's decision criteria don't resolve them. Escalation = write the question + the
   evidence + your recommendation; do not silently pick.
8. **Long-running commands report progress.** Any credentialed or multi-sample command
   that can run longer than a minute prints item-level progress (`i/N`, layer/source,
   id) and flushes output. A silent live run is a defect.
9. **Scope fence.** If work is not required by a slice below or by `docs/DEMO_SCRIPT.md`
   (Slice 5), do not build it. The out-of-scope list (§7) is binding.

---

## §1 — Global reuse inventory (verified 2026-06-28; re-verify before each slice)

| Capability | State | Verify with |
|---|---|---|
| Deterministic sweep + value model + TTV lens | BUILT | `make scorecard-csm` hard gates green |
| Gate (proposal→verdict, hash-bound) + `csm_actions` **with tier semantics** (`autonomy_tier` 1/2, `release_condition` incl. `auto_internal_only`) | BUILT | `grep -n autonomy_tier src/ultra_csm/governance/csm_actions.py` |
| Slot B (fixture + live Anthropic writers, contract validator) | BUILT — **no org knowledge** | `grep -n org_context src/ultra_csm/agent1/slot_b.py` → empty |
| Judge (`eval/judge_anthropic.py`, `judge_csm.py`) + diagnosis toolkit (`diagnose_judge.py`, `compare_judges.py`, `judge_nrun.py`, `determinism_probe.py`) | BUILT — **κ not cleared** | `cat eval/gold/judge_agreement.json` |
| Gold sets: clean 63 (9 variants × 7, blinded, draft labels **pending human approval**) + hard layer + keys + status/validate gates + labeling helper (`eval/label_gold.py`) | BUILT | `make quality-gold-status-csm` |
| Quality regression ladder + no-op control (offline mechanics) | BUILT | `make quality-regression-csm` |
| Two-lane structural regression + live N=30 contract capture + paired McNemar machinery | BUILT | `make regression-csm` |
| Connector smoke + schema explorer (5 sources, cred-gated, fail-clean) | BUILT — discovery only; mapping→config NOT wired | `PYTHONPATH=src:. python -m ultra_csm.cli connectors explore attio_crm` (no creds → clean missing-env report) |
| CLI | ONLY `connectors smoke|explore` — **`proposals` commands DO NOT exist** | `grep -n add_parser src/ultra_csm/cli.py` |
| Committers / send mechanism | **DO NOT EXIST** | `grep -rn Committer src/` → only gate/authorizer hits |
| `agent_wikis/` org-knowledge | **DELETED in simplification** — greenfield | `ls agent_wikis` → gone |
| `sim/` directory | PARTIAL survivor of the cut — contents unverified | `ls sim/; find sim -name '*.py' \| head` — implementer MUST inspect before deciding reuse-vs-build in Slice 3 |
| Outcome rail | `realized_state` hardcoded `not_instrumented` | `grep -n not_instrumented src/ultra_csm/value_model.py` |

---

## §2 — Slice 1: Judge κ diagnosis & fix *(blocks the quality story; do first)*

**Goal:** all six dimensions reach weighted κ ≥ 0.6 vs approved human labels, with
hard-layer `overall_pass_false_negative == 0`, without Goodharting the judge.

**Current facts:** `judge_agreement.json` clean layer: on_task 0.761, safety 1.0 pass;
grounding 0.185, specificity 0.286, tone 0.386, priority 0.394 FAIL. Reference = draft
labels pending human approval → the κs are provisional.

**Iteration counter:** the first blind agreed-cell audit returned 8/10. The misses were
classified as rubric ambiguity, so the grounding-vs-safety and grounding-severity anchors
were clarified and `judge_prompt_version` was bumped. The next judge agreement run is
iteration 1 of 3 and must be paired with a fresh agreed-cell audit sample.

Iteration 1 returned a fresh audit pass (`10/10`) plus a bucket table over 261 disagreeing
cells. The decisions and implementation response are recorded in
[`QUALITY_JUDGE_ADJUDICATION.md`](QUALITY_JUDGE_ADJUDICATION.md). Iteration 2 moves
`priority_fidelity` to deterministic scoring, clarifies grounding/specificity/tone, and
adds the non-conflation rule.

**Steps + decision criteria:**
1. Generate a **disagreement report** (extend `eval/diagnose_judge.py` if it doesn't
   already emit this): for each failing dimension, every item where judge ≠ draft label,
   showing text + both scores + judge rationale. Purpose: make the human label review fast.
   It also emits a separate blind agreed-cell audit: score those cards before opening the
   key. If the audit does not match at least 90%, widen review beyond disagreement rows.
2. **OWNER GATE:** the human reviews/approves the draft labels using the report
   (`make quality-gold-label-csm` flow). Review protocol: read request/output + rubric,
   decide the score first, then read the judge reason. No κ conclusion is valid before
   this.
3. After approved labels, re-run `make judge-agreement-csm`. For each still-failing
   dimension, classify every disagreement into exactly one bucket:
   - **(a) Label error** — label contradicts the rubric anchor → human fixes label.
   - **(b) Rubric ambiguity** — two readings both defensible under the anchor text →
     tighten the anchor wording in the rubric + protocol doc; labels re-checked against
     the tightened anchor.
   - **(c) Judge systematic error** — judge consistently misreads one *category* (e.g.
     rewards length, misses uncited claims) → revise the judge prompt with a **category-
     level** instruction. FORBIDDEN: item-specific rules in the judge prompt ("for
     accounts named X…"). Bump `judge_prompt_version`; re-run full agreement.
   - **(d) Dimension conflation** — two dimensions score near-identically or one has too
     little variance for stable κ → propose merge/redefinition. OWNER GATE (changes the
     quality contract).
   - **(e) Candidate rendering defect** — the generated text does not visibly exhibit the
     intended flaw → regenerate the candidate. Do not fix this by changing labels or judge
     prompt.
4. **IF** all six dims ≥ 0.6 AND hard-layer false_neg = 0 → capture artifact, update
   `claim_boundary.judge_validated=true`, done.
   **IF** any dim < 0.6 after **3** classify-fix-rerun iterations → STOP; escalate with
   the per-iteration κ table and bucket counts. Do not keep tuning (Goodhart guard).

**DoD:** `make judge-agreement-csm` artifact shows all dims ≥ 0.6 (report κ + N per dim),
hard-layer false_neg 0, `judge_prompt_version` recorded; disagreement report committed;
misconduct guard test: judge prompt contains no gold-set-item-specific text (add a test
that greps the judge prompt for gold-set account names → must be absent); blind agreed-cell
audit committed with a separate key.

**Do NOT:** average κ across dimensions; validate against the held-out key and call it
human validation; edit gold labels yourself (human-only); tune the judge and the labels in
the same iteration (change one variable at a time).

**Decision point:** if adjudication shows `priority_fidelity` disagreement is mostly
mechanical factor/score mismatch, move that dimension to a deterministic scorer and shrink
the judge's remit to semantic scoring. Do the same for any purely structural slice of
grounding that can be checked without model judgment.

---

## §3 — Slice 2: Org-knowledge pack + live Slot B in the demo path

**Goal:** Slot B output becomes genuinely good — grounded in product value-props,
terminology, and voice — and the demo path runs the real model.

**Already built / reuse:** Slot B request/writer seam (`ReasonDraftRequest`,
`AnthropicReasonDraftWriter`), contract validator, versioned prompt pattern
(`docs/prompts/`). **Greenfield:** the knowledge content and its loader (`agent_wikis/`
was deleted — do NOT resurrect the old wiki module; build the minimal new thing).

**Build:**
1. `knowledge/org_pack.json` (or `.md` set) — ONE versioned artifact: product value-props
   (the sim product's), terminology, voice/tone rules, gap→play map. Content is for the
   **simulated product**; mark `fictional: true` in the pack metadata.
2. A loader (`src/ultra_csm/knowledge.py`, ~small): validates schema, exposes
   `load_org_pack() -> OrgPack`, carries `pack_version`.
3. Wire into Slot B as `org_context` in the request payload + prompt section. Rules:
   org_context may shape LANGUAGE and play selection; **operational claims still require
   evidence ids** (existing validator unchanged). Bump Slot B `prompt_version` →
   re-baseline regression (intended change; say so in commit).
4. Evals (extend existing suites, don't create parallel ones): **authority invariance**
   (a hostile/absurd org pack cannot change priority, disposition, recipient, or consent
   — hard gate); **citation preserved** (pack facts don't count as evidence); **ablation**
   (judge scores with-pack > without-pack on specificity/tone — run via judge once Slice 1
   clears); **hostile pack** (pack containing injection text is neutralized).

**Decision criteria:** IF a pack field would let the LLM assert a customer-specific fact
not in evidence → that field is forbidden; packs hold product/org knowledge only.
IF pack content needs real-company info → STOP (fictional sim product only).

**DoD:** loader tested (schema-invalid pack fails closed); the four evals green; a
side-by-side artifact (`eval/org_pack_ablation.json`, judge-scored, claim-labeled)
showing the quality lift; `make demo-slot-b` (or equivalent) runs live Slot B with pack
when `ANTHROPIC_API_KEY` present and falls back to fixture cleanly when absent.

**Do NOT:** add RAG/retrieval (§0b trip-wire stands); put the pack on the runtime spine's
deterministic path (it feeds Slot B only); hand-author pack content that contradicts the
sim tenant's fixture facts.

---

## §4 — Slice 3: The loop closes in sim — stateful tenant, committers, tiered autonomy, re-observation

**Goal:** `make demo-loop` runs end-to-end offline: sweep → tier-1 actions auto-execute
into the sim tenant → tier-2/3 wait at the gate → human approves via CLI → committer
"sends" → next sweep re-observes the changed state → outcome rail records a realized
outcome labeled `sim`.

**Already built / reuse (verify each):** gate + verdicts (hash-bound, idempotent);
`csm_actions` tiers + `auto_internal_only` release condition — **read `gate.py` and follow
its existing release semantics**; fixture connectors (`data_plane/fixtures.py`);
`sim/` remnants — INSPECT first (§1): IF `sim/` contains a usable stateful store, extend
it; ELSE build `src/ultra_csm/data_plane/sim_tenant.py` and leave `sim/` untouched.

**Build:**
1. **Stateful sim tenant:** a mutable, seeded, deterministic store behind the SAME
   data-plane Protocols the fixtures implement (fixture connectors stay for CI; sim-tenant
   connectors are selected by the demo config). State persists across sweeps within a
   demo run (file-backed JSON under `demo_state/`, gitignored).
2. **Committer port** (`src/ultra_csm/committers.py`): `Committer.commit(approved_proposal)
   -> CommitReceipt`. Two implementations, both sim: `SimCrmActivityCommitter` (writes
   activity into sim tenant) and `SimOutboundCommitter` (appends to `demo_state/outbox.jsonl`
   — the "inbox"). EVERY commit: loads an APPROVED proposal, re-verifies payload hash via
   the gate's binding check, uses an idempotency key (re-commit = no-op), writes an audit
   event, supports `--dry-run`.
3. **Tier-1 auto-execution:** actions whose spec says `auto_internal_only` flow
   proposal → auto-verdict (actor = system principal, recorded like any verdict) →
   committer. IF `gate.py` already has an auto-release path, use it; IF NOT, add one that
   writes the SAME proposal+verdict rows (never bypasses the ledger). Tier-2/3 remain
   human-gated — no exceptions, enforced by the existing hard gates.
4. **CLI:** add `proposals list|show|approve|reject` subcommands to the existing
   `src/ultra_csm/cli.py` parser (do NOT create a second CLI entry point). Approve/reject
   writes the verdict through the gate API.
5. **Re-observation + outcome:** after commits, the demo advances the sim clock; the next
   sweep reads mutated state; where a previously-open milestone is now met, the outcome
   rail sets `realized_state="known"` with provenance `source="sim"` — and the value-model
   change is visible in the new work queue. Update the `usage_outcome_unverified`
   divergence accordingly.
6. **Eval:** extend the CSM scorecard with the loop's hard gates: tier-2/3 NEVER
   auto-execute (existing gate, now exercised through committers); commit without approved
   verdict = impossible (red-path test); idempotent re-commit; re-observation changes the
   model only via real sim-state change (no fabricated outcomes).
7. **Degradation ladder (the "worse, not wrong" mechanism).** Because correctness lives in
   the deterministic spine and the LLM supplies only quality, runtime LLM failure must
   degrade output quality — never correctness, never coverage. Two pieces, both small:
   - **Slot fallback policy:** IF the live Slot B writer errors, times out, or exhausts its
     retry budget mid-sweep → fall back to `FixtureReasonDraftWriter` for that item and
     continue the sweep. The affected item carries `draft_mode: "template_fallback"` (vs
     `"live"`) in the work item AND the sweep artifact carries a top-level
     `degraded_items` count. Reuse the existing writer seam — do NOT build a new
     writer or a retry orchestrator; ONE fallback rung is the design (the spine carries
     correctness, so more rungs are resilience theater).
   - **Quality circuit breaker (deterministic policy, human reset):** a config stanza in
     the existing policy domain: IF the quality-regression artifact is red (or, later, the
     production drift signal fires) → customer-facing draft actions revert to
     template/internal-review until an operator clears the breaker (a recorded verdict-like
     event, not an env flag). The breaker rule is deterministic code reading a
     deterministic artifact — NO LLM involvement in the breaker decision, ever.
   - **Loudness rule (hard):** degradation is always flagged — on the item, in the
     artifact, in the demo output. A silent fallback is a defect equal to fabrication:
     add a red-path test that a fallback WITHOUT the flag fails the scorecard.

**Decision criteria:** IF a committer would need to touch anything outside the sim tenant
/ `demo_state/` → STOP (that's the live lane, out of scope). IF the auto-verdict design
requires a new principal/permission → follow the existing roster/SoD pattern in
`governance/`; the system principal must NOT hold tier-2/3 approve permission. IF tempted
to add multi-provider failover, retry storms, or self-healing → STOP; the single
fallback-to-deterministic rung + breaker is the complete design.

**DoD:** `make demo-loop` runs offline, deterministic, twice → identical end-state
artifacts; scorecard extended gates green; the outcome rail shows a `sim`-labeled realized
outcome; `claim_boundary`: `loop_closed_sim: true, loop_closed_live: false`.
**Degradation DoD:** a red-path eval kills the (fake) live writer mid-sweep → the sweep
completes the full book, N items flagged `template_fallback`, zero items lost, zero
fabrication, hard gates green; the unflagged-fallback red-path test fails closed; the
breaker trips on a red quality artifact and requires an operator event to clear.

---

## §5 — Slice 4: Slot A — one real classification at the messy edge

**Goal:** the agent visibly *interprets* messy input: free-text support-case notes →
`blocker | noise | unknown`, feeding the existing case-evidence path.

**Already built / reuse:** the Slot A contract is fully specified in
the provable-core section of `docs/CUSTOMER_VALUE_MODEL.md` (constrained output, mandatory `unknown`, no tools, one
account). The sim tenant (Slice 3) supplies the messy free-text notes.

**Build:** `src/ultra_csm/agent1/slot_a.py` mirroring Slot B's architecture exactly:
fixture classifier (deterministic keyword map for CI) + live Anthropic classifier +
boundary validator (output ∈ enum, cited case id exists, `unknown` on anything else).
Classified result enters evidence as `{case_id, classification, source="slot_a",
model_id, prompt_version}` — the deterministic factor logic may then use
`blocker`-classified cases where it currently uses case-status heuristics.

**Evals:** clear-blocker → blocker; clear-noise → noise; ambiguous → `unknown` (never
guessed); injection-in-case-text → classification unaffected + no instruction followed;
fixture/live parity on the clear cases. Falsification: an unsafe classifier that guesses
on ambiguous input fails the eval.

**Decision criteria:** Slot A classifies ONLY case-note text in this slice. IF tempted to
add a second classification task (titles→roles etc.) → out of scope; note it in the
roadmap doc instead.

**DoD:** evals green offline (fixture path); live path cred-gated like Slot B; scorecard
gains the `slot_a_unknown_discipline` hard gate; `unknown` rate reported in the artifact.

---

## §6 — Slice 5: `DEMO_SCRIPT.md` + docs render from artifacts

**Goal:** the 10-minute reviewer path, and the end of hand-typed numbers.

**Build:**
1. `scripts/render_status.py` → generates `STATUS.md` from the artifacts ONLY
   (scorecard, regression, judge agreement, quality regression, gold status, demo-loop
   receipt): every number, κ, gate state, and claim_boundary — rendered, never typed.
   Add `make status` and a CI check: regenerate → `git diff --exit-code STATUS.md`
   (stale STATUS fails the build).
2. Sweep the 21 docs: every hand-typed metric either (a) replaced by a pointer to
   STATUS.md/the artifact, or (b) tagged with the commit hash it was true at. New rule in
   §0 of NEXT_DISPATCH: docs quote artifacts, they don't restate them.
3. `docs/DEMO_SCRIPT.md` — three acts, exact commands + expected output per beat:
   Act 1 messy-data-in (sim tenant dirt, Slot A classifies, guards refuse to fabricate);
   Act 2 decide-draft-act (sweep, divergence surfaces, Slot B live w/ org pack, tier-1
   auto-executes, tier-3 approved in CLI, committer delivers to outbox);
   Act 3 the-system-tells-the-truth (re-observation, outcome recorded `sim`, judge scores
   the draft, planted degradation caught, STATUS.md regenerated live — **and the
   degradation beat:** kill the live-writer key mid-sweep, the agent finishes the full
   book with items loudly flagged `template_fallback`, correctness intact; "worse, not
   wrong," demonstrated live per §4.7).
   Each act lists which artifacts a skeptical reviewer should open.

**DoD:** a fresh clone + `make setup && make demo-loop && make status` reproduces the
script's expected outputs; CI stale-STATUS check active; zero hand-typed current-state
metrics remain in active docs (spot-check: grep for `κ`, score counts, `%` in docs/ and verify
each is rendered or hash-tagged).

---

## §7 — Hard out-of-scope (do not build; do not "quickly add")

Lenses 2/3 · Agent 4 (incl. friction→content facet) · real/live connectors beyond the
existing recorded-shape + smoke boundary · any UI beyond the CLI · scheduler, SLOs,
cost dashboards · framework extraction · multi-tenant · RAG / conversational memory /
autonomous tool-calling (§0b trip-wires unchanged) · Rocketlane account-join (still an
owner decision) · any writes outside `demo_state/` + repo artifacts.

## §8 — Escalation table (owner-gated decisions)

| Decision | Owner because |
|---|---|
| Gold-label approval + any label change (Slice 1) | Human ground truth — implementer must never author labels |
| Dimension merge/redefinition (Slice 1, bucket d) | Changes the quality contract |
| Judge still <0.6 after 3 iterations | May require rethinking a dimension, not more tuning |
| Default tier assignments per action type (Slice 3) | Autonomy policy = values call |
| Any new runtime LLM surface | Provable-core invariant |
| Org-pack voice/content final review (Slice 2) | It is the org's voice, even fictional |
| Anything touching real external systems | No creds; live lane is closed |

## §9 — Execution order & parallelism

Slice 1 first (blocks Act 3 and the Slice-2 ablation). Slice 3 may proceed in parallel
with Slice 1 (disjoint files). Slice 2 after Slice 1's judge clears (its ablation needs a
valid judge) — its non-judge parts (pack, loader, wiring, authority evals) may start
anytime. Slice 4 after Slice 3's sim tenant exists. Slice 5 last, but `render_status.py`
may land early (it only reads artifacts). Every slice: small commits, universal DoD, push.
