"""Quarterly NPS/CSAT survey exhaust (Universe v2, WS-Data-Classes
Phase 4).

Uses the existing ``contracts.SurveyResponse`` (reserved for live connector
integration, simulation deferred until now) -- no new survey contract
invented. Quarterly schedule (days 45, 135, 225, 315) for the six arc
accounts plus both red herrings, scored and worded as causal exhaust of
each account's existing bible arc:

* Pinehill Transport -- day-45 detractor citing "the dispatch integration"
  (mid-stall, matches the day-30/day-80 case beats), recovering to a
  passive/promoter score by day 315 (post day-300 steady_state recovery).
* Quarrystone Logistics -- non-response every wave (absence is the point
  of this arc -- see the bible's "known, flagged risk that nobody acts
  on"; a non-response is represented as no ``SurveyResponse`` row for that
  account/day, not a fabricated score).
* Trailhead Logistics -- promoter, verbatim consistent with the day-165
  ``case_study_published`` health-band driver.
* Pinnacle Supply Chain, Meridian Fleet Group, Aspenridge Supply Chain --
  scores consistent with each arc's own briefing-level truth (recovering
  relational risk, expansion-ready, invisible-to-health-band decline).
* Cedar Valley (herring A), Ironridge Fleet Ops (herring B) -- mid-range,
  benign verbatims at every wave, matching "never actually at risk."

Bible appendix rows for each account/wave are recorded in
docs/SYNTHETIC_UNIVERSE_BIBLE.md's Class canon appendix.
"""

from __future__ import annotations

from ultra_csm.data_plane.aspenridge_comms import ASPENRIDGE_CHAMPION_CONTACT_ID
from ultra_csm.data_plane.comms_fixtures import PINEHILL_CHAMPION_CONTACT_ID
from ultra_csm.data_plane.contracts import SurveyResponse
from ultra_csm.data_plane.fixtures import account_id_for, det_id
from ultra_csm.data_plane.meridian_comms import MERIDIAN_ACCOUNT_ID
from ultra_csm.data_plane.narrative_shared import rfc3339
from ultra_csm.data_plane.pinnacle_comms import PINNACLE_ACCOUNT_ID
from ultra_csm.data_plane.trailhead_comms import TRAILHEAD_CHAMPION_CONTACT_ID

SURVEY_WAVES: tuple[int, ...] = (45, 135, 225, 315)

CEDAR_VALLEY_ACCOUNT_ID = account_id_for("cedar-valley")
CEDAR_VALLEY_CONTACT_ID = det_id("contact", CEDAR_VALLEY_ACCOUNT_ID, "diane.mercer@cedar-valley-dist.example")
IRONRIDGE_ACCOUNT_ID = account_id_for("ironridge-fleet")
IRONRIDGE_CONTACT_ID = det_id("contact", IRONRIDGE_ACCOUNT_ID, "walter.benton@ironridge-fleet.example")
QUARRYSTONE_ACCOUNT_ID = account_id_for("quarrystone-logistics")
ASPENRIDGE_ACCOUNT_ID = account_id_for("aspenridge-supply")

# Meridian's expansion-ready arc surveys the primary champion (Alicia
# Fernandez), whose contact id isn't exported by meridian_comms.py the way
# the single-thread accounts export a CHAMPION_CONTACT_ID constant --
# derived the same way (det_id("contact", account_id, email)).
MERIDIAN_CHAMPION_CONTACT_ID = det_id("contact", MERIDIAN_ACCOUNT_ID, "alicia.fernandez@meridian-fleet.example")


# (account_id, contact_id, day_offset) -> (survey_type, score, comment)
# ``comment=None`` with the row PRESENT still counts as a response (a score
# with no verbatim); a wave with NO row at all for an account is this
# module's representation of non-response -- see ``QUARRYSTONE_ACCOUNT_ID``
# below, which has zero rows across all four waves by design.
_RESPONSES: dict[tuple[str, str, int], tuple[str, float, str | None]] = {
    # Pinehill Transport -- detractor mid-stall, recovers by day 315.
    (account_id_for("pinehill-transport"), PINEHILL_CHAMPION_CONTACT_ID, 45): (
        "NPS", 3.0,
        "Honestly frustrated right now -- the dispatch integration has been nothing but "
        "problems since we signed. If this doesn't get fixed soon I don't know how I "
        "recommend this to anyone.",
    ),
    (account_id_for("pinehill-transport"), PINEHILL_CHAMPION_CONTACT_ID, 135): (
        "NPS", 6.0,
        "Things have gotten better since the integration issues got resolved. Not ready "
        "to call it great yet, but better.",
    ),
    (account_id_for("pinehill-transport"), PINEHILL_CHAMPION_CONTACT_ID, 225): (
        "NPS", 7.0,
        "Steady for a while now, no complaints.",
    ),
    (account_id_for("pinehill-transport"), PINEHILL_CHAMPION_CONTACT_ID, 315): (
        "NPS", 8.0,
        "Would recommend at this point -- the dispatch integration finally works the way "
        "it should have from day one.",
    ),
    # Pinnacle Supply Chain -- single-threaded risk recovers with Monica.
    (PINNACLE_ACCOUNT_ID, det_id("contact", PINNACLE_ACCOUNT_ID, "monica.reeves@pinnacle-supply.example"), 135): (
        "NPS", 6.0, "Still getting oriented, but the team's been responsive.",
    ),
    (PINNACLE_ACCOUNT_ID, det_id("contact", PINNACLE_ACCOUNT_ID, "monica.reeves@pinnacle-supply.example"), 225): (
        "NPS", 7.0, "Recovery plan is working, adoption is back on track.",
    ),
    (PINNACLE_ACCOUNT_ID, det_id("contact", PINNACLE_ACCOUNT_ID, "monica.reeves@pinnacle-supply.example"), 315): (
        "NPS", 8.0, "Confident in the account now, renewal conversation went smoothly.",
    ),
    # Quarrystone Logistics -- NO responses at any wave (absence again).
    # (deliberately no entries here)
    # Aspenridge Supply Chain -- calm, benign, unaware of its own silent decline.
    (ASPENRIDGE_ACCOUNT_ID, ASPENRIDGE_CHAMPION_CONTACT_ID, 45): (
        "NPS", 8.0, "No issues to report, everything's running the way it always has.",
    ),
    (ASPENRIDGE_ACCOUNT_ID, ASPENRIDGE_CHAMPION_CONTACT_ID, 135): (
        "NPS", 8.0, "Same as last quarter -- steady.",
    ),
    (ASPENRIDGE_ACCOUNT_ID, ASPENRIDGE_CHAMPION_CONTACT_ID, 225): (
        "NPS", 7.0, "Nothing new, quarterly review covered everything.",
    ),
    (ASPENRIDGE_ACCOUNT_ID, ASPENRIDGE_CHAMPION_CONTACT_ID, 315): (
        "NPS", 7.0, "Business as usual.",
    ),
    # Meridian Fleet Group -- expansion-ready, warm and growing.
    (MERIDIAN_ACCOUNT_ID, MERIDIAN_CHAMPION_CONTACT_ID, 45): (
        "NPS", 9.0, "Adoption has been fast, the team loves it.",
    ),
    (MERIDIAN_ACCOUNT_ID, MERIDIAN_CHAMPION_CONTACT_ID, 135): (
        "NPS", 9.0, "Expansion conversation is exactly where it should be.",
    ),
    (MERIDIAN_ACCOUNT_ID, MERIDIAN_CHAMPION_CONTACT_ID, 225): (
        "NPS", 9.0, "Thrilled with how the expansion rollout is going.",
    ),
    (MERIDIAN_ACCOUNT_ID, MERIDIAN_CHAMPION_CONTACT_ID, 315): (
        "NPS", 10.0, "Best vendor relationship we have right now.",
    ),
    # Trailhead Logistics -- promoter, case-study consistent from day 225 on
    # (post day-165 case_study_published health-band driver).
    (account_id_for("trailhead-logistics"), TRAILHEAD_CHAMPION_CONTACT_ID, 45): (
        "NPS", 9.0, "Exemplary experience so far, no complaints.",
    ),
    (account_id_for("trailhead-logistics"), TRAILHEAD_CHAMPION_CONTACT_ID, 135): (
        "NPS", 9.0, "Still the best rollout we've had with any vendor.",
    ),
    (account_id_for("trailhead-logistics"), TRAILHEAD_CHAMPION_CONTACT_ID, 225): (
        "NPS", 10.0,
        "Thrilled to have been featured in FleetOps' case study -- happy to keep advocating.",
    ),
    (account_id_for("trailhead-logistics"), TRAILHEAD_CHAMPION_CONTACT_ID, 315): (
        "NPS", 10.0, "Still our top recommendation among fleet platforms.",
    ),
    # Cedar Valley (herring A) -- mid-range, benign, never actually at risk.
    (CEDAR_VALLEY_ACCOUNT_ID, CEDAR_VALLEY_CONTACT_ID, 45): (
        "NPS", 7.0, "Renewal paperwork took a bit but nothing concerning.",
    ),
    (CEDAR_VALLEY_ACCOUNT_ID, CEDAR_VALLEY_CONTACT_ID, 135): (
        "NPS", 7.0, "All good since renewing.",
    ),
    (CEDAR_VALLEY_ACCOUNT_ID, CEDAR_VALLEY_CONTACT_ID, 225): (
        "NPS", 7.0, "Steady, no issues.",
    ),
    (CEDAR_VALLEY_ACCOUNT_ID, CEDAR_VALLEY_CONTACT_ID, 315): (
        "NPS", 8.0, "Happy with the platform overall.",
    ),
    # Ironridge Fleet Ops (herring B) -- mid-range, benign, one-day glitch long past.
    (IRONRIDGE_ACCOUNT_ID, IRONRIDGE_CONTACT_ID, 45): (
        "NPS", 7.0, "Works well for what we need.",
    ),
    (IRONRIDGE_ACCOUNT_ID, IRONRIDGE_CONTACT_ID, 135): (
        "NPS", 8.0, "No real complaints, that webhook hiccup months back was resolved fast.",
    ),
    (IRONRIDGE_ACCOUNT_ID, IRONRIDGE_CONTACT_ID, 225): (
        "NPS", 8.0, "Consistent experience.",
    ),
    (IRONRIDGE_ACCOUNT_ID, IRONRIDGE_CONTACT_ID, 315): (
        "NPS", 8.0, "Still satisfied.",
    ),
}


def survey_responses_as_of(account_id: str, as_of_day: int) -> list[SurveyResponse]:
    """``SurveyResponse`` rows for *account_id* at every wave on or before
    *as_of_day*. An account with no row for a given wave (Quarrystone,
    every wave) is a non-response, not a fabricated score."""

    rows: list[SurveyResponse] = []
    for (acct_id, contact_id, day), (survey_type, score, comment) in _RESPONSES.items():
        if acct_id != account_id or day > as_of_day:
            continue
        rows.append(
            SurveyResponse(
                survey_id=det_id("survey", account_id, contact_id, day),
                account_id=account_id,
                contact_id=contact_id,
                survey_type=survey_type,  # type: ignore[arg-type]
                score=score,
                comment=comment,
                timestamp=rfc3339(day, 9),
            )
        )
    rows.sort(key=lambda r: r.timestamp)
    return rows


def response_rate_by_account(as_of_day: int = max(SURVEY_WAVES)) -> dict[str, float]:
    """Fraction of waves-on-or-before *as_of_day* with an actual response,
    per account -- the shape that would surface Quarrystone's 0.0 as a
    signal to a consumer that reads response rate rather than raw rows."""

    accounts = {acct_id for acct_id, _contact, _day in _RESPONSES} | {QUARRYSTONE_ACCOUNT_ID}
    waves_elapsed = [d for d in SURVEY_WAVES if d <= as_of_day]
    if not waves_elapsed:
        return {account_id: 0.0 for account_id in accounts}
    rates: dict[str, float] = {}
    for account_id in accounts:
        responded = len(survey_responses_as_of(account_id, as_of_day))
        rates[account_id] = responded / len(waves_elapsed)
    return rates
