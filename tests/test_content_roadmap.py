"""content_roadmap.py: hand-computed arithmetic on a fixture, plus a real-
book smoke test proving the aggregation actually runs end-to-end against
fleetops + loopway."""

from __future__ import annotations

from ultra_csm.content_roadmap import (
    KNOWN_TRIGGERS,
    TENANTS,
    RoadmapRow,
    build_content_roadmap,
    score_rows,
)


def test_score_rows_additive_arr_never_deprioritizes():
    """Decision 4: coverage_gap_score = accounts_affected + high_arr_bonus
    - existing_content_count. A gap with zero high-ARR accounts must score
    exactly accounts_affected - existing_content_count, never less."""

    accounts_by_trigger = {
        "health_red": {"a1", "a2", "a3"},
        "feature_shallow_depth": {"a4"},
    }
    high_arr_by_trigger = {
        "health_red": {"a1"},  # 1 of the 3 affected accounts is high-ARR
        "feature_shallow_depth": set(),  # zero high-ARR accounts
    }
    existing_count_by_gap = {"health_red": 2, "feature_shallow_depth": 0}

    rows = {
        r.gap: r
        for r in score_rows("fleetops", accounts_by_trigger, high_arr_by_trigger, existing_count_by_gap)
    }

    health_red = rows["health_red"]
    assert health_red.accounts_affected == 3
    assert health_red.high_arr_bonus == 1
    assert health_red.existing_content_count == 2
    assert health_red.coverage_gap_score == 3 + 1 - 2 == 2

    feature_shallow_depth = rows["feature_shallow_depth"]
    assert feature_shallow_depth.high_arr_bonus == 0
    # Zero high-ARR accounts -> score is exactly accounts_affected - existing, not less.
    assert feature_shallow_depth.coverage_gap_score == 1 + 0 - 0 == 1

    # Every trigger not mentioned in the input dicts still gets a zeroed row.
    assert set(rows) == set(KNOWN_TRIGGERS)
    untouched = [r for g, r in rows.items() if g not in {"health_red", "feature_shallow_depth"}]
    assert all(r.accounts_affected == 0 and r.coverage_gap_score == 0 for r in untouched)


def test_score_rows_covers_every_known_trigger_even_with_empty_input():
    rows = score_rows("loopway", {}, {}, {})
    assert {r.gap for r in rows} == set(KNOWN_TRIGGERS)
    assert all(isinstance(r, RoadmapRow) and r.tenant == "loopway" for r in rows)


def test_build_content_roadmap_real_book_smoke():
    """Real fleetops + loopway books, real _account_tier_and_triggers,
    real content_catalog.json coverage counts -- proves the whole chain
    runs end-to-end, not just the arithmetic in isolation."""

    rows = build_content_roadmap()
    assert len(rows) == len(TENANTS) * len(KNOWN_TRIGGERS)
    assert {r.tenant for r in rows} == set(TENANTS)
    # Sorted descending by coverage_gap_score.
    scores = [r.coverage_gap_score for r in rows]
    assert scores == sorted(scores, reverse=True)
    # At least one real trigger fires across two books this large.
    assert any(r.accounts_affected > 0 for r in rows)
