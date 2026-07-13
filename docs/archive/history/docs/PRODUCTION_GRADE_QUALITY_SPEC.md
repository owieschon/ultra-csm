# Production-Grade Agent Quality — Spec + Dispatch

<!-- clean-docs:purpose -->
Status: the bar and the path to it. Blinded gold-set candidates, explorer mapping, and the
demo org-knowledge pack/wiring are built; human labels, validated judge, live vertical,
and operations gates remain open. "Production-grade agent quality, full stop."
Date: 2026-06-28.
<!-- clean-docs:end purpose -->

## What "production-grade agent quality" actually means

Not a vibe and not a buzzword list. An agent is production-grade when its **output and
behavior are measured against a human-anchored bar and clear it, under real conditions, at
bounded cost, with the loop closing end-to-end, staying good under change, and trustworthy
to a human who relies on it.** Six pillars, each with a **gate** — a concrete, measurable
condition. Production-grade = every gate green. Anything else is a prototype.

The honesty rule from the whole project carries: a gate is *green* only when an artifact
proves it; mechanics-without-proof is labeled `claim_boundary`, never counted.

---

## The six pillars, each gate, and honest current state

### P1 — Output quality: measured, grounded, clears a bar  *(the heart; currently weakest)*
**Gate:** a **human-validated judge** (κ ≥ 0.6 per dimension vs a labeled gold set) scores
**live** Slot B output at ≥ a target pass-rate across the corpus, with **org-knowledge
grounding active** (voice + product value-props + terminology). A stated number, not a vibe.
**Now:** judge math + ladder mechanics built but **seeded** (`live_semantic_quality_proven:
false`); the 63-record gold label queue exists and is blinded at
`eval/gold/slot_b_quality.jsonl`, with the held-out key at
`eval/gold/slot_b_quality_key.jsonl`; the clean layer has 63/63 owner-approved
single-labeler labels; Slot B prompt v2 now receives the demo org-knowledge pack, but judge
validation, judge-scored ablation, and the live semantic quality run have not been captured.
-> This is the gap that most defines "quality" and it's open.

### P2 — Robustness: good under real, messy, adversarial input
**Gate:** passes the adversarial battery (injection, cross-tenant — already green) **and** a
**data-quality + edge-case battery**: stale/dirty/incomplete/duplicate data, ambiguous
identity, cold-start (no history), conflicting signals → output stays grounded/safe or
degrades to `unknown`/escalate, **never fabricates**. **Now:** adversarial battery exists;
**no data-quality/edge-case battery** — the agent assumes clean typed evidence (audit gap).

### P3 — Reliability & operations: runs reliably, observably, at bounded cost
**Gate:** real observability **on** (per-run latency, error rate, token/cost, drift); **SLOs
defined and monitored**; **runtime fail-closed proven** (source/LLM timeout or outage →
safe degrade, tested); **cost-per-run measured and bounded**; **deploy/version/rollback** for
agent + prompts + config + judge; the **scheduler** runs the sweep on cadence. **Now:**
observability is **NoOp by default**; no cost instrumentation; no SLOs; no scheduler; runtime
degradation designed but not proven. → "Built an agent" ≠ "operate one."

### P4 — The loop closes end-to-end on real data
**Gate:** on **one real vertical** (Attio or SF Dev Edition): real connector →
explorer-mapped config → real data → recommendation → CLI → human approve → **committer
actually sends** (test inbox) → **outcome re-observed**. The whole chain runs once, for real.
**Now:** discovery and source-map proposal/config-freeze mechanics are built; no live-verified
connector; CLI records verdicts only; **no committer sends anything**; no re-observation. The
loop is still open at the live connector, commit, and re-observation joints.

### P5 — Continuous quality assurance: stays good under change
**Gate:** every prompt/model/config change runs **judge-scored** quality regression (real,
not seeded) + structural regression; **model-migration paired McNemar, judge-scored**;
**production drift monitored** (live judge sampling + calibration); **judge-drift monitored**
(the judge is a component that degrades). **Now:** structural regression real; quality
regression **seeded mechanics only**; migration lane scores by contract not judge; no
production drift sampling.

### P6 — Trust & governance: a human can rely on it
**Gate:** **confidence/uncertainty surfaced** per recommendation; evidence-cited (there);
**absence-explainability** ("why isn't my account flagged" — `swept_accounts` exists but
isn't surfaced as an answer); full audit trail (gate/provenance — strong); **human
override + teaching** feeds the suggestions-only feedback loop. **Now:** citation + audit
strong; **no confidence surfacing, no absence-explainability, no feedback/teaching loop**.

---

## The honest boundary (what proof needs creds/labels/deployment)

Three gates cannot be fully *proven* without inputs only you/a tenant provide, and the spec
says so rather than faking them:
- **P1's bar number** needs your **gold-set labels** + a **credentialed live judge run**.
- **P3's cost-at-scale** and **P4's real-tenant loop** need **live credentials**.
So the target splits: **production-grade *ready*** = every pillar built and tested to the
credential/label boundary, verified against recorded real shapes; **production-grade
*proven*** = the gates met with real labels + creds + one live vertical. Build to *ready*
now; *proven* the moment inputs exist. Never label *ready* as *proven*.

---

## Dispatch — workstreams to clear the gates (prioritized)

Each is eval-first, provable-core (LLM stays in the two slots; judge/explorer LLM is
config/eval-lane only), and ships with a machine-readable `claim_boundary`.

**W1 — Output quality (P1), the centerpiece.**
1. Generate gold-set candidates (fixture-mode Slot B outputs) → **built** via
   `make quality-gold-csm`.
1a. Blind the queue -> **built.** Label records use opaque ids, the variant lives in a
   held-out key file, and `quality-gold-status/validate` enforce `blind=true` before judge
   validation. Per [`QUALITY_LABELING_PROTOCOL.md`](archive/history/docs/QUALITY_LABELING_PROTOCOL.md).
1b. **Human labels the blinded set** per the protocol (rubric + blind + self-consistency
   re-label). Labels MUST be human; an LLM judge validated against LLM labels is circular.
2. Validate the judge (weighted Cohen κ >= 0.6/dim, report the 95% CI), + the category
   cross-check (blind labels must separate `control_good` from the intended failure
   categories); gate ships only if both clear.
3. **Build + wire the org-knowledge pack into Slot B** (`knowledge/org_pack.json`: voice,
   product value-props, terminology, gap→play) so output is better. Built for the demo pack
   with authority-invariance and hostile-pack checks; the judge-scored ablation remains
   open.
4. Swap the quality-regression's seeded labels for **real judge scores on real Slot B
   output** across the ladder. Report the live quality pass-rate. -> flips
   `live_semantic_quality_proven` to true.

**W2 — Robustness battery (P2).** A data-quality + edge-case eval: stale/dirty/incomplete/
duplicate, ambiguous identity, cold-start, conflicting signals → assert grounded-or-`unknown`,
never fabricated. Add to the scorecard as hard gates.

**W3 — Operations (P3).** Turn OTel real (latency/error/cost/drift per run); add cost-per-run
instrumentation + a bounded-cost check; prove runtime fail-closed (source/LLM failure eval);
define SLOs; add deploy/version/rollback discipline for agent+prompts+config+judge; add the
scheduler.

**W4 — Close the loop (P4).** Explorer→mapping→config proposal is built; next stand up one
live-verified connector (Attio/SF Dev); one **committer that sends** behind the gate +
consent; outcome **re-observation**. One real vertical, end to end.

**W5 — Continuous QA (P5).** Judge-scored quality regression (real) in CI-adjacent on every
prompt/model/config change; migration paired McNemar **judge-scored**; production drift
sampling + judge-drift monitoring.

**W6 — Trust (P6).** Confidence/uncertainty surfacing; absence-explainability from
`swept_accounts`; the suggestions-only feedback/teaching loop (verdict + outcome → proposed
config changes, human-confirmed).

### Sequence
W1 first (it's the heart and the current weakest; everything else assumes measured quality).
W4 next (closes the loop → makes P3/P6 real to instrument). W5 falls out of W1. W2/W3/W6 round
out. Hold the ordering guard: no pillar's claim upgrades until its gate's artifact exists.

---

## Definition of done — production-grade agent quality

**Ready** (buildable now): every workstream built and tested to the credential/label
boundary; mechanics proven offline with labeled `claim_boundary`; recorded-real-shape
adapters; the loop runnable end-to-end in fixture mode.

**Proven** (the bar, "full stop"):
- **P1:** judge validated κ >= 0.6/dim; live Slot B clears the quality bar with org-knowledge on.
- **P2:** adversarial **and** data-quality batteries green; never-fabricate holds on dirty data.
- **P3:** real observability on; cost-per-run bounded; runtime fail-closed proven; rollback exists; scheduler runs.
- **P4:** one real vertical closes the loop — real data → approve → **sent** → re-observed.
- **P5:** judge-scored quality regression + structural regression gate every change; migration paired+judge-scored; drift monitored.
- **P6:** confidence + absence-explainability surfaced; feedback loop suggests, human confirms, nothing self-tunes authority.

All six green = production-grade. Until then, each pillar states exactly which gate it has
and has not cleared — the same discipline that has kept every claim in this repo honest.

## Owner inputs (the only true blockers)
1. **Gold-set labels** (P1) — the judge cannot validate itself.
2. **Live credentials + a candidate model id** (P3/P4/P5-migration).
3. **Config/knowledge content** (P1 org-knowledge voice sign-off, P3 SLO targets,
   consent/channel policy).
Everything else is buildable to *ready* now.

Current label commands:
- `make quality-gold-csm` regenerates the synthetic label queue.
- `make quality-gold-status-csm` reports labeled/unlabeled/invalid counts.
- `make quality-gold-validate-csm` exits nonzero until every record has valid
  `human_labels`.
