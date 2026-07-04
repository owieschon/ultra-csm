"""Fake Attio-shaped CRM transport for Loopway (Universe v2,
WS-Tenant-Loopway, Wave 3).

Same in-memory transport pattern as
``eval/attio_simulated_onboarding.py``'s ``FakeAttioClient`` (the repo's
existing Attio-shaped simulated-vertical lane, see
``docs/UNIVERSE_V2_CONVENTIONS.md`` §1) -- objects/records/attributes
lists, Attio-style ids -- built here against Loopway's own 400-account
book instead of fleetops'. Serves companies/people only (Loopway has no
opportunities/cases in its CRM shape -- see the bible: campaigns and chat
carry the signal this tenant needs, not a Salesforce-shaped case/opp
pipeline).
"""

from __future__ import annotations

import json
from typing import Any

from ultra_csm.data_plane.fixtures import FixtureCustomerData
from ultra_csm.data_plane.live_smoke import HttpRequest, HttpResponse

BASE_URL = "https://api.attio.com"


class FakeLoopwayAttioClient:
    """In-memory Attio-shaped transport for the connector explorer, serving
    Loopway's 400-account book."""

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
        if req.url == f"{BASE_URL}/v2/self":
            return self.payloads["self"]
        if req.url == f"{BASE_URL}/v2/objects":
            return self.payloads["objects"]
        if req.url == f"{BASE_URL}/v2/objects/companies/attributes":
            return self.payloads["companies_attributes"]
        if req.url == f"{BASE_URL}/v2/objects/people/attributes":
            return self.payloads["people_attributes"]
        if req.url == f"{BASE_URL}/v2/objects/companies/records/query":
            return {"data": self.payloads["company_records"][: _request_limit(req)]}
        if req.url == f"{BASE_URL}/v2/objects/people/records/query":
            return {"data": self.payloads["person_records"][: _request_limit(req)]}
        return None


def build_loopway_attio_fixture_payloads(book: FixtureCustomerData) -> dict[str, Any]:
    company_by_id = {company.company_id: company for company in book.companies}
    company_records = [
        _company_record(account, company_by_id.get(account.account_id))
        for account in book.accounts
    ]
    person_records = [_person_record(contact) for contact in book.contacts]
    return {
        "self": {
            "workspace": {
                "slug": "ultra-csm-simulated-attio-loopway",
                "id": {"workspace_id": "workspace_simulated_ultra_csm_loopway"},
            }
        },
        "objects": {
            "data": [
                {"api_slug": "companies", "singular_noun": "Company", "plural_noun": "Companies"},
                {"api_slug": "people", "singular_noun": "Person", "plural_noun": "People"},
            ]
        },
        "companies_attributes": {"data": _company_attributes()},
        "people_attributes": {"data": _person_attributes()},
        "company_records": company_records,
        "person_records": person_records,
    }


def _company_attributes() -> list[dict[str, Any]]:
    return [
        _attribute("id", "text", required=True, system=True),
        _attribute("name", "text", required=True, system=True),
        _attribute("owner", "record-reference", required=False, system=False),
        _attribute("arr_cents", "number", required=False, system=False),
    ]


def _person_attributes() -> list[dict[str, Any]]:
    return [
        _attribute("id", "text", required=True, system=True),
        _attribute("associated_company", "record-reference", required=False, system=False),
        _attribute("email_addresses", "email-address", required=False, system=True),
        _attribute("name", "personal-name", required=False, system=True),
        _attribute("role", "text", required=False, system=False),
        _attribute("job_title", "text", required=False, system=False),
        _attribute("consent_to_contact", "checkbox", required=False, system=False),
    ]


def _attribute(api_slug: str, field_type: str, *, required: bool, system: bool) -> dict[str, Any]:
    return {
        "api_slug": api_slug,
        "title": api_slug.replace("_", " ").title(),
        "type": field_type,
        "is_required": required,
        "is_system_attribute": system,
    }


def _company_record(account, company) -> dict[str, Any]:  # noqa: ANN001 - dataclass-shaped fixture
    arr_cents = company.arr_cents if company is not None else 0
    return {
        "id": {"record_id": account.account_id},
        "values": {
            "id": [{"value": account.account_id}],
            "name": [{"value": account.name}],
            "owner": [{"target_object": "users", "target_record_id": account.owner_id}],
            "arr_cents": [{"value": arr_cents}],
        },
    }


def _person_record(contact) -> dict[str, Any]:  # noqa: ANN001 - dataclass-shaped fixture
    return {
        "id": {"record_id": contact.contact_id},
        "values": {
            "id": [{"value": contact.contact_id}],
            "associated_company": [
                {"target_object": "companies", "target_record_id": contact.account_id}
            ],
            "email_addresses": [{"email_address": contact.email}],
            "name": [{"full_name": contact.name}],
            "role": [{"value": contact.role}],
            "job_title": [{"value": contact.title}] if contact.title else [],
            "consent_to_contact": [{"value": contact.consent_to_contact}],
        },
    }


def _request_limit(req: HttpRequest) -> int:
    if req.body is None:
        return 1
    try:
        payload = json.loads(req.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 1
    if not isinstance(payload, dict):
        return 1
    return max(1, int(payload.get("limit", 1)))
