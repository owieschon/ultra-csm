"""Org-knowledge pack validation."""

from __future__ import annotations

import json

import pytest

from ultra_csm.knowledge import OrgPackError, load_org_pack


def test_default_org_pack_loads_slot_b_context():
    context = load_org_pack().slot_b_context()

    assert context["schema_version"] == 1
    assert context["pack_version"] == "org-pack-ttv-demo-v3"
    assert context["fictional"] is True
    assert context["product_name"] == "FleetOps Platform"
    assert context["voice_rules"]
    assert context["value_props"]
    assert context["gap_plays"]
    assert "account_id" not in json.dumps(context)


def test_org_pack_rejects_runtime_authority_fields(tmp_path):
    path = tmp_path / "org_pack.json"
    path.write_text(json.dumps(_pack(priority={"score": 999})), encoding="utf-8")

    with pytest.raises(OrgPackError, match="runtime field: priority"):
        load_org_pack(path)


def test_org_pack_must_be_marked_fictional(tmp_path):
    path = tmp_path / "org_pack.json"
    path.write_text(json.dumps(_pack(fictional=False)), encoding="utf-8")

    with pytest.raises(OrgPackError, match="must be marked fictional"):
        load_org_pack(path)


def test_default_org_pack_loads_golden_corpus():
    pack = load_org_pack()

    assert pack.golden_corpus
    kinds = {example.kind for example in pack.golden_corpus}
    assert "recap_email" in kinds
    assert all(example.content.strip() for example in pack.golden_corpus)


def test_golden_corpus_missing_dir_is_empty(tmp_path):
    from ultra_csm.knowledge import DEFAULT_ORG_PACK_PATH

    pack = load_org_pack(DEFAULT_ORG_PACK_PATH, corpus_dir=tmp_path / "does-not-exist")

    assert pack.golden_corpus == ()


def test_golden_corpus_malformed_file_fails_closed(tmp_path):
    from ultra_csm.knowledge import DEFAULT_ORG_PACK_PATH

    corpus_dir = tmp_path / "golden_corpus"
    corpus_dir.mkdir()
    (corpus_dir / "broken.json").write_text(
        json.dumps({"fictional": True, "kind": "recap_email"}),  # missing "title"/"content"
        encoding="utf-8",
    )

    with pytest.raises(OrgPackError, match="broken.json"):
        load_org_pack(DEFAULT_ORG_PACK_PATH, corpus_dir=corpus_dir)


def test_org_pack_rejects_unsafe_customer_asks(tmp_path):
    path = tmp_path / "org_pack.json"
    path.write_text(
        json.dumps(_pack(
            play="approve a discount",
            customer_ask="approve a discount for the rollout",
        )),
        encoding="utf-8",
    )

    with pytest.raises(OrgPackError, match="unsafe authority language"):
        load_org_pack(path)


def _pack(
    *,
    fictional: bool = True,
    play: str = "review overdue milestones",
    customer_ask: str = "review overdue milestones",
    **gap_play_extra,
) -> dict:
    gap_play = {
        "factor": "milestones_overdue",
        "play": play,
        "customer_ask": customer_ask,
    }
    gap_play.update(gap_play_extra)
    return {
        "schema_version": 1,
        "pack_version": "bad-pack",
        "fictional": fictional,
        "product_name": "Demo",
        "terminology": {},
        "voice_rules": ["Professional and direct."],
        "value_props": [
            {
                "id": "activation",
                "name": "Activation",
                "summary": "Customer activation context.",
            }
        ],
        "gap_plays": [gap_play],
    }
