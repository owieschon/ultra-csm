"""Push the content roadmap (``content_roadmap.build_content_roadmap``) to
a live Notion "Content Roadmap" database, idempotently.

Mirrors ``data_plane/notion_reader.py``'s raw-HTTP + token-auth pattern
(``_load_creds_file``, ``ULTRA_CSM_NOTION_TOKEN``, ``Notion-Version``) --
NOT the MCP session tools, which are unavailable to a standalone
``make``-invoked script. Also mirrors its GET/POST helpers, extended with
PATCH (property update) and the create-database/create-page calls this
push direction needs that the read-only reader never required.

Decision 6 (idempotent upsert): re-running this script updates only the
4 numeric columns (Accounts Affected, High-ARR Accounts Affected,
Existing Content Count, Coverage Gap Score) for an existing (Tenant, Gap)
row; ``Status`` is set to "Not Started" ONLY when creating a new row and
is never touched on update -- it is a human-owned tracking field once
created.

Live credential gate mirrors ``notion_reader.py``'s own precedent: no
push is attempted without ``ULTRA_CSM_NOTION_TOKEN``; a bracket-wrapped
placeholder value is unwrapped exactly as this session's earlier live
smokes required for the Rocketlane/Notion keys.
"""

from __future__ import annotations

import argparse
import json
import os
from urllib import error as urllib_error
from urllib import request as urllib_request

from ultra_csm.content_roadmap import RoadmapRow, build_content_roadmap

_CREDS_PATH_ENV = "ULTRA_CSM_NOTION_CREDS_PATH"
_DEFAULT_CREDS_PATH = "~/ultra-csm-live-creds.env"
_TOKEN_KEY = "ULTRA_CSM_NOTION_TOKEN"
_NOTION_API_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2025-09-03"

_DATABASE_TITLE = "Content Roadmap"


class ContentRoadmapPushError(RuntimeError):
    """Raised when a live Notion push cannot proceed (missing creds, no
    access, or an unexpected API response)."""


def _load_creds_file(path: str | None = None) -> dict[str, str]:
    creds_path = os.path.expanduser(path or os.environ.get(_CREDS_PATH_ENV) or _DEFAULT_CREDS_PATH)
    env: dict[str, str] = {}
    if not os.path.exists(creds_path):
        return env
    for line in open(creds_path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = _unwrap_placeholder_brackets(value.strip())
    return env


def _unwrap_placeholder_brackets(value: str) -> str:
    """Some pasted credentials in ~/ultra-csm-live-creds.env are wrapped in
    <...> (a placeholder-looking artifact of how they were copied) --
    verified this session on both the Rocketlane and Notion keys. Strip it
    rather than sending a token Notion will reject as malformed."""

    if value.startswith("<") and value.endswith(">"):
        return value[1:-1].strip()
    return value


def _read_token(creds_path: str | None = None) -> str:
    env = _load_creds_file(creds_path)
    token = env.get(_TOKEN_KEY)
    if not token:
        raise ContentRoadmapPushError(
            f"{_TOKEN_KEY} not found in {creds_path or _DEFAULT_CREDS_PATH} -- "
            "live push requires a real Notion credential (Owner Ask)."
        )
    return token


def _notion_request(
    method: str, path: str, *, token: str, body: dict | None = None
) -> dict:
    req = urllib_request.Request(
        f"{_NOTION_API_BASE}{path}",
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": _NOTION_VERSION,
            "accept": "application/json",
            "content-type": "application/json",
        },
        method=method,
    )
    with urllib_request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https host.
        return json.loads(resp.read().decode("utf-8"))


def find_content_roadmap_parent(*, token: str) -> str:
    """Locate the parent page the existing "Content Catalog"/"Org Pack"
    databases live under (Decision 8), via a live, unfiltered search --
    the new database must live under the SAME parent. Raises if nothing
    is found (a real structural gap -- the integration may lack access to
    any page at all; verify with Notion's "Add connections" UI before
    retrying, not by varying the search query).

    Titles are matched by SUBSTRING, not exact equality: the real
    databases are titled "Content Catalog (FleetOps)"/"Org Pack
    (FleetOps)", not the bare names (verified live 2026-07-05, an exact-
    match version of this function silently found nothing despite real
    access being granted). A data_source object carries its own
    ``database_parent`` convenience field (Notion API 2025-09-03) giving
    the ultimate page_id directly -- ``parent`` itself is only a
    ``database_id``, one level short of the page."""

    data = _notion_request("POST", "/search", token=token, body={})
    for result in data.get("results", []):
        if result.get("object") != "data_source":
            continue
        title = "".join(t.get("plain_text", "") for t in result.get("title", []))
        if "Content Catalog" in title or "Org Pack" in title:
            database_parent = result.get("database_parent", {})
            if database_parent.get("type") == "page_id":
                return database_parent["page_id"]
    raise ContentRoadmapPushError(
        "Could not locate the existing Content Catalog/Org Pack databases via "
        "live search, or their parent page, despite the integration having "
        "real search access. This is a structural gap needing manual "
        "investigation in Notion's UI, not a credential/access problem."
    )


_EXPECTED_PROPERTY_NAMES = {"Gap", "Tenant", "Accounts Affected", "Coverage Gap Score"}


def find_existing_database(*, token: str, title: str = _DATABASE_TITLE) -> str | None:
    """A same-titled data source with the WRONG schema is treated as no
    match, not reused -- verified live 2026-07-05: an earlier create call
    (before the initial_data_source fix) silently produced a "Content
    Roadmap" data source with only the default "Name" title property,
    and querying it for "Tenant" 400s. That stray artifact is left in
    place (a destructive trash/delete on a search-found, not
    self-created-this-run, resource was correctly denied by the auto-mode
    classifier) -- an Owner cleanup, not something this function silently
    papers over by reusing it anyway."""

    data = _notion_request(
        "POST", "/search", token=token, body={"query": title}
    )
    for result in data.get("results", []):
        if result.get("object") != "data_source":
            continue
        result_title = "".join(t.get("plain_text", "") for t in result.get("title", []))
        if result_title != title:
            continue
        properties = set(result.get("properties", {}))
        if _EXPECTED_PROPERTY_NAMES <= properties:
            return result["id"]
    return None


def create_content_roadmap_database(*, token: str, parent_page_id: str) -> str:
    """Returns the DATA SOURCE id (not the database id) -- everything
    downstream (find_existing_row/upsert_row) queries via
    /data_sources/{id}, matching what find_existing_database already
    returns from search. Notion API 2025-09-03: property schema for a
    new database's first data source goes under initial_data_source,
    never top-level (verified live 2026-07-05 against a first attempt
    that silently created a database with only the default "Name" title
    property -- top-level "properties" is accepted but ignored, not
    rejected, so this fails silently if not checked)."""

    body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": _DATABASE_TITLE}}],
        "initial_data_source": {
            "properties": {
                "Gap": {"type": "title", "title": {}},
                "Tenant": {
                    "type": "select",
                    "select": {"options": [{"name": t} for t in ("fleetops", "loopway")]},
                },
                "Accounts Affected": {"type": "number", "number": {"format": "number"}},
                "High-ARR Accounts Affected": {"type": "number", "number": {"format": "number"}},
                "Existing Content Count": {"type": "number", "number": {"format": "number"}},
                "Coverage Gap Score": {"type": "number", "number": {"format": "number"}},
                "Status": {
                    "type": "select",
                    "select": {
                        "options": [
                            {"name": "Not Started"},
                            {"name": "In Progress"},
                            {"name": "Published"},
                        ]
                    },
                },
            }
        },
    }
    created = _notion_request("POST", "/databases", token=token, body=body)
    data_sources = created.get("data_sources", [])
    if not data_sources:
        raise ContentRoadmapPushError(
            f"POST /databases response had no data_sources: {created!r}"
        )
    return data_sources[0]["id"]


def find_existing_row(*, token: str, data_source_id: str, row: RoadmapRow) -> str | None:
    """Query-before-write, keyed on (Tenant, Gap) per Decision 6."""

    body = {
        "filter": {
            "and": [
                {"property": "Tenant", "select": {"equals": row.tenant}},
                {"property": "Gap", "title": {"equals": row.gap}},
            ]
        }
    }
    data = _notion_request(
        "POST", f"/data_sources/{data_source_id}/query", token=token, body=body
    )
    results = data.get("results", [])
    return results[0]["id"] if results else None


def _numeric_properties(row: RoadmapRow) -> dict:
    return {
        "Accounts Affected": {"number": row.accounts_affected},
        "High-ARR Accounts Affected": {"number": row.high_arr_bonus},
        "Existing Content Count": {"number": row.existing_content_count},
        "Coverage Gap Score": {"number": row.coverage_gap_score},
    }


def upsert_row(*, token: str, data_source_id: str, row: RoadmapRow) -> tuple[str, bool]:
    """Returns (page_id, created). Updates only the 4 numeric properties on
    an existing row -- Status is never touched here (Decision 6)."""

    existing_page_id = find_existing_row(token=token, data_source_id=data_source_id, row=row)
    if existing_page_id is not None:
        _notion_request(
            "PATCH",
            f"/pages/{existing_page_id}",
            token=token,
            body={"properties": _numeric_properties(row)},
        )
        return existing_page_id, False

    properties = {
        "Gap": {"title": [{"type": "text", "text": {"content": row.gap}}]},
        "Tenant": {"select": {"name": row.tenant}},
        "Status": {"select": {"name": "Not Started"}},
        **_numeric_properties(row),
    }
    created = _notion_request(
        "POST",
        "/pages",
        token=token,
        # A page's parent under a database is data_source_id in this API
        # version (2025-09-03), not database_id -- confirmed live 2026-07-05
        # against an existing Content Catalog row's own parent shape.
        body={"parent": {"data_source_id": data_source_id}, "properties": properties},
    )
    return created["id"], True


def push_content_roadmap(*, dry_run: bool = False, creds_path: str | None = None) -> dict:
    rows = build_content_roadmap()
    if dry_run:
        return {
            "dry_run": True,
            "rows": [row.__dict__ for row in rows],
        }

    token = _read_token(creds_path)
    data_source_id = find_existing_database(token=token)
    if data_source_id is None:
        parent_page_id = find_content_roadmap_parent(token=token)
        data_source_id = create_content_roadmap_database(token=token, parent_page_id=parent_page_id)

    created_count = 0
    updated_count = 0
    for row in rows:
        _page_id, created = upsert_row(token=token, data_source_id=data_source_id, row=row)
        if created:
            created_count += 1
        else:
            updated_count += 1

    return {
        "dry_run": False,
        "data_source_id": data_source_id,
        "rows_created": created_count,
        "rows_updated": updated_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        result = push_content_roadmap(dry_run=args.dry_run)
    except (ContentRoadmapPushError, urllib_error.HTTPError, urllib_error.URLError) as exc:
        print(f"content-roadmap-push failed: {exc}")
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
