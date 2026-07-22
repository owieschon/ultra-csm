# Executor handoff addendum — Lane E (2026-07-02, archived)

> Historical process record. It does not define current implementation or operating guidance.
> Use the [documentation index](../../../README.md) for current pages.

This addendum superseded the Lane E paragraph in `EXECUTOR_HANDOFF.md` (rev 2). It used the same §X
check-in triggers, same one-shot autonomy contract. Owner has ratified every policy
decision below — none of them are open; implement as written.

**What Lane E is now:** two thin lenses (Risk, Expansion) as *declarations* over the
shared value model, a **cross-lens precedence system** (action suppression with awareness
preservation and re-derivation on release), and **manager cohort packets** (the thin,
deterministic slice of the population analyst). No new evidence gathering. No new health
computation. If a lens needs more than config + bindings + a prompt, stop — that's a
design smell (§X trigger 6).

---

## Position in the plan

- **Depends on:** Lane B merged (trajectory factor), Lane A merged (queue/digest surfaces
  for held-item rendering + cohort packets). Runs concurrently with Lane F (disjoint
  files); IF Lane F merges first, bind the lens triggers listed below; IF Lane E merges
  first, ship lenses sweep-driven and add trigger bindings in the same commit that merges F.
- **Files owned (exclusive):** NEW `agent1/lens_risk.py`, NEW `agent1/lens_expansion.py`,
  NEW `agent1/precedence.py`, NEW `config/precedence_config.json`, lens sections in the
  lens/trigger config files, NEW prompts `docs/prompts/agent1_slot_b_risk_v1.md` +
  `agent1_slot_b_expansion_v1.md`, their tests + eval batteries + fixtures, cohort-packet
  module `src/ultra_csm/cohort_packets.py`. Post-merge single-diff touches allowed to:
  the digest assembly (cohort packets in) and the queue renderer (held section) — smallest
  possible diffs, no logic relocation.

## E1 — The lens protocol (formalize it, then instantiate twice)

A lens IS: `(trigger_subscriptions, factor_weight_profile, action_bindings, prompt_version)`.
Implement a small frozen `LensSpec` and make BOTH new lenses pure declarations over it,
projecting the shared `CustomerValueModel` + `snapshot_store` trajectories. The TTV lens
does not need retrofitting in this lane; note it as a follow-up only.

**Risk lens (internal-only default authority):**
- Trigger subscriptions (when F is live): `renewal_window` (deadline, 90d),
  `band_drop` (event), `champion_inactive` (event) + weekly book sweep.
- Factors (all config-thresholded via the existing resolver, positive-evidence-only,
  full provenance): `trajectory_decline` (from Lane B), `renewal_proximity ×
  health_band`, `champion_fragility` (single-threaded concentration × champion-contact
  inactivity × `StakeholderRelationship` edges), `engagement_collapse`
  (`CommunicationSignal` drop over window), `survey_detractor` (`SurveyResponse` —
  sentiment finally has a typed source; missing survey data → `unknown`, never a
  factor), `billing_friction` (`BillingEvent`).
- Claim discipline (hard): NO churn-probability numbers anywhere — outputs are grounded
  fragility findings + recommended internal plays. A "risk score" is the deterministic
  factor sum, never a probability claim.
- Actions: internal escalation / save-play review (tier per existing taxonomy).

**Expansion lens (strictest customer-facing tier):**
- Preconditions are POSITIVE evidence, enforced before any factor counts: sustained
  healthy trajectory (upward/stable trend from snapshots) AND no active blocker per the
  precedence matrix (E2). Then: `consumption_vs_entitlement` gap, `new_function_activity`
  (person-grain usage appearing in a new org function via `org_level`/contact edges),
  `unrealized_value_prop` (stated outcome, loop completable), `overage_signal`
  (`BillingEvent`).
- Actions: tier-1 internal "expansion-ready" flag (proceeds even under hold, carrying the
  conflict context); customer-facing consult proposal (strictest tier, precedence-gated).

## E2 — Cross-lens precedence (ratified policy; implement exactly)

**Invariant (hard gate + red-path test): suppression is a property of the ACTION, never
the FINDING.** Every active finding renders in queue/digest regardless of holds. A held
item absent from the work-queue artifact FAILS the scorecard.

**Declarative matrix** in `config/precedence_config.json`, same grammar discipline:
```json
{"config_version": "precedence-v1",
 "precedence": [
   {"blocker": "risk",    "blocked": "expansion", "scope": "customer_facing"},
   {"blocker": "ttv_gap", "blocked": "expansion", "scope": "customer_facing"}
 ]}
```
Loader rules (tested): unknown lens ids fail load; `scope` may ONLY name customer-facing
tiers — the schema has no field capable of expressing awareness-suppression, internal
suppression, tier changes, or auto-release-without-evidence; a config attempting any of
those fails load (unsafe-foil test).

**Three-checkpoint conflict evaluation** (mirror the gate's hash re-verify pattern):
1. Propose-time: expansion finding + active blocker → item created directly in
   `HELD(blocking_refs)`, visible with refs, `held_since`, release conditions, override
   affordance.
2. Approve-time: verdict endpoint deterministically REFUSES approval of a held/blocked
   item (re-check against CURRENT state, not creation-time state).
3. Commit-time: committer re-checks before executing.

**Hold state machine:**
- `blocking_refs` is a live set; the authoritative check is always "does ANY active
  blocker match the matrix NOW" — never removal of the original ref alone.
- Release sources: (a) organic — blocker factors clear at an observation/tick;
  (b) human dismissal of the blocking finding — release runs SYNCHRONOUSLY in the
  dismissal handler (instant, no tick wait); (c) authorized override (below).
- **Release = re-derivation, never replay** (ratified): on release, re-run the lens for
  that account against CURRENT state. Outcomes: (i) still valid + unblocked → FRESH item
  (fresh evidence/priority/draft; any old pending proposal is withdrawn as `superseded` —
  the payload-hash binding makes replaying stale payloads structurally impossible; assert
  that in a test); (ii) new blocker active → `HELD(refs=A) → HELD(refs=B)` in ONE ledger
  transition, no `ACTIVE` flash, `held_since` preserved; (iii) opportunity gone →
  closed as `expired` LOUDLY (ledger event + history visibility — endings are never
  silent).
- Implement release as an internal `hold_released` event feeding the Lane F trigger
  pipeline (account-scoped lens re-run) — IF F is unmerged, a direct scoped re-run call
  with the same semantics, swapped to the event when F lands.
- Acted-on ≠ resolved: a risk play being approved/executed does NOT release the hold;
  suppression follows factor evidence only.
- Flap control: state/visibility updates immediately; notifications dedupe via the
  existing cooldown/idempotency machinery. Human dismissal is sticky **per
  factor-instance** (reuse the condition-instance identity); a NEW instance re-holds.
- Multi-blocker: release only when ALL refs clear/dismissed; partial dismissal updates
  refs, stays held. Multiple held items on one account hold independently.
- Asymmetry: nothing ever suppresses Risk. TTV and Risk coexist unsuppressed.

**Dismissal vocabulary (ratified #1):** proposal-backed findings — a `deny` verdict IS
the dismissal. Non-proposal internal findings — add exactly two ledger-style events,
`acknowledge` and `dismiss`, recorded like verdicts (actor, timestamp, target finding,
optional note). Nothing more.

**Override (ratified #3):** an authorized human may release a hold, requiring approve
authority for the BLOCKED action's tier (releasing a hold on a tier-3 action is a
tier-3-adjacent judgment). Overrides name the CURRENT refs — if a new blocker appeared
since the override was drafted, it must be re-issued against the new refs. Justification
required; full ledger provenance.

## E3 — Manager cohort packets (the thin population slice; deterministic only)

Extend the digest with `CohortRollupPacket`s computed by `cohort_packets.py`:
- Segment axes from existing synthetic firmographics (size band, lifecycle stage,
  industry); metrics: health-band distribution + trajectory direction counts per
  segment, divergence-pattern aggregation ("N accounts green-band with declining
  trajectory in segment X" — the health-calibration finding), trigger-firing and
  hold/release counts by cohort, action throughput.
- 100% deterministic aggregation over already-computed data. LLM narration optional and
  bounded exactly as the digest already is (no new metrics, no causal claims).
- **Causation discipline (hard):** packets report patterns, never causes; wording in the
  packet schema uses "associated/observed," never "because/predicts." On the synthetic
  book every pattern is DESIGNED — `claim_boundary: sim` on every packet; this
  demonstrates the mechanism, not findings.

## E4 — Eval batteries (FIRST, per lens + precedence; falsification included)

- Per lens: unsafe foil MUST fail ≥3 hard gates; weight-robust ordering fixtures
  (total-dominance pairs); positive-evidence red-paths (missing survey/billing/person
  data → `unknown`, no factor); authority bindings (Risk cannot emit customer-facing;
  Expansion customer-facing carries strictest tier).
- Precedence battery (from the ratified state machine): creation-into-held;
  approve-refused-while-held; commit-blocked-post-approval; organic release;
  synchronous dismissal release; sticky-dismissal no-re-hold; new-instance re-hold;
  release-with-new-blocker (single transition, no ACTIVE flash); release-with-stale-
  evidence (old proposal superseded, hash intact, fresh item); release-with-opportunity-
  gone (loud `expired`, present in history artifact); multi-blocker partial clear;
  override-with-justification + wrong-tier override refused; flap notification dedupe;
  held-item-visible hard gate; **replay falsification** (a release path re-presenting a
  T0 payload after evidence moved MUST fail); config unsafe foils (awareness-suppression
  / internal-scope / unknown-lens rejected at load).
- Cross-lens fixture: one account active in Risk + Expansion simultaneously — both
  findings visible, expansion customer action held, internal expansion flag proceeds
  with conflict context.
- Claim gate unchanged: deterministic lens claims ship on their scorecards; Slot-B
  quality claims wait for judge validation per dimension.

## Decision criteria (IF/THEN)

- IF a factor needs data the typed contracts don't expose → do not extend contracts in
  this lane; note it in the lane summary.
- IF Lane F is unmerged → sweep-driven lenses + direct release re-run (see E2); trigger
  bindings land with F's merge.
- IF the cross-lens fixture reveals a precedence case not in the E2/E4 lists → implement
  the conservative reading (action stays held, finding stays visible), add the case to
  the battery, and record it in the lane summary; §X only if two conservative readings
  conflict.
- IF tempted to add a probability/prediction to Risk output → STOP (claim discipline).

## Lane E DoD

- `LensSpec` exists; both lenses are declarations over it; `grep` shows no evidence
  gathering or health computation inside lens modules.
- Both lens batteries green incl. foils and ordering fixtures; full precedence battery
  green incl. the replay falsification and config foils.
- Cross-lens fixture renders both findings, one hold, one proceeding internal flag.
- Cohort packets in the digest, deterministic, sim claim-bounded; narration adds no
  metrics.
- Ledger records every hold/release/override/dismissal with provenance (unlogged hold =
  scorecard failure).
- Universal suite + hygiene green; baseline re-baselined only if lens factors changed
  fixture priorities (intended-change note); pushed.
