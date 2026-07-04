"""Content catalog schema/coverage check (Universe v2, WS-Data-Classes
Phase 3)."""

from __future__ import annotations

import json
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "tenants" / "fleetops" / "content_catalog.json"

_CANON_MODULES = {
    "core_telematics", "route_optimization", "driver_coaching", "maintenance_alerts",
    "advanced_reporting", "compliance_dashboard", "fuel_analytics", "dispatch_automation",
}

_REQUIRED_FIELDS = {"id", "title", "module", "addresses_gap", "format"}


def _load() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def test_catalog_has_sixteen_entries():
    data = _load()
    assert len(data["entries"]) == 16


def test_catalog_covers_all_eight_canon_modules():
    data = _load()
    modules = {e["module"] for e in data["entries"]}
    assert _CANON_MODULES <= modules


def test_catalog_entries_have_required_fields_and_unique_ids():
    data = _load()
    ids = [e["id"] for e in data["entries"]]
    assert len(ids) == len(set(ids))
    for entry in data["entries"]:
        assert _REQUIRED_FIELDS <= set(entry)


def test_catalog_is_marked_fictional():
    data = _load()
    assert data["fictional"] is True
    assert data["tenant"] == "fleetops"
