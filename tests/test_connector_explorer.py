"""Schema explorer behavior for connector onboarding."""

from __future__ import annotations

import json

from ultra_csm.cli import main
from ultra_csm.data_plane.explorer import run_explorer
from ultra_csm.data_plane.live_smoke import HttpRequest, HttpResponse
from ultra_csm.data_plane.source_mapping import (
    MappingConfirmation,
    freeze_confirmed_source_map,
)


class RoutedClient:
    def __init__(self, routes: dict[str, dict]):
        self.routes = routes
        self.requests: list[HttpRequest] = []

    def send(self, req: HttpRequest) -> HttpResponse:
        self.requests.append(req)
        payload = self.routes.get(req.url, {})
        return HttpResponse(
            status=200,
            body=json.dumps(payload).encode("utf-8"),
            headers={},
        )


def test_explorer_reports_missing_credentials_without_network():
    client = RoutedClient({})

    result = run_explorer("attio_crm", env={}, client=client)

    assert result.ok is False
    assert result.readiness.state == "shape_verified_pending_live_creds"
    assert result.missing_env == ("ULTRA_CSM_ATTIO_ACCESS_TOKEN",)
    assert client.requests == []


def test_attio_explorer_discovers_objects_attributes_and_samples():
    client = RoutedClient(
        {
            "https://api.attio.com/v2/self": {"workspace": {"slug": "demo"}},
            "https://api.attio.com/v2/objects": {
                "data": [
                    {"api_slug": "companies", "singular_noun": "Company"},
                    {"api_slug": "people", "singular_noun": "Person"},
                ]
            },
            "https://api.attio.com/v2/objects/companies/attributes": {
                "data": [
                    {
                        "api_slug": "id",
                        "type": "text",
                        "is_required": True,
                        "is_system_attribute": True,
                    },
                    {
                        "api_slug": "name",
                        "type": "text",
                        "is_required": True,
                        "is_system_attribute": True,
                    }
                ]
            },
            "https://api.attio.com/v2/objects/people/attributes": {
                "data": [
                    {
                        "api_slug": "id",
                        "type": "text",
                        "is_required": True,
                        "is_system_attribute": True,
                    },
                    {
                        "api_slug": "email_addresses",
                        "type": "email-address",
                        "is_required": False,
                        "is_system_attribute": True,
                    }
                ]
            },
            "https://api.attio.com/v2/objects/companies/records/query": {"data": [{}]},
            "https://api.attio.com/v2/objects/people/records/query": {"data": [{}, {}]},
        }
    )

    result = run_explorer(
        "attio_crm",
        env={"ULTRA_CSM_ATTIO_ACCESS_TOKEN": "token"},
        client=client,
    )

    assert result.ok is True
    assert result.readiness.state == "live_schema_verified"
    assert result.snapshot.schema_hash.startswith("sha256:")
    assert result.snapshot.sample_counts["companies_sample"] == 1
    assert result.snapshot.sample_counts["people_sample"] == 2
    fields_by_object = {
        obj.name: {field.name for field in obj.fields}
        for obj in result.snapshot.objects
    }
    assert fields_by_object["companies"] == {"id", "name"}
    assert fields_by_object["people"] == {"id", "email_addresses"}
    assert result.mapping_proposal is not None
    entries = _entries_by_key(result.mapping_proposal)
    assert entries["CRMAccount.name"].state == "mapped"
    assert entries["CRMContact.email"].state == "mapped"
    assert entries["CRMContact.email"].llm_allowed is False
    assert result.mapping_proposal.coverage["mapped"] >= 4


def test_salesforce_explorer_uses_oauth_token_and_describes_objects():
    instance = "https://example.my.salesforce.com"
    routes = {
        "https://login.salesforce.com/services/oauth2/token": {"access_token": "access-token"},
        f"{instance}/services/data/v61.0/sobjects/": {
            "sobjects": [
                {"name": "Account", "label": "Account"},
                {"name": "Contact", "label": "Contact"},
            ]
        },
    }
    for object_name in ("Account", "Contact", "Case", "Opportunity", "Task", "Event"):
        routes[f"{instance}/services/data/v61.0/sobjects/{object_name}/describe"] = {
            "name": object_name,
            "label": object_name,
            "fields": [
                {
                    "name": "Id",
                    "type": "id",
                    "nillable": False,
                    "custom": False,
                },
                {
                    "name": "Name",
                    "type": "string",
                    "nillable": False,
                    "custom": False,
                },
                {
                    "name": f"{object_name}_Custom__c",
                    "type": "string",
                    "nillable": True,
                    "custom": True,
                },
            ],
        }
    client = RoutedClient(routes)

    result = run_explorer(
        "salesforce_crm",
        env={
            "ULTRA_CSM_SALESFORCE_INSTANCE_URL": instance,
            "ULTRA_CSM_SALESFORCE_CLIENT_ID": "client",
            "ULTRA_CSM_SALESFORCE_CLIENT_SECRET": "secret",
            "ULTRA_CSM_SALESFORCE_REFRESH_TOKEN": "refresh",
            "ULTRA_CSM_SALESFORCE_API_VERSION": "v61.0",
        },
        client=client,
    )

    assert result.ok is True
    assert "oauth_refresh" in result.steps
    assert client.requests[1].headers["authorization"] == "Bearer access-token"
    discovered = {obj.name: obj for obj in result.snapshot.objects}
    assert {"Account", "Contact", "Case", "Opportunity", "Task", "Event"} <= set(discovered)
    assert any(field.name == "Id" and field.required for field in discovered["Account"].fields)
    entries = _entries_by_key(result.mapping_proposal)
    assert entries["CRMAccount.account_id"].state == "mapped"
    assert entries["CRMAccount.name"].state == "mapped"
    custom = [
        entry
        for entry in result.mapping_proposal.entries
        if entry.contract == "__tenant_custom__"
    ]
    assert custom == []


def test_gainsight_explorer_discovers_tenant_metadata_objects():
    base = "https://tenant.gainsightcloud.com"
    client = RoutedClient(
        {
            f"{base}/v1/meta/services/objects/Company/describe?ic=true&cl=3&idd=true": {
                "data": {
                    "objectName": "Company",
                    "fields": [
                        {"fieldName": "Gsid", "dataType": "GSID", "required": True},
                        {"fieldName": "CurrentScore", "dataType": "Number"},
                        {"fieldName": "Health Direction", "dataType": "String", "custom": True},
                    ],
                }
            }
        }
    )

    result = run_explorer(
        "gainsight_cs",
        env={
            "ULTRA_CSM_GAINSIGHT_DOMAIN": base,
            "ULTRA_CSM_GAINSIGHT_TOKEN": "token",
            "ULTRA_CSM_GAINSIGHT_DISCOVERY_OBJECTS": "Company",
        },
        client=client,
    )

    assert result.ok is True
    company = result.snapshot.objects[0]
    assert company.name == "Company"
    assert {field.name for field in company.fields} == {
        "Gsid",
        "CurrentScore",
        "Health Direction",
    }
    entries = _entries_by_key(result.mapping_proposal)
    assert entries["CSCompany.current_score"].state == "ambiguous_confirm"
    assert entries["CSCompany.current_score"].value_direction == "direction_confirm"
    assert entries["CSCompany.current_score"].requires_human_confirmation is True
    custom = [
        entry
        for entry in result.mapping_proposal.entries
        if entry.source_field == "Health Direction"
    ]
    assert custom[0].state == "ambiguous_confirm"
    assert custom[0].semantic_role == "health_signal"


def test_rocketlane_explorer_discovers_fields_and_sample_shapes():
    base = "https://api.rocketlane.com/api/1.0"
    client = RoutedClient(
        {
            f"{base}/fields?pageSize=100": {
                "data": [
                    {
                        "objectType": "PROJECT",
                        "fieldName": "Implementation Tier",
                        "fieldType": "SINGLE_SELECT",
                    }
                ]
            },
            f"{base}/projects?pageSize=1&includeAllFields=true": {
                "data": [{"projectId": 1, "inferredProgress": "RUNNING_LATE"}]
            },
            f"{base}/phases?pageSize=1": {"data": [{"phaseId": 2, "status": "OPEN"}]},
            f"{base}/tasks?pageSize=1": {"data": [{"taskId": 3, "atRisk": True}]},
        }
    )

    result = run_explorer(
        "rocketlane_onboarding",
        env={"ULTRA_CSM_ROCKETLANE_API_KEY": "token"},
        client=client,
    )

    assert result.ok is True
    objects = {obj.name: obj for obj in result.snapshot.objects}
    assert "PROJECT" in objects
    assert "Project" in objects
    assert "Task" in objects
    entries = _entries_by_key(result.mapping_proposal)
    assert entries["TimeToValueMilestone.evidence_signal_ids"].state == "mapped"
    assert entries["TimeToValueMilestone.expected_by"].value_direction == "lower_is_better"


def test_telemetry_explorer_discovers_metric_catalog():
    client = RoutedClient(
        {
            "http://localhost:4318": {},
            "https://telemetry.example/catalog": {
                "metrics": [
                    {"name": "ultra_csm.product.usage.value", "unit": "count"},
                    {"name": "ultra_csm.product.entitlement.quantity", "unit": "count"},
                ]
            },
        }
    )

    result = run_explorer(
        "product_telemetry",
        env={
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
            "ULTRA_CSM_TELEMETRY_CATALOG_URL": "https://telemetry.example/catalog",
        },
        client=client,
    )

    assert result.ok is True
    required, catalog = result.snapshot.objects
    assert required.name == "OTelRequiredAttributes"
    assert catalog.name == "OTelMetricCatalog"
    assert {field.name for field in catalog.fields} == {
        "ultra_csm.product.usage.value",
        "ultra_csm.product.entitlement.quantity",
    }
    assert result.mapping_proposal.coverage["mapped"] >= 4
    assert result.mapping_proposal.coverage["missing_to_unknown"] >= 1


def test_telemetry_explorer_without_catalog_url_returns_required_attribute_contract():
    client = RoutedClient({"http://localhost:4318": {}})

    result = run_explorer(
        "product_telemetry",
        env={"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318"},
        client=client,
    )

    assert result.ok is True
    assert [req.url for req in client.requests] == ["http://localhost:4318"]
    assert result.snapshot.objects[0].name == "OTelRequiredAttributes"


def test_connector_explore_cli_reports_missing_credentials(capsys):
    code = main(["connectors", "explore", "gainsight_cs", "--json"])

    captured = capsys.readouterr()

    assert code == 2
    assert '"connector_id": "gainsight_cs"' in captured.out
    assert "ULTRA_CSM_GAINSIGHT_DOMAIN" in captured.out


def test_connector_explore_cli_dry_run_lists_requests(monkeypatch, capsys):
    monkeypatch.setenv("ULTRA_CSM_ATTIO_ACCESS_TOKEN", "token")

    code = main(["connectors", "explore", "attio_crm", "--dry-run"])

    captured = capsys.readouterr()

    assert code == 0
    assert "attio_crm: shape_verified_pending_live_creds" in captured.out
    assert "would request: https://api.attio.com/v2/objects" in captured.out


def test_freeze_confirmed_source_map_rejects_unconfirmed_semantic_mapping():
    result = _gainsight_company_result()
    proposal = result.mapping_proposal

    try:
        freeze_confirmed_source_map(proposal)
    except ValueError as exc:
        assert "CSCompany.current_score requires human confirmation" in str(exc)
    else:  # pragma: no cover - assertion clarity.
        raise AssertionError("unconfirmed semantic mapping should fail")

    config = freeze_confirmed_source_map(
        proposal,
        confirmations={
            "CSCompany.current_score": MappingConfirmation(
                contract="CSCompany",
                internal_field="current_score",
                source_object="Company",
                source_field="CurrentScore",
                source_path="CurrentScore",
                semantic_role="health_signal",
                value_direction="higher_is_better",
            ),
            "__tenant_custom__.health_direction": MappingConfirmation(
                contract="__tenant_custom__",
                internal_field="health_direction",
                source_object="Company",
                source_field="Health Direction",
                source_path="Health Direction",
                semantic_role="health_signal",
                value_direction="higher_is_better",
            ),
        },
    )

    assert config.config_hash.startswith("sha256:")
    assert {
        mapping.key
        for mapping in config.mappings
        if mapping.source_field == "CurrentScore"
    } == {"CSCompany.current_score"}


def _entries_by_key(proposal):
    return {entry.key: entry for entry in proposal.entries}


def _gainsight_company_result():
    base = "https://tenant.gainsightcloud.com"
    client = RoutedClient(
        {
            f"{base}/v1/meta/services/objects/Company/describe?ic=true&cl=3&idd=true": {
                "data": {
                    "objectName": "Company",
                    "fields": [
                        {"fieldName": "Gsid", "dataType": "GSID", "required": True},
                        {"fieldName": "CurrentScore", "dataType": "Number"},
                        {"fieldName": "Health Direction", "dataType": "String", "custom": True},
                    ],
                }
            }
        }
    )
    return run_explorer(
        "gainsight_cs",
        env={
            "ULTRA_CSM_GAINSIGHT_DOMAIN": base,
            "ULTRA_CSM_GAINSIGHT_TOKEN": "token",
            "ULTRA_CSM_GAINSIGHT_DISCOVERY_OBJECTS": "Company",
        },
        client=client,
    )
