"""Tests for the judge disagreement review report."""

from __future__ import annotations

from eval.diagnose_judge import (
    _read_audit_ids,
    _write_audit_history,
    build_agreed_cell_audit,
    build_report,
)
from eval.judge_anthropic import JUDGE_PROMPT_VERSION
from eval.judge_csm import QUALITY_DIMENSIONS
from eval.reference_review import build_reference_review


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
    assert report["judge_prompt_version"] == JUDGE_PROMPT_VERSION
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
    assert "regenerate_candidate" in row["review_fields"]["allowed_buckets"]
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


def test_agreed_cell_audit_is_blind_and_keyed_separately():
    item = {
        "candidate_id": "slot-b-gold-agreed",
        "layer": "clean",
        "family": "control_good",
        "request": {
            "account_name": "Acme Logistics",
            "priority": {"score": 95},
            "evidence": [{"evidence_id": "e1"}],
        },
        "output": {
            "reason": "Specific claim [evidence:e1].",
            "customer_draft": "Hi Jordan, can we review blockers?",
            "cited_evidence_ids": ["e1"],
        },
        "reference": _vec(3, 2, 3, 3, 3, 3),
        "judge": _vec(3, 1, 3, 3, 2, 3),
        "judge_reasons": {
            dimension: f"reason for {dimension}"
            for dimension in QUALITY_DIMENSIONS
        },
    }

    audit, key = build_agreed_cell_audit([item], sample_size=3)

    assert audit["blind"] is True
    assert audit["sample_size"] == 3
    assert key["sample_size"] == 3
    assert {card["audit_id"] for card in audit["cards"]} == {
        record["audit_id"] for record in key["key_records"]
    }
    for card in audit["cards"]:
        assert "reference_score" not in card
        assert "judge_score" not in card
        assert "judge_reason" not in card
        assert "family" not in card
        assert card["human_score"] is None
    assert all(
        record["reference_score"] == record["judge_score"]
        for record in key["key_records"]
    )


def test_agreed_cell_audit_excludes_previous_cards():
    item = {
        "candidate_id": "slot-b-gold-agreed",
        "layer": "clean",
        "family": "control_good",
        "request": {"account_name": "Acme Logistics"},
        "output": {"reason": "ok", "cited_evidence_ids": []},
        "reference": _vec(3, 3, 3, 3, 3, 3),
        "judge": _vec(3, 3, 3, 3, 3, 3),
        "judge_reasons": {},
    }

    first_audit, _ = build_agreed_cell_audit([item], sample_size=1)
    first_id = first_audit["cards"][0]["audit_id"]
    second_audit, second_key = build_agreed_cell_audit(
        [item],
        sample_size=6,
        exclude_audit_ids={first_id},
    )

    assert second_audit["excluded_previous_cards"] == 1
    assert first_id not in {card["audit_id"] for card in second_audit["cards"]}
    assert second_audit["sample_size"] == 5
    assert second_key["sample_size"] == 5


def test_audit_history_round_trips_burned_ids(tmp_path):
    path = tmp_path / "audit_history.json"
    ids = {"judge-audit-a", "judge-audit-b"}

    _write_audit_history(path, ids)

    assert _read_audit_ids(path) == ids


def test_audit_history_reads_key_shape(tmp_path):
    path = tmp_path / "audit_key.json"
    path.write_text(
        """
{
  "artifact": "slot_b_judge_agreed_cell_audit_key",
  "key_records": [
    {"audit_id": "judge-audit-a"},
    {"audit_id": "judge-audit-b"}
  ]
}
""",
        encoding="utf-8",
    )

    assert _read_audit_ids(path) == {"judge-audit-a", "judge-audit-b"}


def test_reference_review_filters_stale_reference_dimensions():
    report = {
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "review_rows": [
            {
                "candidate_id": "slot-b-gold-test",
                "layer": "clean",
                "family": None,
                "request": {"account_name": "Acme Logistics"},
                "output": {"reason": "ok"},
                "disagree_dims": {
                    "grounding_fidelity": {
                        "reference": 2,
                        "judge": 3,
                        "judge_reason": "truthful but generic",
                    },
                    "tone_fit": {
                        "reference": 2,
                        "judge": 3,
                        "judge_reason": "professional direct",
                    },
                },
            }
        ],
    }

    artifact = build_reference_review(report)

    assert artifact["artifact"] == "slot_b_iteration3_reference_review"
    assert artifact["claim_boundary"]["judge_prompt_frozen"] is True
    assert artifact["total_cells"] == 2
    assert artifact["cells_by_dimension"] == {"grounding_fidelity": 1, "tone_fit": 1}
    assert {card["dimension"] for card in artifact["cards"]} == {
        "grounding_fidelity",
        "tone_fit",
    }
    assert all(card["owner_review"]["final_reference_score"] is None for card in artifact["cards"])
