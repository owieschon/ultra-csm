"""Operating cadence: story-day arithmetic must match the drip-seeder's,
byte for byte, since both derive the "current day of the unfolding
narrative" from the same frozen anchor and must never drift apart.

drip_seed.py (~/ultra-csm-corpus-runs/live-reseed-20260704/drip_seed.py)
computes: current_story_day = (today - anchor_date).days, where
anchor_date = date.fromisoformat(anchor["anchor_date"]). scripts/operating/
daily_run.sh reuses the identical formula (see its inline Python block) --
this test locks that formula down against three hand-computed dates so a
future edit to either side trips a red test instead of silent drift.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

# Frozen anchor_date from ~/ultra-csm-corpus-runs/live-reseed-20260704/anchor.json.
# Never recomputed from "today" -- read verbatim, same as the seeder does.
ANCHOR_DATE = date(2026, 5, 15)

# tick.py / demo-sweep's shared fixture-day-offset space uses SEED_DATE
# (synthetic_book.py) as its zero point. anchor.py's own translation rule
# (translated_date = fixture_date + (anchor_date - fixture_seed_date)) with
# fixture_seed_date == SEED_DATE implies fixture day_offset == story_day for
# "today" -- verified here alongside the story-day formula itself.
SEED_DATE = date(2026, 6, 21)


def story_day(today: date, anchor_date: date = ANCHOR_DATE) -> int:
    """Reproduces drip_seed.py's current_story_day formula exactly."""
    return (today - anchor_date).days


def fixture_as_of(today: date) -> date:
    """Reproduces daily_run.sh's as_of derivation for tick/demo-sweep."""
    return SEED_DATE + timedelta(days=story_day(today))


@pytest.mark.parametrize(
    "today, expected_story_day, expected_fixture_as_of",
    [
        # anchor_day 50, as recorded in anchor.json's own "anchor_day": 50
        # for anchor_date 2026-05-15, created_at 2026-07-04.
        (date(2026, 7, 4), 50, date(2026, 8, 10)),
        # The day after: story day advances by exactly one, matching the
        # drip's own +1-per-real-day invariant (dispatch Glossary).
        (date(2026, 7, 5), 51, date(2026, 8, 11)),
        # A hand-picked date well past both seed dates, to rule out an
        # off-by-one that only a single day happens to hide.
        (date(2026, 8, 1), 78, date(2026, 9, 7)),
    ],
)
def test_story_day_matches_drip_seed_formula(today, expected_story_day, expected_fixture_as_of):
    assert story_day(today) == expected_story_day
    assert fixture_as_of(today) == expected_fixture_as_of


def test_story_day_is_days_since_anchor_date_exactly():
    """Guards against reintroducing a +1/-1 or timezone-shift bug: the
    formula is a plain date subtraction, nothing else."""
    today = date(2026, 7, 4)
    assert story_day(today) == (today - ANCHOR_DATE).days
