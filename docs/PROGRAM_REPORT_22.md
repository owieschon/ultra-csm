# Program Report 22 — Harvest 3: Act 3 Curation

This dispatch curates the repo's front door for the two application audiences the
owner is targeting, using the receipts reports 21 and 24 actually produced: a real
daily operating run over the live 181-account fleetops book, and tick motion
resolution made live in the production sweep. Branch `codex/act3-curation`,
worktree-isolated (`~/dev/ultra-csm-act3-curation`) per this repo's convention.

## Tripwires (K12)

None fired. One real fork was surfaced rather than silently resolved: the dispatch
mission text asserts "the two target roles per `docs/POSITION.md`," but
`docs/POSITION.md` on disk names no roles at all — it is competitive/market
positioning against three vendor classes, not a role-targeting document. Per K1
(disk wins) and the dispatch's own precondition guidance ("if its positioning
predates the four-tenant work, note deltas... it is not owned here"), this was
recorded as a delta rather than silently guessed or fabricated as a quote from
POSITION.md. See IF/THEN section.

## DoD Evidence

| Check | Command | Result |
| --- | --- | --- |
| Suite untouched | `LC_ALL=en_US.UTF-8 make eval` | `610 passed, 1 skipped` — same count as Phase 0 baseline, no test added or removed by this dispatch (docs-only ownership map) |
| Hygiene | `make hygiene` | exit 0, no output (no names, no residue) |
| Lint | `make lint` | `All checks passed!` |
| Readiness no-drift | `make deployment-readiness && git status --short` | `docs/DEPLOYMENT_READINESS.md is current`, empty `git status --short` |
| Links resolve | grep-extracted README/TOUR relative `docs/*.md` and `eval/*.{json,py}` backtick-paths → `test -e` loop | all pass, zero MISSING |
| **Rendered docs seen with eyes (OBSERVED BEHAVIOR)** | `gh api /markdown -f text="$(cat README.md)" -f mode=gfm -f context=owieschon/ultra-csm > /tmp/readme_rendered.html` (same for TOUR), served locally and read top-to-bottom via browser text extraction + raw-HTML inspection | See the 3 observations below — link-checks alone would not have caught the differentiator-paragraph stale claim (Phase 2), which only surfaced by reading the actual rendered document narrative, not by grepping paths |
| Script verified | every `docs/SCREENCAST_SCRIPT.md` command run in order | all green, outputs matched every "Expect on screen" line — see Phase 2 receipts below |
| Collateral exists | `ls ~/ultra-csm-dispatches/collateral/ \| wc -l` | `3` (≥ 2) |
| Clean diff | `git diff --check` | exit 0 |

### Observed-behavior receipts (3 observations, rendered HTML actually viewed)

1. **README's "Where it stands" table renders as a real HTML table**, not broken
   pipe-text: `<markdown-accessiblity-table><table role="table"><thead>...<tbody>` with
   7 correctly-scoped `<tr>` rows, each `Area`/`Status` cell intact including inline
   `<code>` and `<strong>` markup inside cells (e.g. the "LLM quality judge" row's
   κ-threshold prose stays in one cell, doesn't spill into the table structure).
2. **Code fences render as GitHub's syntax-highlighted blocks**, not literal text:
   the "Try it in one minute" `git clone`/`pip install`/`claude mcp add` block renders
   as `<div class="highlight highlight-source-shell"><pre class="notranslate">` with
   `<span class="pl-c">` comment spans — confirms the shell script a reader would
   copy-paste is legible and correctly fenced, not accidentally merged with prose.
3. **The narrative reads coherently top-to-bottom in rendered form**, beat by beat:
   extracting plain rendered text (browser `get_page_text`, not raw markdown) for both
   README and TOUR reproduces the intended plot-first order — morning briefing with
   real report-21 numbers, then the four-tenant readiness claim, then the
   differentiator, then mechanics for README; three explicit beats plus a receipts
   section for TOUR — with no broken cross-reference, no dangling half-sentence from a
   line-wrap, and the DEPLOYMENT_READINESS/DECISION_LOG/PROGRAM_REPORT_21/24 paths all
   appearing as intended in the rendered prose, not just in the source markdown.

Link-checks alone would have passed even with the stale gate-judge claim from Phase 1
(the referenced doc paths were all real) — only reading the rendered narrative against
`docs/DECISION_LOG.md`'s actual current section caught that the claim itself was wrong.
This is the row's whole point: artifact gates cannot see a broken *page*, only a broken
*path*.

## Phases completed

- **Phase 0** — bootstrap: worktree, branch, `PROGRESS.md` (K3), preconditions verified
  (`docs/POSITION.md`, `docs/PROGRAM_REPORT_21.md`, `docs/PROGRAM_REPORT_24.md` present
  on synced main at `9303a12`; `make deployment-readiness` no-drift; `make eval` 610
  passed/1 skipped). No commit (bootstrap only). IF/THEN: fresh worktree had no `.venv`
  (Makefile hardcodes `.venv/bin/python`) — symlinked `~/dev/ultra-csm/.venv` in
  (gitignored, zero repo diff, same interpreter/deps), additive/conformant/smallest.
- **Phase 1** — README + TOUR curation to the pre-ratified beat order (morning
  briefing → four-tenant readiness claim → differentiator → mechanics), citing real
  report-21/24 receipts throughout. Commit `069ed11`.
- **Phase 2** — `docs/SCREENCAST_SCRIPT.md` authored and every command executed in
  order on this branch; caught and fixed a stale gate-judge claim in README's own
  Phase-1 differentiator paragraph while verifying Beat 3's grep target against
  `docs/DECISION_LOG.md`. Commit `2c6bc4b`.
- **Phase 3** — collateral drafts in `~/ultra-csm-dispatches/collateral/` (out-of-repo,
  zero repo diff). No commit (out-of-repo by design).
- **Phase 4** — this report, rendered-doc observed-behavior verification, PR.

## The README/POSITION.md role fork, in full

`docs/POSITION.md` researches and dates a three-vendor-class competitive landscape
(capability, control, measurement vendors) for a prospective **buyer/customer**
audience — it does not name job-application "roles" anywhere in its text. The
dispatch's mission line ("Curate the repo for the two target roles per
`docs/POSITION.md`") does not match what is on disk. Rather than silently invent a
"two roles" quote that isn't there, or silently pick roles with no stated reasoning,
this program:

1. Verified the absence directly: a search of `docs/POSITION.md` for audience/role
   framing (`audience`, `reader`, `buyer`, `reviewer`, the recruiting term the dispatch
   itself did not use) returns one match (the word "buyer" in the EU-AI-Act timing
   paragraph), no role names.
2. Inferred two defensible target roles from (a) POSITION.md's own five-things
   framing — a deterministic engineering core, a self-measuring LLM deployment, and a
   product-positioning discipline, which maps naturally onto both a technical-depth
   angle and a product-judgment angle — and (b) the owner's known job-search context
   (AI/ML engineering, US-remote): **AI/ML Engineer** and **Founding/Applied AI
   Engineer** (product-adjacent).
3. Stated this fork explicitly in every collateral file's header, so the owner can
   redirect the role framing without archaeology.

This is a delta noted, not a POSITION.md rewrite — POSITION.md remains untouched, per
the ownership map's MUST NOT TOUCH list.

## IF/THEN Branches Taken

1. **IF** the fresh worktree has no `.venv` (Makefile hardcodes `.venv/bin/python`)
   **THEN** symlink the main worktree's `.venv` in rather than re-running `make setup`
   from scratch — `.venv/` is gitignored (verified: `git check-ignore`), same
   interpreter/deps, zero repo diff, additive and smallest. Confirmed working:
   `make deployment-readiness` and `make eval` both ran clean through the symlink.
2. **IF** the screencast script's Beat 3 grep target matched a decision that
   `docs/DECISION_LOG.md` itself later supersedes (Sonnet-terse as gate judge) **THEN**
   treat that as a real defect in the just-committed README, not a cosmetic mismatch —
   re-read the doc's "supersedes the entry above" section (2026-07-02): the validated
   gate judge is `cot@5` under 5-run aggregation; `terse@5` was disqualified for 3
   aggregated false negatives on the hard adversarial layer. Fixed both the screencast
   script's grep target/narration and the already-committed README paragraph in the
   same Phase-2 commit, rather than shipping a stale claim forward. README's OWN
   pre-existing "Where it stands" table and `docs/TOUR.md` already said `cot@5`
   correctly — only the new Phase-1 differentiator prose was wrong, confirming the
   error was introduced by this program, not inherited.
3. **IF** `docs/POSITION.md`'s mission-cited "two target roles" framing does not exist
   on disk **THEN** do not rewrite POSITION.md (MUST NOT TOUCH) and do not silently
   invent role names — record the delta in this report (above) and make the inferred
   role choice visible in the collateral files' own headers, so the owner can correct
   it without needing this report as context.
4. **IF** a claim under construction (README differentiator paragraph, first draft)
   cannot be traced to a real, current sentence in `docs/DECISION_LOG.md` **THEN** per
   this dispatch's own STOP condition, soften or replace it — never publish an
   invented-but-plausible specific. First draft claimed "a prompt change... silently
   increased judge-vs-judge disagreement on the adversarial set," which is not
   documented anywhere in `docs/DECISION_LOG.md`; replaced before commit with the real,
   quotable Opus-vs-Sonnet determinism-probe numbers that ARE in the doc.

## Consolidated Owner Ask

1. **Record the screencast.** `docs/SCREENCAST_SCRIPT.md` is verified command-by-command
   but the agent cannot record video — the owner follows the script's beats (~6 minutes
   target) in their own voice.
2. **Voice-pass the collateral drafts** in `~/ultra-csm-dispatches/collateral/` (3
   files: two resume-bullet sets, one cover-note-paragraph set) before using any of
   them in an application — every bullet is DRAFT-labeled and maps to a specific repo
   artifact that should be re-verified current at time of use.
3. **Confirm or redirect the inferred target roles.** This program inferred AI/ML
   Engineer and Founding/Applied AI Engineer from POSITION.md's framing plus known
   job-search context, since POSITION.md itself names no roles — flagged above, not
   silently resolved.
4. **Merge this PR manually if the auto-merge attempt below was denied** by the
   Claude Code harness's tool-permission classifier (expected — confirmed on two prior
   PRs in this same harvest per session context). Gate state is clean; see Merge
   policy section.

## STOP Conditions

None fired.
- Every README/TOUR claim added or revised in this program traces to a committed
  artifact (`docs/PROGRAM_REPORT_21.md`, `docs/PROGRAM_REPORT_24.md`,
  `docs/DEPLOYMENT_READINESS.md`, `docs/DECISION_LOG.md`) — the one claim that
  initially could NOT be traced (the invented "regression caught" framing) was caught
  and replaced before commit, per this dispatch's own STOP condition wording ("either
  find the receipt or soften the claim"). No claim needed softening past
  recognizability; a real, equally strong receipt existed once looked for.
- No edit was needed outside the ownership map — `docs/POSITION.md`,
  `docs/DEPLOYMENT_READINESS.md`, any code, any battery, and `STATUS.md` were read but
  never touched.

## Skeptical Reviewer Paragraph

This curation makes the repo's front door state real, cited claims about a
demonstrated system — it does not make the underlying system more proven than reports
21 and 24 already established. Everything this program says about the daily operating
job is bounded exactly as report 21 bounds it: **one verified manual run**, not
unattended operation; the standing `launchd` schedule remains unloaded, an
owner-authorized action still pending. The "validated judge" claim is bounded exactly
as `docs/DECISION_LOG.md` bounds it: N-run aggregated validation against a
single-labeler gold set, with a second independent labeler explicitly still open — this
curation did not add new judge evidence, it corrected a stale description of existing
evidence. The screencast script is verified at the command level (every command runs
green, in order, with matching output) but that is a mechanical property, not a
qualitative one — whether the resulting recording is *compelling* is explicitly the
owner's taste call, per the dispatch's own routing table, not something this program's
gates can certify. Finally, the two target roles this curation optimized the collateral
drafts for are this program's own inference, not a role-targeting instruction that
existed in `docs/POSITION.md` — a materially different framing than the dispatch
mission text implied, disclosed above rather than silently absorbed.

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `610 passed, 1 skipped, 181.84s` |
| `make hygiene` | exit 0, no output |
| `make lint` | `All checks passed!` |
| `make deployment-readiness && git status --short` | `docs/DEPLOYMENT_READINESS.md is current`; empty |
| README/TOUR link-check loop | zero MISSING |
| Rendered-doc read (README, TOUR) | see 3 quoted observations above |
| Every `docs/SCREENCAST_SCRIPT.md` command, in order | all exit 0, output matched stated expectations |
| `ls ~/ultra-csm-dispatches/collateral/ \| wc -l` | `3` |
| `git diff --check` | exit 0 |
| `git status --short` | empty (pre-final-commit) |

## Receipts appendix

- Commits this program: `069ed11` (Phase 1: README + TOUR curation), `2c6bc4b`
  (Phase 2: screencast script + README gate-judge fix).
- Diff budget: 2 files (Phase 1, 65 insertions/15 deletions) + 2 files (Phase 2, 144
  insertions/9 deletions, one new file `docs/SCREENCAST_SCRIPT.md`) + this report = 5
  files across 2 commits (Phase 3 made zero repo diff by design), well within the
  8-file/700-line diff budget.
- Files owned and touched, verified via `git status --short` before every commit:
  `README.md`, `docs/TOUR.md`, `docs/SCREENCAST_SCRIPT.md`,
  `docs/PROGRAM_REPORT_22.md` — no others. `docs/POSITION.md`,
  `docs/DEPLOYMENT_READINESS.md`, all code, all batteries, and `STATUS.md` were read
  but never edited, per the ownership map's MUST NOT TOUCH list.
- Out-of-repo collateral (never committed, verified via
  `ls ~/ultra-csm-dispatches/collateral/`):
  `resume_bullets_ai_ml_engineer.md`, `resume_bullets_founding_applied_ai_engineer.md`,
  `cover_note_paragraphs.md` — all three DRAFT-labeled, OWNER VOICE PASS REQUIRED.
- Rendered-doc receipts (out-of-repo, `/tmp`, regenerable):
  `/tmp/readme_rendered.html`, `/tmp/tour_rendered.html` (raw `gh api /markdown`
  output), `/tmp/readme_preview.html`, `/tmp/tour_preview.html` (viewer-wrapped copies
  actually opened and read via browser tooling).
- Baseline `make eval` this program started from (Phase 0, synced main): `610 passed,
  1 skipped` — unchanged at Phase 4 (docs-only ownership map, no test added/removed).

## Merge policy

Per this dispatch's own Merge policy section (kernel v1.1 K11): verified mechanics
first. `gh api repos/:owner/:repo --jq .allow_auto_merge` → `true`.
`gh api repos/:owner/:repo/branches/main/protection` → configured (required status
check `eval + CSM scorecard`, not a 404). Both confirm auto-merge mechanics are set up.

Per this dispatch's conditional instruction, `gh pr merge --auto --merge` was run once
the PR (#35) was open and this report's DoD table was clean. Unlike the harness-level
tool-permission denial anticipated for this step (confirmed on two prior PRs in this
harvest per session context), the command was NOT denied this time — it succeeded:
`gh pr view 35 --json autoMergeRequest` confirms `autoMergeRequest.enabledAt` set,
`mergeMethod: MERGE`, PR `state: OPEN`. Auto-merge is armed and will complete once the
required status check (`eval + CSM scorecard`) passes — at report time that check was
`pending` (`gh pr checks 35`), not yet green, so the PR remains open pending CI, not
pending a human merge click. Given the TASTE routing of README/TOUR curation, the PR
body also notes that the owner may want a diff glance regardless of gate state.
