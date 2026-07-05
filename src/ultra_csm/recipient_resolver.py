"""Deterministic recipient resolution from the role graph (Harvest 16).

Mirrors ``motion_resolver.py``'s shape: a tenant-agnostic pure function
callers reach with already-resolved inputs (here, a motion and the
account's ``StakeholderRelationship`` rows), no side effects, no LLM
inference of roles (ADR-005 -- every mapping below is a plain lookup on
``StakeholderRelationship.relationship_type``, a field a real CRM sync
populates deterministically).

Replaces the sweep's previous ``first-consenting-contact`` pick
(``agent1/sweep.py``, formerly at the ``_work_item_for_account`` recipient
line) with a role-graph-driven, per-motion mapping. Falls back to the
original first-consenting behavior whenever the role graph can't resolve
someone eligible -- no regression versus pre-Harvest-16 behavior.
"""

from __future__ import annotations

from ultra_csm.data_plane.contracts import CRMContact, StakeholderRelationship

# Motion -> eligible StakeholderRelationship.relationship_type(s), in
# priority order (first eligible+consenting role wins). Per dispatch
# Decisions (ratified, not re-litigated here): working_session/qbr ->
# champion or executive_sponsor; escalation -> executive_sponsor;
# personal_email -> champion else primary (primary = no specific role
# requirement, any consenting contact, i.e. the fallback). content_route's
# ratified mapping is "the entitled end_users (may be many -- the
# person-cohort case)" -- CSMWorkItem (agent1/sweep.py) has no
# multi-recipient slot, so :func:`resolve_recipient` (wired into the
# sweep's single-contact slot) treats content_route as end_user-priority
# single-pick; :func:`resolve_content_route_recipients` implements the full
# cohort mapping and is ready to wire in once/if CSMWorkItem gains a
# multi-recipient slot (recorded as an Owner Ask in docs/PROGRAM_REPORT_32.md
# -- out of this dispatch's scope, which replaces the existing single pick,
# not CSMWorkItem's shape). campaign_enroll/cohort_action are not named in
# the dispatch's mapping; both fall through to the first-consenting
# fallback (recorded as an IF/THEN, not invented).
_SINGLE_RECIPIENT_ROLE_PRIORITY: dict[str, tuple[str, ...]] = {
    "working_session": ("champion", "executive_sponsor"),
    "qbr": ("champion", "executive_sponsor"),
    "escalation": ("executive_sponsor",),
    "personal_email": ("champion",),
    "content_route": ("end_user",),
}

CONTENT_ROUTE_ROLE = "end_user"


def _consenting_contact_by_id(
    contacts: tuple[CRMContact, ...],
) -> dict[str, CRMContact]:
    return {c.contact_id: c for c in contacts if c.consent_to_contact}


def _first_consenting_fallback(contacts: tuple[CRMContact, ...]) -> CRMContact | None:
    """The pre-Harvest-16 behavior, preserved verbatim as the fallback path
    (dispatch Decisions: "FALL BACK to the current first-consenting
    behavior (no regression)")."""

    return next((c for c in contacts if c.consent_to_contact), None)


def resolve_recipient(
    motion: str | None,
    stakeholders: tuple[StakeholderRelationship, ...],
    contacts: tuple[CRMContact, ...],
) -> tuple[CRMContact | None, str]:
    """Resolve the single-recipient case (all motions except
    ``content_route``). Returns ``(contact, resolution)`` where
    ``resolution`` is ``"role_graph"`` when a role-eligible consenting
    contact was found, or ``"first_consenting_fallback"`` when the graph
    couldn't resolve one (no stakeholder data, no role match, or the
    role-matched contact hasn't consented) -- callers should record which
    path fired (dispatch: "record it").
    """

    consenting_by_id = _consenting_contact_by_id(contacts)
    role_priority = _SINGLE_RECIPIENT_ROLE_PRIORITY.get(motion or "", ())
    for role in role_priority:
        for s in stakeholders:
            if s.relationship_type != role:
                continue
            contact = consenting_by_id.get(s.contact_id)
            if contact is not None:
                return contact, "role_graph"
    fallback = _first_consenting_fallback(contacts)
    return fallback, "first_consenting_fallback"


def resolve_content_route_recipients(
    stakeholders: tuple[StakeholderRelationship, ...],
    contacts: tuple[CRMContact, ...],
) -> tuple[tuple[CRMContact, ...], str]:
    """``content_route``'s person-cohort case: every consenting
    ``end_user``-role contact (may be zero, one, or many). Returns
    ``(contacts, resolution)`` -- falls back to the single first-consenting
    contact (as a one-tuple) when no end_user role is on the graph, same
    no-regression contract as :func:`resolve_recipient`.
    """

    consenting_by_id = _consenting_contact_by_id(contacts)
    end_users = tuple(
        consenting_by_id[s.contact_id]
        for s in stakeholders
        if s.relationship_type == CONTENT_ROUTE_ROLE and s.contact_id in consenting_by_id
    )
    if end_users:
        return end_users, "role_graph"
    fallback = _first_consenting_fallback(contacts)
    return ((fallback,) if fallback is not None else ()), "first_consenting_fallback"
