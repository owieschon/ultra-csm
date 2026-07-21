# Operator Runbook

<!-- sourcebound:purpose -->
This file is the builder-to-operator handoff surface for credentialed lanes.
Builder lanes only add commands here; they do not execute them.
<!-- sourcebound:end purpose -->
<!-- sourcebound:allow doc-length reason="The daily operation and its recovery path are one operator task" -->

## R0 — Transport Fidelity Agreement Check

Purpose: verify the `claude_code` transport reproduces the committed judge path
before any later operator lane trusts it.

Command:

```bash
ULTRA_CSM_LLM_TRANSPORT=claude_code \
python -m eval.run_quality_judge --model claude-sonnet-5
```

Expected receipt:

- The run completes through the existing judge path without direct API wiring.
- The written artifact records the same `judge_prompt_version` and `model_id`
  as the committed lane, with transport set to `claude_code` in runtime
  telemetry.
- Token telemetry is present from the transport layer; any dollar field remains
  an estimate or zero-cost local receipt, not a billing claim.

Timeout and retries: the `claude_code` transport shells out to the `claude`
CLI, which has real process startup and auth/session overhead on top of model
latency, so it defaults to a 120s per-call timeout (vs. 30s for the direct
API). Override either transport's timeout with `ULTRA_CSM_LLM_TIMEOUT_S=<seconds>`.
`subprocess.TimeoutExpired` and `subprocess.CalledProcessError` from the
`claude_code` transport are retried like the direct API's connection/timeout
errors, up to the same `MAX_RETRIES`.

Status:

- Added by builder during MP-F1 Wave 0.
- Timeout/retry coverage for the `claude_code` transport landed via finding #2
  (`docs/R0_RETRY_COVERAGE_FINDING.md`).
- Third run completed all 127/127 items with zero crashes but landed outside
  the committed kappa/false-open bar; see `docs/R0_KAPPA_BAND_FINDING.md`
  (owner reviewed and authorized proceeding).

## R2 — Writer Bake-off: Haiku 4.5 vs Sonnet 5 (`eval.writer_bakeoff`)

Purpose: validate the cheap drafting model the program will use for Slot B,
before adopting it. Both candidates draft the same MDD-power-sized, stratified
scenario set; drafts are scored by the Sonnet-5 judge on the five currently-
validated gating dimensions (`eval.judge_validation`'s scope guard) plus Slot
B's own deterministic contract checks; `on_task_relevance` is scored and
reported, never gated. Adoption is an absolute bar per arm, not head-to-head —
see the module docstring in `eval/writer_bakeoff.py` for the exact bar and the
self-preference disclosure (the judge is Sonnet 5, and one candidate arm is
Sonnet 5 too).

Command:

```bash
ULTRA_CSM_LLM_TRANSPORT=claude_code \
python -m eval.writer_bakeoff --drop-pp 0.20 --pass-k 3 \
  --checkpoint-dir .writer_bakeoff_checkpoints
```

Expected receipt:

- `eval/gold/writer_bakeoff_report.json` records both arms' `gated_pass_rate`,
  `pass_k_rate`, `contract_violation_rate`, per-dimension pass rates, and
  token telemetry, plus the `adopt_eligible` verdict per arm.
- Checkpointed per model under `--checkpoint-dir`; safe to stop and resume —
  each draw's checkpoint entry is keyed by `(scenario_id, draw_index)`.
- STOP → OA-Q1/OA-R2: the owner picks the adopted writer from the table; the
  gates decide eligibility, not this recommendation.

Status:

- Harness built by builder (no prior R2 harness existed); not yet operated.

## R1 — Deterministic World Build Receipt

Purpose: regenerate the seeded living-world artifact and verify the graph,
oracle, and knowability surfaces from a single operator command.

Command:

```bash
make world SEED=7 SCALE=60
```

Expected receipt:

- `build/world/seed-7/world.json` is rewritten deterministically.
- The CLI reports `knowability hard_ok: True`.
- The graph section counts cover the six required graph sections.

## R3 — Knowability Auditor Challenge

Purpose: prove the hard-gate auditor can catch a planted violation instead of
merely reporting green on the clean path.

Command:

```bash
PYTHONPATH=src:. python -m eval.knowability_audit --seed 7 --scale 60 --planted-violation
```

Expected receipt:

- The command reports `hard_ok=False`.
- `hard_failures` includes `planted_violation:latent_truth_imported_into_surface_path`.

## R4 — Pass^k Handoff Only

Purpose: hand the metered pass^k lane to the operator without the local builder lane executing it.

Command:

```bash
ULTRA_CSM_LLM_TRANSPORT=claude_code \
python -m eval.world_scoreboard --seed 7 --scale 60 --pass-k 8 --model claude-sonnet-5
```

Expected receipt:

- The scoreboard artifact records the operator-selected `pass_k` and `model`.
- Any actual metered pass^k sampling remains an operator decision outside the
  builder lane.
