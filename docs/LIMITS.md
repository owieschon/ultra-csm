# Current limits

Use this page to distinguish the behavior Ultra CSM currently proves from behavior that
still needs live data, an operator decision, or production outcome evidence.

## Evidence boundary

| Area | Current boundary | Executable or direct evidence |
| --- | --- | --- |
| Synthetic universe | The fixture book is deterministic and internally consistent. It is not evidence about a real customer. | `src/ultra_csm/data_plane/synthetic_book.py`, `src/ultra_csm/data_plane/book_simulator.py`, `tests/test_hosted_readonly_demo.py` |
| Hosted read-only build | The hosted and local static builds prove the operations UI over committed fixtures. They export no write routes and do not prove live connector access or production approval. | `scripts/export_hosted_readonly_demo.py`, `ui/public/demo-api/manifest.json`, `tests/test_hosted_readonly_demo.py` |
| Outcome rail | The value model represents known, unknown, and not-instrumented outcomes. It does not infer a known result from usage alone. Current realized-outcome fixtures use terminal renewal opportunities; broader attribution and live rollout remain unproven. | `src/ultra_csm/value_model.py`, `tests/test_value_model.py`, `tests/test_agent1_sweep.py` |
| Draft source | A draft may come from a fixture, a live model, a labeled template fallback, or no source. The hosted walkthrough uses `draft_mode: fixture`, so it is not a live-model demonstration. | `src/ultra_csm/agent1/sweep.py`, `ui/public/demo-api/sweep-day-140.json` |
| Judge validation | Five quality dimensions are scoped-gateable. `on_task_relevance` remains report-only because its hard-layer aggregate still has false opens. The gold set has one human labeler and no independent second blind labeler. | `eval/gold/slot_b_quality_status.json`, `eval/gold/slot_b_quality_hard_status.json`, `eval/judge_validation.py` |
| Internal handoff | One Engineering/Product routing pair is validated end to end, including abstention and cited evidence. Other handoff archetypes and real-world durability remain unproven. | `src/ultra_csm/internal_bridge/routing.py`, `src/ultra_csm/internal_bridge/packet.py`, `tests/test_internal_bridge.py` |
| Customer-facing send | Live Gmail and Salesforce committers exist behind the gate, but the repository includes no receipt for an approved production customer send. The hosted demo cannot call them. | `src/ultra_csm/data_plane/gmail_writeback.py`, `src/ultra_csm/data_plane/salesforce_writeback.py`, `tests/test_gmail_writeback.py`, `tests/test_salesforce_writeback.py` |
| Governance | Customer-facing actions require a proposal, consent where applicable, a verdict from a configured human-kind principal distinct from the proposing actor, and a committer bound to the authorized payload hash. The software verifies the configured identity, not the person holding its token. | `src/ultra_csm/_api_helpers.py`, `src/ultra_csm/governance/gate.py`, `migrations/0009_safety_backstops.sql`, `tests/test_action_gate_machine.py` |
| Monitoring | Sentry envelope, missed-run, and cost-alarm behavior is tested with fake transports. A live ingestion claim requires an operator-configured DSN and a live receipt. | `src/ultra_csm/operating_monitor.py`, `tests/test_operating_monitor.py` |
| Persistent operation | The runtime and daily operating path have persistence tests. The repository does not prove weeks of unattended production operation. | `tests/test_persistent_runtime.py`, `tests/test_operating_run.py` |
| Production outcomes | No production retention lift, expansion lift, or customer deployment outcome is claimed. A controlled fixture can prove mechanism and refusal behavior, not business impact. | `eval/scorecard_csm.json`, `tests/test_value_model.py` |

## How to interpret the boundary

- High usage without realized-outcome evidence stays unverified.
- A judge that fails one dimension stays false overall; only independently validated
  dimensions may gate.
- A handoff route is called proven only for the validated pair.
- A prepared customer message remains a proposal until a configured approval principal
  authorizes it through the gate.
- A green static demo proves its fixture and route contract, not its effectiveness on a
  live tenant.

Move one boundary by adding the missing receipt and its negative test. Do not widen the
claim first.
