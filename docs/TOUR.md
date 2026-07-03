# A ten-minute tour

Everything below runs locally with **no credentials, no cloud, and no customer data**.
Each beat is one command plus what to look at and what it demonstrates. Total wall
time is a few minutes; reading the artifacts is the rest.

Prerequisite: `make setup && make doctor` (doctor boots and tears down a real
throwaway Postgres cluster — if it passes, everything below will run).

## 1. The deterministic spine holds

```sh
make scorecard-csm
```

Look at the terminal line (`24/24 hard_ok=True`) and `eval/scorecard_csm.json`.
Tenant isolation, consent gating, payload-hash binding, and no-authority-minting
are enforced in code against a real Postgres and fail the build if broken. This is
the part of the system that is *proven*, not sampled.

## 2. A year in the life of a book of business

```sh
PYTHONPATH=src:. .venv/bin/python -m eval.year_in_life_digest
```

Open `demo_state/year_in_life_digest.json`. A 35-account synthetic book evolves
across 365 simulated days — accounts decline, recover, churn — and the value model
snapshots trajectory at each step. Note the `claim_boundary` on the artifact: it
says fixture, because it is.

## 3. Triggers fire — and get suppressed — over simulated time

```sh
make tick-demo-csm
```

Watch the terminal narrate schedule/deadline/event triggers firing per simulated
day, then open `demo_state/tick_demo/tick_ledger.jsonl`. The interesting rows are
the `suppressions`: every trigger that did NOT fire records why (cooldown, already
fired), with the evidence predicate inline. Silence is logged, not assumed.

## 4. Talk to the book (MCP, read-only)

From the repo root:

```sh
claude mcp add ultra-csm --env ULTRA_CSM_MCP_READONLY=1 -- \
  "$(pwd)/.venv/bin/python" -m ultra_csm.mcp_server
```

Then, in Claude Code, ask things like:

- *"Which accounts are most at risk right now, and what evidence says so?"*
- *"Give me the brief for Harborview Fleet — what changed in the last 60 days?"*
- *"Are any expansion actions currently held, and what's blocking them?"*
- *"Approve the pending proposal for Sagebrush Transport."* — it will refuse:
  write tools return a typed `MCP_READONLY` error enforced in the server process,
  not left to the model's judgment.

Every answer is grounded in the same deterministic tools the agent uses; the model
narrates, it never computes health. A captured transcript of exactly this session
shape lives at `demo_state/mcp_readonly_transcript.json` (`make mcp-readonly-demo-csm`).

## 5. The full artifact bundle

```sh
make demo
```

Runs the scorecard, spine regression, Slot A classifier scorecard, earned-autonomy
report, all three simulated connector onboardings (Attio, Gainsight, product
telemetry — real explorer/mapping code against fake transports, degrading honestly
to `unknown` rather than guessing), the MCP transcript, and the oversight report.

## 6. The audit question

```sh
make oversight-report
```

Open `demo_state/oversight_report.md`. This is the document a reviewer, auditor, or
security team asks for when someone claims "humans oversee this AI": every verdict
with its proposal id, payload-hash-bound outbound receipts, suppression history,
breaker trips and operator resets, the judge-validation evidence quoted verbatim,
and autonomy tier provenance. Section 8 lists what is NOT instrumented — the report
would rather admit a gap than imply coverage.

## Where the claims live

- `STATUS.md` — rendered from artifacts, never hand-written (`make status` fails if stale).
- `docs/DECISION_LOG.md` — append-only record of non-obvious decisions and the
  evidence behind them, including the judge validation methodology.
- Every artifact carries a machine-readable `claim_boundary` stating what it does
  and does not prove. Simulation is labeled simulation, everywhere.
