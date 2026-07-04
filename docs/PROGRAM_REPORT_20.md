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
