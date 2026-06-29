"""Salesforce raw-shape transforms.

These functions are pure: no sockets, no credentials, no live Salesforce client. A
live client should fetch records and hand raw JSON to these transforms.
"""

from __future__ import annotations

from typing import Any

from ultra_csm.data_plane.contracts import (
    CRMAccount,
    CRMCase,
    CRMContact,
    CRMOpportunity,
)
from ultra_csm.data_plane.transforms import (
    TransformError,
    money_to_cents,
    optional_bool,
    optional_str,
    require_str,
)


def parse_account(record: dict[str, Any]) -> CRMAccount:
    return CRMAccount(
        account_id=require_str(record, "Id"),
        name=require_str(record, "Name"),
        owner_id=require_str(record, "OwnerId"),
        industry=optional_str(record, "Industry"),
    )


def parse_contact(record: dict[str, Any]) -> CRMContact:
    return CRMContact(
        contact_id=require_str(record, "Id"),
        account_id=require_str(record, "AccountId"),
        email=require_str(record, "Email"),
        name=require_str(record, "Name"),
        role=optional_str(record, "Role__c"),
        title=optional_str(record, "Title"),
        consent_to_contact=optional_bool(record, "Consent_To_Contact__c", default=False),
    )


def parse_case(record: dict[str, Any]) -> CRMCase:
    return CRMCase(
        case_id=require_str(record, "Id"),
        account_id=require_str(record, "AccountId"),
        status=require_str(record, "Status"),
        priority=require_str(record, "Priority"),
        origin=require_str(record, "Origin"),
        subject=require_str(record, "Subject"),
        created_at=require_str(record, "CreatedDate"),
        closed_at=optional_str(record, "ClosedDate"),
    )


def parse_opportunity(record: dict[str, Any]) -> CRMOpportunity:
    return CRMOpportunity(
        opportunity_id=require_str(record, "Id"),
        account_id=require_str(record, "AccountId"),
        stage_name=require_str(record, "StageName"),
        amount_cents=money_to_cents(record, "Amount"),
        close_date=require_str(record, "CloseDate"),
        opportunity_type=require_str(record, "Type"),
    )


def parse_query_records(payload: dict[str, Any], parser):
    records = payload.get("records")
    if not isinstance(records, list):
        raise TransformError("Salesforce query payload missing records list")
    return tuple(parser(record) for record in records)


def next_records_url(payload: dict[str, Any]) -> str | None:
    done = payload.get("done")
    if done is True:
        return None
    url = payload.get("nextRecordsUrl")
    if isinstance(url, str) and url:
        return url
    raise TransformError("Salesforce query payload is not done and has no nextRecordsUrl")
