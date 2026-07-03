"""Official-doc-grounded connector catalog."""

from __future__ import annotations

from ultra_csm.data_plane.readiness import ConnectorSpec, OfficialDocRef, RecordedShape

ACCESSED_ON = "2026-06-28"


def doc(title: str, url: str) -> OfficialDocRef:
    return OfficialDocRef(title=title, url=url, accessed_on=ACCESSED_ON)


SALESFORCE_CRM_SPEC = ConnectorSpec(
    connector_id="salesforce_crm",
    display_name="Salesforce CRM",
    mode_env="ULTRA_CSM_SALESFORCE_MODE",
    credential_env=(
        "ULTRA_CSM_SALESFORCE_INSTANCE_URL",
        "ULTRA_CSM_SALESFORCE_CLIENT_ID",
        "ULTRA_CSM_SALESFORCE_CLIENT_SECRET",
        "ULTRA_CSM_SALESFORCE_REFRESH_TOKEN",
    ),
    auth_strategies=("oauth2",),
    pagination=("soql_next_records_url",),
    source_contracts=("CRMAccount", "CRMContact", "CRMCase", "CRMOpportunity", "CRMActivity"),
    discovery_surfaces=("Describe Global", "sObject Describe"),
    recorded_shapes=(
        RecordedShape(
            name="account_describe",
            contract="CRMAccount",
            fixture_path="tests/fixtures/connectors/salesforce/account_describe.json",
            docs=(
                doc(
                    "sObject Describe",
                    "https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_sobject_describe.htm",
                ),
            ),
        ),
        RecordedShape(
            name="account_query_page",
            contract="CRMAccount",
            fixture_path="tests/fixtures/connectors/salesforce/account_query_page.json",
            docs=(
                doc(
                    "REST API Query",
                    "https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_query.htm",
                ),
            ),
        ),
    ),
    smoke_command="ucsm connectors smoke salesforce_crm --read-only",
    docs=(
        doc(
            "Describe Global",
            "https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_describeGlobal.htm",
        ),
        doc(
            "sObject Describe",
            "https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_sobject_describe.htm",
        ),
    ),
)


ATTIO_CRM_SPEC = ConnectorSpec(
    connector_id="attio_crm",
    display_name="Attio CRM",
    mode_env="ULTRA_CSM_ATTIO_MODE",
    credential_env=("ULTRA_CSM_ATTIO_ACCESS_TOKEN",),
    auth_strategies=("oauth2", "api_key"),
    pagination=("offset", "cursor"),
    source_contracts=("CRMAccount", "CRMContact", "CRMActivity"),
    discovery_surfaces=("OpenAPI", "objects", "attributes", "records", "lists"),
    recorded_shapes=(
        RecordedShape(
            name="company_records_query",
            contract="CRMAccount",
            fixture_path="tests/fixtures/connectors/attio/company_records_query.json",
            docs=(
                doc(
                    "List company records",
                    "https://docs.attio.com/rest-api/endpoint-reference/companies/list-company-records",
                ),
            ),
        ),
        RecordedShape(
            name="person_records_query",
            contract="CRMContact",
            fixture_path="tests/fixtures/connectors/attio/person_records_query.json",
            docs=(
                doc(
                    "List person records",
                    "https://docs.attio.com/rest-api/endpoint-reference/people/list-person-records",
                ),
            ),
        ),
    ),
    smoke_command="ucsm connectors smoke attio_crm --read-only",
    docs=(
        doc("Attio REST API overview", "https://docs.attio.com/rest-api/overview"),
        doc("Attio authentication", "https://docs.attio.com/rest-api/guides/authentication"),
        doc("Attio rate limits", "https://docs.attio.com/rest-api/guides/rate-limiting"),
        doc("Attio pagination", "https://docs.attio.com/rest-api/guides/pagination"),
        doc("Attio OpenAPI", "https://docs.attio.com/rest-api/endpoint-reference/openapi"),
    ),
)


GAINSIGHT_CS_SPEC = ConnectorSpec(
    connector_id="gainsight_cs",
    display_name="Gainsight CS",
    mode_env="ULTRA_CSM_GAINSIGHT_MODE",
    credential_env=("ULTRA_CSM_GAINSIGHT_DOMAIN", "ULTRA_CSM_GAINSIGHT_TOKEN"),
    auth_strategies=("oauth2", "access_key"),
    pagination=("offset",),
    source_contracts=("CSCompany", "HealthScore", "CTA", "SuccessPlan", "AdoptionSummary"),
    discovery_surfaces=("Data Management object schema", "scorecard measure metadata"),
    recorded_shapes=(
        RecordedShape(
            name="company_read",
            contract="CSCompany",
            fixture_path="tests/fixtures/connectors/gainsight/company_read.json",
            docs=(
                doc(
                    "Company API Documentation",
                    "https://support.gainsight.com/gainsight_nxt/API_and_Developer_Docs/Company_and_Relationship_API/Company_API_Documentation",
                ),
            ),
        ),
        RecordedShape(
            name="cta_read",
            contract="CTA",
            fixture_path="tests/fixtures/connectors/gainsight/cta_read.json",
            docs=(
                doc(
                    "CTA API Documentation",
                    "https://support.gainsight.com/gainsight_nxt/API_and_Developer_Docs/Cockpit_API/Call_To_Action_%28CTA%29_API_Documentation",
                ),
            ),
        ),
    ),
    smoke_command="ucsm connectors smoke gainsight_cs --read-only",
    docs=(
        doc(
            "API Documentation Overview",
            "https://support.gainsight.com/gainsight_nxt/API_and_Developer_Docs/About/API_Documentation_Overview",
        ),
        doc(
            "OAuth for Gainsight APIs",
            "https://support.gainsight.com/gainsight_nxt/01Onboarding_and_Implementation/Onboarding_for_Gainsight_NXT/Login_and_Permissions/OAuth_for_Gainsight_APIs",
        ),
        doc(
            "Custom Object API Documentation",
            "https://support.gainsight.com/gainsight_nxt/API_and_Developer_Docs/Custom_Object_API/Gainsight_Custom_Object_API_Documentation",
        ),
    ),
)


ROCKETLANE_ONBOARDING_SPEC = ConnectorSpec(
    connector_id="rocketlane_onboarding",
    display_name="Rocketlane Onboarding",
    mode_env="ULTRA_CSM_ROCKETLANE_MODE",
    credential_env=("ULTRA_CSM_ROCKETLANE_API_KEY",),
    auth_strategies=("api_key",),
    pagination=("offset",),
    source_contracts=("TimeToValueMilestone",),
    discovery_surfaces=("projects", "phases", "tasks", "fields", "webhooks"),
    recorded_shapes=(
        RecordedShape(
            name="projects_page",
            contract="TimeToValueMilestone",
            fixture_path="tests/fixtures/connectors/rocketlane/projects_page.json",
            docs=(
                doc(
                    "Get all projects",
                    "https://developer.rocketlane.com/reference/get-all-projects",
                ),
            ),
        ),
        RecordedShape(
            name="fields_page",
            contract="TimeToValueMilestone",
            fixture_path="tests/fixtures/connectors/rocketlane/fields_page.json",
            docs=(doc("Fields", "https://developer.rocketlane.com/reference/fields"),),
        ),
    ),
    smoke_command="ucsm connectors smoke rocketlane_onboarding --read-only",
    docs=(
        doc("Rocketlane overview", "https://developer.rocketlane.com/docs/overview"),
        doc("Rocketlane quick start", "https://developer.rocketlane.com/docs/quick-start"),
        doc("Rocketlane API Explorer", "https://developer.rocketlane.com/docs/api-explorer"),
    ),
)


PRODUCT_TELEMETRY_SPEC = ConnectorSpec(
    connector_id="product_telemetry",
    display_name="Product Telemetry",
    mode_env="ULTRA_CSM_TELEMETRY_MODE",
    credential_env=("OTEL_EXPORTER_OTLP_ENDPOINT",),
    auth_strategies=("otlp_config",),
    pagination=("collector_batch",),
    source_contracts=("Entitlement", "UsageSignal", "TimeToValueMilestone"),
    discovery_surfaces=("OTLP samples", "Collector config", "metric catalog"),
    recorded_shapes=(
        RecordedShape(
            name="otlp_metrics_batch",
            contract="UsageSignal",
            fixture_path="tests/fixtures/connectors/telemetry/otlp_metrics_batch.json",
            docs=(doc("OTLP Specification", "https://opentelemetry.io/docs/specs/otlp/"),),
        ),
        RecordedShape(
            name="entitlements_export",
            contract="Entitlement",
            fixture_path="tests/fixtures/connectors/telemetry/entitlements_export.json",
            docs=(
                doc(
                    "OpenTelemetry Specifications",
                    "https://opentelemetry.io/docs/specs/",
                ),
            ),
        ),
    ),
    smoke_command="ucsm connectors smoke product_telemetry --read-only",
    docs=(
        doc("OTLP Specification", "https://opentelemetry.io/docs/specs/otlp/"),
        doc(
            "OTLP Metrics Exporter",
            "https://opentelemetry.io/docs/specs/otel/metrics/sdk_exporters/otlp/",
        ),
        doc("OpenTelemetry Specifications", "https://opentelemetry.io/docs/specs/"),
    ),
)


EXTERNAL_BOOK_SPEC = ConnectorSpec(
    connector_id="external_book",
    display_name="External book import",
    mode_env="ULTRA_CSM_EXTERNAL_BOOK_MODE",
    credential_env=("CORPUS_A_BASE_URL", "CORPUS_A_TABLE", "CORPUS_A_" "API_KEY"),
    auth_strategies=("api_key",),
    pagination=("offset",),
    source_contracts=("CRMAccount", "CRMContact", "CRMOpportunity"),
    discovery_surfaces=("sample records", "confirmed source map"),
    recorded_shapes=(
        RecordedShape(
            name="raw_record_sample",
            contract="CRMAccount",
            fixture_path="tests/fixtures/connectors/external_book/raw_record_sample.json",
            docs=(
                doc(
                    "PostgREST Resource Embedding",
                    "https://postgrest.org/en/stable/references/api/resource_embedding.html",
                ),
            ),
        ),
    ),
    smoke_command="ucsm connectors smoke external_book --read-only",
    docs=(
        doc("PostgREST Tables and Views", "https://postgrest.org/en/stable/references/api/tables_views.html"),
        doc("PostgREST Pagination and Count", "https://postgrest.org/en/stable/references/api/pagination_count.html"),
    ),
)


CONNECTOR_SPECS: dict[str, ConnectorSpec] = {
    spec.connector_id: spec
    for spec in (
        SALESFORCE_CRM_SPEC,
        ATTIO_CRM_SPEC,
        GAINSIGHT_CS_SPEC,
        ROCKETLANE_ONBOARDING_SPEC,
        PRODUCT_TELEMETRY_SPEC,
        EXTERNAL_BOOK_SPEC,
    )
}
