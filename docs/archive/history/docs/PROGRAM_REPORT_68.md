# Program Report 68 - MP-B Internal Bridge Handoff Spike

MP-B tested one internal handoff pair end to end: a deterministic route from
grounded CRM support/feedback cases to Engineering or Product, an
evidence-complete internal packet, and a first-class `abstained` field. The
spike proves the pattern is buildable for this one pair. It does not claim
real-world durability or owner-confirmed spike validation.

## DoD Evidence

| Area | Evidence |
| --- | --- |
| Report number claim | `~/ultra-csm-dispatches/harvest/00_HARVEST_PLAN.md` registry row says `next report: 68`; no `docs/PROGRAM_REPORT_68.md` existed before this phase. |
| Wave-0 oracle | `docs/HANDOFF_SPIKE_SPEC.md` and `eval/gold/fleetops_handoff_expected_actions.json` define 18 owner-reviewed rows for tenant `fleetops_handoff`: 14 `gap`, 4 `none`. |
| Blind delivery protocol | OA-B1 was delivered as Part A account states first, then Part B oracle rows after the owner's independent calls; Addendum 1 reconciliation is recorded in PR #98. |
| Deterministic routing | `src/ultra_csm/internal_bridge/routing.py` emits `target`, `motion`, `signal`, `evidence`, `abstained`, and `reason` without an LLM call. |
| Sweep integration | `CSMWorkItem.internal_bridge_decision` is additive; existing Slot A/Slot B disposition and action selection are unchanged. |
| Packet schema | `src/ultra_csm/internal_bridge/packet.py` carries `abstained: bool`, `reason`, packet body, and exact `cited_evidence_ids`. |
| B3 validation artifact | `eval/internal_bridge_validation_report.json` reports `routing_core_hard_ok=true`, `routing_failed_cases=[]`, 18 cases, zero confidently-wrong cells, and zero packet prose failures. |
| Capability map | `docs/CAPABILITY_MAP.md` marks only spike-scoped IB-1/IB-2/IB-3 as built; IB-4, IB-5, and VM-8 remain not built. |

## Routing Matrix

| Oracle target cell | Agent target cell | Count |
| --- | --- | ---: |
| `engineering` | `engineering` | 8 |
| `product` | `product` | 4 |
| `engineering|product` | `engineering` | 2 |
| `abstain` | `abstain` | 4 |

Confidently-wrong cells: 0.

Abstain axis:

| Axis cell | Count |
| --- | ---: |
| Oracle abstain / agent abstain | 4 |
| Oracle route / agent route | 14 |
| Oracle route / agent abstain | 0 |
| Oracle abstain / agent route | 0 |

## Packet Prose Scores

The packet prose lane reused the existing Slot B judge: `claude-sonnet-5`,
`quality-judge-v8`, `KAPPA_GATE=0.6`; `judge_validation_status.validated=true`
in the artifact. No new judge was created or validated.

| Dimension | Score distribution |
| --- | --- |
| `grounding_fidelity` | 18 x 3 |
| `on_task_relevance` | 18 x 3 |
| `account_specificity` | 14 x 3, 4 x 2 |
| `priority_fidelity` | 18 x 2 |
| `tone_fit` | 18 x 3 |
| `safety_boundary` | 18 x 3 |

Packet prose failures: 0. `priority_fidelity` is 18 x 2 because the adapter
supplies the internal-bridge signal as the priority-like factor but no priority
score; this is recorded as a boundary of reusing the Slot B quality dimensions
for an internal packet.

## IF/THEN Taken

1. IF a row genuinely split Engineering vs Product, THEN the oracle widened
   the allowed `motion_in`/target set instead of forcing a single convenient
   answer. This is why B0-09 and B0-14 are `engineering|product` cells.
2. IF a same-model ambiguity probe disagreed on B0-04/B0-06, THEN the rows
   stayed Product per owner-confirmed oracle but were recorded as gap/none
   fence-sitters.
3. IF the second pass made B0-15 read Engineering-only, THEN the widened row
   collapsed to Engineering-only before build.
4. IF live judge execution required the Anthropic client, THEN the missing
   package was installed into the local venv only; no dependency file changed.
5. IF the live judge returned malformed/truncated JSON, THEN the B3 runner
   added bounded parser retries and a terse fallback. The committed artifact
   contains no fallback cases.
6. IF `make eval` regenerated `eval/mcp_operator_transcript.json` with the
   additive bridge field, THEN that generated artifact was reverted because it
   was outside the B1/B2/B3/B4 ownership fences.

## Owner Asks

| Ask | Status |
| --- | --- |
| OA-B1 confirm routing oracle | Completed in B0. The owner reconciled the oracle to 14 `gap` / 4 `none`, confirmed widened rows, and accepted the recorded residuals. |
| OA-B2 optional second labeler | Not supplied. The report states single-oracle; the same-model ambiguity probe is disclosed as correlated and not IRR. |
| OA-B3 merge routing/packet/gold PRs | Open. PR #97, #98, and #99 remain owner-review PRs. |
| OA-B4 optional VM-8 outcome-rail track | No owner direction to scaffold in this dispatch. VM-8 remains a named parallel track, not delivered here. |

## STOP Conditions Hit

No K14 oracle/threshold edit was made to force a pass. No `submit_verdict` was
cast. No customer-facing send occurred. No secret value was printed or
committed. The only owner-gated stop that remained open is OA-B2's independent
human second labeler, which was skipped and disclosed rather than fabricated.

## Skeptical Reviewer

This spike does not prove real-world durability. A green account that churns
anyway is still measured nowhere until VM-8 outcome rail instrumentation exists.
It does not prove the routing ceiling beyond a single owner-confirmed oracle;
there is no independent human inter-rater kappa. It does not prove IB-4 feedback
loop closure, IB-5 QBR narrative generation, or the other five asserted
archetypes. Those archetypes must clear their own blind oracle, deterministic
routing, packet, and matrix gates before the result generalizes.

## Final Verification Table

| Phase | Branch / PR | Receipt |
| --- | --- | --- |
| B0 oracle | PR #96, merged to `main` as `fc68f2e` | Loader accepted 18 rows: 14 `gap`, 4 `none`; `jq empty eval/gold/fleetops_handoff_expected_actions.json` passed. |
| B1 routing | PR #97, open | `PYTHONPATH=src:. .venv/bin/python -m eval.internal_bridge_battery --check` passed; `make eval` reported 812 passed, 1 skipped, 1 warning before PR. |
| B2 packet | PR #98, open | Packet schema and evidence-citation checks passed; `make eval` reported 815 passed, 1 skipped, 1 warning before PR. |
| B3 validation | PR #99, open | Validation artifact reports `routing_core_hard_ok=true`, zero confidently-wrong cells, zero packet prose failures; post-rebase `make eval` reported 817 passed, 1 skipped, 1 warning. |
| B4 report | PR pending | `make setup` completed in the B4 worktree; `make hygiene` passed via `scripts/hygiene_scan.py`. |

## Receipts Appendix

- B0 PR: https://github.com/owieschon/ultra-csm/pull/96.
- B1 PR: https://github.com/owieschon/ultra-csm/pull/97.
- B2 PR: https://github.com/owieschon/ultra-csm/pull/98.
- B3 PR: https://github.com/owieschon/ultra-csm/pull/99.
- Oracle spec: `docs/HANDOFF_SPIKE_SPEC.md`.
- Oracle rows: `eval/gold/fleetops_handoff_expected_actions.json`.
- Routing code: `src/ultra_csm/internal_bridge/routing.py`.
- Packet code: `src/ultra_csm/internal_bridge/packet.py`.
- Validation runner: `eval/internal_bridge_validation.py`.
- Validation artifact: `eval/internal_bridge_validation_report.json`.
- Decision log: `docs/DECISION_LOG.md`.
- Capability map: `docs/CAPABILITY_MAP.md`.
