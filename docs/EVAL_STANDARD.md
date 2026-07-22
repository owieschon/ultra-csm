# Eval Standard

<!-- sourcebound:purpose -->
This repo now carries a frontier-style living-world evaluation substrate with an explicit honesty boundary.
<!-- sourcebound:end purpose -->

Frontier-standard mapping:

| Requirement | Repo surface | Status |
| --- | --- | --- |
| Deterministic seeded world | `ucsm world`, `build/world/seed-<n>/world.json` | built |
| Latent truth separated from surface | `src/ultra_csm/world/*`, `eval/knowability_audit.py` | built |
| Structural agent blindness proof | AST import audit over `src/ultra_csm/agent1/` | built |
| Context graph core | `src/ultra_csm/world/graph.py` | built |
| False-negative vs latent truth tracking | `build_oracle_report()` | built |
| Auditor challenge case | `--planted-violation` mode | built |
| Degenerate baselines | `build_baseline_report()` | built |
| No-spine ablation | `eval/world_scoreboard.json` W4 row | blocked, not run |
| Pass^k | `eval/gold/q4_pass_k_report.json` | executed for Q4/R4; repeat lane operator-owned |
| Statistical power sizing | `eval.drift_power_csm` helpers reused in baseline report | built |

Hard gates:

- `make eval`
- `python -m eval.gold_slot_b_quality --check`
- `python -m eval.gold_slot_b_hard --check`
- `python -m eval.knowability_audit --check`

Claim boundary:

- The living-world harness proves deterministic structure, agent blindness, and auditability.
- It does not prove production retention impact.
- The committed Q4/R4 report contains one executed pass^k evaluation: 63 live draws across 21
  scenarios, with pass^3 at 0.8095. It does not generalize that result to another seed, model,
  prompt, or world scale.
- The no-spine ablation remains blocked and unrun.
