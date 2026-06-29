"""Ultra CSM data-plane contracts and deterministic fixtures."""

from __future__ import annotations

from dataclasses import fields
import socket

from ultra_csm.data_plane import (
    ACME_LOGISTICS,
    ALL_SOURCE_MAPS,
    CRMContact,
    FixtureCustomerData,
    GAINSIGHT_SOURCE_MAPS,
    NOVA_FIELD,
    FixtureCRMDataConnector,
    PRODUCT_TELEMETRY_SOURCE_MAPS,
    SALESFORCE_SOURCE_MAPS,
    account_id_for,
    build_fixture_data_plane,
    default_fixture_data,
    resolve_candidates,
)
from ultra_csm.data_plane import contracts


def test_resolve_candidates_never_autopicks():
    assert resolve_candidates([]).state == "none"
    one = resolve_candidates(["acct-1", "acct-1"])
    assert one.state == "exactly_one"
    assert one.account_id == "acct-1"

    many = resolve_candidates(["acct-b", "acct-a", "acct-a"])
    assert many.state == "ambiguous"
    assert many.account_id is None
    assert many.candidates == ("acct-a", "acct-b")


def test_fixture_data_plane_resolves_crm_identity_and_is_idempotent():
    plane = build_fixture_data_plane()

    res = plane.crm.resolve_account_by_email("OPS@ACME-LOGISTICS.EXAMPLE")
    assert res.state == "exactly_one"
    assert res.account_id == ACME_LOGISTICS
    assert plane.crm.resolve_account_by_email("missing@example.test").state == "none"

    ref1 = plane.crm.log_activity(
        ACME_LOGISTICS,
        channel="email",
        direction="out",
        summary="sent activation plan",
        idempotency_key="activation-plan-1",
    )
    ref2 = plane.crm.log_activity(
        ACME_LOGISTICS,
        channel="email",
        direction="out",
        summary="duplicate retry",
        idempotency_key="activation-plan-1",
    )
    assert ref1 == ref2
    assert len(plane.crm.logged) == 1


def test_fixture_data_is_tenant_free_synthetic_and_stable():
    data = default_fixture_data()
    assert account_id_for("acme-logistics") == ACME_LOGISTICS
    assert account_id_for("nova-field-services") == NOVA_FIELD
    assert {a.account_id for a in data.accounts} == {ACME_LOGISTICS, NOVA_FIELD}
    assert {c.company_id for c in data.companies} == {ACME_LOGISTICS, NOVA_FIELD}
    assert all(c.email.endswith(".example") for c in data.contacts)


def test_gainsight_context_is_separate_from_raw_product_telemetry():
    plane = build_fixture_data_plane()

    company = plane.cs.get_company(ACME_LOGISTICS)
    assert company is not None
    assert company.lifecycle_stage == "onboarding"
    assert company.arr_cents == 18400000
    assert company.current_score == 62.0

    health = plane.cs.get_health_score(ACME_LOGISTICS)
    assert health is not None
    assert health.band == "yellow"
    assert "activation_gap" in health.drivers

    adoption = plane.cs.get_adoption_summary(ACME_LOGISTICS)
    assert adoption is not None
    assert adoption.adoption_rate == 0.40
    assert "route_optimization" in adoption.underused_capabilities

    entitlements = plane.telemetry.list_entitlements(ACME_LOGISTICS)
    assert {e.capability for e in entitlements} >= {
        "core_telematics",
        "route_optimization",
        "driver_coaching",
    }

    usage = plane.telemetry.list_usage_signals(
        ACME_LOGISTICS,
        metric_name="route_optimization_trips",
    )
    assert len(usage) == 1
    assert usage[0].value == 6.0


def test_time_to_value_fixture_has_evidence_backing_each_gap():
    plane = build_fixture_data_plane()
    signal_ids = {
        s.signal_id
        for s in plane.telemetry.list_usage_signals(ACME_LOGISTICS)
    }
    gaps = [
        m for m in plane.telemetry.list_ttv_milestones(ACME_LOGISTICS)
        if m.achieved_at is None
    ]
    assert {g.milestone for g in gaps} == {
        "activate_50_percent_of_assets",
        "first_route_optimization_workflow",
    }
    assert all(set(g.evidence_signal_ids) <= signal_ids for g in gaps)


def test_fixtures_do_not_open_sockets(monkeypatch):
    opened = []

    def boom(*args, **kwargs):
        opened.append((args, kwargs))
        raise AssertionError("fixture attempted network access")

    monkeypatch.setattr(socket, "create_connection", boom)

    plane = build_fixture_data_plane()
    assert plane.crm.get_account(ACME_LOGISTICS).name == "Acme Logistics"
    assert plane.cs.list_ctas(ACME_LOGISTICS, status="open")
    assert plane.telemetry.list_usage_signals(ACME_LOGISTICS)
    assert opened == []


def test_custom_fixture_can_exercise_ambiguous_crm_resolution():
    data = default_fixture_data()
    duplicate = CRMContact(
        contact_id="duplicate-contact",
        account_id=NOVA_FIELD,
        email=data.contacts[0].email,
        name="Duplicate Contact",
        role="operations",
        title="Ops",
        consent_to_contact=True,
    )
    custom = FixtureCustomerData(
        accounts=data.accounts,
        companies=data.companies,
        contacts=(*data.contacts, duplicate),
        cases=data.cases,
        opportunities=data.opportunities,
        health_scores=data.health_scores,
        ctas=data.ctas,
        success_plans=data.success_plans,
        adoption_summaries=data.adoption_summaries,
        entitlements=data.entitlements,
        usage_signals=data.usage_signals,
        milestones=data.milestones,
    )
    crm = FixtureCRMDataConnector(data=custom)
    res = crm.resolve_account_by_email(data.contacts[0].email)
    assert res.state == "ambiguous"
    assert set(res.candidates) == {ACME_LOGISTICS, NOVA_FIELD}


def test_vendor_source_maps_ground_salesforce_and_gainsight_contracts():
    assert SALESFORCE_SOURCE_MAPS["CRMAccount"].object_name == "Account"
    assert SALESFORCE_SOURCE_MAPS["CRMAccount"].fields["account_id"].api_name == "Id"
    assert SALESFORCE_SOURCE_MAPS["CRMAccount"].fields["industry"].standard is True
    assert SALESFORCE_SOURCE_MAPS["CRMContact"].fields["role"].standard is False
    assert (
        SALESFORCE_SOURCE_MAPS["CRMContact"].fields["consent_to_contact"].standard
        is False
    )

    company = GAINSIGHT_SOURCE_MAPS["CSCompany"]
    assert company.object_name == "Company"
    assert company.fields["renewal_date"].api_name == "RenewalDate"
    assert company.fields["arr_cents"].note == "stored internally as cents"

    assert PRODUCT_TELEMETRY_SOURCE_MAPS["UsageSignal"].docs_url.startswith("https://")
    for source_map in (
        *SALESFORCE_SOURCE_MAPS.values(),
        *GAINSIGHT_SOURCE_MAPS.values(),
    ):
        assert source_map.docs_url.startswith("https://")
        assert source_map.fields

    assert set(ALL_SOURCE_MAPS) >= {
        "CRMAccount",
        "CRMContact",
        "CSCompany",
        "CTA",
        "UsageSignal",
    }


def test_source_maps_cover_every_data_plane_contract_field():
    mapped_contracts = {
        "CRMAccount": contracts.CRMAccount,
        "CRMContact": contracts.CRMContact,
        "CRMCase": contracts.CRMCase,
        "CRMOpportunity": contracts.CRMOpportunity,
        "CRMActivity": contracts.CRMActivity,
        "CSCompany": contracts.CSCompany,
        "HealthScore": contracts.HealthScore,
        "CTA": contracts.CTA,
        "SuccessPlan": contracts.SuccessPlan,
        "AdoptionSummary": contracts.AdoptionSummary,
        "Entitlement": contracts.Entitlement,
        "UsageSignal": contracts.UsageSignal,
    }
    assert set(ALL_SOURCE_MAPS) >= set(mapped_contracts)
    for name, contract in mapped_contracts.items():
        contract_fields = {f.name for f in fields(contract)}
        mapped_fields = set(ALL_SOURCE_MAPS[name].fields)
        assert contract_fields == mapped_fields, name


def test_source_maps_classify_sensitive_fields_for_mapping_and_readiness():
    contact = SALESFORCE_SOURCE_MAPS["CRMContact"].fields
    assert contact["email"].pii == "contact"
    assert contact["email"].llm_allowed is False
    assert contact["name"].pii == "contact"

    assert SALESFORCE_SOURCE_MAPS["CRMCase"].fields["subject"].pii == "customer_content"
    assert SALESFORCE_SOURCE_MAPS["CRMActivity"].fields["summary"].pii == "customer_content"

    subject = PRODUCT_TELEMETRY_SOURCE_MAPS["UsageSignal"].fields["subject_id"]
    assert subject.pii == "contact"
    assert subject.llm_allowed is False

    for source_map in ALL_SOURCE_MAPS.values():
        for field in source_map.fields.values():
            assert field.pii in {"none", "contact", "customer_content", "secret"}
