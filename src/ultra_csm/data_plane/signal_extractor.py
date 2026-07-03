"""Deterministic communication/cadence signal extraction. Metadata only.

No LLM, no randomness: every function here is a pure computation over
``CommunicationSignal`` / ``StakeholderRelationship`` rows (contracts.py --
previously declared but unused, "reserved for live connector integration")
and raw calendar/case wire shapes. Output is shaped so an existing lens can
cite it: each extracted signal carries a metric value plus the source
record ids it was computed from, mirroring (not reusing, to avoid touching
the shared ``EvidenceSource`` literal in contracts.py) the
``EvidenceRef(source, source_id, field, observed_at)`` shape from
:mod:`ultra_csm.data_plane.contracts`.

Four signal families, matching docs/SYNTHETIC_UNIVERSE_BIBLE.md's Phase U1
scope:

* reply-latency trend -- is the champion's average response time to CSM
  outbound email stretching or compressing over a trailing window;
* thread-participation width -- how many distinct contacts are active on
  the account's communication threads;
* meeting-cadence shift -- is the interval between confirmed calendar
  events widening, narrowing, or holding steady;
* ticket-frequency window -- open-case count in a trailing window, split
  by topic so repeat-topic pressure (e.g. Pinehill's three ``integration``
  cases) is visible as a single signal, not three independent ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from ultra_csm.data_plane.contracts import CommunicationSignal, CRMCase, StakeholderRelationship


@dataclass(frozen=True)
class SignalEvidence:
    """One grounded citation for an extracted signal. Same four fields as
    ``EvidenceRef`` (source/source_id/field/observed_at); a local type so
    this module never needs to widen the shared ``EvidenceSource`` literal
    for a source kind ("communications") that contract doesn't declare."""

    source: str
    source_id: str
    field: str
    observed_at: str


@dataclass(frozen=True)
class ExtractedSignal:
    """One deterministic metric, computed as of a given day, with its
    supporting evidence."""

    account_id: str
    metric_name: str
    value: float | None
    unit: str
    as_of: str
    evidence: tuple[SignalEvidence, ...]
    detail: str


def _iso(value: str) -> date:
    return date.fromisoformat(value[:10])


def reply_latency_trend(
    account_id: str,
    signals: list[CommunicationSignal],
    *,
    as_of: str,
    window_days: int = 21,
) -> ExtractedSignal:
    """Mean champion reply latency (hours) in the trailing *window_days*
    ending at *as_of*, vs. the equally-sized window immediately before it.
    Positive ``value`` = latency stretching (getting slower); negative =
    compressing. ``None`` when there isn't at least one inbound reply in
    each window (fail-closed: never fabricate a trend from partial data).
    """

    as_of_d = _iso(as_of)
    replies = [
        s
        for s in signals
        if s.account_id == account_id
        and s.direction == "inbound"
        and s.response_time_hours is not None
        and _iso(s.timestamp) <= as_of_d
    ]
    recent = [s for s in replies if (as_of_d - _iso(s.timestamp)).days <= window_days]
    prior = [
        s
        for s in replies
        if window_days < (as_of_d - _iso(s.timestamp)).days <= 2 * window_days
    ]
    if not recent or not prior:
        return ExtractedSignal(
            account_id=account_id,
            metric_name="reply_latency_trend_hours",
            value=None,
            unit="hours_delta",
            as_of=as_of,
            evidence=tuple(
                SignalEvidence("communications", s.signal_id, "response_time_hours", s.timestamp)
                for s in recent
            ),
            detail="insufficient reply history in one or both windows",
        )
    recent_mean = sum(s.response_time_hours for s in recent) / len(recent)
    prior_mean = sum(s.response_time_hours for s in prior) / len(prior)
    delta = round(recent_mean - prior_mean, 1)
    evidence = tuple(
        SignalEvidence("communications", s.signal_id, "response_time_hours", s.timestamp)
        for s in (*prior, *recent)
    )
    return ExtractedSignal(
        account_id=account_id,
        metric_name="reply_latency_trend_hours",
        value=delta,
        unit="hours_delta",
        as_of=as_of,
        evidence=evidence,
        detail=(
            f"trailing {window_days}d mean reply latency {recent_mean:.1f}h "
            f"vs prior window {prior_mean:.1f}h"
        ),
    )


def thread_participation_width(
    account_id: str,
    relationships: list[StakeholderRelationship],
    *,
    as_of: str,
) -> ExtractedSignal:
    """Count of distinct contacts with an active (``last_interaction`` on or
    before *as_of*) relationship to the account. Width 1 for the whole
    Pinehill arc is itself a signal: the stall never broadens or narrows the
    thread, distinguishing it from a single-threaded-risk story."""

    as_of_d = _iso(as_of)
    active = [r for r in relationships if r.account_id == account_id and _iso(r.last_interaction) <= as_of_d]
    evidence = tuple(
        SignalEvidence("communications", r.contact_id, "relationship_type", r.last_interaction)
        for r in active
    )
    return ExtractedSignal(
        account_id=account_id,
        metric_name="thread_participation_width",
        value=float(len(active)),
        unit="distinct_contacts",
        as_of=as_of,
        evidence=evidence,
        detail=f"{len(active)} active stakeholder relationship(s) as of {as_of}",
    )


def meeting_cadence_shift(
    account_id: str,
    calendar_events: dict,
    *,
    as_of: str,
    window_days: int = 30,
) -> ExtractedSignal:
    """Median gap (days) between confirmed events in the trailing
    *window_days*, vs. the equally-sized prior window. Positive = cadence
    widening (meetings further apart); ``cancelled`` events are excluded
    from the confirmed set but still counted as "a meeting was scheduled
    and didn't happen" via a lower confirmed-count, not fabricated as
    attended.
    """

    as_of_d = _iso(as_of)
    confirmed_days = sorted(
        (datetime.fromisoformat(item["start"]["dateTime"].replace("Z", "+00:00")).date())
        for item in calendar_events["items"]
        if item["status"] == "confirmed"
    )
    confirmed_days = [d for d in confirmed_days if d <= as_of_d]

    def _median_gap(days: list[date]) -> float | None:
        gaps = [(b - a).days for a, b in zip(days, days[1:])]
        if not gaps:
            return None
        gaps.sort()
        mid = len(gaps) // 2
        if len(gaps) % 2:
            return float(gaps[mid])
        return (gaps[mid - 1] + gaps[mid]) / 2.0

    recent = [d for d in confirmed_days if (as_of_d - d).days <= window_days]
    prior = [d for d in confirmed_days if window_days < (as_of_d - d).days <= 2 * window_days]
    recent_gap = _median_gap(recent)
    prior_gap = _median_gap(prior)
    if recent_gap is None or prior_gap is None:
        return ExtractedSignal(
            account_id=account_id,
            metric_name="meeting_cadence_shift_days",
            value=None,
            unit="days_delta",
            as_of=as_of,
            evidence=(),
            detail="insufficient confirmed-event history in one or both windows",
        )
    delta = round(recent_gap - prior_gap, 1)
    evidence = tuple(
        SignalEvidence(
            "communications",
            item["id"],
            "status",
            item["start"]["dateTime"],
        )
        for item in calendar_events["items"]
        if item["status"] == "confirmed" and datetime.fromisoformat(
            item["start"]["dateTime"].replace("Z", "+00:00")
        ).date() <= as_of_d
    )
    return ExtractedSignal(
        account_id=account_id,
        metric_name="meeting_cadence_shift_days",
        value=delta,
        unit="days_delta",
        as_of=as_of,
        evidence=evidence,
        detail=f"trailing {window_days}d median gap {recent_gap:.1f}d vs prior window {prior_gap:.1f}d",
    )


def ticket_frequency_window(
    account_id: str,
    cases: list[CRMCase],
    *,
    as_of: str,
    window_days: int = 90,
) -> ExtractedSignal:
    """Count of cases opened in the trailing *window_days* ending at
    *as_of*, grouped implicitly by being on the same account (topic-level
    grouping is left to the caller via ``subject``/``origin`` -- this
    signal answers "how much support pressure," not "about what").
    """

    as_of_d = _iso(as_of)
    in_window = [
        c
        for c in cases
        if c.account_id == account_id and 0 <= (as_of_d - _iso(c.created_at)).days <= window_days
    ]
    evidence = tuple(
        SignalEvidence("crm", c.case_id, "created_at", c.created_at) for c in in_window
    )
    return ExtractedSignal(
        account_id=account_id,
        metric_name="ticket_frequency_window",
        value=float(len(in_window)),
        unit="cases_opened",
        as_of=as_of,
        evidence=evidence,
        detail=f"{len(in_window)} case(s) opened in trailing {window_days}d as of {as_of}",
    )
