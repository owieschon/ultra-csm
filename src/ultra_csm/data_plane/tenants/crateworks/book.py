"""Crateworks WMS flat book: the messy homegrown-CRM export.

Per ``docs/TENANT_CRATEWORKS_BIBLE.md`` section 0/1/3: ten accounts (1
high / 3 mid / 6 tech), authored as raw CSV-export-shaped flat dict rows
-- exactly the wire shape a homegrown spreadsheet-turned-database "API"
would actually emit, deliberately including the mess spec's authored
quotas (empty optional fields, free-text enum values, duplicate contact
rows, one stale record, inconsistent header casing/whitespace).

This is the tenant analog of ``docs/PROGRAM_REPORT_3.md``'s corpus-A flat
path. The raw rows below are driven through the real, unmodified
conversational-onboarding surface (``ultra_csm.mcp_server.ingest_table`` /
``confirm_book``, the exact tools ``eval/week1_protocol.py``'s onboarding
driver already calls in-process) rather than a second hand-rolled
transform -- the same driver that MEASURES the degradation (Phase 3) is
also what BUILDS the data plane every other phase reads, so there is only
one ingest path to keep honest, not two that could silently drift apart.

No CS platform, no product telemetry vendor for this tenant (bible
section 0): ARR/tier bookkeeping is derived directly from the CRM
Opportunity's ``amount_cents`` (the closed subscription value), not from a
fabricated ``CSCompany`` row -- inventing a Gainsight-shaped record for a
tenant whose bible explicitly says "no CS platform" would misrepresent the
vendor stack this tenant is supposed to demonstrate the DEGRADED read of.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ultra_csm.data_plane.canary_registry import canary_token
from ultra_csm.data_plane.contracts import CustomerDataPlane
from ultra_csm.data_plane.external_book import RelationalTable, ingest_relational_book
from ultra_csm.data_plane.fixtures import (
    FixtureCRMDataConnector,
    FixtureCSPlatformConnector,
    FixtureCustomerData,
    FixtureProductTelemetryConnector,
    det_id,
)

TENANT = "crateworks"
SEED_DATE = "2026-06-21"  # aligned with fleetops' SEED_DATE for cross-tenant day-offset parity
STALE_DATE = "2023-06-21"  # exactly 3 years before SEED_DATE, per bible section 3.4

DOCKSIDE_SLUG = "crateworks-dockside-fulfillment"
BOOK_ID = "crateworks-book"

# (slug, display name, arr_cents, csm_owner_id) -- bible section 1's ten-account table.
ACCOUNTS: tuple[tuple[str, str, int, str], ...] = (
    (DOCKSIDE_SLUG, "Dockside Fulfillment", 18_000_000, "csm-cw-01"),
    ("crateworks-northgate-3pl", "Northgate 3PL", 6_000_000, "csm-cw-01"),
    ("crateworks-portline-logistics", "Portline Logistics", 4_200_000, "csm-cw-01"),
    ("crateworks-summitcrate-storage", "Summitcrate Storage", 3_000_000, "csm-cw-01"),
    ("crateworks-basinwood-supply", "Basinwood Supply", 900_000, "csm-cw-01"),
    ("crateworks-drydock-warehousing", "Drydock Warehousing", 700_000, "csm-cw-01"),
    ("crateworks-fernbridge-distro", "Fernbridge Distro", 650_000, "csm-cw-01"),
    ("crateworks-ledgerport-storage", "Ledgerport Storage", 500_000, "csm-cw-01"),
    ("crateworks-mossway-fulfillment", "Mossway Fulfillment", 400_000, "csm-cw-01"),
    ("crateworks-quillstack-3pl", "Quillstack 3PL", 350_000, "csm-cw-01"),
)

CONTROL_SLUGS: tuple[str, ...] = tuple(slug for slug, *_ in ACCOUNTS if slug != DOCKSIDE_SLUG)

# Bible section 3.2: the same semantic "active" status, spelled three
# incompatible ways, cycled deterministically across accounts (never random).
_STATUS_VARIANTS = ("kinda active?", "ACTIVE", "active ")

# Bible section 3.3: per-account duplicate-contact pair. Dockside's pair IS
# Dana Okafor (arc C1, see comms.py); every other account gets an unrelated,
# un-arced duplicate pair (a plain casing-drift artifact, no story).
_CONTROL_DUPLICATE_NAMES: dict[str, str] = {
    "crateworks-northgate-3pl": "Priya Chandrasekaran",
    "crateworks-portline-logistics": "Tomas Reyes",
    "crateworks-summitcrate-storage": "Whitney Voss",
    "crateworks-basinwood-supply": "Marcus Iglehart",
    "crateworks-drydock-warehousing": "Renata Cho",
    "crateworks-fernbridge-distro": "Owen Bramlett",
    "crateworks-ledgerport-storage": "Ida Marchetti",
    "crateworks-mossway-fulfillment": "Colton Rasmussen",
    "crateworks-quillstack-3pl": "Grace Delacroix",
}


def crateworks_account_id(slug: str) -> str:
    return det_id("account", slug)


def _casefold_variant(name: str) -> str:
    """A second, differently-cased spelling of the same name -- the
    casing-chaos half of bible section 3.3's duplicate-contact quota."""

    return name.upper()


@dataclass(frozen=True)
class FlatCrateworksBook:
    """The raw, unmapped, CSV-export-shaped tables -- before any ingest."""

    account_rows: tuple[dict[str, Any], ...]
    contact_rows: tuple[dict[str, Any], ...]
    opportunity_rows: tuple[dict[str, Any], ...]


def _account_row(slug: str, name: str, arr_cents: int, csm_owner_id: str, index: int) -> dict[str, Any]:
    """One row of the account table. Header keys deliberately mix casing/
    spacing across this table vs. the contact/opportunity tables (bible
    section 3.5): this table uses ``"Account Name "`` (trailing space,
    title case) for the display-name column.

    Optional columns (bible section 3.1, >=40% empty): of the ten optional
    columns below (``secondary_contact_email``, ``renewal_notes``,
    ``parent_company_ref``, ``last_qbr_date``, ``tier_override_reason``,
    ``preferred_channel``, ``billing_contact``, ``support_plan``,
    ``onboarding_owner``, ``expansion_notes``), exactly 6 are blank on every
    row (60%, over the 40% floor) except Dockside, whose ``parent_company_ref``
    is deliberately the one populated field that names the acquiring
    parent -- the single structured causal link for Arc C1 (bible section
    2), leaving 5 blank there (50%, still over the floor).
    """

    account_id = crateworks_account_id(slug)
    is_dockside = slug == DOCKSIDE_SLUG
    optional = {
        "secondary_contact_email": "",
        "renewal_notes": "",
        "parent_company_ref": "crateworks-dockside-parent" if is_dockside else "",
        "last_qbr_date": "",
        "tier_override_reason": "",
        "preferred_channel": "email" if index % 3 == 0 else "",
        "billing_contact": "",
        "support_plan": "",
        "onboarding_owner": "",
        "expansion_notes": "",
    }
    return {
        "Account Name ": name,
        "acct_id": account_id,
        "OwnerId": csm_owner_id,
        "industry": "warehousing",
        "account_status": _STATUS_VARIANTS[index % len(_STATUS_VARIANTS)],
        "account_notes": (
            f"Crateworks WMS customer account, warehousing vertical. "
            f"Internal reference: {canary_token(TENANT, slug)}"
        ),
        **optional,
    }


def _contact_row(
    *,
    contact_id: str,
    account_id: str,
    name: str,
    email: str,
    title: str,
    last_touch: str,
) -> dict[str, Any]:
    return {
        "contact_id": contact_id,
        "AccountId": account_id,
        "full_name": name,
        "email_address": email,
        "title": title,
        "last_touch": last_touch,
    }


def _dockside_contact_rows(account_id: str) -> tuple[dict[str, Any], ...]:
    """Arc C1's identity mess (bible section 2): two duplicate contact rows
    for Dana Okafor, differently cased, neither carrying the later
    ``d.okafor@...parent...`` address (that address only ever appears in
    the ticket transport -- see comms.py -- so a perfect CRM dedupe alone
    would not resolve the identity)."""

    return (
        _contact_row(
            contact_id=det_id("contact", account_id, "dana-okafor-1"),
            account_id=account_id,
            name="Dana Okafor",
            email="dana.okafor@crateworks-dockside-fulfillment.example",
            title="VP Warehouse Ops",
            last_touch="2026-08-19",  # ~day 59, last healthy pre-fade touch
        ),
        _contact_row(
            contact_id=det_id("contact", account_id, "dana-okafor-2"),
            account_id=account_id,
            name="DANA OKAFOR",
            email="dana.okafor@crateworks-dockside-fulfillment.example",
            title="VP Warehouse Ops",
            last_touch="2026-08-19",
        ),
        # Bible section 3.4: one stale record, 3 years dead, no soft-delete.
        _contact_row(
            contact_id=det_id("contact", account_id, "stale-legacy-contact"),
            account_id=account_id,
            name="Harlan Voss",
            email="harlan.voss@crateworks-dockside-fulfillment.example",
            title="Former Ops Coordinator",
            last_touch=STALE_DATE,
        ),
    )


def _control_contact_rows(slug: str, account_id: str) -> tuple[dict[str, Any], ...]:
    name = _CONTROL_DUPLICATE_NAMES[slug]
    base_id = slug.replace("crateworks-", "")
    return (
        _contact_row(
            contact_id=det_id("contact", account_id, f"{base_id}-dup-1"),
            account_id=account_id,
            name=name,
            email=f"{name.split()[0].lower()}@{slug}.example",
            title="Operations Manager",
            last_touch="2026-09-01",
        ),
        _contact_row(
            contact_id=det_id("contact", account_id, f"{base_id}-dup-2"),
            account_id=account_id,
            name=_casefold_variant(name),
            email=f"{name.split()[0].lower()}@{slug}.example",
            title="Operations Manager",
            last_touch="2026-09-01",
        ),
        # Bible section 3.4: one stale record per account, every account.
        _contact_row(
            contact_id=det_id("contact", account_id, "stale-legacy-contact"),
            account_id=account_id,
            name=f"Legacy Contact ({base_id})",
            email=f"legacy@{slug}.example",
            title="Former Site Lead",
            last_touch=STALE_DATE,
        ),
    )


def _opportunity_row(*, opportunity_id: str, account_id: str, arr_cents: int) -> dict[str, Any]:
    return {
        "opp_id": opportunity_id,
        "account_ref": account_id,
        "stage": "Closed Won",
        "amount": arr_cents / 100.0,
        "close_date": "2026-01-15",
        "opp_type": "subscription",
    }


def build_flat_crateworks_book() -> FlatCrateworksBook:
    account_rows: list[dict[str, Any]] = []
    contact_rows: list[dict[str, Any]] = []
    opportunity_rows: list[dict[str, Any]] = []

    for index, (slug, name, arr_cents, csm_owner_id) in enumerate(ACCOUNTS):
        account_id = crateworks_account_id(slug)
        account_rows.append(_account_row(slug, name, arr_cents, csm_owner_id, index))
        if slug == DOCKSIDE_SLUG:
            contact_rows.extend(_dockside_contact_rows(account_id))
        else:
            contact_rows.extend(_control_contact_rows(slug, account_id))
        opportunity_rows.append(
            _opportunity_row(
                opportunity_id=det_id("opportunity", account_id, "subscription"),
                account_id=account_id,
                arr_cents=arr_cents,
            )
        )

    return FlatCrateworksBook(
        account_rows=tuple(account_rows),
        contact_rows=tuple(contact_rows),
        opportunity_rows=tuple(opportunity_rows),
    )


# ---------------------------------------------------------------------------
# Build the confirmed data plane by driving the raw rows through the real
# relational multi-table engine (``ingest_relational_book``,
# ``docs/PROGRAM_REPORT_3.md``'s proven join path) with a hand-authored, but
# HONEST, confirmed mapping: every mapping below is exactly what a human
# onboarding this source would confirm (identity fields, the display name,
# the FK join columns) -- the same confirmations
# ``eval/crateworks_onboarding.py``'s live driver arrives at by answering the
# real ``ingest_table``/``confirm_book`` confirmation questions, not a
# shortcut around them. Kept as a second, explicit call here (rather than
# reusing the mcp_server session dict) so this module has no import-time
# dependency on mcp_server's global relay-session state.
# ---------------------------------------------------------------------------


def _frozen_for_table(
    *,
    table_name: str,
    contract: str,
    records: tuple[dict[str, Any], ...],
    confirmations: dict[str, Any],
):
    """Propose, apply contract intent (the same
    ``mcp_server._apply_contract_intent`` every conversational onboarding
    session already runs through -- reused directly rather than
    reimplemented, so this fixture-build path can never silently diverge
    from what the live/relay MCP surface actually enforces), then freeze.

    ``confirmations`` supplies this table's OWN contract's answers; any
    other contract's proposed fields on this table are synthesized as
    ``not_mappable`` by ``_apply_contract_intent`` -- the hollow-records
    guard (``RELAY_CONTRACT_INTENT_CONFLICT`` in the MCP surface) that
    stops a contact/opportunity table's stray column from minting a
    phantom account, and vice versa.
    """

    from ultra_csm.data_plane.external_book import (
        ExternalSourceDescriptor,
        propose_external_source_mapping,
    )
    from ultra_csm.data_plane.source_mapping import freeze_confirmed_source_map
    from ultra_csm.mcp_server import _apply_contract_intent

    descriptor = ExternalSourceDescriptor(
        source_name=f"crateworks_{table_name}_export",
        expected_count=len(records),
        object_name=table_name,
    )
    _snapshot, proposal, _unrepr = propose_external_source_mapping(list(records), descriptor)
    intent_proposal, _demoted, synthesized = _apply_contract_intent(proposal, contract)
    frozen = freeze_confirmed_source_map(
        intent_proposal, confirmations={**synthesized, **confirmations}
    )
    return RelationalTable(
        table_name=table_name,
        records=records,
        frozen_map=frozen,
        expected_count=len(records),
    )


def _account_table(book: FlatCrateworksBook) -> RelationalTable:
    from ultra_csm.data_plane.source_mapping import MappingConfirmation

    confirmations = {
        "CRMAccount.account_id": MappingConfirmation(
            contract="CRMAccount", internal_field="account_id",
            source_object="accounts", source_field="acct_id", source_path="acct_id",
        ),
        "CRMAccount.name": MappingConfirmation(
            contract="CRMAccount", internal_field="name",
            source_object="accounts", source_field="Account Name ", source_path="Account Name ",
        ),
        "CRMAccount.owner_id": MappingConfirmation(
            contract="CRMAccount", internal_field="owner_id",
            source_object="accounts", source_field="OwnerId", source_path="OwnerId",
        ),
        "CRMAccount.industry": MappingConfirmation(
            contract="CRMAccount", internal_field="industry",
            source_object="accounts", source_field="industry", source_path="industry",
        ),
    }
    return _frozen_for_table(
        table_name="accounts",
        contract="CRMAccount",
        records=book.account_rows,
        confirmations=confirmations,
    )


def _contact_table(book: FlatCrateworksBook) -> RelationalTable:
    from ultra_csm.data_plane.source_mapping import MappingConfirmation

    confirmations = {
        "CRMContact.contact_id": MappingConfirmation(
            contract="CRMContact", internal_field="contact_id",
            source_object="contacts", source_field="contact_id", source_path="contact_id",
        ),
        "CRMContact.account_id": MappingConfirmation(
            contract="CRMContact", internal_field="account_id",
            source_object="contacts", source_field="AccountId", source_path="AccountId",
        ),
        "CRMContact.email": MappingConfirmation(
            contract="CRMContact", internal_field="email",
            source_object="contacts", source_field="email_address", source_path="email_address",
        ),
        "CRMContact.name": MappingConfirmation(
            contract="CRMContact", internal_field="name",
            source_object="contacts", source_field="full_name", source_path="full_name",
        ),
        "CRMContact.title": MappingConfirmation(
            contract="CRMContact", internal_field="title",
            source_object="contacts", source_field="title", source_path="title",
        ),
    }
    return _frozen_for_table(
        table_name="contacts",
        contract="CRMContact",
        records=book.contact_rows,
        confirmations=confirmations,
    )


def _opportunity_table(book: FlatCrateworksBook) -> RelationalTable:
    from ultra_csm.data_plane.source_mapping import MappingConfirmation

    confirmations = {
        "CRMOpportunity.opportunity_id": MappingConfirmation(
            contract="CRMOpportunity", internal_field="opportunity_id",
            source_object="opportunities", source_field="opp_id", source_path="opp_id",
        ),
        "CRMOpportunity.account_id": MappingConfirmation(
            contract="CRMOpportunity", internal_field="account_id",
            source_object="opportunities", source_field="account_ref", source_path="account_ref",
        ),
        "CRMOpportunity.stage_name": MappingConfirmation(
            contract="CRMOpportunity", internal_field="stage_name",
            source_object="opportunities", source_field="stage", source_path="stage",
        ),
        "CRMOpportunity.amount_cents": MappingConfirmation(
            contract="CRMOpportunity", internal_field="amount_cents",
            source_object="opportunities", source_field="amount", source_path="amount",
            transform="currency_to_cents",
        ),
        "CRMOpportunity.close_date": MappingConfirmation(
            contract="CRMOpportunity", internal_field="close_date",
            source_object="opportunities", source_field="close_date", source_path="close_date",
        ),
        "CRMOpportunity.opportunity_type": MappingConfirmation(
            contract="CRMOpportunity", internal_field="opportunity_type",
            source_object="opportunities", source_field="opp_type", source_path="opp_type",
        ),
    }
    return _frozen_for_table(
        table_name="opportunities",
        contract="CRMOpportunity",
        records=book.opportunity_rows,
        confirmations=confirmations,
    )


def build_crateworks_data_plane() -> CustomerDataPlane:
    """Assemble the full crateworks data plane (CRM only -- no CS platform,
    no product telemetry, per bible section 0) from the flat book, routed
    through ``ingest_relational_book`` (Program 3's relational-multi-table
    join engine) so contacts/opportunities join to accounts by a real,
    confirmed foreign key exactly as a normalized read of this export
    would, rather than hand-assembling ``CRMContact``/``CRMOpportunity``
    dataclasses directly."""

    book = build_flat_crateworks_book()
    result = ingest_relational_book(
        (
            _account_table(book),
            _contact_table(book),
            _opportunity_table(book),
        )
    )
    data: FixtureCustomerData = result.data
    return CustomerDataPlane(
        crm=FixtureCRMDataConnector(tenant=TENANT, data=data),
        cs=FixtureCSPlatformConnector(data=data),
        telemetry=FixtureProductTelemetryConnector(data=data),
    )
