# Program Report 69 - VM-8 Outcome Integrity Slice

Harvest 33 delivered a narrow VM-8 outcome-integrity slice. It wires one
synthetic realized-outcome source - terminal Renewal `CRMOpportunity` rows -
into the existing outcome rail and proves the rail does not fabricate `known`
from usage, health, or adoption alone. This is not a full VM-8 completion
claim: broader business metrics, attribution, live connector rollout, and UI
depth remain unbuilt.

## What Changed

| Area | Change |
| --- | --- |
| Canonical value model | `build_customer_value_model(..., opportunities=())` now accepts optional CRM opportunities. Only Renewal opportunities with terminal `stage_name` count as realized outcome evidence. |
| Date fence | When `as_of` is supplied, a terminal renewal close counts only if `CRMOpportunity.close_date <= as_of`, so future outcomes cannot backfill an earlier checkpoint. |
| Outcome direction | `Closed Won` produces `renewal_outcome_closed_won` with value `1.0`; `Closed Lost` produces `renewal_outcome_closed_lost` with value `-1.0`. Both cite the opportunity id and keep contribution `0`. |
| Deep simulation bridge | `value_model_bridge` mirrors terminal renewal handling for `OpportunityTimeline.current_stage`. |
| Product paths | API helpers, sweep trigger evaluation, tick trigger state, reconciliation, and expansion-lens builders pass account-scoped opportunities into the value model where those paths already read CRM data. |
| Capability map | VM-8 is marked partial: synthetic renewal outcome ingestion is built; broader outcome instrumentation remains open. |

## Proof Cases

| Case | Expected | Observed | Evidence |
| --- | --- | --- | --- |
| Green/high-usage account that later churns, checkpoint T | Outcome not `known`; `usage_outcome_unverified` fires because objectives exist and no terminal outcome is in scope. | `test_green_high_usage_account_that_later_churns_does_not_backfill_known_outcome` observed `not_instrumented` and `usage_outcome_unverified`. | Future `Closed Lost` opportunity `opp-closed-lost-2026-07-01` was not counted at `as_of=2026-06-21`. |
| Same account at T + lag | Terminal negative renewal evidence is known and direction is distinguishable from success. | The rail became `known` with factor `renewal_outcome_closed_lost`, value `-1.0`, contribution `0`, evidence source `crm`. | `opp-closed-lost-2026-07-01`, field `stage_name`, observed at `2026-07-01`. |
| Positive realized outcome | Terminal `Closed Won` renewal evidence marks outcome `known` and suppresses the unverified-outcome warning. | `test_closed_won_renewal_is_positive_realized_outcome_evidence` observed `known`, `renewal_outcome_closed_won`, value `1.0`, and no `usage_outcome_unverified`. | `opp-closed-won-2026-06-15`, field `stage_name`, observed at `2026-06-15`. |
| Missing or ambiguous evidence | Non-terminal Renewal and terminal non-Renewal opportunities do not fabricate `known`. | `test_non_terminal_or_non_renewal_opportunity_does_not_fabricate_known_outcome` observed `not_instrumented` and only `outcome_stated`. | `Proposal` Renewal and `Closed Won` Expansion were ignored for outcome realization. |

## Green Account That Churned

The flagship check intentionally separates a healthy-looking checkpoint from a
later realized outcome. At `as_of=2026-06-21`, the account has high usage and a
stated objective, but the renewal closes on `2026-07-01`; the rail therefore
stays `not_instrumented` and the existing `usage_outcome_unverified` warning
fires. At `as_of=2026-07-02`, the same opportunity is in scope as `Closed Lost`;
the rail records `known` with an explicit negative factor instead of implying
success. This proves the system did not claim success at checkpoint T.

## Gate Receipts

| Gate | Receipt |
| --- | --- |
| Baseline before coding | `make eval` passed: 817 passed, 1 skipped, 1 warning in 213.93s; Slot B gold checks current. |
| Focused proof cases | `.venv/bin/python -m pytest tests/test_value_model.py::test_green_high_usage_account_that_later_churns_does_not_backfill_known_outcome tests/test_value_model.py::test_closed_won_renewal_is_positive_realized_outcome_evidence tests/test_value_model.py::test_non_terminal_or_non_renewal_opportunity_does_not_fabricate_known_outcome tests/test_agent1_sweep.py::test_outcome_unknown_trigger_absent_when_terminal_renewal_outcome_known -q` -> 4 passed. |
| Existing outcome regression set | `.venv/bin/python -m pytest tests/test_value_model.py tests/test_agent1_sweep.py tests/test_rocketlane_ttv_bridge.py -q` -> 49 passed. |
| Evidence audit | `rg -n "renewal_outcome_closed_(won|lost)|EvidenceRef\\(" src/ultra_csm/value_model.py src/ultra_csm/value_model_bridge.py tests/test_value_model.py tests/test_agent1_sweep.py` shows both renewal factor paths and their explicit `EvidenceRef` construction. |
| Hygiene | `make hygiene` passed via `scripts/hygiene_scan.py`. |
| Lint | `make lint` passed: Ruff reported `All checks passed!`. |
| Final eval | `make eval` passed: 821 passed, 1 skipped, 1 warning in 212.92s; Slot B gold checks current. |

## Known Boundaries

- `known` means realized evidence is known, not that the outcome was good.
- Negative renewal outcomes are explicit factors, not success signals.
- Usage, health, adoption, ARR, and green status still cannot mark outcome
  `known`.
- This slice uses synthetic fixture/test evidence; no live CRM credentials or
  customer data were used.
- VM-8 remains partial until broader realized-outcome sources, attribution
  semantics, and UI/ops depth land in later work.
