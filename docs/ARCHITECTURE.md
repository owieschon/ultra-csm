# Ultra CSM architecture

Use this page to locate the current runtime spine and the boundaries that model output
cannot cross.

Ultra CSM centers on one verifiable customer-action loop:

```text
CustomerDataPlane
  -> CustomerValueModel and TTV lens
  -> bounded Slot B reason and draft
  -> ActionGate proposal
  -> verdict from a configured approval identity
  -> payload-bound committer receipt
```

## Runtime components

- `src/ultra_csm/agent1/`: Time-to-Value evidence, sweep, and bounded Slot B reason/draft.
- `src/ultra_csm/value_model.py`: deterministic rails, config resolution, factors,
  and TTV projection.
- `src/ultra_csm/data_plane/`: CRM, CS-platform, and product telemetry contracts,
  fixtures, source maps, and shared evidence references.
- `src/ultra_csm/governance/`: CSM action taxonomy, RBAC lookup, payload binding,
  and pending-proposal gate.
- `src/ultra_csm/platform/`: minimal local Postgres boot, migrations, session seam,
  and deterministic seed constants for scorecards/tests.
- `src/ultra_csm/observability/`: no-op and recording trace/metric ports used by
  Agent 1 and tests.

## Hard Boundaries

- The deterministic model computes priority. Slot B never mints factors or scores. Its
  source is labeled as fixture, live, template fallback, or none.
- Customer-affecting actions are proposals. Delivery and record mutation require
  explicit release outside the scored agent.
- Ambiguous identity never auto-picks an account.
- Missing evidence never fabricates a risk signal.
- Live model variance is measured only by the credential-gated regression lane.

## Verification

- `make scorecard-csm`: deterministic Agent 1 scorecard; see the generated artifact for
  the current gate count.
- `make regression-csm`: exact deterministic spine regression plus seeded
  distributional mechanics.
- `make eval`: offline pytest suite, scoped quality-gold checks, and knowability audit.
- `make hygiene`: active-surface residue scan.
