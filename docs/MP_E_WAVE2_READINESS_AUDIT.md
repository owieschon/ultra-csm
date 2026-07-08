# MP-E Wave 2 Readiness Audit

Date: 2026-07-08

Status: Wave 2 is not yet open on `main`. MP-E Wave 1 and Wave 6 are parked on
`codex/mp-e-wave1-6`; Waves 2-5 must wait for MP-D2 landings.

## Gate Receipts

Checked refs:

| Ref | Gated organs present |
|---|---|
| `origin/main` | none of `centralize_telemetry.py`, `self_serve_activation.py`, `blocked_value_path.py`, `work_packets.py`, `workflow_core.py`, `workflow_playbooks.py` |
| `origin/codex/work-packet-architecture` | `src/ultra_csm/data_plane/centralize_telemetry.py`, `src/ultra_csm/self_serve_activation.py`, `src/ultra_csm/blocked_value_path.py`, `src/ultra_csm/work_packets.py`, `src/ultra_csm/workflow_core.py`, `src/ultra_csm/workflow_playbooks.py` |
| `origin/codex/mp-d2-packet-salvage` | `src/ultra_csm/work_packets.py` |
| `origin/codex/mp-d2-validation-spine` | `src/ultra_csm/work_packets.py` |
| `origin/codex/mp-d2-packet-ui` | `src/ultra_csm/work_packets.py` |

Active MP-D2 worktree:

`/Users/owieschon/dev/ultra-csm-mp-d2-salvage` is on
`codex/mp-d2-self-serve-workflow-proof` with uncommitted changes:

- modified: `Makefile`, `src/ultra_csm/api.py`, `src/ultra_csm/audit_ledger.py`
- untracked: `eval/self_serve_workflow_eval.py`,
  `migrations/0011_workflow_packet.sql`,
  `src/ultra_csm/self_serve_activation.py`,
  `src/ultra_csm/self_serve_activation_store.py`,
  `src/ultra_csm/workflow_core.py`,
  `src/ultra_csm/workflow_playbooks.py`,
  `tests/test_self_serve_activation_workflow.py`,
  `tests/test_workflow_core.py`,
  `tests/test_workflow_playbooks.py`

## Decision

Do not start MP-E Wave 2 from `main` yet. The named landing
(`Centralize + the self-serve vertical`) is not on `main`, and the active MP-D2
agent is still editing the self-serve proof worktree.

Do not start MP-E Wave 2 from the dirty MP-D2 worktree. That would collide with
MP-D2's fenced files and consume an unstable local state.

The first safe Wave 2 base is the branch or merge commit that contains:

- `src/ultra_csm/data_plane/centralize_telemetry.py`
- `src/ultra_csm/self_serve_activation.py`
- `src/ultra_csm/blocked_value_path.py`
- MP-D2's workflow grading spine
- committed and pushed MP-D2 self-serve proof artifacts

## Ready-To-Start Checklist

Before MP-E Wave 2 implementation, run:

```bash
git fetch origin --prune
git ls-tree -r --name-only <base-ref> | rg 'centralize_telemetry.py|self_serve_activation.py|blocked_value_path.py|work_packets.py|workflow_core.py|workflow_playbooks.py'
git status --short --branch
```

Proceed only if the base ref is committed, pushed, and no longer the active
dirty MP-D2 worktree.

## Non-Collision Rule

MP-E Wave 2 may extend user-grain telemetry and identity resolution around the
landed organs, but it must not edit MP-D2-owned files while MP-D2 is active:

- `work_packets.py`
- workflow grading spine
- sweep/API packet wiring
- workbench UI

Any necessary change inside those files is a handoff back to MP-D2, not an MP-E
edit.
