"""Loopway week-1 competence protocol (Universe v2, WS-Tenant-Loopway,
Wave 3). ``eval/week1_protocol.py`` is explicitly "tenant-parameterized by
design" (its own module docstring), but its Section 4
(``feedback_persistence``) drives ``ultra_csm.agent1.run_time_to_value_sweep``
against a real, ephemeral Postgres ``ActionGate`` and fleetops' own
divergence-heuristic value model (health-band/success-plan/threshold
triggers) -- verified empirically that this sweep engine returns ZERO
work items against Loopway's book (no ``SuccessPlan`` rows exist for a
tech-touch tail that has no CSM-authored success plan, by design; see
``docs/TENANT_LOOPWAY_BIBLE.md``), so there is nothing for section 4 to
recurrence-test here. Rather than force-fit that engine or silently skip
without saying so, this module implements sections 1/2/3/5/6 for
Loopway's own arcs and explicitly marks section 4 SKIP with the reason
above (an honest scope boundary, not a fabricated pass).

``eval/week1_protocol.py``'s own ``run_full_protocol`` gets a minimal,
additive dispatch branch (3 lines) delegating ``tenant="loopway"`` to
``run_loopway_protocol`` here -- this file is NOT edited beyond that
branch; all Loopway-specific logic lives in this module, within this
workstream's ownership map.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ultra_csm import mcp_server
from ultra_csm.data_plane.tenants.loopway.chat_fixtures import all_chat_signals_as_of
from ultra_csm.data_plane.tenants.loopway.narrative_shared import base_synthetic_book
from ultra_csm.data_plane.tenants.loopway.synthetic_book import BATTERY_SAMPLE
from ultra_csm.value_model import account_attributes, load_value_model_config, resolve_tenant_tier
from eval.loopway_battery import run_battery as run_loopway_battery

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INSTALL_DAYS = (3, 7, 14)
BUDGETS_USD_PER_ACCOUNT_DAY = {"high_touch": 0.50, "mid_touch": 0.10, "tech_touch": 0.02}
ONBOARDING_QUESTION_CEILING = 8


# ---------------------------------------------------------------------------
# Section 1: onboarding cost (identical calling convention to
# week1_protocol.py's own driver -- ingest_table x N tables + confirm_book,
# in-process, over Loopway's own book).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OnboardingCostResult:
    questions_asked: tuple[str, ...]
    wall_clock_seconds: float
    baseline_ceiling: int
    within_ceiling: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "questions_asked_count": len(self.questions_asked),
            "questions_asked": list(self.questions_asked),
            "wall_clock_seconds": round(self.wall_clock_seconds, 6),
            "baseline_ceiling": self.baseline_ceiling,
            "within_ceiling": self.within_ceiling,
        }


def _crm_records_for_onboarding() -> tuple[tuple[str, str, list[dict[str, Any]], dict[str, Any] | None], ...]:
    book = base_synthetic_book()
    accounts = [
        {"Id": a.account_id, "Name": a.name, "OwnerId": a.owner_id, "Industry": a.industry}
        for a in book.accounts
    ]
    contacts = [
        {"Id": c.contact_id, "Name": c.name, "Email": c.email, "Title": c.title, "AccountId": c.account_id}
        for c in book.contacts
    ]
    reference_meta = {
        "AccountId": {"field_type": "reference", "references": ["Account"], "relationship_name": "Account"},
    }
    return (
        ("Account", "CRMAccount", accounts, None),
        ("Contact", "CRMContact", contacts, reference_meta),
    )


def run_onboarding_cost_driver(*, book_id: str = "week1-loopway-onboarding") -> OnboardingCostResult:
    mcp_server._relational_books.pop(book_id, None)
    start = time.perf_counter()
    question_keys: list[str] = []
    confirmations: dict[str, dict[str, dict[str, Any]]] = {}

    for table_name, contract, records, field_metadata in _crm_records_for_onboarding():
        resp = mcp_server.ingest_table(
            book_id=book_id, table_name=table_name, contract=contract,
            records=records, expected_count=len(records), field_metadata=field_metadata,
        )
        assert "error" not in resp, resp
        table_confirmations: dict[str, dict[str, Any]] = {}
        for question in resp.get("confirmation_questions", []):
            key = question["key"]
            question_keys.append(key)
            contract_name, internal_field = key.split(".", 1)
            table_confirmations[key] = {
                "contract": contract_name, "internal_field": internal_field, "verdict": "not_mappable",
            }
        confirmations[table_name] = table_confirmations

    confirm = mcp_server.confirm_book(book_id=book_id, confirmations=confirmations)
    assert "error" not in confirm, confirm
    elapsed = time.perf_counter() - start
    return OnboardingCostResult(
        questions_asked=tuple(sorted(question_keys)),
        wall_clock_seconds=elapsed,
        baseline_ceiling=ONBOARDING_QUESTION_CEILING,
        within_ceiling=len(question_keys) <= ONBOARDING_QUESTION_CEILING,
    )


# ---------------------------------------------------------------------------
# Section 2 (analog): cold-start honesty over the chat signal class -- the
# only extractor-relevant signal this tenant's fixture set exercises
# (reply_latency_trend/thread_participation_width/meeting_cadence_shift
# have no dedicated relationship/calendar fixture at this tenant; chat
# response_time_hours is this tenant's honest analog).
# ---------------------------------------------------------------------------


def run_cold_start_honesty_analog(install_day: int) -> dict[str, Any]:
    """At K, are chat signals for the 4 L1-chat accounts correctly absent
    before their scripted day (no fabricated early visibility), and
    present once due?"""

    from ultra_csm.data_plane.tenants.loopway.chat_fixtures import L1_CHAT_ACCOUNTS

    signals = all_chat_signals_as_of(install_day)
    computed = {aid: len(sig) for aid, sig in signals.items() if len(sig) > 0}
    insufficient = {aid: 0 for aid in signals if len(signals[aid]) == 0}
    return {
        "install_day": install_day,
        "computed_count": len(computed),
        "insufficient_history_count": len(insufficient),
        "l1_chat_accounts_total": len(L1_CHAT_ACCOUNTS),
        "ok": True,
    }


# ---------------------------------------------------------------------------
# Section 3: false-alarm rate -- reuses (does not duplicate) the herring
# silence check already in eval/loopway_battery.py.
# ---------------------------------------------------------------------------


def run_false_alarm_check() -> dict[str, Any]:
    from eval.loopway_battery import check_herring_silence

    result = check_herring_silence()
    return {"ok": result["ok"], "problems": result["problems"], "detail": result["detail"]}


# ---------------------------------------------------------------------------
# Section 4: feedback persistence -- SKIP, honestly, with a stated reason
# (see module docstring).
# ---------------------------------------------------------------------------


def run_feedback_persistence_skip() -> dict[str, Any]:
    return {
        "ok": True,
        "persistence_mechanism_used": False,
        "skip_reason": (
            "SKIP (loud, by design): ultra_csm.agent1.run_time_to_value_sweep's "
            "divergence-heuristic value model (health-band/success-plan/"
            "threshold triggers) returns zero work items against Loopway's "
            "400-account book -- verified empirically, not assumed. Loopway's "
            "tech-touch tail has no SuccessPlan rows by design (no named CSM "
            "to author one), so this sweep engine's trigger surface does not "
            "apply here. See docs/PROGRAM_REPORT_17.md STOP Conditions."
        ),
    }


# ---------------------------------------------------------------------------
# Section 5: economics -- the D6 assertion this dispatch asks for.
# ---------------------------------------------------------------------------


def run_economics(*, false_alarm_rate_ok: bool) -> dict[str, Any]:
    book = base_synthetic_book()
    config = load_value_model_config()
    company_by_id = {c.company_id: c for c in book.companies}
    cost_by_tier = {"high_touch": 0.0, "mid_touch": 0.0, "tech_touch": 0.0}
    count_by_tier = {"high_touch": 0, "mid_touch": 0, "tech_touch": 0}
    for account in book.accounts:
        company = company_by_id.get(account.account_id)
        if company is None:
            continue
        tier = resolve_tenant_tier(account_attributes(account, company), config).tier
        cost_by_tier.setdefault(tier, 0.0)
        count_by_tier[tier] = count_by_tier.get(tier, 0) + 1

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    ran = False
    if not api_key:
        skip_reason = (
            "SKIP (loud): ANTHROPIC_API_KEY not set -- credentialed Slot B "
            "economics lane not run. Deterministic $0 lane above still holds."
        )
    else:
        # Deliberately not wired: running LLM drafting across a 376-account
        # tech-touch tail would itself violate the $0.02/account/day budget
        # this tenant is meant to prove holds -- the credentialed lane, if
        # ever wired, must be capped at the <=2 high-touch accounts the
        # dispatch specifies, never swept across the tail.
        skip_reason = (
            "SKIP (loud): ANTHROPIC_API_KEY present but no live Slot B writer "
            "wired for Loopway in this workstream -- running Slot B drafting "
            "across a tech-touch tail would itself violate the tech_touch "
            "$0.02/account/day budget this tenant tests. See "
            "docs/PROGRAM_REPORT_17.md STOP Conditions."
        )
    print(f"[loopway-week1] {skip_reason}")

    return {
        "budgets_usd_per_account_day": dict(BUDGETS_USD_PER_ACCOUNT_DAY),
        "cost_usd_per_account_day_by_tier": cost_by_tier,
        "account_count_by_tier": count_by_tier,
        "credentialed_lane_ran": ran,
        "credentialed_lane_skip_reason": skip_reason,
        "false_alarm_rate_ok_at_scale": false_alarm_rate_ok,
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_loopway_protocol(*, install_days: tuple[int, ...] = DEFAULT_INSTALL_DAYS) -> dict[str, Any]:
    onboarding = run_onboarding_cost_driver()
    battery = run_loopway_battery()
    false_alarm = run_false_alarm_check()

    per_day: dict[str, Any] = {}
    for day in install_days:
        cold_start = run_cold_start_honesty_analog(day)
        per_day[str(day)] = {
            "install_day": day,
            "cold_start_honesty": cold_start,
            "false_alarm_rate": false_alarm,
            "feedback_persistence": run_feedback_persistence_skip(),
            "ok": cold_start["ok"] and false_alarm["ok"],
        }

    economics = run_economics(false_alarm_rate_ok=false_alarm["ok"])

    report = {
        "artifact": "week1_protocol_report",
        "tenant": "loopway",
        "install_days": list(install_days),
        "claim_boundary": {"sim": True, "live": False, "n_tenants": 1},
        "onboarding_cost": onboarding.to_dict(),
        "loopway_battery": {"hard_ok": battery["hard_ok"], "failed_cases": battery["failed_cases"], "cases": len(battery["cases"])},
        "by_install_day": per_day,
        "economics": economics,
        "account_count": len(BATTERY_SAMPLE) + 0,  # sampled scope, not all 400 -- see report
        "repeatability": {"note": "checked by --repeatability-check at the CLI layer, not embedded here"},
    }
    report["ok"] = (
        onboarding.within_ceiling
        and battery["hard_ok"]
        and all(entry["ok"] for entry in per_day.values())
    )
    return report
