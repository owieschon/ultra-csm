# MP-D2 Wave 1 Salvage Receipt

## Scope

This branch salvages only the reviewable Wave 1 core from PR #108:

- `CSMWorkPacket` contract and deterministic planner in `src/ultra_csm/work_packets.py`
- sweep wiring that attaches `work_packet` to real `CSMWorkItem` rows
- API contract coverage through existing `/sweep` response serialization
- tests proving backend CTA enablement derives from `governance/csm_actions.py`

The planner is a read-side envelope over existing organs: Agent 1 sweep output,
value-model priority factors, Slot B artifacts, internal-bridge routing, and
governance action specs. It does not create a second motion resolver, scorer, or
approval source.

## Wave 0 Receipts

- Clean worktree created from `origin/main` on branch `codex/mp-d2-packet-salvage`.
- PR #108 was treated as reference-only and was not merged or extended.
- PR #108 red CI cause: `make lint` failed before eval on unused names in the
  blob branch:
  - `src/ultra_csm/enterprise_onboarding.py:58` unused import
    `evaluate_source_coverage`
  - `src/ultra_csm/enterprise_onboarding.py:842` unused local
    `contact_by_id`
- PR #108 blob size from `origin/main..origin/codex/work-packet-architecture`:
  `260 files changed, 1050671 insertions(+), 373 deletions(-)`.

## Addendum 1 Survey

`origin/main` does not yet contain `workflow_core`, `workflow_playbooks`,
`workflow_scenario_eval`, or `workflow_quality_eval`.

The #108 reference branch does contain the workflow layer:

- `src/ultra_csm/workflow_core.py`
- `src/ultra_csm/workflow_playbooks.py`
- `src/ultra_csm/workflow_quality_eval.py`
- `src/ultra_csm/workflow_scenario_eval.py`
- vertical workflow tests for enterprise onboarding, self-serve activation, and
  adoption regression

Direct workflow references found on #108 across `src`, `tests`, and `eval`: 28.
Per Addendum 1, this is not deleted or treated as a duplicate motion layer. It
remains out of Wave 1 and should be promoted through the Wave 2 grading contract:
real workflow execution can count as runnable, but not independently validated
until expectations come from deterministic or owner-labeled ground truth.

## Gates

Run from `/Users/owieschon/dev/ultra-csm-mp-d2-salvage`.

- Compile:
  `python3 -m py_compile src/ultra_csm/work_packets.py src/ultra_csm/agent1/sweep.py src/ultra_csm/api.py`
- Planner generation-import grep:
  `rg -n "openai|anthropic|ReasonDraftWriter|FixtureReasonDraftWriter|LIVE_SLOT_B|generateText|streamText|workflow_core|workflow_playbooks" src/ultra_csm/work_packets.py`
  produced no matches.
- Focused tests:
  `python3 -m pytest tests/test_work_packets.py tests/test_ui_contract.py::TestSweepMotionLive -q`
  -> `7 passed`
- Connected sweep/API regression:
  `python3 -m pytest tests/test_agent1_sweep.py tests/test_api.py tests/test_ui_contract.py tests/test_work_packets.py -q`
  -> `73 passed`
- Lint:
  `python3 -m ruff check src eval tests scripts`
  -> `All checks passed!`
- Eval:
  `make PYTHON=python3 eval`
  -> `835 passed, 1 skipped`
  -> `eval/gold/slot_b_quality_status.json is current`
  -> `eval/gold/slot_b_quality_hard_status.json is current`

`make lint` without `PYTHON=python3` was not usable in this fresh worktree
because `.venv/bin/python` does not exist; the equivalent lint command above
passed with the installed interpreter.
