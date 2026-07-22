# Representative reading path

Read these four files in order to follow one customer action from source evidence to a
payload-bound receipt through the implementation used by the tests.

1. **`src/ultra_csm/agent1/sweep.py`** joins source evidence, computes deterministic
   priority, requests a bounded draft, and emits a pending proposal. Start at
   `run_time_to_value_sweep`, then `_propose_outreach`. The draft mode is explicit:
   fixture, live model, labeled template fallback, or none.
2. **`src/ultra_csm/governance/gate.py`** records approve, deny, or revise; verifies the
   stored approver is human-kind and distinct from the proposing actor; and binds
   authorization to the effective payload hash. `src/ultra_csm/_api_helpers.py` owns the
   bearer-token mapping that creates that configured identity.
3. **`src/ultra_csm/committers.py`** rechecks the authorized hash, reserves an
   idempotency key, writes only to a simulated target in the public demo path, and emits a
   receipt.
4. **`tests/test_action_gate_machine.py`** attacks the promise: self-approval,
   non-human approval, missing consent, post-approval tampering, duplicate verdicts, and
   revised-payload substitution.

The adjacent UI is `ui/components/QueueDetail.tsx` and
`ui/components/ActionRail.tsx`. It distinguishes rule-based priority from a draft,
labels the draft source, and shows only the selected proposal's receipt.

## Structural debt

`agent1/sweep.py` is oversized because it still combines evidence assembly, value-model
projection, motion selection, drafting fallback, proposal construction, and work-item
serialization. The intended extraction follows those responsibilities. Until that
decomposition is complete, this file remains in the reading path because it is the
runtime path the tests exercise.

`api.py` and `mcp_server.py` are also too large. They are not part of this representative
slice and should be split by resource or tool family before they become recommended
extension points.
