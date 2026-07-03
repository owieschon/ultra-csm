# Program Report 6 — Close the Loops

Branch `claude/close-the-loops` off `main` (PR #11 + #12 merged), commits
`7a0963c`..`23cfecf`..`a913311` plus this report's commit. Program 4 closed
with a design gap (Owner Ask #2: an onboarding account whose only signal is
delivery slippage is invisible to Agent 1's sweep) and a keystone gate
unproven (`STATUS.md`'s `next_gate`: "Prove live semantic quality on real
tenant output"). This program closes both, adds a live write-back path, and
corrects the demo's positioning.

## DoD Evidence

| Lane | Result | Evidence |
| --- | --- | --- |
| A: lifecycle-aware TTV scoring | Complete | Reproduced the blindness directly (`test_activation_gap_milestone_clears_no_date_based_gap`): a D3-shaped fixture (phase not overdue, one task `at_risk`) clears no date-based gap. Fixed as a new `onboarding_activation_gap` priority factor (`value_model.py`), scored only when `lifecycle_stage == "onboarding"` and gated to phases not already covered by the date-based filter -- a lifecycle-aware weighting, not a global `score>0` loosening (proven by a paired negative test on a `steady_state` company with the identical fixture). Also fixed `derive_ttv_milestones` to prefer a task-level `due_date_actual` over the phase-level one, guarding against the auto-completion-cascade contamination Program 4 found live. The cross-system beat (`tests/test_rocketlane_cross_system_beat.py`) now runs on the D3 (at-risk-cluster) dataset Program 4 had to substitute D2 for, and passes. 9 new tests. Commit `7a0963c`. |
| B: live semantic quality (the keystone gate) | Complete, result is **pass** | Traced `org_pack` wiring end-to-end: it already reaches the live drafting prompt in full (`ReasonDraftRequest.org_context` -> `AnthropicReasonDraftWriter`'s JSON payload) and the v2 prompt (`docs/prompts/agent1_slot_b_reason_draft_v2.md`) already instructs the model to use `voice_rules`/`gap_plays`/`terminology` -- a positive finding, no wiring change needed. Built a 2-account live book from real corpus B (Salesforce) account names fetched live; generated real Slot B drafts with the live model (`claude-opus-4-8`); scored them with the validated N-run judge (cot@5, prompt v7, `claude-sonnet-4-6`) exactly per `docs/DECISION_LOG.md`. Added `eval.judge_validation.live_semantic_quality_status`, deriving the proven/failed claim from the evidence artifact on disk -- never hand-set, same discipline as `judge_validation_status`. Commit `a913311`. |
| C.1: SFDC write-back | Complete, live-executed | `LiveSalesforceActivityCommitter` -- create-only live sibling of `SimCrmActivityCommitter`, same `Committer` protocol, same idempotency-key derivation, same payload-binding check. 5 unit tests against a fake transport (create-only assertion, idempotency, dry-run, action allowlist, non-2xx handling). Then live-executed once, with owner approval: one `Task` (subject `UCSM-P5A ...`) created via `propose -> approve -> commit` on a seeded UCSM-P3E account, count-verified 0 -> 1, ledgered outside the repo. Commit `23cfecf`. |
| C.2: Gmail draft placement | Verified, not newly built | `src/ultra_csm/email_drafts.py` (Program 2) already has the full offline path: `render_email_draft_from_proposal`, `GmailDraftCommitter` (create-only `users.drafts.create`, OAuth refresh, never `.send`), and a test proving no delivery endpoint exists in the module. Re-ran `tests/test_email_drafts.py` (4/4 pass) to confirm. Live placement remains gated on Gmail OAuth credentials (owner ask below); reused rather than rebuilt. |
| D: plot-first curation | Complete | README lede rewritten to BEAT 1 (book-of-business value)/BEAT 2 (live-vendor proof + validated judge)/BEAT 3 (receipts); `docs/TOUR.md` reordered so the operator-morning briefing opens the tour and onboarding is beat two, machinery folded into a "rest of the mechanics" section after the receipts. This report. `make status` confirmed current with no artifact drift. |

## IF/THEN Branches Taken

- Lane A's fix scope was pre-decided by the owner (lifecycle-aware weighting
  in the TTV lens, not a global threshold change) -> implemented exactly
  that: a new `onboarding_activation_gap` factor gated on
  `model.lifecycle_stage == "onboarding"`, with its own threshold
  (`onboarding_activation_gap_points`, config-driven like every other TTV
  factor). Proven not-a-global-loosening by a negative test asserting the
  identical fixture scores nothing outside the onboarding stage.
- The achieved-at contamination guard (Program 4's auto-completion-cascade
  finding) could have added a new field to the shared, frozen
  `TimeToValueMilestone` contract to record which level (phase vs task)
  supplied the achieved date. That widens a contract every other TTV
  consumer depends on for a secondary guard. Instead: the *value* selection
  is fixed (task-level wins when both exist, proven by
  `test_achieved_at_prefers_task_actual_over_contaminated_phase_actual`),
  and the fallback path is proven separately
  (`test_achieved_at_falls_back_to_phase_actual_with_no_task_actual`).
  Documented here as a deliberate scope decision, not a silent gap: the
  contract itself does not carry explicit source-level provenance.
- Lane B discovered `live_semantic_quality_proven` was hardcoded `False` in
  `eval/quality_regression_csm.py`'s offline artifact -- correctly so, since
  that report is explicitly offline/fixture-only mechanics
  (`tests/test_quality_regression_csm.py` asserts the `False` on purpose).
  Rather than overwrite that correct offline claim, a new, additive,
  evidence-derived function (`live_semantic_quality_status`) and a new
  artifact class (`eval/gold/live_semantic_quality.json`) were built
  following the exact same pattern as `judge_validation_status` --
  extending the mechanism the dispatch named, not repurposing an unrelated
  one.
- The live book for Lane B could not use a live CS-platform/telemetry
  connector -- none exists in this architecture (Gainsight/telemetry are
  fixture-only by design). Followed Program 4's cross-system-beat
  precedent exactly: real Salesforce account *names* fetched live, synthetic
  but plausible CS-platform/telemetry evidence layered on top, stated
  explicitly in the artifact's `book_source` field rather than implied as
  more-live-than-it-is.
- Real Salesforce record ids (the numeric object ids on the sentinel
  denylist) were never used as the join key in anything
  persisted -- opaque ids (`corpus-b-live-1`, `corpus-b-live-2`) are the
  join key in the committed live-book artifact; the real ids only ever
  existed transiently in tool output and the local writeback ledger
  outside the repo.
- The live Salesforce write-back was blocked once by the harness's own
  safety classifier (the account id's provenance depended on an
  unseen prior tool call) -- not routed around. Surfaced to the owner via
  `AskUserQuestion`, who approved; the write then executed cleanly
  (0 -> 1 Task, ledgered). A second, unrelated classifier block (broad
  credential-store scanning for `ANTHROPIC_API_KEY`) was also not routed
  around -- the owner named the exact source (`~/dev/parts-cs-agent/.env`)
  and the key was sourced narrowly into the shell environment for this
  session only, never written to a new file on disk.
- `STATUS.md`'s auto-rendering (`scripts/render_status.py`) was not
  extended to surface the new `live_semantic_quality` artifact as its own
  section. `make status` was run and confirmed current (no drift) against
  its existing artifact set, satisfying the stated gate literally; adding
  a new rendered section is scoped out here as a follow-up, not silently
  skipped -- see Consolidated Owner Ask.

## Consolidated Owner Ask

1. **Gmail OAuth credentials.** `ULTRA_CSM_GMAIL_CLIENT_ID`/`_CLIENT_SECRET`/
   `_REFRESH_TOKEN`/`_SENDER` are empty in `~/ultra-csm-live-creds.env`. The
   offline draft-never-send path is fully built and tested
   (`src/ultra_csm/email_drafts.py`, Program 2); live placement needs these
   filled in. OAuth itself must be run by the owner, not this program.
2. **Rocketlane `create_project` capability** (carried over from Program 4,
   still open): no tool in this environment's Rocketlane MCP surface can
   create a new project, and the REST lane remains 401-blocked. Blocks the
   D6 join-set dataset from Program 4's original plan.
3. **`STATUS.md` auto-rendering for `live_semantic_quality`.** The new
   evidence artifact (`eval/gold/live_semantic_quality.json`) and its
   derived claim are real and committed, but `scripts/render_status.py`
   does not yet have a section for it, so `STATUS.md` doesn't surface it
   automatically. A small, scoped follow-up (a `_live_semantic_quality_lines`
   renderer, mirroring `_judge_agreement_lines`) would close this.

## STOP Conditions Hit (and how they were resolved)

- **ANTHROPIC_API_KEY absent** at session start -- per the dispatch's
  explicit allowance, this was the one mid-run ask. The owner pointed to
  `~/dev/parts-cs-agent/.env`; the key was sourced narrowly for the
  session (never written to a new file, never displayed).
- **Live Salesforce write-back blocked by the harness's safety
  classifier** (account-id provenance from an unseen tool call) -- asked,
  owner approved, executed exactly once as scoped (single Task,
  create-only, ledgered).
- **No update/delete anywhere.** No test/threshold/judge gate was
  weakened to pass. No `*_proven` flag was hand-set --
  `live_semantic_quality_proven` is computed by
  `eval.judge_validation.live_semantic_quality_status` from the artifact on
  disk, and it derives `True` on the evidence actually gathered this
  program, not asserted.
- No org-identifying credential or record id appears in any committed
  file (sentinel grep clean on every commit in this program; the real
  Salesforce Task id and Account id exist only in the local writeback
  ledger under `~/ultra-csm-corpus-runs/writeback-20260703/`, outside the
  repo).

## Skeptical Reviewer Paragraph

A skeptical reviewer should note several things this program did NOT do.
Lane B's live proof is 2 candidates, not a statistically powered sample --
"proven" here means the evidence-derivation gate passed on the run actually
performed, not that live semantic quality is proven at scale; a mediocre
`account_specificity` score of 2 (not 3) on the first candidate shows the
judge is not rubber-stamping, but two candidates is a small N. The
CS-platform/telemetry evidence in that live book is synthetic, not fetched
from a live CS-platform -- no such connector exists in this architecture, a
scope boundary stated in the artifact itself, but a reviewer should not read
"live semantic quality proven" as "every input to that draft was live." The
live Salesforce write-back is a single write against a single seeded test
account, not a proven-at-scale production path -- it proves the committer
mechanism works end-to-end through governance, not that it has been
exercised at any volume. Lane A's contamination guard fixes the *value*
Rocketlane's phase auto-completion contaminates, but does not add
schema-level provenance for which level (phase vs task) supplied an
achieved date -- a deliberate, stated scope cut, not an oversight, but one a
future reader relying on `TimeToValueMilestone.achieved_at`'s provenance
should know about. Finally, `STATUS.md` does not yet auto-render the new
live-semantic-quality gate; a reader trusting `STATUS.md` alone as the
single source of truth would miss that this gate now passes until the
follow-up in the Owner Ask lands.

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `467 passed, 1 skipped` (cross-system-beat test skips without live env vars) |
| `LC_ALL=en_US.UTF-8 make lint` | `All checks passed!` |
| `LC_ALL=en_US.UTF-8 make hygiene` | Exited 0 |
| `git diff --check` | Exited 0 (every commit this program) |
| `LC_ALL=en_US.UTF-8 make relational-battery-csm` | `hard_ok: true`, 20/20 seeds |
| `LC_ALL=en_US.UTF-8 make relay-battery-csm` | 11/11 passed |
| `LC_ALL=en_US.UTF-8 make demo` | Passed; `git status --short` clean after (no artifact drift) |
| `LC_ALL=en_US.UTF-8 make status` | `STATUS.md is current` |
| Cross-system beat, live-shaped (D3 payload, env-set locally) | `1 passed` |
| `python -m eval.live_semantic_quality_csm` (live, credentialed) | `proven=True failures=[]`, both candidates' N-run aggregate passed |
| Live Salesforce write-back (live, owner-approved) | Task count 0 -> 1 on the seeded account; ledgered outside the repo |
| Sentinel grep on every staged diff this program | Zero matches, every commit |
