# Executor handoff addendum — Lane F (2026-07-02, archived)

> Historical process record. It does not define current implementation or operating guidance.
> Use the [documentation index](../../../README.md) for current pages.

This was an addendum to `EXECUTOR_HANDOFF.md` (rev 2). It used the same §X check-in triggers and
one-shot autonomy contract. Read this AFTER the main handoff.

**What Lane F adds:** configurable **schedule**, **deadline**, and **event** triggers so
the agent runs proactive work — not just fixed cycles. Design principle (do not deviate):
**separate "what should fire" from "when the process wakes up."** Trigger evaluation is a
pure, deterministic function over (state, previous snapshot, clock, config). The thing
that wakes the process is any boring external beat (cron / CI / an API call) driving ONE
entrypoint: `ucsm tick`. No daemon, no scheduler infrastructure, no LLM anywhere in
trigger evaluation.

---

## Position in the plan

- **Depends on:** Lane A merged (cli.py registration) AND Lane B merged (snapshot feed
  for event detection). May run **concurrently with Lane E** (disjoint files).
- **Merge order becomes:** A → B → D → C2–C4 → E ∥ F (E and F merge in whichever order
  finishes; run the full verification suite after each).
- **Files owned (exclusive):** NEW `src/ultra_csm/triggers.py`, NEW
  `src/ultra_csm/tick.py`, NEW `config/trigger_config.json`, NEW
  `tests/test_triggers.py` + `tests/test_tick.py`, NEW `eval/trigger_battery.py` (+ its
  artifact), Makefile target `tick-demo-csm`. Post-A-merge, Lane F may touch `cli.py`
  ONLY to register the `tick` subcommand (single, minimal diff).

## F1 — Trigger config (extend the existing grammar; do NOT invent a DSL)

Triggers are declarative entries in the same `field op value` style as the value-model
config, with exactly TWO new operators: `within_days` (deadline) and `transition`
(event; value = `[from, to]`, each side a band value or `*`). Example shape:

```json
{
  "config_version": "triggers-v1",
  "triggers": [
    {"name": "daily_ttv", "kind": "schedule", "every": "1d",
     "action": {"lens": "ttv", "scope": "book"}},
    {"name": "renewal_window", "kind": "deadline",
     "when": [{"field": "renewal_date", "op": "within_days", "value": 90}],
     "action": {"lens": "risk", "scope": "account"}, "cooldown_days": 30},
    {"name": "band_drop", "kind": "event",
     "when": [{"field": "health_band", "op": "transition", "value": ["green", "*"]}],
     "action": {"lens": "risk", "scope": "account"}, "cooldown_days": 14}
  ]
}
```

Loader rules (fail-closed, tested):
- Unknown `field`, unknown `op`, unknown `kind` → config load FAILS (reuse the resolver's
  validation pattern).
- Unknown `action.lens` → load FAILS. Therefore the DEFAULT shipped config references
  only lenses that exist at merge time (IF Lane E is unmerged when F lands → default
  config uses `ttv` only, with risk/expansion examples present but commented; enable them
  in the same commit that merges E, whichever lands second).
- Config is versioned and under regression like every other config: a trigger change
  re-baselines with an intended-change note.

## F2 — `evaluate_triggers` (the deterministic core)

```python
def evaluate_triggers(state, prev_snapshot, as_of, config) -> tuple[FiredTrigger, ...]
```
- **Pure function.** No I/O, no clock reads (`as_of` is an argument), no LLM. Same inputs
  → identical output, always (test: run twice, byte-identical).
- **Schedule kind:** fires when `as_of` crosses the cadence boundary since the last tick
  (last-tick timestamp comes from the tick ledger, passed in — not read inside).
- **Deadline kind:** date-field predicates vs `as_of` + horizon, over typed model/state
  fields only.
- **Event kind:** computed as a **diff between `prev_snapshot` and current state** —
  reuse `snapshot_store`'s trend/band-change math; do NOT build webhook infrastructure.
  (Live-lane webhooks later merely schedule an early re-observation; they are not a
  second trigger mechanism. Note this in the module docstring.)
- **Positive-evidence rule (hard):** missing data never fires. No previous snapshot or
  <2 points → event triggers are `unknown` → no fire. A missing date field → deadline
  trigger does not fire. Schedule triggers are exempt (they need only the clock).
- **`FiredTrigger` provenance (required fields):** trigger name, `config_version`, the
  evidence that fired it (field values / transition pair / date math), `as_of`. This
  flows into the resulting work item as evidence — every queue item must be able to
  answer "why did the agent look at this account today."
- **Noise control (deterministic):** per-trigger `cooldown_days`; a fired-ledger deduped
  by (trigger, account, condition-instance) via the existing idempotency-key pattern;
  and NEVER re-fire while a proposal created by this trigger+account is still `pending`
  (query the gate). All three have explicit not-fires tests.

## F3 — The tick runner (`ucsm tick --as-of <ts>`)

Composes existing entrypoints — it does not modify them:
1. Observe state for the tick's `as_of` (sim lane: the day's book via the existing
   simulators; store the snapshot via `snapshot_store` exactly as the API path does).
2. `evaluate_triggers(...)`.
3. For each fired trigger, run the corresponding lens sweep **scoped per the trigger**
   (`book` → full sweep; `account` → that account) by CALLING the existing sweep/lens
   functions.
4. Emit the work queue/digest artifacts + append the tick ledger entry
   (`demo_state/tick_ledger.jsonl`: as_of, fired triggers, suppressed-by-cooldown list,
   artifacts written). Suppressions are RECORDED, not silent — loudness rule applies.
5. `--dry-run` prints what would fire without running sweeps.

Authority guard (hard, tested): a trigger selects WORK, never authority. Whatever a
trigger causes still lands in the gate at the action's existing tier. There is no field
in trigger config that can name a tier, a release condition, or a recipient — the schema
simply does not have one; add a test asserting the loader rejects any such key.

## F4 — Eval battery FIRST (`eval/trigger_battery.py`)

Write and run these before/with F2–F3 (eval-first, falsification included):
1. Fires-when-should: one case per kind (schedule boundary, deadline enters horizon,
   band transition).
2. Does-NOT-fire: cooldown active; no transition (stable band); missing data (no
   snapshot; absent date field); pending-proposal suppression.
3. Reproducibility: identical tick inputs twice → identical `FiredTrigger` tuples and
   identical ledger entries.
4. Provenance: every fired trigger's evidence fields present and real.
5. **Unsafe foil:** a config attempting `{"tier": 1}` / `{"release_condition": ...}` /
   an unknown lens → loader fails closed; and a fired trigger's downstream proposal is
   asserted to carry the action taxonomy's own tier, unchanged.
6. Artifact `eval/trigger_battery.json` with `claim_boundary` (sim/fixture lane).

## F5 — Demo integration + adopter line

- `make tick-demo-csm`: run ticks across selected sim days (e.g. 0→365 step 30 plus the
  known event days) and print the firing narrative — the demo beat is: *day 61 band-drop
  fires for one account; day 240 renewal-window fires for another; day 270 a duplicate is
  suppressed by cooldown* (derive the real days from the sim book; do not hand-pick
  numbers into docs — quote the ledger).
- QUICKSTART gains one line under "going live": schedule = point cron (or any runner) at
  `ucsm tick`; webhooks later just call tick early for one account.
- `DEMO_SCRIPT`/Act 3 gains the tick beat if Lane D's script work is still open;
  otherwise note it in the demo docs.

## Decision criteria (IF/THEN)

- IF a desired trigger needs a field the typed state doesn't expose → do NOT extend the
  state in this lane; note it in the lane summary (§X only if it blocks a DoD).
- IF schedule semantics collide with an externally-driven beat (two ticks in one period)
  → the ledger's last-fired timestamp wins; second tick records `suppressed: schedule`.
- IF Lane E is unmerged at F's merge time → default config = `ttv` triggers only (see F1).
- IF tempted to add a daemon, background thread, webhook server, or queue → STOP; out of
  scope by design. The external beat is the adopter's cron.

## Lane F DoD

- `evaluate_triggers` pure + reproducible (tested twice-identical); all battery cases
  green including every not-fires case and the unsafe foil.
- `ucsm tick --as-of` runs offline end-to-end on the sim lane; ledger records fires AND
  suppressions; `--dry-run` works.
- Provenance flows into work items (a queue item shows its firing trigger as evidence).
- No modification to sweep/lens/gate internals; cli.py diff is the single registration.
- `make tick-demo-csm` produces the firing narrative from the ledger; QUICKSTART line
  added; universal suite + hygiene green; pushed.
