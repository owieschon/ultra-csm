"""Org-knowledge pack validation."""

from __future__ import annotations

import json

import pytest

from ultra_csm.knowledge import (
    Booking,
    GoldenExample,
    GOLDEN_EXEMPLAR_MAX_COUNT,
    GOLDEN_EXEMPLAR_TOKEN_BUDGET,
    OrgPackError,
    PlaybookError,
    load_org_pack,
    load_playbooks,
    select_golden_exemplars,
)


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


def test_select_golden_exemplars_matches_kind_for_escalate_disposition():
    pack = load_org_pack()

    selected = select_golden_exemplars(
        pack.golden_corpus, disposition="escalate", recommended_action="recommend_next_best_action"
    )

    assert len(selected) == 1
    assert selected[0].kind == "escalation_email"


def test_select_golden_exemplars_defaults_to_recap_for_other_dispositions():
    pack = load_org_pack()

    for disposition in ("propose_customer_action", "internal_review"):
        selected = select_golden_exemplars(
            pack.golden_corpus, disposition=disposition, recommended_action="draft_customer_outreach"
        )
        assert len(selected) == 1
        assert selected[0].kind == "recap_email"


def test_select_golden_exemplars_is_deterministic():
    pack = load_org_pack()

    first = select_golden_exemplars(pack.golden_corpus, disposition="escalate")
    second = select_golden_exemplars(pack.golden_corpus, disposition="escalate")

    assert first == second


def test_select_golden_exemplars_respects_cap():
    examples = tuple(
        GoldenExample(kind="recap_email", title=f"Recap {i}", content="word " * 10)
        for i in range(5)
    )

    selected = select_golden_exemplars(examples, disposition="internal_review")

    assert len(selected) == GOLDEN_EXEMPLAR_MAX_COUNT
    assert [example.title for example in selected] == ["Recap 0", "Recap 1"]


def test_select_golden_exemplars_respects_token_budget():
    # Each exemplar is ~ (chars // 4) tokens; force a single oversized entry
    # past the budget to prove it is excluded rather than silently truncated.
    oversized_content = "x" * ((GOLDEN_EXEMPLAR_TOKEN_BUDGET + 100) * 4)
    examples = (
        GoldenExample(kind="recap_email", title="Fits", content="short recap body"),
        GoldenExample(kind="recap_email", title="Oversized", content=oversized_content),
    )

    selected = select_golden_exemplars(examples, disposition="internal_review")

    assert [example.title for example in selected] == ["Fits"]


def test_select_golden_exemplars_empty_corpus_returns_empty():
    assert select_golden_exemplars((), disposition="escalate") == ()


def test_slot_b_context_without_disposition_is_unchanged():
    pack = load_org_pack()

    context = pack.slot_b_context()

    assert "golden_exemplars" not in context


def test_slot_b_context_with_disposition_adds_golden_exemplars():
    pack = load_org_pack()

    context = pack.slot_b_context(disposition="escalate", recommended_action="recommend_next_best_action")

    assert "golden_exemplars" in context
    assert context["golden_exemplars"][0]["kind"] == "escalation_email"
    assert "account_id" not in json.dumps(context)


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


def test_default_org_pack_booking_is_the_sim_fictional_url():
    pack = load_org_pack()

    assert pack.booking is not None
    assert pack.booking.url.startswith("https://calendar.example/")
    assert pack.booking.label


def test_default_org_pack_slot_b_context_carries_booking():
    context = load_org_pack().slot_b_context()

    assert context["booking"]["url"].startswith("https://calendar.example/")
    assert context["booking"]["label"]


def test_org_pack_booking_absent_is_dormant_not_an_error(tmp_path):
    path = tmp_path / "org_pack.json"
    path.write_text(json.dumps(_pack()), encoding="utf-8")

    pack = load_org_pack(path)

    assert pack.booking is None
    assert "booking" not in pack.slot_b_context()


def test_org_pack_booking_malformed_missing_url_fails_closed(tmp_path):
    path = tmp_path / "org_pack.json"
    raw = _pack()
    raw["booking"] = {"label": "Book time"}
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(OrgPackError):
        load_org_pack(path)


def test_org_pack_booking_rejects_non_http_url(tmp_path):
    path = tmp_path / "org_pack.json"
    raw = _pack()
    raw["booking"] = {"url": "not-a-url", "label": "Book time"}
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(OrgPackError, match="http"):
        load_org_pack(path)


def test_org_pack_booking_url_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "ULTRA_CSM_BOOKING_URL",
        "https://calendar.google.com/calendar/appointments/real-live-url",
    )
    path = tmp_path / "org_pack.json"
    raw = _pack()
    raw["booking"] = {
        "url": "https://calendar.example/schedule/sim",
        "label": "Book time",
    }
    path.write_text(json.dumps(raw), encoding="utf-8")

    pack = load_org_pack(path)

    assert pack.booking == Booking(
        url="https://calendar.google.com/calendar/appointments/real-live-url",
        label="Book time",
    )
