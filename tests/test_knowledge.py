"""Org-knowledge pack validation."""

from __future__ import annotations

import json

import pytest

from ultra_csm.knowledge import OrgPackError, PlaybookError, load_org_pack, load_playbooks


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


def test_fleetops_playbooks_load():
    playbooks = load_playbooks("fleetops")

    assert playbooks.tenant == "fleetops"
    assert {t.tier for t in playbooks.service_tiers} == {"high_touch", "mid_touch", "tech_touch"}
    tech_touch = playbooks.tier_for("tech_touch")
    assert "personal_email" in tech_touch.forbidden_motions
    assert playbooks.plays
    for play in playbooks.plays:
        assert play.motion


def test_playbooks_reject_unknown_motion(tmp_path):
    tenants_dir = tmp_path / "tenants"
    (tenants_dir / "acme").mkdir(parents=True)
    (tenants_dir / "acme" / "playbooks.json").write_text(
        json.dumps(_playbooks(motion="send_carrier_pigeon")), encoding="utf-8"
    )

    with pytest.raises(PlaybookError, match="unknown motion"):
        load_playbooks("acme", tenants_dir=tenants_dir)


def test_playbooks_reject_play_with_undefined_tier(tmp_path):
    tenants_dir = tmp_path / "tenants"
    (tenants_dir / "acme").mkdir(parents=True)
    (tenants_dir / "acme" / "playbooks.json").write_text(
        json.dumps(_playbooks(play_tier="ghost_tier")), encoding="utf-8"
    )

    with pytest.raises(PlaybookError, match="undefined service tier"):
        load_playbooks("acme", tenants_dir=tenants_dir)


def test_playbooks_require_fictional_flag(tmp_path):
    tenants_dir = tmp_path / "tenants"
    (tenants_dir / "acme").mkdir(parents=True)
    (tenants_dir / "acme" / "playbooks.json").write_text(
        json.dumps(_playbooks(fictional=False)), encoding="utf-8"
    )

    with pytest.raises(PlaybookError, match="must be marked fictional"):
        load_playbooks("acme", tenants_dir=tenants_dir)


def _playbooks(
    *,
    fictional: bool = True,
    motion: str = "content_route",
    play_tier: str = "tech_touch",
) -> dict:
    return {
        "schema_version": 1,
        "fictional": fictional,
        "tenant": "acme",
        "service_tiers": [
            {
                "tier": "tech_touch",
                "rule": {"default": True},
                "allowed_motions": ["campaign_enroll", "content_route", "cohort_action"],
                "forbidden_motions": ["personal_email", "working_session", "qbr"],
            }
        ],
        "plays": [
            {
                "id": "test-play",
                "trigger_factor": "feature_shallow_depth",
                "motion": motion,
                "tiers": [play_tier],
                "content_refs": [],
            }
        ],
    }


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
