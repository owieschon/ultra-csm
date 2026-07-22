# Executor handoff — 2026-07-02 (archived)

> Historical process record. It does not define the current branch, operating state, or work
> queue. Use the [documentation index](../../../README.md) for current guidance; branch-specific facts
> below are preserved only as provenance.

This was the pickup note for the next executor. It covers the last active work window,
the current worktree state, and the next safe sequence. It is intentionally operational:
verify the claims below before building on them.

## 0. Current Branch And Ownership

**Update (same day, later in the window):** the revise slice below (§2) and the
Gainsight/product-telemetry lane (§3) are both done and pushed. Sections 1-6 below are
kept as a historical record of the sequence that got here; do not re-do them. See
"State as of latest push" immediately below for what to actually pick up next.

### State as of latest push

- Branch: `codex/demo-execution-plan`
- Last pushed commit: `a0c8525 Add Gainsight and product-telemetry simulated onboarding
  verticals`
- Remote state: `origin/codex/demo-execution-plan` points at `a0c8525`
- `a97d7a8 Expose bounded draft revise surface` landed and was pushed **concurrently by
  another process** while this handoff's own pickup sequence was mid-verification
  (committer timestamp 2026-07-02 18:04:37 EDT, authored under the local git identity,
  not the coding-agent tool) — i.e. the revise slice in §2/§4 below got done by
  someone/something else while it was independently being verified here. Content matches
  what §2/§4 specify; independently re-verified after the fact (`make eval` 333 passed at
  the time, full suite minus the judge lane clean, lint/hygiene/scorecard/regression all
  green, `git diff --check` clean). Nothing further to do for the revise slice.
- `a0c8525` adds the Gainsight and product-telemetry simulated onboarding verticals per
  §3's recommendation, mirroring the Attio pattern exactly (real explorer/source-map code
  against a fake transport backed by the synthetic book). Both wired into `make demo`.
  Full verification suite green before commit (see below); pushed clean, no rebase
  needed.
- **Known anomaly to watch for:** a commit landed on this branch from an identity other
  than this session while verification was in progress. If you pick up this branch next,
  run `git log --oneline -5` and `git status --short --branch` FIRST and diff against
  what this doc claims before trusting it — someone else may be writing to
  `codex/demo-execution-plan` concurrently. Do not assume you have exclusive ownership of
  the branch just because the usual build agent is reported offline/unavailable.
- Do not edit the judge lane unless explicitly assigned. It is currently mid-edit and
  **known broken** (`tests/test_judge_anthropic.py` fails 4/4 with
  `ValueError: zip() argument 2 is longer than argument 1` against the dirty
  `LLM_JUDGE_DIMENSIONS` in `eval/judge_anthropic.py` — a tuple that currently has fewer
  entries than the checked-in test expects, consistent with an in-flight
  dimension-consolidation edit). This is pre-existing, not introduced by anything in this
  doc; leave it alone:
  - `eval/deterministic_quality.py`
  - `eval/gold/slot_b_quality.jsonl`
  - `eval/gold/slot_b_quality_hard_key.jsonl`
  - `eval/judge_anthropic.py`
  - `eval/label_gold.py`
  - `eval/apply_v6_ontask_rescore.py`
  - `eval/gold/v6_ontask_apply_report.json`
  Because of this, `make eval` / full `pytest tests/` will show 4 failures until the
  judge lane finishes its edit. Use
  `pytest tests/ -q --ignore=tests/test_judge_anthropic.py` to verify everything else.
- Untracked docs currently exist from another lane (still untracked, not committed by
  anyone as of `a0c8525`):
  - `docs/POSITION.md`
  - `docs/EXECUTOR_HANDOFF_LANE_H.md`
  Treat them as another executor's work unless told otherwise.

## Original handoff below (historical — §1-§6 describe how we got to `87b8284` and the
revise-slice pickup sequence, which is now done; §3's recommendation is now built)

## 1. Completed And Pushed In The Last Work Window

### API/MCP/Adoption Foundation

- `5907017` added the FastAPI surface, MCP server, structured logging, and tests.
- `4b5a7fa` added demo controls, cost/latency tracking, API metrics, quality breaker,
  and operations guardrails.
- `3942ce4` added the simulation closed-loop demo.
- `29cdb18` wired org knowledge into Slot B.
- `40c053a`, `0da3a79`, `3b4a581`, and `3364da6` added executor handoff, operating proof,
  status rendering, API helper dedupe, connector mapping confirmation, and lane dispatch
  structure.

### Simulation And Timeline

- `04096e3`, `b1d117f`, `e3e86a9`, `3c30fd3`, and `6b6216f` added the 35-account
  synthetic book, time-evolving book simulator, deep data layer, value-model bridge, snapshot
  store, trajectory layer, and detection artifacts.
- `acbcd44` added the year-in-life digest.

### Lenses, Triggers, Precedence, And Read-Only Conversation

- `eaffbca` added deterministic Risk and Expansion lenses plus tick triggers.
- `9cfb53e` added the precedence core, held-action lane, and cohort packet artifacts.
- `a3185cf` added read-only MCP conversation mode, read-only red-path tests, and a demo
  transcript artifact.

### Capability Wave Commit

`87b8284 Add capability demo slices` is pushed and is the last clean remote point.
It includes:

- Held expansion actions in `/queue/delegation`.
- API refusal for held customer-facing expansion approvals via `409 PRECEDENCE_HELD`.
- Slot A case-note classifier:
  - fixture classifier,
  - credential-gated live classifier,
  - validator,
  - versioned prompt,
  - scorecard and tests.
- Bounded draft revise core in `src/ultra_csm/agent1/revise.py`:
  - one automatic Slot B re-run,
  - superseding pending proposal,
  - hostile-edit refusal,
  - preference-pair artifact,
  - loop-bound tests.
- Earned-autonomy report:
  - deterministic verdict-ledger aggregation,
  - promotion/demotion proposal artifacts only,
  - no tier mutation.
- Attio simulated onboarding vertical:
  - uses the real Attio explorer and source-map freeze machinery,
  - uses a fake Attio transport backed by the simulated customer book,
  - writes `eval/attio_simulated_onboarding.json`,
  - claim boundary says sim only, no live tenant proof.
- `make demo` now runs:
  - `scorecard-csm`
  - `regression-csm`
  - `slot-a-scorecard-csm`
  - `autonomy-report-csm`
  - `attio-simulated-onboarding-csm`
  - `mcp-readonly-demo-csm`

Verification completed after `87b8284`:

- `make demo` passed.
- `make eval` passed: `329 passed, 1 warning`.
- `make lint` passed.
- `make hygiene` passed.
- `make scorecard-csm` passed: `24/24 hard_ok=True`.
- `make regression-csm` passed: `hard_ok=True`.
- Targeted capability tests passed: `65 passed, 1 warning`.
- `git diff --check` passed.

## 2. Current In-Progress Work: API/CLI Revise Surface

The latest work was stopped before commit. It is not pushed. The goal was to expose the
already-tested bounded revise loop through the operator surfaces.

Files currently changed for this slice:

- `src/ultra_csm/agent1/__init__.py`
- `src/ultra_csm/agent1/sweep.py`
- `src/ultra_csm/api.py`
- `src/ultra_csm/cli.py`
- `tests/test_api.py`
- `tests/test_cli_connectors.py`

Important current git state:

- Some of the revise files are staged from the first implementation.
- `src/ultra_csm/agent1/sweep.py` is `MM`: staged plus additional unstaged refactor.
- Before committing, run:
  - `git diff --cached --stat`
  - `git diff --stat`
  - inspect `git diff -- src/ultra_csm/agent1/sweep.py`
- If keeping the refactor, stage the final `sweep.py` version before commit.

What the in-progress slice does:

- Adds `build_reason_draft_request_for_account(...)` in `agent1.sweep`.
- Refactors shared Slot B request inputs into `_slot_b_inputs_for_account(...)` so sweep and
  revise reconstruction use one evidence/priority assembly path.
- Exports `build_reason_draft_request_for_account` from `agent1.__init__`.
- Extends the API verdict schema to `approve | deny | revise`.
- Adds `edit_instruction` to `VerdictRequest`.
- Adds `superseding_proposal_id` to `VerdictResponse`.
- Routes API `revise` through `run_slot_b_revise_loop(...)`.
- Keeps revise deterministic in this first API slice; it uses the existing bounded loop and
  fixture writer path, not a live model call.
- Adds stable failure codes:
  - `REVISE_INSTRUCTION_REQUIRED`
  - `REVISE_UNSUPPORTED_ACTION`
  - `REVISE_NOT_RECONSTRUCTABLE`
  - `REVISE_REFUSED`
  - `REVISE_BOUND_REACHED`
  - `REVISE_GATE_ERROR`
- Adds `ucsm proposals revise <proposal_id> --edit-instruction ...`.
- Adds API tests for:
  - revise creates a superseding pending proposal,
  - hostile edit is refused,
  - one automatic rerun is enforced.
- Adds CLI test that `proposals revise` posts the edit instruction and prints the superseding
  proposal id.

Verification already run for this in-progress slice:

- Before the refactor:
  - `tests/test_api.py tests/test_cli_connectors.py tests/test_revise_loop.py`: `40 passed`.
  - Ruff on touched files passed.
  - `git diff --check` passed.
- After the refactor:
  - `tests/test_api.py tests/test_cli_connectors.py tests/test_revise_loop.py tests/test_agent1_sweep.py`: `47 passed, 1 warning`.
  - Ruff on touched files passed.
  - `make lint` passed.
  - `make hygiene` passed.
  - `make scorecard-csm` passed: `24/24 hard_ok=True`.
  - `make regression-csm` passed: `hard_ok=True`.
- `make eval` was interrupted on user request after `273 passed`; do not treat the full suite
  as complete for the revise slice.

## 3. Latest Product Direction To Carry Forward

The owner asked whether Gainsight and direct product telemetry should be simulated the same
way Attio was simulated. Treat that as the next connector-standard issue after the revise
surface is either committed or deliberately abandoned.

Recommendation for the next build:

- Yes, add simulated connector verticals for:
  - `gainsight_cs`
  - `product_telemetry`
- Mirror the Attio standard:
  - real explorer code path,
  - fake transport/client backed by the simulated customer book,
  - source-map proposal where applicable,
  - confirmed/frozen config where applicable,
  - readiness artifact with `sim=true`, `live=false`, no live-tenant claim,
  - tests proving no network calls without credentials and deterministic output.
- Do not claim these are live integrations. The target claim is: real code to the credential
  boundary, proven against simulated/recorded API-shaped data.

Suggested artifact names:

- `eval/gainsight_simulated_onboarding.py`
- `eval/gainsight_simulated_onboarding.json`
- `eval/gainsight_simulated_confirmations.json` if confirmations are needed.
- `eval/product_telemetry_simulated_onboarding.py`
- `eval/product_telemetry_simulated_onboarding.json`
- Matching tests under `tests/`.

Suggested Make targets:

- `gainsight-simulated-onboarding-csm`
- `product-telemetry-simulated-onboarding-csm`
- Add both to `make demo` only after the artifacts are deterministic and fast.

## 4. Exact Pickup Sequence

1. Re-check status:

   ```sh
   git status --short --branch
   git diff --cached --stat
   git diff --stat
   ```

2. Decide the revise slice state:

   - If keeping it, stage the unstaged refactor in `src/ultra_csm/agent1/sweep.py`.
   - If not keeping it, unstage/revert only the revise files listed in §2. Do not touch judge
     lane files.

3. If keeping revise, run:

   ```sh
   .venv/bin/python -m pytest tests/test_api.py tests/test_cli_connectors.py tests/test_revise_loop.py tests/test_agent1_sweep.py -q
   .venv/bin/python -m ruff check src/ultra_csm/agent1/sweep.py src/ultra_csm/api.py src/ultra_csm/cli.py src/ultra_csm/agent1/__init__.py tests/test_api.py tests/test_cli_connectors.py
   make eval
   make lint
   make hygiene
   make scorecard-csm
   make regression-csm
   git diff --check
   ```

4. Commit only the revise files if all gates pass:

   ```sh
   git add src/ultra_csm/agent1/__init__.py \
     src/ultra_csm/agent1/sweep.py \
     src/ultra_csm/api.py \
     src/ultra_csm/cli.py \
     tests/test_api.py \
     tests/test_cli_connectors.py
   git diff --cached --name-only
   git diff --cached --check
   git commit -m "Expose bounded draft revise surface"
   ```

5. Push safely:

   ```sh
   git pull --rebase --autostash
   git push
   git status --short --branch
   ```

   `bd dolt push` currently fails in this checkout because no beads database is present.
   Do not initialize beads unless explicitly asked.

6. Then build Gainsight and product telemetry simulated verticals using the Attio slice as the
   template, not by copy-pasting large modules. Keep shared helpers if common fake transport,
   artifact, or readiness logic repeats.

## 5. Files To Inspect First

- Attio pattern:
  - `eval/attio_simulated_onboarding.py`
  - `eval/attio_simulated_onboarding.json`
  - `eval/attio_simulated_confirmations.json`
  - `tests/test_attio_simulated_onboarding.py`
- Explorer and mapping:
  - `src/ultra_csm/data_plane/explorer.py`
  - `src/ultra_csm/data_plane/source_mapping.py`
  - `src/ultra_csm/data_plane/readiness.py`
- Connector catalog:
  - `src/ultra_csm/data_plane/connector_catalog.py`
- Simulated book:
  - `src/ultra_csm/data_plane/synthetic_book.py`
  - `src/ultra_csm/data_plane/fixtures.py`
- Revise surface:
  - `src/ultra_csm/agent1/revise.py`
  - `src/ultra_csm/agent1/sweep.py`
  - `src/ultra_csm/api.py`
  - `src/ultra_csm/cli.py`

## 6. Guardrails

- Keep judge-owned files out of unrelated commits.
- Keep generated status out of a commit if it only changed because judge files are dirty.
- Avoid duplicating score/evidence assembly. Shared code is preferred over parallel helper paths.
- Keep connector artifacts honest:
  - fixture/sim proof is not live proof,
  - no network calls in unit tests,
  - missing credentials must return before transport use,
  - partial coverage must be recorded as unknown or degraded, never inferred.
- Do not expose write-capable MCP tools through the read-only conversational path.
- Do not add new runtime LLM surfaces while finishing connector simulation.
