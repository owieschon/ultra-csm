# Honest Limits

Ultra CSM is meant to be judged by what it can prove. The strongest claim in
the repo is not that every surface is production-finished; it is that the
system records the boundary when evidence runs out.

## What The Evidence Proves

| Limit | Current line | Receipt |
| --- | --- | --- |
| Synthetic universe | The fixture book is deterministic and internally consistent, but it is not proof on real customer data. Synthetic accounts, personas, support cases, telemetry, and comms are built as a controlled test world. | `docs/SYNTHETIC_UNIVERSE_BIBLE.md`; `docs/UNIVERSE_V2_CONVENTIONS.md`; `docs/PROGRAM_REPORT_67.md` |
| Hosted demo | The hosted demo is read-only and fixture-backed. It proves safe distribution of the operations UI, not live connector access or production approval. | `docs/PROGRAM_REPORT_67.md`; `scripts/export_hosted_readonly_demo.py`; `ui/public/demo-api/` |
| Outcome rail | The value model can represent `known`, `unknown`, and `not_instrumented` outcome states and the VM-8 slice proves it does not infer `known` from usage alone. The current realized-outcome source is synthetic terminal Renewal `CRMOpportunity` evidence; broader business metrics, attribution, and live connector rollout remain unbuilt. | `docs/PROGRAM_REPORT_69.md`; `tests/test_value_model.py`; `tests/test_agent1_sweep.py`; `src/ultra_csm/value_model.py` |
| Judge validation | The full judge validation claim is false. Five dimensions are scoped-gateable; `on_task_relevance` is excluded by the per-dimension guard because three hard-layer aggregate false opens remain. The gold posture is single-labeler; no independent second blind human labeler has been supplied. | `docs/PROGRAM_REPORT_70.md`; `eval/gold/slot_b_quality_status.json`; `eval/gold/slot_b_quality_hard_status.json`; `docs/archive/PROGRAM_REPORT_64.md` |
| Internal handoff thesis | MP-B proves one Engineering/Product routing pair end to end: deterministic route, evidence-complete packet, abstention as a first-class field, and zero confidently-wrong validation cells. It does not prove the other internal-bridge archetypes or real-world durability. | `docs/PROGRAM_REPORT_68.md`; `docs/HANDOFF_SPIKE_SPEC.md`; `eval/internal_bridge_validation_report.json`; `src/ultra_csm/internal_bridge/routing.py`; `src/ultra_csm/internal_bridge/packet.py` |
| Customer-facing send | The system has staged one burner-scoped `draft_customer_outreach` proposal and stopped before owner approval. No `submit_verdict` call was made and no Gmail send occurred. | `docs/PROGRAM_REPORT_60.md` |
| Governance boundary | Customer-facing actions stay behind proposal, human verdict, and committer paths. The LLM does not own authorization, consent, payload binding, tenant containment, or the approval principal. | `README.md`; `docs/PROGRAM_REPORT_58.md`; `docs/PROGRAM_REPORT_60.md`; `eval/scorecard_csm.json` |
| Monitoring | Sentry envelope/check-in code and missed-run/cost alarm logic are tested with fake transports. Live Sentry ingestion is not proven because no live DSN/token receipt exists. | `docs/PROGRAM_REPORT_65.md`; `docs/archive/PROGRAM_REPORT_59.md`; `docs/OBSERVABILITY.md`; `scripts/operating/daily_run.sh` |
| Persistent operation | The daily operating path has been loaded locally and persistent audit rows have been written, but this is not weeks of unattended production operation. | `docs/PROGRAM_REPORT_65.md`; `docs/PROGRAM_REPORT_58.md` |
| Production customer outcomes | The repo does not claim production retention lift, production customer deployment, or production-customer outcome improvement. | `README.md`; `docs/PROGRAM_REPORT_65.md`; `docs/PROGRAM_REPORT_69.md` |

## How To Read These Limits

These boundaries are not caveats to hide. They are the product shape: the
system distinguishes evidence it has from evidence it does not have, and it
keeps unproven claims structurally unproven.

That means:

- high usage without realized outcome evidence stays unverified;
- a judge that fails one dimension stays false overall and exposes only the
  validated scoped dimensions;
- a handoff route is called proven only for the validated pair;
- a prepared customer message remains a proposal until a human principal
  approves it through the gate.

The next proof should move one boundary at a time. Until it does, this file is
the front-door line.
