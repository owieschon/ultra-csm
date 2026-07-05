"""Tenant-agnostic trigger_factor+tier -> motion resolution, with cohort
collapse.

Promoted from a resolver `eval/tier_policy_battery.py` (fleetops) and
`eval/loopway_battery.py` (loopway) each proved independently offline
(Universe v2, WS-Segmented-Book). Callers own tier resolution (call
`ultra_csm.value_model.resolve_tenant_tier` themselves) and trigger
derivation (tenant-specific, stays with the caller); this module owns only
the matching + cohort-collapse algorithm both battery resolvers had
duplicated verbatim (see docs/PROGRAM_REPORT_23.md receipts).

A single-account map (one entry) is a valid input: with only one account in
any (trigger_factor, tier) group, the cohort-collapse branch never fires
(group size can never reach ``cohort_threshold``), so this same function
resolves one account's motion without any special-casing.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from ultra_csm.knowledge import PlaybookSet

COHORT_THRESHOLD = 10


def resolve_motions(
    tier_by_account_id: Mapping[str, str],
    triggers_by_account_id: Mapping[str, set[str]],
    playbooks: PlaybookSet,
    *,
    cohort_threshold: int = COHORT_THRESHOLD,
    slug_by_account_id: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Resolve every account's tier-appropriate motion(s).

    Returns ``{"per_account": {account_id: [{"play_id", "motion",
    "trigger_factor"}]}, "cohort_actions": [...]}`` -- individual plays for
    accounts below *cohort_threshold*, and one synthesized ``cohort_action``
    entry (covering the qualifying account list) for trigger/tier groups at
    or above it. If *slug_by_account_id* is given, each cohort_action also
    carries a sorted ``account_slugs`` list (loopway's own divergence from
    fleetops' original resolver).
    """

    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for account_id, triggers in triggers_by_account_id.items():
        tier = tier_by_account_id[account_id]
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
        if len(account_ids) >= cohort_threshold and cohort_plays:
            play = cohort_plays[0]
            cohort_action: dict[str, Any] = {
                "play_id": play.id,
                "motion": "cohort_action",
                "trigger_factor": trigger,
                "tier": tier,
                "account_ids": sorted(account_ids),
            }
            if slug_by_account_id is not None:
                cohort_action["account_slugs"] = sorted(
                    slug_by_account_id[account_id] for account_id in account_ids
                )
            cohort_actions.append(cohort_action)
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


def no_play_targets_a_forbidden_tier(playbooks: PlaybookSet) -> list[str]:
    """Static config-consistency check: no play in *playbooks* targets a
    tier whose config forbids that play's own motion.

    This holds independent of any account/trigger data -- if it holds, no
    sweep over any book (real or hypothetical) could ever emit a
    tier-forbidden motion, since :func:`resolve_motions` only ever emits
    motions from matching plays. Returns a list of violation descriptions
    (empty if none).
    """

    violations: list[str] = []
    for play in playbooks.plays:
        for tier_name in play.tiers:
            tier = playbooks.tier_for(tier_name)
            if play.motion in tier.forbidden_motions:
                violations.append(
                    f"play {play.id!r} (motion {play.motion!r}) targets tier "
                    f"{tier_name!r}, which forbids that motion"
                )
    return violations
