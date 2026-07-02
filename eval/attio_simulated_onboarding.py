"""Attio simulated connector onboarding vertical.

This uses the real Attio explorer and source-map freeze machinery against an
in-memory fake Attio client built from the synthetic customer book. The output is
an onboarding/readiness artifact only; it is not live tenant proof.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from ultra_csm.data_plane.explorer import ExplorerResult, run_explorer
from ultra_csm.data_plane.fixtures import FixtureCustomerData
from ultra_csm.data_plane.live_smoke import HttpRequest, HttpResponse
from ultra_csm.data_plane.readiness import SourceReadiness, readiness_report
from ultra_csm.data_plane.source_mapping import (
    freeze_confirmed_source_map,
    load_mapping_confirmations,
)
from ultra_csm.data_plane.synthetic_book import build_synthetic_book


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIRMATIONS_PATH = REPO / "eval" / "attio_simulated_confirmations.json"
DEFAULT_OUTPUT = REPO / "eval" / "attio_simulated_onboarding.json"
BASE_URL = "https://api.attio.com"


class FakeAttioClient:
    """In-memory Attio-shaped transport for the connector explorer."""

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


def build_attio_simulated_onboarding_artifact(
    *,
    confirmations_path: Path = DEFAULT_CONFIRMATIONS_PATH,
    output_path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    book = build_synthetic_book()
    payloads = build_attio_fixture_payloads(book)

    no_cred_client = FakeAttioClient(payloads)
    missing = run_explorer("attio_crm", env={}, client=no_cred_client)
    fake_client = FakeAttioClient(payloads)
    discovered = run_explorer(
        "attio_crm",
        env={"ULTRA_CSM_ATTIO_ACCESS_TOKEN": "simulated-attio-token"},
        client=fake_client,
    )
    if not discovered.ok or discovered.snapshot is None or discovered.mapping_proposal is None:
        raise RuntimeError(f"Attio simulated discovery failed: {discovered.errors}")

    confirmations = load_mapping_confirmations(confirmations_path)
    _validate_confirmation_fixture(discovered, confirmations)
    frozen = freeze_confirmed_source_map(
        discovered.mapping_proposal,
        confirmations=confirmations,
    )
    sim_readiness = SourceReadiness(
        connector_id="attio_crm",
        mode="fixture",
        state="fixture_verified",
        connected=False,
        rails_degraded=_unknown_contracts(frozen.unknown_fields),
        required_operator_actions=(
            "connect live Attio credentials before any live readiness claim",
            "review unknown source-map fields before customer-tenant use",
        ),
        evidence=(
            "synthetic_customer_book",
            "fake_attio_client",
            "attio_explorer_parser",
            "frozen_source_map_config",
        ),
    )
    ambiguous_keys = sorted(
        entry.key
        for entry in discovered.mapping_proposal.entries
        if entry.state == "ambiguous_confirm"
    )
    missing_keys = sorted(
        entry.key
        for entry in discovered.mapping_proposal.entries
        if entry.state == "missing_to_unknown"
    )
    artifact = {
        "artifact": "attio_simulated_onboarding",
        "generated_by": "eval.attio_simulated_onboarding",
        "claim_boundary": {
            "sim": True,
            "live": False,
            "uses_live_credentials": False,
            "live_tenant_proven": False,
        },
        "measurement_scope": (
            "Attio discovery, source-map proposal, deterministic confirmation, "
            "freeze, and readiness artifact over synthetic data and fake transport."
        ),
        "source_book": {
            "source": "src/ultra_csm/data_plane/synthetic_book.py",
            "accounts": len(book.accounts),
            "contacts": len(book.contacts),
            "companies": len(book.companies),
        },
        "credential_boundary": {
            "missing_env": list(missing.missing_env),
            "missing_credentials_state": missing.readiness.state,
            "requests_without_credentials": len(no_cred_client.requests),
            "transport": "FakeAttioClient",
            "simulated_credentials_used": True,
            "live_credentials_used": False,
            "live_tenant_proof": False,
        },
        "fixture_payload": {
            "objects": ["companies", "people"],
            "company_records_available": len(payloads["company_records"]),
            "person_records_available": len(payloads["person_records"]),
            "sample_company_record": _record_preview(payloads["company_records"][0]),
            "sample_person_record": _record_preview(payloads["person_records"][0]),
        },
        "discovery": _discovery_summary(discovered, fake_client),
        "mapping_proposal": {
            "proposal_hash": discovered.mapping_proposal.proposal_hash,
            "schema_hash": discovered.mapping_proposal.schema_hash,
            "coverage": discovered.mapping_proposal.coverage,
            "required_operator_actions": list(
                discovered.mapping_proposal.required_operator_actions
            ),
            "ambiguous_keys": ambiguous_keys,
            "missing_to_unknown_keys": missing_keys,
        },
        "confirmation_fixture": {
            "path": _display_path(confirmations_path),
            "confirmed_keys": sorted(confirmations),
        },
        "frozen_source_map": frozen.to_dict(),
        "readiness": asdict(sim_readiness),
        "readiness_report": readiness_report((sim_readiness,)),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def build_attio_fixture_payloads(book: FixtureCustomerData) -> dict[str, Any]:
    company_by_id = {company.company_id: company for company in book.companies}
    company_records = [
        _company_record(account, company_by_id.get(account.account_id))
        for account in book.accounts
    ]
    person_records = [_person_record(contact) for contact in book.contacts]
    return {
        "self": {
            "workspace": {
                "slug": "ultra-csm-simulated-attio",
                "id": {"workspace_id": "workspace_simulated_ultra_csm"},
            }
        },
        "objects": {
            "data": [
                {
                    "api_slug": "companies",
                    "singular_noun": "Company",
                    "plural_noun": "Companies",
                },
                {
                    "api_slug": "people",
                    "singular_noun": "Person",
                    "plural_noun": "People",
                },
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
        _attribute("fleet_size", "number", required=False, system=False),
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
        _attribute("fleet_contact_code", "text", required=False, system=False),
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
    fleet_size = max(1, arr_cents // 1_000_000)
    return {
        "id": {"record_id": account.account_id},
        "values": {
            "id": [{"value": account.account_id}],
            "name": [{"value": account.name}],
            "owner": [{"target_object": "users", "target_record_id": account.owner_id}],
            "fleet_size": [{"value": fleet_size}],
        },
    }


def _person_record(contact) -> dict[str, Any]:  # noqa: ANN001 - dataclass-shaped fixture
    return {
        "id": {"record_id": contact.contact_id},
        "values": {
            "id": [{"value": contact.contact_id}],
            "associated_company": [
                {
                    "target_object": "companies",
                    "target_record_id": contact.account_id,
                }
            ],
            "email_addresses": [{"email_address": contact.email}],
            "name": [{"full_name": contact.name}],
            "role": [{"value": contact.role}],
            "job_title": [{"value": contact.title}],
            "consent_to_contact": [{"value": contact.consent_to_contact}],
            "fleet_contact_code": [{"value": contact.contact_id[-8:]}],
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


def _validate_confirmation_fixture(
    result: ExplorerResult,
    confirmations: dict[str, Any],
) -> None:
    assert result.mapping_proposal is not None
    ambiguous = {
        entry.key
        for entry in result.mapping_proposal.entries
        if entry.state == "ambiguous_confirm"
    }
    missing = ambiguous - set(confirmations)
    unused = set(confirmations) - {
        entry.key for entry in result.mapping_proposal.entries
    }
    if missing:
        raise RuntimeError(f"confirmation fixture missing keys: {sorted(missing)}")
    if unused:
        raise RuntimeError(f"confirmation fixture has unused keys: {sorted(unused)}")


def _unknown_contracts(unknown_fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({item.split(".", 1)[0] for item in unknown_fields}))


def _discovery_summary(result: ExplorerResult, client: FakeAttioClient) -> dict[str, Any]:
    assert result.snapshot is not None
    return {
        "ok": result.ok,
        "schema_hash": result.snapshot.schema_hash,
        "source_steps": list(result.snapshot.source_steps),
        "sample_counts": result.snapshot.sample_counts,
        "objects": [
            {
                "name": obj.name,
                "fields": [field.name for field in obj.fields],
            }
            for obj in result.snapshot.objects
            if obj.fields
        ],
        "requests_on_fake_transport": len(client.requests),
        "request_urls": [request.url for request in client.requests],
        "explorer_state_on_fake_transport": result.readiness.state,
        "explorer_connected_flag_is_not_live_proof": result.readiness.connected,
    }


def _record_preview(record: dict[str, Any]) -> dict[str, Any]:
    values = record["values"]
    return {
        "record_id": record["id"]["record_id"],
        "value_keys": sorted(values),
    }


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirmations", type=Path, default=DEFAULT_CONFIRMATIONS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    artifact = build_attio_simulated_onboarding_artifact(
        confirmations_path=args.confirmations,
        output_path=args.output,
    )
    print(json.dumps({
        "artifact": _display_path(args.output),
        "fixture_state": artifact["readiness"]["state"],
        "live_tenant_proven": artifact["claim_boundary"]["live_tenant_proven"],
        "config_hash": artifact["frozen_source_map"]["config_hash"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
