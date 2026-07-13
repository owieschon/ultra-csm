# MP-D2 Wave 2 Validation Receipt

## Scope

Wave 2 adds the validation spine for `CSMWorkPacket` without treating
contested judgment as correctness.

Added:

- `eval/work_packet_eval.py`
- `make work-packet-eval`
- adversarial tests for ungraded fields, laundered inference, validated
  hypothesis evidence steps, CTA/gate drift, and feedback reason mining
- `RejectionLedger` reason mining via `recurring_rejection_reasons`
- explicit `proposal_status` in `GovernanceBoundary` so CTA validation does
  not infer pending-ness from text

## Grading Contract

- Structural/routing fields: deterministic oracle.
- Governance/CTA fields: deterministic oracle against
  `governance/csm_actions.py` and packet proposal status.
- Evidence chain: deterministic provenance checks.
  - `raw_fact` must carry a source receipt and cannot contain inferential
    language.
  - `hypothesis` cannot be shipped as validated.
- Diagnostic hypothesis and confidence: honest-labeling only,
  `out_of_validated_domain`, capped confidence.
- Prepared customer draft: declared as Slot-B judge domain when present; no new
  judge is introduced here.
- Feedback hooks: must target `RejectionLedger`; recurring reasons are mined as
  candidate factors, not autonomous truth.

## Addendum 1 Boundary

The workflow layer remains outside this stacked Wave 2 branch because it is not
present on `origin/main`. The Wave 2 evaluator is ready to grade workflows once
that layer is promoted, but workflow scenario expectations must still be backed
by deterministic or owner-labeled ground truth before a pass is called
validated.

## Gates

Run from `/Users/owieschon/dev/ultra-csm-mp-d2-salvage`.

- Compile:
  `python3 -m py_compile eval/work_packet_eval.py src/ultra_csm/work_packets.py src/ultra_csm/rejection_ledger.py`
- Focused validation tests:
  `python3 -m pytest tests/test_work_packets.py tests/test_work_packet_eval.py -q`
  -> `10 passed`
- Work-packet eval:
  `make PYTHON=python3 work-packet-eval`
  -> `packet_count: 6`, `findings: []`, `passed: true`
- Focused lint:
  `python3 -m ruff check src/ultra_csm/work_packets.py src/ultra_csm/rejection_ledger.py eval/work_packet_eval.py tests/test_work_packet_eval.py tests/test_work_packets.py`
  -> `All checks passed!`
