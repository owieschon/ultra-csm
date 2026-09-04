# Representative reading path

Follow one customer action from source evidence to a payload-bound receipt, then the
tests that attack every step. Links are pinned to
[`62b4972`](https://github.com/owieschon/ultra-csm/tree/62b497286352fd2db1b6d67187e82d058effaed5),
so each resolves to the exact line even after later edits move the code.

## 1. Source evidence -> proposal

[`sweep.py#L177 run_time_to_value_sweep`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/src/ultra_csm/agent1/sweep.py#L177)
walks the tenant's accounts, and for each calls
[`sweep.py#L968 _work_item_for_account`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/src/ultra_csm/agent1/sweep.py#L968),
which assembles evidence, computes a deterministic priority score, and resolves a
recipient. When customer contact is allowed,
[`sweep.py#L1204 _propose_outreach`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/src/ultra_csm/agent1/sweep.py#L1204)
builds the payload and calls `gate.propose`. The draft body behind that payload comes
from [`sweep.py#L1190 _write_slot_b_with_fallback`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/src/ultra_csm/agent1/sweep.py#L1190),
which reports its `draft_mode` as `fixture`, `live`, or `template_fallback` (on a writer
exception or contract violation). `none` is a separate, unset default on
`CSMWorkItem.draft_mode`, never returned by this function.

## 2. Configured human approval

[`gate.py#L120 ActionGate.propose`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/src/ultra_csm/governance/gate.py#L120)
hashes the payload (`payload_sha256`) and inserts the proposal as `pending`.
[`gate.py#L173 ActionGate.record_verdict`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/src/ultra_csm/governance/gate.py#L173)
locks the stored row, applies the verdict, and — for autonomy tier 2+ — requires the
approving principal to be `kind='human'` and distinct from the proposing actor
([`gate.py#L243-L259`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/src/ultra_csm/governance/gate.py#L243-L259)).
That principal is not caller-asserted: it comes from
[`_api_helpers.py#L205 _ensure_human_principal`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/src/ultra_csm/_api_helpers.py#L205),
which maps a bearer token (or the loopback-only demo no-auth path, via
[`_api_helpers.py#L155 resolve_write_principal`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/src/ultra_csm/_api_helpers.py#L155))
to a durably stored `kind='human'` row. A `revise` verdict atomically rewrites the
proposal's payload and hash to the human's edit before approving it, so the revised
body — not the original draft — is what gets authorized.

## 3. Payload recheck before commit

[`gate.py#L334 ActionGate.assert_payload_bound`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/src/ultra_csm/governance/gate.py#L334)
re-reads the durable proposal and verdict rows and requires the payload a committer is
about to execute to hash-match exactly what was authorized. Both
[`committers.py#L115 SimOutboundCommitter.commit`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/src/ultra_csm/committers.py#L115)
and `SimCrmActivityCommitter.commit` call it before touching their simulated target —
never the in-memory `GateOutcome` alone, since that object is caller-constructible.

## 4. Idempotency and receipt

Still inside `SimOutboundCommitter.commit`, a key derived from the proposal id, the
authorized payload hash, and the target
([`committers.py#L331 _idempotency_key`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/src/ultra_csm/committers.py#L331))
is leased through `gate.acquire_sim_idempotency_attempt`
([`gate.py#L468`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/src/ultra_csm/governance/gate.py#L468))
before the write to the simulated outbox happens. A `failed` reservation, or a `pending`
one whose lease has expired (or was never set), can be reclaimed by a new attempt; an
active unexpired lease or a `completed` result cannot. On a key that is already
`completed`, the committer returns a freshly synthesized receipt with `committed=False`
rather than writing again; if it instead finds the canonical target row present but
owns a reclaimed failed/expired lease, it repairs the missing audit entry before
marking the key complete.

## Negative tests

[`tests/test_action_gate_machine.py`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/tests/test_action_gate_machine.py)
attacks each step above:

- [`L305 test_agent_kind_self_approve_rejected_for_tier_two`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/tests/test_action_gate_machine.py#L305) —
  the proposing actor approving its own tier-2 proposal is rejected.
- [`L320 test_agent_kind_distinct_approver_still_rejected_for_tier_two`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/tests/test_action_gate_machine.py#L320) —
  an approver distinct from the actor but not `kind='human'` is still rejected;
  distinctness alone is not sufficient without human-kind.
- [`L224 test_db_rejects_approved_outreach_without_contact_consent`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/tests/test_action_gate_machine.py#L224) —
  the database backstops consent even if an app-level check is bypassed.
- [`L123 test_gate_tampered_payload_refused`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/tests/test_action_gate_machine.py#L123) —
  a payload edited after approval fails the hash-bound recheck.
- [`L264 test_stale_snapshot_cannot_record_second_verdict`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/tests/test_action_gate_machine.py#L264) —
  a second verdict against an already-decided proposal loses the compare-and-set.
- [`L86 test_gate_revise_applies_revised_payload`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/tests/test_action_gate_machine.py#L86) —
  after a revise, the original payload no longer authorizes; only the edited one does.

[`tests/test_demo_loop.py#L171 test_sim_committers_recover_pending_crash_reservations`](https://github.com/owieschon/ultra-csm/blob/62b497286352fd2db1b6d67187e82d058effaed5/tests/test_demo_loop.py#L171)
proves the idempotency retry statement above end to end: a planted `OSError` between
the outbox append and the audit append leaves the reservation `failed`; the retry
reclaims that failed lease, repairs the missing audit entry, and marks the key
`completed`; a further retry against the now-`completed` key returns `committed=False`
without appending a second customer action.

The adjacent UI is `ui/components/QueueDetail.tsx` and `ui/components/ActionRail.tsx`.
It distinguishes rule-based priority from a draft, labels the draft source, and shows
only the selected proposal's receipt. The hosted build simulates this browser state —
approve, deny, and edit never reach the gate, a committer, or a live send, and reloading
clears the decision; see [`DEMO.md`](DEMO.md) and [`LIMITS.md`](LIMITS.md) for what
that boundary does and does not prove (no calibrated judge, no independent usage, no
real person authenticated).

## Structural debt

`agent1/sweep.py` is oversized because it still combines evidence assembly, value-model
projection, motion selection, drafting fallback, proposal construction, and work-item
serialization. The intended extraction follows those responsibilities. Until that
decomposition is complete, this file remains in the reading path because it is the
runtime path the tests exercise.

`api.py` and `mcp_server.py` are also too large. They are not part of this representative
slice and should be split by resource or tool family before they become recommended
extension points.
