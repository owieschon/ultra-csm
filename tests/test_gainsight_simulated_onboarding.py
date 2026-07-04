from __future__ import annotations

from eval.gainsight_simulated_onboarding import build_gainsight_simulated_onboarding_artifact


def test_gainsight_simulated_onboarding_runs_full_pipeline_without_live_claims(tmp_path):
    artifact = build_gainsight_simulated_onboarding_artifact(
        output_path=tmp_path / "gainsight_simulated_onboarding.json"
    )

    assert artifact["claim_boundary"] == {
        "sim": True,
        "live": False,
        "uses_live_credentials": False,
        "live_tenant_proven": False,
    }
    assert artifact["credential_boundary"]["requests_without_credentials"] == 0
    assert artifact["credential_boundary"]["missing_env"] == [
        "ULTRA_CSM_GAINSIGHT_DOMAIN",
        "ULTRA_CSM_GAINSIGHT_TOKEN",
    ]
    assert artifact["source_book"]["accounts"] == 180
    assert artifact["discovery"]["ok"] is True
    assert artifact["discovery"]["requests_on_fake_transport"] == 6
    assert artifact["readiness"]["mode"] == "fixture"
    assert artifact["readiness"]["connected"] is False
    assert artifact["readiness_report"]["sources"] == {"gainsight_cs": "fixture_verified"}


def test_gainsight_simulated_mapping_confirms_ambiguous_fields_and_degrades_scorecard_rails(
    tmp_path,
):
    artifact = build_gainsight_simulated_onboarding_artifact(
        output_path=tmp_path / "gainsight_simulated_onboarding.json"
    )

    proposal = artifact["mapping_proposal"]
    frozen = artifact["frozen_source_map"]

    assert proposal["coverage"] == {
        "mapped": 17,
        "ambiguous_confirm": 5,
        "missing_to_unknown": 13,
        "total": 35,
    }
    assert sorted(proposal["ambiguous_keys"]) == artifact["confirmation_fixture"]["confirmed_keys"]
    assert all(mapping["state"] == "mapped" for mapping in frozen["mappings"])
    assert all(
        mapping["requires_human_confirmation"] is False for mapping in frozen["mappings"]
    )
    # Gainsight's metadata-describe surface does not expose a single object matching the
    # HealthScore/AdoptionSummary source maps' expected names (they live behind
    # tenant-specific Scorecard/Adoption Explorer configuration) -- both rails degrade to
    # unknown honestly instead of guessing an object match.
    assert artifact["readiness"]["rails_degraded"] == ("AdoptionSummary", "HealthScore")
    assert "HealthScore.score" in proposal["missing_to_unknown_keys"]
    assert "AdoptionSummary.adoption_rate" in proposal["missing_to_unknown_keys"]


def test_gainsight_simulated_onboarding_is_deterministic(tmp_path):
    first = build_gainsight_simulated_onboarding_artifact(output_path=tmp_path / "first.json")
    second = build_gainsight_simulated_onboarding_artifact(output_path=tmp_path / "second.json")

    assert first == second
