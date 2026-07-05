"""Person-derived account factors (Harvest 16).

Wires the dormant person layer -- ``StakeholderRelationship``
(``data_plane/contracts.py:253``) and ``JobChangeSignal``
(``data_plane/relationship_signals.py``) -- into the live value model as
ADDITIVE, deterministic account-level :class:`~ultra_csm.value_model.ValueFactor`
instances. The unit of action stays the account: these are account factors
that happen to be derived from person records, never a person-level health
score or queue item (ADR-005: no LLM inference of roles/org-structure --
every factor here is a plain deterministic read of CRM + observed data).

Four factors, RISK lens (first three) / ADOPTION lens (fourth) --
see docs/PROGRAM_REPORT_32.md for the LENS_ARCHITECTURE mapping:

* :func:`champion_departed_factor`
* :func:`single_threaded_from_graph_factor` (replaces the telemetry-proxy
  INPUT to ``value_model._single_threaded_risk`` only when graph data is
  available; the proxy remains the fallback -- see that function's
  docstring for the zero-drift argument).
* :func:`new_stakeholder_unengaged_factor`
* :func:`usage_concentration_factor` (the promoted concentration helper
  also used by ``value_model_bridge.py``, so there is one computation, not
  two -- see :func:`top_user_share`).
"""

from __future__ import annotations

from ultra_csm.data_plane.contracts import CommunicationSignal, EvidenceRef, StakeholderRelationship
from ultra_csm.data_plane.relationship_signals import JobChangeSignal

# Person-record evidence is filed under the "crm" source: StakeholderRelationship
# and JobChangeSignal are both Salesforce/enrichment-adjacent contact records,
# and EvidenceSource (contracts.py:28) is a closed Literal with no "enrichment"
# member -- widening it is out of this dispatch's sanctioned scope.
_PERSON_EVIDENCE_SOURCE = "crm"

ENGAGED_ROLES = ("champion", "executive_sponsor", "technical_lead", "admin", "end_user")


def top_user_share(totals: dict[str, float]) -> float | None:
    """The promoted concentration computation: top contributor's share of
    total activity. Shared by the sweep-path value model
    (:func:`ultra_csm.value_model._single_threaded_risk`) and
    :func:`ultra_csm.value_model_bridge.build_deep_value_model` so there is
    one concentration implementation, not two parallel copies (the
    motion-wiring lesson this dispatch's Reading list names).

    Returns ``None`` when there is no activity to rank (total <= 0).
    """

    total = sum(totals.values())
    if total <= 0:
        return None
    return max(totals.values()) / total


def champion_departed(
    stakeholders: tuple[StakeholderRelationship, ...],
    job_changes: tuple[JobChangeSignal, ...],
    *,
    as_of: str,
    window_days: int,
) -> tuple[JobChangeSignal, StakeholderRelationship] | None:
    """A ``JobChangeSignal`` departure for a contact whose
    ``StakeholderRelationship.relationship_type == "champion"`` on the same
    account, observed within *window_days* of *as_of* (both RFC3339/ISO date
    strings -- compared as dates, not raw fixture day-offsets, so this holds
    for any tenant's data, not just the synthetic book's SEED_DATE). Returns
    the (departure, stakeholder-role) evidence pair for the caller to cite,
    or ``None`` if no such pair exists.
    """

    from ultra_csm._util import iso_date

    champion_contact_ids = {
        s.contact_id for s in stakeholders if s.relationship_type == "champion"
    }
    if not champion_contact_ids:
        return None
    as_of_date = iso_date(as_of)
    for change in job_changes:
        if change.change_type != "departure":
            continue
        if change.contact_id not in champion_contact_ids:
            continue
        observed_date = iso_date(change.observed_at)
        if observed_date > as_of_date:
            continue
        if (as_of_date - observed_date).days > window_days:
            continue
        role = next(
            s for s in stakeholders
            if s.contact_id == change.contact_id and s.relationship_type == "champion"
        )
        return (change, role)
    return None


def engaged_contact_count(
    stakeholders: tuple[StakeholderRelationship, ...],
    *,
    as_of: str,
    recency_days: int,
) -> tuple[int, tuple[StakeholderRelationship, ...]]:
    """Count of distinct contacts with a ``StakeholderRelationship`` whose
    ``last_interaction`` falls within *recency_days* of *as_of* -- the real
    person-graph width, replacing the telemetry-usage-signal proxy count.
    Returns the count and the engaged rows (for evidence).
    """

    from ultra_csm._util import iso_date

    as_of_date = iso_date(as_of)
    engaged: list[StakeholderRelationship] = []
    seen_contacts: set[str] = set()
    for s in stakeholders:
        if s.contact_id in seen_contacts:
            continue
        age = (as_of_date - iso_date(s.last_interaction)).days
        if 0 <= age <= recency_days:
            engaged.append(s)
            seen_contacts.add(s.contact_id)
    return len(engaged), tuple(engaged)


def new_stakeholder_unengaged(
    stakeholders: tuple[StakeholderRelationship, ...],
    comms: tuple[CommunicationSignal, ...],
    *,
    as_of: str,
    window_days: int,
) -> StakeholderRelationship | None:
    """A ``StakeholderRelationship`` of role admin/executive_sponsor whose
    only observed activity (``last_interaction``) is within *window_days* of
    *as_of* (i.e. newly appeared) and has no matching ``CommunicationSignal``
    -- a stakeholder the CRM knows about but who has never actually engaged.
    Returns the stakeholder row, or ``None``.
    """

    from ultra_csm._util import iso_date

    as_of_date = iso_date(as_of)
    commed_contact_ids = {c.contact_id for c in comms}
    for s in stakeholders:
        if s.relationship_type not in ("admin", "executive_sponsor"):
            continue
        age = (as_of_date - iso_date(s.last_interaction)).days
        if age < 0 or age > window_days:
            continue
        if s.contact_id in commed_contact_ids:
            continue
        return s
    return None


def evidence_for_champion_departed(
    change: JobChangeSignal, role: StakeholderRelationship
) -> tuple[EvidenceRef, ...]:
    return (
        EvidenceRef(_PERSON_EVIDENCE_SOURCE, change.signal_id, "change_type", change.observed_at),
        EvidenceRef(_PERSON_EVIDENCE_SOURCE, role.contact_id, "relationship_type", role.last_interaction),
    )


def evidence_for_single_threaded_graph(
    engaged: tuple[StakeholderRelationship, ...],
) -> tuple[EvidenceRef, ...]:
    return tuple(
        EvidenceRef(_PERSON_EVIDENCE_SOURCE, s.contact_id, "last_interaction", s.last_interaction)
        for s in engaged
    )


def evidence_for_new_stakeholder_unengaged(s: StakeholderRelationship) -> tuple[EvidenceRef, ...]:
    return (
        EvidenceRef(_PERSON_EVIDENCE_SOURCE, s.contact_id, "relationship_type", s.last_interaction),
    )
