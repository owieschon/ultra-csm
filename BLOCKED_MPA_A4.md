# MP-A Phase A4 STOP

Phase A4 stopped on its explicit drift condition.

## What Changed

The attempted implementation moved Risk/Expansion precedence construction from API inline derivation to `RiskLensResult` / `ExpansionLensResult` outputs via a pure `precedence_packets_from_lens_results(...)` adapter and a write-free projection gate.

## Drift Observed

Focused gate:

```text
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 .venv/bin/python -m pytest \
  tests/test_precedence.py \
  tests/test_api.py::TestGovernanceEndpoints::test_delegation_queue_groups_pending_proposals \
  tests/test_api.py::TestGovernanceEndpoints::test_verdict_precedence_recheck_uses_proposals_own_day_not_static_default -q
```

Result:

```text
21 passed, 1 failed, 1 warning
FAILED tests/test_api.py::TestGovernanceEndpoints::test_delegation_queue_groups_pending_proposals
assert held["action"]["account_id"] == ACME_LOGISTICS
E AssertionError: assert 'b2178254-7d72-55e3-84af-27846a0cb7d5' == 'a317f5e7-575e-5879-8256-9082e40ef19f'
```

Existing behavior held the first delegation expansion action for `ACME_LOGISTICS` (`a317f5e7-575e-5879-8256-9082e40ef19f`). Under lens-output precedence packets, the first held expansion action became `b2178254-7d72-55e3-84af-27846a0cb7d5`.

## STOP Reason

The MP-A Phase A4 prompt says to STOP if any existing precedence/hold test asserts a different outcome under lens outputs. This is exactly that case. I did not rebaseline the test, did not silently accept the new hold ordering/account, and restored the worktree to a report-only state.

## Receipt

The attempted diff was captured locally before restore:

```text
/tmp/mpa-a4-drift.diff
384 lines
```

No runtime code changes are included in this branch.
