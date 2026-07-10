"""Minimal additive persistence for "rejected with reason, don't re-propose".

Universe v2 Wave 1 (WS-Week1-Harness) finding: the existing gate machinery
(``ultra_csm.governance.gate.ActionGate.record_verdict``) records a ``deny``
verdict as a terminal ``action_proposal`` status, but nothing consults that
history when the next sweep runs -- a denied recurring-eligible proposal for
the same account/factor/motion simply reappears unchanged the next day. This
module is the smallest fix: a flat, config-shaped rejection ledger (state,
not a hard-coded rule) that the harness (and, if adopted later, the tick
runner) consults before treating a freshly swept work item as a *new*
recurrence of something a human already said no to.

This is deliberately not a database table and does not touch
``ActionGate``/``action_proposal``/``action_verdict``: it is a parallel,
file-backed ledger scoped to the (tenant, account, factor, motion) triple a
human rejected, so the day-K+1 sweep can recognize "this is the same ask
again" without any change to the governance schema. Recurring proposals are
matched on ``(tenant_id, account_id, factor_name, motion)`` -- the three
things the megaprompt calls "same account, same factor, same motion".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RejectionRecord:
    """One human rejection of a recurring-eligible proposal."""

    tenant_id: str
    account_id: str
    factor_name: str
    motion: str
    reason: str
    rejected_on_day: int
    proposal_id: str

    def key(self) -> tuple[str, str, str, str]:
        return (self.tenant_id, self.account_id, self.factor_name, self.motion)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "account_id": self.account_id,
            "factor_name": self.factor_name,
            "motion": self.motion,
            "reason": self.reason,
            "rejected_on_day": self.rejected_on_day,
            "proposal_id": self.proposal_id,
        }


class RejectionLedger:
    """Append-only, JSON-file-backed rejection ledger.

    Config/state, not code: a rule like "never re-propose an escalation for
    pinnacle-supply's reply_latency_trend factor" lives as a row in this
    file, never as an if-branch in the sweep. ``recurs_unchanged`` is the
    predicate the harness's feedback-persistence check applies: a proposal
    recurs unchanged only if its (account, factor, motion) key matches a
    rejection AND its evidence/motion payload is byte-identical to what was
    rejected; a changed motion or changed evidence is a legitimate new ask.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._records: list[RejectionRecord] = []
        if self.path is not None and self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._records = [RejectionRecord(**row) for row in raw.get("rejections", [])]

    def reject(
        self,
        *,
        tenant_id: str,
        account_id: str,
        factor_name: str,
        motion: str,
        reason: str,
        rejected_on_day: int,
        proposal_id: str,
    ) -> RejectionRecord:
        record = RejectionRecord(
            tenant_id=tenant_id,
            account_id=account_id,
            factor_name=factor_name,
            motion=motion,
            reason=reason,
            rejected_on_day=rejected_on_day,
            proposal_id=proposal_id,
        )
        self._records.append(record)
        self._flush()
        return record

    def lookup(
        self, *, tenant_id: str, account_id: str, factor_name: str, motion: str
    ) -> RejectionRecord | None:
        key = (tenant_id, account_id, factor_name, motion)
        for record in reversed(self._records):
            if record.key() == key:
                return record
        return None

    def all_records(self) -> tuple[RejectionRecord, ...]:
        return tuple(self._records)

    def _flush(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"rejections": [r.to_dict() for r in self._records]}
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def top_factor_name(factors: tuple[Any, ...]) -> str | None:
    """The dominant factor name for a work item's priority, matching the
    same-account/same-factor/same-motion recurrence key. ``factors`` is a
    ``Priority.factors`` tuple of ``ValueFactor``-shaped objects (each has a
    ``.name`` and a ``.contribution``); factors are not emitted in
    contribution order (``project_ttv_lens`` concatenates base factors and
    ``model.ttv_factors`` in a fixed construction order, not sorted), so the
    dominant factor is the max by ``contribution``, ties broken by name for
    determinism."""

    if not factors:
        return None
    best_contribution = max(f.contribution for f in factors)
    tied = sorted(f.name for f in factors if f.contribution == best_contribution)
    return tied[0]


def recurring_rejection_reasons(
    records: tuple[RejectionRecord, ...] | list[RejectionRecord],
    *,
    min_count: int = 2,
) -> tuple[tuple[str, int], ...]:
    """Return repeated rejection reasons for factor-discovery review.

    This is deliberately descriptive, not autonomous behavior: recurring
    reasons are candidates for later archetype/factor work, not proof that the
    product should change or that a recommendation was wrong.
    """

    counts: dict[str, int] = {}
    for record in records:
        reason = record.reason.strip()
        if not reason:
            continue
        counts[reason] = counts.get(reason, 0) + 1
    return tuple(
        sorted(
            (
                (reason, count)
                for reason, count in counts.items()
                if count >= min_count
            ),
            key=lambda item: (-item[1], item[0]),
        )
    )
