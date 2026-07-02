"""Recorded connector shape transforms."""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest

from ultra_csm.data_plane import SALESFORCE_SOURCE_MAPS
from ultra_csm.data_plane.adapters.salesforce import (
    next_records_url,
    parse_account,
    parse_case,
    parse_contact,
    parse_opportunity,
    parse_query_records,
)
from ultra_csm.data_plane.contracts import CRMAccount, CRMCase, CRMContact, CRMOpportunity
from ultra_csm.data_plane.transforms import TransformError

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "connectors" / "salesforce"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("fixture_name", "parser", "contract", "expected_id"),
    (
        ("account_query_page.json", parse_account, CRMAccount, "001000000000001"),
        ("contact_query_page.json", parse_contact, CRMContact, "003000000000001"),
        ("case_query_page.json", parse_case, CRMCase, "500000000000001"),
        ("opportunity_query_page.json", parse_opportunity, CRMOpportunity, "006000000000001"),
    ),
)
def test_salesforce_recorded_shapes_parse_to_contracts(
    fixture_name,
    parser,
    contract,
    expected_id,
):
    parsed = parse_query_records(load_fixture(fixture_name), parser)

    assert len(parsed) == 1
    assert isinstance(parsed[0], contract)
    id_field = fields(contract)[0].name
    assert getattr(parsed[0], id_field) == expected_id


def test_salesforce_unknown_fields_are_ignored_by_transform():
    record = load_fixture("account_query_page.json")["records"][0]

    assert "Ignored_Custom__c" in record
    account = parse_account(record)

    assert account == CRMAccount(
        account_id="001000000000001",
        name="Acme Logistics",
        owner_id="005000000000001",
        industry="Transportation",
    )


def test_salesforce_required_field_missing_fails_closed():
    record = dict(load_fixture("account_query_page.json")["records"][0])
    record.pop("OwnerId")

    with pytest.raises(TransformError, match="OwnerId"):
        parse_account(record)


def test_salesforce_query_payload_requires_records_list():
    with pytest.raises(TransformError, match="records list"):
        parse_query_records({"done": True}, parse_account)


def test_salesforce_pagination_uses_next_records_url_until_done():
    assert next_records_url(load_fixture("account_query_page.json")) is None
    assert next_records_url(load_fixture("account_query_first_page.json")) == (
        "/services/data/v61.0/query/01g000000000001-2000"
    )

    with pytest.raises(TransformError, match="nextRecordsUrl"):
        next_records_url({"done": False, "records": []})


def test_salesforce_null_opportunity_amount_fails_closed():
    record = dict(load_fixture("opportunity_query_page.json")["records"][0])
    record["Amount"] = None

    with pytest.raises(TransformError, match="Amount"):
        parse_opportunity(record)


def test_salesforce_parsers_match_declared_source_maps():
    expected = {
        "CRMAccount": {"Id", "Name", "OwnerId", "Industry"},
        "CRMContact": {
            "Id",
            "AccountId",
            "Email",
            "Name",
            "Role__c",
            "Title",
            "Consent_To_Contact__c",
            "Org_Level__c",
        },
        "CRMCase": {
            "Id",
            "AccountId",
            "Status",
            "Priority",
            "Origin",
            "Subject",
            "CreatedDate",
            "ClosedDate",
        },
        "CRMOpportunity": {"Id", "AccountId", "StageName", "Amount", "CloseDate", "Type"},
    }

    for contract, api_names in expected.items():
        mapped = {
            field.api_name
            for field in SALESFORCE_SOURCE_MAPS[contract].fields.values()
        }
        assert api_names <= mapped
