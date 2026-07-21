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
| No-spine ablation | baseline report row | built |
| Pass^k | operator handoff only | partial by design |
| Statistical power sizing | `eval.drift_power_csm` helpers reused in baseline report | built |

Hard gates:

- `make eval`
- `python -m eval.gold_slot_b_quality --check`
- `python -m eval.gold_slot_b_hard --check`
- `python -m eval.knowability_audit --check`

Claim boundary:

- The living-world harness proves deterministic structure, agent blindness, and auditability.
- It does not prove production retention impact.
- It does not claim that pass^k has been executed locally; that lane is documented for the operator and intentionally unrun by the local builder lane.
