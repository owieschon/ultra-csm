PYTHON := .venv/bin/python

# One-time reviewer setup. Requires Python 3.10+ and local PostgreSQL 16 tooling
# (`initdb`/`pg_ctl`) available on PATH or through the platform package.
.PHONY: setup eval lint scorecard-csm csm-work-queue demo clean outcome-simulation-csm stochastic-csm regression-csm regression-csm-live quality-regression-csm quality-gold-csm quality-gold-label-csm quality-gold-status-csm quality-gold-validate-csm quality-gold-hard-csm quality-gold-hard-label-csm quality-gold-hard-status-csm quality-gold-hard-validate-csm judge-agreement-csm judge-diagnosis-csm judge-reference-review-csm judge-reference-recheck-csm judge-reference-apply-csm hygiene
setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

eval:
	$(PYTHON) -m pytest tests/ -q

lint:
	$(PYTHON) -m ruff check src eval tests scripts

scorecard-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.scorecard_csm

csm-work-queue: scorecard-csm

outcome-simulation-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.outcome_simulation_csm

stochastic-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.stochastic_csm

regression-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.regression_csm

quality-regression-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.quality_regression_csm --runs $${RUNS:-5}

quality-gold-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.gold_slot_b_quality

quality-gold-label-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.label_gold --labeler $${QUALITY_LABELER:-reviewer}

quality-gold-status-csm:
	PYTHONPATH=src:. $(PYTHON) -m eval.gold_slot_b_quality --status

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

hygiene:
	$(PYTHON) scripts/hygiene_scan.py

clean:
	rm -rf build/tmp

demo:
	$(MAKE) scorecard-csm
	$(MAKE) regression-csm
