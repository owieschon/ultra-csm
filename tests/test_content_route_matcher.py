"""Offline tests for the trigger-to-content matcher (pure function) and
its disk loader. No CustomerDataPlane, no live Notion -- Decision 9 of
``19_CONTENT_ROADMAP.md``: this module never calls the Notion API."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tests._govhelpers import CLOCK, T1, setup_roster
from ultra_csm.agent1 import run_time_to_value_sweep
from ultra_csm.agent1.content_route_matcher import (
    ContentCatalogEntry,
    load_tenant_content_catalog,
    match_content,
)
from ultra_csm.data_plane import ACME_LOGISTICS, DEFAULT_TENANT, build_sweep_fixture_data_plane
from ultra_csm.governance import ActionGate, FixtureVerdictSource
from ultra_csm.knowledge import PlaybookSet, ServiceTier

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


# --- Phase 5 sweep-integration tests -----------------------------------
# ACME_LOGISTICS (build_sweep_fixture_data_plane's fixture book) resolves
# to high_touch and fires feature_shallow_depth among other triggers
# (verified directly this session). A minimal local PlaybookSet -- not
# fleetops's real playbooks.json -- gives full control over
# forbidden_motions without depending on real playbook content.

_FORBIDDING_PLAYBOOKS = PlaybookSet(
    schema_version=1,
    fictional=True,
    tenant="test-tenant",
    service_tiers=tuple(
        ServiceTier(
            tier=tier,
            rule={},
            allowed_motions=("content_route",),
            forbidden_motions=("personal_email",),
        )
        for tier in ("high_touch", "mid_touch", "tech_touch")
    ),
    plays=(),
)

_ALLOWING_PLAYBOOKS = PlaybookSet(
    schema_version=1,
    fictional=True,
    tenant="test-tenant",
    service_tiers=tuple(
        ServiceTier(tier=tier, rule={}, allowed_motions=("personal_email",), forbidden_motions=())
        for tier in ("high_touch", "mid_touch", "tech_touch")
    ),
    plays=(),
)

_MATCHING_ENTRY = ContentCatalogEntry(
    "c-match", "Feature Depth Guide", "core", "feature_shallow_depth", "guide"
)


@pytest.fixture
def sweep_conn(runtime_conn):
    runtime_conn.execute("BEGIN")
    try:
        yield runtime_conn
    finally:
        runtime_conn.rollback()


def _run_sweep(sweep_conn, *, playbooks):
    orch, _authority = setup_roster(sweep_conn)
    gate = ActionGate(
        sweep_conn, tenant_id=T1, actor_principal_id=orch, verdict_source=FixtureVerdictSource(), now=CLOCK,
    )
    return run_time_to_value_sweep(
        build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
        DEFAULT_TENANT,
        gate,
        sweep_principal_id=orch,
        as_of="2026-06-27",
        playbooks=playbooks,
    )


def test_sweep_integration_content_route_fires_when_tier_forbids_outreach_but_catalog_matches(sweep_conn):
    with patch(
        "ultra_csm.agent1.sweep.load_tenant_content_catalog", return_value=(_MATCHING_ENTRY,)
    ):
        sweep = _run_sweep(sweep_conn, playbooks=_FORBIDDING_PLAYBOOKS)

    acme = next(item for item in sweep.work_items if item.account_id == ACME_LOGISTICS)
    assert acme.recommended_action == "content_route"
    assert acme.disposition == "propose_customer_action"
    assert acme.proposal is not None


def test_sweep_integration_content_route_does_not_fire_without_a_catalog_match(sweep_conn):
    with patch("ultra_csm.agent1.sweep.load_tenant_content_catalog", return_value=()):
        sweep = _run_sweep(sweep_conn, playbooks=_FORBIDDING_PLAYBOOKS)

    acme = next(item for item in sweep.work_items if item.account_id == ACME_LOGISTICS)
    assert acme.recommended_action == "recommend_next_best_action"
    assert acme.proposal is None


def test_sweep_integration_draft_customer_outreach_takes_precedence_over_content_route(sweep_conn):
    """A tier that does NOT forbid personal_email gets draft_customer_outreach
    as usual -- content_route never overrides an account draft_customer_outreach
    already claimed, even when a catalog match exists."""

    with patch(
        "ultra_csm.agent1.sweep.load_tenant_content_catalog", return_value=(_MATCHING_ENTRY,)
    ):
        sweep = _run_sweep(sweep_conn, playbooks=_ALLOWING_PLAYBOOKS)

    acme = next(item for item in sweep.work_items if item.account_id == ACME_LOGISTICS)
    assert acme.recommended_action == "draft_customer_outreach"
