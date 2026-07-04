"""Validation for the Universe v2 expected-actions gold set."""

from __future__ import annotations

import json

import pytest

from eval.expected_actions_gold import (
    ExpectedActionsGoldError,
    load_expected_actions,
)


def test_fleetops_expected_actions_load_and_cover_all_checkpoints():
    rows = load_expected_actions("fleetops")

    assert len(rows) >= 18
    accounts = {row.account_slug for row in rows}
    assert accounts >= {
        "pinehill-transport",
        "pinnacle-supply",
        "quarrystone-logistics",
        "aspenridge-supply",
        "meridian-fleet",
        "trailhead-logistics",
    }


def test_expected_actions_modes_are_final_vocabulary():
    rows = load_expected_actions("fleetops")

    assert {row.mode for row in rows} == {"shadow", "gap", "none"}
    for row in rows:
        if row.mode == "none":
            assert row.signal is None
            assert row.motion_in == ()
        else:
            assert row.motion_in


def test_expected_actions_rejects_unknown_mode(tmp_path):
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    (gold_dir / "acme_expected_actions.json").write_text(
        json.dumps([_row(mode="maybe")]), encoding="utf-8"
    )

    with pytest.raises(ExpectedActionsGoldError, match="unknown grading mode"):
        load_expected_actions("acme", gold_dir=gold_dir)


def test_expected_actions_rejects_unresolvable_account(tmp_path):
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    rows = [_row() for _ in range(18)]
    rows[0]["account_slug"] = "not-a-real-account"
    (gold_dir / "acme_expected_actions.json").write_text(json.dumps(rows), encoding="utf-8")

    with pytest.raises(ExpectedActionsGoldError, match="unknown acme synthetic-book account slug"):
        load_expected_actions("acme", gold_dir=gold_dir)


def test_expected_actions_rejects_none_mode_with_a_motion(tmp_path):
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    row = _row(mode="none")
    row["required"]["motion_in"] = ["personal_email"]
    (gold_dir / "acme_expected_actions.json").write_text(
        json.dumps([row] * 18), encoding="utf-8"
    )

    with pytest.raises(ExpectedActionsGoldError, match="empty motion_in"):
        load_expected_actions("acme", gold_dir=gold_dir)


def _row(*, mode: str = "shadow", account_slug: str = "pinehill-transport") -> dict:
    return {
        "tenant": "acme",
        "account_slug": account_slug,
        "checkpoint_day": 1,
        "mode": mode,
        "required": {
            "signal": None if mode == "none" else "reply_latency_trend",
            "motion_in": [] if mode == "none" else ["personal_email"],
            "evidence_must_include": [],
        },
        "forbidden_motions": [],
        "notes": "synthetic test row",
    }
