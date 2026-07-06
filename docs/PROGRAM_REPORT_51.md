# Program Report 51 — Harvest 30: Wire Risk and Expansion lenses into the live tick loop

Branch `codex/lens-trigger-wiring` off synced `main` (96bda58, report 33 /
PR #50). `lens_risk.py` (528 lines) and `lens_expansion.py` (565 lines)
were fully built, deterministic, evidence-citing lenses — README calls
both "deterministic lens built" in the "one model, three lenses"
architecture section — but neither was ever called from the live tick
loop: `triggers.py:34` hard-coded `KNOWN_LENSES = frozenset({"ttv"})`,
rejecting any trigger config naming `"lens": "risk"`/`"expansion"` at
parse time, and `run_tick_with_config` always called
`run_time_to_value_sweep` regardless of a fired trigger's `action.lens`
value. This wires both lenses into the same live loop the TTV lens
already uses.

## Tripwires

None. Zero STOPs, IF/THEN count 1 (well under the threshold of 8), no
gate retries.

## IF/THEN branches taken

1. `tests/test_triggers.py:156`'s `test_trigger_config_fails_closed_for_
   unknowns` parametrize used `{"action": {"lens": "risk", "scope":
   "account"}}` as its example of an unrecognized lens value expected to
   raise `TriggerConfigError`. Widening `KNOWN_LENSES` to include `"risk"`
   makes this specific case no longer actually invalid — the test's
   INTENT (fail-closed on a bad lens value) is unchanged, only its
   example value was stale. Updated to `"not_a_real_lens"`, a value
   guaranteed to stay invalid regardless of future lens additions. This
   is a fixture-value update preserving a test's actual intent under an
   intentional, dispatch-sanctioned allowlist expansion — not an
   anti-Goodhart edit (K14): the test still asserts exactly what it
   always asserted, just with a genuinely-still-unknown example.
   Confirmed additive-only elsewhere: `test_default_trigger_config_is_
   ttv_only` reads `config/trigger_config.json` (the real production
   config, untouched by this dispatch — only `_demo_trigger_config()` in
   `tick.py` gained new entries), so that assertion needed no change.

## Owner Asks

None.

## STOP conditions hit

None.

## Skeptical Reviewer paragraph

This dispatch WIRES two already-built, already-evidence-citing
deterministic lenses into the live tick loop — it does not change either
lens's own detection logic (`lens_risk.py`/`lens_expansion.py` are
untouched), does not add cohort-collapse or proposal-governance behavior
beyond what each lens already implements on its own (`collapse_cohorts`
stays TTV-lens-specific per its own docstring), and the new
`weekly_risk_sweep`/`weekly_expansion_sweep` demo trigger entries are
illustrative wiring — proof that the dispatch mechanism works end to
end — not a validated production trigger policy. `config/trigger_config
.json` (the file `run_tick_cli`, the real `ucsm tick` entrypoint, actually
loads) is untouched and still only names the TTV lens; a future dispatch
deciding WHEN risk/expansion should actually fire in production (trigger
cadence, cooldown policy, which accounts) is separate, real work this
report does not do.

## Final verification table

| Check | Command | Result |
| --- | --- | --- |
| Baseline (pre-edit) | `LC_ALL=en_US.UTF-8 make eval` | `668 passed, 1 skipped` (547s, slow due to ~9 concurrent worktrees from another emitter session's parallel queue running `make eval` simultaneously on this machine — CPU contention, not a defect) |
| Zero-drift (post-edit) | `LC_ALL=en_US.UTF-8 make eval` | `671 passed, 1 skipped` — exactly +3 (the two new parametrized risk/expansion dispatch tests + the TTV-unchanged companion test), 1 skip unchanged, no pre-existing assertion changed |
| New dispatch tests | `.venv/bin/python -m pytest tests/test_tick.py -q -k "risk_and_expansion or ttv_lens_dispatch_unchanged"` | `3 passed` |
| KNOWN_LENSES + existing lens scorecards | `.venv/bin/python -m pytest tests/test_triggers.py tests/test_agent1_lenses.py -q` | `18 passed` |
| Dry-run fire proof | manual `run_tick_with_config(..., dry_run=True)` with a `"lens": "risk"` trigger | `fired: ['weekly_risk_sweep']`, `action.lens: 'risk'` |
| Lint / hygiene / status / clean | `make lint hygiene status && git diff --check` | `All checks passed!` / hygiene exit 0 / `STATUS.md is current` / exit 0 |

## Receipts appendix

- Commit `16d7aa9` — "Lens wiring: KNOWN_LENSES widened, tick.py
  dispatches risk/expansion lenses" — 4 files changed, 174 insertions(+),
  24 deletions(-) (`src/ultra_csm/tick.py`, `src/ultra_csm/triggers.py`,
  `tests/test_tick.py`, `tests/test_triggers.py`).
- Dormancy premise, BEFORE (precondition check, pre-edit): `grep -rn
  "lens_risk\|lens_expansion" src/ultra_csm/tick.py
  src/ultra_csm/agent1/sweep.py src/ultra_csm/api.py` → no match.
- Dormancy closed, AFTER: `grep -n "lens_risk\|lens_expansion"
  src/ultra_csm/tick.py` → `tick.py:23-24` (imports),
  `tick.py:779` (demo config comment referencing both `*_LENS_SPEC`
  constants).
- `KNOWN_LENSES` at `src/ultra_csm/triggers.py:34` →
  `frozenset({"ttv", "risk", "expansion"})`.
- `run_tick_with_config`'s branch (`src/ultra_csm/tick.py`, the
  `for fired in evaluation.fired:` loop) — `"risk"`/`"expansion"` call
  `run_risk_lens`/`run_expansion_lens` via `_lens_payload_for_trigger`;
  the `else` branch (TTV) is unchanged from before this dispatch, moved
  inside the branch verbatim.
- New tests: `tests/test_tick.py::test_tick_dispatches_risk_and_
  expansion_lenses[risk]`, `[expansion]`,
  `test_tick_ttv_lens_dispatch_unchanged`.
- `config/trigger_config.json` — confirmed byte-unchanged (not in this
  dispatch's Ownership map; `git diff` shows no changes to this file).
