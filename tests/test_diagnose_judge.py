"""Tests for the judge disagreement review report."""

from __future__ import annotations

from eval.diagnose_judge import build_report
from eval.judge_csm import QUALITY_DIMENSIONS


def _vec(g: int, t: int, a: int, p: int, tone: int, safety: int) -> dict[str, int]:
    return dict(zip(QUALITY_DIMENSIONS, [g, t, a, p, tone, safety], strict=True))


class _FakeJudge:
    model_id = "fake-judge"
    reasoning = True

    def __init__(self, scores: dict[str, int]) -> None:
        self._scores = scores

    def score_output_with_reasons(self, request: dict, output: dict):
        return self._scores, {
            dimension: f"reason for {dimension}"
            for dimension in QUALITY_DIMENSIONS
        }


def test_disagreement_report_includes_review_context(monkeypatch):
    reference = _vec(3, 3, 3, 3, 3, 3)
    judge_scores = _vec(3, 3, 1, 3, 3, 3)
    item = {
        "candidate_id": "slot-b-gold-test",
        "request": {
            "account_name": "Acme Logistics",
            "disposition": "propose_customer_action",
            "recommended_action": "draft_customer_outreach",
            "customer_contact_allowed": True,
            "priority": {"score": 95},
            "evidence": [{"evidence_id": "e1"}],
            "untrusted_text_fragments": [],
        },
        "output": {
            "reason": "Specific claim [evidence:e1].",
            "customer_draft": "Hi Jordan, can we review blockers?",
            "cited_evidence_ids": ["e1"],
        },
        "reference": reference,
        "family": None,
    }
    monkeypatch.setattr(
        "eval.diagnose_judge._layer_items",
        lambda layer: [{**item, "layer": layer}],
    )

    report = build_report(_FakeJudge(judge_scores), layer="clean")

    assert report["artifact"] == "slot_b_judge_disagreement_report"
    assert report["summary"]["disagreement_items"] == 1
    row = report["review_rows"][0]
    assert row["candidate_id"] == "slot-b-gold-test"
    assert row["request"]["priority"]["score"] == 95
    assert row["output"]["customer_draft"].startswith("Hi Jordan")
    assert row["disagree_dims"] == {
        "account_specificity": {
            "reference": 3,
            "judge": 1,
            "judge_reason": "reason for account_specificity",
        }
    }
    assert row["review_fields"]["bucket"] is None


def test_disagreement_report_supports_limit_and_progress(monkeypatch):
    reference = _vec(3, 3, 3, 3, 3, 3)
    judge_scores = _vec(3, 3, 3, 3, 3, 3)
    items = [
        {
            "candidate_id": f"slot-b-gold-{index}",
            "request": {"account_name": f"Account {index}"},
            "output": {"reason": "ok", "cited_evidence_ids": []},
            "reference": reference,
            "family": None,
        }
        for index in range(3)
    ]
    monkeypatch.setattr(
        "eval.diagnose_judge._layer_items",
        lambda layer: [{**item, "layer": layer} for item in items],
    )
    progress_calls = []

    report = build_report(
        _FakeJudge(judge_scores),
        layer="clean",
        limit=2,
        progress=lambda index, total, item: progress_calls.append(
            (index, total, item["candidate_id"])
        ),
    )

    assert report["summary"]["total_items_scored"] == 2
    assert progress_calls == [
        (1, 2, "slot-b-gold-0"),
        (2, 2, "slot-b-gold-1"),
    ]
