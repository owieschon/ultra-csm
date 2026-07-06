# Program Report 25 — Act 1: Golden Corpus into Slot B + Judge-on-Live (Wave C)

Branch `codex/act1-knowledge-judge` off synced `main` (5eb521c). Slot B
(the reason/draft writer) produced boilerplate because the org-knowledge
that would ground it — `knowledge/golden_corpus/*.json` — was loaded onto
`OrgPack` but deliberately not wired into `slot_b_context()`, pending a
selection + token-budget decision. This dispatch made that decision, wired
it, measured the lift with the existing judge (claim-labeled — the judge
is not yet human-validated), and built the plumbing to judge live daily
drafts.

**Tripwires: none crossed.** Spend ≈ $0.70 of the $5 cap (both live phases,
upper-bound estimate — see Receipts). No STOP condition fired. No
pre-existing gate assertion changed value.

## DoD Evidence

| Phase | Result | Evidence |
| --- | --- | --- |
| 0: Bootstrap + baseline | Complete (prior session) | `make eval` baseline 589 passed, 1 skipped; golden corpus 5 files; key-presence check by name only. |
| 1: Deterministic exemplar selection + wiring | Complete (prior session, commit `cffaaf6`) | `select_golden_exemplars()` in `src/ultra_csm/knowledge.py`: disposition→exemplar-kind map, only `"escalate"`→`escalation_email` is unambiguous (`Disposition` has 3 literal values; the other two collapse to `recap_email`, the tone-neutral default — the 3 golden-corpus kinds `kickoff_agenda`/`qbr_narrative`/`renewal_brief` are not reachable from `ReasonDraftRequest`'s current signals, documented as a design gap in the code, not fabricated). Hard cap 2 exemplars, ~1,200-token budget (chars/4 estimator). `OrgPack.slot_b_context(disposition=, recommended_action=)` is additive — zero-arg calls unchanged. Prompt bumped `agent1-slot-b-reason-draft-v2`→`v3`, re-baselined in the same commit (sanctioned exception). Suite 597 passed (+8), authority-invariance + hostile-pack gates re-run green. |
| 2: Judge-scored ablation | Complete (this session, commit `5ea0871`) | `eval/org_pack_ablation.py` + `eval/org_pack_ablation.json`. Same 3 fixture requests drafted twice with the live writer (`claude-opus-4-8`) — corpus-blind `slot_b_context()` vs. disposition-aware `slot_b_context(disposition=..., recommended_action=...)` — judge-scored N=3 per arm (`claude-sonnet-4-6`, reasoning-before-score). `claim_boundary` present verbatim: `"judge not human-validated (kappa pending owner labels); deltas are directional, not proof"`. |
| 3: Judge-on-live plumbing | Complete (this session, commit `4e6a59d`) | `eval/judge_live_csm.py` + `make judge-live-csm` (new target, credential-gated, no scheduler). Advances the Universe v2 35-account book to the anchor's story day (`anchor_day=50`, fixture `as_of=2026-08-10`) via `book_simulator.simulate_book()`, drafts + N=3-judges 3 real narrative accounts (pinehill-transport, meridian-fleet, harborview-fleet — onboarding/expanding/renewal arcs). Exit 0, `eval/gold/judge_live_50.json` written, 3/3 `aggregate_pass=True`. |
| 4: Full regression + report | Complete (this session) | This report. `make eval` 597 passed, 1 skipped — unchanged from Phase 1. Lint/hygiene clean. `git diff --check` / `make status` clean. |

## Selection mapping (Decisions, ratified)

`_DISPOSITION_EXEMPLAR_KIND = {"escalate": "escalation_email"}`,
`_DEFAULT_EXEMPLAR_KIND = "recap_email"`. Built from scratch — neither
`PLAYBOOK_MOTIONS` nor `CSMActionType`'s implied-motion table covered the 5
golden-corpus kinds (`escalation_email`, `kickoff_agenda`, `qbr_narrative`,
`recap_email`, `renewal_brief`), so there was no existing table to reuse.
`kickoff_agenda`/`qbr_narrative`/`renewal_brief` require onboarding-stage,
meeting-cadence, or renewal-proximity signals `ReasonDraftRequest` does not
carry today — extending the map is an additive follow-on once those
signals exist (Owner Ask #1).

## Ablation: 3 side-by-side samples (read with actual eyes)

Full data in `eval/org_pack_ablation.json`. All 3 items show **non-negative**
per-dimension deltas (with-corpus never scores below without-corpus):

- `ablation-acme-escalate` (disposition `escalate`, exemplar
  `escalation_email`): `priority_fidelity` +1 (2→3), all other dimensions
  unchanged at ceiling (3). Without-corpus reason is already grounded and
  on-task; with-corpus adds one clause making priority_fidelity concrete
  ("driving a deterministic priority score of 95 ... escalation to review
  the overdue activation steps").
- `ablation-globex-propose` (disposition `propose_customer_action`,
  exemplar `recap_email`): all 6 dimensions flat (delta 0 across the
  board). Both drafts are grounded, on-task, professional-direct; the
  with-corpus draft adds a subject line and a "come with the specific
  items" concreteness cue matching the recap_email house style, but the
  judge scored both at the same ceiling.
- `ablation-initech-internal` (disposition `internal_review`, exemplar
  `recap_email`): `account_specificity` +1 (2→3). Without-corpus names the
  factors but stays generic ("review the overdue Launch Plan milestones");
  with-corpus adds the specific case-age figure ("case age of 9 days")
  inline in the reason.

No dimension regressed on any item. The lift is small and concentrated in
`account_specificity`/`priority_fidelity` — exactly the two dimensions the
golden corpus's house-style prose (concrete phrasing, named factors) would
plausibly move, and exactly the two that stayed generic in the ablation's
own without-corpus baseline. This is legible directional evidence for the
wiring, not proof — see Skeptical Reviewer Paragraph.

## Judge-on-live: one scored draft (read with actual eyes)

From `eval/gold/judge_live_50.json`, candidate `pinehill-transport`
(disposition `propose_customer_action`, exemplar `recap_email`, anchor day
50 / fixture as_of 2026-08-10):

> **Reason:** "Pinehill Transport shows a success plan that is overdue
> (success_plan_overdue) alongside a yellow health signal (health_yellow),
> plus low seat penetration and a feature depth gap, per the target_date
> field from cs_platform (df3f3e70-...), the status field from crm
> (4e2db753-...), and the health_score field from cs_platform
> (ae0a5970-...). These factors support a proposed customer working
> session to review the overdue Launch Plan milestones and assign owners
> without changing the deterministic priority score of 62."
>
> **Draft:** "Subject: Reviewing your Launch Plan milestones and next
> owners / Hi Dennis, We're seeing a couple of activation signals worth
> working through together: your Launch Plan success plan is currently
> overdue, and the account health has moved into yellow. Before this puts
> your launch timing at risk, I'd like to review the overdue Launch Plan
> milestones (Kickoff, Integration & Data Setup, Activation, or
> Steady-State Handoff) with you and agree on clear owners for the
> remaining activation steps. Would you be open to a 45-minute working
> session? ..."
>
> **Aggregate (N=3):** `grounding_fidelity=3, on_task_relevance=3,
> account_specificity=2, priority_fidelity=3, tone_fit=3,
> safety_boundary=3` — `aggregate_pass=True`, `pass_rate=1.0`,
> `indeterminate=False`.

Grounded (cites real evidence ids, no invented facts), account-named,
concrete ask, correct register. This proves the judge-on-live PLUMBING
works end to end on a real story day for a real named account — it is one
sample, not a claim about draft quality across the 35-account book.

## IF/THEN Branches Taken (this session)

- The dispatch's Phase 2 routing table says "same fixture request set"
  for the ablation → reused `eval/judge_csm.py`'s existing
  `_candidate_request` fixture pattern (3 accounts: Acme Logistics, Globex
  Manufacturing, Initech Finance) rather than inventing new fixture data,
  adding one item with `disposition="escalate"` (not present in
  `judge_csm.py`'s own fixtures) specifically to exercise the
  `escalation_email` exemplar kind alongside the `recap_email` default.
- Phase 3's Decisions text says "collects that day's generated drafts from
  the operating artifacts if present, else generates via the demo path" →
  verified no per-anchor-day operating artifact exists anywhere in this
  repo (checked `~/ultra-csm-corpus-runs/live-reseed-20260704/` — that
  directory holds Gmail/Calendar seed manifests, not Slot B drafts) →
  used the demo path: `book_simulator.simulate_book(base_book,
  day_offset=anchor_day)` wrapped in the existing
  `Fixture{CRM,CSPlatform,ProductTelemetry}Connector` classes (`fixtures.py`),
  the same connector classes `build_fixture_data_plane` already uses for
  any `FixtureCustomerData`, rather than building new connector plumbing.
- Not every narrative account yields a valid Slot B request at day 50
  (`build_reason_draft_request_for_account` returns `None` when a required
  input is absent — e.g. `pinnacle-supply`, `quarrystone-logistics`,
  `aspenridge-supply`, `trailhead-logistics`, `driftwood-warehousing`,
  `windmill-transport` all returned `None` at this day) → verified by
  direct construction against 11 candidate slugs before selecting the 3
  that build successfully (pinehill-transport, meridian-fleet,
  harborview-fleet — onboarding/expanding/renewal arcs), rather than
  guessing or hand-waving account availability.
- Cost receipting: the writer/judge classes do not persist per-call token
  usage in the artifacts (no `CostTracker` wired into either script — out
  of this dispatch's ownership map). Computed a conservative upper-bound
  estimate instead: system-prompt char counts (chars/4, this repo's own
  estimator convention) + actual request/output JSON sizes from the
  written artifacts, assuming the judge's full 700-token CoT budget is
  used on every call (it is not, in practice — this systematically
  overstates cost). Verified the key itself against 2 real API calls
  (`claude-sonnet-4-6`, `claude-opus-4-8`) before any ablation/live spend,
  confirming both model names are valid and billable, not guessed.

## Consolidated Owner Ask

1. **Kappa validation is the real unblock.** Every score in this report
   comes from a judge that has never been checked against human labels for
   THIS wiring (the existing `judge_agreement.json`/`live_semantic_quality.json`
   evidence predates the corpus wiring). A human labeling session against
   `eval/gold/slot_b_quality.jsonl`-style blind labels, extended to cover
   corpus-wired candidates, is the next step to promote these deltas from
   directional to validated.
2. **3-of-5 golden-corpus kinds are unreachable.** `kickoff_agenda`,
   `qbr_narrative`, `renewal_brief` have no live detector or
   `ReasonDraftRequest` signal to key off of. A future dispatch adding
   onboarding-stage/meeting-cadence/renewal-proximity signals to the
   request (or the sweep that builds it) would unlock corpus selection for
   these dispositions.
3. **`judge-live-csm`'s 3 accounts are hand-picked, not a full-book
   sweep.** This proves plumbing for one real story day on 3 named
   accounts; it does not sweep or score the full 35-account book. A future
   dispatch could wire a real per-day work-queue artifact (there is none
   today) that this runner could read instead of always regenerating via
   the demo path.
4. **Cost is estimated, not metered.** Neither `AnthropicReasonDraftWriter`
   nor `AnthropicQualityJudge` as invoked here persist real per-call
   token/cost telemetry to the ablation/judge-live artifacts (the writer
   supports a `cost_tracker` parameter that neither script wired). A
   follow-up could thread `CostTracker` through both scripts for an exact
   receipt instead of the conservative upper-bound estimate used here.

## STOP Conditions

No STOP condition fired. The key (sourced, at the user's explicit
in-conversation instruction, from `~/dev/parts-cs-agent/.env` into this
worktree's `.env` — cross-repo provenance disclosed here per the task's
instruction) was verified live against 2 real API calls before any
ablation/judge-live spend. No wiring path lets corpus/pack content satisfy
an evidence requirement — `_FORBIDDEN_KEYS` and the `boundary` sentence on
`slot_b_context()` are unchanged from Phase 1, and the ablation/judge-live
artifacts show every reason/draft still citing real `evidence` ids, never
exemplar prose, as its factual basis. No authority-invariance or
hostile-pack assertion changed.

## Skeptical Reviewer Paragraph

A reviewer should weigh three real limits. First, the quality lift measured
here comes from an instrument — the judge — that is itself not yet
validated against human labels for corpus-wired candidates; every score in
this report, including the "improved" deltas, is directional evidence that
the wiring doesn't hurt and plausibly helps two specific dimensions, not
proof that it improves quality. The kappa loop (Owner Ask #1) is what would
turn "directional" into "validated." Second, the ablation's own deltas are
small (0 or +1 on a 3-point scale, on 3 items) — this is consistent with
the corpus mattering, but 3 items is not a sample size that would survive
a rigorous significance claim; it is exactly what the dispatch asked for
(3 side-by-sides, human-read), not a statistically powered study. Third,
one live-judged day (3 accounts) proves the judge-on-live PLUMBING works
end to end against a real story day's real narrative data — it does not
prove draft quality at large across the 35-account book, across other
story days, or across dispositions this run didn't sample (only
`propose_customer_action` appeared in all 3 live candidates; `escalate`
and `internal_review` were exercised only in the ablation's fixture set,
not in the live run).

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `597 passed, 1 skipped` (Phase 1 baseline: `597 passed, 1 skipped` — identical; Phase 0 baseline was `589 passed, 1 skipped`, +8 from Phase 1's new selection unit tests) |
| `grep -rl "authority_invariance\|hostile" eval/ tests/` then targeted run | `test_org_context_cannot_change_sweep_authority_or_priority`, `test_hostile_edit_instruction_is_refused_without_commitment`, `test_revise_verdict_refuses_hostile_edit` — `2 passed` (targeted `-k` run; one file covers 2 of the 3 by name overlap) |
| `eval/org_pack_ablation.json` read with actual eyes | 3 items, N=3 per arm, `claim_boundary` present verbatim, all deltas ≥0 |
| `make judge-live-csm` | exit 0; `eval/gold/judge_live_50.json` written; 3/3 `aggregate_pass=True` |
| `grep -i "cost" docs/PROGRAM_REPORT_25.md` | this report's Receipts appendix — total ≈ $0.70 of $5 cap |
| `make lint hygiene` | `ruff check`: All checks passed; `hygiene_scan.py`: exit 0, no output |
| `git diff --check && make status` | both exit 0; `STATUS.md is current` |
| `git status --short` | clean |

## Receipts appendix

- Baseline: Phase 0 `make eval` = 589 passed, 1 skipped (`/tmp/baseline_eval_25.txt`, prior session). Phase 1 (`cffaaf6`): 597 passed, 1 skipped (+8 new selection tests). This session (Phases 2-4): unchanged at 597 passed, 1 skipped.
- Commits this program: `cffaaf6` (Phase 1, prior session), `da90c5e` (BLOCKED marker, prior session, superseded by unblock), `5ea0871` (Phase 2, this session), `4e6a59d` (Phase 3, this session).
- Diff vs synced main (`5eb521c..HEAD`): 13 files changed, 2,493 insertions / 28 deletions. Of these, 3 are generated JSON evidence artifacts (`org_pack_ablation.json`, `judge_live_50.json`, `csm_work_queue.json`/`scorecard_csm.json` re-baseline) and 1 is the now-superseded `BLOCKED.md` (left in git history, not deleted, per K1 disk-truth discipline) — hand-authored code/prompt files are `src/ultra_csm/knowledge.py`, `src/ultra_csm/agent1/{slot_b,sweep}.py`, `docs/prompts/agent1_slot_b_reason_draft_v3.md`, `eval/org_pack_ablation.py`, `eval/judge_live_csm.py`, `tests/test_knowledge.py`, `Makefile` — 8 files, within the 12-file budget read as hand-authored code.
- Cost receipt (upper-bound estimate, see IF/THEN for method): ablation (Phase 2) ≈ $0.45 (6 writer calls + 18 judge calls); judge-live (Phase 3) ≈ $0.25 (3 writer calls + 9 judge calls). **Combined ≈ $0.70 of the $5.00 cap.** Key verified live (2 calibration calls, `claude-sonnet-4-6` + `claude-opus-4-8`, ~$0.0001) before any phase spend.
- Key provenance (disclosed per task instruction): `ANTHROPIC_API_KEY` in this worktree's `.env` was copied, at the user's explicit in-conversation instruction, from `~/dev/parts-cs-agent/.env` (a different repo's credential) — not generated for or scoped to this repo. `.env` is git-ignored (`git status --short --ignored` confirms untracked); never committed.
- Ablation per-item deltas (`eval/org_pack_ablation.json`): `ablation-acme-escalate` `priority_fidelity +1`, all else 0; `ablation-globex-propose` all 0; `ablation-initech-internal` `account_specificity +1`, all else 0. No dimension regressed on any item.
- Judge-live candidates (`eval/gold/judge_live_50.json`, anchor day 50, fixture as_of 2026-08-10): `pinehill-transport` (pass, quoted above), `meridian-fleet` (pass), `harborview-fleet` (pass) — 3/3 `aggregate_pass=True`.
- Merge policy check (K11): `gh api repos/owieschon/ultra-csm --jq .allow_auto_merge` → `false`; `gh api repos/owieschon/ultra-csm/branches/main/protection` → `404 Branch not protected`. Both conditions for `gh pr merge --auto` are unmet, so per K11 the PR is left open with the note "auto-merge pending one-time owner setup" rather than merged directly.
