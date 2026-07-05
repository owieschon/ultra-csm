"""Recipient resolver tests (Harvest 16)."""

from __future__ import annotations

from ultra_csm.data_plane.contracts import CRMContact, StakeholderRelationship
from ultra_csm.recipient_resolver import resolve_content_route_recipients, resolve_recipient

_ACCOUNT_ID = "acct-1"


def _contact(contact_id: str, *, consent: bool = True) -> CRMContact:
    return CRMContact(
        contact_id=contact_id,
        account_id=_ACCOUNT_ID,
        email=f"{contact_id}@example.com",
        name=contact_id,
        role="operations",
        title="Manager",
        consent_to_contact=consent,
    )


def _stakeholder(contact_id: str, relationship_type: str) -> StakeholderRelationship:
    return StakeholderRelationship(
        account_id=_ACCOUNT_ID,
        contact_id=contact_id,
        relationship_type=relationship_type,  # type: ignore[arg-type]
        strength="strong",
        last_interaction="2026-06-21T00:00:00Z",
        multi_thread_depth=1,
    )


def test_working_session_prefers_champion():
    champion = _contact("champion-1")
    admin = _contact("admin-1")
    stakeholders = (_stakeholder("champion-1", "champion"), _stakeholder("admin-1", "admin"))
    contact, resolution = resolve_recipient("working_session", stakeholders, (admin, champion))
    assert contact is champion
    assert resolution == "role_graph"


def test_working_session_falls_back_to_executive_sponsor_when_no_champion():
    sponsor = _contact("sponsor-1")
    stakeholders = (_stakeholder("sponsor-1", "executive_sponsor"),)
    contact, resolution = resolve_recipient("working_session", stakeholders, (sponsor,))
    assert contact is sponsor
    assert resolution == "role_graph"


def test_qbr_prefers_champion_over_executive_sponsor():
    champion = _contact("champion-1")
    sponsor = _contact("sponsor-1")
    stakeholders = (_stakeholder("sponsor-1", "executive_sponsor"), _stakeholder("champion-1", "champion"))
    contact, resolution = resolve_recipient("qbr", stakeholders, (sponsor, champion))
    assert contact is champion
    assert resolution == "role_graph"


def test_escalation_resolves_executive_sponsor_only():
    champion = _contact("champion-1")
    sponsor = _contact("sponsor-1")
    stakeholders = (_stakeholder("champion-1", "champion"), _stakeholder("sponsor-1", "executive_sponsor"))
    contact, resolution = resolve_recipient("escalation", stakeholders, (champion, sponsor))
    assert contact is sponsor
    assert resolution == "role_graph"


def test_personal_email_prefers_champion_else_primary():
    champion = _contact("champion-1")
    other = _contact("other-1")
    stakeholders = (_stakeholder("champion-1", "champion"),)
    contact, resolution = resolve_recipient("personal_email", stakeholders, (other, champion))
    assert contact is champion
    assert resolution == "role_graph"


def test_content_route_resolves_end_user_single_pick():
    end_user = _contact("eu-1")
    other = _contact("other-1")
    stakeholders = (_stakeholder("eu-1", "end_user"),)
    contact, resolution = resolve_recipient("content_route", stakeholders, (other, end_user))
    assert contact is end_user
    assert resolution == "role_graph"


def test_content_route_cohort_returns_all_consenting_end_users():
    eu1 = _contact("eu-1")
    eu2 = _contact("eu-2")
    stakeholders = (_stakeholder("eu-1", "end_user"), _stakeholder("eu-2", "end_user"))
    contacts, resolution = resolve_content_route_recipients(stakeholders, (eu1, eu2))
    assert set(contacts) == {eu1, eu2}
    assert resolution == "role_graph"


def test_fallback_to_first_consenting_when_no_stakeholders():
    primary = _contact("primary-1")
    contact, resolution = resolve_recipient("working_session", (), (primary,))
    assert contact is primary
    assert resolution == "first_consenting_fallback"


def test_fallback_to_first_consenting_when_role_matched_contact_has_not_consented():
    non_consenting_champion = _contact("champion-1", consent=False)
    fallback_contact = _contact("other-1")
    stakeholders = (_stakeholder("champion-1", "champion"),)
    contact, resolution = resolve_recipient(
        "personal_email", stakeholders, (non_consenting_champion, fallback_contact)
    )
    assert contact is fallback_contact
    assert resolution == "first_consenting_fallback"


def test_fallback_for_unmapped_motion():
    primary = _contact("primary-1")
    stakeholders = (_stakeholder("someone", "champion"),)
    contact, resolution = resolve_recipient("campaign_enroll", stakeholders, (primary,))
    assert contact is primary
    assert resolution == "first_consenting_fallback"


def test_fallback_when_motion_is_none():
    primary = _contact("primary-1")
    contact, resolution = resolve_recipient(None, (), (primary,))
    assert contact is primary
    assert resolution == "first_consenting_fallback"


def test_no_eligible_and_no_fallback_returns_none():
    contact, resolution = resolve_recipient("working_session", (), ())
    assert contact is None
    assert resolution == "first_consenting_fallback"


def test_content_route_cohort_falls_back_when_no_end_user_role():
    primary = _contact("primary-1")
    contacts, resolution = resolve_content_route_recipients((), (primary,))
    assert contacts == (primary,)
    assert resolution == "first_consenting_fallback"
