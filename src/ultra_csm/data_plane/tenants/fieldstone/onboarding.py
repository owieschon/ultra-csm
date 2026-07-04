"""fieldstone's onboarding-cost driver: the second data point for the
onboarding-cost claim (Universe v2, WS-Tenant-Fieldstone, Wave 3),
proving the conversational-onboarding path
(``ingest_table``/``confirm_book``) handles a HubSpot-shaped source whose
foreign-key metadata arrives via associations, not a reference-typed
column the way Salesforce's ``AccountId`` field does.

Mirrors ``eval.week1_protocol.run_onboarding_cost_driver``'s
in-process-MCP-call style (Program 13's IF/THEN: the live stdio driver
talks to a real org and cannot run offline; this calls the same MCP tool
functions in-process, exactly like ``eval/mcp_relational_demo.py`` does).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ultra_csm import mcp_server
from ultra_csm.data_plane.tenants.fieldstone.book import build_fieldstone_book
from ultra_csm.data_plane.tenants.fieldstone.hubspot_transport import (
    _hubspot_company_id,
    _hubspot_contact_id,
)

_TIER_A_REASON = "auto-mapped: source-declared reference"
_TIER_B_REASON = "auto-mapped: exact standard-field match"


@dataclass(frozen=True)
class FieldstoneOnboardingCostResult:
    questions_asked: tuple[str, ...]
    auto_mapped_by_tier: dict[str, int]
    confirmations_required: int
    wall_clock_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "questions_asked_count": len(self.questions_asked),
            "questions_asked": list(self.questions_asked),
            "auto_mapped_by_tier": self.auto_mapped_by_tier,
            "confirmations_required": self.confirmations_required,
            "wall_clock_seconds": round(self.wall_clock_seconds, 6),
        }


def _hubspot_records_for_onboarding() -> tuple[
    tuple[str, str, list[dict[str, Any]], dict[str, Any] | None], ...
]:
    """fieldstone's HubSpot-shaped book (Account/Contact), as raw dict
    records in a ``properties``-map wire shape -- association-derived
    metadata (NOT a lookup field, per the bible's "associations, not
    lookup fields" requirement) is what drives the Contact table's
    foreign-key mapping."""

    data = build_fieldstone_book()
    accounts = [
        {
            "Id": _hubspot_company_id(_slug_for(a.account_id)),
            "Name": a.name,
            "OwnerId": a.owner_id,
            "Industry": a.industry,
        }
        for a in data.accounts
    ]
    contacts = [
        {
            "Id": _hubspot_contact_id(_slug_for(c.account_id)),
            "Name": c.name,
            "Email": c.email,
            "Title": c.title,
            # HubSpot-shaped wire: the join key is an ASSOCIATION id, not a
            # plain lookup field -- carried here as the raw associated
            # company id, exactly as the associations API would return it
            # alongside the contact record. field_metadata below declares
            # this column's provenance as association-schema-derived
            # (Tier A per the explorer's new hubspot association parser),
            # not a bare foreign key the driver has to guess at.
            "AssociatedCompanyId": _hubspot_company_id(_slug_for(c.account_id)),
        }
        for c in data.contacts
    ]
    association_meta = {
        "AssociatedCompanyId": {
            "field_type": "reference",
            "references": ["Account"],
            "relationship_name": "AssociatedCompany",
        }
    }
    return (
        ("Account", "CRMAccount", accounts, None),
        ("Contact", "CRMContact", contacts, association_meta),
    )


def _slug_for(account_id: str) -> str:
    from ultra_csm.data_plane.tenants.fieldstone.book import ACCOUNT_SLUGS, account_id_for

    for slug in ACCOUNT_SLUGS:
        if account_id_for(slug) == account_id:
            return slug
    raise KeyError(account_id)


def run_fieldstone_onboarding_cost_driver(
    *, book_id: str = "week1-onboarding-fieldstone",
) -> FieldstoneOnboardingCostResult:
    import time as _time

    mcp_server._relational_books.pop(book_id, None)
    start = _time.perf_counter()

    question_keys: list[str] = []
    auto_mapped_by_tier = {"tier_a_source_declared": 0, "tier_b_exact_alias": 0, "other": 0}
    confirmations: dict[str, dict[str, dict[str, Any]]] = {}

    for table_name, contract, records, field_metadata in _hubspot_records_for_onboarding():
        resp = mcp_server.ingest_table(
            book_id=book_id,
            table_name=table_name,
            contract=contract,
            records=records,
            expected_count=len(records),
            field_metadata=field_metadata,
        )
        assert "error" not in resp, resp
        for entry in resp.get("auto_mapped", []):
            reason = entry.get("reason", "")
            if reason.startswith(_TIER_A_REASON):
                auto_mapped_by_tier["tier_a_source_declared"] += 1
            elif reason.startswith(_TIER_B_REASON):
                auto_mapped_by_tier["tier_b_exact_alias"] += 1
            else:
                auto_mapped_by_tier["other"] += 1
        table_confirmations: dict[str, dict[str, Any]] = {}
        for question in resp.get("confirmation_questions", []):
            key = question["key"]
            question_keys.append(key)
            contract_name, internal_field = key.split(".", 1)
            table_confirmations[key] = {
                "contract": contract_name,
                "internal_field": internal_field,
                "verdict": "not_mappable",
            }
        confirmations[table_name] = table_confirmations

    confirm = mcp_server.confirm_book(book_id=book_id, confirmations=confirmations)
    assert "error" not in confirm, confirm
    elapsed = _time.perf_counter() - start

    return FieldstoneOnboardingCostResult(
        questions_asked=tuple(sorted(question_keys)),
        auto_mapped_by_tier=auto_mapped_by_tier,
        confirmations_required=len(question_keys),
        wall_clock_seconds=elapsed,
    )
