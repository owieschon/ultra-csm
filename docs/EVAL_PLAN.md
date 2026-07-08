# Ultra CSM Eval Plan

Status: active eval landing page.

## Runnable Artifacts

- `eval/scorecard_csm.py`
- `eval/scorecard_csm.json`
- `eval/csm_work_queue.json`
- `eval/baseline_csm.json`
- `eval/regression_csm.py`
- `eval/regression_csm.json`
- `eval/regression_csm_live.json`
- `eval/workflow_scenario_battery.py`
- `eval/workflow_scenario_battery.json`
- `eval/outcome_simulation_csm.py`
- `eval/stochastic_csm.py`

## Deterministic Hard Gates

The CSM scorecard covers:

- complete evidence bundle assembly;
- pending-only customer outreach proposals;
- ambiguous identity escalation;
- missing telemetry blocking;
- contact-consent blocking;
- import quarantine away from deleted runtime seams;
- deterministic book-sweep ranking;
- cross-tenant containment;
- refusal on insufficient evidence;
- grounded factor provenance;
- proposal-only action posture;
- no authority minting by the CSM agent;
- prompt-injection resistance;
- reproducibility;
- Slot B contract validation and unsafe-output rejection.
- workflow scenario behavior over the deterministic synthetic universe,
  including source coverage, value-model alignment, customer-output
  suppression, and counterfactual missing-evidence behavior.

Expected result:

```text
Agent 1 CSM scorecard: see `eval/scorecard_csm.json` for current score and hard-gate status.
```

## Regression

`make regression-csm` compares the deterministic spine against
`eval/baseline_csm.json` with exact, zero-tolerance matching. It also runs a
seeded distributional fixture so the pass-rate band and failure-cluster machinery
can go red offline.

`make regression-csm-live` is separate and credential-gated. It may capture live
Slot B behavior, but it is not a CI gate and must not be described as offline
proof.
