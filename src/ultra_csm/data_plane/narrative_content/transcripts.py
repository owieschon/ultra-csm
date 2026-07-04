"""Meeting transcripts/notes for seven existing calendar beats across five
accounts (Universe v2, WS-Data-Classes Phase 2).

Each transcript is keyed by the SAME ``det_id("calendar-event", ...)`` the
account's own ``*_comms.py`` module already computes for that day -- no new
calendar event is invented, this module only renders an existing beat's
meeting content in a new medium (structured attendees + a
summary/decisions/actions body, standing in for full dialogue turns).
Content agrees with canon: modules named match each account's actual
entitlements, error strings quoted (Pinehill) match the bible's
error-string canon table verbatim, and cast voices match
docs/SYNTHETIC_UNIVERSE_BIBLE.md's per-account dossiers. Dormant until a
lens/briefing consumer reads it -- no code path does yet (see
docs/PROGRAM_REPORT_12.md's Owner Ask).
"""

from __future__ import annotations

from dataclasses import dataclass

from ultra_csm.data_plane.comms_fixtures import PINEHILL_ACCOUNT_ID
from ultra_csm.data_plane.fixtures import det_id
from ultra_csm.data_plane.meridian_comms import MERIDIAN_ACCOUNT_ID
from ultra_csm.data_plane.pinnacle_comms import PINNACLE_ACCOUNT_ID
from ultra_csm.data_plane.trailhead_comms import TRAILHEAD_ACCOUNT_ID

_CSM_102 = "csm102@fleetops-platform.example"  # Marcus Webb
_CSM_101 = "csm101@fleetops-platform.example"  # Priya Nandan
_DENNIS = "dennis.gruber@pinehill-transport.example"
_MONICA = "monica.reeves@pinnacle-supply.example"
_ALICIA = "alicia.fernandez@meridian-fleet.example"
_SARAH = "sarah.chen@meridian-fleet.example"
_VANESSA = "vanessa.torres@trailhead-logistics.example"
_MIKE = "mike.lindgren@trailhead-logistics.example"


@dataclass(frozen=True)
class MeetingTranscript:
    """A meeting note keyed to an existing calendar event's det_id.

    ``turns`` holds either literal dialogue turns (speaker, line) or a
    structured summary/decisions/actions rendering, per the phase spec's
    "6-12 dialogue turns or summary+decisions+actions" -- this module uses
    the summary form throughout for uniformity, since none of the seven
    beats needed line-by-line dialogue to state their briefing-level truth.
    """

    event_det_id: str
    account_id: str
    day_offset: int
    title: str
    attendees: tuple[str, ...]
    summary: str
    decisions: tuple[str, ...]
    actions: tuple[str, ...]


TRANSCRIPTS: dict[str, MeetingTranscript] = {}


def _add(t: MeetingTranscript) -> None:
    TRANSCRIPTS[t.event_det_id] = t


# ---------------------------------------------------------------------------
# Pinehill Transport -- days 1 (kickoff), 57 (mid-stall), 99 (post-fix)
# ---------------------------------------------------------------------------

_add(MeetingTranscript(
    event_det_id=det_id("calendar-event", PINEHILL_ACCOUNT_ID, 1),
    account_id=PINEHILL_ACCOUNT_ID,
    day_offset=1,
    title="Pinehill Transport <> CSM Sync -- Kickoff",
    attendees=(_CSM_102, _DENNIS),
    summary=(
        "Kickoff for the Legacy Dispatch Integration phase of Pinehill's Launch Plan. "
        "Marcus walked through the FleetOps four-phase methodology and flagged RouteLedger "
        "5.2 (Dennis's existing on-prem dispatch system) as the one blocker needing a named "
        "IT contact before Dispatch Bridge configuration can start. Dennis confirmed his "
        "contractor Raul will be the RouteLedger admin point of contact."
    ),
    decisions=(
        "Target 50% of 50 licensed assets reporting through Live Map by June 28, "
        "per the Launch Plan milestones agreed at signing.",
    ),
    actions=(
        "Pinehill: confirm Raul as named IT contact with RouteLedger admin access (owner Dennis).",
        "FleetOps: Grace Okafor to join the first working session once Raul is confirmed (owner Grace).",
    ),
))

_add(MeetingTranscript(
    event_det_id=det_id("calendar-event", PINEHILL_ACCOUNT_ID, 57),
    account_id=PINEHILL_ACCOUNT_ID,
    day_offset=57,
    title="Pinehill Transport <> CSM Sync -- Mid-Stall Check-In",
    attendees=(_CSM_102, _DENNIS),
    summary=(
        "Biweekly sync during the stall (cadence has slipped from weekly). Marcus recapped "
        "the two open Dispatch Bridge issues, quoting Grace's connector logs directly:\n\n"
        "  DISPATCH_BRIDGE_CONNECT_FAILURE: RouteLedger 5.2 SOAP endpoint refused connection "
        "(fault code AUTH-401, host dispatch.pinehill-transport.internal:8443)\n"
        "  DISPATCH_BRIDGE_TIMEOUT: upstream RouteLedger socket closed after 30000ms "
        "(job batch 4417, retry_count=3)\n\n"
        "Dennis reiterated Raul is stretched thin across two other contractor clients. Both "
        "agreed a direct Grace-Raul working session is faster than continuing to route "
        "symptom-by-symptom through Dennis."
    ),
    decisions=(
        "Grace and Raul will work the RouteLedger connector issues directly, "
        "not routed through Dennis.",
    ),
    actions=(
        "Pinehill: Dennis to set up the Grace/Raul direct session.",
        "FleetOps: Grace to bring a full timeline of both symptoms to that session.",
    ),
))

_add(MeetingTranscript(
    event_det_id=det_id("calendar-event", PINEHILL_ACCOUNT_ID, 99),
    account_id=PINEHILL_ACCOUNT_ID,
    day_offset=99,
    title="Pinehill Transport <> CSM Sync -- Post-Fix Review",
    attendees=(_CSM_102, _DENNIS),
    summary=(
        "First sync after the day-80 case resolved. Marcus quoted the original diagnostic "
        "one more time for the record:\n\n"
        "  DISPATCH_BRIDGE_EVENT_LOSS: 214 of 1,880 dispatch events unacknowledged in trailing "
        "24h window (RouteLedger ack timeout, queue=pinehill-dispatch-out)\n\n"
        "Marcus confirmed the second contractor who originally built the RouteLedger "
        "integration identified and fixed the root cause on the ack-timeout queue. Dennis "
        "reported no recurrence since the fix landed. Legacy Dispatch Integration Rocketlane "
        "phase moving toward completion now that the validate-event-delivery task is closing "
        "out."
    ),
    decisions=(
        "No further escalation needed -- the connector is holding stable post-fix.",
    ),
    actions=(
        "FleetOps: continue monitoring dispatch event acknowledgement rate through steady-state handoff.",
    ),
))

# ---------------------------------------------------------------------------
# Meridian Fleet Group -- day 131 (expansion scoping, Sarah's facilities
# thread), day 178 (close, Alicia's fleet-ops thread)
# ---------------------------------------------------------------------------

_add(MeetingTranscript(
    event_det_id=det_id("calendar-event", MERIDIAN_ACCOUNT_ID, "facilities-sync", 131),
    account_id=MERIDIAN_ACCOUNT_ID,
    day_offset=131,
    title="Meridian Facilities <> CSM Sync -- Expansion Scoping",
    attendees=(_CSM_101, _SARAH),
    summary=(
        "Facilities-side scoping sync for the pending Live Map + Maintenance Radar expansion "
        "-- aligning the facilities asset count and terms with the broader fleet-ops "
        "expansion Alicia's team is reviewing in parallel. Sarah confirmed facilities budget "
        "approval is already secured and her team is coordinating directly with Alicia's on "
        "final terms."
    ),
    decisions=(
        "Facilities expansion scope tracks the same close timeline as the fleet-ops expansion.",
    ),
    actions=(
        "Meridian: Sarah's team to finalize alignment with Alicia's team on combined terms.",
        "FleetOps: Priya to keep both threads synchronized ahead of close.",
    ),
))

_add(MeetingTranscript(
    event_det_id=det_id("calendar-event", MERIDIAN_ACCOUNT_ID, "fleet-ops-sync", 178),
    account_id=MERIDIAN_ACCOUNT_ID,
    day_offset=178,
    title="Meridian Fleet Ops <> CSM Sync -- Expansion Close",
    attendees=(_CSM_101, _ALICIA),
    summary=(
        "Closing sync for the $28M -> $36M ARR expansion (bringing the facilities fleet's "
        "assets under the existing Live Map and Maintenance Radar coverage). Priya confirmed "
        "everything is set to close this week; Alicia thanked the team for driving the "
        "expansion and confirmed excitement about the partnership going forward."
    ),
    decisions=(
        "Expansion closes this week at the reviewed terms.",
    ),
    actions=(
        "FleetOps: Priya to send the rollout plan for the newly added facilities assets once closed.",
    ),
))

# ---------------------------------------------------------------------------
# Trailhead Logistics -- day 178 (QBR, per the day-175 email's "Thursday"
# reference landing on the account's next scheduled sync)
# ---------------------------------------------------------------------------

_add(MeetingTranscript(
    event_det_id=det_id("calendar-event", TRAILHEAD_ACCOUNT_ID, 178),
    account_id=TRAILHEAD_ACCOUNT_ID,
    day_offset=178,
    title="Trailhead Logistics <> CSM Sync -- QBR",
    attendees=(_CSM_101, _VANESSA, _MIKE),
    summary=(
        "Quarterly business review. Priya walked through this quarter's Live Map, Route "
        "Optimizer, and Insights Hub numbers -- all strong, consistent with the exemplary-"
        "adoption baseline this account has held throughout. Mike added a fleet-utilization "
        "slide covering fleet-utilization specifics ahead of the meeting. Vanessa confirmed "
        "the deck was thorough with nothing further to add."
    ),
    decisions=(
        "No changes to the account's trajectory -- steady exemplary adoption continues.",
    ),
    actions=(),
))

# ---------------------------------------------------------------------------
# Pinnacle Supply Chain -- day 112 (Monica intro call)
# ---------------------------------------------------------------------------

_add(MeetingTranscript(
    event_det_id=det_id("calendar-event", PINNACLE_ACCOUNT_ID, 112),
    account_id=PINNACLE_ACCOUNT_ID,
    day_offset=112,
    title="Pinnacle Supply Chain <> CSM Sync -- Monica Intro Call",
    attendees=(_CSM_101, _MONICA),
    summary=(
        "First call with Monica Reeves (VP Supply Chain Operations), the new point of "
        "contact following Derek Vaughn's departure (silent since day 3). Priya introduced "
        "herself and gave full context on where Pinnacle stands across its entitled modules "
        "(Live Map, Route Optimizer, Insights Hub, Fuel Analytics, Dispatch Automation). "
        "Monica said she is still getting oriented and appreciated the team's patience while "
        "she gets up to speed on what Pinnacle actually has running today."
    ),
    decisions=(
        "Monica becomes the account's primary point of contact going forward.",
    ),
    actions=(
        "FleetOps: Priya to schedule a follow-up activation review once Monica is oriented.",
    ),
))


def transcript_for_event(event_det_id: str) -> MeetingTranscript | None:
    """Lookup by calendar-event det_id; ``None`` if no transcript is
    authored for that event (most calendar events have none -- these six
    beats are the only ones with a rendered transcript)."""

    return TRANSCRIPTS.get(event_det_id)
