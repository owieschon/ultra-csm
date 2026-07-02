from __future__ import annotations

from eval.product_telemetry_simulated_onboarding import (
    build_product_telemetry_simulated_onboarding_artifact,
)


def test_product_telemetry_simulated_onboarding_runs_full_pipeline_without_live_claims(
    tmp_path,
):
    artifact = build_product_telemetry_simulated_onboarding_artifact(
        output_path=tmp_path / "product_telemetry_simulated_onboarding.json"
    )

    assert artifact["claim_boundary"] == {
        "sim": True,
        "live": False,
        "uses_live_credentials": False,
        "live_tenant_proven": False,
    }
    assert artifact["credential_boundary"]["requests_without_credentials"] == 0
    assert artifact["credential_boundary"]["missing_env"] == ["OTEL_EXPORTER_OTLP_ENDPOINT"]
    assert artifact["source_book"]["accounts"] == 35
    assert artifact["discovery"]["ok"] is True
    assert artifact["discovery"]["requests_on_fake_transport"] == 2
    assert artifact["readiness"]["mode"] == "fixture"
    assert artifact["readiness"]["connected"] is False
    assert artifact["readiness_report"]["sources"] == {"product_telemetry": "fixture_verified"}


def test_product_telemetry_simulated_mapping_resolves_identity_fields_and_degrades_values(
    tmp_path,
):
    artifact = build_product_telemetry_simulated_onboarding_artifact(
        output_path=tmp_path / "product_telemetry_simulated_onboarding.json"
    )

    proposal = artifact["mapping_proposal"]
    frozen = artifact["frozen_source_map"]

    assert proposal["coverage"] == {
        "mapped": 6,
        "ambiguous_confirm": 0,
        "missing_to_unknown": 9,
        "total": 15,
    }
    # Required-attribute discovery resolves identity/join fields (account, grain,
    # metric name, source ref); per-datapoint values require a live sample capture
    # of the OTLP payload itself, not just attribute introspection -- so both
    # contracts honestly degrade rather than guess the missing fields.
    assert proposal["ambiguous_keys"] == []
    assert artifact["confirmation_fixture"]["confirmed_keys"] == []
    assert all(mapping["state"] == "mapped" for mapping in frozen["mappings"])
    assert artifact["readiness"]["rails_degraded"] == ("Entitlement", "UsageSignal")
    assert "UsageSignal.value" in proposal["missing_to_unknown_keys"]
    assert "Entitlement.entitled_quantity" in proposal["missing_to_unknown_keys"]


def test_product_telemetry_simulated_onboarding_is_deterministic(tmp_path):
    first = build_product_telemetry_simulated_onboarding_artifact(
        output_path=tmp_path / "first.json"
    )
    second = build_product_telemetry_simulated_onboarding_artifact(
        output_path=tmp_path / "second.json"
    )

    assert first == second
