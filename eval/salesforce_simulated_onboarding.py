"""Salesforce simulated connector onboarding vertical.

This uses the real Salesforce explorer, source-map freeze, SOQL fetch, typed
contract parsing, and coverage reporting against an in-memory fake Salesforce
transport. It is not live tenant proof.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any
from urllib import parse

from ultra_csm.data_plane.explorer import ExplorerResult, run_explorer
from ultra_csm.data_plane.fixtures import FixtureCustomerData
from ultra_csm.data_plane.live_smoke import HttpRequest, HttpResponse
from ultra_csm.data_plane.readiness import SourceReadiness, readiness_report
from ultra_csm.data_plane.salesforce_live import (
    DEFAULT_ROW_CAP,
    fetch_salesforce_book,
)
from ultra_csm.data_plane.source_mapping import (
    freeze_confirmed_source_map,
    load_mapping_confirmations,
)
from ultra_csm.data_plane.synthetic_book import build_synthetic_book


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIRMATIONS_PATH = REPO / "eval" / "salesforce_simulated_confirmations.json"
DEFAULT_OUTPUT = REPO / "eval" / "salesforce_simulated_onboarding.json"
BASE_URL = "https://ultra-csm-simulated.my.salesforce.com"
LOGIN_URL = "https://login.salesforce.com"
API_VERSION = "v61.0"
PAGE_SIZE = 2


class FakeSalesforceClient:
    """In-memory Salesforce-shaped transport for discovery and query."""

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

    def _payload_for(self, req: HttpRequest) -> dict[str, Any] | list[dict[str, Any]] | None:
        if req.url == f"{LOGIN_URL}/services/oauth2/token":
            return {"access_token": "simulated-salesforce-token"}
        if req.url == f"{BASE_URL}/services/data/{API_VERSION}/sobjects/":
            return {
                "sobjects": [
                    {"name": name, "label": name}
                    for name in ("Account", "Contact", "Case", "Opportunity", "Task", "Event")
                ]
            }
        for object_name in ("Account", "Contact", "Case", "Opportunity", "Task", "Event"):
            if req.url == f"{BASE_URL}/services/data/{API_VERSION}/sobjects/{object_name}/describe":
                return _describe(object_name)
        if req.url.startswith(f"{BASE_URL}/services/data/{API_VERSION}/query?"):
            parsed = parse.urlparse(req.url)
            query = parse.parse_qs(parsed.query).get("q", [""])[0]
            object_name = _object_from_query(query)
            return _query_page(
                self.payloads["records"].get(object_name, ()),
                object_name=object_name,
                offset=0,
            )
        marker = f"{BASE_URL}/services/data/{API_VERSION}/query/"
        if req.url.startswith(marker):
            locator = req.url.removeprefix(marker)
            object_name, raw_offset = locator.rsplit("-", 1)
            return _query_page(
                self.payloads["records"].get(object_name, ()),
                object_name=object_name,
                offset=int(raw_offset),
            )
        if req.url == f"{BASE_URL}/services/data":
            return [{"version": API_VERSION.removeprefix("v"), "label": "Spring '24"}]
        return None


def build_salesforce_simulated_onboarding_artifact(
    *,
    confirmations_path: Path = DEFAULT_CONFIRMATIONS_PATH,
    output_path: Path = DEFAULT_OUTPUT,
    row_cap: int = 5,
) -> dict[str, Any]:
    book = build_synthetic_book()
    payloads = build_salesforce_fixture_payloads(book)

    no_cred_client = FakeSalesforceClient(payloads)
    missing = run_explorer("salesforce_crm", env={}, client=no_cred_client)
    fake_client = FakeSalesforceClient(payloads)
    env = {
        "ULTRA_CSM_SALESFORCE_INSTANCE_URL": BASE_URL,
        "ULTRA_CSM_SALESFORCE_CLIENT_ID": "simulated-client-id",
        "ULTRA_CSM_SALESFORCE_CLIENT_SECRET": "simulated-client-secret",
        "ULTRA_CSM_SALESFORCE_REFRESH_TOKEN": "simulated-refresh-token",
        "ULTRA_CSM_SALESFORCE_API_VERSION": API_VERSION,
    }
    discovered = run_explorer("salesforce_crm", env=env, client=fake_client)
    if not discovered.ok or discovered.snapshot is None or discovered.mapping_proposal is None:
        raise RuntimeError(f"Salesforce simulated discovery failed: {discovered.errors}")

    confirmations = load_mapping_confirmations(confirmations_path)
    _validate_confirmation_fixture(discovered, confirmations)
    frozen = freeze_confirmed_source_map(
        discovered.mapping_proposal,
        confirmations=confirmations,
    )
    fetch_client = FakeSalesforceClient(payloads)
    book_result = fetch_salesforce_book(
        frozen,
        env=env,
        client=fetch_client,
        row_cap=row_cap,
    )
    sim_readiness = SourceReadiness(
        connector_id="salesforce_crm",
        mode="fixture",
        state="fixture_verified",
        connected=False,
        rails_degraded=_unknown_contracts(frozen.unknown_fields),
        required_operator_actions=(
            "connect live Salesforce credentials before any live readiness claim",
            "review custom Contact fields and ordered categorical fields with the owner before live use",
        ),
        evidence=(
            "synthetic_customer_book",
            "fake_salesforce_client",
            "salesforce_explorer_parser",
            "frozen_source_map_config",
            "bounded_soql_fetch",
            "typed_crm_contracts",
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
        "artifact": "salesforce_simulated_onboarding",
        "generated_by": "eval.salesforce_simulated_onboarding",
        "claim_boundary": {
            "sim": True,
            "live": False,
            "uses_live_credentials": False,
            "live_tenant_proven": False,
            "read_only": True,
        },
        "measurement_scope": (
            "Salesforce describe discovery, source-map proposal, deterministic confirmation, "
            "freeze, bounded SOQL query pagination, typed CRM contracts, coverage report, "
            "and briefing over synthetic data and fake transport."
        ),
        "source_book": {
            "source": "src/ultra_csm/data_plane/synthetic_book.py",
            "accounts": len(book.accounts),
            "contacts": len(book.contacts),
            "cases": len(book.cases),
            "opportunities": len(book.opportunities),
        },
        "credential_boundary": {
            "missing_env": list(missing.missing_env),
            "missing_credentials_state": missing.readiness.state,
            "requests_without_credentials": len(no_cred_client.requests),
            "transport": "FakeSalesforceClient",
            "simulated_credentials_used": True,
            "live_credentials_used": False,
            "live_tenant_proof": False,
        },
        "fixture_payload": {
            "objects": ["Account", "Contact", "Case", "Opportunity"],
            "records_available": {
                key: len(value)
                for key, value in payloads["records"].items()
            },
            "page_size": PAGE_SIZE,
            "row_cap": row_cap,
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
        "fetch": {
            "auth_source": book_result.auth_source,
            "requests_on_fake_transport": len(fetch_client.requests),
            "request_methods": [request.method for request in fetch_client.requests],
            "fetches": [fetch.to_dict() for fetch in book_result.fetches],
        },
        "coverage": book_result.coverage.to_dict(),
        "briefing": list(book_result.briefing),
        "readiness": asdict(sim_readiness),
        "readiness_report": readiness_report((sim_readiness,)),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def build_salesforce_fixture_payloads(book: FixtureCustomerData) -> dict[str, Any]:
    return {
        "records": {
            "Account": [
                {
                    "Id": account.account_id,
                    "Name": account.name,
                    "OwnerId": account.owner_id,
                    "Industry": account.industry,
                }
                for account in book.accounts
            ],
            "Contact": [
                {
                    "Id": contact.contact_id,
                    "AccountId": contact.account_id,
                    "Email": contact.email,
                    "Name": contact.name,
                    "Role__c": contact.role,
                    "Title": contact.title,
                    "Consent_To_Contact__c": contact.consent_to_contact,
                    "Org_Level__c": contact.org_level,
                }
                for contact in book.contacts
            ],
            "Case": [
                {
                    "Id": case.case_id,
                    "AccountId": case.account_id,
                    "Status": case.status,
                    "Priority": case.priority,
                    "Origin": case.origin,
                    "Subject": case.subject,
                    "CreatedDate": case.created_at,
                    "ClosedDate": case.closed_at,
                }
                for case in book.cases
            ],
            "Opportunity": [
                {
                    "Id": opportunity.opportunity_id,
                    "AccountId": opportunity.account_id,
                    "StageName": opportunity.stage_name,
                    "Amount": opportunity.amount_cents / 100,
                    "CloseDate": opportunity.close_date,
                    "Type": opportunity.opportunity_type,
                }
                for opportunity in book.opportunities
            ],
        }
    }


def _describe(object_name: str) -> dict[str, Any]:
    fields_by_object = {
        "Account": (
            _field("Id", "id", required=True),
            _field("Name", "string", required=True),
            _field("OwnerId", "reference", required=True),
            _field("Industry", "picklist"),
        ),
        "Contact": (
            _field("Id", "id", required=True),
            _field("AccountId", "reference", required=True),
            _field("Email", "email", required=True),
            _field("Name", "string", required=True),
            _field("Role__c", "string", custom=True),
            _field("Title", "string"),
            _field("Consent_To_Contact__c", "boolean", custom=True),
            _field("Org_Level__c", "int", custom=True),
        ),
        "Case": (
            _field("Id", "id", required=True),
            _field("AccountId", "reference", required=True),
            _field("Status", "picklist", required=True),
            _field("Priority", "picklist", required=True),
            _field("Origin", "picklist", required=True),
            _field("Subject", "string", required=True),
            _field("CreatedDate", "datetime", required=True),
            _field("ClosedDate", "datetime"),
        ),
        "Opportunity": (
            _field("Id", "id", required=True),
            _field("AccountId", "reference", required=True),
            _field("StageName", "picklist", required=True),
            _field("Amount", "currency", required=True),
            _field("CloseDate", "date", required=True),
            _field("Type", "picklist", required=True),
        ),
        "Task": (
            _field("Id", "id", required=True),
            _field("WhatId", "reference"),
            _field("Description", "textarea"),
            _field("ActivityDate", "date"),
        ),
        "Event": (
            _field("Id", "id", required=True),
            _field("WhatId", "reference"),
            _field("Description", "textarea"),
            _field("ActivityDate", "date"),
        ),
    }
    return {
        "name": object_name,
        "label": object_name,
        "fields": list(fields_by_object[object_name]),
    }


def _field(
    name: str,
    field_type: str,
    *,
    required: bool = False,
    custom: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "label": name.replace("__c", "").replace("_", " "),
        "type": field_type,
        "nillable": not required,
        "custom": custom,
    }


def _query_page(
    records: list[dict[str, Any]],
    *,
    object_name: str,
    offset: int,
) -> dict[str, Any]:
    page = records[offset: offset + PAGE_SIZE]
    next_offset = offset + PAGE_SIZE
    done = next_offset >= len(records)
    payload: dict[str, Any] = {
        "totalSize": len(records),
        "done": done,
        "records": page,
    }
    if not done:
        payload["nextRecordsUrl"] = f"/services/data/{API_VERSION}/query/{object_name}-{next_offset}"
    return payload


def _object_from_query(query: str) -> str:
    parts = query.split()
    try:
        return parts[parts.index("FROM") + 1]
    except (ValueError, IndexError) as exc:
        raise RuntimeError(f"query missing FROM object: {query}") from exc


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


def _discovery_summary(result: ExplorerResult, client: FakeSalesforceClient) -> dict[str, Any]:
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
        "request_methods": [request.method for request in client.requests],
        "explorer_state_on_fake_transport": result.readiness.state,
        "explorer_connected_flag_is_not_live_proof": result.readiness.connected,
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
    parser.add_argument("--row-cap", type=int, default=DEFAULT_ROW_CAP)
    args = parser.parse_args(argv)
    artifact = build_salesforce_simulated_onboarding_artifact(
        confirmations_path=args.confirmations,
        output_path=args.output,
        row_cap=args.row_cap,
    )
    print(json.dumps({
        "artifact": _display_path(args.output),
        "fixture_state": artifact["readiness"]["state"],
        "live_tenant_proven": artifact["claim_boundary"]["live_tenant_proven"],
        "config_hash": artifact["frozen_source_map"]["config_hash"],
        "truncated": artifact["coverage"]["truncated"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
