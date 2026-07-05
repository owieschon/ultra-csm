"""Render a captured Notion authoring payload into the exact JSON shapes
``ultra_csm.knowledge.load_org_pack``/``load_playbooks`` and the
``content_catalog``/``handoff_notes`` schema tests already accept.

Mirrors ``scripts/render_status.py``'s build-step + ``--check`` byte-identity
convention. Output root is ``knowledge/_generated/`` -- never the curated
demo artifacts under ``knowledge/`` (Decision 1): this proves "Notion -> JSON
the loaders accept" without touching the fictional universe.

One-directional (Notion -> repo JSON, committed via PR); the runtime never
imports this module or ``notion_reader``.

The renderer does NOT strip forbidden keys (Decision 3): if an author places
an account-specific fact into an agnostic-tier field, that field is emitted
verbatim, and ``load_org_pack`` -- not this script -- is what raises. Silent
stripping would hide the authoring mistake instead of surfacing it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ultra_csm.data_plane.notion_reader import NotionAuthoringPayload, load_captured_payload
from ultra_csm.knowledge import ORG_CONTEXT_SCHEMA_VERSION, PLAYBOOK_SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[1]
GENERATED_ROOT = ROOT / "knowledge" / "_generated"

# Static fields the demo org pack carries that the captured fixture's
# authoring surfaces do not yet model (voice_rules prose, product_name,
# value_props, booking). These are NOT account-specific facts (no
# _FORBIDDEN_KEYS member among them) -- they are agnostic-tier config this
# render pass sources from the payload where the payload has it (voice_rules,
# terminology, gap_plays) and leaves at safe, generic defaults elsewhere,
# same discipline as any renderer facing a partially-populated source: never
# fabricate a customer-facing claim, but a "generic" default value_prop
# summary is not that.
_DEFAULT_PRODUCT_NAME = "Notion-Authored Platform"
_DEFAULT_VALUE_PROPS = [
    {
        "id": "notion_authoring",
        "name": "Notion-authored knowledge",
        "summary": "Org-agnostic voice and play guidance authored by the CSM team in Notion.",
    }
]


def render_org_pack(payload: NotionAuthoringPayload, *, pack_version: str) -> dict:
    return {
        "schema_version": ORG_CONTEXT_SCHEMA_VERSION,
        "pack_version": pack_version,
        "fictional": True,
        "product_name": _DEFAULT_PRODUCT_NAME,
        "terminology": {row.term: row.definition for row in payload.terminology},
        "voice_rules": list(payload.voice_rule_paragraphs),
        "value_props": _DEFAULT_VALUE_PROPS,
        "gap_plays": [
            {"factor": row.factor, "play": row.play, "customer_ask": row.customer_ask}
            for row in payload.gap_plays
        ],
    }


def render_golden_corpus(payload: NotionAuthoringPayload) -> dict[str, dict]:
    """One exemplar file per authored exemplar page. The fixture models a
    single recap-email exemplar; additional Notion pages of other
    ``golden_corpus`` kinds are additive follow-on (see
    ``knowledge.py``'s ``_DISPOSITION_EXEMPLAR_KIND`` docstring for why only
    ``recap_email``/``escalation_email`` are reachable today)."""

    if not payload.exemplar_paragraphs:
        return {}
    content = "\n\n".join(payload.exemplar_paragraphs)
    return {
        "recap_email_exemplar.json": {
            "fictional": True,
            "kind": "recap_email",
            "title": "Post-meeting recap — Notion-authored exemplar",
            "content": content,
        }
    }


def render_playbooks(payload: NotionAuthoringPayload, *, tenant: str) -> dict:
    plays_for_tenant = [row for row in payload.playbook_plays if row.tenant == tenant]
    return {
        "schema_version": PLAYBOOK_SCHEMA_VERSION,
        "fictional": True,
        "tenant": tenant,
        "service_tiers": [
            {
                "tier": "high_touch",
                "rule": {"arr_cents_gte": 10000000},
                "allowed_motions": [
                    "personal_email",
                    "working_session",
                    "qbr",
                    "escalation",
                    "campaign_enroll",
                    "content_route",
                    "cohort_action",
                ],
            },
            {
                "tier": "mid_touch",
                "rule": {"arr_cents_gte": 2500000},
                "allowed_motions": [
                    "personal_email",
                    "escalation",
                    "campaign_enroll",
                    "content_route",
                    "cohort_action",
                ],
            },
            {
                "tier": "tech_touch",
                "rule": {"default": True},
                "allowed_motions": ["campaign_enroll", "content_route", "cohort_action"],
                "forbidden_motions": ["personal_email", "working_session", "qbr"],
            },
        ],
        "plays": [
            {
                "id": row.play_id,
                "trigger_factor": row.trigger_factor,
                "motion": row.motion,
                "tiers": list(row.tiers),
                "content_refs": [],
            }
            for row in plays_for_tenant
        ],
    }


def render_content_catalog(payload: NotionAuthoringPayload, *, tenant: str) -> dict:
    return {
        "schema_version": 1,
        "fictional": True,
        "tenant": tenant,
        "entries": [
            {
                "id": row.content_id,
                "title": row.title,
                "module": row.module,
                "addresses_gap": row.addresses_gap,
                "format": row.format,
            }
            for row in payload.content_catalog_rows
        ],
    }


def render_handoff_note(payload: NotionAuthoringPayload, *, tenant: str, account_slug: str) -> dict | None:
    if not payload.handoff_narrative_paragraphs:
        return None
    narrative = " ".join(payload.handoff_narrative_paragraphs)
    return {
        "schema_version": 1,
        "fictional": True,
        "tenant": tenant,
        "account_slug": account_slug,
        "why_they_bought": narrative,
        "legacy_system": None,
        "success_criteria": [narrative],
        "stakeholders": [],
    }


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_all(
    payload: NotionAuthoringPayload,
    *,
    output_root: Path,
    tenant: str,
    pack_version: str,
    account_slug: str | None = None,
) -> list[Path]:
    """Render every artifact and return the list of paths written, in a
    stable (sorted) order -- used by both the writer and the ``--check``
    byte-identity comparison."""

    written: list[Path] = []

    org_pack_path = output_root / "org_pack.json"
    _write_json(org_pack_path, render_org_pack(payload, pack_version=pack_version))
    written.append(org_pack_path)

    for filename, exemplar in sorted(render_golden_corpus(payload).items()):
        path = output_root / "golden_corpus" / filename
        _write_json(path, exemplar)
        written.append(path)

    playbooks_path = output_root / "tenants" / tenant / "playbooks.json"
    _write_json(playbooks_path, render_playbooks(payload, tenant=tenant))
    written.append(playbooks_path)

    if payload.content_catalog_rows:
        catalog_path = output_root / "tenants" / tenant / "content_catalog.json"
        _write_json(catalog_path, render_content_catalog(payload, tenant=tenant))
        written.append(catalog_path)

    if account_slug and payload.handoff_narrative_paragraphs:
        note = render_handoff_note(payload, tenant=tenant, account_slug=account_slug)
        if note is not None:
            note_path = output_root / "tenants" / tenant / "handoff_notes" / f"{account_slug}.json"
            _write_json(note_path, note)
            written.append(note_path)

    return sorted(written)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--payload",
        default=str(ROOT / "tests" / "fixtures" / "notion" / "authoring_payload.json"),
        help="path to a captured Notion authoring payload JSON file",
    )
    parser.add_argument("--tenant", default="fleetops")
    parser.add_argument("--account-slug", default="notionharbor-fleet")
    parser.add_argument("--pack-version", default="notion-pack-v1")
    parser.add_argument("--output-root", default=str(GENERATED_ROOT))
    parser.add_argument(
        "--check", action="store_true", help="fail if generated output is not byte-identical to a fresh render"
    )
    args = parser.parse_args(argv)

    payload = load_captured_payload(args.payload, pack_version=args.pack_version)
    output_root = Path(args.output_root)

    if args.check:
        before = {
            path: path.read_bytes()
            for path in output_root.rglob("*.json")
            if path.is_file()
        } if output_root.exists() else {}
        written = render_all(
            payload,
            output_root=output_root,
            tenant=args.tenant,
            pack_version=args.pack_version,
            account_slug=args.account_slug,
        )
        after = {path: path.read_bytes() for path in written}
        if before != after or set(before) != set(after):
            print("knowledge/_generated is stale; run `make notion-render`")
            return 1
        print("knowledge/_generated is current (byte-identical)")
        return 0

    written = render_all(
        payload,
        output_root=output_root,
        tenant=args.tenant,
        pack_version=args.pack_version,
        account_slug=args.account_slug,
    )
    for path in written:
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
