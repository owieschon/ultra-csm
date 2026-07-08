PYTHON := .venv/bin/python

# Bind address for `make serve`. Defaults to loopback-only for local demo
# safety; pass HOST=0.0.0.0 explicitly to expose it on the LAN.
HOST ?= 127.0.0.1

# One-time reviewer setup. Requires Python 3.10+ and local PostgreSQL 16 tooling
# (`initdb`/`pg_ctl`) available on PATH or through the platform package.
.PHONY: setup eval lint scorecard-csm scorecard-csm-check takeover-scoreboard csm-work-queue demo-loop year-in-life-csm tick-demo-csm mcp-readonly-demo-csm mcp-operator-demo-csm mcp-relay-demo-csm mcp-relational-demo-csm mcp-stdio-replay-csm slot-a-scorecard-csm autonomy-report-csm attio-simulated-onboarding-csm gainsight-simulated-onboarding-csm product-telemetry-simulated-onboarding-csm telemetry-simulated-live-csm salesforce-simulated-onboarding-csm hubspot-simulated-onboarding-csm relay-battery-csm relational-battery-csm narrative-battery-csm content-battery-csm content-invariance-csm canary-battery-csm adversarial-surfaces-battery-csm week1-protocol-csm week1-protocol-fieldstone-csm quantity-battery-csm transcript-battery-csm tier-policy-battery-csm tier-gating-battery-csm perturbation-battery-csm drift-battery-csm deployment-readiness fieldstone-battery-csm crateworks-battery-csm crateworks-onboarding-csm week1-protocol-crateworks-csm loopway-battery-csm loopway-attio-simulated-onboarding-csm week1-protocol-loopway-csm demo clean outcome-simulation-csm stochastic-csm regression-csm regression-csm-live oversight-report doctor quality-regression-csm drift-power-csm quality-gold-csm quality-gold-label-csm quality-gold-status-csm quality-gold-status-check-csm quality-gold-validate-csm quality-gold-hard-csm quality-gold-hard-label-csm quality-gold-hard-status-csm quality-gold-hard-status-check-csm quality-gold-hard-validate-csm judge-agreement-csm judge-diagnosis-csm judge-reference-review-csm judge-reference-recheck-csm judge-reference-apply-csm judge-live-csm status hygiene serve mcp fieldstone-perturbation-battery-csm fieldstone-drift-battery-csm crateworks-perturbation-battery-csm crateworks-drift-battery-csm loopway-perturbation-battery-csm loopway-drift-battery-csm ui-dev ui-build ui-check hosted-readonly-demo resilience-battery-csm person-factor-battery-csm
setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev,api,mcp]" -c constraints.txt

serve:
	ULTRA_CSM_BIND_HOST=$(HOST) PYTHONPATH=src:. $(PYTHON) -m uvicorn ultra_csm.api:app --host $(HOST) --port 8000 --reload

mcp:
	PYTHONPATH=src:. $(PYTHON) -m ultra_csm.mcp_server

# Operations surface UI (Harvest 9). Dev: `make serve` in one shell (adds
# CORS for :3000), `make ui-dev` in another. Demo/prod: `make ui-build` then
# `make serve` mounts ui/out at /ui same-origin (set ULTRA_CSM_DEMO_NOAUTH=1
# to exercise approve/edit/deny without a mapped API token).
ui-dev:
	cd ui && npm run dev

ui-build:
	cd ui && npm ci && npm run build

ui-check:
	cd ui && npm ci && npm run lint && npm run build

hosted-readonly-demo:
	PYTHONPATH=src:. $(PYTHON) scripts/export_hosted_readonly_demo.py
	cd ui && npm ci && NEXT_PUBLIC_UCSM_READONLY_DEMO=1 npm run lint && NEXT_PUBLIC_UCSM_READONLY_DEMO=1 npm run build

eval:
	$(PYTHON) -m pytest tests/ -q
	PYTHONPATH=src:. $(PYTHON) -m eval.gold_slot_b_quality --check
	PYTHONPATH=src:. $(PYTHON) -m eval.gold_slot_b_hard --check

lint:
	$(PYTHON) -m ruff check src eval tests scripts

scorecard-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.scorecard_csm

scorecard-csm-check:
	PYTHONPATH=src:. $(PYTHON) -m eval.scorecard_csm --check

takeover-scoreboard:
	PYTHONPATH=src:. $(PYTHON) -m eval.takeover_scoreboard

csm-work-queue: scorecard-csm

demo-loop:
	PYTHONPATH=src:. $(PYTHON) -m eval.demo_loop_csm

year-in-life-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.year_in_life_digest --live

tick-demo-csm:
	PYTHONPATH=src:. $(PYTHON) -m ultra_csm.tick --demo

mcp-readonly-demo-csm:
	PYTHONPATH=src:. ULTRA_CSM_MCP_READONLY=1 $(PYTHON) -m eval.mcp_readonly_demo

mcp-operator-demo-csm:
	PYTHONPATH=src:. ULTRA_CSM_DEMO_OPERATOR=1 $(PYTHON) -m eval.mcp_operator_demo

mcp-relay-demo-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.mcp_relay_demo

mcp-relational-demo-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.mcp_relational_demo

mcp-stdio-replay-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.mcp_stdio_replay

slot-a-scorecard-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.slot_a_scorecard

autonomy-report-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.autonomy_report

attio-simulated-onboarding-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.attio_simulated_onboarding

gainsight-simulated-onboarding-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.gainsight_simulated_onboarding

product-telemetry-simulated-onboarding-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.product_telemetry_simulated_onboarding

telemetry-simulated-live-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.telemetry_simulated_live

salesforce-simulated-onboarding-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.salesforce_simulated_onboarding

relay-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.relay_battery

relational-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.relational_battery

narrative-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.narrative_battery

person-factor-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.person_factor_battery

content-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.content_battery

content-invariance-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.content_invariance_check --check

canary-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.canary_battery

adversarial-surfaces-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.adversarial_surfaces_battery

week1-protocol-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.week1_protocol --tenant fleetops

week1-protocol-crateworks-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.week1_protocol --tenant crateworks

crateworks-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.crateworks_battery

crateworks-perturbation-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.crateworks_perturbation_battery

crateworks-drift-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.crateworks_drift_battery

crateworks-onboarding-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.crateworks_onboarding

tier-policy-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.tier_policy_battery

tier-gating-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.tier_gating_battery

perturbation-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.perturbation_battery

drift-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.drift_battery

resilience-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.resilience_battery

loopway-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.loopway_battery

loopway-perturbation-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.loopway_perturbation_battery

loopway-drift-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.loopway_drift_battery

loopway-attio-simulated-onboarding-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.loopway_attio_simulated_onboarding

week1-protocol-loopway-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.week1_protocol --tenant loopway

fieldstone-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.fieldstone_battery

fieldstone-perturbation-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.fieldstone_perturbation_battery

fieldstone-drift-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.fieldstone_drift_battery

hubspot-simulated-onboarding-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.hubspot_simulated_onboarding

week1-protocol-fieldstone-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.week1_protocol --tenant fieldstone

quantity-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.quantity_battery

transcript-battery-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.transcript_battery

outcome-simulation-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.outcome_simulation_csm

stochastic-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.stochastic_csm

regression-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.regression_csm

quality-regression-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.quality_regression_csm --runs $${RUNS:-5}

drift-power-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.drift_power_csm

quality-gold-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.gold_slot_b_quality

quality-gold-label-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.label_gold --labeler $${QUALITY_LABELER:-reviewer}

quality-gold-status-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.gold_slot_b_quality --status

quality-gold-status-check-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.gold_slot_b_quality --check

quality-gold-validate-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.gold_slot_b_quality --require-complete

# Adversarial hard layer: cases where a surface read scores wrong. Separate split
# so judge-vs-human kappa is reported per-layer, never averaged with the clean set.
quality-gold-hard-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.gold_slot_b_hard

quality-gold-hard-label-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.label_gold --file eval/gold/slot_b_quality_hard.jsonl --labeler $${QUALITY_LABELER:-reviewer}

quality-gold-hard-status-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.gold_slot_b_hard --status

quality-gold-hard-status-check-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.gold_slot_b_hard --check

quality-gold-hard-validate-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.gold_slot_b_hard --require-complete

# Credential-gated judge-vs-reference agreement run. Scores both gold layers with the
# Anthropic quality judge and writes eval/gold/judge_agreement.json. Needs ANTHROPIC_API_KEY.
# Not a CI gate. The number that matters is hard-layer kappa with zero false negatives.
judge-agreement-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.run_quality_judge $${MODEL:+--model $${MODEL}}

judge-diagnosis-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.diagnose_judge $${MODEL:+--model $${MODEL}}

judge-reference-review-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.reference_review

judge-reference-recheck-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.reference_recheck

judge-reference-apply-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.apply_reference_review

# Credential-gated live regression lane. Not a CI gate.
regression-csm-live:
	PYTHONPATH=src:. $(PYTHON) -m eval.regression_csm --live --runs $${RUNS:-30}

# Credential-gated, manually-invoked judge-on-live run for the current story
# day. Not a CI gate, no scheduler -- see eval/judge_live_csm.py docstring.
judge-live-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.judge_live_csm

status:
	PYTHONPATH=src:. $(PYTHON) scripts/render_status.py
	PYTHONPATH=src:. $(PYTHON) scripts/render_status.py --check

notion-render:
	PYTHONPATH=src:. $(PYTHON) scripts/notion_render.py

notion-render-check:
	PYTHONPATH=src:. $(PYTHON) scripts/notion_render.py --check

deployment-readiness:
	PYTHONPATH=src:. $(PYTHON) scripts/render_deployment_readiness.py
	PYTHONPATH=src:. $(PYTHON) scripts/render_deployment_readiness.py --check

oversight-report:
	PYTHONPATH=src:. $(PYTHON) scripts/oversight_report.py

doctor:
	PYTHONPATH=src:. $(PYTHON) scripts/doctor.py

hygiene:
	$(PYTHON) scripts/hygiene_scan.py

clean:
	PYTHONPATH=src:. $(PYTHON) scripts/reap_stale_clusters.py
	rm -rf build/tmp

demo:
	$(MAKE) scorecard-csm
	$(MAKE) regression-csm
	$(MAKE) slot-a-scorecard-csm
	$(MAKE) autonomy-report-csm
	$(MAKE) attio-simulated-onboarding-csm
	$(MAKE) gainsight-simulated-onboarding-csm
	$(MAKE) product-telemetry-simulated-onboarding-csm
	$(MAKE) salesforce-simulated-onboarding-csm
	$(MAKE) mcp-readonly-demo-csm
	$(MAKE) mcp-operator-demo-csm
	$(MAKE) mcp-relay-demo-csm
	$(MAKE) mcp-relational-demo-csm
	$(MAKE) oversight-report
