# Executor handoff — three-bucket scope, lane-parallel (2026-07-02, archived)

> Historical process record. It does not define the current branch, work queue, or operating
> guidance. Use the [documentation index](../../../README.md) for current pages.

This was the single entry point for the July 2 work window. It superseded rev 1 and the START
HERE block in `DEMO_EXECUTION_PLAN.md`. Its protocol rules required verify-before-build,
eval-first, provable-core, claim_boundary on every artifact, no hand-typed metrics,
progress output on long runs.

**Mission scope (owner-ratified):** make the repo simultaneously (a) the strongest demo
artifact and (b) genuinely adoptable by a startup that brings its own credentials — with
NO live tenant access on our side. Everything below is buildable with zero external
credentials except `ANTHROPIC_API_KEY` (Lane C only). Live-tenant anything stays out.

**One-shot autonomy contract:** execute this handoff end-to-end without checking in,
EXCEPT on the check-in triggers in §X. Every decision an executor might face has a
criterion below; if you hit one that genuinely isn't covered, that is itself a §X trigger.

---

## §S. State ledger (verified on this machine, rev-2 cut)

- Branch `codex/demo-execution-plan`, local == origin at `acbcd44`; backup branch exists.
- DONE + verified (see `docs/OPERATING_PROOF.md`): git reconcile; operating audit of the
  API/MCP/CLI/demo surface; degradation ladder BOTH halves (slot fallback
  `template_fallback` + loudness scorecard gate + quality breaker).
- DONE + verified: year-in-life digest (`eval/year_in_life_digest.py` + Makefile target).
  Live demo artifact writes to `demo_state/year_in_life_digest.json` and records cost in
  the artifact; full draft text stays out of tracked eval artifacts.
- Judge lane is OWNED BY THE OWNER's separate session: do not edit `eval/gold/*`,
  `eval/judge_*`, rubric anchors, labels, or judge prompts. Additive NEW artifact files
  from Lane C (new filenames only) are the sole exception.
- Doc drift remaining: `DEMO_EXECUTION_PLAN §7` fence vs shipped API/MCP surface (Lane D4).

## §P. Parallelization plan

Five lanes with **exclusive file ownership** — no lane touches another lane's files, so
they cannot conflict. Integration happens by merge order (§M).

| Lane | Owns (exclusive) | Depends on |
|---|---|---|
| **A — API surgery** | `api.py`, `mcp_server.py`, `cli.py`, new `_api_helpers.py`, their tests | nothing |
| **B — Core loop close** | `agent1/sweep.py`, `snapshot_store.py`, their tests, `baseline_csm.json` refresh | nothing |
| **C — Cred lane (sequential inside)** | `eval/year_in_life_digest.py`, NEW eval artifacts/files only | `ANTHROPIC_API_KEY`; C4 prefers judge-validated dims |
| **D — Adoption kit** | `data_plane/explorer.py`, `source_maps.py`, config files, NEW `committers.py`, `QUICKSTART.md`, `scripts/render_status.py`, doc fixes | nothing |
| **E — Lenses** | NEW `agent1/lens_risk.py`, `agent1/lens_expansion.py`, their eval batteries + fixtures | B merged (uses trajectory) |

**Dispatch criteria:** IF the harness supports parallel sub-agents with isolated git
worktrees → run A, B, C, D concurrently (max 3 heavy agents at once on this machine;
C counts as heavy), E after B merges. IF NOT → sequential order: finish C1 → A → B → D →
C2–C4 → E. NEVER run two agents in one shared working tree (lock/commit races). Each lane
commits only its owned files; anything else it needs changed → §X trigger.

## §M. Merge & verification protocol

1. Merge order: C1 is done; next merge order is A → B → D → C2–C4 → E.
2. After EACH merge: `make eval && make lint && make hygiene && make scorecard-csm &&
   make regression-csm` + `git diff --check` → push. No unpushed multi-commit streaks.
3. Regression re-baseline is allowed ONLY for Lane B's intended deterministic change and
   must say so in the commit message.

---

## Lane A — API surgery (Bucket 1: trust repairs)

**A1 — Dedupe.** Extract the duplicated logic (`_score_one_account`,
`_build_account_brief`, ~400 LOC) into `src/ultra_csm/_api_helpers.py`; both `api.py` and
`mcp_server.py` import it. Pure refactor: byte-identical endpoint responses (assert via
existing tests before/after).
**A2 — Authentication + real principals.** Decision is made; implement exactly this:
- Env `ULTRA_CSM_API_TOKENS` = comma-separated `token:display_name` pairs. Any
  state-changing endpoint (verdicts, sweep trigger) requires `Authorization: Bearer
  <token>`; the verdict is signed by the principal mapped to THAT token (created
  deterministically on first use via the existing principal machinery) — **delete the
  server-held authority principal.** Read-only GETs stay open.
- Demo mode: `ULTRA_CSM_DEMO_NOAUTH=1` restores tokenless local demo with a loud startup
  banner + `auth: demo-noauth` in `/health` and every artifact it touches.
- MCP: stdio transport = local-operator trust, documented as such in the server docstring;
  IF an HTTP transport exists, it requires the same bearer token. Verdict-capable MCP
  tools take the token → principal identically.
- Rename inherited principal/display names in these files to CS-domain names (e.g.
  `csm-approval-authority`); grep both files for other inherited-domain names and rename.
- SoD invariant (test it): the orchestrator/server principal holds PROPOSE only; approve
  authority exists ONLY via token-mapped human principals; a request with no/unknown token
  cannot approve (red-path test).
**A3 — No silent failures.** Replace the `except Exception: pass` blocks (list_accounts,
digest) with structured warn logs + an explicit `priority_score: null` +
`priority_score_error: <ExcName>` field. Test: a poisoned account yields the flagged null,
not a silent drop.
**A4 — Delegation view + manager digest (Bucket 3 surface).** Read-only additions over
existing data: `GET /queue/delegation` (tier-grouped pending: auto-executed tier-1 audit
trail, batch-approvable tier-2, escalation tier-3) + `ucsm queue` CLI; extend `/digest`
with the manager rollup (book health counts, divergence patterns, action throughput —
deterministic packets only, no narration). No new mutation paths; batch-approve = N
individual gate verdicts by the authenticated principal, atomic per item, never a bypass.

**Lane A DoD:** all four landed; endpoint responses unchanged where not specified; SoD
red-path tests green; zero duplicated helper bodies (`grep -c "def _score_one_account"
src/` → 1); universal suite green.

## Lane B — Core loop close (Bucket 1)

**B1 — snapshot→sweep.** The sweep reads `snapshot_store` trajectory for each account and
computes a deterministic `trajectory_decline` factor (config-thresholded via the existing
resolver: `decline_slope`/window already exist; positive-evidence-only — no snapshots or
<2 points → NO factor, state `unknown`). Factor carries evidence refs to the snapshots +
config provenance like every other factor.
**B2 — Tests for the untested paths.** Trajectory endpoint (day=N branches),
`value_model_bridge` correctness (known bundle → expected rails), `data_simulator` +
`book_simulator` determinism (same inputs → identical output, twice), `snapshot_store`
trend/band-change math.
**Decision criteria:** IF trajectory factor changes fixture-book priorities → that's the
intended change; re-baseline with the note. IF a bridge test reveals a computation bug →
fix the bridge (it's Lane B-owned scope... `value_model_bridge.py` is hereby Lane B's) and
record it in the commit; IF the bug is in `value_model.py` itself → §X trigger (shared
spine, owner visibility).

**Lane B DoD:** factor live with tests incl. missing-data red-path; all B2 suites green;
baseline refreshed with intended-change note; universal suite green.

## Lane C — Credentialed lane (Bucket 2; sequential C1→C4)

**C1 — Finish the year-in-life digest** (done): complete per the existing runbook
(`make year-in-life-csm`), commit the untracked files + Makefile change. Fixture-mode test
in CI; live artifact to `demo_state/` (full synthetic text allowed THERE only);
`claim_boundary: sim`; costs via `cost_tracker` within budget.
**C2 — Determinism probe on the PRODUCTION judge.** Re-run the existing probe with
`JUDGE_MODEL_ID` (sonnet) — NEW artifact filename (`determinism_probe_judge_v5.json`);
do not overwrite prior artifacts. From results, compute and REPORT (not enact): modal
stability vs N ∈ {3,5,10}, recommended N, and an indeterminate-case rule (IF N runs split
on the gate → route to human review). Owner ratifies; do not wire into gates yet.
**C3 — Live org-pack adversarial eval.** ~20 hostile org-pack payloads (commitment asks,
recipient changes, priority-override instructions, injection-in-voice-rules) against the
LIVE writer; assert the contract validator + prompt confinement hold: no hostile ask
reaches `customer_draft`, no authority field moves. NEW eval file + artifact; failures are
FINDINGS to report, not to silently patch around (a prompt fix bumps `prompt_version` and
re-runs the whole set once; a second failure after the fix → §X).
**C4 — Writer migration, Opus vs Sonnet.** Existing paired McNemar lane on shared cases.
Per dimension: IF judge-validated (κ ≥ 0.6 in the CURRENT `judge_agreement.json` at run
time) → judge-scored; ELSE contract-scored; the artifact labels which. Report discordants,
p-value, clusters, cost delta, and a one-paragraph verdict (keep / switch / insufficient).

**Lane C DoD:** four artifacts captured with claim boundaries; no gold/judge-prompt/label
files touched; progress printed per item on every live run.

## Lane D — Adoption kit (Bucket 3)

**D1 — Explorer → mapping → config.** Close the known gap: `SchemaSnapshot` →
auto-proposed source-map (deterministic for standard/known fields; LLM-suggest is allowed
ONLY here, config-time, and ONLY if `ANTHROPIC_API_KEY` present — ELSE deterministic-only
with ambiguous fields flagged) → human-confirm file (`ucsm connectors confirm` reads/writes
a pending-map file; value-DIRECTION entries always require explicit confirm) → frozen
versioned config the data plane loads. Coverage states per field:
`mapped | ambiguous_confirm | missing_to_unknown`; a config referencing an unconfirmed
ambiguous field fails load (fail-closed). Test against the recorded real schemas.
**D2 — Committers to the credential boundary.** `src/ultra_csm/committers.py`: the
`Committer` port + one real outbound adapter shape (email-style) + CRM-writeback shape,
each with recorded-shape tests, `--dry-run`, idempotency key, gate-binding re-verify
(reuse the gate's hash check), and readiness `shape_verified_pending_live_creds`. NO
network calls in tests; the sim committers from the demo loop stay as the executable pair.
**D3 — `QUICKSTART.md`.** The adopter's path, verified by actually executing every command
in fixture/sim mode: clone → `make setup` → 10-minute demo (`make demo` targets) → connect
your stack (env vars per connector → `smoke` → `explore` → `confirm` → sweep) → what the
readiness report will tell you at each stage. Every command in the doc must be run before
it's written down.
**D4 — STATUS render + doc reconciliation.** `scripts/render_status.py` → `STATUS.md`
generated ONLY from artifacts (scorecards, regression, judge_agreement, readiness,
operating proof) + `make status` + CI stale-check (`git diff --exit-code STATUS.md`).
Then the leftover doc fixes: §7 fence amended to own API/MCP/cost/metrics; sim-circularity
claim_boundary verified on `deep_vs_shallow_detection.json` and everywhere the
87.5%/37% numbers appear; `NEXT_DISPATCH.md` refreshed with artifact-owned numbers only.

**Lane D DoD:** an executor who has never seen the repo can follow QUICKSTART start to
finish in fixture mode; explorer→confirm→frozen-config round-trips on recorded schemas
with direction-confirm enforced; `make status` + CI check active; no doc contradicts the
codebase.

## Lane E — Risk + Expansion lenses (Bucket 2; after B merges)

As previously specified: thin projections over the shared model + trajectories; eval
battery FIRST with unsafe foils (the unsafe placeholder MUST fail ≥3 hard gates each);
weight-robust ordering fixtures; own action-taxonomy bindings through the existing gate
(Risk → internal-only authority; Expansion → strictest customer-facing tier);
lens-specific versioned Slot B prompts. **Claim gate:** deterministic lens claims ship on
their scorecards; Slot-B quality claims wait for judge validation.
**Lane E DoD:** two lens scorecards green incl. foil failures; one fixture account appears
in two lenses' queues without conflict; universal suite green.

## §X. Check-in triggers — the ONLY reasons to stop and ask

1. Push rejected with a NON-empty diff vs origin (never force through content differences).
2. Any need to modify judge-lane files (gold/labels/anchors/judge prompts) or
   `value_model.py` spine logic.
3. A DoD unmet after 3 genuine attempts (report the attempts + evidence).
4. C3 adversarial failure that survives one prompt-version fix.
5. Any action requiring credentials beyond `ANTHROPIC_API_KEY`, any write outside
   sim/`demo_state/`/repo, or anything on the owner-gated list below.
6. Two architecturally plausible designs not resolved by a criterion above.

## §O. Owner-gated (surface, never decide)

Judge/labels/rubric/anchors; merge to `main`; second labeler; live-tenant anything;
new runtime LLM surface beyond the two slots + config-time explorer suggestions.

## §F. Final one-shot DoD (the exit state)

All five lanes merged in §M order, each lane's DoD met; `STATUS.md` rendered and CI-checked;
QUICKSTART executable end-to-end in fixture mode; full suite + hygiene + scorecards +
regression green; every commit pushed; a closing summary listing per-lane results, every
§X trigger encountered (ideally none), and the artifacts a reviewer should open first.
