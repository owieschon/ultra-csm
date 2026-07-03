"""Read-only Salesforce onboarding fetch path.

The live boundary here is intentionally narrow: authenticate, describe/query via
GET, transform records into typed CRM contracts, and report coverage. No sObject
mutation surface is implemented in this module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Callable, Mapping
from urllib import parse

from ultra_csm.data_plane.adapters.salesforce import (
    next_records_url,
    parse_account,
    parse_case,
    parse_contact,
    parse_opportunity,
)
from ultra_csm.data_plane.contracts import (
    CRMAccount,
    CRMCase,
    CRMContact,
    CRMOpportunity,
)
from ultra_csm.data_plane.explorer import ExplorerResult, run_explorer
from ultra_csm.data_plane.external_book import ExternalCoverageReport, RejectedRecord
from ultra_csm.data_plane.fixtures import DEFAULT_TENANT, FixtureCustomerData
from ultra_csm.data_plane.live_smoke import HttpClient, HttpRequest, UrllibHttpClient, _env
from ultra_csm.data_plane.source_mapping import (
    FrozenSourceMapConfig,
    MappingConfirmation,
    ProposedFieldMapping,
    freeze_confirmed_source_map,
)
from ultra_csm.data_plane.transforms import TransformError

DEFAULT_ROW_CAP = 200
MAX_ROW_CAP = 2_000
_FIELD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?$")
_PRIMARY_IDENTITY_FIELDS = {
    "CRMAccount": "account_id",
    "CRMContact": "contact_id",
    "CRMCase": "case_id",
    "CRMOpportunity": "opportunity_id",
}


class SalesforceReadError(RuntimeError):
    """A read-only Salesforce operation failed."""


@dataclass(frozen=True)
class SalesforceAuth:
    instance_url: str
    api_version: str
    access_token: str
    auth_source: str
    auth_steps: tuple[str, ...]


@dataclass(frozen=True)
class SalesforceObjectFetch:
    contract: str
    source_object: str
    query: str
    total_size: int
    fetched_count: int
    row_cap: int
    truncated: bool
    request_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SalesforceBookResult:
    frozen_map: FrozenSourceMapConfig
    data: FixtureCustomerData
    coverage: ExternalCoverageReport
    briefing: tuple[str, ...]
    fetches: tuple[SalesforceObjectFetch, ...]
    auth_source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "frozen_map": self.frozen_map.to_dict(),
            "coverage": self.coverage.to_dict(),
            "briefing": list(self.briefing),
            "fetches": [fetch.to_dict() for fetch in self.fetches],
            "auth_source": self.auth_source,
        }


@dataclass(frozen=True)
class SalesforceOnboardingResult:
    discovery: ExplorerResult
    book: SalesforceBookResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "discovery": {
                "ok": self.discovery.ok,
                "steps": list(self.discovery.steps),
                "errors": list(self.discovery.errors),
                "schema_hash": (
                    self.discovery.snapshot.schema_hash
                    if self.discovery.snapshot
                    else None
                ),
                "mapping_proposal": (
                    self.discovery.mapping_proposal.to_dict()
                    if self.discovery.mapping_proposal
                    else None
                ),
            },
            "book": self.book.to_dict(),
        }


_Parser = Callable[[dict[str, Any]], CRMAccount | CRMContact | CRMCase | CRMOpportunity]
_PARSERS: dict[str, _Parser] = {
    "CRMAccount": parse_account,
    "CRMContact": parse_contact,
    "CRMCase": parse_case,
    "CRMOpportunity": parse_opportunity,
}


def salesforce_auth_from_env(
    env: Mapping[str, str],
    *,
    client: HttpClient | None = None,
) -> SalesforceAuth:
    instance = _env(env, "ULTRA_CSM_SALESFORCE_INSTANCE_URL").rstrip("/")
    api_version = env.get("ULTRA_CSM_SALESFORCE_API_VERSION", "v61.0")
    direct = env.get("ULTRA_CSM_SALESFORCE_ACCESS_TOKEN")
    if direct:
        return SalesforceAuth(
            instance_url=instance,
            api_version=api_version,
            access_token=direct,
            auth_source="direct_access_token",
            auth_steps=(),
        )

    http = client or UrllibHttpClient()
    login_url = env.get("ULTRA_CSM_SALESFORCE_LOGIN_URL", "https://login.salesforce.com").rstrip("/")
    body = parse.urlencode(
        {
            "grant_type": "refresh_token",
            "client_id": _env(env, "ULTRA_CSM_SALESFORCE_CLIENT_ID"),
            "client_secret": _env(env, "ULTRA_CSM_SALESFORCE_CLIENT_SECRET"),
            "refresh_token": _env(env, "ULTRA_CSM_SALESFORCE_REFRESH_TOKEN"),
        }
    ).encode("utf-8")
    response = http.send(
        HttpRequest(
            "POST",
            f"{login_url}/services/oauth2/token",
            {"content-type": "application/x-www-form-urlencoded"},
            body=body,
        )
    )
    if response.status != 200:
        raise SalesforceReadError(f"oauth_refresh unexpected status {response.status}")
    raw = response.json()
    if not isinstance(raw, dict) or not isinstance(raw.get("access_token"), str):
        raise SalesforceReadError("oauth_refresh missing access_token")
    return SalesforceAuth(
        instance_url=instance,
        api_version=api_version,
        access_token=raw["access_token"],
        auth_source="oauth_refresh",
        auth_steps=("oauth_refresh",),
    )


def preflight_salesforce_versions(
    env: Mapping[str, str],
    *,
    client: HttpClient | None = None,
) -> dict[str, Any]:
    auth = salesforce_auth_from_env(env, client=client)
    http = client or UrllibHttpClient()
    response = http.send(
        HttpRequest(
            "GET",
            f"{auth.instance_url}/services/data",
            _auth_headers(auth),
        )
    )
    return {
        "ok": response.status == 200,
        "status": response.status,
        "auth_source": auth.auth_source,
        "business_data_touched": False,
    }


def run_salesforce_onboarding(
    *,
    env: Mapping[str, str],
    confirmations: Mapping[str, MappingConfirmation],
    client: HttpClient | None = None,
    row_cap: int = DEFAULT_ROW_CAP,
) -> SalesforceOnboardingResult:
    discovery = run_explorer("salesforce_crm", env=env, client=client)
    if not discovery.ok or discovery.mapping_proposal is None:
        raise SalesforceReadError(f"salesforce discovery failed: {discovery.errors}")
    frozen = freeze_confirmed_source_map(
        discovery.mapping_proposal,
        confirmations=confirmations,
    )
    audit_distinct_identity_paths(frozen)
    return SalesforceOnboardingResult(
        discovery=discovery,
        book=fetch_salesforce_book(
            frozen,
            env=env,
            client=client,
            row_cap=row_cap,
        ),
    )


def fetch_salesforce_book(
    frozen_map: FrozenSourceMapConfig,
    *,
    env: Mapping[str, str],
    client: HttpClient | None = None,
    row_cap: int = DEFAULT_ROW_CAP,
) -> SalesforceBookResult:
    if frozen_map.connector_id != "salesforce_crm":
        raise SalesforceReadError("frozen map is not for salesforce_crm")
    audit_distinct_identity_paths(frozen_map)
    capped = _row_cap(row_cap)
    http = client or UrllibHttpClient()
    auth = salesforce_auth_from_env(env, client=http)
    mapped = _mapping_index(frozen_map.mappings)
    accounts: list[CRMAccount] = []
    contacts: list[CRMContact] = []
    cases: list[CRMCase] = []
    opportunities: list[CRMOpportunity] = []
    rejected: list[RejectedRecord] = []
    fetches: list[SalesforceObjectFetch] = []

    for contract, parser in _PARSERS.items():
        contract_mappings = mapped.get(contract, {})
        if not contract_mappings:
            continue
        source_object = _single_source_object(contract, contract_mappings)
        query = build_soql(contract_mappings.values(), source_object=source_object, row_cap=capped)
        raw_records, fetch = _query_records(
            http,
            auth,
            contract=contract,
            source_object=source_object,
            query=query,
            row_cap=capped,
        )
        fetches.append(fetch)
        for offset, record in enumerate(raw_records, start=1):
            try:
                parsed = parser(record)
            except TransformError as exc:
                rejected.append(RejectedRecord(offset, str(exc), contract))
                continue
            if contract == "CRMAccount":
                accounts.append(parsed)  # type: ignore[arg-type]
            elif contract == "CRMContact":
                contacts.append(parsed)  # type: ignore[arg-type]
            elif contract == "CRMCase":
                cases.append(parsed)  # type: ignore[arg-type]
            elif contract == "CRMOpportunity":
                opportunities.append(parsed)  # type: ignore[arg-type]

    account_ids = {account.account_id for account in accounts}
    joined_contacts = sum(1 for contact in contacts if contact.account_id in account_ids)
    total_size = sum(fetch.total_size for fetch in fetches)
    fetched_count = sum(fetch.fetched_count for fetch in fetches)
    source_totals = {
        fetch.contract: {
            "source_object": fetch.source_object,
            "totalSize": fetch.total_size,
            "fetched_count": fetch.fetched_count,
            "row_cap": fetch.row_cap,
            "truncated": fetch.truncated,
            "query": fetch.query,
        }
        for fetch in fetches
    }
    coverage = ExternalCoverageReport(
        records_received=total_size,
        records_processed=fetched_count,
        records_typed={
            "CRMAccount": len(accounts),
            "CRMContact": len(contacts),
            "CRMCase": len(cases),
            "CRMOpportunity": len(opportunities),
        },
        records_rejected=tuple(rejected),
        rejection_counts=_rejection_counts(rejected),
        field_coverage=_field_coverage(frozen_map),
        join_coverage={
            "contact_candidates": len(contacts),
            "contacts_joined": joined_contacts,
            "ratio": round(joined_contacts / len(contacts), 4) if contacts else None,
        },
        unknown_fields=frozen_map.unknown_fields,
        unrepresentable_paths=(),
        duplicate_identities=_duplicate_identities(accounts, contacts, cases, opportunities),
        expected_count=None,
        count_mismatch=False,
        truncated=any(fetch.truncated for fetch in fetches),
        dropped_record_count=sum(
            max(0, fetch.total_size - fetch.fetched_count)
            for fetch in fetches
        ),
        injection_marker_count=0,
        source_totals=source_totals,
    )
    data = FixtureCustomerData(
        accounts=tuple(accounts),
        companies=(),
        contacts=tuple(contacts),
        cases=tuple(cases),
        opportunities=tuple(opportunities),
        health_scores=(),
        ctas=(),
        success_plans=(),
        adoption_summaries=(),
        entitlements=(),
        usage_signals=(),
        milestones=(),
        tenant_accounts={DEFAULT_TENANT: tuple(sorted(account_ids))},
    )
    return SalesforceBookResult(
        frozen_map=frozen_map,
        data=data,
        coverage=coverage,
        briefing=_briefing(coverage),
        fetches=tuple(fetches),
        auth_source=auth.auth_source,
    )


def build_soql(
    mappings: Any,
    *,
    source_object: str,
    row_cap: int = DEFAULT_ROW_CAP,
) -> str:
    fields = sorted({
        _safe_field(mapping.source_path or mapping.source_field)
        for mapping in mappings
        if mapping.source_path or mapping.source_field
    })
    if not fields:
        raise SalesforceReadError(f"{source_object}: no mapped fields to query")
    return f"SELECT {', '.join(fields)} FROM {_safe_field(source_object)} LIMIT {_row_cap(row_cap)}"


def audit_distinct_identity_paths(config: FrozenSourceMapConfig) -> None:
    seen: dict[tuple[str, str], str] = {}
    for mapping in config.mappings:
        if _PRIMARY_IDENTITY_FIELDS.get(mapping.contract) != mapping.internal_field:
            continue
        if not mapping.source_object or not mapping.source_path:
            continue
        key = (mapping.source_object, mapping.source_path)
        other = seen.get(key)
        if other is not None:
            raise SalesforceReadError(
                "identity confirmation collision: "
                f"{other} and {mapping.key} both use {mapping.source_object}.{mapping.source_path}"
            )
        seen[key] = mapping.key


def _query_records(
    http: HttpClient,
    auth: SalesforceAuth,
    *,
    contract: str,
    source_object: str,
    query: str,
    row_cap: int,
) -> tuple[list[dict[str, Any]], SalesforceObjectFetch]:
    records: list[dict[str, Any]] = []
    total_size = 0
    request_count = 0
    url = (
        f"{auth.instance_url}/services/data/{auth.api_version}/query?"
        f"q={parse.quote(query, safe='')}"
    )
    while url and len(records) < row_cap:
        response = http.send(HttpRequest("GET", url, _auth_headers(auth)))
        request_count += 1
        if response.status != 200:
            raise SalesforceReadError(f"{contract}: query unexpected status {response.status}")
        raw = response.json()
        if not isinstance(raw, dict):
            raise SalesforceReadError(f"{contract}: query payload was not an object")
        if request_count == 1:
            total_size = _int(raw.get("totalSize"), default=0)
        page_records = raw.get("records")
        if not isinstance(page_records, list):
            raise SalesforceReadError(f"{contract}: query payload missing records")
        remaining = row_cap - len(records)
        records.extend(
            item for item in page_records[:remaining] if isinstance(item, dict)
        )
        next_url = next_records_url(raw)
        url = f"{auth.instance_url}{next_url}" if next_url and len(records) < row_cap else ""
    fetched = len(records)
    truncated = total_size > fetched or bool(url)
    return records, SalesforceObjectFetch(
        contract=contract,
        source_object=source_object,
        query=query,
        total_size=total_size,
        fetched_count=fetched,
        row_cap=row_cap,
        truncated=truncated,
        request_count=request_count,
    )


def _auth_headers(auth: SalesforceAuth) -> dict[str, str]:
    return {
        "accept": "application/json",
        "authorization": f"Bearer {auth.access_token}",
    }


def _row_cap(value: int) -> int:
    return min(MAX_ROW_CAP, max(1, int(value)))


def _safe_field(value: str | None) -> str:
    if value is None or not _FIELD_RE.fullmatch(value):
        raise SalesforceReadError(f"unsafe Salesforce field/object name: {value!r}")
    return value


def _mapping_index(
    mappings: tuple[ProposedFieldMapping, ...],
) -> dict[str, dict[str, ProposedFieldMapping]]:
    index: dict[str, dict[str, ProposedFieldMapping]] = {}
    for mapping in mappings:
        index.setdefault(mapping.contract, {})[mapping.internal_field] = mapping
    return index


def _single_source_object(
    contract: str,
    mappings: Mapping[str, ProposedFieldMapping],
) -> str:
    objects = {
        mapping.source_object
        for mapping in mappings.values()
        if mapping.source_object
    }
    if len(objects) != 1:
        raise SalesforceReadError(f"{contract}: expected one Salesforce object, got {sorted(objects)}")
    return _safe_field(next(iter(objects)))


def _field_coverage(config: FrozenSourceMapConfig) -> dict[str, dict[str, int]]:
    coverage: dict[str, dict[str, int]] = {}
    for mapping in config.mappings:
        bucket = coverage.setdefault(mapping.contract, {"mapped": 0})
        bucket["mapped"] += 1
    for unknown in config.unknown_fields:
        contract = unknown.split(".", 1)[0]
        bucket = coverage.setdefault(contract, {"mapped": 0})
        bucket["unknown"] = bucket.get("unknown", 0) + 1
    return coverage


def _rejection_counts(rejected: list[RejectedRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in rejected:
        counts[item.reason] = counts.get(item.reason, 0) + 1
    return dict(sorted(counts.items()))


def _duplicate_identities(
    accounts: list[CRMAccount],
    contacts: list[CRMContact],
    cases: list[CRMCase],
    opportunities: list[CRMOpportunity],
) -> tuple[str, ...]:
    duplicates: list[str] = []
    for label, values in (
        ("CRMAccount", [item.account_id for item in accounts]),
        ("CRMContact", [item.contact_id for item in contacts]),
        ("CRMCase", [item.case_id for item in cases]),
        ("CRMOpportunity", [item.opportunity_id for item in opportunities]),
    ):
        seen: set[str] = set()
        for value in values:
            if value in seen:
                duplicates.append(f"{label}:{value}")
            seen.add(value)
    return tuple(sorted(duplicates))


def _briefing(coverage: ExternalCoverageReport) -> tuple[str, ...]:
    if coverage.records_processed == 0:
        return ("Salesforce fetch returned no CRM records; no account was invented.",)
    return (
        (
            "Salesforce fetch typed "
            f"{coverage.records_typed.get('CRMAccount', 0)} CRM accounts from "
            f"{coverage.records_processed} fetched records."
        ),
        (
            "Salesforce CRM alone does not provide CS-platform health or product "
            "telemetry; value-model rails that require those sources remain unknown."
        ),
    )


def _int(value: object, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
