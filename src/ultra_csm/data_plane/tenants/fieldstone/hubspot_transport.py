"""Fake HubSpot-shaped CRM transport for fieldstone (Universe v2,
WS-Tenant-Fieldstone, Wave 3). Mirrors
``eval.attio_simulated_onboarding.FakeAttioClient``'s pattern: an
in-memory fake client built from the fieldstone book, used against the
real ``ultra_csm.data_plane.explorer.run_explorer`` machinery.

HubSpot-shaped wire conventions this module follows (real API shapes,
never an invented schema):
- objects carry a ``properties`` map (``{"properties": {...}}``), not flat
  fields;
- ``lifecyclestage`` is a real HubSpot company/contact property;
- ids are HubSpot-style numeric-string ids (``"101"``, ``"5001"``, ...),
  not UUIDs;
- contacts/companies are linked via ASSOCIATIONS
  (``/crm/v4/associations/...``), never a lookup field on the contact
  record itself -- this is the whole point of the Tier-A pluggability
  test (see ``explorer.py``'s ``_parse_hubspot_associations_schema``).
"""

from __future__ import annotations

import json
from typing import Any

from ultra_csm.data_plane.live_smoke import HttpRequest, HttpResponse
from ultra_csm.data_plane.tenants.fieldstone.book import (
    ACCOUNT_SLUGS,
    FieldstoneCustomerData,
    account_id_for,
    arr_cents_for,
    build_fieldstone_book,
    tier_for,
)

BASE_URL = "https://api.hubapi.com"


def _hubspot_company_id(slug: str) -> str:
    """HubSpot-style short numeric-string id, deterministic from the
    account's index in the book (not a UUID -- HubSpot's real ids are
    small integers)."""

    return str(100 + ACCOUNT_SLUGS.index(slug))


def _hubspot_contact_id(slug: str) -> str:
    return str(5000 + ACCOUNT_SLUGS.index(slug))


class FakeHubSpotClient:
    """In-memory HubSpot-shaped transport for the connector explorer."""

    def __init__(self, payloads: dict[str, Any]) -> None:
        self.payloads = payloads
        self.requests: list[HttpRequest] = []

    def send(self, req: HttpRequest) -> HttpResponse:
        self.requests.append(req)
        payload = self._payload_for(req)
        status = 200 if payload is not None else 404
        return HttpResponse(
            status=status,
            body=json.dumps(payload or {}, sort_keys=True).encode("utf-8"),
            headers={"content-type": "application/json"},
        )

    def _payload_for(self, req: HttpRequest) -> dict[str, Any] | None:
        if req.url == f"{BASE_URL}/crm/v3/properties/companies":
            return self.payloads["company_properties"]
        if req.url == f"{BASE_URL}/crm/v3/properties/contacts":
            return self.payloads["contact_properties"]
        if req.url == f"{BASE_URL}/crm/v4/associations/contacts/companies/labels":
            return self.payloads["contact_company_associations_schema"]
        return None


def build_hubspot_fixture_payloads(book: FieldstoneCustomerData) -> dict[str, Any]:
    company_records = [_company_record(account) for account in book.accounts]
    contact_records = [_contact_record(contact) for contact in book.contacts]
    return {
        "company_properties": {"results": _company_properties()},
        "contact_properties": {"results": _contact_properties()},
        "contact_company_associations_schema": {
            "results": [
                {"category": "HUBSPOT_DEFINED", "typeId": 1, "label": "Primary"},
            ]
        },
        "company_records": company_records,
        "contact_records": contact_records,
        "associations": _associations(book),
    }


def _company_properties() -> list[dict[str, Any]]:
    return [
        {"name": "name", "type": "string", "hubspotDefined": True},
        {"name": "lifecyclestage", "type": "enumeration", "hubspotDefined": True},
        {"name": "annualrevenue", "type": "number", "hubspotDefined": True},
        {"name": "fieldstone_service_tier", "type": "string", "hubspotDefined": False},
    ]


def _contact_properties() -> list[dict[str, Any]]:
    return [
        {"name": "email", "type": "string", "hubspotDefined": True},
        {"name": "firstname", "type": "string", "hubspotDefined": True},
        {"name": "lastname", "type": "string", "hubspotDefined": True},
        {"name": "jobtitle", "type": "string", "hubspotDefined": True},
    ]


def _company_record(account) -> dict[str, Any]:  # noqa: ANN001 - dataclass-shaped fixture
    slug = _slug_for_account(account.account_id)
    return {
        "id": _hubspot_company_id(slug),
        "properties": {
            "name": account.name,
            "lifecyclestage": "customer",
            "annualrevenue": str(arr_cents_for(slug) / 100.0),
            "fieldstone_service_tier": tier_for(slug),
        },
    }


def _contact_record(contact) -> dict[str, Any]:  # noqa: ANN001 - dataclass-shaped fixture
    name_parts = contact.name.split(" ", 1)
    first = name_parts[0]
    last = name_parts[1] if len(name_parts) > 1 else ""
    slug = _slug_for_account(contact.account_id)
    return {
        "id": _hubspot_contact_id(slug),
        "properties": {
            "email": contact.email,
            "firstname": first,
            "lastname": last,
            "jobtitle": contact.title,
        },
    }


def _associations(book: FieldstoneCustomerData) -> list[dict[str, Any]]:
    """HubSpot-shaped association records: ``{fromObjectId, toObjectId,
    associationType}`` -- NOT a lookup field on the contact record. This
    is the wire-level proof of the "associations, not lookup fields"
    requirement: a contact's link to its company lives entirely in this
    separate list, never as a field on the contact properties map above.
    """

    out = []
    for contact in book.contacts:
        slug = _slug_for_account(contact.account_id)
        out.append({
            "fromObjectType": "contacts",
            "fromObjectId": _hubspot_contact_id(slug),
            "toObjectType": "companies",
            "toObjectId": _hubspot_company_id(slug),
            "associationType": "contact_to_company",
        })
    return out


def _slug_for_account(account_id: str) -> str:
    for slug in ACCOUNT_SLUGS:
        if account_id_for(slug) == account_id:
            return slug
    raise KeyError(f"unknown fieldstone account_id: {account_id}")


def fieldstone_hubspot_payloads() -> dict[str, Any]:
    return build_hubspot_fixture_payloads(build_fieldstone_book())
