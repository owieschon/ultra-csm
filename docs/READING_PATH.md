# Representative reading path

<!-- clean-docs:purpose -->
Read these four files in order. Together they show the normal customer-action path,
including its least flattering seam; none is an isolated showcase module.
<!-- clean-docs:end purpose -->

1. **`src/ultra_csm/agent1/sweep.py`** — joins source evidence, computes deterministic
   priority, requests a bounded draft, and emits a pending proposal. Start at
   `run_time_to_value_sweep`, then `_propose_outreach`.
2. **`src/ultra_csm/governance/gate.py`** — records approve, deny, or revise; verifies the
   approver is a distinct human principal; and binds authorization to the effective
   payload hash.
3. **`src/ultra_csm/committers.py`** — rechecks the authorized hash, reserves an
   idempotency key, writes only to a simulated target in the public demo path, and emits a
   receipt.
4. **`tests/test_action_gate_machine.py`** — attacks the promise: self-approval,
   non-human approval, missing consent, post-approval tampering, duplicate verdicts, and
   revised-payload substitution.

The adjacent UI is `ui/components/QueueDetail.tsx` and
`ui/components/ActionRail.tsx`. It distinguishes rule-based priority from AI-written
drafts and shows only the selected proposal's receipt.

## Named debt

`agent1/sweep.py` is oversized because it still combines evidence assembly, value-model
projection, motion selection, drafting fallback, proposal construction, and work-item
serialization. The correct extraction is by those responsibilities—not by moving a few
functions into a cosmetic reviewer-only façade. Until that decomposition is complete,
this file remains in the reading path so the repository does not hide its normal shape.

`api.py` and `mcp_server.py` are also too large. They are not part of the representative
slice and should be split by resource/tool family before either is promoted as visible
craft.
