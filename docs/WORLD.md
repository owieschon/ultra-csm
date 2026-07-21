# Living World

<!-- sourcebound:purpose -->
`ucsm world` builds a deterministic synthetic world with two layers:
<!-- sourcebound:end purpose -->

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

World response (MP-W1R):

- `src/ultra_csm/world/response.py`'s `respond()` closes the loop the
  "Known gaps" section below used to describe as a placeholder: it returns
  a seeded-deterministic, latent-conditioned `ObservableEvent` (or `None`
  for internal/no-response actions) per `(seed, account_id, action_id,
  day)`. Reply-probability bands, the action-to-response-class mapping,
  live injection-event categories, and the one scripted mid-run shock are
  all in `knowledge/world_response_config.json`
  (`docs/SYNTHETIC_UNIVERSE_BIBLE.md`'s "World response" section is the
  ratified record; a config change is a bible change first).
- These are WORLD-LEVEL properties. Wiring them into the live agent-visible
  evidence path (`src/ultra_csm/agent1/sweep.py`) is a natural next-wave
  task, not yet done — this dispatch's ownership map is `world/**` only.
- Replay claim, stated precisely: `make world` itself is byte-deterministic
  (no LLM calls in world generation). Deterministic replay applies to all
  non-LLM state; LLM calls made BY AGENTS OPERATING IN this world vary
  run-to-run (neither transport pins temperature) — see
  `docs/R0_KAPPA_BAND_FINDING.md` for the internal evidence. Never claim
  "replayable" without this distinction.

Known gaps:

- The pass^k lane is built as a handoff surface only; the local builder lane does not execute the metered branch.
- The graph is intentionally limited to the six required sections and does not claim a broader ontology.
- D3's dirty-data flags (`LatentAccountTruth.data_quality_flags`) and D4's
  injection events are generated but, like world response above, not yet
  wired into the live agent-visible evidence path.
