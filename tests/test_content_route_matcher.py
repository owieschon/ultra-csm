"""Offline tests for the trigger-to-content matcher (pure function) and
its disk loader. No CustomerDataPlane, no live Notion -- Decision 9 of
``19_CONTENT_ROADMAP.md``: this module never calls the Notion API."""

from __future__ import annotations

from pathlib import Path

from ultra_csm.agent1.content_route_matcher import (
    ContentCatalogEntry,
    load_tenant_content_catalog,
    match_content,
)

_ENTRIES = (
    ContentCatalogEntry("c1", "Feature Depth Guide", "core", "feature_shallow_depth", "guide"),
    ContentCatalogEntry("c2", "Health Recovery Playbook", "core", "health_red", "playbook"),
    ContentCatalogEntry("c3", "Champion Handoff", "core", "champion_inactive", "one_pager"),
)


def test_match_content_returns_entries_whose_gap_is_in_triggers():
    matched = match_content({"feature_shallow_depth", "outcome_unknown"}, _ENTRIES)
    assert matched == (_ENTRIES[0],)


def test_match_content_returns_empty_when_no_trigger_matches():
    assert match_content({"outcome_unknown"}, _ENTRIES) == ()


def test_match_content_can_return_multiple_entries():
    matched = match_content({"health_red", "champion_inactive"}, _ENTRIES)
    assert matched == (_ENTRIES[1], _ENTRIES[2])


def test_load_tenant_content_catalog_reads_real_fleetops_file():
    entries = load_tenant_content_catalog("fleetops")
    assert len(entries) == 16
    assert all(isinstance(e, ContentCatalogEntry) for e in entries)
    gaps = {e.addresses_gap for e in entries}
    # Post-relabel (Decision 2): none of the 5 merged/renamed categories survive.
    assert not gaps & {
        "underused_capability",
        "activation_stalled",
        "single_threaded_risk",
        "renewal_risk",
        "low_engagement",
    }
    # The 3 explicitly-unmatched categories (no corresponding trigger) are untouched.
    assert gaps & {"alert_fatigue", "integration_blocker"}


def test_load_tenant_content_catalog_reads_real_loopway_file():
    entries = load_tenant_content_catalog("loopway")
    assert len(entries) == 5


def test_load_tenant_content_catalog_returns_empty_for_missing_tenant():
    assert load_tenant_content_catalog("fieldstone") == ()
    assert load_tenant_content_catalog("no-such-tenant") == ()
