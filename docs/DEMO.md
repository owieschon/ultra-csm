# Ultra CSM Demo Runbook

Status: active demo runbook for the current CSM proof.

The demo should show the internal scaled-CSM workflow, not the inherited
structural battery. The primary path is:

1. Run hygiene and deterministic Agent 1 scoring.
2. Show the Time-to-Value sweep result: work items, escalation lane, evidence ids,
   and gated proposals.
3. Run the offline regression lane.
4. Optionally show the captured live Slot B drift artifact.

## Local Setup

Use a clean terminal from the repo root:

```bash
make hygiene
make scorecard-csm
make regression-csm
```

Expected current artifacts:

- `eval/scorecard_csm.json`: deterministic Agent 1 CSM scorecard.
- `eval/regression_csm.json`: offline regression report with exact deterministic
  spine checks plus seeded distributional Slot B machinery.
- `eval/regression_csm_live.json`: captured credential-gated live Slot B drift
  report. This is an artifact, not a CI requirement.
- `eval/outcome_simulation_csm.json`: synthetic outcome-simulation report.

## What To Show

Lead with the CSM-native result:

- The sweep consumes `CustomerDataPlane` fixtures shaped around CRM, CS platform,
  product telemetry, and entitlements.
- Ambiguous identity routes to the escalation lane with `priority=None`.
- TTV-ranked work items carry deterministic priority factors backed by evidence.
- Customer-facing drafts are pending proposals, never direct sends.
- Insufficient evidence produces refusal/audit state instead of invented risk.

Then show regression:

- `make regression-csm` keeps deterministic fields exact.
- The seeded distributional fixture proves the pass-rate and failure-cluster
  machinery can fail reproducibly without calling a live model.
- `eval/regression_csm_live.json` shows the live Slot B red/green capture:
  normal prompt green, degraded prompt red, deterministic spine exact-green, and
  no full generated text stored.

## Demo Boundary

Do not claim production customer lift from fixture or simulation artifacts.
Synthetic outcome simulation is training/eval evidence only. Live adapters and
live model lanes are credential-gated and excluded from CI by design.
