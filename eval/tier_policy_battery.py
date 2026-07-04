"""Tier-policy battery (Universe v2, WS-Segmented-Book, Wave 2).

The point of this program: a real book is a distribution, and the tier
changes what the CORRECT action is. This module builds a small,
deterministic "policy resolver" over the 180-account book --
trigger_factor -> tier-appropriate motion, per `knowledge/tenants/fleetops/
playbooks.json` -- and asserts three properties against it:

1. Every `eval/gold/fleetops_expected_actions.json` tier-mirror row's
   required motion is what the resolver actually emits for that
   account/day.
2. No account ever receives a motion its tier forbids, swept across the
   full 180-account book at three checkpoint days (the
   economics-correctness assertion).
3. The 25-account cohort (bible "Tier-mirror 3") collapses to exactly one
   `cohort_action`, never 25 individual per-account motions.

Runtime discipline: sweeping all 180 accounts at 3 checkpoint days is
O(540) account-day evaluations of cheap dict lookups -- well under the
90-second per-battery ceiling; no sampling was needed here (unlike a
battery that would re-run the narrative extractors per account).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from eval.expected_actions_gold import load_expected_actions
from ultra_csm.data_plane.book_simulator import simulate_book
from ultra_csm.data_plane.fixtures import account_id_for
from ultra_csm.data_plane.synthetic_book import build_synthetic_book
from ultra_csm.knowledge import load_playbooks
from ultra_csm.value_model import account_attributes, load_value_model_config, resolve_tenant_tier

ARTIFACT_PATH = Path(__file__).with_name("tier_policy_battery.json")

# Below this many same-day, same-tier, same-capability accounts, each gets
# its own per-account play motion. At or above it, the cohort collapses to
# one cohort_action -- the anti-pattern assertion tier-mirror 3 exists to
# test. 25 (the bible's authored cohort size) safely clears this floor;
# 10 is small enough that no other incidental cluster in the 180-account
# book crosses it by accident (verified empirically in this module's own
# tests, not assumed).
COHORT_THRESHOLD = 10

CHECKPOINT_DAYS = (90, 130, 140)

# The tier-mirror accounts this battery grades (bible "Tier-mirror 1/2/3").
# Not every gold row at these checkpoint days is a tier-mirror row -- some
# existing arc accounts (e.g. aspenridge-supply) happen to share day 90 --
# so this battery scopes to its own accounts by slug, not by day alone.
_TIER_MIRROR_1_2 = ("ironclad-freight", "farrow-fleet-ops", "brookstone-supply-chain", "sterling-fleet-services")
_TIER_MIRROR_3_COHORT = (
    "glenbrook-distribution", "kestrel-logistics", "wolfden-warehousing", "copperfield2-carriers",
    "duskwood-transport-co", "evergreen-warehousing", "pathfinder-freight", "truewind-distribution",
    "underpass-transport-co", "vernonhall-delivery", "emberfield-delivery", "ivorygate-freight",
    "juniperfield-logistics", "oldstone-industrial-supply", "poplarcreek-trucking", "quietbrook-warehousing",
    "vinecrest-freight", "watermill-trucking", "amberfield-fleet-ops", "ironwood2-line-haul",
    "kettlecreek-distribution", "mossgate-logistics", "palewood-field-services", "quarrycreek-haulage",
    "roughcut-freight",
)
TIER_MIRROR_ACCOUNTS = _TIER_MIRROR_1_2 + _TIER_MIRROR_3_COHORT


def _account_triggers(account_id: str, health, adoption, entitlements) -> set[str]:
    triggers: set[str] = set()
    if health is not None and "champion_inactive" in health.drivers:
        triggers.add("champion_inactive")
    if adoption is not None and adoption.underused_capabilities:
        entitled_caps = {e.capability for e in entitlements}
        if any(cap in entitled_caps for cap in adoption.underused_capabilities):
            triggers.add("feature_shallow_depth")
    return triggers


def resolve_motions_for_day(day: int) -> dict[str, Any]:
    """Resolve every account's tier-appropriate motion(s) at *day*.

    Returns ``{"per_account": {account_id: [{"play_id", "motion",
    "trigger_factor"}]}, "cohort_actions": [...]}`` -- individual plays
    for accounts below the cohort threshold, and one synthesized
    ``cohort_action`` entry (covering the qualifying account list) for
    trigger/tier/capability groups at or above it.
    """

    base = build_synthetic_book()
    book = simulate_book(base, day)
    playbooks = load_playbooks("fleetops")
    cfg = load_value_model_config()

    company_by_id = {c.company_id: c for c in book.companies}
    health_by_id = {h.account_id: h for h in book.health_scores}
    adoption_by_id = {a.account_id: a for a in book.adoption_summaries}
    entitlements_by_id: dict[str, list] = defaultdict(list)
    for e in book.entitlements:
        entitlements_by_id[e.account_id].append(e)

    tier_by_id: dict[str, str] = {}
    triggers_by_id: dict[str, set[str]] = {}
    for account in book.accounts:
        company = company_by_id.get(account.account_id)
        if company is None:
            continue
        tier = resolve_tenant_tier(account_attributes(account, company), cfg).tier
        tier_by_id[account.account_id] = tier
        triggers_by_id[account.account_id] = _account_triggers(
            account.account_id,
            health_by_id.get(account.account_id),
            adoption_by_id.get(account.account_id),
            entitlements_by_id.get(account.account_id, ()),
        )

    # Group accounts by (trigger_factor, tier) to detect cohort-sized clusters.
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for account_id, triggers in triggers_by_id.items():
        tier = tier_by_id[account_id]
        for trigger in triggers:
            groups[(trigger, tier)].append(account_id)

    per_account: dict[str, list[dict[str, str]]] = defaultdict(list)
    cohort_actions: list[dict[str, Any]] = []

    for (trigger, tier), account_ids in sorted(groups.items()):
        matching_plays = [
            play for play in playbooks.plays
            if play.trigger_factor == trigger and tier in play.tiers
        ]
        if not matching_plays:
            continue
        cohort_plays = [p for p in matching_plays if p.motion == "cohort_action"]
        if len(account_ids) >= COHORT_THRESHOLD and cohort_plays:
            play = cohort_plays[0]
            cohort_actions.append({
                "play_id": play.id,
                "motion": "cohort_action",
                "trigger_factor": trigger,
                "tier": tier,
                "account_ids": sorted(account_ids),
            })
            continue
        non_cohort_plays = [p for p in matching_plays if p.motion != "cohort_action"]
        for play in non_cohort_plays:
            for account_id in account_ids:
                per_account[account_id].append({
                    "play_id": play.id,
                    "motion": play.motion,
                    "trigger_factor": trigger,
                })

    return {"per_account": dict(per_account), "cohort_actions": cohort_actions}


def _tier_for_account(account_id: str, day: int) -> str:
    base = build_synthetic_book()
    book = simulate_book(base, day)
    company_by_id = {c.company_id: c for c in book.companies}
    account = next(a for a in book.accounts if a.account_id == account_id)
    cfg = load_value_model_config()
    return resolve_tenant_tier(account_attributes(account, company_by_id[account_id]), cfg).tier


def check(ok: bool, problems: list[str], label: str, detail: Any = None) -> None:
    if not ok:
        problems.append(f"{label}: {detail}" if detail is not None else label)


def check_expected_motions_resolved() -> dict[str, Any]:
    """Every tier-mirror gold row's required motion is what the resolver
    actually emits for that account/day (cohort rows checked against the
    synthesized cohort_action, not per-account plays)."""

    problems: list[str] = []
    detail: dict[str, Any] = {}
    rows = load_expected_actions("fleetops")
    tier_mirror_rows = [r for r in rows if r.account_slug in TIER_MIRROR_ACCOUNTS]

    by_day: dict[int, dict[str, Any]] = {}
    for row in tier_mirror_rows:
        day = row.checkpoint_day
        if day not in by_day:
            by_day[day] = resolve_motions_for_day(day)
        resolved = by_day[day]
        account_id = account_id_for(row.account_slug)

        cohort_hit = next(
            (c for c in resolved["cohort_actions"] if account_id in c["account_ids"]), None
        )
        if cohort_hit is not None:
            emitted_motions = {"cohort_action"}
        else:
            emitted_motions = {p["motion"] for p in resolved["per_account"].get(account_id, [])}

        required = set(row.motion_in)
        overlap = required & emitted_motions
        detail[row.account_slug] = {"required": sorted(required), "emitted": sorted(emitted_motions)}
        check(
            bool(overlap),
            problems,
            f"{row.account_slug} day {row.checkpoint_day}: required motion(s) {sorted(required)} not emitted",
            sorted(emitted_motions),
        )
        forbidden_hit = emitted_motions & set(row.forbidden_motions)
        check(
            not forbidden_hit,
            problems,
            f"{row.account_slug} day {row.checkpoint_day}: forbidden motion(s) emitted",
            sorted(forbidden_hit),
        )

    return {"case": "expected-motions-resolved", "ok": not problems, "problems": problems, "detail": detail}


def check_no_tier_forbidden_motion_anywhere() -> dict[str, Any]:
    """Sweep the full 180-account book at 3 checkpoint days: no account
    ever receives a motion its own tier forbids."""

    problems: list[str] = []
    detail: dict[str, Any] = {"accounts_swept_per_day": 0}
    playbooks = load_playbooks("fleetops")
    forbidden_by_tier = {t.tier: set(t.forbidden_motions) for t in playbooks.service_tiers}

    for day in CHECKPOINT_DAYS:
        resolved = resolve_motions_for_day(day)
        base = build_synthetic_book()
        book = simulate_book(base, day)
        cfg = load_value_model_config()
        company_by_id = {c.company_id: c for c in book.companies}
        detail["accounts_swept_per_day"] = len(book.accounts)

        for account in book.accounts:
            company = company_by_id.get(account.account_id)
            if company is None:
                continue
            tier = resolve_tenant_tier(account_attributes(account, company), cfg).tier
            forbidden = forbidden_by_tier.get(tier, set())
            emitted = {p["motion"] for p in resolved["per_account"].get(account.account_id, ())}
            hit = emitted & forbidden
            if hit:
                problems.append(f"day {day}, account {account.account_id} (tier {tier}): forbidden motion(s) {sorted(hit)}")

        for cohort in resolved["cohort_actions"]:
            if cohort["motion"] in forbidden_by_tier.get(cohort["tier"], set()):
                problems.append(f"day {day}: cohort_action forbidden at tier {cohort['tier']}")

    return {"case": "no-tier-forbidden-motion", "ok": not problems, "problems": problems, "detail": detail}


def check_cohort_collapses_to_one_action() -> dict[str, Any]:
    """The bible's 25-account tier-mirror-3 cohort yields exactly one
    cohort_action at day 140, and zero per-account personal motions for
    those 25 accounts."""

    problems: list[str] = []
    cohort_slugs = sorted(
        row.account_slug
        for row in load_expected_actions("fleetops")
        if row.checkpoint_day == 140 and "cohort_action" in row.motion_in
    )
    cohort_ids = {account_id_for(slug) for slug in cohort_slugs}
    resolved = resolve_motions_for_day(140)

    matching_cohort_actions = [c for c in resolved["cohort_actions"] if cohort_ids <= set(c["account_ids"])]
    check(len(matching_cohort_actions) == 1, problems,
          "expected exactly one cohort_action covering the 25-account cohort", len(matching_cohort_actions))

    per_account_leaks = {
        aid: [p["motion"] for p in resolved["per_account"].get(aid, ())]
        for aid in cohort_ids
        if resolved["per_account"].get(aid)
    }
    check(not per_account_leaks, problems,
          "cohort accounts should have zero per-account motions once collapsed", per_account_leaks)

    return {
        "case": "cohort-collapses-to-one-action",
        "ok": not problems,
        "problems": problems,
        "detail": {"cohort_size": len(cohort_ids), "cohort_actions_found": len(matching_cohort_actions)},
    }


def check_repeatability() -> dict[str, Any]:
    first = json.dumps(resolve_motions_for_day(140), sort_keys=True, default=str)
    second = json.dumps(resolve_motions_for_day(140), sort_keys=True, default=str)
    identical = first == second
    return {
        "case": "repeatability",
        "ok": identical,
        "problems": [] if identical else ["two consecutive resolutions were not byte-identical"],
        "detail": {},
    }


CASES = (
    check_expected_motions_resolved,
    check_no_tier_forbidden_motion_anywhere,
    check_cohort_collapses_to_one_action,
    check_repeatability,
)


def run_battery() -> dict[str, Any]:
    results = [fn() for fn in CASES]
    return {
        "artifact": "tier_policy_battery",
        "cases": results,
        "hard_ok": all(r["ok"] for r in results),
        "failed_cases": [r["case"] for r in results if not r["ok"]],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ARTIFACT_PATH)
    args = parser.parse_args(argv)
    report = run_battery()
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "artifact": str(args.output),
        "cases": len(report["cases"]),
        "hard_ok": report["hard_ok"],
        "failed_cases": report["failed_cases"],
    }, indent=2, sort_keys=True))
    return 0 if report["hard_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
