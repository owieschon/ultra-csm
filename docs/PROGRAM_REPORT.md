# Mega Relay Program Report

Branch: `codex/mega-relay-program`  
Worktree: `/Users/owieschon/dev/ultra-csm-mega`  
Claim boundary: sanitized program report; no private corpus values, field keys, URLs, or credentials.

## Commits

- `54e323c` Harden relay mapping confirmations
- `1b6f273` Record phase one corpus reprobe
- `5e1c588` Merge Lane J operator demo
- `fe5491f` Cut flaky pgserver fallback
- `a4eaad4` Add MCP relay book tools

## Phase 0 - Lane J

| DoD | Verification |
| --- | --- |
| Demo-operator full loop boots over the real gate, sweep-at-boot, sim-labeled tokenless verdicts, readonly conflict refusal | `pytest -q tests/test_platform_boot_tier.py tests/test_mcp_operator_demo.py tests/test_mcp_server.py` -> 22 passed before relay changes; later full suite -> 379 passed. `make mcp-operator-demo-csm` -> `access_mode=demo_operator`, 11 tool calls, refusal codes `CONSENT_MISSING` and `PRECEDENCE_HELD`. |
| Postgres boot tier | `make doctor` -> Python 3.14.3, system Postgres 16.13, throwaway cluster booted via system, UTF8. Python 3.12 pgserver verification failed because pgserver lacks the required `pgcrypto` extension, so the IF/THEN branch was taken and pgserver was cut. |
| Briefing, next steps, suggested next, demo instructions | Covered by operator transcript test and fixture; `eval/mcp_operator_transcript.json` includes briefing, queue, revise, approval, refusal, ledger beats. |
| MCP revise shares the REST bounded revise path | `tests/test_mcp_server.py::TestSubmitVerdict::test_revise_uses_bounded_loop` in full suite; response includes `superseding_proposal_id`. |
| Session ledger includes verdicts and refusals | Operator transcript includes `get_session_ledger` and both typed refusal events. |
| Deterministic demo transcript | `tests/test_mcp_operator_demo.py` -> deterministic transcript comparison passed in full suite. |
| QUICKSTART and TOUR demo section | `QUICKSTART.md` and `docs/TOUR.md` include the operator morning. |
| Honest sim state | Refusal proposals are seeded through the same gate and sim data path; no fake tool response was introduced. |

## Phase 1 - Confirmation Flow

| DoD | Verification |
| --- | --- |
| K1 sparsity surface | `tests/test_external_book.py` checks competing display-label candidate coverage; relay proposal entries carry `rows_present`, `rows_nonempty`, and `rows_sampled`. |
| K2 unknown verdict | `tests/test_external_book.py` and `tests/test_relay_battery.py` cover `not_mappable` freeze to `unknown_fields`; missing confirmations still raise. |
| K3 cross-book sampling | `_processed_records` samples across the fetched set deterministically; full suite passed. |
| K4 nested collections | `tests/test_external_book.py` extracts nested CRMContact records via parent account identity and preserves unrepresentable paths otherwise. |
| Relay battery | `PYTHONPATH=src:. python3 -m eval.relay_battery` -> `hard_ok=true`, score 11/11; full suite confirms byte determinism. |
| Private corpus reprobe | Runtime-only bounded read: discovery fetched 200 rows, 13 confirmations, 4 unknown, 0 silent guesses. Confirmed pass typed CRMAccount 200/200, CRMContact 200/200, CRMOpportunity 200/200, contact joins 200/200, injection markers 0. Sanitized aggregates appended to `docs/FOREIGN_CORPUS_FINDINGS.md`. |

## Phase 2 - Relay Surface

| DoD | Verification |
| --- | --- |
| `report_readiness` | `tests/test_mcp_server.py::TestRelayTools` checks checklist, minimum viable CRM route, and sim-morning route for no sources. |
| `ingest_book` | Tests cover required `expected_count`, chunked accumulation, count-mismatch refusal, capped truncation, raw-input digest, mapping proposal, and confirmation questions. |
| `confirm_book_mappings` | Tests cover freeze/transform/coverage/briefing, claim boundary, `not_mappable`, and replay digest stability. |
| Relay actions propose-only | Tests assert returned draft action has `live_send_performed=false`; relay code has no committer or receipt path. |
| Replay determinism | Confirming the same session twice yields identical `replay_sha256`; full suite passed. |
| Battery extensions | MCP tests cover oversized payload truncation, chunked reassembly, count mismatch, injection text no-echo. |
| Readonly/demo composition | Readonly refuses all three relay tools; demo-operator mode returns `RELAY_DEMO_OPERATOR_CONFLICT`. |
| Relay transcript | `make mcp-relay-demo-csm` -> CRMAccount 2, CRMContact 2, CRMOpportunity 2, tool calls 3; `eval/mcp_relay_transcript.json` committed. |

## Phase 3 - Integration

| DoD | Verification |
| --- | --- |
| Bring-your-own-book docs | `README.md`, `QUICKSTART.md`, and `docs/TOUR.md` document readiness -> ingest -> confirm, source checklist, partial credit, degradation, and no-send boundary. `get_next_steps` points at the relay tools and docs. |
| STATUS current | `make status` -> wrote `STATUS.md`; `scripts/render_status.py --check` -> `STATUS.md is current`; no resulting diff. |
| Full gates and stdio replay | Latest observed gates: `make mcp-stdio-replay-csm` -> `ok=true`, operator refusals `CONSENT_MISSING` and `PRECEDENCE_HELD`, relay typed CRMAccount/CRMContact/CRMOpportunity 2/2/2; `make eval` -> 379 passed, 1 dependency warning; `make lint` -> all checks passed; `make hygiene` -> passed; `git diff --check` -> passed. |
| Program report | This file. |
| Single PR | Blocked in this environment: `gh pr create` failed with `GraphQL: Resource not accessible by personal access token (createPullRequest)`. Branch is pushed and GitHub returned the PR creation URL. |

## Deviations and IF/THEN Branches

- pgserver fallback was cut. A Python 3.12 fallback verification failed before demo boot because the bundled pgserver Postgres distribution lacked the required extension for migrations. This matches the Lane J IF/THEN: cut it and keep brew/system Postgres only.
- GitHub PR creation is not possible with the available token. The pushed branch is ready for a PR created by a token with `createPullRequest` permission.

## Open Items

- Create the PR from `codex/mega-relay-program` to `main` once GitHub credentials allow it.
- A relay book with only CRM data intentionally scores zero accounts through the full value-model path because CS-platform and telemetry rails are absent; this is a claim-boundary choice, not a scoring success claim.
- A second independent labeler remains outside this program and is still noted by the project roadmap.
