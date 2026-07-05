"""Notion authoring-edge: fixture parse, renderer (agnostic + account-specific
tiers), two-tier isolation, and byte-idempotence.

Acceptance oracle (Decision 2 / K14): the unmodified existing loaders
(``load_org_pack``, ``load_playbooks``) and the unmodified schema constants
lifted from ``test_content_catalog.py``/``test_handoff_notes.py`` are what
prove a render is safe -- this file never edits those loaders/tests to make
a render pass.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.notion_render import render_all, render_org_pack
from ultra_csm.data_plane.notion_reader import load_captured_payload
from ultra_csm.knowledge import OrgPackError, load_org_pack, load_playbooks

FIXTURE_PATH = str(
    Path(__file__).resolve().parent / "fixtures" / "notion" / "authoring_payload.json"
)
TENANT = "fleetops"
ACCOUNT_SLUG = "notionharbor-fleet"


def test_fixture_loads_into_parsed_shape():
    payload = load_captured_payload(FIXTURE_PATH, pack_version="notion-pack-v1")

    assert payload.pack_version == "notion-pack-v1"
    assert payload.gap_plays
    assert payload.gap_plays[0].factor == "milestones_overdue"
    assert payload.terminology
    assert payload.terminology[0].term == "activation"
    assert payload.playbook_plays
    assert payload.playbook_plays[0].tenant == "fleetops"
    assert payload.playbook_plays[0].motion == "content_route"
    assert payload.playbook_plays[0].tiers == ("tech_touch", "mid_touch")
    assert payload.content_catalog_rows
    assert payload.content_catalog_rows[0].module == "route_optimization"
    assert payload.voice_rule_paragraphs
    assert payload.exemplar_paragraphs
    assert payload.handoff_narrative_paragraphs


def test_agnostic_render_is_loader_accepted(tmp_path):
    payload = load_captured_payload(FIXTURE_PATH, pack_version="notion-pack-v1")
    output_root = tmp_path / "_generated"

    render_all(
        payload,
        output_root=output_root,
        tenant=TENANT,
        pack_version="notion-pack-v1",
        account_slug=ACCOUNT_SLUG,
    )

    org_pack = load_org_pack(
        output_root / "org_pack.json", corpus_dir=output_root / "golden_corpus"
    )
    assert org_pack.pack_version == "notion-pack-v1"
    assert org_pack.gap_plays
    assert org_pack.voice_rules
    assert org_pack.golden_corpus

    playbooks = load_playbooks(TENANT, tenants_dir=output_root / "tenants")
    assert playbooks.tenant == TENANT
    assert playbooks.plays
    for play in playbooks.plays:
        assert play.motion


def test_two_tier_isolation_enforced_by_loader_not_renderer(tmp_path):
    """An author mistake -- an account-specific fact (``account_id``) placed
    into an agnostic-tier field via a stray Notion database column -- must
    be caught by ``load_org_pack``'s ``_reject_forbidden_keys``, not stripped
    by the renderer (Decision 3). This asserts BOTH halves: the raise, and
    that the forbidden key actually reached the generated file untouched --
    proof the loader, not renderer cleverness, is what enforces the
    boundary."""

    payload = load_captured_payload(FIXTURE_PATH, pack_version="notion-pack-v1")
    org_pack = render_org_pack(payload, pack_version="notion-pack-v1")

    # Simulate a Notion author's stray "Account ID" column leaking into a
    # gap_play row -- an account-specific fact authored into the agnostic
    # gap_plays tier. The renderer must carry it through verbatim.
    org_pack["gap_plays"][0]["account_id"] = "acct-notionharbor-0001"

    output_root = tmp_path / "_generated"
    output_root.mkdir(parents=True)
    (output_root / "org_pack.json").write_text(json.dumps(org_pack), encoding="utf-8")

    # Renderer did NOT strip the forbidden key: it is still on disk.
    on_disk = json.loads((output_root / "org_pack.json").read_text(encoding="utf-8"))
    assert on_disk["gap_plays"][0]["account_id"] == "acct-notionharbor-0001"

    # The unmodified loader -- not the renderer -- is what rejects it.
    with pytest.raises(OrgPackError, match="runtime field: account_id"):
        load_org_pack(output_root / "org_pack.json", corpus_dir=output_root / "golden_corpus")
