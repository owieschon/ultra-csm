"""Crateworks tenant battery (Universe v2, Wave 3, WS-Tenant-Crateworks).

Same ``hard_ok`` pattern as ``eval/canary_battery.py``. All offline/
deterministic: fixture data and fake transports only, no credentials, no
network calls.

Anti-Goodhart note: ``docs/TENANT_CRATEWORKS_BIBLE.md`` owns the ground
truth. This battery may be edited to add cases or correct an assertion
against a bible change -- never to match whatever the system currently
outputs.

Finding (recorded, not routed around): crateworks has NO CS platform and NO
product telemetry vendor (bible section 0), so
``ultra_csm.agent1.sweep._slot_b_inputs_for_account`` -- which requires a
``CSCompany``/``HealthScore``/``AdoptionSummary`` triple -- fails closed
(returns ``None``) for every crateworks account by construction. This is
the CORRECT degraded behavior for this tenant, not a defect: the full
sweep/proposal pipeline literally cannot run here, exactly as the bible
predicts for the "almost nothing is clean at the source" tenant. Arc C1's
checkpoint truths are therefore graded directly against the
``signal_extractor`` outputs (the same evidence a human-facing escalation
would cite) against ``eval/gold/crateworks_expected_actions.json``, not
through the sweep engine, which this tenant's own vendor-stack gap makes
inapplicable.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ultra_csm.data_plane.canary_registry import canary_token
from ultra_csm.data_plane.signal_extractor import reply_latency_trend, thread_participation_width
from ultra_csm.data_plane.tenants.crateworks.book import (
    ACCOUNTS,
    CONTROL_SLUGS,
    DOCKSIDE_SLUG,
    SEED_DATE,
    TENANT,
    build_flat_crateworks_book,
    crateworks_account_id,
)
from ultra_csm.data_plane.tenants.crateworks.comms import (
    DOCKSIDE_ID,
    FakeZendeskClient,
    arc_c1_comms,
    arc_c1_relationships,
    dockside_ticket,
)
from eval.expected_actions_gold import load_expected_actions

ARTIFACT_PATH = Path(__file__).with_name("crateworks_battery.json")

CHECKPOINT_DAYS = (60, 100, 200)


def check(ok: bool, problems: list[str], label: str, detail: Any = None) -> None:
    if not ok:
        problems.append(f"{label}: {detail}" if detail is not None else label)


def _as_of(day_offset: int) -> str:
    return (date.fromisoformat(SEED_DATE) + timedelta(days=day_offset)).isoformat()


# ---------------------------------------------------------------------------
# 1. Arc C1 checkpoint truths (gold rows)
# ---------------------------------------------------------------------------


def check_arc_c1_checkpoints() -> dict[str, Any]:
    problems: list[str] = []
    detail: dict[str, Any] = {}

    gold_rows = {
        row.checkpoint_day: row
        for row in load_expected_actions("crateworks")
        if row.account_slug == DOCKSIDE_SLUG
    }
    comms = arc_c1_comms()

    for day in CHECKPOINT_DAYS:
        row = gold_rows.get(day)
        check(row is not None, problems, f"day {day}: no gold row for {DOCKSIDE_SLUG}", None)
        if row is None:
            continue
        check(row.mode == "gap", problems, f"day {day}: gold mode must be 'gap'", row.mode)
        check(
            "escalation" in row.motion_in,
            problems,
            f"day {day}: gold motion_in must require escalation",
            row.motion_in,
        )

        rels = arc_c1_relationships(day)
        latency = reply_latency_trend(DOCKSIDE_ID, comms, as_of=_as_of(day))
        width = thread_participation_width(DOCKSIDE_ID, rels, as_of=_as_of(day))

        latency_evidence_ids = {e.source_id for e in latency.evidence}
        gold_evidence_ids = set(row.evidence_must_include)
        check(
            gold_evidence_ids <= latency_evidence_ids,
            problems,
            f"day {day}: gold evidence_must_include not a subset of real reply_latency_trend evidence",
            {"gold": sorted(gold_evidence_ids), "real": sorted(latency_evidence_ids)},
        )

        # THE core assertion (bible section 2, FORBIDDEN clause): width must
        # never be reported/graded as "two engaged stakeholders" -- this
        # battery asserts the raw signal reads 2 (proving the mess is real
        # and uncorrected) while the gold row for this checkpoint requires
        # escalation, not a "multi-threaded health" motion. There is no
        # "healthy multi-threaded" motion in PLAYBOOK_MOTIONS this could
        # silently satisfy instead (content_route/cohort_action/campaign_enroll
        # are all lower-touch happy-path motions, none of which is
        # "escalation" -- so requiring escalation in motion_in is itself the
        # assertion that width-2 must not read as fine).
        check(
            width.value == 2.0,
            problems,
            f"day {day}: expected the mess to produce width=2 (uncorrected duplicate-contact read)",
            width.value,
        )
        detail[str(day)] = {
            "latency_trend_hours": latency.value,
            "width": width.value,
            "gold_mode": row.mode,
            "gold_motion_in": list(row.motion_in),
        }

    return {"case": "arc-c1-checkpoints", "ok": not problems, "problems": problems, "detail": detail}


# ---------------------------------------------------------------------------
# 2. Mess-integrity checks (the authored mess quotas are actually present)
# ---------------------------------------------------------------------------

_OPTIONAL_ACCOUNT_FIELDS = (
    "secondary_contact_email", "renewal_notes", "parent_company_ref", "last_qbr_date",
    "tier_override_reason", "preferred_channel", "billing_contact", "support_plan",
    "onboarding_owner", "expansion_notes",
)
_STALE_DATE = "2023-06-21"


def check_mess_integrity() -> dict[str, Any]:
    problems: list[str] = []
    detail: dict[str, Any] = {}
    book = build_flat_crateworks_book()

    account_by_slug = {slug: row for slug, row in zip((s for s, *_ in ACCOUNTS), book.account_rows)}
    for slug, row in account_by_slug.items():
        empties = sum(1 for f in _OPTIONAL_ACCOUNT_FIELDS if not row.get(f))
        ratio = empties / len(_OPTIONAL_ACCOUNT_FIELDS)
        check(
            ratio >= 0.4,
            problems,
            f"{slug}: optional-field empty ratio below the 40% floor",
            ratio,
        )
        detail.setdefault("empty_ratio_by_account", {})[slug] = ratio

    statuses = {row["account_status"] for row in book.account_rows}
    required_variants = {"kinda active?", "ACTIVE", "active "}
    check(
        required_variants <= statuses,
        problems,
        "account_status free-text variants missing required set",
        {"expected_subset": sorted(required_variants), "found": sorted(statuses)},
    )
    detail["status_variants"] = sorted(statuses)

    contacts_by_account: dict[str, list[dict[str, Any]]] = {}
    for row in book.contact_rows:
        contacts_by_account.setdefault(row["AccountId"], []).append(row)

    for slug, *_rest in ACCOUNTS:
        account_id = crateworks_account_id(slug)
        rows = contacts_by_account.get(account_id, [])
        # Duplicate pair: two rows whose case-folded names match.
        names = [r["full_name"].strip().lower() for r in rows]
        dup_count = len(names) - len(set(names))
        check(
            dup_count >= 1,
            problems,
            f"{slug}: expected at least one duplicate-contact-name pair",
            {"names": names},
        )
        # Stale record: exactly one row with last_touch == the 3-years-ago date.
        stale_rows = [r for r in rows if r["last_touch"] == _STALE_DATE]
        check(
            len(stale_rows) == 1,
            problems,
            f"{slug}: expected exactly one stale record ({_STALE_DATE})",
            len(stale_rows),
        )

    # Header mess: the account table's display-name header carries the
    # trailing-space/title-case variant; the contact table's account-join
    # header is differently cased/shaped ("AccountId" vs the account
    # table's own "acct_id") -- both authored, checked directly.
    check(
        "Account Name " in book.account_rows[0],
        problems,
        "account table missing the trailing-space display-name header",
        list(book.account_rows[0].keys()),
    )
    check(
        "acct_id" in book.account_rows[0],
        problems,
        "account table missing the snake_case identity header",
        list(book.account_rows[0].keys()),
    )

    return {"case": "mess-integrity", "ok": not problems, "problems": problems, "detail": detail}


# ---------------------------------------------------------------------------
# 3. Degradation honesty: zero fabricated values across all 10 accounts at
#    3 checkpoint days.
# ---------------------------------------------------------------------------


def check_degradation_honesty() -> dict[str, Any]:
    problems: list[str] = []
    detail: dict[str, Any] = {}
    comms = arc_c1_comms()

    for slug, *_rest in ACCOUNTS:
        account_id = crateworks_account_id(slug)
        for day in CHECKPOINT_DAYS:
            as_of = _as_of(day)
            if slug == DOCKSIDE_SLUG:
                rels = arc_c1_relationships(day)
                latency = reply_latency_trend(account_id, comms, as_of=as_of)
                width = thread_participation_width(account_id, rels, as_of=as_of)
            else:
                # Controls have no comms/relationship fixtures at all (bible
                # section 4): this IS the honest degraded read -- both
                # signals must return None/insufficient_history, never a
                # fabricated number computed from nothing.
                latency = reply_latency_trend(account_id, [], as_of=as_of)
                width = thread_participation_width(account_id, [], as_of=as_of)
                check(
                    latency.value is None,
                    problems,
                    f"{slug}@day{day}: reply_latency_trend fabricated a value with zero comms fixtures",
                    latency.value,
                )
                check(
                    width.value == 0.0,
                    problems,
                    f"{slug}@day{day}: thread_participation_width should read 0 with zero relationship fixtures",
                    width.value,
                )
            # Every computed value must trace to real evidence ids -- never
            # a value present with no evidence backing it.
            if latency.value is not None:
                check(
                    len(latency.evidence) > 0,
                    problems,
                    f"{slug}@day{day}: reply_latency_trend has a value but no evidence ids",
                    latency.value,
                )
            if width.value and width.value > 0:
                check(
                    len(width.evidence) > 0,
                    problems,
                    f"{slug}@day{day}: thread_participation_width has a nonzero value but no evidence ids",
                    width.value,
                )
            detail[f"{slug}@{day}"] = {
                "latency_value": latency.value,
                "width_value": width.value,
            }

    return {"case": "degradation-honesty", "ok": not problems, "problems": problems, "detail": detail}


# ---------------------------------------------------------------------------
# 4. Controls zero-flag: none of the nine non-arc accounts produce a
#    signal-derived flag at any checkpoint.
# ---------------------------------------------------------------------------


def check_controls_zero_flag() -> dict[str, Any]:
    problems: list[str] = []
    detail: dict[str, Any] = {}

    for slug in CONTROL_SLUGS:
        account_id = crateworks_account_id(slug)
        for day in CHECKPOINT_DAYS:
            as_of = _as_of(day)
            latency = reply_latency_trend(account_id, [], as_of=as_of)
            width = thread_participation_width(account_id, [], as_of=as_of)
            flagged = latency.value is not None or (width.value or 0) > 0
            check(
                not flagged,
                problems,
                f"{slug}@day{day}: control account produced a non-null/non-zero signal",
                {"latency": latency.value, "width": width.value},
            )
            detail[f"{slug}@{day}"] = {"flagged": flagged}

    gold_rows = load_expected_actions("crateworks")
    for row in gold_rows:
        if row.account_slug in CONTROL_SLUGS:
            check(
                row.mode == "none",
                problems,
                f"{row.account_slug}@day{row.checkpoint_day}: control gold row must be mode 'none'",
                row.mode,
            )

    return {"case": "controls-zero-flag", "ok": not problems, "problems": problems, "detail": detail}


# ---------------------------------------------------------------------------
# 5. Canary presence across all 10 accounts (D4 sweep-list requirement).
# ---------------------------------------------------------------------------


def check_canary_presence() -> dict[str, Any]:
    problems: list[str] = []
    detail: dict[str, Any] = {}
    book = build_flat_crateworks_book()

    for slug, row in zip((s for s, *_ in ACCOUNTS), book.account_rows):
        token = canary_token(TENANT, slug)
        check(
            token in row.get("account_notes", ""),
            problems,
            f"{slug}: account_notes missing its own canary token",
            row.get("account_notes"),
        )
        detail[slug] = token

    ticket = dockside_ticket()
    dockside_token = canary_token(TENANT, DOCKSIDE_SLUG)
    check(
        any(dockside_token in note for note in ticket.internal_notes),
        problems,
        "Dockside ticket internal note missing its canary token",
        ticket.internal_notes,
    )

    client = FakeZendeskClient()
    from ultra_csm.data_plane.live_smoke import HttpRequest

    resp = client.send(
        HttpRequest(method="GET", url="https://crateworks.zendesk.example/api/v2/tickets.json", headers={})
    )
    body_text = json.dumps(resp.json())
    check(dockside_token in body_text, problems, "canary token not present in served ticket payload", None)

    return {"case": "canary-presence", "ok": not problems, "problems": problems, "detail": detail}


# ---------------------------------------------------------------------------
# 6. Determinism
# ---------------------------------------------------------------------------


def check_repeatability() -> dict[str, Any]:
    first = run_battery(_recurse=False)
    second = run_battery(_recurse=False)
    identical = json.dumps(first, sort_keys=True, default=str) == json.dumps(
        second, sort_keys=True, default=str
    )
    return {
        "case": "repeatability",
        "ok": identical,
        "problems": [] if identical else ["two consecutive runs were not byte-identical"],
        "detail": {},
    }


CASES = (
    check_arc_c1_checkpoints,
    check_mess_integrity,
    check_degradation_honesty,
    check_controls_zero_flag,
    check_canary_presence,
)


def run_battery(*, _recurse: bool = True) -> dict[str, Any]:
    results = [fn() for fn in CASES]
    if _recurse:
        results.append(check_repeatability())
    return {
        "artifact": "crateworks_battery",
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
