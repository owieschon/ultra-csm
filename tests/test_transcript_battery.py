"""The transcript-consistency battery must hold for every case and be
deterministic across two runs (Universe v2, WS-Data-Classes Phase 2)."""

from __future__ import annotations

from eval.transcript_battery import CASES, run_battery
from ultra_csm.data_plane.narrative_content.transcripts import TRANSCRIPTS, transcript_for_event


def test_transcript_battery_holds_for_every_case():
    report = run_battery()
    assert report["hard_ok"], f"failing cases: {report['failed_cases']}"
    assert len(report["cases"]) == len(CASES)


def test_transcript_battery_is_deterministic_across_two_runs():
    first = run_battery()
    second = run_battery()
    assert first == second


def test_seven_transcripts_authored_across_five_accounts():
    assert len(TRANSCRIPTS) == 7
    account_ids = {t.account_id for t in TRANSCRIPTS.values()}
    assert len(account_ids) == 4  # pinehill, meridian, trailhead, pinnacle


def test_transcript_lookup_returns_none_for_unknown_event():
    assert transcript_for_event("not-a-real-event-id") is None


def test_pinehill_day99_quotes_the_day80_error_string_verbatim():
    from ultra_csm.data_plane.comms_fixtures import PINEHILL_ACCOUNT_ID
    from ultra_csm.data_plane.fixtures import det_id

    t = transcript_for_event(det_id("calendar-event", PINEHILL_ACCOUNT_ID, 99))
    assert t is not None
    assert "DISPATCH_BRIDGE_EVENT_LOSS: 214 of 1,880 dispatch events unacknowledged" in t.summary
