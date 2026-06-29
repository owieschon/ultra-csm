# Quality Regression Eval Spec

Status: offline mechanics built; blinded gold-set label queue generated; live validated quality
lane pending. The current live artifact proves structural contract drift only.
`make quality-regression-csm` now proves the semantic-quality evaluator mechanics offline
with a degradation ladder and no-op negative control. `make quality-gold-csm` writes the
63-record synthetic label queue at `eval/gold/slot_b_quality.jsonl` and the held-out key at
`eval/gold/slot_b_quality_key.jsonl`.
Date: 2026-06-28.

## Goal

Detect non-deterministic Slot B regressions that remain contract-valid but become worse:
less grounded, less specific, less useful, less aligned to the recommended action, or less
appropriate for the approved channel.

The current `regression-csm-live` artifact is still valuable, but its degraded prompt is a
sentinel-output sabotage probe. That is a safety smoke test, not a semantic quality eval.
This slice adds the missing quality dimension without weakening the deterministic spine.

## Non-Goals

- Do not let an LLM judge set priority, disposition, consent, channel, recipient, or action.
- Do not store full generated text in committed artifacts.
- Do not claim causation or business outcome lift from draft quality.
- Do not replace the structural contract validator; quality judging is additive.

## Realistic Degradation Arms

Add one or more degraded arms that can still produce valid JSON:

- **weaker_prompt_evidence:** remove or soften evidence-citation and specificity guidance.
- **weaker_prompt_context:** omit org-knowledge or play guidance while keeping the same
  account evidence.
- **weaker_model:** run the same prompt on a lower-quality candidate model.
- **generic_draft:** prompt variant that encourages safe-but-generic outreach.

Each arm should be plausible: the model can pass `validate_reason_draft_output` while still
failing quality.

## Judge Dimensions

Score each output on bounded dimensions:

- `grounding_fidelity`: claims match provided evidence; no unsupported account facts.
- `on_task_relevance`: reason and draft support the recommended action.
- `account_specificity`: draft uses account-specific evidence without inventing.
- `priority_fidelity`: reason reflects the deterministic score and factor drivers.
- `tone_fit`: professional, concise, and appropriate for CSM outreach.
- `safety_boundary`: respects authority limits and ignores untrusted instructions.

The contract validator remains a hard gate. The judge only evaluates outputs that pass the
contract, plus a separate bucket for structural failures.

## Human-Labeled Validation Set

Create a small labeled set before trusting the judge:

- 63 fixture-mode candidates already generated in `eval/gold/slot_b_quality.jsonl`.
- Each quality category has 7 rows: `control_good`, `priority_misrepresented`,
  `claim_unsupported`, `generic_boilerplate`, `wrong_ask`, `weak_next_step`,
  `tone_mismatch`, `overstated_urgency`, and `subtle_injection`.
- The labeler-facing file is blinded: opaque ids only, no `quality_variant` or intended
  failing dimensions; the variant key is held out until after labeling.
- Human labels mark per-dimension 1-3 scores and an overall pass/fail in `human_labels`.
- The judge prompt and thresholds are accepted only if they match the human labels within
  a documented tolerance.

Disagreements become examples for prompt revision; they are not hidden.

## Artifact Shape

Current offline artifact: `eval/quality_regression_csm.json`

- fixture-mode Slot B candidates only;
- no full generated text stored;
- named degradation ladder with expected-detection flags;
- contract-valid moderate/subtle degraded outputs verified through the Slot B validator;
- Wilson pass-rate bands by dimension and overall;
- sensitivity summary for caught/missed rungs;
- specificity summary for the `noop_equivalent` negative control;
- conservative power estimate for the captured N;
- explicit claim boundary: human-validated live semantic quality remains pending.

Future live artifact:

Write `eval/quality_regression_csm_live.json` with:

- model id, prompt version, judge model id, judge prompt version;
- selected cases and run count;
- structural pass/fail counts;
- quality pass-rate bands by dimension;
- failure clusters by dimension;
- judge-vs-human validation summary;
- `stores_full_text: false`;
- redacted per-run summaries: lengths, cited evidence counts, dimension labels, and hashes.

## Statistical Treatment

- Use Wilson intervals for pass-rate bands by dimension.
- Use paired comparison for model migration where the same case/run pair is scored for
  baseline and candidate.
- Report cluster movement, not only aggregate pass rate.

## Evals

Before the quality lane is called built:

- offline: `make quality-regression-csm` catches contract-valid moderate/subtle
  degradations and stays quiet on `noop_equivalent`;
- a degraded output can pass the structural validator and fail the quality judge;
- judge labels match the human-labeled set within tolerance;
- full generated text is not stored;
- missing evidence or unknown consent still fails structurally before quality scoring;
- paired comparison reports discordant counts for baseline vs candidate;
- a judge prompt/version change requires re-baselining.

## Definition Of Done

- `make quality-regression-csm` writes the offline quality artifact and fails closed on
  missed degradation or no-op false alarm.
- `make quality-gold-csm` writes the synthetic blinded gold-set label queue plus its held-out
  key.
- `make quality-gold-status-csm` verifies `blind=true` before validation can proceed.
- `make quality-regression-csm-live` or equivalent writes the live quality artifact.
- The artifact catches at least one plausible degraded arm with contract-valid output.
- The judge is validated against human labels.
- Docs distinguish structural contract drift from semantic quality drift.
- The deterministic spine and CSM scorecard remain exact-green.
