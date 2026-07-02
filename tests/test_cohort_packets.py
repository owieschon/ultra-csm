"""Deterministic manager cohort packet tests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from eval.cohort_packets import build_fixture_artifact
from ultra_csm.cohort_packets import (
    CLAIM_BOUNDARY,
    build_cohort_packets_artifact,
    build_cohort_rollup_packets,
)
from ultra_csm.data_plane import ACME_LOGISTICS, NOVA_FIELD, default_fixture_data
from ultra_csm.snapshot_store import SnapshotStore

BANNED_CAUSAL_TERMS = re.compile(
    r"\b(because|predicts?|predicted|prediction|causes?|caused|causing|causal)\b",
    re.IGNORECASE,
)


def test_cohort_packets_roll_up_segments_and_optional_artifacts():
    data = default_fixture_data()
    packets = build_cohort_rollup_packets(
        data,
        snapshots=_fixture_snapshots(data),
        divergence_patterns=(
            {"account_id": ACME_LOGISTICS, "pattern": "observed_activation_gap"},
            {"account_id": NOVA_FIELD, "pattern": "observed_renewal_alignment"},
        ),
        tick_ledger=(
            {
                "account_id": ACME_LOGISTICS,
                "trigger_name": "band_drop",
                "event_type": "trigger_fired",
            },
            {"account_id": ACME_LOGISTICS, "event_type": "hold_created"},
            {
                "account_id": NOVA_FIELD,
                "trigger_name": "renewal_window",
                "event_type": "trigger_fired",
            },
            {"account_id": NOVA_FIELD, "event_type": "hold_released"},
        ),
        action_packets=(
            {"account_id": ACME_LOGISTICS, "proposal": {"status": "pending"}},
            {"account_id": NOVA_FIELD, "proposal": {"status": "approved"}},
        ),
    )

    assert {packet.segment_axis for packet in packets} == {
        "size_band",
        "lifecycle_stage",
        "industry",
    }
    mid_market = _packet(packets, "size_band", "mid_market")
    assert mid_market.claim_boundary == CLAIM_BOUNDARY
    assert mid_market.associated_account_count == 2
    assert mid_market.associated_account_ids == tuple(sorted((ACME_LOGISTICS, NOVA_FIELD)))
    assert mid_market.observed_health_band_distribution == {
        "green": 1,
        "yellow": 1,
        "red": 0,
        "unknown": 0,
    }
    assert mid_market.observed_trajectory_direction_counts == {
        "improving": 1,
        "stable": 0,
        "declining": 1,
        "unknown": 0,
    }
    assert {
        item.pattern: item.associated_account_count
        for item in mid_market.observed_divergence_patterns
    } == {
        "observed_activation_gap": 1,
        "observed_renewal_alignment": 1,
    }
    assert mid_market.observed_trigger_firing_counts == {
        "band_drop": 1,
        "renewal_window": 1,
    }
    assert mid_market.observed_hold_release_counts == {"held": 1, "released": 1}
    assert mid_market.observed_action_throughput == {"approved": 1, "pending": 1}


def test_optional_metrics_are_empty_when_artifacts_are_absent():
    data = default_fixture_data()
    packet = _packet(build_cohort_rollup_packets(data), "size_band", "mid_market")

    assert packet.observed_trajectory_direction_counts == {}
    assert packet.observed_divergence_patterns == ()
    assert packet.observed_trigger_firing_counts == {}
    assert packet.observed_hold_release_counts == {"held": 0, "released": 0}
    assert packet.observed_action_throughput == {}


def test_object_shaped_action_artifacts_are_supported():
    data = default_fixture_data()
    artifact = _LensArtifact(work_items=(
        _LensWorkItem(
            account_id=ACME_LOGISTICS,
            proposal=_LensProposal(status="approved"),
        ),
    ))

    packet = _packet(
        build_cohort_rollup_packets(data, action_packets=artifact),
        "size_band",
        "mid_market",
    )

    assert packet.observed_action_throughput == {"approved": 1}


def test_artifact_and_packets_carry_sim_claim_boundary():
    artifact = build_cohort_packets_artifact(default_fixture_data())

    assert artifact["claim_boundary"] == CLAIM_BOUNDARY
    assert artifact["packet_count"] == len(artifact["packets"])
    assert artifact["packets"]
    assert all(packet["claim_boundary"] == CLAIM_BOUNDARY for packet in artifact["packets"])


def test_packet_text_and_keys_use_observed_associated_language():
    artifact = build_cohort_packets_artifact(
        default_fixture_data(),
        snapshots=_fixture_snapshots(default_fixture_data()),
        divergence_patterns=(
            {"account_id": ACME_LOGISTICS, "pattern": "observed_activation_gap"},
        ),
    )

    matches = [
        text for text in _walk_text(artifact)
        if BANNED_CAUSAL_TERMS.search(text)
    ]
    assert matches == []


def test_eval_fixture_artifact_is_repeatable(tmp_path):
    output = tmp_path / "cohort_packets.json"

    first = build_fixture_artifact(output)
    first_text = output.read_text(encoding="utf-8")
    second = build_fixture_artifact(output)

    assert output.read_text(encoding="utf-8") == first_text
    assert second == first
    assert first["claim_boundary"] == CLAIM_BOUNDARY
    assert first["repeatability"]["matched"] is True
    assert first["repeatability"]["first_sha256"] == first["repeatability"]["second_sha256"]
    assert all(packet["claim_boundary"] == CLAIM_BOUNDARY for packet in first["packets"])


def _fixture_snapshots(data) -> SnapshotStore:  # noqa: ANN001
    companies = {company.company_id: company for company in data.companies}
    health = {score.account_id: score for score in data.health_scores}
    store = SnapshotStore()
    store.store_snapshot(
        0,
        ACME_LOGISTICS,
        _snapshot(companies[ACME_LOGISTICS], health[ACME_LOGISTICS], 70.0),
    )
    store.store_snapshot(
        30,
        ACME_LOGISTICS,
        _snapshot(companies[ACME_LOGISTICS], health[ACME_LOGISTICS], 62.0),
    )
    store.store_snapshot(
        0,
        NOVA_FIELD,
        _snapshot(companies[NOVA_FIELD], health[NOVA_FIELD], 75.0),
    )
    store.store_snapshot(
        30,
        NOVA_FIELD,
        _snapshot(companies[NOVA_FIELD], health[NOVA_FIELD], 81.0),
    )
    return store


def _snapshot(company, health, score: float) -> dict[str, Any]:  # noqa: ANN001
    return {
        "health_band": health.band,
        "health_score": score,
        "priority_score": 0,
        "priority_factors": (),
        "lifecycle_stage": company.lifecycle_stage,
        "arr_cents": company.arr_cents,
    }


def _packet(packets, axis: str, value: str):  # noqa: ANN001, ANN202
    return next(
        packet for packet in packets
        if packet.segment_axis == axis and packet.segment_value == value
    )


def _walk_text(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _walk_text(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_text(item)
    elif isinstance(value, str):
        yield value


@dataclass(frozen=True)
class _LensProposal:
    status: str


@dataclass(frozen=True)
class _LensWorkItem:
    account_id: str
    proposal: _LensProposal


@dataclass(frozen=True)
class _LensArtifact:
    work_items: tuple[_LensWorkItem, ...]
