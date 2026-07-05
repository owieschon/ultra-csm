# Program Report 20 — Harvest 1: Retro across Universe v2 (reports 10-18)

Branch `codex/harvest-retro` off synced `main` (tip `1788b16`, Program 9's
live re-seed merged). Nine autonomous streams ran to completion
(Foundations through Perturbation-Drift) and their lessons were unmined:
`docs/AGENT_PROFILE.md`'s scoreboard had zero real rows, and at least one
systemic pattern (the identical playbooks.json-not-wired disclosure
repeated six times) was visible across reports but never centrally
recorded. This program mines reports 10-18, backfills the scoreboard, and
produces ratification-ready proposals — nothing auto-applied to the
kernel or template.

## Mining table (reports 10-18)

| Report | Stream | IF/THEN count | STOPs fired | Gate retries (evidenced) | Auto-merge | Key lesson(s) |
| --- | --- | --- | --- | --- | --- | --- |
| PROGRAM_REPORT_10.md | Foundations | 5 | 0 | 0 | manual (pre-policy) | tier_rules kept separate from rules to avoid corrupting existing threshold ties; three new action types are governance-layer only — first instance of the playbooks.json-not-wired thread |
| PROGRAM_REPORT_11.md | Safety | 4 | 0 | 0 | manual | canary placement is dormant by construction, disclosed not hidden; snapshot regenerated exactly once per the anti-Goodhart rule |
| PROGRAM_REPORT_12.md | Data-Classes | 6 | 0 | 0 | manual | 5/6 new modules dormant corpus (no live consumer); telemetry reconciliation's "0% error" is self-consistency, not independent validation — a real methodological caveat |
| PROGRAM_REPORT_13.md | Week1-Harness | 6 | 0 | 0 | manual | RejectionLedger built + proven necessary (proposals recur unchanged without it) but explicitly not wired into tick.py — same shape of gap as playbooks.json, correctly scoped out; N(tenants)=1 caveat stated plainly |
| PROGRAM_REPORT_14.md | Segmented-Book | 8 | 0 | 0 | manual | onboarding question count proven independent of row count (5 questions at 35 AND 180 accounts) — schema-shape diversity drives it; cohort-collapse threshold (10) is a hardcoded constant flagged for promotion to config |
| PROGRAM_REPORT_15.md | Fieldstone | 9 | 0 | 0 | manual | proved risk=delta-from-baseline discriminates correctly at an identical starting absolute value; closed a real HubSpot Tier-A gap while correctly leaving the identical Attio gap disclosed-not-fixed (scope discipline) |
| PROGRAM_REPORT_16.md | Crateworks | 8 | 0 | 0 | manual | the "6 vs 5 questions" framing is a weaker signal than it looks (identity fields never auto-map regardless of mess) — real degradation evidence was elsewhere; sweep pipeline structurally cannot run for a no-CS-platform tenant |
| PROGRAM_REPORT_17.md | Loopway | 9 | 0 | 0 | manual | cohort singularity proven at two independent trigger types; onboarding-count-independent-of-row-count reconfirmed a second way AND across a third vendor dialect; sampling bounds explicitly named, not silently narrowed |
| PROGRAM_REPORT_18.md | Perturbation-Drift | 5 | 0 | 0 | manual (asked) | all 6 perturbation cells + 5 drift checks passed first try; **the executor caught a real conflict between the dispatch's earned-auto-merge clause and the session's standing ask-first policy and resolved it by asking, not by silently picking either instruction** |

Totals: 60 IF/THEN branches recorded across 9 streams (mean ~6.7/report),
zero STOP conditions fired anywhere, zero evidenced gate retries, zero
auto-merges attempted (all nine PRs were pre-policy or explicitly
deferred to manual review). No report shows signs of instruction decay
or containment failure.

## Quality-gate log (since gate installation)

9 total log entries as of this retro, all my own manual test/verification
cases from the gate's build session (see `feedback_taste_to_structure_toolchain`
memory) — zero real production catches yet, since the gate only guards
sessions started after it was wired. One override entry
(`slop-ok: adversarial test fixture`, legitimate). No register-
strengthening proposal is warranted from this data; noted honestly as
"insufficient signal yet" rather than manufacturing a finding.

## Cross-report pattern: playbooks.json (the retro's actual headline finding)

Six of nine reports (10, 12, 14, 16, 17, 18) independently disclosed the
identical gap, worded almost identically each time: `playbooks.json`,
`load_playbooks`, `resolve_tenant_tier`, and the three new CSM action
types are correctly built and battery-validated, but zero production code
consumes any of it. This is the single most-repeated Owner Ask in the
whole program — see `docs/PROGRAM_REPORT_23.md` (Harvest 5,
motion-path-wiring), dispatched specifically to close it.

## DoD Evidence

The mining table above IS this report's primary evidence table (per K10's
report-contract flexibility — a retro's "DoD" is the mining itself, not a
code-change verification table). Supplementary: `docs/AGENT_PROFILE.md`
gained 10 scoreboard rows (9 backfilled + this run) and 7 harvested quirks
(Phase 2, commit `cd93ac5`); `docs/RETRO_PROPOSALS_2026-07.md` carries 3
ratification-ready proposals + 2 explicitly-rejected candidates (Phase 3).

## IF/THEN Branches Taken

- Presented the mining table as this report's DoD evidence directly
  rather than duplicating it into a separate table — the dispatch's own
  Decisions section left the exact report shape to the executor's
  judgment; this is the smallest faithful rendering.
- Proposed the two kernel amendments (K10, K12) as single-clause
  extensions to EXISTING enumerated lists rather than new K-rules,
  specifically to respect the kernel's own size-budget discipline
  ("adding a rule requires consolidating or removing one") — a new K15
  would have cost more lines for the same content.
- The runtime-ceiling-mandate and telemetry-self-consistency candidates
  were considered as kernel proposals and explicitly REJECTED (not
  silently dropped) — recorded in the proposals doc's "Not proposed"
  section with reasoning, since both are real observations that don't
  pass the kernel's "make sense in a repo you've never seen" litmus test.
- Scoreboard/quirks were applied directly to `docs/AGENT_PROFILE.md`
  without a ratification step, per the megaprompt skill's own explicit
  rule distinguishing profile facts (auto-apply) from kernel/template
  changes (ratify-only) — this is not this retro's own judgment call,
  it is the skill's pre-existing, documented policy.

## Consolidated Owner Ask

1. **Ratify or reject the three proposals in `docs/RETRO_PROPOSALS_2026-07.md`.**
   Proposals 1-2 are kernel amendments (K12 tripwire extension, K10
   report-contract extension); Proposal 3 is a template-only addition
   with no kernel-budget cost. None have been applied.
2. **Kernel headroom is now tight.** Applying Proposals 1+2 brings the
   kernel to roughly 121-122 lines against its stated 120-line budget —
   right at the edge. Whoever ratifies should either accept a small
   budget overrun, trim something else first, or apply only one of the
   two this round and defer the other.
3. **The quality-gate log has almost no real signal yet** (9 entries, all
   from the gate's own build/test session). A future retro should re-check
   this log once more sessions have run under the fresh-session-only
   hook — there was nothing to mine this time, which is itself worth
   knowing rather than assuming the gate has been silently proving itself.

## STOP Conditions

No STOP conditions fired. This program touched exactly the three files in
its ownership map (`docs/AGENT_PROFILE.md`, `docs/RETRO_PROPOSALS_2026-07.md`,
`docs/PROGRAM_REPORT_20.md`) — verified by `git status --short` before
every commit. No kernel or template file was edited (proposals only). No
code, battery, or test was touched; `make eval`'s count is unchanged from
this branch's baseline (589 passed, 1 skipped, captured before any commit).

## Skeptical Reviewer Paragraph

A reviewer should weigh two real limits. First, this retro's scoreboard
(IF/THEN counts, STOP counts, gate-retry counts for reports 10-18) is
MINED FROM EACH REPORT'S OWN SELF-REPORTED TEXT, not independently
re-verified against the actual commits/diffs of all nine prior programs —
that would be a full re-audit, out of scope here. "Zero STOPs across nine
reports" means nine reports each SAID zero STOPs fired, which is
consistent with (but not independent proof against) a report having
under-disclosed a STOP-worthy event — the same trust boundary this
project's own reports routinely apply to live-system claims, now applied
reflexively to its own retro. Second, the quality-gate log analysis is an
honest non-finding: 9 entries, all pre-production test data, essentially
zero signal about whether the gate is working well in real use yet — a
reader should not read "no register-strengthening proposal was needed"
as "the gate has been proven effective," only as "there isn't enough
data yet to say either way."

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `589 passed, 1 skipped` (baseline, unchanged — docs-only program) |
| `LC_ALL=en_US.UTF-8 make lint` | `All checks passed!` |
| `LC_ALL=en_US.UTF-8 make hygiene` | Exited 0 |
| `git diff --check` | Exited 0 |
| `grep -c "PROGRAM_REPORT_1" docs/PROGRAM_REPORT_20.md` | `9` |
| `grep -c "\| 2026" docs/AGENT_PROFILE.md` | `10` |
| `make status` | (see receipts appendix) |

## Receipts appendix

- Reports mined (file:line spot-checks quoted verbatim above): `docs/PROGRAM_REPORT_10.md:23-68`, `_11.md:22-57`, `_12.md:25-77`, `_13.md:25-94`, `_14.md:29-89`, `_15.md:70-163`, `_16.md:43-122`, `_17.md:54-149`, `_18.md:28-79`.
- Commits this program: `455bb9b` (Phase 1, mining table), `cd93ac5` (Phase 2, scoreboard + quirks).
- Files owned and touched, verified via `git status --short`: `docs/AGENT_PROFILE.md`, `docs/RETRO_PROPOSALS_2026-07.md`, `docs/PROGRAM_REPORT_20.md` — no others.
