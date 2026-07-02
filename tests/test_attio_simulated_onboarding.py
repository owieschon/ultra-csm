from __future__ import annotations

from eval.attio_simulated_onboarding import build_attio_simulated_onboarding_artifact


def test_attio_simulated_onboarding_runs_full_pipeline_without_live_claims(tmp_path):
    artifact = build_attio_simulated_onboarding_artifact(
        output_path=tmp_path / "attio_simulated_onboarding.json"
    )

    assert artifact["claim_boundary"] == {
        "sim": True,
        "live": False,
        "uses_live_credentials": False,
        "live_tenant_proven": False,
    }
    assert artifact["credential_boundary"]["requests_without_credentials"] == 0
    assert artifact["credential_boundary"]["missing_env"] == ["ULTRA_CSM_ATTIO_ACCESS_TOKEN"]
    assert artifact["source_book"]["accounts"] == 35
    assert artifact["fixture_payload"]["company_records_available"] == 35
    assert artifact["discovery"]["ok"] is True
    assert artifact["discovery"]["requests_on_fake_transport"] == 6
    assert artifact["discovery"]["sample_counts"] == {
        "self": 0,
        "objects": 2,
        "companies_attributes": 4,
        "people_attributes": 8,
        "companies_sample": 1,
        "people_sample": 1,
    }
    assert artifact["readiness"]["mode"] == "fixture"
    assert artifact["readiness"]["connected"] is False
    assert artifact["readiness_report"]["sources"] == {"attio_crm": "fixture_verified"}


def test_attio_simulated_mapping_freezes_confirmed_fields_and_keeps_unknowns(tmp_path):
    artifact = build_attio_simulated_onboarding_artifact(
        output_path=tmp_path / "attio_simulated_onboarding.json"
    )

    proposal = artifact["mapping_proposal"]
    frozen = artifact["frozen_source_map"]

    assert "CRMAccount.industry" in proposal["missing_to_unknown_keys"]
    assert "CRMAccount.industry" in frozen["unknown_fields"]
    assert sorted(proposal["ambiguous_keys"]) == artifact["confirmation_fixture"]["confirmed_keys"]
    assert all(mapping["state"] == "mapped" for mapping in frozen["mappings"])
    assert all(
        mapping["requires_human_confirmation"] is False
        for mapping in frozen["mappings"]
    )
    assert artifact["readiness"]["rails_degraded"] == ("CRMAccount",)


def test_attio_simulated_onboarding_is_deterministic(tmp_path):
    first = build_attio_simulated_onboarding_artifact(output_path=tmp_path / "first.json")
    second = build_attio_simulated_onboarding_artifact(output_path=tmp_path / "second.json")

    assert first == second
