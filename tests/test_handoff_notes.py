"""Sales->CS handoff notes: schema/coverage + verbatim-consistency check
against the bible dossier strings (Universe v2, WS-Data-Classes Phase 5)."""

from __future__ import annotations

import json
from pathlib import Path

HANDOFF_DIR = Path(__file__).resolve().parents[1] / "knowledge" / "tenants" / "fleetops" / "handoff_notes"

_ARC_ACCOUNTS = (
    "pinehill-transport", "pinnacle-supply", "quarrystone-logistics",
    "aspenridge-supply", "meridian-fleet", "trailhead-logistics",
)
_HERRINGS = ("cedar-valley", "ironridge-fleet")
_ALL_ACCOUNTS = _ARC_ACCOUNTS + _HERRINGS

_REQUIRED_FIELDS = {
    "schema_version", "fictional", "tenant", "account_slug",
    "why_they_bought", "legacy_system", "success_criteria", "stakeholders",
}

# The bible dossier's exact legacy-system string per account (or None where
# canon names none) -- docs/SYNTHETIC_UNIVERSE_BIBLE.md's per-account
# dossiers section, cross-checked verbatim.
_BIBLE_LEGACY_SYSTEM = {
    "pinehill-transport": "RouteLedger 5.2",
    "pinnacle-supply": "a homegrown dispatch spreadsheet",
    "quarrystone-logistics": None,
    "aspenridge-supply": "a mix of spreadsheets and a regional ELD-compliance tool",
    "meridian-fleet": "FleetTrak Enterprise",
    "trailhead-logistics": "a patchwork of spreadsheets and a regional compliance-reporting tool",
    "cedar-valley": None,
    "ironridge-fleet": None,
}


def _load(slug: str) -> dict:
    return json.loads((HANDOFF_DIR / f"{slug}.json").read_text(encoding="utf-8"))


def test_all_eight_accounts_have_a_handoff_note():
    for slug in _ALL_ACCOUNTS:
        assert (HANDOFF_DIR / f"{slug}.json").exists(), slug


def test_every_note_has_required_fields():
    for slug in _ALL_ACCOUNTS:
        data = _load(slug)
        assert _REQUIRED_FIELDS <= set(data), slug
        assert data["account_slug"] == slug
        assert data["fictional"] is True
        assert data["tenant"] == "fleetops"


def test_legacy_system_matches_bible_dossier_verbatim():
    for slug, expected in _BIBLE_LEGACY_SYSTEM.items():
        data = _load(slug)
        assert data["legacy_system"] == expected, slug


def test_stakeholders_have_name_and_title():
    for slug in _ALL_ACCOUNTS:
        data = _load(slug)
        assert len(data["stakeholders"]) >= 1, slug
        for s in data["stakeholders"]:
            assert s["name"]
            assert s["title"]


def test_success_criteria_is_nonempty():
    for slug in _ALL_ACCOUNTS:
        data = _load(slug)
        assert len(data["success_criteria"]) >= 1, slug
