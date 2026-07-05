# BLOCKED — Harvest 7: Act 1 Knowledge + Judge

## What's blocked

Phases 2 (judge-scored ablation) and 3 (judge-on-live plumbing) require a live call to the
Anthropic API. `ANTHROPIC_API_KEY` is not present in this session's process environment.

Verified by reading source, not by guessing: both credential-gated call sites --
`eval/judge_anthropic.py`'s `AnthropicQualityJudge.__init__` (line 108-112) and
`src/ultra_csm/agent1/slot_b.py`'s `AnthropicReasonDraftWriter.__init__` (line 174-187) --
construct `anthropic.Anthropic()` with no explicit `api_key=` argument. The Anthropic Python
SDK's documented default behavior is to read `ANTHROPIC_API_KEY` from the process environment
when no key is passed explicitly. Confirmed absent via `env | grep -c "^ANTHROPIC_API_KEY="` ->
`0` (no value inspected or printed, per the no-credential-hunting instruction).

Per this dispatch's own precondition text (07_ACT1_KNOWLEDGE_JUDGE.md, "Preconditions" section):

> Anthropic key present BY NAME ONLY ... If absent: judge/live phases run fixture-only and say
> so; ablation becomes a STOP (it needs the real judge).

And per the dispatch's own STOP conditions:

> ANTHROPIC key absent/invalid (ablation and judge-live cannot run honestly; fixture-judging is
> meaningless -- surface, don't fake).

Per the task's own explicit instruction, I did not attempt to locate or retrieve the key from
`~/ultra-csm-live-creds.env`, keychains, other files, or shell profiles -- only what is already
present in the normal process environment was checked, and it is not there.

## What is NOT blocked, and was completed

Phase 0 (bootstrap + baseline) and Phase 1 (deterministic exemplar selection + wiring) have no
judge/live-API dependency and were completed and committed green, per K8 ("commit green work").
See PROGRESS.md (excluded from git, present at worktree root) for the full ledger.

- Commit `cffaaf6` — "Wire golden corpus into Slot B context (deterministic selection)" on
  branch `codex/act1-knowledge-judge`.
- Full suite: 597 passed (+8 new tests), 1 skipped, 0 failed.
- Authority-invariance and hostile-pack gates specifically re-run and green
  (`test_org_context_cannot_change_sweep_authority_or_priority`,
  `test_hostile_edit_instruction_is_refused_without_commitment`,
  `test_revise_verdict_refuses_hostile_edit`).
- Lint (`ruff check`) and hygiene scan both clean.

## What remains once the key is available

- Phase 2: build `eval/org_pack_ablation.py` per the dispatch's ratified Decisions section
  (same fixture request set, with/without corpus, judge scores both sides N=3 per item,
  claim-labeled artifact with 3 side-by-side samples pulled into the report).
- Phase 3: judge-live runner + Makefile target, one manual run against the current story day
  from `~/ultra-csm-corpus-runs/live-reseed-20260704/anchor.json`.
- Phase 4: full regression + `docs/PROGRAM_REPORT_25.md` with spend receipt (budget: $5 total,
  not yet touched -- $0.00 spent) and the kappa Owner Ask.

## Unblock

Set `ANTHROPIC_API_KEY` in the environment this dispatch runs in, then resume from Phase 2. No
other precondition is unmet; Phase 1's wiring is ready for the ablation to consume immediately.

## Tree state

Working tree is clean (`git status --short` empty) as of this file's writing. No PR opened --
Phase 1 alone is not the dispatch's done-sentence (ablation + judge-live artifacts are required),
so per the task's instruction this stops at BLOCKED.md rather than opening a partial PR.
