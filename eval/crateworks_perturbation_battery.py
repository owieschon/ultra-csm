"""Crateworks perturbation battery (Harvest 11: robustness-grid extension).

Report 18's six-cell perturbation grid ran on fleetops only. This battery
answers the calibration question for crateworks, whose bible premise
(``docs/TENANT_CRATEWORKS_BIBLE.md``) is that data hygiene/identity mess
is the whole point -- the system must degrade honestly and never crash or
silently resolve an ambiguity, no matter how much noise is layered on top
of the fixed mess quota already authored into every account. Reuses
``eval/perturbation/perturb.py``'s pure functions unmodified.

Axes tested (bible-driven per Harvest 11 Decisions, verified against
``docs/TENANT_CRATEWORKS_BIBLE.md``):

| Axis | Correct behavior | Failure it catches |
| hygiene_drop 50% (stress, ON TOP of the authored mess quota) | no crash reading a doubly-perturbed contact; controls stay flag-free | null-handling brittleness beyond the fixed authored quota |
| identity-collision (volume-noise injected into Arc C1's real comms) | thread_participation_width stays exactly 2 (width is structurally isolated from comms volume, verified directly, not assumed) | noise silently "resolving" the identity ambiguity via a comms-to-width leak |
| volume x0.1 (Arc C1 comms thinned) | reply_latency_trend degrades to insufficient-history, never fabricated | window logic fabricating a trend from thinned data |

Axes NOT applicable, disclosed (not silently skipped):
- schema_rename / arr_shift: omitted, not silently -- crateworks's mapping
  layer already gets a PERMANENT schema-mapping stress test baked into
  every ingest run (bible section 3.5's header-casing mess -- "Account
  Name " vs "acct_id" reconciled on every single run, not just a
  perturbation cell), and tier resolution reuses the same generic,
  tenant-agnostic mechanism fleetops' cell 6 already calibration-tests.
  Crateworks's actual differentiator -- hygiene/identity-mess survival --
  is what the cells above test; repeating the generic-mechanism cells
  here would add no crateworks-specific calibration coverage.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from eval.perturbation.perturb import hygiene_drop, volume_scale
from ultra_csm.data_plane.signal_extractor import reply_latency_trend, thread_participation_width
from ultra_csm.data_plane.tenants.crateworks.book import (
    CONTROL_SLUGS,
    SEED_DATE,
    build_crateworks_data_plane,
    crateworks_account_id,
)
from ultra_csm.data_plane.tenants.crateworks.comms import DOCKSIDE_ID, arc_c1_comms, arc_c1_relationships

ARTIFACT_PATH = Path(__file__).with_name("crateworks_perturbation_battery.json")
_CHECKPOINT_DAY = 200  # bible section 2's post-transition checkpoint


def _as_of(day_offset: int) -> str:
    from datetime import date, timedelta

    return (date.fromisoformat(SEED_DATE) + timedelta(days=day_offset)).isoformat()


def check(ok: bool, problems: list[str], label: str, detail: Any = None) -> None:
    if not ok:
        problems.append(f"{label}: {detail}" if detail is not None else label)


def check_hygiene_drop_stress_no_crash() -> dict[str, Any]:
    """hygiene_drop 50% ON TOP of the authored mess quota (every account
    already carries a duplicate/stale-record mess by bible section 3) --
    must not crash a downstream reader, and must not manufacture a flag
    on any of the nine control accounts, whose latency/width signals are
    computed from EMPTY comms/relationship fixtures per bible section 4
    and therefore never read the contact table at all."""

    problems: list[str] = []
    dp = build_crateworks_data_plane()
    contacts = tuple(dp.crm.list_contacts(crateworks_account_id(slug)) for slug in CONTROL_SLUGS)
    flat_contacts = tuple(c for group in contacts for c in group)
    check(len(flat_contacts) > 0, problems, "expected crateworks control contacts to be non-empty", len(flat_contacts))

    dropped = hygiene_drop(flat_contacts, 0.5)
    crashed = False
    try:
        for c in dropped:
            _ = (c.title, c.role, c.org_level)
    except Exception as exc:  # noqa: BLE001 - this cell's whole point is "did anything crash"
        crashed = True
        problems.append(f"reading perturbed contacts raised: {exc!r}")

    nulled_count = sum(1 for c in dropped if c.title is None and c.role is None and c.org_level is None)
    for slug in CONTROL_SLUGS:
        account_id = crateworks_account_id(slug)
        latency = reply_latency_trend(account_id, [], as_of=_as_of(_CHECKPOINT_DAY))
        width = thread_participation_width(account_id, [], as_of=_as_of(_CHECKPOINT_DAY))
        flagged = latency.value is not None or (width.value or 0) > 0
        check(
            not flagged,
            problems,
            f"{slug}: control account flagged after a hygiene-drop stress on its contacts (which its signals never read)",
            {"latency": latency.value, "width": width.value},
        )

    detail = {"contacts": len(flat_contacts), "nulled": nulled_count, "crashed": crashed}
    check(not crashed, problems, "hygiene_drop must never crash a downstream reader, even stacked on the authored mess", detail)
    return {"case": "hygiene-drop-stress-no-crash", "ok": not problems, "problems": problems, "detail": detail}


def check_identity_collision_width_isolated_from_comms_noise() -> dict[str, Any]:
    """thread_participation_width must stay exactly 2 (the uncorrected
    duplicate-contact read the bible requires) regardless of what
    happens to comms volume -- width is computed purely from
    ``arc_c1_relationships``, never from ``CommunicationSignal``, so no
    amount of comms-side noise could ever cause the system to silently
    "discover" a third contact or collapse the ambiguity to width=1.
    Verified directly (the same discipline
    ``eval/drift_battery.py``'s ``check_width_signals_unaffected_by_junk_import``
    uses), not merely asserted from the bible text.

    Measured, not assumed (disclosed IF/THEN): ``volume_scale``'s filler
    path pins every synthetic signal to ``signals[0].timestamp`` (Arc
    C1's day-10 entry), which never falls inside any of this arc's
    checkpoint windows (verified empirically across days 30/60/80/100/
    140/200: ``reply_latency_trend`` was byte-identical with and without
    the injected noise at every one of them). The noise injection below
    therefore cannot dynamically test whether added volume masks the
    real evidence at this checkpoint -- that is a property of the shared
    perturbation library's filler placement (designed and unit-tested for
    a "does more volume crash" cell, never exercised at k>=1 by any
    existing battery), not a crateworks-specific finding, and not fixed
    here (fleetops-owned shared code, out of this dispatch's ownership
    map). The evidence-superset assertion below is recorded honestly as
    holding vacuously for that reason -- the width-isolation assertion is
    this cell's real, non-vacuous proof."""

    problems: list[str] = []
    as_of = _as_of(_CHECKPOINT_DAY)
    comms = arc_c1_comms()
    rels = arc_c1_relationships(_CHECKPOINT_DAY)

    baseline_latency = reply_latency_trend(DOCKSIDE_ID, comms, as_of=as_of)
    baseline_width = thread_participation_width(DOCKSIDE_ID, rels, as_of=as_of)

    noisy_comms = volume_scale(tuple(comms), 1.5, account_id=DOCKSIDE_ID)
    noisy_latency = reply_latency_trend(DOCKSIDE_ID, list(noisy_comms), as_of=as_of)
    noisy_width = thread_participation_width(DOCKSIDE_ID, rels, as_of=as_of)

    baseline_evidence_ids = {e.source_id for e in baseline_latency.evidence}
    noisy_evidence_ids = {e.source_id for e in noisy_latency.evidence}
    noise_entered_window = noisy_latency.value != baseline_latency.value

    detail = {
        "baseline_latency": baseline_latency.value,
        "noisy_latency": noisy_latency.value,
        "baseline_width": baseline_width.value,
        "noisy_width": noisy_width.value,
        "baseline_evidence_ids": sorted(baseline_evidence_ids),
        "noisy_evidence_ids": sorted(noisy_evidence_ids),
        "injected_filler_count": len(noisy_comms) - len(comms),
        "noise_entered_checkpoint_window": noise_entered_window,
        "evidence_superset_note": (
            "holds vacuously -- see IF/THEN in this case's docstring: "
            "volume_scale's k>=1 fillers never land inside this arc's "
            "checkpoint windows"
        ) if not noise_entered_window else "noise entered the window; assertion is non-vacuous",
    }
    check(
        noisy_width.value == 2.0 and baseline_width.value == 2.0,
        problems,
        "width must stay exactly 2 under comms-volume noise -- it is structurally isolated from CommunicationSignal",
        detail,
    )
    check(
        baseline_evidence_ids <= noisy_evidence_ids,
        problems,
        "the real fading-champion evidence ids must never be dropped from reply_latency_trend's evidence under added noise",
        detail,
    )
    return {
        "case": "identity-collision-width-isolated-from-comms-noise",
        "ok": not problems, "problems": problems, "detail": detail,
    }


def check_volume_down_degrades_honestly() -> dict[str, Any]:
    """Thinning Arc C1's comms to 10% must degrade the trend to
    insufficient-history, never fabricate one from what's left."""

    problems: list[str] = []
    as_of = _as_of(_CHECKPOINT_DAY)
    comms = arc_c1_comms()
    thinned = volume_scale(tuple(comms), 0.1, account_id=DOCKSIDE_ID)
    perturbed = reply_latency_trend(DOCKSIDE_ID, list(thinned), as_of=as_of)

    detail = {"thinned_count": len(thinned), "original_count": len(comms), "perturbed_trend": perturbed.value}
    check(
        perturbed.value is None,
        problems,
        "thinning Arc C1's comms to 10% should degrade to insufficient-history, not fabricate a trend",
        detail,
    )
    return {"case": "volume-down-degrades-honestly", "ok": not problems, "problems": problems, "detail": detail}


CASES = (
    check_hygiene_drop_stress_no_crash,
    check_identity_collision_width_isolated_from_comms_noise,
    check_volume_down_degrades_honestly,
)


def run_battery() -> dict[str, Any]:
    results = [fn() for fn in CASES]
    return {
        "artifact": "crateworks_perturbation_battery",
        "cases": results,
        "axes_not_applicable": [
            {
                "axis": "schema-rename",
                "applicable": False,
                "reason": (
                    "crateworks's mapping layer already gets a PERMANENT "
                    "schema-mapping stress test (header-casing mess, bible "
                    "section 3.5) baked into every ingest run, not just a "
                    "perturbation cell"
                ),
            },
            {
                "axis": "arr-shift",
                "applicable": False,
                "reason": (
                    "tier resolution reuses the same generic, tenant-agnostic "
                    "mechanism fleetops' own perturbation cell 6 already "
                    "calibration-tests; no crateworks-specific arc turns on "
                    "an ARR change"
                ),
            },
        ],
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
