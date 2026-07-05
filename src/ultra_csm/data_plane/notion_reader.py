"""Notion authoring-edge reader: parses a captured Notion API payload into a
typed, renderer-facing contract, and (live path) pulls that payload from the
real Notion API read-only.

This module is the parse/map half of the authoring edge; ``scripts/
notion_render.py`` is the render half that turns the parsed contract into
the exact JSON shapes ``ultra_csm.knowledge.load_org_pack``/``load_playbooks``
and the ``content_catalog``/``handoff_notes`` schema tests already accept.
Notion is an authoring front door only -- nothing in the runtime (``tick.py``,
``agent1/sweep.py``) imports this module.

Response shapes mirror Notion's documented API (accessed 2026-07-05):
- data source query: https://developers.notion.com/reference/query-a-data-source
  (``{"object": "list", "results": [...], "has_more": bool, "next_cursor": str|None}``)
- page properties: https://developers.notion.com/reference/page-property-values
  (typed properties: ``select``, ``multi_select``, ``rich_text``, ``title``)
- block children: https://developers.notion.com/reference/get-block-children
- block object: https://developers.notion.com/reference/block

Worked example (Decision 5): a Notion ``select`` property maps to a
``motion`` enum value -- this reader emits the raw string from
``property["select"]["name"]`` and does NOT pre-validate it against
``PLAYBOOK_MOTIONS``. An unknown motion string is a renderer-emits,
loader-rejects situation: ``ultra_csm.knowledge._validate_motions`` is the
sole authority that raises on it (K14 -- never re-implement the loader's
validation in the reader).

Auth (verify-at-runtime, Decision 5): a Notion internal integration
authenticates with ``Authorization: Bearer <token>``
(https://developers.notion.com/docs/authorization). This reader mirrors
``live_gmail_reader.py``'s direct-parse-of-the-creds-file pattern (rather
than the heavier ``connector_catalog``/``live_smoke`` HTTP-smoke framework
used by Salesforce/Attio/Gainsight, which this dispatch does not touch):
read ``ULTRA_CSM_NOTION_TOKEN`` from ``~/ultra-csm-live-creds.env``, raise if
absent. Read-only: this module only ever issues GET/POST *query* requests
against the Notion REST API, never a page/block write endpoint.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import request as urllib_request


_CREDS_PATH_ENV = "ULTRA_CSM_NOTION_CREDS_PATH"
_DEFAULT_CREDS_PATH = "~/ultra-csm-live-creds.env"
_TOKEN_KEY = "ULTRA_CSM_NOTION_TOKEN"
_NOTION_API_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2025-09-03"


class NotionReadError(RuntimeError):
    """Raised when a live Notion read cannot proceed (missing creds, bad shape)."""


def _env(env: dict[str, str], key: str) -> str:
    value = env.get(key, "")
    if not value:
        raise KeyError(key)
    return value


def _missing_env(env: dict[str, str]) -> tuple[str, ...]:
    return tuple(key for key in (_TOKEN_KEY,) if not env.get(key))


def _load_creds_file(path: str | None = None) -> dict[str, str]:
    """Parse ``KEY=value`` lines from the credentials env file, mirroring
    ``live_gmail_reader._imap_connect``'s direct-parse approach rather than
    pulling in the ``connector_catalog`` registry (out of this dispatch's
    OWNS list). Missing file -> empty dict, same fail-closed-at-point-of-use
    discipline as the gmail reader (the caller raises when a required key is
    absent, not this loader)."""

    creds_path = os.path.expanduser(path or os.environ.get(_CREDS_PATH_ENV) or _DEFAULT_CREDS_PATH)
    env: dict[str, str] = {}
    if not os.path.exists(creds_path):
        return env
    for line in open(creds_path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


@dataclass(frozen=True)
class NotionGapPlayRow:
    factor: str
    play: str
    customer_ask: str


@dataclass(frozen=True)
class NotionTerminologyRow:
    term: str
    definition: str


@dataclass(frozen=True)
class NotionPlaybookPlayRow:
    tenant: str
    play_id: str
    trigger_factor: str
    motion: str
    tiers: tuple[str, ...]


@dataclass(frozen=True)
class NotionContentCatalogRow:
    content_id: str
    title: str
    module: str
    addresses_gap: str
    format: str


@dataclass(frozen=True)
class NotionAuthoringPayload:
    """The reader's parsed-input contract: everything the renderer needs,
    already lifted out of Notion's typed-property/block wrapper shapes into
    plain strings/tuples. The renderer maps THIS into loader/schema-accepted
    JSON; this dataclass carries no opinions about org_pack/playbook/
    content_catalog/handoff_notes field names."""

    gap_plays: tuple[NotionGapPlayRow, ...]
    terminology: tuple[NotionTerminologyRow, ...]
    playbook_plays: tuple[NotionPlaybookPlayRow, ...]
    content_catalog_rows: tuple[NotionContentCatalogRow, ...]
    voice_rule_paragraphs: tuple[str, ...]
    exemplar_paragraphs: tuple[str, ...]
    handoff_narrative_paragraphs: tuple[str, ...]
    pack_version: str | None = None


def _rich_text_plain(rich_text: list[dict[str, Any]]) -> str:
    return "".join(fragment.get("plain_text", "") for fragment in rich_text)


def _property_text(properties: dict[str, Any], name: str) -> str | None:
    prop = properties.get(name)
    if not isinstance(prop, dict):
        return None
    ptype = prop.get("type")
    if ptype == "title":
        return _rich_text_plain(prop.get("title", []))
    if ptype == "rich_text":
        return _rich_text_plain(prop.get("rich_text", []))
    if ptype == "select":
        select = prop.get("select")
        return select.get("name") if isinstance(select, dict) else None
    return None


def _property_multi_select(properties: dict[str, Any], name: str) -> tuple[str, ...]:
    prop = properties.get(name)
    if not isinstance(prop, dict) or prop.get("type") != "multi_select":
        return ()
    return tuple(item.get("name", "") for item in prop.get("multi_select", []))


def _paragraph_texts(block_children_response: dict[str, Any]) -> tuple[str, ...]:
    """Extract every paragraph block's plain text, in document order. Other
    block types (headings, etc.) are structural and skipped -- the renderer
    only needs the authored prose."""

    texts: list[str] = []
    for block in block_children_response.get("results", []):
        if block.get("type") != "paragraph":
            continue
        rich_text = block.get("paragraph", {}).get("rich_text", [])
        text = _rich_text_plain(rich_text)
        if text:
            texts.append(text)
    return tuple(texts)


def parse_authoring_payload(
    raw: dict[str, Any],
    *,
    pack_version: str | None = None,
) -> NotionAuthoringPayload:
    """Parse a captured (or live-fetched) Notion payload -- shaped like
    ``tests/fixtures/notion/authoring_payload.json`` -- into the reader's
    typed contract. Unknown/malformed rows are skipped defensively at parse
    time (a Notion database row missing its title property is an authoring
    mistake, not a crash); the two-tier isolation and schema contracts are
    enforced downstream by the unmodified loaders/tests, not here (K14)."""

    gap_plays: list[NotionGapPlayRow] = []
    terminology: list[NotionTerminologyRow] = []
    for page in raw.get("org_pack_database", {}).get("results", []):
        props = page.get("properties", {})
        kind = _property_text(props, "Row Kind")
        if kind == "gap_play":
            factor = _property_text(props, "Factor")
            play = _property_text(props, "Play")
            ask = _property_text(props, "Customer Ask")
            if factor and play and ask:
                gap_plays.append(NotionGapPlayRow(factor=factor, play=play, customer_ask=ask))
        elif kind == "terminology":
            term = _property_text(props, "Term")
            definition = _property_text(props, "Definition")
            if term and definition:
                terminology.append(NotionTerminologyRow(term=term, definition=definition))

    playbook_plays: list[NotionPlaybookPlayRow] = []
    for page in raw.get("playbooks_database", {}).get("results", []):
        props = page.get("properties", {})
        tenant = _property_text(props, "Tenant")
        play_id = _property_text(props, "Play ID")
        trigger = _property_text(props, "Trigger Factor")
        motion = _property_text(props, "Motion")
        tiers = _property_multi_select(props, "Tiers")
        if tenant and play_id and trigger and motion:
            playbook_plays.append(
                NotionPlaybookPlayRow(
                    tenant=tenant,
                    play_id=play_id,
                    trigger_factor=trigger,
                    motion=motion,
                    tiers=tiers,
                )
            )

    content_catalog_rows: list[NotionContentCatalogRow] = []
    for page in raw.get("content_catalog_database", {}).get("results", []):
        props = page.get("properties", {})
        content_id = _property_text(props, "Content ID")
        title = _property_text(props, "Title")
        module = _property_text(props, "Module")
        addresses_gap = _property_text(props, "Addresses Gap")
        fmt = _property_text(props, "Format")
        if content_id and title and module and addresses_gap and fmt:
            content_catalog_rows.append(
                NotionContentCatalogRow(
                    content_id=content_id,
                    title=title,
                    module=module,
                    addresses_gap=addresses_gap,
                    format=fmt,
                )
            )

    voice_rule_paragraphs = _paragraph_texts(raw.get("voice_rules_page_blocks", {}))
    exemplar_paragraphs = _paragraph_texts(raw.get("exemplar_email_page_blocks", {}))
    handoff_narrative_paragraphs = _paragraph_texts(raw.get("handoff_narrative_page_blocks", {}))

    return NotionAuthoringPayload(
        gap_plays=tuple(gap_plays),
        terminology=tuple(terminology),
        playbook_plays=tuple(playbook_plays),
        content_catalog_rows=tuple(content_catalog_rows),
        voice_rule_paragraphs=voice_rule_paragraphs,
        exemplar_paragraphs=exemplar_paragraphs,
        handoff_narrative_paragraphs=handoff_narrative_paragraphs,
        pack_version=pack_version,
    )


def load_captured_payload(fixture_path: str, *, pack_version: str | None = None) -> NotionAuthoringPayload:
    """Offline path: parse a captured payload file (e.g. the checked-in
    fixture) exactly as the live path would parse a real API response."""

    raw = json.loads(open(fixture_path, encoding="utf-8").read())
    return parse_authoring_payload(raw, pack_version=pack_version)


def _notion_get(url: str, *, token: str) -> dict[str, Any]:
    req = urllib_request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": _NOTION_VERSION,
            "accept": "application/json",
        },
        method="GET",
    )
    with urllib_request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https host, read-only GET.
        return json.loads(resp.read().decode("utf-8"))


def _notion_post(url: str, *, token: str, body: dict[str, Any]) -> dict[str, Any]:
    """Query a data source is documented as POST with a JSON body
    (https://developers.notion.com/reference/query-a-data-source, verified
    2026-07-05) -- unlike get-block-children, which really is GET. An empty
    body means "no filter": per the same docs, non-archived pages are
    returned with pagination when no filter is supplied."""

    req = urllib_request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": _NOTION_VERSION,
            "accept": "application/json",
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https host, read-only query.
        return json.loads(resp.read().decode("utf-8"))


def live_authoring_payload(
    *,
    org_pack_database_id: str,
    playbooks_database_id: str,
    content_catalog_database_id: str,
    voice_rules_page_id: str,
    exemplar_email_page_id: str,
    handoff_narrative_page_id: str,
    creds_path: str | None = None,
    pack_version: str | None = None,
) -> NotionAuthoringPayload:
    """Live, read-only pull: query each configured Notion data source and
    page, assemble the same wrapper shape ``parse_authoring_payload`` expects
    (mirrors ``live_gmail_reader.live_email_thread``'s pattern of reshaping a
    live fetch into the exact dict the offline-tested parser consumes).
    Raises :class:`NotionReadError` if ``ULTRA_CSM_NOTION_TOKEN`` is absent --
    this is the Owner Ask path (Decision 4 / K8): no live pull is attempted
    without a real credential."""

    env = _load_creds_file(creds_path)
    missing = _missing_env(env)
    if missing:
        raise NotionReadError(
            f"missing Notion credential(s) in {creds_path or _DEFAULT_CREDS_PATH}: {', '.join(missing)}"
        )
    token = _env(env, _TOKEN_KEY)

    def query_database(database_id: str) -> dict[str, Any]:
        return _notion_post(f"{_NOTION_API_BASE}/data_sources/{database_id}/query", token=token, body={})

    def block_children(page_id: str) -> dict[str, Any]:
        return _notion_get(f"{_NOTION_API_BASE}/blocks/{page_id}/children", token=token)

    raw = {
        "org_pack_database": query_database(org_pack_database_id),
        "playbooks_database": query_database(playbooks_database_id),
        "content_catalog_database": query_database(content_catalog_database_id),
        "voice_rules_page_blocks": block_children(voice_rules_page_id),
        "exemplar_email_page_blocks": block_children(exemplar_email_page_id),
        "handoff_narrative_page_blocks": block_children(handoff_narrative_page_id),
    }
    return parse_authoring_payload(raw, pack_version=pack_version)
