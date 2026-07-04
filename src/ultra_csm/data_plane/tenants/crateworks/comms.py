"""Arc C1 comms/relationship fixtures for `crateworks-dockside-storage`
(``docs/TENANT_CRATEWORKS_BIBLE.md`` section 2): the fading champion, read
through the identity mess.

Uses the existing ``signal_extractor.py`` contracts (``CommunicationSignal``,
``StakeholderRelationship``) unmodified -- the same fixture shape
``eval/week1_protocol.py`` already computes the four signal families over
for the fleetops arcs. No new signal machinery: the width-2 misread at day
100 is a property of feeding two real contact ids into the existing,
unmodified ``thread_participation_width``, not a new code path.

Also provides a thin Zendesk-ish ticket transport (a fake HTTP client
serving CSV/JSON-ticket-shaped payloads) for the one internal-note canary
placement required by ``docs/UNIVERSE_V2_CONVENTIONS.md`` section 4 and
bible section 6 -- "simulated-vertical" pattern, same discipline as
``eval/attio_simulated_onboarding.py``'s ``FakeAttioClient``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from ultra_csm.data_plane.canary_registry import canary_token
from ultra_csm.data_plane.contracts import CommunicationSignal, CRMCase, StakeholderRelationship
from ultra_csm.data_plane.fixtures import det_id
from ultra_csm.data_plane.live_smoke import HttpRequest, HttpResponse
from ultra_csm.data_plane.tenants.crateworks.book import (
    DOCKSIDE_SLUG,
    TENANT,
    crateworks_account_id,
)

DOCKSIDE_ID = crateworks_account_id(DOCKSIDE_SLUG)

_DANA_PARENT = "d.okafor@crateworks-dockside-parent.example"
CONTACT_DANA_1 = det_id("contact", DOCKSIDE_ID, "dana-okafor-1")
CONTACT_DANA_2 = det_id("contact", DOCKSIDE_ID, "dana-okafor-2")

_BASE_ZENDESK_URL = "https://crateworks.zendesk.example/api/v2"
_TICKET_ID = det_id("ticket", DOCKSIDE_ID, "champion-transition-note")


def _sig_id(day: int, kind: str) -> str:
    return det_id("commsig", DOCKSIDE_ID, kind, day)


def _at(day_offset: int) -> str:
    from datetime import date, timedelta

    from ultra_csm.data_plane.tenants.crateworks.book import SEED_DATE

    return (date.fromisoformat(SEED_DATE) + timedelta(days=day_offset)).isoformat() + "T09:00:00+00:00"


def arc_c1_comms() -> list[CommunicationSignal]:
    """Reply-latency evidence on ``dana.okafor@...`` (healthy through ~day
    60, stretching 60-200, silent after ~130) plus the sparse
    ``d.okafor@...parent...`` thread from day 130 on -- bible section 2.
    Every inbound reply carries a real ``response_time_hours`` so
    ``reply_latency_trend`` never fabricates a trend from a partial
    window (the extractor's own fail-closed ``None`` behavior, unmodified)."""

    signals: list[CommunicationSignal] = []

    # Healthy baseline, day 0-59: latency ~8-14h, biweekly cadence.
    for day, latency in ((10, 8.0), (24, 10.0), (38, 11.0), (52, 14.0)):
        signals.append(
            CommunicationSignal(
                signal_id=_sig_id(day, "dana-original-inbound"),
                account_id=DOCKSIDE_ID,
                contact_id=CONTACT_DANA_1,
                channel="email",
                direction="inbound",
                timestamp=_at(day),
                response_time_hours=latency,
            )
        )
    # Fade window, day 60-129: latency stretching 14h -> 60h+ on the same
    # original address/contact_id.
    for day, latency in ((66, 18.0), (80, 28.0), (95, 40.0), (110, 55.0), (125, 62.0)):
        signals.append(
            CommunicationSignal(
                signal_id=_sig_id(day, "dana-original-fading"),
                account_id=DOCKSIDE_ID,
                contact_id=CONTACT_DANA_1,
                channel="email",
                direction="inbound",
                timestamp=_at(day),
                response_time_hours=latency,
            )
        )
    # Day 130+: sparse replies from the parent-company address, same human,
    # under the SECOND duplicate contact row (contact_id 2) -- the CRM
    # dedupe accident and the domain-change event are independent messes
    # that happen to compound (bible section 2's point exactly).
    for day, latency in ((135, 50.0), (160, 58.0), (190, 65.0)):
        signals.append(
            CommunicationSignal(
                signal_id=_sig_id(day, "dana-parent-sparse"),
                account_id=DOCKSIDE_ID,
                contact_id=CONTACT_DANA_2,
                channel="email",
                direction="inbound",
                timestamp=_at(day),
                response_time_hours=latency,
            )
        )

    return signals


# Per-contact relationship-graph activity day history, in offset-day order,
# used to derive each relationship row's real ``last_interaction`` as-of a
# given checkpoint. The CRM's accidental duplication (bible section 3.3)
# means BOTH duplicate rows for Dana Okafor already carry independent
# relationship-graph activity through the healthy/fading pre-transition
# period (the duplication is a CRM-side artifact of the same underlying
# person, not a comms-side split -- ``arc_c1_comms()`` correctly attributes
# every actual EMAIL to one real address/contact_id at a time; this
# relationship-graph history is the separate signal
# ``thread_participation_width`` reads, and is where the bible's day-100
# "two weak contacts" misread actually lives). Contact 2 additionally picks
# up the later parent-domain activity from day 130 on.
_CONTACT_1_DAYS = (10, 24, 38, 52, 66, 80, 95, 110, 125)
_CONTACT_2_DAYS = (15, 45, 75, 135, 160, 190)


def arc_c1_relationships(as_of_day: int | None = None) -> list[StakeholderRelationship]:
    """``StakeholderRelationship`` rows keyed by the two duplicate
    ``contact_id``s, each present only once that contact has a real first
    touch on or before ``as_of_day`` -- exactly what makes
    ``thread_participation_width`` read 2 at day 100 (both duplicate rows
    already have relationship-graph activity by day 100 -- see the module
    note above) without any identity-resolution layer (bible section 2's
    day-100 checkpoint truth), while still reading 1 before either contact
    has any activity at all, and reading through the day-130+ transition
    (contact 1 goes stale, contact 2 stays active on the parent thread).

    ``as_of_day=None`` returns the full-history (no filtering) shape used
    by the mess-integrity/duplicate-contact battery, not a specific
    checkpoint read.
    """

    def _last_on_or_before(days: tuple[int, ...], limit: int | None) -> int | None:
        eligible = [d for d in days if limit is None or d <= limit]
        return max(eligible) if eligible else None

    rows: list[StakeholderRelationship] = []
    last1 = _last_on_or_before(_CONTACT_1_DAYS, as_of_day)
    if last1 is not None:
        rows.append(
            StakeholderRelationship(
                account_id=DOCKSIDE_ID,
                contact_id=CONTACT_DANA_1,
                relationship_type="champion",
                strength="strong" if last1 < 60 else "weak",
                last_interaction=_at(last1)[:10],
                multi_thread_depth=1,
            )
        )
    last2 = _last_on_or_before(_CONTACT_2_DAYS, as_of_day)
    if last2 is not None:
        rows.append(
            StakeholderRelationship(
                account_id=DOCKSIDE_ID,
                contact_id=CONTACT_DANA_2,
                relationship_type="champion",
                strength="weak",
                last_interaction=_at(last2)[:10],
                multi_thread_depth=1,
            )
        )
    return rows


def arc_c1_cases() -> list[CRMCase]:
    """No support cases scripted for Arc C1 -- the story lives entirely in
    comms/relationship signals (bible section 2's "risk visible only
    through the mess" framing: not a ticket-volume story)."""

    return []


# ---------------------------------------------------------------------------
# Zendesk-ish fake ticket transport (bible section 6's canary placement:
# one internal-note comment, verbatim, on the Dockside ticket).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FakeTicket:
    ticket_id: str
    subject: str
    requester_email: str
    internal_notes: tuple[str, ...]


def dockside_ticket() -> FakeTicket:
    return FakeTicket(
        ticket_id=_TICKET_ID,
        subject="Champion contact transition -- confirm before next renewal touch",
        requester_email=_DANA_PARENT,
        internal_notes=(
            f"Internal note: possible duplicate/transitioned contact for Dana Okafor "
            f"following the Dockside/parent-co reorg; do not treat as a new "
            f"stakeholder without confirming. Internal reference: "
            f"{canary_token(TENANT, DOCKSIDE_SLUG)}",
        ),
    )


class FakeZendeskClient:
    """In-memory Zendesk-shaped HTTP transport -- the "simulated-vertical"
    pattern (``docs/UNIVERSE_V2_CONVENTIONS.md`` section 1), same shape as
    ``eval/attio_simulated_onboarding.py``'s ``FakeAttioClient``. Serves
    exactly one ticket (Dockside's) plus an empty-list response for every
    other account, matching a real Zendesk-ish ticket API's shape closely
    enough to exercise a transport boundary without inventing a schema."""

    def __init__(self) -> None:
        self.requests: list[HttpRequest] = []

    def send(self, req: HttpRequest) -> HttpResponse:
        self.requests.append(req)
        if req.url == f"{_BASE_ZENDESK_URL}/tickets.json":
            ticket = dockside_ticket()
            payload = {
                "tickets": [
                    {
                        "id": ticket.ticket_id,
                        "subject": ticket.subject,
                        "requester_email": ticket.requester_email,
                        "comments": [
                            {"public": False, "body": note} for note in ticket.internal_notes
                        ],
                    }
                ]
            }
            return HttpResponse(
                status=200,
                body=json.dumps(payload, sort_keys=True).encode("utf-8"),
                headers={"content-type": "application/json"},
            )
        return HttpResponse(status=404, body=b"{}", headers={"content-type": "application/json"})
