"""Offline tests for content_roadmap_push.py's write mechanics -- no live
Notion calls. The live smoke (real database create/update, idempotency
across two real runs) is a separate DoD row, BLOCKED per K8: the
ULTRA_CSM_NOTION_TOKEN integration has zero pages shared with it
(verified 2026-07-05, see PROGRESS.md/BLOCKED.md), an Owner Ask, not
something more test coverage here can substitute for."""

from __future__ import annotations

from unittest.mock import patch

from scripts.content_roadmap_push import (
    _unwrap_placeholder_brackets,
    push_content_roadmap,
    upsert_row,
)
from ultra_csm.content_roadmap import RoadmapRow

_ROW = RoadmapRow(
    tenant="fleetops",
    gap="health_red",
    accounts_affected=5,
    high_arr_bonus=1,
    existing_content_count=2,
    coverage_gap_score=4,
)


def test_unwrap_placeholder_brackets_strips_angle_brackets():
    assert _unwrap_placeholder_brackets("<ntn_abc123>") == "ntn_abc123"


def test_unwrap_placeholder_brackets_leaves_plain_value_untouched():
    assert _unwrap_placeholder_brackets("ntn_abc123") == "ntn_abc123"


def test_dry_run_never_touches_the_network():
    with patch("scripts.content_roadmap_push._notion_request") as mock_request:
        result = push_content_roadmap(dry_run=True)
    mock_request.assert_not_called()
    assert result["dry_run"] is True
    assert len(result["rows"]) > 0


def test_upsert_row_updates_existing_row_numeric_properties_only():
    """Decision 6: an existing (Tenant, Gap) row gets a PATCH with only
    the 4 numeric properties -- Status is never included in the update
    payload, so a human-set Status can never be silently overwritten."""

    with patch("scripts.content_roadmap_push.find_existing_row", return_value="page-123"):
        with patch("scripts.content_roadmap_push._notion_request") as mock_request:
            page_id, created = upsert_row(token="tok", data_source_id="ds-1", row=_ROW)

    assert page_id == "page-123"
    assert created is False
    mock_request.assert_called_once()
    _method, _path = mock_request.call_args[0]
    body = mock_request.call_args[1]["body"]
    assert "Status" not in body["properties"]
    assert body["properties"]["Coverage Gap Score"]["number"] == 4


def test_upsert_row_creates_new_row_with_default_status():
    with patch("scripts.content_roadmap_push.find_existing_row", return_value=None):
        with patch("scripts.content_roadmap_push._notion_request") as mock_request:
            page_id, created = upsert_row(token="tok", data_source_id="ds-1", row=_ROW)

    assert created is True
    body = mock_request.call_args[1]["body"]
    assert body["properties"]["Status"]["select"]["name"] == "Not Started"
