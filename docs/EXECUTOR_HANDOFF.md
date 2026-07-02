# Executor Handoff — current state + next work (2026-07-02, post-dispatch)

The single entry point for the next build session. Supersedes the START HERE block in
`DEMO_EXECUTION_PLAN.md`. Protocol rules (§0 of `DEMO_EXECUTION_PLAN.md`) apply unchanged:
verify-before-building, eval-first, provable-core, claim_boundary on every artifact,
no hand-typed metrics in docs, progress output on long runs, escalate per the table.

---

## A. Verified state (checked on this machine, 2026-07-02)

- **Branch:** `codex/demo-execution-plan`, local **ahead of origin** with the full
  dispatch-session day (HEAD `6b6216f`). Working tree: `contracts.py` modified
  (relationship-graph fields), untracked `run_verification.sh` and `.venv-sandbox/`.
- **Judge lane is separate and protected.** The gold set is owner-approved and the
  semantic-quality judge remains gated. Another agent owns that lane now. Do not edit
  `eval/gold/*`, `eval/judge_*`, rubric anchors, or judge artifacts from this handoff.
- **New surface from the dispatch session** (large; treat as *built-unverified* until
  Task 1 passes): REST API (`api.py`), MCP server (`mcp_server.py`), `cost_tracker.py`,
  `api_metrics.py`, `quality_breaker.py` (+ demo loop), `logging_config.py`,
  `synthetic_book.py` (35 accounts), `book_simulator.py` (365-day mutations),
  `data_simulator.py` (deep per-user/per-case data), `value_model_bridge.py`,
  `snapshot_store.py`, 5 new contract types, org knowledge wired into Slot B (`29cdb18`),
  scorecard 24/24, 224+ non-Postgres tests.
- **Known doc drift to fix (Task 2):** `DEMO_EXECUTION_PLAN §7` still bans surface that
  now exists (API/MCP/cost/metrics — owner-sanctioned expansion).

## B. Task 0 — Git reconcile & push (FIRST, exactly this sequence)

The prior handoff's housekeeping block contained `git reset --hard origin/...` — **DO NOT
RUN IT.** Local is the ahead side; reset --hard orphans the day's work. Instead:

```bash
cd ~/dev/ultra-csm
find .git -name "*.lock" -delete
rm -rf build/tmp/pgdata.*
git branch backup/dispatch-20260702          # insurance; never deleted this session
echo ".venv-sandbox/" >> .gitignore
git add .gitignore run_verification.sh src/ultra_csm/data_plane/contracts.py \
        src/ultra_csm/data_plane/synthetic_book.py docs/EXECUTOR_HANDOFF.md \
        docs/DEMO_EXECUTION_PLAN.md
git commit -m "add relationship-graph contact fields; executor handoff; hygiene fixes"
git push origin codex/demo-execution-plan
# IF push rejected non-fast-forward:
#   git diff origin/codex/demo-execution-plan HEAD   → IF EMPTY (content-identical twin):
#   git push --force-with-lease origin codex/demo-execution-plan
#   IF NOT EMPTY → STOP, escalate with the diff. Do not force.
```

DoD: `git status` clean; local == origin; backup branch exists.

## C. Task 1 — Verification pass (nothing is "built" until this is green)

```bash
bash run_verification.sh          # non-judge by default; RUN_JUDGE_GATE=1 is separate
make eval && make lint && make hygiene && make scorecard-csm && make regression-csm
```
Then the **skeleton-vs-operating audit** of the new surface, by executing entrypoints:
- Boot the API; `curl /health`, `/accounts`, `/sweep`, `/metrics` against the synthetic
  book; confirm responses are real computed data, not stubs.
- Exercise the MCP server's tools once each (fixture mode).
- Run `ucsm demo-book`, `ucsm demo-sweep --day 60 --deep`, `ucsm demo-timeline --deep`,
  and the quality-breaker demo loop.
- IF any surface is scaffolded-not-operating → record it in the artifact/claim_boundary
  and this doc; do NOT silently fix beyond small wiring; escalate anything structural.

DoD: every command above runs green from this checkout; a short verification note
(commands + observed results) committed. Infra + unit tests ≠ operating — this task IS
the operating proof.

## D. Task 2 — Doc reconciliation (kill the drift while it's cheap)

1. Amend `DEMO_EXECUTION_PLAN §7` (scope fence) to OWN the sanctioned expansion: REST
   API, MCP server, cost budgets, API metrics are now in-scope demo surface. Keep the
   rest of the fence (no live-tenant writes, no second UI, no framework extraction).
2. Replace the stale START HERE block in `DEMO_EXECUTION_PLAN.md` with a pointer to this
   file.
3. `eval/deep_vs_shallow_detection.json`: verify it carries a `claim_boundary` stating
   the sim-circularity honestly — the deep sim was *designed* to contain early signals,
   so the comparison demonstrates the mechanism (granular evidence → earlier detection)
   on a synthetic book, **not** a field result. Same wording wherever the
   87.5%/37%-earlier numbers are quoted.
4. Refresh `NEXT_DISPATCH.md`'s "where we are" (artifact-owned numbers only — no
   hand-typed counts; that rule already bit us twice).

DoD: no tracked doc contradicts the codebase; grep for the old fence text returns
nothing; hygiene green.

## E. Task 3 — Complete the degradation ladder (§4.7)

`quality_breaker.py` + demo loop exist (verify in Task 1: deterministic trip on red
artifact, operator-event reset, no LLM in the breaker path). Then verify-or-build the
**slot fallback** half:
- Live Slot B error/timeout mid-sweep → falls back to the fixture writer for that item,
  sweep completes; item carries `draft_mode: "template_fallback"`; artifact carries
  `degraded_items` count.
- Red-path tests: kill the fake live writer mid-sweep → full book completes, N flagged,
  zero lost, zero fabricated; **an unflagged fallback fails the scorecard** (loudness is
  a hard gate).

DoD: both halves proven by tests; scorecard gains the loudness gate.

## F. Task 4 — The timeline demo artifact (the demo centerpiece)

Run the live Slot B writer (org knowledge on) against the top-priority accounts at
timeline snapshots (day 0/30/60/90/120/180/270/365) over the synthetic book. Produce the
"year in the life" digest: real LLM-drafted proposals evolving as the book evolves.
- Credentialed lane; progress output per §0; costs recorded via `cost_tracker`.
- Demo digests MAY store draft text (all data synthetic, PII-free) — **eval artifacts
  keep the no-full-text rule**; don't confuse the two lanes.
- Every digest carries `claim_boundary: sim`.

DoD: the digest artifact + a short runbook line in the demo docs; deterministic spine
identical across re-runs; costs within the configured budget.

## G. Task 5 — Writer model comparison (the migration lane's flagship use)

Opus (current writer) vs Sonnet (candidate) via the **existing paired McNemar migration
lane** on shared cases — judge-scored where the judge is validated, contract-scored
otherwise, and say which is which in the artifact.
- Report discordant counts, p-value, failure clusters, verdict
  (regressed / no-evidence / improved) + cost delta from `cost_tracker`.
- **Claim discipline:** IF the judge is still unvalidated on a dimension, the comparison
  reports that dimension as contract/structural only. No quality claim rides on an
  unvalidated judge.

DoD: migration artifact captured; a one-paragraph recommendation (keep Opus / switch /
insufficient evidence) grounded in the artifact.

## H. Task 6 — Risk + Expansion lenses (eval-first; quality claims gated)

Build as thin projections per the lens protocol — **no evidence re-gathering, no health
re-derivation**; consume the shared model + `snapshot_store` trajectories:
- **Risk lens:** trajectory decline + champion/engagement fragility + renewal proximity
  → internal escalation actions (default authority: internal only).
- **Expansion lens:** sustained health + consumption-vs-entitlement gap + new-department
  activity → gated consult/expansion proposals (strictest customer-facing tier).
- Each lens: eval battery FIRST with unsafe foils (an unsafe placeholder must fail),
  weight-robust ordering fixtures, its own action-taxonomy bindings through the existing
  gate, lens-specific Slot B prompt (versioned).
- **Claim gate:** lens Slot-B *quality* claims wait for judge validation; deterministic
  lens behavior claims may ship on their scorecards.

DoD: two lens scorecards green incl. foil failures; work queue shows multi-lens items on
the same account without conflict (same model fact, two actions).

## I. Owner-gated — do not touch, surface only

1. Judge/labels/rubric/anchors and all judge artifacts. 2. Any push/merge to `main`.
3. Second-labeler recruitment. 4. Anything requiring live tenant credentials or writes
outside sim/`demo_state/`. 5. New runtime LLM surface beyond the two slots.

## J. Sibling repo (parts-cs-agent) — separate lane, brief

Fires committed but **unverified on this machine**; another agent reportedly broke its
eval to 72/93. First action there is verification only:
`python3 -m pytest -x -q && make scorecard-live` (creds), then bisect the 72/93 against
the Fire-2 commits (`autonomy.py`, `loop.py`). Do NOT start Pile-3 hardening until the
battery is green again. Keep the two repos' work in separate commits/sessions.

## K. Sequence

Task 0 → 1 are strictly first and sequential. Then 2 (cheap, unblocks honest docs) → 3 →
4 → 5, with 6 in parallel after 1 if capacity allows. Small commits; universal DoD every
slice; push at every stable point (no more multi-commit unpushed streaks — that's how
today's divergence happened).
