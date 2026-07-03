from __future__ import annotations

from dataclasses import replace
import inspect
import re

from eval.salesforce_simulated_onboarding import (
    API_VERSION,
    BASE_URL,
    FakeSalesforceClient,
    build_salesforce_fixture_payloads,
    build_salesforce_simulated_onboarding_artifact,
)
from ultra_csm.data_plane.explorer import run_explorer
from ultra_csm.data_plane.salesforce_live import (
    DEFAULT_ROW_CAP,
    SalesforceReadError,
    audit_distinct_identity_paths,
    fetch_salesforce_book,
)
from ultra_csm.data_plane.source_mapping import (
    MappingConfirmation,
    freeze_confirmed_source_map,
    load_mapping_confirmations,
)
from ultra_csm.data_plane.synthetic_book import build_synthetic_book


def test_salesforce_simulated_onboarding_runs_full_pipeline_without_live_claims(tmp_path):
    artifact = build_salesforce_simulated_onboarding_artifact(
        output_path=tmp_path / "salesforce_simulated_onboarding.json",
        row_cap=5,
    )

    assert artifact["claim_boundary"] == {
        "sim": True,
        "live": False,
        "uses_live_credentials": False,
        "live_tenant_proven": False,
        "read_only": True,
    }
    assert artifact["credential_boundary"]["requests_without_credentials"] == 0
    assert artifact["credential_boundary"]["missing_env"] == [
        "ULTRA_CSM_SALESFORCE_INSTANCE_URL",
        "ULTRA_CSM_SALESFORCE_CLIENT_ID",
        "ULTRA_CSM_SALESFORCE_CLIENT_SECRET",
        "ULTRA_CSM_SALESFORCE_REFRESH_TOKEN",
    ]
    assert artifact["discovery"]["ok"] is True
    assert artifact["readiness"]["mode"] == "fixture"
    assert artifact["readiness"]["connected"] is False
    assert artifact["readiness_report"]["sources"] == {"salesforce_crm": "fixture_verified"}
    assert artifact["coverage"]["records_typed"]["CRMAccount"] == 5
    assert artifact["coverage"]["truncated"] is True
    assert artifact["coverage"]["source_totals"]["CRMAccount"]["totalSize"] == 35
    assert artifact["coverage"]["source_totals"]["CRMAccount"]["fetched_count"] == 5


def test_salesforce_fetch_uses_direct_token_without_oauth_and_queries_mapped_fields_only():
    book = build_synthetic_book()
    payloads = build_salesforce_fixture_payloads(book)
    env = {
        "ULTRA_CSM_SALESFORCE_INSTANCE_URL": BASE_URL,
        "ULTRA_CSM_SALESFORCE_ACCESS_TOKEN": "short-lived-token",
        "ULTRA_CSM_SALESFORCE_API_VERSION": API_VERSION,
    }
    explorer_client = FakeSalesforceClient(payloads)
    discovered = run_explorer("salesforce_crm", env=env, client=explorer_client)
    confirmations = load_mapping_confirmations("eval/salesforce_simulated_confirmations.json")
    frozen = freeze_confirmed_source_map(
        discovered.mapping_proposal,
        confirmations=confirmations,
    )
    fetch_client = FakeSalesforceClient(payloads)

    result = fetch_salesforce_book(
        frozen,
        env=env,
        client=fetch_client,
        row_cap=3,
    )

    assert result.auth_source == "direct_access_token"
    assert all(request.method == "GET" for request in fetch_client.requests)
    queries = [
        details["query"]
        for details in result.coverage.source_totals.values()
    ]
    assert all("SELECT FIELDS(ALL)" not in query for query in queries)
    assert "SELECT Id, Industry, Name, OwnerId FROM Account LIMIT 3" in queries
    assert result.coverage.records_typed["CRMAccount"] == 3
    assert result.coverage.source_totals["CRMContact"]["truncated"] is True


def test_salesforce_identity_audit_rejects_primary_identity_coordinate_collision():
    book = build_synthetic_book()
    payloads = build_salesforce_fixture_payloads(book)
    env = {
        "ULTRA_CSM_SALESFORCE_INSTANCE_URL": BASE_URL,
        "ULTRA_CSM_SALESFORCE_ACCESS_TOKEN": "short-lived-token",
        "ULTRA_CSM_SALESFORCE_API_VERSION": API_VERSION,
    }
    discovered = run_explorer("salesforce_crm", env=env, client=FakeSalesforceClient(payloads))
    confirmations = load_mapping_confirmations("eval/salesforce_simulated_confirmations.json")
    confirmations = {
        **confirmations,
        "CRMContact.contact_id": MappingConfirmation(
            contract="CRMContact",
            internal_field="contact_id",
            source_object="Account",
            source_field="Id",
            source_path="Id",
            semantic_role="identity_join",
            verdict="mapped",
        ),
    }
    proposal = discovered.mapping_proposal
    entries = []
    for entry in proposal.entries:
        if entry.key == "CRMContact.contact_id":
            entries.append(
                replace(
                    entry,
                    state="ambiguous_confirm",
                    requires_human_confirmation=True,
                )
            )
        else:
            entries.append(entry)
    proposal = proposal.__class__(
        connector_id=proposal.connector_id,
        schema_hash=proposal.schema_hash,
        proposal_hash=proposal.proposal_hash,
        entries=tuple(entries),
        coverage=proposal.coverage,
        required_operator_actions=proposal.required_operator_actions,
    )
    frozen = freeze_confirmed_source_map(proposal, confirmations=confirmations)

    try:
        audit_distinct_identity_paths(frozen)
    except SalesforceReadError as exc:
        assert "identity confirmation collision" in str(exc)
    else:
        raise AssertionError("expected identity confirmation collision")


def test_salesforce_live_module_has_no_write_surface():
    import ultra_csm.data_plane.salesforce_live as salesforce_live

    source = inspect.getsource(salesforce_live)

    assert "PATCH" not in source
    assert "DELETE" not in source
    assert not re.search(r"def\s+(create|update|delete)", source)
    assert DEFAULT_ROW_CAP <= 200
