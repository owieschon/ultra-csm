# Living World

`ucsm world` builds a deterministic synthetic world with two layers:

- Surface data in the repo’s existing `FixtureCustomerData` contract shapes.
- Latent truth that remains isolated from agent import paths and is used only by world-local eval code.

Core guarantees:

- `make world SEED=n` is byte-deterministic for fixed inputs.
- Anchor accounts come from the existing synthetic book; the remainder are generated from deterministic hash schedules.
- Base-rate realism is explicit: the quiet majority dominates, doomed accounts are the minority, and corruption is additive rather than universal.
- Corruption processes are structural (`duplicate_contact`, `stale_field`, `mislinked_case`, `red_herring`), not hidden prompt tricks.
- Bible-style arcs are mounted as anchors through the existing synthetic-book and deep-simulation substrate.

Artifacts:

- World build: `build/world/seed-<n>/world.json`
- Scoreboard rows: `eval/world_scoreboard.json`
- Knowability audit: `eval/knowability_audit.json`

Context graph:

- `bitemporal_spine`
- `supersedence`
- `decision_nodes`
- `closed_loop_hooks`
- `identity_resolution`
- `conflict_nodes`

Blindness boundary:

- `src/ultra_csm/agent1/` may not import `ultra_csm.world`.
- Surface decisions may not cite latent-only keys or evidence ids.
- `make eval` now runs `python -m eval.knowability_audit --check` as a hard gate.

Known gaps:

- The pass^k lane is built as a handoff surface only; the local builder lane does not execute the metered branch.
- The current closed-loop hooks are deterministic placeholders for follow-up measurement, not live retention outcomes.
- The graph is intentionally limited to the six required sections and does not claim a broader ontology.
