# Executor Handoff — Lane J: The Sim Morning (operator demo mode)

Same protocol as prior lanes (one-shot autonomy, IF/THEN criteria, verify by
executing). This lane builds the **first-value experience**: a self-narrating,
zero-credential "morning as a CSM with an agent" that a stranger can reach from
`claude mcp add` in under five minutes, experiencing the full designed loop —
sweep → prioritized queue → evidence → revise → verdict → receipt → refusal —
against the simulated book.

## Why this is the demo (context)

The product's designed value is the working relationship, not Q&A over data:
Agent 1 triages the book, drafts evidence-grounded outreach, and can act only
through gated proposals a human approves, denies, or revises. The current
frictionless MCP path is read-only and therefore hides exactly this. Lane J makes
the loop itself the frictionless front door. The user's own data comes later
(relay/ingest lanes); this lane needs no external data because what it
demonstrates is the loop.

## The experience script (build to this, beat by beat)

Setup target: `pip install` + `claude mcp add` + typing anything. The server's
MCP `instructions` field scripts the host model into the role: open with the
morning briefing, guide the beats, offer the next move after every action. The
user never needs to know what to ask.

- **Beat 0 — briefing.** User types "start" (or anything). A `get_morning_briefing`
  tool returns: sim date, book summary (accounts, ARR), and the headline — N
  accounts need you today, X drafts awaiting verdict, one action blocked on
  consent, one expansion held behind an open risk, $Y ARR stalled before first
  value. The sweep already ran at boot; the briefing is instant.
- **Beat 1 — queue.** Ranked work items; every priority score shown as legible
  factor arithmetic (`milestones_overdue +50, health_red +30`), never a bare
  number.
- **Beat 2 — one account deep.** The existing account brief: overdue milestone
  with telemetry evidence, and the draft citing those exact evidence ids.
- **Beat 3 — revise.** "Shorten it and mention the Q3 rollout" → revise verdict →
  bounded re-draft → superseding proposal returns for verdict; original preserved.
- **Beat 4 — approve.** Receipt with payload sha256 bound to exactly the approved
  text, committed to the clearly-sim outbox.
- **Beat 5 — the catch.** The differentiator. The host model should OFFER this
  ("want to see what happens if you overreach?"). "Approve everything" /
  outreach to the no-consent account / approving the held expansion → typed
  refusals (`CONSENT_MISSING`, `PRECEDENCE_HELD` with blocking ref and release
  conditions). Enforced in the server process, not model judgment.
- **Beat 6 — receipts.** Session closer: "your 5 minutes produced 2 approvals,
  1 revision, 2 refusals — here is your audit trail," rendered from the verdicts
  this session actually cast (a session-scoped slice of the oversight-report
  pattern). Ends with the exit ramp: a `get_next_steps` tool pointing at the
  real-data path.

## Build slices

### J1 — demo-operator boot mode

New env `ULTRA_CSM_DEMO_OPERATOR=1` on the MCP server:

- Full loop enabled (sweep, verdicts) with the REAL gate — no parallel gate
  implementation, no authority-logic duplication. Reuse the existing
  `ULTRA_CSM_DEMO_NOAUTH` path for tokenless local verdicts; the mode implies it.
- Every artifact and tool response carries `claim_boundary: {sim: true}` and the
  outbox is explicitly a sim outbox (this already holds — verify, don't assume).
- Sweep runs at boot so Beat 0 is instant. Read-only mode behavior is unchanged.
- Mutually exclusive with `ULTRA_CSM_MCP_READONLY` — refuse to boot with both set,
  loudly.

### J2 — Postgres friction: tiered boot (evidence already gathered)

The gate needs its store, which today needs system `initdb`/`pg_ctl`. Verified
2026-07-02 on this machine: the `pgserver` pip package (bundles real PostgreSQL
16.2 binaries) boots and accepts a psycopg connection in ~2.5 s, UTF-8, zero
system dependencies. Caveats, verified against PyPI: wheels for CPython
3.9–3.12 ONLY (none for 3.13/3.14), last release 2024-06-08 (assume
unmaintained; pin exactly).

Build: in `platform/`, `EphemeralCluster` tries system binaries first
(unchanged), falls back to `pgserver` when importable. Ship as optional extra
`demo = ["pgserver==0.1.4; python_version < '3.13'"]`. `make doctor` learns to
report which tier it used. Result: the full-loop demo is pip-only on Python
≤3.12; 3.13+ users get the existing brew path with a clear doctor message.
IF the fallback proves flaky in tests → drop it and keep brew-only; the demo
mode must not ship on an unreliable boot path.

### J3 — the narrative tools

- `get_morning_briefing`: counts + headline derived from the boot sweep and
  held/blocked state. Numbers must be derived from the actual sweep result —
  never hardcoded copy.
- `get_next_steps`: the exit ramp (real-data path, tour, oversight report).
- `suggested_next` field appended to every demo-mode tool response (one short
  affordance string, e.g. "try: revise this draft in plain English").
- Server `instructions` rewritten for demo mode to script the host-model role
  and the beat structure, including offering Beat 5. Keep readonly instructions
  as they are.

### J4 — revise verdict over MCP

`submit_verdict` gains `revise` + `edit_instruction`, routed through the SAME
`run_slot_b_revise_loop(...)` the REST API uses (`api.py` is the reference
implementation — port the semantics, share the code, do not fork it). Stable
failure codes identical to the API's (`REVISE_INSTRUCTION_REQUIRED`,
`REVISE_REFUSED`, `REVISE_BOUND_REACHED`, ...). Response carries
`superseding_proposal_id`. Readonly mode still refuses the tool entirely.

### J5 — session receipts

`get_session_ledger`: verdicts cast this session (proposal id, verdict, reason,
payload sha, receipt id where committed), plus refusal events (Beat 5 must show
up here — refusals are oversight evidence, same doctrine as the oversight
report). Render-only over what the session already recorded; no new derived
metrics; disclaimer line consistent with `scripts/oversight_report.py`.

## Decision criteria (IF/THEN)

- IF a beat needs data the synthetic book lacks (e.g. no held expansion exists
  at boot) → adjust the SIM BOOK fixtures so the state exists honestly at boot;
  never fake a tool response.
- IF the host model can't be relied on to narrate a beat → strengthen
  `instructions` and `suggested_next`; do NOT move narration into tool responses
  beyond one affordance line (tools return data, the host tells the story).
- IF revise-over-MCP can't cleanly share the API's loop code → STOP and flag;
  a forked second revise path is worse than no MCP revise.
- IF pgserver misbehaves → cut J2 to brew-only rather than shipping flaky boot.

## Out of scope

Relay/ingest work (sparsity review surface, unknown-verdict confirmations — those
are the next ingest lane, seeded by docs/FOREIGN_CORPUS_FINDINGS.md), live
connectors, real email delivery, any change to judge/gold lanes, README/TOUR
restructure beyond adding the demo-mode section.

## Verification gates and DoD

- `make eval` / `lint` / `hygiene` green; new tools tested (briefing derives from
  sweep, revise supersedes, session ledger records refusals, dual-env boot
  refusal).
- An end-to-end stdio MCP session transcript (initialize → briefing → queue →
  revise → approve → refusal → session ledger) captured as a fixture artifact,
  like `demo_state/mcp_readonly_transcript.json` — deterministic and committed.
- `make doctor` reports the boot tier; on a Python ≤3.12 venv with no system
  Postgres, `ULTRA_CSM_DEMO_OPERATOR=1` boots via pgserver (test with PATH
  stripped, the Lane-of-record technique in git history).
- QUICKSTART/TOUR gain the demo-operator section (one command + the beats).
- Branch off current `main`; new branch `codex/lane-j-sim-morning`; PR, no direct
  push to main. Work in a separate worktree — the main checkout may be in use.
