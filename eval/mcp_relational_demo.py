"""Capture the conversational relational-onboarding MCP transcript artifact.

The fixture is a small synthetic normalized CRM in the shape a Salesforce org
relays: three tables (Account/Contact/Opportunity) with source-declared
foreign-key metadata on the child tables. The transcript proves the whole
conversational flow — readiness, one ingest_table per table, one confirm_book —
and that only the genuinely human questions (identity picks and value
direction) come back to the user.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT_PATH = Path("eval") / "mcp_relational_transcript.json"

BOOK_ID = "relational-transcript"

# The questions a fully-metadata'd three-table book still asks a human:
# two parent picks, two child identity picks, one value direction. Everything
# else is auto-mapped (source-declared references, exact standard aliases) or
# declared not_mappable by contract intent.
EXPECTED_QUESTION_KEYS = (
    "CRMAccount.account_id",
    "CRMAccount.owner_id",
    "CRMContact.contact_id",
    "CRMOpportunity.opportunity_id",
    "CRMOpportunity.stage_name",
)


def fixture_tables() -> tuple[tuple[str, str, list[dict[str, Any]], dict | None], ...]:
    """(table_name, contract, records, field_metadata) per table."""

    accounts = [
        {"Id": "001SYN0000000001AAA", "Name": "Harbor Analytics", "OwnerId": "005SYN0000000001AAA", "Industry": "logistics"},
        {"Id": "001SYN0000000002AAA", "Name": "Cobalt Manufacturing", "OwnerId": "005SYN0000000002AAA", "Industry": "manufacturing"},
        {"Id": "001SYN0000000003AAA", "Name": "Meridian Health Labs", "OwnerId": "005SYN0000000001AAA", "Industry": "healthcare"},
    ]
    contacts = [
        {"Id": "003SYN0000000001AAA", "Name": "Dana Wells", "Email": "dana@harbor.example.test", "Title": "Operations Lead", "AccountId": "001SYN0000000001AAA"},
        {"Id": "003SYN0000000002AAA", "Name": "Priya Nair", "Email": "priya@cobalt.example.test", "Title": "Plant Manager", "AccountId": "001SYN0000000002AAA"},
        {"Id": "003SYN0000000003AAA", "Name": "Marcus Cole", "Email": "marcus@cobalt.example.test", "Title": "Procurement", "AccountId": "001SYN0000000002AAA"},
        {"Id": "003SYN0000000004AAA", "Name": "Elena Ruiz", "Email": "elena@meridian.example.test", "Title": "Lab Director", "AccountId": "001SYN0000000003AAA"},
    ]
    opportunities = [
        {"Id": "006SYN0000000001AAA", "StageName": "Prospecting", "Amount": 18000.0, "CloseDate": "2026-09-30", "Type": "New Business", "AccountId": "001SYN0000000001AAA"},
        {"Id": "006SYN0000000002AAA", "StageName": "Negotiation", "Amount": 42000.5, "CloseDate": "2026-08-15", "Type": "Expansion", "AccountId": "001SYN0000000002AAA"},
        {"Id": "006SYN0000000003AAA", "StageName": "Closed Won", "Amount": 27500.0, "CloseDate": "2026-06-01", "Type": "Renewal", "AccountId": "001SYN0000000002AAA"},
        {"Id": "006SYN0000000004AAA", "StageName": "Qualification", "Amount": 9800.0, "CloseDate": "2026-11-20", "Type": "New Business", "AccountId": "001SYN0000000003AAA"},
    ]
    reference = {
        "AccountId": {
            "field_type": "reference",
            "references": ["Account"],
            "relationship_name": "Account",
        }
    }
    return (
        ("Account", "CRMAccount", accounts, None),
        ("Contact", "CRMContact", contacts, reference),
        ("Opportunity", "CRMOpportunity", opportunities, reference),
    )


def fixture_confirmations() -> dict[str, dict[str, dict[str, Any]]]:
    """The five human answers, keyed by table then question key."""

    def mapped(contract: str, field: str, path: str, role: str, direction: str = "not_applicable") -> dict[str, Any]:
        return {
            "contract": contract,
            "internal_field": field,
            "source_object": "records",
            "source_field": path,
            "source_path": path,
            "semantic_role": role,
            "value_direction": direction,
            "verdict": "mapped",
        }

    return {
        "Account": {
            "CRMAccount.account_id": mapped("CRMAccount", "account_id", "Id", "identity_join"),
            "CRMAccount.owner_id": mapped("CRMAccount", "owner_id", "OwnerId", "context"),
        },
        "Contact": {
            "CRMContact.contact_id": mapped("CRMContact", "contact_id", "Id", "identity_join"),
        },
        "Opportunity": {
            "CRMOpportunity.opportunity_id": mapped("CRMOpportunity", "opportunity_id", "Id", "identity_join"),
            "CRMOpportunity.stage_name": mapped("CRMOpportunity", "stage_name", "StageName", "context", "higher_is_better"),
        },
    }


def build_mcp_relational_transcript(
    *,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> dict[str, Any]:
    """Run the deterministic relational onboarding flow and write its transcript."""

    from ultra_csm import mcp_server

    mcp_server._relational_books.clear()

    calls: list[dict[str, Any]] = []
    _call(calls, "report_readiness", mcp_server.report_readiness(["crm"]))
    question_keys: list[str] = []
    for table_name, contract, records, field_metadata in fixture_tables():
        ingest = _call(
            calls,
            "ingest_table",
            mcp_server.ingest_table(
                book_id=BOOK_ID,
                table_name=table_name,
                contract=contract,
                records=records,
                expected_count=len(records),
                field_metadata=field_metadata,
            ),
        )
        question_keys.extend(q["key"] for q in ingest["confirmation_questions"])
    confirm = _call(
        calls,
        "confirm_book",
        mcp_server.confirm_book(
            book_id=BOOK_ID,
            confirmations=fixture_confirmations(),
        ),
    )
    artifact = {
        "artifact": "mcp_relational_transcript",
        "claim_boundary": {
            "provenance": "mcp_relay",
            "unverified_mapping": True,
            "sim": False,
            "live": False,
        },
        "beats": [
            "readiness",
            "ingest_table:Account",
            "ingest_table:Contact",
            "ingest_table:Opportunity",
            "confirm_book",
        ],
        "book_id": BOOK_ID,
        "question_keys": sorted(question_keys),
        "question_count": len(question_keys),
        "typed_counts": confirm["typed_counts"],
        "foreign_key_joins": confirm["coverage"]["join_coverage"]["foreign_key_joins"],
        "replay_sha256": confirm["replay_sha256"],
        "tool_calls": calls,
    }
    artifact["artifact_sha256"] = _hash_without_self(artifact)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return artifact


def _call(calls: list[dict[str, Any]], name: str, output: dict[str, Any]) -> dict[str, Any]:
    calls.append({
        "tool": name,
        "output_sha256": hashlib.sha256(
            json.dumps(output, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "output": output,
    })
    return output


def _hash_without_self(artifact: dict[str, Any]) -> str:
    payload = {key: value for key, value in artifact.items() if key != "artifact_sha256"}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def main() -> int:
    artifact = build_mcp_relational_transcript()
    print(json.dumps({
        "artifact": str(DEFAULT_OUTPUT_PATH),
        "question_count": artifact["question_count"],
        "question_keys": artifact["question_keys"],
        "typed_counts": artifact["typed_counts"],
        "tool_calls": len(artifact["tool_calls"]),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
