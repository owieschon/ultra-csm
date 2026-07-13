# Retro Proposals — 2026-07 (from Harvest 1, reports 10-18)

Ratification-ready. Nothing here has been applied. Kernel proposals
require explicit owner approval and a kernel version bump per the
megaprompt skill's own rule (`~/.claude/skills/megaprompt/SKILL.md`:
"Kernel edits: only via RETRO ratification"). Profile facts from this
retro (quirks, scoreboard) were already applied directly to
`docs/AGENT_PROFILE.md` in this program's Phase 2 — they are data, not
kernel/template changes, and don't need ratification.

## Proposal 1 — Kernel K12: reconcile dispatch policy against standing
user policy by asking, not silently resolving

**Evidence:** `docs/PROGRAM_REPORT_18.md`, IF/THEN section, final entry —
quoted here verbatim because it is the single best piece of evidence
this whole retro surfaced:

> The dispatch's PR-policy line reads: "Open PR with EARNED AUTO-MERGE:
> if this run had zero STOP events... run `gh pr merge --auto --merge`."
> This run genuinely qualifies — but this session's user has repeatedly,
> explicitly confirmed a standing policy of being asked before any PR
> merge, at every prior wave boundary, with no stated exception for an
> "earned" case → the PR is opened normally, and the user is asked
> whether to invoke the dispatch's earned-auto-merge clause or hold for
> manual review, rather than the agent silently auto-merging a policy the
> user hasn't been asked to confirm applies here too.

**Why this matters generically** (not project-specific — passes the
kernel's own litmus test): any dispatch can carry a written policy that
conflicts with something the SESSION has independently established with
the user. K11 already tells an executor how to check merge MECHANICS
(`allow_auto_merge`, branch protection) before requesting a merge — but
it says nothing about checking for a conflicting STANDING INSTRUCTION
from the user that the mechanics-check can't detect. This gap is real
and will recur with any dispatch-carried policy, not just merge policy.

**Proposed diff** (extend K12's enumerated tripwire list by one clause —
minimal, no new rule, respects the size budget):

```diff
 ## K12. Tripwires (demote to human attention; do not silently absorb)
 Any STOP fired; IF/THEN count exceeds the dispatch's stated threshold
 (default 8); any gate needed >3 retries; diff exceeds the stated budget;
 an irreversible-action class not named in the dispatch's risk posture
-appears; cumulative cost/time crosses 50% of budget with >50% of work
-remaining. A tripwire = demoted merge (K11) + a flagged line at the top
-of the report.
+appears; cumulative cost/time crosses 50% of budget with >50% of work
+remaining; the dispatch's stated policy (merge, autonomy, or otherwise)
+conflicts with a standing instruction the user established earlier in
+this session that the dispatch could not have known about. A tripwire =
+demoted merge (K11) + a flagged line at the top of the report; for a
+policy conflict specifically, ask which policy governs rather than
+picking either side silently.
```

**Cost:** +3 lines to K12 (99→102 lines total kernel length once applied,
comfortably inside the 120-line budget with no consolidation needed this
time — flagging that the budget has ~15 lines of headroom left after
this, so the NEXT kernel proposal after this one likely will need a
real trim).

## Proposal 2 — Kernel K10: cite prior reports' identical disclosures by
number, don't re-derive independently

**Evidence:** six of nine reports (10, 12, 14, 16, 17, 18) independently
disclosed the identical playbooks.json-not-wired gap in Owner Ask
sections, each phrased slightly differently. This is not a defect — each
program correctly disclosed what it found — but `docs/PROGRAM_REPORT_17.md`
(Loopway) shows the better pattern already happening informally: "identical
disclosure to `eval/tier_policy_battery.py`'s own Owner Ask #1." Making
this citation-by-number the DEFAULT rather than the exception would make
future retro mining faster (grep for "same disclosed gap as Report N"
finds the whole thread in one query instead of nine independent reads)
and would make repeated gaps visibly repeated, which is useful signal
in itself — a gap disclosed once is a finding; the same gap disclosed six
times unlabeled looks like six findings until a human reads all nine
reports to notice it's one.

**Proposed diff** (extend K10's report contract with one clause):

```diff
 ## K10. Report contract
 The dispatch names the report file. Sections, in order: DoD evidence
 table (observed numbers, not adjectives) / IF/THEN branches taken (every
-K2 fork) / Owner Asks / STOP conditions hit / Skeptical Reviewer
+K2 fork) / Owner Asks (if a prior report disclosed the same gap, cite it
+by report number rather than re-deriving independently) / STOP conditions
+hit / Skeptical Reviewer
 paragraph (what this work does NOT prove) / Final verification table
 (command + verbatim result) / Receipts appendix (K4).
```

**Cost:** +1 line (net, after reflow). Cheap.

## Proposal 3 — Template: name the eventual production-wiring location
when a dispatch scopes an eval-only resolver

**Evidence:** `docs/PROGRAM_REPORT_14.md` built `eval/tier_policy_battery.py`'s
standalone resolver; `docs/PROGRAM_REPORT_17.md` (Loopway) independently
built its own copy in `eval/loopway_battery.py` rather than sharing the
first one, explicitly disclosed as such in its own IF/THEN ("this file is
NOT in this workstream's ownership map... built Loopway's own..."). Both
decisions were individually correct given each workstream's ownership
map — but the DUPLICATION across two tenants is exactly the shape of
work `docs/PROGRAM_REPORT_23.md` (Harvest 5) now has to consolidate. A
dispatch that scopes "prove the ground truth with a standalone eval
resolver, wire it into production later" should say, at authoring time,
where the future production version will live — so a second tenant
workstream re-uses the plan instead of re-deriving its own copy.

**Proposed diff** (`~/.claude/skills/megaprompt/templates/dispatch_skeleton.md`,
"Sanctioned exceptions" section — add one guiding sentence):

```diff
 ## Sanctioned exceptions (bounded escape valves)
 {Explicit, counted permissions: "AT MOST n of X", "the ONE regeneration
 of Y, in the same commit as its justification". Empty list = state
 "none".}
+
+If this dispatch scopes a standalone eval-only resolver/algorithm that a
+later dispatch will need to promote into production, name the intended
+future src/ location NOW (even if not built now) so a second workstream
+reuses the plan instead of independently re-deriving its own copy.
```

**Cost:** template-only, no kernel-size-budget impact (the skeleton file
has no stated size budget). Low cost, real value given this pattern
recurred exactly once already and is expensive to unwind after the fact
(Harvest 5's Phase 1 exists specifically to undo it).

## Not proposed (considered, rejected)

- **A kernel rule mandating explicit runtime ceilings in every dispatch.**
  Segmented-Book stated a 3-minute ceiling; Perturbation-Drift didn't and
  reported its runtime honestly anyway (188.58s, no target to compare
  against). This is real but task-specific, not universal (a docs-only
  dispatch has no meaningful runtime ceiling) — better as author guidance
  in the template's Phase/DoD sections than a kernel rule. Not proposed
  as a kernel change; noted here so it isn't silently lost, and left as
  an open question for whoever next revises the template wholesale.
- **A stricter kernel rule about telemetry/self-consistency proofs**
  (Report 12's "0% reconciliation error is self-consistency, not
  independent validation" caveat). This is a real methodological point
  but is specific to one workstream's architecture (derived-from-the-
  same-simulator telemetry), not a pattern that generalizes to "any
  repo, any dispatch" — fails the kernel's own litmus test. Left as a
  standing skeptical-reviewer discipline (already covered by K10's
  existing "what this work does NOT prove" requirement), not a new rule.
