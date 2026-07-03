from __future__ import annotations

import json

from eval.relay_battery import build_relay_battery_artifact


def test_relay_battery_exercises_all_adversarial_cases(tmp_path):
    artifact = build_relay_battery_artifact(output_path=tmp_path / "relay.json")

    assert artifact["hard_ok"] is True
    assert artifact["score"] == {"passed": 8, "total": 8}
    assert {case["name"] for case in artifact["cases"]} == {
        "truncated_payload",
        "paraphrased_keys",
        "duplicated_rows",
        "partial_identity_join",
        "injected_text",
        "optional_fields_missing",
        "empty_book",
        "oversized_book",
    }


def test_relay_battery_reports_specific_failure_modes(tmp_path):
    artifact = build_relay_battery_artifact(output_path=tmp_path / "relay.json")
    cases = {case["name"]: case for case in artifact["cases"]}

    assert cases["truncated_payload"]["coverage"]["count_mismatch"] is True
    assert cases["paraphrased_keys"]["proposal"]["mapped_count"] == 0
    assert cases["paraphrased_keys"]["proposal"]["ambiguous_count"] >= 4
    assert cases["duplicated_rows"]["coverage"]["duplicate_identities"]
    assert cases["partial_identity_join"]["coverage"]["join_coverage"]["ratio"] == 0.5
    assert cases["injected_text"]["coverage"]["injection_marker_count"] == 1
    assert cases["optional_fields_missing"]["coverage"]["unknown_fields"]
    assert cases["empty_book"]["coverage"]["records_processed"] == 0
    assert cases["oversized_book"]["coverage"]["truncated"] is True


def test_relay_battery_artifact_is_deterministic_and_sanitized(tmp_path):
    first = build_relay_battery_artifact(output_path=tmp_path / "first.json")
    second = build_relay_battery_artifact(output_path=tmp_path / "second.json")

    assert first == second
    serialized = json.dumps(first, sort_keys=True)
    assert "Jordan Lee" not in serialized
    assert "Ignore previous instructions" not in serialized
    assert "example.test" not in serialized
