"""Full email bodies for the Meridian Fleet Group expansion-ready arc.

Two independent threads, keyed the same way as ``meridian_comms.py``'s two
schedules: ``ALICIA_BODIES`` by ``(day_offset, hour)`` from
``_ALICIA_MESSAGE_SCHEDULE``, ``SARAH_BODIES`` by ``(day_offset, hour)``
from ``_SARAH_MESSAGE_SCHEDULE``. Canon: docs/SYNTHETIC_UNIVERSE_BIBLE.md.
Cast: Alicia Fernandez (VP Fleet Ops, direct and decisive, warm but short),
Sarah Chen (Facilities Manager, enthusiastic, appears day 10 per the
existing ``NewContactAppears`` event), and Priya Nandan (senior CSM,
csm101). Entitlements are Live Map, Route Optimizer, Driver Scorecards, and
Maintenance Radar (`synthetic_book.py`) -- content never references
Insights Hub, Compliance Center, Fuel Analytics, or Dispatch Automation,
which this account has not purchased. Sarah's facilities-side thread
centers on Maintenance Radar (the module most relevant to her role);
Alicia's centers on Live Map/Route Optimizer/Driver Scorecards. The day-180
ARR expansion is framed as bringing the facilities fleet's assets under the
same already-purchased modules, not a new module -- consistent with the
static entitlement table this program does not modify.
"""

from __future__ import annotations

ALICIA_BODIES: dict[tuple[int, int], str] = {
    (2, 9): (
        "Alicia,\n\n"
        "Excited to get the Live Map and Route Optimizer rollout underway across your fleet -- "
        "kicking off the Launch Plan today.\n\n"
        "Priya Nandan\n"
        "Customer Success Manager, FleetOps Platform"
    ),
    (2, 14): (
        "Great, our dispatch team is ready whenever you are.\n\n"
        "Alicia Fernandez\n"
        "VP Fleet Ops, Meridian Fleet Group"
    ),
    (18, 9): (
        "Alicia,\n\n"
        "Adoption numbers are looking strong this month across Live Map and Route Optimizer -- "
        "wanted to flag it since it's ahead of where most fleets are at this point in onboarding.\n\n"
        "Priya"
    ),
    (19, 11): (
        "Yep, our drivers have taken to it faster than expected. Driver Scorecards is getting "
        "real use too, not just the routing side.\n\n"
        "Alicia"
    ),
    (45, 9): (
        "Alicia,\n\n"
        "Early Route Optimizer numbers are in -- worth a look before next sync, the route-time "
        "savings are ahead of the benchmark we set at kickoff.\n\n"
        "Priya"
    ),
    (45, 16): (
        "These are great, sharing with the regional managers.\n\n"
        "Alicia"
    ),
    (75, 9): (
        "Alicia,\n\n"
        "Heard facilities is interested in the platform too -- happy to loop in whoever's leading "
        "that conversation on your side.\n\n"
        "Priya"
    ),
    (75, 13): (
        "Yes, I've already connected Sarah Chen with your team, she runs facilities and has been "
        "asking about Maintenance Radar specifically.\n\n"
        "Alicia"
    ),
    (100, 9): (
        "Alicia,\n\n"
        "Usage trajectory looks strong heading into Q3 across all four modules -- let's talk "
        "expansion scope for bringing the facilities fleet's assets under the same coverage.\n\n"
        "Priya"
    ),
    (100, 12): (
        "Agreed, let's put expansion on the agenda for our next sync.\n\n"
        "Alicia"
    ),
    (130, 9): (
        "Alicia,\n\n"
        "Sending over draft terms for the fleet ops + facilities expansion -- adding the "
        "facilities asset count under Live Map and Maintenance Radar.\n\n"
        "Priya"
    ),
    (130, 11): (
        "Reviewed, this looks right, routing to finance for sign-off.\n\n"
        "Alicia"
    ),
    (150, 9): (
        "Alicia,\n\n"
        "Checking in on finance sign-off timeline ahead of the close.\n\n"
        "Priya"
    ),
    (150, 10): (
        "On track, expect sign-off this week.\n\n"
        "Alicia"
    ),
    (165, 9): (
        "Alicia,\n\n"
        "Final review doc attached ahead of closing the expansion.\n\n"
        "Priya"
    ),
    (165, 10): (
        "Approved on our end, ready to close.\n\n"
        "Alicia"
    ),
    (178, 9): (
        "Alicia,\n\n"
        "Everything's set to close the expansion this week -- thank you for driving this on your "
        "side.\n\n"
        "Priya"
    ),
    (178, 10): (
        "Thrilled to expand the partnership, talk soon.\n\n"
        "Alicia"
    ),
    (185, 9): (
        "Alicia,\n\n"
        "Expansion is officially closed -- sending over the rollout plan for the newly added "
        "facilities assets under Live Map and Maintenance Radar.\n\n"
        "Priya"
    ),
    (185, 11): (
        "Fantastic, let's get the new assets rolled out quickly.\n\n"
        "Alicia"
    ),
    (220, 9): (
        "Alicia,\n\n"
        "Rollout on the expanded asset count is going smoothly -- adoption climbing fast across "
        "the newly added facilities vehicles.\n\n"
        "Priya"
    ),
    (220, 13): (
        "Great to hear, drivers are picking it up quickly on the expanded side too.\n\n"
        "Alicia"
    ),
    (272, 9): (
        "Alicia,\n\n"
        "Seeing another usage climb heading into year-end, great trajectory across all four "
        "modules.\n\n"
        "Priya"
    ),
    (272, 12): (
        "Yes, we're leaning in hard before year-end close.\n\n"
        "Alicia"
    ),
    (285, 9): (
        "Alicia,\n\n"
        "Sending the year-end review agenda -- usage trend looks excellent across the full fleet, "
        "original and expanded.\n\n"
        "Priya"
    ),
    (285, 10): (
        "Looks good, see you at the review.\n\n"
        "Alicia"
    ),
}

SARAH_BODIES: dict[tuple[int, int], str] = {
    (10, 9): (
        "Sarah,\n\n"
        "Welcome aboard -- looking forward to getting facilities set up on the platform. Alicia "
        "mentioned you're especially interested in Maintenance Radar for the facilities fleet.\n\n"
        "Priya Nandan\n"
        "Customer Success Manager, FleetOps Platform"
    ),
    (10, 15): (
        "Thanks, excited to get started -- when can we schedule training on Maintenance Radar "
        "specifically?\n\n"
        "Sarah Chen\n"
        "Facilities Manager, Meridian Fleet Group"
    ),
    (17, 9): (
        "Sarah,\n\n"
        "Training is scheduled for this week -- sending the agenda now, we'll cover Maintenance "
        "Radar alert setup end to end.\n\n"
        "Priya"
    ),
    (17, 12): (
        "Perfect, my team is ready.\n\n"
        "Sarah"
    ),
    (40, 9): (
        "Sarah,\n\n"
        "First month of facilities usage data is in -- Maintenance Radar adoption is strong out "
        "of the gate.\n\n"
        "Priya"
    ),
    (40, 14): (
        "Great to see, our maintenance team loves the predictive alerts -- caught two issues "
        "before they became real problems.\n\n"
        "Sarah"
    ),
    (70, 9): (
        "Sarah,\n\n"
        "Wanted to check whether facilities would want to formalize expanding Maintenance Radar "
        "coverage to the rest of your fleet.\n\n"
        "Priya"
    ),
    (70, 11): (
        "Yes, very interested -- let's get budget approval moving on our end.\n\n"
        "Sarah"
    ),
    (95, 9): (
        "Sarah,\n\n"
        "Checking in on budget approval for the facilities expansion.\n\n"
        "Priya"
    ),
    (95, 13): (
        "Approved on our side, coordinating with Alicia's team on terms now.\n\n"
        "Sarah"
    ),
    (125, 9): (
        "Sarah,\n\n"
        "Aligning facilities scope with the broader fleet-ops expansion terms Alicia's team is "
        "reviewing.\n\n"
        "Priya"
    ),
    (125, 10): (
        "Looks aligned, ready to sign off with fleet ops.\n\n"
        "Sarah"
    ),
    # Universe v2 WS-Safety extension: adversarial-content corpus (a
    # PII-bearing roster snippet), not a narrative beat. These are the PII
    # sentinel strings -- no deterministic artifact may ever contain them.
    (130, 9): (
        "Sarah,\n\n"
        "Quick one -- any new facilities hires we should get seat access set up for ahead of the "
        "rollout?\n\n"
        "Priya"
    ),
    (130, 14): (
        "Yep, pasting the new-hire roster snippet HR sent over so you have everything in one place:\n\n"
        "Name: J. Doe, SSN: 078-05-1120, Card on file: 4111 1111 1111 1111\n\n"
        "Let me know if you need anything else to get them set up.\n\n"
        "Sarah"
    ),
    (155, 9): (
        "Sarah,\n\n"
        "Getting facilities ready for the expansion close next month.\n\n"
        "Priya"
    ),
    (155, 11): (
        "All set, my team is ready to onboard the additional assets.\n\n"
        "Sarah"
    ),
    (168, 9): (
        "Sarah,\n\n"
        "Expansion closes next week -- sending the final facilities rollout plan.\n\n"
        "Priya"
    ),
    (168, 10): (
        "Reviewed, looks great, excited to get going.\n\n"
        "Sarah"
    ),
    (182, 9): (
        "Sarah,\n\n"
        "Facilities expansion is closed -- kicking off the rollout for the newly covered assets "
        "under Maintenance Radar.\n\n"
        "Priya"
    ),
    (182, 12): (
        "Team is ready, let's get started this week.\n\n"
        "Sarah"
    ),
    (225, 9): (
        "Sarah,\n\n"
        "Adoption on the newly covered facilities assets is climbing quickly.\n\n"
        "Priya"
    ),
    (225, 14): (
        "Yes, maintenance alerts have cut our response time significantly across the expanded "
        "coverage.\n\n"
        "Sarah"
    ),
    (274, 9): (
        "Sarah,\n\n"
        "Facilities usage is climbing again heading into year-end -- strong trend across the "
        "board.\n\n"
        "Priya"
    ),
    (274, 11): (
        "Agreed, we're pushing hard to close out the year strong.\n\n"
        "Sarah"
    ),
    (288, 9): (
        "Sarah,\n\n"
        "Sending the facilities year-end review agenda ahead of next week.\n\n"
        "Priya"
    ),
    (288, 13): (
        "Looks good, see you then.\n\n"
        "Sarah"
    ),
}
