"""Tests for the R2 writer bake-off harness (no live creds)."""

from __future__ import annotations

import json

from eval.writer_bakeoff import (
    GATED_DIMENSIONS,
    REPORTED_NOT_GATED,
    Scenario,
    _aggregate_arm,
    build_scenario_set,
    run_arm,
    run_draw,
    sized_n_per_arm,
)
from eval.drift_power_csm import required_n_per_arm
from ultra_csm.agent1.slot_b import AnthropicReasonDraftWriter
from eval.judge_anthropic import AnthropicQualityJudge, LLM_JUDGE_DIMENSIONS
from ultra_csm.llm_transport import TransportResponse


class _StubWriterTransport:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls = 0

    def complete(self, **kwargs):
        self.calls += 1
        return TransportResponse(text=self._text, transport="stub", input_tokens=100, output_tokens=50)


class _RaisingWriterTransport:
    def complete(self, **kwargs):
        raise AssertionError("should not be called after a contract violation is raised in _parse_live_output")


class _StubJudgeTransport:
    def __init__(self, scores: dict[str, int]) -> None:
        payload = {dim: {"reason": "stub", "score": score} for dim, score in scores.items()}
        self._text = json.dumps(payload)
        self.calls = 0

    def complete(self, **kwargs):
        self.calls += 1
        return TransportResponse(text=self._text, transport="stub", input_tokens=200, output_tokens=80)


def _passing_llm_scores() -> dict[str, int]:
    return {dim: 3 for dim in LLM_JUDGE_DIMENSIONS}


def test_build_scenario_set_is_deterministic_and_stratified():
    first = build_scenario_set(30)
    second = build_scenario_set(30)
    assert first == second
    families = {s.family for s in first}
    assert len(families) > 1
    for scenario in first:
        assert scenario.request.evidence_ids()


def test_sized_n_per_arm_uses_the_mdd_helper():
    assert sized_n_per_arm(0.20) == required_n_per_arm(0.80, 0.60)


def _scenario_and_output_text(family_target: str | None = None) -> tuple[Scenario, str]:
    scenarios = build_scenario_set(11)  # 11 families -> 1 each
    scenario = next(
        (s for s in scenarios if family_target is None or s.family == family_target),
        scenarios[0],
    )
    cited = scenario.request.evidence_ids()[:1]
    factors = scenario.request.priority.factors
    factor_text = " and ".join(f"{f.name}={f.contribution}" for f in factors)
    reason = (
        f"{scenario.request.account_name} has deterministic Time-to-Value score "
        f"{scenario.request.priority.score} from {factor_text}; citing {cited[0]}."
    )
    payload = {
        "reason": reason,
        "cited_evidence_ids": list(cited),
        "customer_draft": (
            f"Hi {scenario.request.contact_name or 'there'}, following up on {factors[0].name}."
            if scenario.request.customer_contact_allowed
            else None
        ),
    }
    return scenario, json.dumps(payload)


def test_run_draw_scores_and_gates_a_passing_draft():
    scenario, output_text = _scenario_and_output_text()
    writer = AnthropicReasonDraftWriter(
        transport=_StubWriterTransport(output_text), model_id="claude-haiku-4-5"
    )
    judge = AnthropicQualityJudge(
        transport=_StubJudgeTransport(_passing_llm_scores()), model_id="claude-sonnet-5", reasoning=True
    )

    result = run_draw(scenario, 0, writer=writer, judge=judge)

    assert result.contract_ok
    assert result.gated_pass
    for dim in GATED_DIMENSIONS:
        assert result.scores[dim] >= 2
    for dim in REPORTED_NOT_GATED:
        assert dim in result.scores  # reported...
    # ...but a failing on_task_relevance alone must not flip gated_pass.
    result.scores["on_task_relevance"] = 1
    assert all(result.scores[dim] >= 2 for dim in GATED_DIMENSIONS)


def test_run_draw_records_contract_violation_without_calling_the_judge():
    scenario = build_scenario_set(11)[0]
    bad_payload = json.dumps({"reason": "no evidence cited here", "cited_evidence_ids": [], "customer_draft": None})
    writer = AnthropicReasonDraftWriter(transport=_StubWriterTransport(bad_payload), model_id="claude-haiku-4-5")
    judge = AnthropicQualityJudge(transport=_RaisingJudgeTransport(), model_id="claude-sonnet-5")

    result = run_draw(scenario, 0, writer=writer, judge=judge)

    assert not result.contract_ok
    assert not result.gated_pass
    assert result.scores is None
    assert "evidence" in (result.contract_error or "").lower()


class _RaisingJudgeTransport:
    def complete(self, **kwargs):
        raise AssertionError("judge must not be called when the writer's contract check already failed")


def test_aggregate_arm_pass_k_and_adopt_bar():
    scenarios = build_scenario_set(11)[:2]
    passing = {dim: 3 for dim in (*GATED_DIMENSIONS, *REPORTED_NOT_GATED)}
    draws = []
    # scenario 0: passes all k=3 draws -> counts toward pass_k_rate.
    for i in range(3):
        draws.append(
            {
                "scenario_id": scenarios[0].scenario_id,
                "draw_index": i,
                "contract_ok": True,
                "contract_error": None,
                "scores": passing,
                "gated_pass": True,
            }
        )
    # scenario 1: fails on the third draw -> does not count toward pass_k_rate,
    # but still contributes 2 passing draws to gated_pass_rate.
    for i in range(2):
        draws.append(
            {
                "scenario_id": scenarios[1].scenario_id,
                "draw_index": i,
                "contract_ok": True,
                "contract_error": None,
                "scores": passing,
                "gated_pass": True,
            }
        )
    draws.append(
        {
            "scenario_id": scenarios[1].scenario_id,
            "draw_index": 2,
            "contract_ok": True,
            "contract_error": None,
            "scores": {**passing, "tone_fit": 1},
            "gated_pass": False,
        }
    )

    arm = _aggregate_arm("claude-haiku-4-5", scenarios, draws, pass_k=3)

    assert arm["n_draws"] == 6
    assert arm["gated_pass_rate"] == round(5 / 6, 4)
    assert arm["pass_k_rate"] == 0.5  # only scenario 0 of 2 is fully consistent
    assert arm["contract_violation_rate"] == 0.0
    # gated_pass_rate (0.833) clears 0.90? No -- adopt bar must reflect that.
    assert not arm["adopt_eligible"]


def test_run_arm_checkpoint_skips_already_completed_draws(tmp_path):
    scenarios = build_scenario_set(11)[:1]
    checkpoint = tmp_path / "checkpoint.json"
    _scenario, output_text = _scenario_and_output_text(scenarios[0].family)
    writer_transport = _StubWriterTransport(output_text)
    judge_transport = _StubJudgeTransport(_passing_llm_scores())
    writer = AnthropicReasonDraftWriter(transport=writer_transport, model_id="claude-haiku-4-5")
    judge = AnthropicQualityJudge(transport=judge_transport, model_id="claude-sonnet-5", reasoning=True)

    import eval.writer_bakeoff as bakeoff_mod

    original_writer_cls = bakeoff_mod.AnthropicReasonDraftWriter
    original_judge_cls = bakeoff_mod.AnthropicQualityJudge
    bakeoff_mod.AnthropicReasonDraftWriter = lambda **_: writer
    bakeoff_mod.AnthropicQualityJudge = lambda **_: judge
    try:
        run_arm("claude-haiku-4-5", scenarios, pass_k=3, checkpoint_path=checkpoint)
        calls_after_first_run = writer_transport.calls
        assert calls_after_first_run == 3  # pass_k draws, no more

        run_arm("claude-haiku-4-5", scenarios, pass_k=3, checkpoint_path=checkpoint)
        assert writer_transport.calls == calls_after_first_run  # resumed, made no new calls
    finally:
        bakeoff_mod.AnthropicReasonDraftWriter = original_writer_cls
        bakeoff_mod.AnthropicQualityJudge = original_judge_cls
