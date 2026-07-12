"""Tests for the R2 writer bake-off harness (no live creds)."""

from __future__ import annotations

import json

import pytest

from eval.writer_bakeoff import (
    GATED_DIMENSIONS,
    REPORTED_NOT_GATED,
    CheckpointProvenanceError,
    Scenario,
    _aggregate_arm,
    _run_provenance,
    _telemetry_from_draws,
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


def test_telemetry_from_draws_sums_only_priced_draws_and_reports_coverage():
    draws = [
        {"input_tokens": 100, "output_tokens": 50, "cost_usd": 0.001, "latency_ms": 500.0},
        {"input_tokens": 200, "output_tokens": 80, "cost_usd": 0.002, "latency_ms": 700.0},
        # A contract violation (or a draw from a pre-fix checkpoint) has no
        # telemetry -- must be excluded from the sums, not treated as zero.
        {"input_tokens": None, "output_tokens": None, "cost_usd": None, "latency_ms": None},
    ]

    telemetry = _telemetry_from_draws(draws)

    assert telemetry["n_draws_total"] == 3
    assert telemetry["n_draws_priced"] == 2
    assert telemetry["coverage"] == pytest.approx(2 / 3, abs=1e-4)
    assert telemetry["total_input_tokens"] == 300
    assert telemetry["total_output_tokens"] == 130
    assert telemetry["total_cost_usd"] == pytest.approx(0.003)
    assert telemetry["avg_latency_ms"] == pytest.approx(600.0)


def test_telemetry_from_draws_empty_arm_is_zero_not_a_crash():
    telemetry = _telemetry_from_draws([])

    assert telemetry["n_draws_total"] == 0
    assert telemetry["coverage"] == 0.0
    assert telemetry["avg_latency_ms"] is None


def test_run_arm_captures_per_draw_telemetry_via_a_real_per_draw_tracker(tmp_path, monkeypatch):
    # Reproduces the R2 finding: telemetry must NOT depend on a single
    # tracker shared across the whole arm (that tracker dies with the
    # process on a kill+resume). Each draw gets its own real
    # AnthropicReasonDraftWriter + CostTracker, stubbed only at the
    # transport boundary -- the constructor and cost-recording logic run
    # for real.
    scenarios = build_scenario_set(11)[:1]
    checkpoint = tmp_path / "checkpoint.json"
    _scenario, output_text = _scenario_and_output_text(scenarios[0].family)

    import eval.writer_bakeoff as bakeoff_mod

    def fake_writer(*, model_id, cost_tracker=None, **_):
        return AnthropicReasonDraftWriter(
            transport=_StubWriterTransport(output_text),
            model_id=model_id,
            cost_tracker=cost_tracker,
        )

    def fake_judge(**_):
        return AnthropicQualityJudge(
            transport=_StubJudgeTransport(_passing_llm_scores()),
            model_id="claude-sonnet-5",
            reasoning=True,
        )

    monkeypatch.setattr(bakeoff_mod, "AnthropicReasonDraftWriter", fake_writer)
    monkeypatch.setattr(bakeoff_mod, "AnthropicQualityJudge", fake_judge)

    arm = run_arm("claude-haiku-4-5", scenarios, pass_k=3, checkpoint_path=checkpoint)

    # _StubWriterTransport reports fixed input_tokens=100/output_tokens=50
    # per call; 3 draws (pass_k=3) with no retries needed.
    assert arm["telemetry"]["coverage"] == 1.0
    assert arm["telemetry"]["total_input_tokens"] == 3 * 100
    assert arm["telemetry"]["total_output_tokens"] == 3 * 50


def test_run_arm_telemetry_survives_from_checkpoint_alone_after_a_simulated_resume(tmp_path):
    # This is the direct regression test for the bug: a checkpoint written
    # by an earlier, now-dead process already has full per-draw telemetry.
    # run_arm must report it correctly WITHOUT making any new calls and
    # WITHOUT any live tracker -- because the checkpoint is the only thing
    # that survived the kill.
    scenarios = build_scenario_set(11)[:1]
    checkpoint = tmp_path / "checkpoint.json"
    passing_scores = {dim: 3 for dim in (*GATED_DIMENSIONS, *REPORTED_NOT_GATED)}
    prewritten_draws = [
        {
            "scenario_id": scenarios[0].scenario_id,
            "family": scenarios[0].family,
            "draw_index": i,
            "contract_ok": True,
            "contract_error": None,
            "scores": passing_scores,
            "gated_pass": True,
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.001,
            "latency_ms": 500.0,
        }
        for i in range(3)
    ]
    checkpoint.write_text(
        json.dumps(
            {
                "provenance": _run_provenance("claude-haiku-4-5", 3, scenarios),
                "draws": prewritten_draws,
            }
        )
    )

    import eval.writer_bakeoff as bakeoff_mod

    original_judge_cls = bakeoff_mod.AnthropicQualityJudge
    # No draws are outstanding, so this judge is never actually called --
    # stubbed only so run_arm's unconditional construction doesn't reach
    # for a real ANTHROPIC_API_KEY-backed client in this test environment.
    bakeoff_mod.AnthropicQualityJudge = lambda **_: object()
    try:
        arm = run_arm("claude-haiku-4-5", scenarios, pass_k=3, checkpoint_path=checkpoint)
    finally:
        bakeoff_mod.AnthropicQualityJudge = original_judge_cls

    assert arm["n_draws"] == 3
    assert arm["telemetry"]["coverage"] == 1.0
    assert arm["telemetry"]["total_input_tokens"] == 300
    assert arm["telemetry"]["total_cost_usd"] == pytest.approx(0.003)


def test_resume_refuses_when_scenario_content_changed(tmp_path):
    """report 76 finding D: a checkpoint whose scenarios_hash no longer matches
    (e.g. the P1 world fix changed request content while ids stayed stable)
    must refuse to resume rather than return stale draws."""
    scenarios = build_scenario_set(11)[:1]
    checkpoint = tmp_path / "checkpoint.json"
    stale = _run_provenance("claude-haiku-4-5", 3, scenarios)
    stale["scenarios_hash"] = "0" * 64  # simulate pre-fix world content
    checkpoint.write_text(json.dumps({"provenance": stale, "draws": []}))

    import eval.writer_bakeoff as bakeoff_mod

    original_judge_cls = bakeoff_mod.AnthropicQualityJudge
    bakeoff_mod.AnthropicQualityJudge = lambda **_: object()
    try:
        with pytest.raises(CheckpointProvenanceError, match="scenarios_hash"):
            run_arm("claude-haiku-4-5", scenarios, pass_k=3, checkpoint_path=checkpoint)
    finally:
        bakeoff_mod.AnthropicQualityJudge = original_judge_cls


def test_resume_refuses_legacy_checkpoint_without_provenance(tmp_path):
    scenarios = build_scenario_set(11)[:1]
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(json.dumps({"draws": []}))  # pre-guard format

    import eval.writer_bakeoff as bakeoff_mod

    original_judge_cls = bakeoff_mod.AnthropicQualityJudge
    bakeoff_mod.AnthropicQualityJudge = lambda **_: object()
    try:
        with pytest.raises(CheckpointProvenanceError, match="predates provenance"):
            run_arm("claude-haiku-4-5", scenarios, pass_k=3, checkpoint_path=checkpoint)
    finally:
        bakeoff_mod.AnthropicQualityJudge = original_judge_cls


def test_aggregate_arm_drops_orphan_draws():
    """A draw whose (scenario_id, draw_index) is outside the current scenario
    set x pass_k must not be counted."""
    scenarios = build_scenario_set(11)[:1]
    passing = {dim: 3 for dim in (*GATED_DIMENSIONS, *REPORTED_NOT_GATED)}

    def draw(scenario_id, di):
        return {
            "scenario_id": scenario_id,
            "family": "x",
            "draw_index": di,
            "contract_ok": True,
            "contract_error": None,
            "scores": passing,
            "gated_pass": True,
            "input_tokens": 1,
            "output_tokens": 1,
            "cost_usd": 0.0,
            "latency_ms": 1.0,
        }

    valid = [draw(scenarios[0].scenario_id, i) for i in range(3)]
    orphans = [draw(scenarios[0].scenario_id, 9), draw("ghost-scenario", 0)]
    arm = _aggregate_arm("claude-haiku-4-5", scenarios, valid + orphans, pass_k=3)

    assert arm["n_draws"] == 3  # orphans excluded
