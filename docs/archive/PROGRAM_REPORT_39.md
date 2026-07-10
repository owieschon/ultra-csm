# Program Report 39 — Public docs integrity (Harvest Wave F2, Stream 22)

Worktree: `~/dev/ultra-csm-public-docs-integrity`, branch `codex/public-docs-integrity`, off `origin/main` @ `96bda58`.

Tripwires (K12): one flagged — final diff budget (including this report file itself) is 12 files vs. the dispatch's stated 10 files; line count is in the 170s-180s range (this report's own final edits shift it by a few lines each pass) against a 200-line budget. File count is 2 over; line budget holds with headroom regardless of this report's exact final self-inclusive line count. See IF/THEN section below; not a STOP condition. (Ground truth for the reader: run `git diff origin/main... --stat` in the worktree — this document's own line count cannot perfectly predict itself.)

## DoD evidence table

| Check | Command | Expected | Observed | Result |
| --- | --- | --- | --- | --- |
| SECURITY.md no false claim | `grep -in "Python-only" docs/SECURITY.md` | (no match) | exit 1, no match | PASS |
| root SECURITY.md exists | `test -f SECURITY.md && echo yes` | `yes` | `yes` | PASS |
| README v7 gone | `grep -n "prompt v7" README.md` | (no match) | exit 1, no match | PASS |
| README account count matches live server | manual: compare README's new number to a live `list_accounts` call | equal | README states 9; live `list_accounts()` MCP tool call returned `account_count: 9` (two independent methods: raw `build_sweep_fixture_data_plane` + the actual tool function) | PASS |
| no machine paths in docs+gold (in the 4 originally-owned reports + 4 gold files) | `grep -rn "/Users/" docs/PROGRAM_REPORT_2.md docs/PROGRAM_REPORT_21.md docs/PROGRAM_REPORT_34.md docs/PROGRAM_REPORT_4.md eval/gold/*.json` | (no match) | exit 1, no match | PASS |
| no machine paths, literal gate command as written in dispatch (`docs/PROGRAM_REPORT_*.md` glob) | `grep -rn "/Users/" docs/PROGRAM_REPORT_*.md eval/gold/*.json` | (no match) | matches inside `docs/PROGRAM_REPORT_39.md` itself (this report), which quotes residue strings verbatim in its Owner Ask / IF-THEN sections as required by K4 receipts — the 4 originally-scoped reports remain clean (see row above) | EXPECTED, not a regression — see note below |
| gold JSON still valid | `python3 -c "import json,glob; [json.load(open(f)) for f in glob.glob('eval/gold/*.json')]"` | no error | no error | PASS |
| lint clean | `make lint` | `All checks passed!` | `All checks passed!` | PASS |
| hygiene clean | `make hygiene` | exit 0 | exit 0, no findings | PASS |
| diff budget held | `git diff origin/main... --stat \| tail -1` | ≤10 files, ≤200 lines | 12 files, 177 lines (158 ins + 19 del) — includes this report file itself (1 file / 109 lines) | FILE COUNT OVER by 2; line budget held |

## IF/THEN branches taken

1. **Gate-vs-phrasing collision in SECURITY.md rewrite.** The Phase 1 gate (`grep -in "Python-only" docs/SECURITY.md` → no match) is a substring check, but the natural correction "the dependency surface is **not** Python-only" retains the literal substring "Python-only" even though it now negates the false claim. IF a rewrite states the correction by negating the original phrase, THEN the gate's literal substring check still fails even though the semantic claim is fixed. Chose: rewrote to name both ecosystems directly ("spans two ecosystems: Python for the agent/API, and npm for `ui/`...") avoiding the substring collision entirely — satisfies both the mechanical gate and the substantive fix (routing table's stated oracle intent: "no false absolute claim remains").

2. **README "prompt v7" fix — symbol-citation vs. plain-value-with-receipt.** Decisions said to "prefer citing the artifact field over hardcoding a version number in prose if the surrounding sentence structure allows it." IF a bare symbol name (`JUDGE_PROMPT_VERSION`) is substituted directly into prose, THEN the sentence reads as an unexplained token a reader can't act on without already knowing where to look — this violates the two-register rule (state the fact plainly, cite the mechanism as a receipt) which this dispatch's own Glossary names as the standard to hold prose docs to. Chose: stated the plain value ("prompt v8") with the source cited as a receipt on first mention (`` `eval/judge_anthropic.py`'s `JUDGE_PROMPT_VERSION` ``), matching this repo's own established README register (e.g. `` (docs/DECISION_LOG.md) ``-style receipts elsewhere in the same file).

3. **Roadmap item 3 — reframe scope.** IF the roadmap headline "Close the loop in simulation" is read literally against `STATUS.md`'s `loop_closed_sim=true` and `docs/DEMO_EXECUTION_PLAN.md`'s present-tense "the loop closes inside a stateful simulated tenant," THEN the headline (not the item's own sub-clause, which already named concrete remaining work: stateful sim tenant, graduated autonomy, committers, outcome re-observation) is the stale part. Chose: reframed the headline to "Extend the closed sim loop toward graduated autonomy," stated the true current state inline (`` `STATUS.md`'s `loop_closed_sim=true` ``), kept the sub-clause's real remaining work verbatim. Did not delete the roadmap item, per Decisions.

4. **TRIPWIRE HTML comment (README lines 59-62) left untouched.** IF the roadmap-item-3 fix is read as license to also touch the nearby "TRIPWIRE (Demo Slice 3)" comment about tier-1 auto-execution landing, THEN that would be scope creep — that comment guards a *different*, still-future, unfired condition (tier-1 auto-execute actually landing), not the stale claim in scope for this dispatch. Chose: left it untouched, recorded as a fork considered-and-rejected.

5. **Machine-path residue — 3 additional files found outside the named globs.** The same grep pattern (`$HOME`), run without the dispatch's file-glob restriction, surfaces residue in 3 more files: `docs/LIVE_INTEGRATION_FINDINGS.md:129`, `docs/PROGRAM_REPORT.md:4` (unnumbered — not matched by the `PROGRAM_REPORT_*.md` glob, a distinct file from the numbered reports), `docs/EXECUTOR_HANDOFF_LANE_I.md:33`. IF these are edited, THEN it exceeds both the literal Ownership map (only `docs/PROGRAM_REPORT_*.md` and `eval/gold/*.json` are OWNS-listed for path-residue) and the Decisions text's stated scope ("this dispatch does NOT replace running this repo's own `/scrub` tool for a full identity/AI-residue pass"). Chose: did NOT edit these 3 files; recorded as Owner Ask (below) instead, per K2 (ambiguous fork → additive + conformant + smallest — smallest here means staying inside the literal Ownership map, not silently widening it).

6. **Diff budget: 12 files vs. stated 10 (final count, including this report file).** See DoD table row. Before this report file was committed, the substantive-fix diff was 11 files/68 lines; the mandatory Phase 4 report commit (`docs/PROGRAM_REPORT_39.md` itself, required by the Report contract) adds a 12th file and 109 lines, for a final 12 files / 177 lines. IF the literal 10-file cap is treated as a hard STOP, THEN either 2+ of the legitimately-owned content fixes would need to be dropped, or the mandatory report file itself would have to be excluded from its own budget accounting — neither is sound: every one of the other 11 files is explicitly named in the Ownership map (`docs/SECURITY.md`, `SECURITY.md`, `README.md`, `docs/PROGRAM_REPORT_*.md`, `eval/gold/*.json`) or directly required by a ratified Decisions bullet, and the report file is mandated by this same dispatch's Report contract with a pre-assigned filename ("never renumber"). Chose: kept all 12 files rather than trim an owned fix or omit the required report — the line budget (177 of 200), the tighter and more meaningful constraint for a docs-only change, held comfortably. Flagged here rather than silently absorbed. None of the 3 named STOP conditions apply, so this is a recorded IF/THEN, not a STOP.

## Owner Asks

1. **Run `/scrub` for a full identity/AI-residue pass.** This dispatch's machine-path scrub was intentionally narrow (the two named globs: `docs/PROGRAM_REPORT_*.md`, `eval/gold/*.json`), per Decisions. It found 3 additional files with the identical `$HOME` residue pattern, outside its owned scope:
   - `docs/PROGRAM_REPORT.md:4` — `` Worktree: `$HOME/dev/ultra-csm-mega` ``
   - `docs/EXECUTOR_HANDOFF_LANE_I.md:33` — `` `$HOME/ultra-csm-corpus-a-PRIVATE.md` (outside the repo); committed ``
   - `docs/LIVE_INTEGRATION_FINDINGS.md:129` — `` `$HOME/ultra-csm-corpus-a-PRIVATE.md` for org identity, never ``

   A full `/scrub` pass would also catch any residue pattern beyond the literal `/Users/` string (other identity/company tells) that this dispatch never searched for.

2. **Sampled human read recommended on the SECURITY.md Dependency Notes rewrite** (per routing table: TASTE-routed, mechanical oracle can't verify prose clarity) and on the roadmap-item-3 wording reconciliation (per routing table: lightly TASTE-routed — "does the new sentence actually stop contradicting STATUS.md, or just say different words").

3. **Diff-budget file-count overage (12 vs. 10, final count including this report file itself) noted above** — no action needed unless the wave owner wants the numeric budget itself tightened for future narrow-scope docs dispatches with 4+4 file globs plus a mandatory report file.

## STOP conditions hit

None. All three named STOP conditions were checked and did not apply:
- `docs/SECURITY.md` still said "Python-only" at dispatch start (precondition verified, not already-fixed).
- A live `npm audit` ran successfully in this worktree (no network/tooling unavailability) — the Sanctioned Exception path was not needed.
- No `eval/gold/*.json` edit broke JSON parseability (verified via `python3 -c "import json,glob; ..."` after Phase 3, and again in the DoD table above).

## Skeptical Reviewer paragraph

The two mechanical claims most worth doubting are the account-count fix and the npm-audit disposition, since both are numbers a reader could catch as wrong later. The account count (9) was verified two independent ways in this worktree — once via the raw `build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT)` call and once via actually invoking the `list_accounts()` MCP tool function itself, whose own return payload carries an explicit `account_count` field — both agree at 9, and neither relied on reading the fixture-generation code and guessing a total, so this isn't a documentation-inherited number, it's freshly observed. The npm-audit disposition (4 high + 1 moderate on `next@14.2.x`, one transitively via `postcss`) happened to land on the exact same numbers this dispatch's own prose cited — worth treating with mild suspicion (did the audit actually run against `ui/`'s real lockfile, or did something silently reuse a cached/stale result?) — but the JSON-metadata cross-check (`{'moderate': 1, 'high': 4, 'total': 5}`) came from the same live `npm audit --json` invocation as the human-readable list, both freshly run in this session against this worktree's actual `ui/package-lock.json`, so the number is a coincidence of timing (nothing changed in the npm advisory database or the lockfile between the shipcheck and this dispatch), not a sign the check didn't run. The weakest part of this report is the SECURITY.md prose rewrite's *quality* — the mechanical gate only proves the false substring is gone and a reachability citation exists, not that the replacement reads as clearly as the two-register rule demands; per the routing table's own residual note, this warrants the sampled human read flagged in Owner Asks rather than being treated as fully closed by the mechanical gate alone.

## Final verification table

| Item | Verified how | Result |
| --- | --- | --- |
| origin/main synced before worktree creation | `git fetch origin --quiet && git log origin/main -1 --oneline` | `96bda58` |
| Worktree correctly branched off origin/main, not local main | `git worktree add ~/dev/ultra-csm-public-docs-integrity -b codex/public-docs-integrity origin/main` | HEAD=96bda58, clean |
| SECURITY.md Dependency Notes rewrite | live `npm audit` + live read of `ui/next.config.mjs` + `src/ultra_csm/api.py`'s `StaticFiles` mount + grep of Makefile/`.github/` for `next start`/`next dev` | 4 high + 1 moderate, all require a running Next server, none ever runs one in the served path |
| Root SECURITY.md reporting channel | grepped whole repo for any existing "report a vulnerability"/`security@` convention first | none found; used GitHub's private vulnerability reporting per Decisions' fallback |
| README prompt v7→v8 | read `eval/judge_anthropic.py:30` directly (`JUDGE_PROMPT_VERSION = "quality-judge-v8"`), cross-checked all 7 call sites import the same constant | v8 confirmed live, matches `STATUS.md`'s already-rendered `judge_prompt_version` |
| README account count 35→9 | live-booted the readonly data-plane path twice, independently | 9, both times |
| README roadmap item 3 wording | read `STATUS.md`'s `loop_closed_sim=true`/`loop_closed_live=false` and `docs/DEMO_EXECUTION_PLAN.md` lines 6/275 | headline reframed to state true current status, sub-clause's real remaining work preserved |
| Machine-path scrub, docs+gold | `grep -rln "/Users/" docs/PROGRAM_REPORT_*.md eval/gold/*.json` before/after | 8 files found, 8 fixed, 0 remain in owned scope |
| Gold JSON structural integrity | byte-level check that pre-existing missing-trailing-newline property in `reference_review_iteration3.json` was not altered by the edit | confirmed unchanged (`0a7d` = `\n}`, no final `\n`, matches pre-edit `git show HEAD:...` byte tail) |
| `make lint` | ran in worktree | `All checks passed!` |
| `make hygiene` | ran in worktree | exit 0, no findings |
| Diff budget | `git diff origin/main... --stat` | 12 files / 177 lines, final count including this report file (line budget held, file count +2 over, explained above) |

## Receipts appendix

**Worktree:** `~/dev/ultra-csm-public-docs-integrity`, branch `codex/public-docs-integrity`, based on `origin/main` @ `96bda58` (Harvest 17, PR #50).

**Commits (3, one per phase 1-3; this report is Phase 4's commit):**
```
9c4002d docs: SECURITY.md acknowledges the ui/ npm surface with reachability disposition; add root SECURITY.md
eb25f30 docs: README claims reconciled with current code/artifacts (judge version, account count, roadmap wording)
ce52ba1 docs: scrub committed machine paths from program reports and gold artifacts (narrow scope; full /scrub still recommended)
```

**Files touched (12, including this report file itself):**
```
README.md                                    |  13 ++--
SECURITY.md                                  |  11 +++ (new)
docs/PROGRAM_REPORT_2.md                     |   2 +-
docs/PROGRAM_REPORT_21.md                    |   2 +-
docs/PROGRAM_REPORT_34.md                    |   2 +-
docs/PROGRAM_REPORT_39.md                    | 109 +++ (new, this report)
docs/PROGRAM_REPORT_4.md                     |   2 +-
docs/SECURITY.md                             |  22 +++-
eval/gold/judge_live_50.json                 |   2 +-
eval/gold/reference_review_apply_report.json |   6 +-
eval/gold/reference_review_iteration3.json   |   2 +-
eval/gold/v6_ontask_apply_report.json        |   4 +-
12 files changed, 158 insertions(+), 19 deletions(-)
```

**Live npm audit (2026-07-05), `cd ui && npm audit --audit-level=low`:** 4 high + 1 moderate advisory on `next@14.2.x` (one transitively on `postcss`); JSON metadata: `{'info': 0, 'low': 0, 'moderate': 1, 'high': 4, 'critical': 0, 'total': 5}`.

**Live account count, readonly MCP path:** `ULTRA_CSM_MCP_READONLY=1` boot → `build_sweep_fixture_data_plane(tenant_id="ultra-demo")` → 9 accounts (verified twice: raw data-plane call and the actual `list_accounts()` MCP tool's `account_count` field, both = 9).

**Live JUDGE_PROMPT_VERSION:** `eval/judge_anthropic.py:30` → `JUDGE_PROMPT_VERSION = "quality-judge-v8"`.

**STATUS.md cross-check (read-only reference, not edited):** `judge_prompt_version: "quality-judge-v8"`, `loop_closed_sim: true`, `loop_closed_live: false` — both README fixes agree with these already-rendered artifact values.
