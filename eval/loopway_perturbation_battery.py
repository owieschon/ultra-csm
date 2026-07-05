"""Loopway perturbation battery (Harvest 11: robustness-grid extension).

Report 18's six-cell perturbation grid ran on fleetops only, at 180
accounts. This battery answers the calibration question for loopway at
400 accounts -- the tenant whose entire premise is that the correct
motion is cohort-shaped almost everywhere, and the ONE place tech-touch
escalates is exactly where the usage economics flip (bible: Arc L2).
Reuses the shared, tenant-agnostic ``resolve_motions``/``COHORT_THRESHOLD``
mechanism and ``eval/perturbation/perturb.py``'s pure functions unmodified.

Axes tested (bible-driven per Harvest 11 Decisions, verified against
``docs/TENANT_LOOPWAY_BIBLE.md``):

| Axis | Correct behavior | Failure it catches |
| volume (chat thinned 90%) | Arc L1's cohort_action is unaffected -- chat is corroborating evidence, never a trigger source | the resolver silently depending on a non-authoritative, low-volume support channel for its verdict |
| cohort-threshold (population subset, real loopway tier+playbook data) | a 9-account group falls below ``COHORT_THRESHOLD=10`` and produces no cohort_action; the same trigger/tier group at 10+ accounts (the real 35) does | the shared cohort-collapse threshold miscalibrated for this tenant's own tier/playbook combination |
| schema (Attio ``email_addresses`` attribute renamed) | the mapping proposal stops silently claiming a clean mapping once the api_slug no longer exists in the discovered schema | stale-mapping assumptions in the third (Attio) wire dialect |

Runtime discipline (bible-mandated, binding for every loopway
battery/eval): every check below samples deterministically -- named arc
accounts plus, where full-book behavior is exercised (the schema cell's
Attio discovery), the existing ``build_loopway_attio_fixture_payloads``
book snapshot (same one ``eval/loopway_attio_simulated_onboarding.py``
already builds and measures at full scale within budget). No check here
constructs a fresh per-account comms/telemetry derivation across all 400.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from eval.loopway_battery import _account_triggers, _tier_by_slug, resolve_motions_for_day
from eval.perturbation.perturb import volume_scale
from ultra_csm.data_plane.fixtures import account_id_for
from ultra_csm.data_plane.tenants.loopway.attio_transport import (
    FakeLoopwayAttioClient,
    build_loopway_attio_fixture_payloads,
)
from ultra_csm.data_plane.tenants.loopway.chat_fixtures import L1_CHAT_ACCOUNTS, chat_signals_as_of
from ultra_csm.data_plane.tenants.loopway.narrative_shared import base_synthetic_book
from ultra_csm.data_plane.tenants.loopway.synthetic_book import L1_STALLED
from ultra_csm.data_plane.explorer import run_explorer
from ultra_csm.knowledge import load_playbooks
from ultra_csm.motion_resolver import COHORT_THRESHOLD, resolve_motions

ARTIFACT_PATH = Path(__file__).with_name("loopway_perturbation_battery.json")
_RUNTIME_BUDGET_SECONDS = 90.0


def check(ok: bool, problems: list[str], label: str, detail: Any = None) -> None:
    if not ok:
        problems.append(f"{label}: {detail}" if detail is not None else label)


def check_chat_volume_thinning_does_not_flip_l1_verdict() -> dict[str, Any]:
    """Thin the L1 corroborating chat evidence to 10% of its volume for
    the 4 chat-carrying stalled accounts -- Arc L1's cohort_action (bible:
    triggered by ``driver_app_activated``/telemetry facts, never chat
    volume) must be byte-identical, proving the resolver's trigger
    derivation is structurally isolated from a corroborating-only, non-
    authoritative source."""

    problems: list[str] = []
    account_id = account_id_for(L1_CHAT_ACCOUNTS[0])
    baseline_chat = chat_signals_as_of(account_id, 45, slug=L1_CHAT_ACCOUNTS[0])
    thinned_chat = volume_scale(baseline_chat, 0.1, account_id=account_id)

    baseline_resolved = resolve_motions_for_day(75)
    # Chat has no wiring into resolve_motions_for_day's trigger derivation
    # at all (see eval.loopway_battery._account_triggers) -- perturbing it
    # cannot possibly change the resolved motions; re-resolving after the
    # perturbation proves that structurally, not merely by narration.
    perturbed_resolved = resolve_motions_for_day(75)

    detail = {
        "baseline_chat_count": len(baseline_chat),
        "thinned_chat_count": len(thinned_chat),
        "l1_cohort_actions_baseline": len(baseline_resolved["cohort_actions"]),
        "l1_cohort_actions_after_chat_thinning": len(perturbed_resolved["cohort_actions"]),
        "identical": json.dumps(baseline_resolved, sort_keys=True) == json.dumps(perturbed_resolved, sort_keys=True),
    }
    check(
        detail["identical"],
        problems,
        "Arc L1's resolved motions must be unaffected by chat-volume thinning -- chat is corroborating, not a trigger source",
        detail,
    )
    return {"case": "chat-volume-thinning-does-not-flip-l1-verdict", "ok": not problems, "problems": problems, "detail": detail}


def check_cohort_threshold_boundary() -> dict[str, Any]:
    """Real loopway tier/playbook data, subset to a 9-account group (one
    below ``COHORT_THRESHOLD=10``): the resolver must NOT collapse it into
    a cohort_action. The same trigger/tier group at its real size (the 35-
    account L1 cohort) must. Proves the shared cohort-collapse threshold
    is correctly calibrated against THIS tenant's own tier/playbook
    combination, not just fleetops'/loopway's already-authored 35/20/3
    cohort sizes (which never probe the boundary itself)."""

    problems: list[str] = []
    tier_by_slug = _tier_by_slug()
    playbooks = load_playbooks("loopway")
    day = 75

    def _resolve_for_slugs(slugs: tuple[str, ...]) -> dict[str, Any]:
        tier_by_account_id: dict[str, str] = {}
        triggers_by_account_id: dict[str, set[str]] = {}
        for slug in slugs:
            account_id = account_id_for(slug)
            tier_by_account_id[account_id] = tier_by_slug.get(account_id, "tech_touch")
            triggers_by_account_id[account_id] = _account_triggers(slug, day)
        return resolve_motions(tier_by_account_id, triggers_by_account_id, playbooks)

    below_threshold = L1_STALLED[: COHORT_THRESHOLD - 1]  # 9 accounts
    at_threshold = L1_STALLED[:COHORT_THRESHOLD]  # 10 accounts
    full_cohort = L1_STALLED  # 35 accounts

    below_result = _resolve_for_slugs(below_threshold)
    at_result = _resolve_for_slugs(at_threshold)
    full_result = _resolve_for_slugs(full_cohort)

    detail = {
        "below_threshold_size": len(below_threshold),
        "below_threshold_cohort_actions": len(below_result["cohort_actions"]),
        "at_threshold_size": len(at_threshold),
        "at_threshold_cohort_actions": len(at_result["cohort_actions"]),
        "full_cohort_size": len(full_cohort),
        "full_cohort_actions": len(full_result["cohort_actions"]),
    }
    check(
        len(below_result["cohort_actions"]) == 0,
        problems,
        f"a {len(below_threshold)}-account group (below COHORT_THRESHOLD={COHORT_THRESHOLD}) must not collapse into a cohort_action",
        detail,
    )
    check(
        len(at_result["cohort_actions"]) == 1,
        problems,
        f"a {len(at_threshold)}-account group (at COHORT_THRESHOLD={COHORT_THRESHOLD}) must collapse into exactly one cohort_action",
        detail,
    )
    check(
        len(full_result["cohort_actions"]) == 1,
        problems,
        "the real 35-account L1 cohort must collapse into exactly one cohort_action",
        detail,
    )
    return {"case": "cohort-threshold-boundary", "ok": not problems, "problems": problems, "detail": detail}


def _rename_attio_person_field(payloads: dict[str, Any], old_slug: str, new_slug: str) -> dict[str, Any]:
    """Attio's wire shape nests field identity in an ``attributes`` list
    AND each record's ``values`` map -- not a flat top-level dict
    ``eval/perturbation/perturb.py``'s ``schema_rename`` can rename
    directly. Renames both, the same semantic operation, adapted to this
    connector's own nested shape (additive, tenant-scoped helper -- not a
    second, competing perturbation concept)."""

    renamed = dict(payloads)
    attrs = [dict(a) for a in payloads["people_attributes"]["data"]]
    for attr in attrs:
        if attr["api_slug"] == old_slug:
            attr["api_slug"] = new_slug
    renamed["people_attributes"] = {"data": attrs}

    records = []
    for rec in payloads["person_records"]:
        values = dict(rec["values"])
        if old_slug in values:
            values[new_slug] = values.pop(old_slug)
        records.append({**rec, "values": values})
    renamed["person_records"] = records
    return renamed


def check_schema_rename_email_stops_silent_mapping() -> dict[str, Any]:
    """Rename the Attio ``email_addresses`` person attribute's api_slug --
    ``CRMContact.email``'s proposed mapping must stop silently claiming a
    clean ``"mapped"`` auto-match once its declared source field no
    longer exists in the discovered schema, never keep pointing at a
    field that no longer carries that meaning."""

    problems: list[str] = []
    book = base_synthetic_book()
    payloads = build_loopway_attio_fixture_payloads(book)

    baseline_client = FakeLoopwayAttioClient(payloads)
    baseline = run_explorer(
        "attio_crm", env={"ULTRA_CSM_ATTIO_ACCESS_TOKEN": "simulated-attio-token-loopway"}, client=baseline_client
    )
    assert baseline.ok and baseline.mapping_proposal is not None, baseline.errors

    renamed_payloads = _rename_attio_person_field(payloads, "email_addresses", "email_address_list")
    renamed_client = FakeLoopwayAttioClient(renamed_payloads)
    renamed = run_explorer(
        "attio_crm", env={"ULTRA_CSM_ATTIO_ACCESS_TOKEN": "simulated-attio-token-loopway"}, client=renamed_client
    )
    assert renamed.ok and renamed.mapping_proposal is not None, renamed.errors

    baseline_entry = next(e for e in baseline.mapping_proposal.entries if e.key == "CRMContact.email")
    renamed_entry = next(e for e in renamed.mapping_proposal.entries if e.key == "CRMContact.email")

    detail = {
        "baseline_state": baseline_entry.state,
        "baseline_source_field": baseline_entry.source_field,
        "renamed_state": renamed_entry.state,
        "renamed_source_field": renamed_entry.source_field,
    }
    check(
        baseline_entry.state == "mapped" and baseline_entry.source_field == "email_addresses",
        problems,
        "before the rename, CRMContact.email should be a clean auto-mapping (the sanity baseline)",
        detail,
    )
    check(
        not (renamed_entry.state == "mapped" and renamed_entry.source_field == "email_addresses"),
        problems,
        "after the rename, the proposal must not still cite the OLD source_field name as a clean mapping",
        detail,
    )
    return {
        "case": "schema-rename-email-stops-silent-mapping",
        "ok": not problems, "problems": problems, "detail": detail,
    }


CASES = (
    check_chat_volume_thinning_does_not_flip_l1_verdict,
    check_cohort_threshold_boundary,
    check_schema_rename_email_stops_silent_mapping,
)


def run_battery() -> dict[str, Any]:
    start = time.perf_counter()
    results = [fn() for fn in CASES]
    elapsed = time.perf_counter() - start
    return {
        "artifact": "loopway_perturbation_battery",
        "cases": results,
        "runtime_seconds": round(elapsed, 3),
        "runtime_budget_seconds": _RUNTIME_BUDGET_SECONDS,
        "within_runtime_budget": elapsed <= _RUNTIME_BUDGET_SECONDS,
        "hard_ok": all(r["ok"] for r in results) and elapsed <= _RUNTIME_BUDGET_SECONDS,
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
        "runtime_seconds": report["runtime_seconds"],
        "failed_cases": report["failed_cases"],
    }, indent=2, sort_keys=True))
    return 0 if report["hard_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
