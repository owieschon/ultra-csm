"""Regression coverage for the R0 retry/timeout fix (finding #2, PR #119)."""

from __future__ import annotations

import subprocess

import pytest

from eval.run_quality_judge import _retryable, _score_with_retry
from ultra_csm.llm_transport import TRANSPORT_ENV_VAR


class _FlakyJudge:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self.calls = 0

    def score_output(self, request, output):
        self.calls += 1
        if self.calls == 1:
            raise self._exc
        return {"grounding_fidelity": 3}


class _AlwaysTimesOutJudge:
    def score_output(self, request, output):
        raise subprocess.TimeoutExpired(cmd=["claude"], timeout=120.0)


def test_retryable_recognizes_claude_code_subprocess_failures(monkeypatch):
    monkeypatch.setenv(TRANSPORT_ENV_VAR, "claude_code")

    assert _retryable(subprocess.TimeoutExpired(cmd=["claude"], timeout=120.0))
    assert _retryable(subprocess.CalledProcessError(1, ["claude"]))


def test_retryable_ignores_subprocess_failures_for_anthropic_api(monkeypatch):
    monkeypatch.setenv(TRANSPORT_ENV_VAR, "anthropic_api")

    assert not _retryable(subprocess.TimeoutExpired(cmd=["claude"], timeout=30.0))
    assert not _retryable(subprocess.CalledProcessError(1, ["claude"]))


def test_score_with_retry_survives_a_single_claude_code_timeout(monkeypatch):
    # Reproduces finding #2: R0's second run completed 109/127 gold items,
    # then one subprocess.TimeoutExpired aborted the entire run because
    # _retryable() didn't recognize it. This proves the run now continues.
    monkeypatch.setenv(TRANSPORT_ENV_VAR, "claude_code")
    judge = _FlakyJudge(subprocess.TimeoutExpired(cmd=["claude"], timeout=120.0))

    result = _score_with_retry(judge, {}, {})

    assert result == {"grounding_fidelity": 3}
    assert judge.calls == 2


def test_score_with_retry_still_aborts_on_a_persistent_claude_code_timeout(monkeypatch):
    monkeypatch.setenv(TRANSPORT_ENV_VAR, "claude_code")

    with pytest.raises(subprocess.TimeoutExpired):
        _score_with_retry(_AlwaysTimesOutJudge(), {}, {})
