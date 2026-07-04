"""Quantity-reconciliation battery (Universe v2, WS-Data-Classes Phase 1).

Checks the bible Canon's quantitative email/case-verbatim claims (asset
counts, event-loss percentages) against `book_simulator.simulate_book`'s
`AdoptionSummary` ground truth -- the same ground truth
`telemetry_events.py`'s event-level derivation reproduces exactly (see
`tests/test_telemetry_events.py`). Canon table:
docs/SYNTHETIC_UNIVERSE_BIBLE.md's "Quantity-reconciliation canon table"
(Class canon appendix).

Same ``hard_ok`` / two-identical-consecutive-runs pattern as
``eval/narrative_battery.py`` and ``eval/content_battery.py``.

Anti-Goodhart note (inherited from the bible): this battery asserts the
DOCUMENTED variance/tolerance for each row. Where a claim is irreconcilable
with the simulator, the battery does not "fix" either side -- it asserts
the known, stated variance stays exactly as documented. A change to either
side that silently drifts the variance without a bible update is exactly
what this battery exists to catch.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ultra_csm.data_plane.book_simulator import simulate_book
from ultra_csm.data_plane.fixtures import account_id_for
from ultra_csm.data_plane.narrative_content import case_verbatims, pinehill_content
from ultra_csm.data_plane.narrative_shared import base_synthetic_book

ARTIFACT_PATH = Path(__file__).with_name("quantity_battery.json")


def check(ok: bool, problems: list[str], label: str, detail: Any = None) -> None:
    if not ok:
        problems.append(f"{label}: {detail}" if detail is not None else label)


def check_pinehill_day8_known_variance() -> dict[str, Any]:
    """Bible canon table row 1: the day-8 email claims "22 of 50 assets";
    the simulator's actual day-8 ``active_assets`` is 12. This is a
    documented, known variance -- the assertion is that the DOCUMENTED gap
    (claimed 22, simulator 12) holds exactly, not that the two agree."""

    problems: list[str] = []
    base = base_synthetic_book()
    account_id = account_id_for("pinehill-transport")
    book = simulate_book(base, 8)
    adoption = next(a for a in book.adoption_summaries if a.account_id == account_id)

    body = pinehill_content.BODIES[(8, 9)]
    claimed_text = "22 of 50 assets"
    check(claimed_text in body, problems, "day8 email no longer contains the canon claim text", body)

    check(
        adoption.active_assets == 12,
        problems,
        "day8 simulator active_assets drifted from the documented known-variance baseline",
        adoption.active_assets,
    )
    check(
        adoption.entitled_assets == 50,
        problems,
        "day8 simulator entitled_assets drifted from the documented baseline",
        adoption.entitled_assets,
    )
    return {
        "case": "pinehill_day8_known_variance",
        "ok": not problems,
        "problems": problems,
        "detail": {
            "claimed_text": claimed_text,
            "claimed_active": 22,
            "claimed_entitled": 50,
            "simulator_active_assets": adoption.active_assets,
            "simulator_entitled_assets": adoption.entitled_assets,
            "status": "known_variance",
        },
    }


def check_pinehill_day85_internal_math_consistency() -> dict[str, Any]:
    """Bible canon table row 2: "214 of 1,880 ... about 11%" has no
    simulator counterpart (a dispatch-event-loss metric, not an
    AdoptionSummary quantity) -- the assertion is internal-math
    consistency of the claim itself: 214/1880 rounds to 11%."""

    problems: list[str] = []
    body = pinehill_content.BODIES[(85, 9)]
    numerator, denominator, claimed_pct = 214, 1880, 11
    check("214 of 1,880" in body, problems, "day85 email no longer contains the canon count claim", body)
    check("about 11%" in body, problems, "day85 email no longer contains the canon percent claim", body)

    computed_pct = round(numerator / denominator * 100)
    check(
        computed_pct == claimed_pct,
        problems,
        "214/1880 no longer rounds to the claimed 11%",
        computed_pct,
    )
    return {
        "case": "pinehill_day85_internal_math_consistency",
        "ok": not problems,
        "problems": problems,
        "detail": {
            "numerator": numerator,
            "denominator": denominator,
            "computed_pct": computed_pct,
            "claimed_pct": claimed_pct,
            "status": "consistent_no_simulator_counterpart",
        },
    }


def check_ironridge_webhook_internal_math_consistency() -> dict[str, Any]:
    """Bible canon table row 3: Ironridge's "6 of 140 attempts" webhook
    claim has no simulator counterpart (Ironridge is outside
    ``telemetry_events.TELEMETRY_ACCOUNTS``) -- asserted as an internal
    presence/consistency check against the case-verbatim canon only."""

    from ultra_csm.data_plane.telemetry_events import TELEMETRY_ACCOUNTS

    problems: list[str] = []
    ironridge_id = case_verbatims._IRONRIDGE
    case_id = case_verbatims._case_id(ironridge_id, 40)
    verbatim = case_verbatims.VERBATIMS.get(case_id)
    check(verbatim is not None, problems, "ironridge day40 verbatim missing")
    if verbatim is not None:
        claim_text = "6 of 140 attempts"
        found = any(claim_text in c.body for c in verbatim.comments)
        check(found, problems, "ironridge webhook claim text missing from case verbatim", claim_text)

    check(
        "ironridge-fleet" not in TELEMETRY_ACCOUNTS,
        problems,
        "ironridge unexpectedly gained a telemetry_events entry -- canon table row is stale",
        TELEMETRY_ACCOUNTS,
    )
    return {
        "case": "ironridge_webhook_internal_math_consistency",
        "ok": not problems,
        "problems": problems,
        "detail": {"status": "consistent_no_simulator_counterpart"},
    }


CASES = (
    check_pinehill_day8_known_variance,
    check_pinehill_day85_internal_math_consistency,
    check_ironridge_webhook_internal_math_consistency,
)


def run_battery() -> dict[str, Any]:
    results = [fn() for fn in CASES]
    return {
        "artifact": "quantity_reconciliation_battery",
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
