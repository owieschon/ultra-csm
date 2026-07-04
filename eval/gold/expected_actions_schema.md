# Expected-actions gold schema (Universe v2 grading substrate)

`eval/gold/fleetops_expected_actions.json` is a JSON array of rows in this
shape, one row per (account, checkpoint day) pair from
`docs/SYNTHETIC_UNIVERSE_BIBLE.md`:

```json
{
  "tenant": "fleetops",
  "account_slug": "pinehill-transport",
  "checkpoint_day": 50,
  "mode": "shadow",
  "required": {
    "signal": "reply_latency_trend",
    "motion_in": ["personal_email", "escalation"],
    "evidence_must_include": ["<det_id or signal name>"]
  },
  "forbidden_motions": [],
  "notes": "bible §1 during-checkpoint"
}
```

## Field reference

- `tenant` — always `"fleetops"` for this seed file; other tenants get
  their own `<slug>_expected_actions.json` sibling file when their
  workstream lands (see `docs/UNIVERSE_V2_CONVENTIONS.md` D5).
- `account_slug` — the bible's account slug (matches
  `ultra_csm.data_plane.fixtures.account_id_for`'s input).
- `checkpoint_day` — the bible's named checkpoint day for that arc.
- `mode` — one of three values, FINAL semantics (bible, D3):
  - `"shadow"` — the scripted CSM already acted; the agent's output is
    graded against the script's own action as reference behavior.
  - `"gap"` — the scripted CSM missed it; the agent's recommendation is
    the only correct action and silence is a failure.
  - `"none"` — the correct action is no action (controls, herrings).
- `required.signal` — the extractor/signal_extractor function name (or
  fixture-level fact, e.g. `"case_count"`) an ideal agent's evidence should
  cite. `null` for `mode: "none"` rows (no signal should fire).
- `required.motion_in` — the set of playbook motions
  (`knowledge/tenants/fleetops/playbooks.json`'s `PLAYBOOK_MOTIONS` vocabulary)
  that count as a correct action for this checkpoint. Empty for `mode:
  "none"` rows.
- `required.evidence_must_include` — real, computed identifiers (a CRM
  case UUID via `det_id("case", ...)`, or a named signal like
  `"reply_latency_trend"` when no single fixture id captures the evidence)
  that must appear in the agent's cited evidence. Never a canary token
  (see the bible's Canary spec) and never a fabricated id — every value
  in the seed file was computed by calling the real fixture functions, not
  invented.
- `forbidden_motions` — motions that would be a grading failure if
  proposed at this checkpoint, independent of `motion_in`.
- `notes` — a short human-readable pointer back to the bible section.

## Validation

`eval/gold/fleetops_expected_actions.json` must satisfy, and
`tests/test_expected_actions_gold.py` asserts:

1. Every row's `mode` is one of `shadow`/`gap`/`none`.
2. Every row's `account_slug` resolves via
   `ultra_csm.data_plane.fixtures.account_id_for`.
3. `mode: "none"` rows have empty `required.motion_in` and
   `required.signal: null`.
4. `mode` in `{"shadow", "gap"}` rows have a non-empty `required.motion_in`
   drawn only from `ultra_csm.knowledge.PLAYBOOK_MOTIONS`.
5. At least 18 rows exist (one per checkpoint across the bible's six
   scripted arcs) — the battery's own coverage floor, so a future edit
   can't silently drop a checkpoint.

## Anti-Goodhart note

Same discipline as `eval/narrative_battery.py`: this file is graded
*against* the bible, not the other way around. A row may be corrected only
when the bible itself changes (a new beat, a corrected checkpoint) — never
edited to match whatever an agent currently outputs.
