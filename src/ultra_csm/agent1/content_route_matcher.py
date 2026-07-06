"""Trigger-to-content-catalog matching for the ``content_route`` action.

``content_route`` (``governance/csm_actions.py``) has been a defined,
gated CSM action since the Notion authoring edge (Report 34) or earlier,
but nothing has ever proposed it: verified by grep, ``campaigns.py`` runs
exactly one hand-curated static campaign and no trigger-driven matching
exists anywhere. This module is the missing matcher -- pure, no I/O
beyond reading a tenant's own ``content_catalog.json`` from disk, no
Notion API calls (Decision 9 of ``19_CONTENT_ROADMAP.md``: the runtime
never reads Notion live; the only path from Notion-authored content to
here is a human-reviewed ``notion_render.py --target curated`` build
step that updates the same JSON this module reads).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TENANTS_DIR = Path(__file__).resolve().parents[3] / "knowledge" / "tenants"


@dataclass(frozen=True)
class ContentCatalogEntry:
    content_id: str
    title: str
    module: str
    addresses_gap: str
    format: str


def load_tenant_content_catalog(
    tenant: str, *, tenants_dir: Path = DEFAULT_TENANTS_DIR
) -> tuple[ContentCatalogEntry, ...]:
    """Read *tenant*'s ``content_catalog.json`` from disk. Returns an empty
    tuple if the tenant has no catalog file (not every tenant has one --
    e.g. fieldstone/crateworks today)."""

    path = tenants_dir / tenant / "content_catalog.json"
    if not path.is_file():
        return ()
    with path.open() as f:
        raw = json.load(f)
    return tuple(
        ContentCatalogEntry(
            content_id=entry["id"],
            title=entry["title"],
            module=entry["module"],
            addresses_gap=entry["addresses_gap"],
            format=entry["format"],
        )
        for entry in raw["entries"]
    )


def match_content(
    triggers: set[str], catalog_entries: tuple[ContentCatalogEntry, ...]
) -> tuple[ContentCatalogEntry, ...]:
    """Entries whose ``addresses_gap`` is one of *triggers*, in catalog
    order. Pure: no I/O, no data-plane dependency -- takes plain data,
    returns plain data (mirrors ``_account_triggers_for_motion``'s own
    separable-pure-function shape)."""

    return tuple(entry for entry in catalog_entries if entry.addresses_gap in triggers)
