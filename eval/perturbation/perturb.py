"""Perturbation library (Universe v2, WS-Perturbation-Drift, Wave 4).

Five pure functions, one per D7-reserved axis
(``docs/UNIVERSE_V2_CONVENTIONS.md`` section 6: ``latency_scale``,
``volume_scale``, ``hygiene_drop_pct``, ``schema_rename_map``,
``arr_shift_pct``). Every function takes a tuple/list of fixture rows and
returns a PERTURBED COPY -- none mutate their input, none touch the base
book cache (``narrative_shared.base_synthetic_book`` and its per-tenant
equivalents), and none require ``random`` or wall-clock time: every
"random-seeming" choice (which field to null, which offset to add a
filler exchange at) is a deterministic function of ``det_id`` ordering
over the input's own ids, so two calls with the same input always
produce byte-identical output.

Hand-authored tenants catch judgment failures; this library exists to
catch CALIBRATION failures -- thresholds/assumptions that only held
because every tenant's numbers happened to sit where the bible authors
put them.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from ultra_csm.data_plane.contracts import CommunicationSignal, CRMContact, CSCompany
from ultra_csm.data_plane.fixtures import det_id


def latency_scale(
    signals: tuple[CommunicationSignal, ...], k: float
) -> tuple[CommunicationSignal, ...]:
    """Scale every inbound reply's ``response_time_hours`` by *k*. Both the
    "recent" and "prior" trailing windows scale together (this is what a
    tenant-wide, uniform latency shift looks like), so a correctly-built
    trend delta should read approximately unchanged after this
    perturbation -- an absolute-hours threshold hiding anywhere would
    instead see BOTH windows cross it and (wrongly) fire.

    Outbound signals (no ``response_time_hours``) and timestamps are left
    untouched -- day-boundary/window-membership integrity is exactly what
    the accompanying battery's "windowed application" cell needs held
    fixed while only the *magnitude* changes.
    """

    return tuple(
        replace(s, response_time_hours=round(s.response_time_hours * k, 2))
        if s.response_time_hours is not None
        else s
        for s in signals
    )


def latency_scale_recent_window(
    signals: tuple[CommunicationSignal, ...], k: float, *, as_of_days_ago_cutoff: int, now_days: int
) -> tuple[CommunicationSignal, ...]:
    """Scale ``response_time_hours`` by *k* only for signals whose
    timestamp falls within the trailing ``as_of_days_ago_cutoff`` days of
    ``now_days`` (days since epoch, caller-supplied so this stays a pure
    function of its inputs, never wall-clock ``now()``). This is the
    "recent window only" cell the battery uses to prove delta-detection
    still fires when a shift is real and localized, as opposed to
    :func:`latency_scale`'s tenant-wide shift where every window moves
    together and nothing should fire.
    """

    from datetime import date

    def _day_offset(ts: str) -> int:
        return (date.fromisoformat(ts[:10]) - date(1970, 1, 1)).days

    cutoff_day = now_days - as_of_days_ago_cutoff
    out = []
    for s in signals:
        if s.response_time_hours is None or _day_offset(s.timestamp) < cutoff_day:
            out.append(s)
        else:
            out.append(replace(s, response_time_hours=round(s.response_time_hours * k, 2)))
    return tuple(out)


def volume_scale(
    signals: tuple[CommunicationSignal, ...],
    k: float,
    *,
    protected_signal_ids: frozenset[str] = frozenset(),
    account_id: str = "",
) -> tuple[CommunicationSignal, ...]:
    """Duplicate/thin comms volume by *k*, never touching a
    ``protected_signal_ids`` member (bible-checkpoint-bearing evidence).

    ``k > 1``: adds ``round((k - 1) * len(signals))`` deterministic benign
    filler exchanges -- synthetic outbound/inbound pairs with generated
    ids and a fixed 2h response time, inserted at deterministic offsets
    (interleaved by rank, never appended in a block that would shift
    window boundaries all at once).

    ``k < 1``: drops every Nth non-protected signal, where
    ``N = round(1 / (1 - k))``, ranked by a stable ``det_id``-derived
    order (never by original list position, so the drop set doesn't
    silently correlate with insertion order).
    """

    if k >= 1.0:
        filler_count = round((k - 1.0) * len(signals))
        fillers = []
        for i in range(filler_count):
            filler_id = det_id("perturb-volume-filler", account_id, i)
            fillers.append(
                CommunicationSignal(
                    signal_id=filler_id,
                    account_id=account_id,
                    contact_id=det_id("perturb-volume-filler-contact", account_id, i),
                    channel="email",
                    direction="inbound",
                    timestamp=signals[0].timestamp if signals else "2026-06-21T00:00:00Z",
                    response_time_hours=2.0,
                )
            )
        # Interleave fillers evenly among the real signals (rank-based,
        # deterministic) rather than appending them all at the end.
        merged = list(signals)
        step = max(1, len(merged) // max(1, filler_count)) if filler_count else 0
        for i, filler in enumerate(fillers):
            insert_at = min(len(merged), (i + 1) * step)
            merged.insert(insert_at, filler)
        return tuple(merged)

    drop_fraction = 1.0 - k
    if drop_fraction <= 0:
        return signals
    n = max(1, round(1.0 / drop_fraction))
    ranked = sorted(
        range(len(signals)), key=lambda i: det_id("perturb-volume-rank", account_id, signals[i].signal_id)
    )
    drop_ranks = {r for idx, r in enumerate(ranked) if idx % n == 0}
    kept = [
        s
        for i, s in enumerate(signals)
        if s.signal_id in protected_signal_ids or i not in drop_ranks
    ]
    return tuple(kept)


def hygiene_drop(contacts: tuple[CRMContact, ...], pct: float) -> tuple[CRMContact, ...]:
    """Null out *pct* fraction of each contact's OPTIONAL fields (``role``,
    ``title``, ``org_level`` -- never ``contact_id``/``account_id``/
    ``email``/``name``/``consent_to_contact``, which are never optional in
    the contract). Selection is deterministic: contacts are ranked by
    ``det_id``, and the first ``round(pct * len(contacts))`` in that rank
    order get their optional fields nulled.
    """

    if not contacts:
        return contacts
    ranked = sorted(range(len(contacts)), key=lambda i: det_id("perturb-hygiene-rank", contacts[i].contact_id))
    drop_count = round(pct * len(contacts))
    drop_indices = set(ranked[:drop_count])
    return tuple(
        replace(c, role=None, title=None, org_level=None) if i in drop_indices else c
        for i, c in enumerate(contacts)
    )


def schema_rename(records: list[dict[str, Any]], rename_map: dict[str, str]) -> list[dict[str, Any]]:
    """Rename source-table columns before the mapping layer sees them --
    ``rename_map`` is ``{old_key: new_key}``. A key not in ``rename_map``
    passes through unchanged. Never mutates the input records."""

    return [
        {rename_map.get(key, key): value for key, value in record.items()}
        for record in records
    ]


def arr_shift(companies: tuple[CSCompany, ...], pct: float) -> tuple[CSCompany, ...]:
    """Scale every company's ``arr_cents`` by ``(1 + pct)`` (``pct`` may be
    negative, e.g. ``-0.6`` for a 60% cut). Rounds to the nearest cent."""

    return tuple(replace(c, arr_cents=round(c.arr_cents * (1.0 + pct))) for c in companies)
