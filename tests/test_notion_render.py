"""Notion authoring-edge: fixture parse, renderer (agnostic + account-specific
tiers), two-tier isolation, and byte-idempotence.

Acceptance oracle (Decision 2 / K14): the unmodified existing loaders
(``load_org_pack``, ``load_playbooks``) and the unmodified schema constants
lifted from ``test_content_catalog.py``/``test_handoff_notes.py`` are what
prove a render is safe -- this file never edits those loaders/tests to make
a render pass.
"""

from __future__ import annotations

from pathlib import Path

from scripts.notion_render import render_all
from ultra_csm.data_plane.notion_reader import load_captured_payload
from ultra_csm.knowledge import load_org_pack, load_playbooks

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
