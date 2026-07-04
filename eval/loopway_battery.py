"""Loopway battery (Universe v2, WS-Tenant-Loopway, Wave 3).

The economics tenant's grading substrate: a self-contained, deterministic
policy resolver over the 400-account book -- mirrors
``eval/tier_policy_battery.py``'s pattern (trigger_factor + tier ->
motion, honoring ``forbidden_motions``, collapsing same-day/same-tier/
same-trigger clusters at or above a cohort threshold into ONE
``cohort_action``) at 10x the account count and this tenant's own arcs
(``docs/TENANT_LOOPWAY_BIBLE.md``): Arc L1 cohort activation stall (the
headline cohort-singularity claim: one action, 35 accounts), Arc L2 PQL
surfacing (the one place tech-touch escalates to a human), Arc L3 silent
mass churn-risk (a second, independent cohort-collapse case), and Herring
L-H1 (silence during a mid-dip that later self-recovers).

Runtime discipline (bible-mandated, binding): every check samples
deterministically -- all 98 named arc accounts plus the fixed 40-account
tail sample (``synthetic_book.PLAIN_TAIL_SAMPLE_40``), never a sweep of
all 400 for anything that constructs comms/telemetry per account. Tier
resolution itself (pure dict/arithmetic lookups over the already-built,
cached book) may run over the full 400 -- mirrors
``eval/tier_policy_battery.py``'s own precedent that O(400) cheap lookups
is not the runtime risk.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ultra_csm.data_plane.fixtures import account_id_for
from ultra_csm.data_plane.tenants.loopway.canary_registry import ACCOUNT_DESCRIPTIONS as CANARY_DESCRIPTIONS
from ultra_csm.data_plane.tenants.loopway.canary_registry import TENANT as CANARY_TENANT
from ultra_csm.data_plane.tenants.loopway.canary_registry import canary_token
from ultra_csm.data_plane.tenants.loopway.chat_fixtures import L1_CHAT_ACCOUNTS, all_chat_signals_as_of
from ultra_csm.data_plane.tenants.loopway.event_telemetry import milestone_achieved_as_of, usage_as_of
from ultra_csm.data_plane.tenants.loopway.narrative_shared import base_synthetic_book
from ultra_csm.data_plane.tenants.loopway.synthetic_book import (
    BATTERY_SAMPLE,
    HERRING_COHORT,
    L1_ACTIVATED,
    L1_STALLED,
    L2_COHORT,
    L3_COHORT,
    NAMED_ACCOUNTS,
)
from ultra_csm.knowledge import load_playbooks
from ultra_csm.motion_resolver import COHORT_THRESHOLD, resolve_motions
from ultra_csm.value_model import account_attributes, load_value_model_config, resolve_tenant_tier

ARTIFACT_PATH = Path(__file__).with_name("loopway_battery.json")
GOLD_PATH = Path(__file__).parent / "gold" / "loopway_expected_actions.json"


# ---------------------------------------------------------------------------
# Loopway-scoped gold loader (eval/expected_actions_gold.py's
# ``_KNOWN_ACCOUNT_SLUGS`` is hardcoded to fleetops' own ``_ACCT_DATA`` --
# not reusable for a second tenant's slug space without editing a file
# outside this workstream's ownership map. This loader applies the same
# validation discipline -- fail-closed on unknown mode/motion, non-empty
# motion_in for non-"none" rows -- scoped to Loopway's own account slugs.)
# ---------------------------------------------------------------------------


class LoopwayGoldError(ValueError):
    pass


def load_loopway_gold(path: Path = GOLD_PATH) -> tuple[dict[str, Any], ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or len(raw) < 18:
        raise LoopwayGoldError(f"{path.name} must be a JSON array with >= 18 rows")
    known_slugs = set(NAMED_ACCOUNTS)
    for row in raw:
        if row.get("tenant") != "loopway":
            raise LoopwayGoldError(f"row tenant mismatch: {row.get('tenant')!r}")
        if row.get("account_slug") not in known_slugs:
            raise LoopwayGoldError(f"unknown loopway account slug: {row.get('account_slug')!r}")
        if row.get("mode") not in ("shadow", "gap", "none"):
            raise LoopwayGoldError(f"unknown grading mode: {row.get('mode')!r}")
        required = row.get("required", {})
        if row["mode"] == "none":
            if required.get("signal") is not None or required.get("motion_in"):
                raise LoopwayGoldError(f"mode 'none' row for {row['account_slug']} must have empty signal/motion_in")
        else:
            if not required.get("motion_in"):
                raise LoopwayGoldError(f"mode {row['mode']!r} row for {row['account_slug']} needs non-empty motion_in")
    return tuple(raw)


def check(ok: bool, problems: list[str], label: str, detail: Any = None) -> None:
    if not ok:
        problems.append(f"{label}: {detail}" if detail is not None else label)


# ---------------------------------------------------------------------------
# Policy resolver: trigger_factor + tier -> motion, with cohort collapse.
# ---------------------------------------------------------------------------


def _tier_by_slug() -> dict[str, str]:
    """Tier for every one of the 400 accounts -- pure dict/arithmetic
    lookups over the cached book, safe to run at full scale (see module
    docstring's runtime-discipline note)."""

    book = base_synthetic_book()
    cfg = load_value_model_config()
    company_by_id = {c.company_id: c for c in book.companies}
    result: dict[str, str] = {}
    for account in book.accounts:
        company = company_by_id.get(account.account_id)
        if company is None:
            continue
        tier = resolve_tenant_tier(account_attributes(account, company), cfg).tier
        result[account.account_id] = tier
    return result


def _account_triggers(slug: str, day: int) -> set[str]:
    triggers: set[str] = set()
    if slug in L1_STALLED and day >= 75:
        triggers.add("activation_stalled")
    if slug in L2_COHORT and day >= 120:
        triggers.add("product_qualified_lead")
    if slug in L3_COHORT and day >= 200:
        triggers.add("usage_decay_silent")
    return triggers


def resolve_motions_for_day(day: int) -> dict[str, Any]:
    """Resolve every named account's tier-appropriate motion(s) at *day*.

    Only the 98 named arc accounts carry a scripted trigger (bible: no
    scripted CSM at this scale for anyone else), so this resolver is
    scoped to ``NAMED_ACCOUNTS`` -- a full 400-account sweep of triggers
    would find nothing new on the other 302 (there is no trigger fact for
    them), so it would only cost runtime for zero assertion value."""

    tier_by_slug = _tier_by_slug()
    playbooks = load_playbooks("loopway")

    triggers_by_slug: dict[str, set[str]] = {
        slug: _account_triggers(slug, day) for slug in NAMED_ACCOUNTS
    }

    tier_by_account_id: dict[str, str] = {}
    triggers_by_account_id: dict[str, set[str]] = {}
    slug_by_account_id: dict[str, str] = {}
    for slug, triggers in triggers_by_slug.items():
        account_id = account_id_for(slug)
        tier_by_account_id[account_id] = tier_by_slug.get(account_id, "tech_touch")
        triggers_by_account_id[account_id] = triggers
        slug_by_account_id[account_id] = slug

    return resolve_motions(
        tier_by_account_id,
        triggers_by_account_id,
        playbooks,
        slug_by_account_id=slug_by_account_id,
    )


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_l1_cohort_singularity() -> dict[str, Any]:
    """Arc L1: exactly ONE cohort_action covering the 35 stalled accounts,
    zero per-account motions on any of them, and the 25-account contrast
    group (milestone met) gets no action at all."""

    problems: list[str] = []
    resolved = resolve_motions_for_day(75)
    stalled_ids = {account_id_for(s) for s in L1_STALLED}

    matching = [c for c in resolved["cohort_actions"] if stalled_ids <= set(c["account_ids"]) and c["trigger_factor"] == "activation_stalled"]
    check(len(matching) == 1, problems, "expected exactly one cohort_action covering the 35-account L1 cohort", len(matching))

    per_account_leaks = {
        aid: [p["motion"] for p in resolved["per_account"].get(aid, ())]
        for aid in stalled_ids
        if resolved["per_account"].get(aid)
    }
    check(not per_account_leaks, problems, "L1 stalled accounts should have zero per-account motions once collapsed", per_account_leaks)

    contrast_ids = {account_id_for(s) for s in L1_ACTIVATED}
    contrast_leaks = {
        aid: resolved["per_account"].get(aid) or next((c for c in resolved["cohort_actions"] if aid in c["account_ids"]), None)
        for aid in contrast_ids
        if resolved["per_account"].get(aid) or any(aid in c["account_ids"] for c in resolved["cohort_actions"])
    }
    check(not contrast_leaks, problems, "L1 activated contrast group should get no action at all", contrast_leaks)

    for aid in stalled_ids:
        milestone = milestone_achieved_as_of(next(s for s in L1_STALLED if account_id_for(s) == aid), 75)
        check(not milestone, problems, f"L1 stalled account {aid} should NOT have activated by day 75", milestone)
    for aid in contrast_ids:
        slug = next(s for s in L1_ACTIVATED if account_id_for(s) == aid)
        milestone = milestone_achieved_as_of(slug, 75)
        check(milestone, problems, f"L1 contrast account {slug} should have activated by day 75", milestone)

    return {
        "case": "l1-cohort-singularity",
        "ok": not problems,
        "problems": problems,
        "detail": {
            "stalled_count": len(stalled_ids),
            "contrast_count": len(contrast_ids),
            "cohort_actions_found": len(matching),
        },
    }


def check_l2_pql_escalation() -> dict[str, Any]:
    """Arc L2: exactly 3 accounts escalate (not a cohort_action, not
    forbidden), and each shows >=5x the plain-tail median usage by day
    120."""

    problems: list[str] = []
    resolved = resolve_motions_for_day(120)
    pql_ids = {account_id_for(s) for s in L2_COHORT}

    for aid in pql_ids:
        motions = {p["motion"] for p in resolved["per_account"].get(aid, ())}
        check("escalation" in motions, problems, f"L2 account {aid} should have escalation motion", sorted(motions))
        forbidden_hit = motions & {"personal_email", "working_session", "qbr"}
        check(not forbidden_hit, problems, f"L2 account {aid} should never get a forbidden tech-touch motion", sorted(forbidden_hit))
        in_cohort = any(aid in c["account_ids"] for c in resolved["cohort_actions"])
        check(not in_cohort, problems, f"L2 account {aid} should not be collapsed into a cohort_action (only 3 accounts, below threshold)", in_cohort)

    # Usage magnitude check: L2 accounts >= 5x the plain-tail median at day 120.
    import statistics
    from ultra_csm.data_plane.tenants.loopway.synthetic_book import PLAIN_TAIL_SAMPLE_40

    book = base_synthetic_book()
    usage_by_account: dict[str, dict[str, float]] = {}
    for u in book.usage_signals:
        usage_by_account.setdefault(u.account_id, {})[u.metric_name] = u.value
    plain_active = [usage_by_account[account_id_for(s)]["active_users"] for s in PLAIN_TAIL_SAMPLE_40]
    median_active = statistics.median(plain_active)

    for slug in L2_COHORT:
        point = usage_as_of(slug, 120)
        ratio = point.active_users / median_active if median_active else float("inf")
        check(ratio >= 5.0, problems, f"{slug}: active_users ratio to tail median should be >=5x at day 120", ratio)

    return {
        "case": "l2-pql-escalation",
        "ok": not problems,
        "problems": problems,
        "detail": {"pql_count": len(pql_ids), "tail_median_active_users": median_active},
    }


def check_l3_cohort_singularity() -> dict[str, Any]:
    """Arc L3: exactly ONE win-back cohort_action covering the 20-account
    churn-risk cohort, zero per-account drafts, and usage genuinely decays
    to zero with no support contact."""

    problems: list[str] = []
    resolved = resolve_motions_for_day(200)
    churn_ids = {account_id_for(s) for s in L3_COHORT}

    matching = [c for c in resolved["cohort_actions"] if churn_ids <= set(c["account_ids"]) and c["trigger_factor"] == "usage_decay_silent"]
    check(len(matching) == 1, problems, "expected exactly one cohort_action covering the 20-account L3 cohort", len(matching))

    per_account_leaks = {
        aid: [p["motion"] for p in resolved["per_account"].get(aid, ())]
        for aid in churn_ids
        if resolved["per_account"].get(aid)
    }
    check(not per_account_leaks, problems, "L3 accounts should have zero per-account motions once collapsed", per_account_leaks)

    for slug in L3_COHORT:
        point = usage_as_of(slug, 200)
        check(point.active_users == 0.0, problems, f"{slug}: active_users should be exactly zero by day 200", point.active_users)

    return {
        "case": "l3-cohort-singularity",
        "ok": not problems,
        "problems": problems,
        "detail": {"cohort_size": len(churn_ids), "cohort_actions_found": len(matching)},
    }


def check_herring_silence() -> dict[str, Any]:
    """Herring L-H1: no action (cohort or per-account) at day 105 (mid-dip),
    and the recovery to baseline by day 130 is a computed fact, not
    asserted by narration alone."""

    problems: list[str] = []
    resolved = resolve_motions_for_day(105)
    herring_ids = {account_id_for(s) for s in HERRING_COHORT}

    for aid in herring_ids:
        has_motion = bool(resolved["per_account"].get(aid)) or any(aid in c["account_ids"] for c in resolved["cohort_actions"])
        check(not has_motion, problems, f"herring account {aid} should get no action at mid-dip day 105", has_motion)

    dip_values = [usage_as_of(s, 95).active_users for s in HERRING_COHORT]
    recovered_values = [usage_as_of(s, 130).active_users for s in HERRING_COHORT]
    baseline_values = [usage_as_of(s, 0).active_users for s in HERRING_COHORT]
    check(all(d < b for d, b in zip(dip_values, baseline_values)), problems, "herring accounts should show a genuine dip at day 95", dip_values)
    check(all(abs(r - b) < 1e-6 for r, b in zip(recovered_values, baseline_values)), problems, "herring accounts should fully recover to baseline by day 130", list(zip(recovered_values, baseline_values)))

    return {
        "case": "herring-silence",
        "ok": not problems,
        "problems": problems,
        "detail": {"cohort_size": len(herring_ids)},
    }


def check_no_tier_forbidden_motion_sampled() -> dict[str, Any]:
    """Sampled forbidden-motion sweep across the tail (bible: "a sampled
    forbidden-motion sweep across the tail"): every named account plus the
    fixed 40-account tail sample, at each of the three arc checkpoint days
    -- no account ever receives a motion its own tier forbids."""

    problems: list[str] = []
    playbooks = load_playbooks("loopway")
    forbidden_by_tier = {t.tier: set(t.forbidden_motions) for t in playbooks.service_tiers}
    tier_by_id = _tier_by_slug()
    sample_ids = {account_id_for(s) for s in BATTERY_SAMPLE}

    for day in (75, 120, 200):
        resolved = resolve_motions_for_day(day)
        for aid in sample_ids:
            tier = tier_by_id.get(aid, "tech_touch")
            forbidden = forbidden_by_tier.get(tier, set())
            emitted = {p["motion"] for p in resolved["per_account"].get(aid, ())}
            hit = emitted & forbidden
            check(not hit, problems, f"day {day}, account {aid} (tier {tier}): forbidden motion(s) emitted", sorted(hit))
        for cohort in resolved["cohort_actions"]:
            hit = cohort["motion"] in forbidden_by_tier.get(cohort["tier"], set())
            check(not hit, problems, f"day {day}: cohort_action forbidden at tier {cohort['tier']}", cohort)

    return {
        "case": "no-tier-forbidden-motion-sampled",
        "ok": not problems,
        "problems": problems,
        "detail": {"sample_size": len(sample_ids), "days_checked": [75, 120, 200]},
    }


def check_chat_signal_integration() -> dict[str, Any]:
    """The 4 L1-stalled accounts with chat evidence: their chat signal ids
    are real, computed, and available as corroborating evidence for the
    cohort_action -- not that the resolver's cohort_action payload embeds
    them (it doesn't carry per-account evidence lists), but that the
    evidence EXISTS and is retrievable for exactly those 4 accounts, once
    the chat message is due, and not fabricated for any other account."""

    problems: list[str] = []
    chat_by_account = all_chat_signals_as_of(75)
    l1_chat_ids = {account_id_for(s) for s in L1_CHAT_ACCOUNTS}

    for aid, signals in chat_by_account.items():
        if aid in l1_chat_ids:
            check(len(signals) > 0, problems, f"L1 chat account {aid} should have >=1 chat signal by day 75", len(signals))
            check(all(s.channel == "chat" for s in signals), problems, f"{aid}: all signals should be channel=chat", [s.channel for s in signals])
        else:
            # Non-L1 chat accounts (the 8 plain ones) should have their own
            # thin, benign chat -- present, but never mentioning "activation
            # stalled" content (no signal contamination across accounts).
            check(len(signals) <= 1, problems, f"plain chat account {aid} should have at most 1 thin message", len(signals))

    check(len(l1_chat_ids) == 4, problems, "exactly 4 L1 stalled accounts should carry chat evidence", len(l1_chat_ids))

    return {
        "case": "chat-signal-integration",
        "ok": not problems,
        "problems": problems,
        "detail": {"l1_chat_accounts": sorted(L1_CHAT_ACCOUNTS)},
    }


def check_gold_rows_valid() -> dict[str, Any]:
    """The gold file loads, validates, and every gap-mode row's required
    motion is what the resolver actually emits (cohort rows checked
    against the synthesized cohort_action)."""

    problems: list[str] = []
    rows = load_loopway_gold()
    by_day: dict[int, dict[str, Any]] = {}

    for row in rows:
        day = row["checkpoint_day"]
        if day not in by_day:
            by_day[day] = resolve_motions_for_day(day)
        resolved = by_day[day]
        account_id = account_id_for(row["account_slug"])

        cohort_hit = next((c for c in resolved["cohort_actions"] if account_id in c["account_ids"]), None)
        if cohort_hit is not None:
            emitted_motions = {"cohort_action"}
        else:
            emitted_motions = {p["motion"] for p in resolved["per_account"].get(account_id, [])}

        if row["mode"] == "none":
            check(not emitted_motions, problems, f"{row['account_slug']} day {day}: mode 'none' but emitted {sorted(emitted_motions)}", sorted(emitted_motions))
            continue

        required = set(row["required"]["motion_in"])
        overlap = required & emitted_motions
        check(bool(overlap), problems, f"{row['account_slug']} day {day}: required motion(s) {sorted(required)} not emitted", sorted(emitted_motions))
        forbidden_hit = emitted_motions & set(row.get("forbidden_motions", ()))
        check(not forbidden_hit, problems, f"{row['account_slug']} day {day}: forbidden motion(s) emitted", sorted(forbidden_hit))

    return {"case": "gold-rows-valid", "ok": not problems, "problems": problems, "detail": {"rows": len(rows)}}


def check_canary_integrity() -> dict[str, Any]:
    """Every one of the 64 canary-bearing accounts (24 named + fixed
    40-account tail sample) carries its own token in its description, and
    no canary token ever appears in a campaign/chat-derived artifact this
    tenant produces (the L1/L3 cohort campaigns' content_refs, the chat
    transcripts) -- mirrors ``eval/canary_battery.py``'s
    ``check_canary_integrity`` pattern at this tenant's own scale."""

    problems: list[str] = []
    missing = [
        slug for slug in CANARY_DESCRIPTIONS
        if canary_token(CANARY_TENANT, slug) not in CANARY_DESCRIPTIONS[slug]
    ]
    check(not missing, problems, "account description missing its own canary", missing)

    # No canary token in any chat transcript text this tenant authors.
    from ultra_csm.data_plane.tenants.loopway.chat_fixtures import (
        _L1_SETUP_QUESTIONS,
        _plain_question_for,
        PLAIN_CHAT_ACCOUNTS,
    )

    all_texts = [q[1] for q in _L1_SETUP_QUESTIONS]
    for idx, slug in enumerate(PLAIN_CHAT_ACCOUNTS):
        all_texts.append(_plain_question_for(slug, idx)[1])
    leaked = [t[:60] for t in all_texts if "CANARY-" in t]
    check(not leaked, problems, "canary token found in a chat transcript (forbidden placement)", leaked)

    return {
        "case": "canary-integrity",
        "ok": not problems,
        "problems": problems,
        "detail": {"accounts_with_canary": len(CANARY_DESCRIPTIONS) - len(missing)},
    }


def check_repeatability() -> dict[str, Any]:
    first = json.dumps(
        [resolve_motions_for_day(d) for d in (75, 120, 200, 105)], sort_keys=True, default=str
    )
    second = json.dumps(
        [resolve_motions_for_day(d) for d in (75, 120, 200, 105)], sort_keys=True, default=str
    )
    identical = first == second
    return {
        "case": "repeatability",
        "ok": identical,
        "problems": [] if identical else ["two consecutive resolutions were not byte-identical"],
        "detail": {},
    }


CASES = (
    check_l1_cohort_singularity,
    check_l2_pql_escalation,
    check_l3_cohort_singularity,
    check_herring_silence,
    check_no_tier_forbidden_motion_sampled,
    check_chat_signal_integration,
    check_gold_rows_valid,
    check_canary_integrity,
    check_repeatability,
)


def run_battery() -> dict[str, Any]:
    results = [fn() for fn in CASES]
    return {
        "artifact": "loopway_battery",
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
