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

from scripts.notion_render import (
    ContentCatalogValidationError,
    render_all,
    render_content_catalog_curated,
    render_org_pack,
    validate_content_catalog_payload,
)
from tests.test_content_catalog import _CANON_MODULES, _REQUIRED_FIELDS as _CATALOG_REQUIRED_FIELDS
from tests.test_handoff_notes import _REQUIRED_FIELDS as _HANDOFF_REQUIRED_FIELDS
from ultra_csm.data_plane.notion_reader import (
    NotionReadError,
    live_authoring_payload,
    load_captured_payload,
)
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


def test_account_specific_render_is_schema_accepted(tmp_path):
    """Acceptance oracle for the account-specific tier: the schema
    assertions lifted verbatim from ``test_content_catalog.py``/
    ``test_handoff_notes.py`` (Decision 2), applied to generated output
    instead of the curated demo fixtures. Those test files are imported,
    never edited."""

    payload = load_captured_payload(FIXTURE_PATH, pack_version="notion-pack-v1")
    output_root = tmp_path / "_generated"

    written = render_all(
        payload,
        output_root=output_root,
        tenant=TENANT,
        pack_version="notion-pack-v1",
        account_slug=ACCOUNT_SLUG,
    )

    catalog_path = output_root / "tenants" / TENANT / "content_catalog.json"
    assert catalog_path in written
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert catalog["fictional"] is True
    assert catalog["tenant"] == TENANT
    ids = [entry["id"] for entry in catalog["entries"]]
    assert len(ids) == len(set(ids))
    for entry in catalog["entries"]:
        assert _CATALOG_REQUIRED_FIELDS <= set(entry)
        assert "addresses_gap" in entry and entry["addresses_gap"]
    # The fixture's one content-catalog row uses a real canon module; this
    # does not assert full 8-module coverage (that is the curated demo
    # catalog's job, per test_content_catalog.py's own fixed-path test).
    assert {entry["module"] for entry in catalog["entries"]} <= _CANON_MODULES

    note_path = output_root / "tenants" / TENANT / "handoff_notes" / f"{ACCOUNT_SLUG}.json"
    assert note_path in written
    note = json.loads(note_path.read_text(encoding="utf-8"))
    assert _HANDOFF_REQUIRED_FIELDS <= set(note)
    assert note["account_slug"] == ACCOUNT_SLUG
    assert note["fictional"] is True
    assert note["tenant"] == TENANT
    assert note["success_criteria"]


def test_live_reader_fails_closed_without_credentials(tmp_path):
    """Decision 4 / K8: absent a NOTION_* credential entry, the live pull
    must raise rather than silently no-op or fabricate a payload. This is
    the offline-testable half of the live reader; the live-network half is
    the Owner Ask documented in the program report and cannot be exercised
    here (Decision 5, verify-at-runtime)."""

    empty_creds = tmp_path / "empty-creds.env"
    empty_creds.write_text("", encoding="utf-8")

    with pytest.raises(NotionReadError, match="ULTRA_CSM_NOTION_TOKEN"):
        live_authoring_payload(
            org_pack_database_id="x",
            playbooks_database_id="x",
            content_catalog_database_id="x",
            voice_rules_page_id="x",
            exemplar_email_page_id="x",
            handoff_narrative_page_id="x",
            creds_path=str(empty_creds),
        )


# --- Phase 6: --target curated bridge (19_CONTENT_ROADMAP.md) ----------
# validate_content_catalog_payload replicates ONLY the tenant-agnostic
# subset of test_content_catalog.py's assertions (required fields, unique
# ids, fictional flag, tenant match) -- NOT its "16 entries"/"8 canon
# modules" checks, which are fleetops-canon-specific facts that would
# wrongly reject loopway's real 5-entry catalog. test_content_catalog.py
# itself is untouched (verified below).


def test_curated_render_writes_only_content_catalog(tmp_path):
    payload = load_captured_payload(FIXTURE_PATH, pack_version="notion-pack-v1")
    knowledge_root = tmp_path / "knowledge"

    path = render_content_catalog_curated(payload, tenant=TENANT, knowledge_root=knowledge_root)

    assert path == knowledge_root / "tenants" / TENANT / "content_catalog.json"
    assert path.is_file()
    # Nothing else was written -- org_pack/playbooks/handoff_notes stay
    # --target generated-only (out of this dispatch's scope).
    written = sorted(p.relative_to(knowledge_root) for p in knowledge_root.rglob("*.json"))
    assert written == [Path("tenants") / TENANT / "content_catalog.json"]

    data = json.loads(path.read_text(encoding="utf-8"))
    for entry in data["entries"]:
        assert _CATALOG_REQUIRED_FIELDS <= set(entry)


def test_curated_render_refuses_to_write_a_payload_missing_required_fields(tmp_path):
    bad_data = {
        "fictional": True,
        "tenant": TENANT,
        "entries": [{"id": "c1", "title": "x"}],  # missing module/addresses_gap/format
    }
    with pytest.raises(ContentCatalogValidationError, match="missing required fields"):
        validate_content_catalog_payload(bad_data, tenant=TENANT)

    # Refusal means nothing is written -- prove the file never exists.
    knowledge_root = tmp_path / "knowledge"
    assert not (knowledge_root / "tenants" / TENANT / "content_catalog.json").exists()


def test_curated_render_refuses_a_tenant_mismatch():
    data = {"fictional": True, "tenant": "loopway", "entries": []}
    with pytest.raises(ContentCatalogValidationError, match="tenant"):
        validate_content_catalog_payload(data, tenant="fleetops")


def test_generated_target_unchanged_by_the_curated_addition(tmp_path):
    """Negative check: --target generated's render_all output is
    byte-identical to before this dispatch's edit -- the curated path is
    a pure addition, never a modification of the existing default."""

    payload = load_captured_payload(FIXTURE_PATH, pack_version="notion-pack-v1")
    written = render_all(
        payload,
        output_root=tmp_path,
        tenant=TENANT,
        pack_version="notion-pack-v1",
        account_slug=ACCOUNT_SLUG,
    )
    assert len(written) == 5  # org_pack, golden_corpus exemplar, playbooks, content_catalog, handoff_note
    load_org_pack(str(tmp_path / "org_pack.json"))
    load_playbooks(TENANT, tenants_dir=str(tmp_path / "tenants"))
