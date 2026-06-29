"""Connector catalog and readiness guardrails."""

from __future__ import annotations

import pytest

from ultra_csm.data_plane import (
    CONNECTOR_SPECS,
    SourceReadiness,
    readiness_report,
    validate_connector_spec,
    validate_readiness_state,
)
from ultra_csm.data_plane.readiness import ConnectorSpec, OfficialDocRef, RecordedShape


def test_every_connector_spec_meets_the_shared_real_ready_bar():
    assert set(CONNECTOR_SPECS) == {
        "salesforce_crm",
        "attio_crm",
        "gainsight_cs",
        "rocketlane_onboarding",
        "product_telemetry",
    }
    for spec in CONNECTOR_SPECS.values():
        validate_connector_spec(spec)
        assert spec.credential_env
        assert spec.discovery_surfaces
        assert spec.recorded_shapes
        assert all(doc.accessed_on == "2026-06-28" for doc in spec.docs)


def test_attio_is_held_to_the_same_connector_standard():
    spec = CONNECTOR_SPECS["attio_crm"]

    assert spec.credential_env == ("ULTRA_CSM_ATTIO_ACCESS_TOKEN",)
    assert set(spec.auth_strategies) == {"oauth2", "api_key"}
    assert set(spec.pagination) == {"offset", "cursor"}
    assert {"OpenAPI", "objects", "attributes", "records", "lists"} <= set(
        spec.discovery_surfaces
    )
    assert {shape.contract for shape in spec.recorded_shapes} >= {
        "CRMAccount",
        "CRMContact",
    }
    assert all("attio" in doc.url for doc in spec.docs)


def test_connector_spec_requires_official_docs_and_recorded_shapes():
    bad = ConnectorSpec(
        connector_id="attio_crm",
        display_name="Attio CRM",
        mode_env="ULTRA_CSM_ATTIO_MODE",
        credential_env=("ULTRA_CSM_ATTIO_ACCESS_TOKEN",),
        auth_strategies=("api_key",),
        pagination=("offset",),
        source_contracts=("CRMAccount",),
        discovery_surfaces=("objects",),
        recorded_shapes=(
            RecordedShape(
                name="company_records_query",
                contract="CRMAccount",
                fixture_path="tests/fixtures/connectors/attio/company_records_query.json",
                docs=(OfficialDocRef("local notes", "internal://notes", "2026-06-28"),),
            ),
        ),
        smoke_command="ucsm connectors smoke attio_crm --read-only",
        docs=(OfficialDocRef("local notes", "internal://notes", "2026-06-28"),),
    )

    with pytest.raises(ValueError, match="official docs"):
        validate_connector_spec(bad)


def test_connector_spec_requires_shared_smoke_command_and_fixture_path():
    bad = ConnectorSpec(
        connector_id="salesforce_crm",
        display_name="Salesforce CRM",
        mode_env="ULTRA_CSM_SALESFORCE_MODE",
        credential_env=("ULTRA_CSM_SALESFORCE_REFRESH_TOKEN",),
        auth_strategies=("oauth2",),
        pagination=("soql_next_records_url",),
        source_contracts=("CRMAccount",),
        discovery_surfaces=("Describe Global",),
        recorded_shapes=(
            RecordedShape(
                name="account_describe",
                contract="CRMAccount",
                fixture_path="tmp/account_describe.json",
                docs=(
                    OfficialDocRef(
                        "sObject Describe",
                        "https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_sobject_describe.htm",
                        "2026-06-28",
                    ),
                ),
            ),
        ),
        smoke_command="python smoke_salesforce.py",
        docs=(
            OfficialDocRef(
                "Describe Global",
                "https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_describeGlobal.htm",
                "2026-06-28",
            ),
        ),
    )

    with pytest.raises(ValueError, match="smoke_command"):
        validate_connector_spec(bad)


def test_readiness_states_fail_closed():
    spec = CONNECTOR_SPECS["gainsight_cs"]
    live = SourceReadiness(
        connector_id="gainsight_cs",
        mode="live",
        state="live_smoke_verified",
        connected=True,
        rails_degraded=(),
        required_operator_actions=(),
        evidence=("smoke:gainsight_cs:2026-06-28",),
    )
    validate_readiness_state(live, spec)

    with pytest.raises(ValueError, match="live smoke"):
        validate_readiness_state(
            SourceReadiness(
                connector_id="gainsight_cs",
                mode="fixture",
                state="live_smoke_verified",
                connected=False,
                rails_degraded=(),
                required_operator_actions=(),
            ),
            spec,
        )

    with pytest.raises(ValueError, match="disabled"):
        validate_readiness_state(
            SourceReadiness(
                connector_id="gainsight_cs",
                mode="disabled",
                state="degraded",
                connected=False,
                rails_degraded=("outcome",),
                required_operator_actions=("enable Gainsight",),
            ),
            spec,
        )


def test_readiness_report_keeps_missing_sources_explicit():
    report = readiness_report(
        (
            SourceReadiness(
                connector_id="attio_crm",
                mode="live",
                state="live_schema_verified",
                connected=True,
                rails_degraded=(),
                required_operator_actions=("run Attio smoke",),
            ),
            SourceReadiness(
                connector_id="rocketlane_onboarding",
                mode="disabled",
                state="disabled",
                connected=False,
                rails_degraded=("onboarding",),
                required_operator_actions=("connect Rocketlane",),
            ),
        )
    )

    assert report["sources"]["attio_crm"] == "live_schema_verified"
    assert report["sources"]["rocketlane_onboarding"] == "disabled"
    assert report["degraded_rails"] == ("onboarding",)
    assert report["required_operator_actions"] == (
        "run Attio smoke",
        "connect Rocketlane",
    )
