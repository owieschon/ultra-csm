# Program Report 53 — Harvest 32: Surface the reconciliation agent in the ops UI

Branch `codex/reconciliation-ui` off synced `main` (7b4ba71, report 52 /
PR #74 merged, plus the other emitter session's further merges —
including a major `ui/` dependency upgrade, PR #73: Next 14→16, React
18→19, TypeScript 5→6). Report 52 built a reconciliation record
(deterministic divergence/lens signals + an LLM explanation + judge-gated
candidate divergences) reachable only via a raw API call. This dispatch
surfaces it in the ops UI: an expansion inside account detail — no new
view — with a hard visual distinction between deterministic Tier-1
signals and advisory, LLM-hypothesis Tier-2 candidates.

## Tripwires

None. Zero STOPs. IF/THEN count: 2 (well under the threshold of 8).

## IF/THEN branches taken

1. Report 52's live endpoint (`GET /accounts/{id}/reconciliation`) never
   serves `judge_scores` — only the offline battery script
   (`eval/reconciliation_battery.py`) computes and writes those, by
   design (a live judge call on every GET would be the same
   cost/side-effect problem the writer itself was built to avoid).
   The dispatch's Decisions described the drill-down showing judge
   scores "as a secondary, smaller-emphasis line" — this is UNAVAILABLE
   from the live endpoint. Fixed by omitting that line entirely
   (claim/confidence/evidence render; nothing fabricated in its place).
   A smaller drill-down than specified, additive/smallest correction,
   not a STOP.
2. Built `ReconciliationSection.tsx` as one sibling component covering
   both the Tier-1+explanation and Tier-2+drill-down content in a single
   pass, committed as one UI commit rather than mechanically splitting
   identical file content across two commits (the dispatch's own text
   has no stated `Commit:` line for its second phase — an authoring gap,
   same class of gap this wave's other two dispatches also had for their
   final phase).

## Owner Asks

- If judge scores on the LIVE reconciliation view are wanted (not just
  the offline battery artifact), report 52's endpoint would need either
  a cached/precomputed judge pass or an explicit opt-in query param —
  out of this dispatch's scope, named here for a future dispatch.

## STOP conditions hit

None.

## Skeptical Reviewer paragraph

This dispatch SHOWS report 52's reconciliation record within the
existing two views with no new surface and no fabricated data — it does
not add a new view and does not itself judge whether a candidate
divergence is business-correct (that remains report 52's judge gate,
and that gate's score isn't even reachable from this live view — see
IF/THEN #1). This dispatch's own contribution is making the
deterministic-vs-hypothesis distinction legible to a CSM at a glance:
verified via `preview_screenshot` in both dark and light theme, Tier-1
signals render as solid `.factor` cards (the SAME visual language every
other priority factor in this UI already uses), while a Tier-2 candidate
renders in a deliberately different dashed, amber-tinted box labeled
"HYPOTHESIS — NOT VERIFIED" with its confidence and disclaimer visible
as plain text — a CSM could tell the two apart without reading any
source. Because report 52's default `FixtureReconciliationWriter` never
returns a real candidate divergence (by design — no synthetic fixture
data), the Tier-2 path was exercised by temporarily intercepting the
`/reconciliation` fetch response in the browser (client-side JavaScript
only, no file touched, discarded on page reload) with one realistic
candidate, then triggering a fresh render through the real, unmodified
component. This proves the rendering CODE PATH, not that report 52's
live default demo data currently contains a candidate for any given
account — a future dispatch adding a fixture candidate to a bible arc
would be needed to see this in the untouched demo path end-to-end.

## Final verification table

| Check | Command | Result |
| --- | --- | --- |
| Backend zero-drift | `LC_ALL=en_US.UTF-8 make eval` | `728 passed, 1 skipped` before and after — pure UI dispatch, no backend files touched |
| UI builds | `make ui-check` | lint (0 errors, 1 new pre-existing-pattern warning matching `QueueDetail.tsx`'s own established `setState(null)`-in-effect convention), TypeScript, and Turbopack build all green on the upgraded Next 16.2.10/React 19 stack |
| Tier-1 + explanation observed | `preview_start`/`preview_screenshot` against a real work item (Trailhead Logistics) | 7 deterministic signals rendered as `.factor` rows with plain-language labels + which lens(es) surfaced each; explanation rendered with its "AI-written — explanation only" chip + disclaimer text; zero candidates rendered as an honest empty Tier-2 (no fabricated rows) |
| Tier-2 + drill-down observed (both themes) | client-side fetch intercept (temporary, browser-only) + `preview_screenshot` | Tier-2 candidate rendered in the dashed/warm `.hyp-row` treatment, "HYPOTHESIS — NOT VERIFIED" badge, confidence, and disclaimer all visible as text; visual separation from Tier-1 held in both dark and light theme |
| No new view | `grep -rn "route\|<Route\|view=" ui/ --include="*.tsx" --include="*.ts" \| grep -vE "book\|queue"` | only the pre-existing Book/Queue `view` state prop + unrelated `_route`-suffixed label strings; no third view introduced |
| No fake reconciliation data | `grep -rniE "mock\|fake\|placeholder\|lorem" ui/components/ReconciliationSection.tsx ui/lib/api.ts` | no matches |
| Two-register label completeness | observed-behavior pass caught 2 unlabeled factor names (`overdue_success_plan`, `open_expansion_opportunity`) — no automated gate detects this | both added to `TRIGGER_LABELS`, re-verified rendering plain-language text |
| Lint / hygiene / status / clean | `make lint hygiene status && git diff --check` | `All checks passed!` / hygiene exit 0 / `STATUS.md is current` / exit 0 |

## Receipts appendix

- Commit `9911d38` — "Reconciliation UI: Tier-1 signals + explanation +
  Tier-2 hypothesis + drill-down" — 5 files changed, 226 insertions(+):
  `ui/app/globals.css`, `ui/components/QueueDetail.tsx`,
  `ui/components/ReconciliationSection.tsx` (new), `ui/lib/api.ts`,
  `ui/lib/labels.ts`.
- Element → field map (Phase 0, `PROGRESS.md`): Tier-1 rows ←
  `deterministic_signals[]`; explanation + chip ← `explanation.text`/
  `.disclaimer`/`.evidence[]`; Tier-2 rows ← `candidate_divergences[]`
  (minus `judge_scores`, unavailable from the live endpoint — IF/THEN #1).
- New CSS: `.hyp-row`/`.hyp-badge`/`.hyp-claim`/`.hyp-conf`/
  `.hyp-disclaimer`/`.rec-explain` in `ui/app/globals.css`, reusing the
  existing `--warn`/`--warn-dim` tokens (color-as-exception, not a new
  palette).
- Observed-behavior screenshots (ephemeral preview captures, this
  session): Trailhead Logistics real Tier-1 signals + explanation (dark
  theme); Clearwater Field Ops Tier-1 + injected Tier-2 hypothesis, dark
  theme; same, light theme — all three confirm the visual distinction
  and label rendering described above.
- Preview servers used: `reconciliation-ui-api` (port 8014,
  `ULTRA_CSM_DEMO_NOAUTH=1`), `reconciliation-ui-ui` (port 3000 — matches
  `api.py`'s hardcoded CORS `allow_origins=["http://localhost:3000"]`,
  recorded in `~/.claude/launch.json` alongside the other emitter
  session's entries, none removed).
