"""Universe v2 WS-Segmented-Book: tier-policy resolver + battery."""

from __future__ import annotations

from eval.tier_policy_battery import (
    COHORT_THRESHOLD,
    TIER_MIRROR_ACCOUNTS,
    resolve_motions_for_day,
    run_battery,
)
from ultra_csm.data_plane.fixtures import account_id_for


def test_tier_policy_battery_hard_ok():
    report = run_battery()
    assert report["hard_ok"], report["failed_cases"]
    assert len(report["cases"]) == 4


def test_champion_quiet_mirror_differs_by_tier():
    resolved = resolve_motions_for_day(130)
    high_id = account_id_for("ironclad-freight")
    tech_id = account_id_for("farrow-fleet-ops")

    high_motions = {p["motion"] for p in resolved["per_account"].get(high_id, ())}
    tech_motions = {p["motion"] for p in resolved["per_account"].get(tech_id, ())}

    assert "personal_email" in high_motions
    assert "personal_email" not in tech_motions
    assert "campaign_enroll" in tech_motions


def test_shallow_adoption_mirror_differs_by_tier():
    resolved = resolve_motions_for_day(90)
    mid_id = account_id_for("brookstone-supply-chain")
    high_id = account_id_for("sterling-fleet-services")

    mid_motions = {p["motion"] for p in resolved["per_account"].get(mid_id, ())}
    high_motions = {p["motion"] for p in resolved["per_account"].get(high_id, ())}

    assert mid_motions == {"content_route"}
    assert high_motions == {"working_session"}


def test_cohort_collapses_not_25_individual_actions():
    resolved = resolve_motions_for_day(140)
    cohort_slugs = [
        s for s in TIER_MIRROR_ACCOUNTS
        if s not in ("ironclad-freight", "farrow-fleet-ops", "brookstone-supply-chain", "sterling-fleet-services")
    ]
    assert len(cohort_slugs) >= COHORT_THRESHOLD

    cohort_ids = {account_id_for(s) for s in cohort_slugs}
    matching = [c for c in resolved["cohort_actions"] if cohort_ids <= set(c["account_ids"])]
    assert len(matching) == 1

    for account_id in cohort_ids:
        assert account_id not in resolved["per_account"] or not resolved["per_account"][account_id]
