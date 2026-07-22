# Credentialed evaluation runbook

Use this page to run the model-backed and metered evaluation lanes that remain outside
the default offline proof.

Run `make setup`, `make doctor`, and the offline gates before supplying credentials.
Keep API keys and model credentials in the environment; do not write them to artifacts,
commands committed to the repository, or issue text.

<a id="r0-transport-adapter"></a>
## Check transport fidelity

Run the committed quality-judge path through the command-backed model transport:

```sh
ULTRA_CSM_LLM_TRANSPORT=claude_code \
  PYTHONPATH=src:. .venv/bin/python -m eval.run_quality_judge \
  --model claude-sonnet-5
```

The written artifact must retain the committed `judge_prompt_version` and `model_id` and
record the selected transport. Token counts are runtime telemetry; dollar values remain
estimates unless reconciled to a provider bill.

The command-backed transport allows process startup and authentication overhead, so its
default per-call timeout is 120 seconds. Set `ULTRA_CSM_LLM_TIMEOUT_S` to override it.
Timeouts and nonzero subprocess exits use the same bounded retry policy as the direct API
transport.

## Run the writer bake-off

```sh
ULTRA_CSM_LLM_TRANSPORT=claude_code \
  PYTHONPATH=src:. .venv/bin/python -m eval.writer_bakeoff \
  --drop-pp 0.20 --pass-k 3 --checkpoint-dir .writer_bakeoff_checkpoints
```

The report at `eval/gold/writer_bakeoff_report.json` records gated pass rate, pass-k rate,
contract violations, per-dimension results, token telemetry, and adoption eligibility for
each arm. The judge shares a model family with one candidate arm, so interpret comparison
results with that self-preference risk visible. A checkpoint is keyed by scenario and draw
index and can resume after interruption.

Eligibility gates do not select a production writer. Review the report, the contract
failures, and cost telemetry before changing configuration.

## Rebuild the deterministic world

```sh
make world SEED=7 SCALE=60
```

The command rewrites `build/world/seed-7/world.json`, reports the knowability result, and
emits counts for each required graph section. Run the planted negative control before
trusting a green auditor result:

```sh
PYTHONPATH=src:. .venv/bin/python -m eval.knowability_audit \
  --seed 7 --scale 60 --planted-violation
```

The negative control must report `hard_ok=False` and include
`planted_violation:latent_truth_imported_into_surface_path` in `hard_failures`.

## Run pass-k sampling

```sh
ULTRA_CSM_LLM_TRANSPORT=claude_code \
  PYTHONPATH=src:. .venv/bin/python -m eval.world_scoreboard \
  --seed 7 --scale 60 --pass-k 8 --model claude-sonnet-5
```

This is a metered lane. The scoreboard must record the selected model and `pass_k`; it
does not convert sampling results into authority to approve or send customer actions.
