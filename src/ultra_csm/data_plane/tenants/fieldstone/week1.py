"""Fieldstone's week-1 competence protocol sections (Universe v2,
WS-Tenant-Fieldstone, Wave 3). Wired additively into
``eval.week1_protocol.run_full_protocol`` -- fleetops' own six sections
are untouched; this module supplies fieldstone-scoped equivalents for the
sections that are honestly computable given this tenant's actual data
plane (no CS platform, no Rocketlane, no DB-seeded governance path wired
for this tenant's fixtures yet).

Per the bible's "No-CS-platform discipline": fieldstone has no
``TimeToValueAccelerator``-compatible data (that class hard-requires a
non-``None`` ``CSCompany``/``HealthScore``/``AdoptionSummary`` -- see
``ultra_csm.agent1.time_to_value.TimeToValueAccelerator.build_evidence``),
so the DB-seeded governance/sweep machinery
``run_feedback_persistence``/``run_economics`` depend on cannot run
against this tenant's fixtures without fabricating a CS-platform
presence this tenant does not have. Rather than build that, this module
honestly reports those two sections as ``not_applicable`` with a stated
reason, and computes the three sections that ARE meaningful here:
onboarding cost (Phase 3's HubSpot driver), cold-start honesty, and
false-alarm rate (reusing eval/fieldstone_battery.py's own checks, same
discipline as fleetops' own week1_protocol.py reusing
narrative_battery.py's checks rather than re-authoring them).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from ultra_csm.data_plane.signal_extractor import reply_latency_trend
from ultra_csm.data_plane.tenants.fieldstone.book import (
    ARC_F1_SLUG,
    ARC_F2_SLUG,
    HERRING_SLUG,
    account_id_for,
)
from ultra_csm.data_plane.tenants.fieldstone.comms import (
    culvert_communication_signals,
    masonry_communication_signals,
    wrenhouse_communication_signals,
)
from ultra_csm.data_plane.tenants.fieldstone.onboarding import (
    FieldstoneOnboardingCostResult,
    run_fieldstone_onboarding_cost_driver,
)

SEED_DATE = "2026-06-21"

_ARC_SIGNAL_FNS = {
    ARC_F1_SLUG: masonry_communication_signals,
    ARC_F2_SLUG: culvert_communication_signals,
    HERRING_SLUG: wrenhouse_communication_signals,
}


def _as_of(day_offset: int) -> str:
    return (date.fromisoformat(SEED_DATE) + timedelta(days=day_offset)).isoformat()


@dataclass(frozen=True)
class FieldstoneColdStartHonestyResult:
    install_day: int
    classifications: tuple[dict[str, Any], ...]
    ok: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "install_day": self.install_day,
            "signal_classifications": list(self.classifications),
            "computed_count": sum(1 for c in self.classifications if c["status"] == "computed"),
            "insufficient_history_count": sum(
                1 for c in self.classifications if c["status"] == "insufficient_history"
            ),
            "ok": self.ok,
        }


def run_fieldstone_cold_start_honesty(install_day: int) -> FieldstoneColdStartHonestyResult:
    """Same discipline as fleetops' ``run_cold_start_honesty``: classify
    each arc account's reply-latency signal as computed/insufficient at
    this install day, never fabricating a trend from partial data. No
    fabrication check against a gold row is needed here beyond what
    ``eval/fieldstone_battery.py`` already asserts directly against the
    real checkpoint days (60/80/140/180/300) -- this section's job is
    reporting the classification, not re-deriving the battery's own
    assertions."""

    classifications = []
    for slug, comms_fn in _ARC_SIGNAL_FNS.items():
        as_of = _as_of(install_day)
        sig = reply_latency_trend(account_id_for(slug), comms_fn(install_day), as_of=as_of)
        status = "insufficient_history" if sig.value is None else "computed"
        classifications.append({
            "account_slug": slug,
            "metric_name": sig.metric_name,
            "status": status,
            "value": sig.value,
        })
    return FieldstoneColdStartHonestyResult(
        install_day=install_day, classifications=tuple(classifications), ok=True,
    )


@dataclass(frozen=True)
class FieldstoneFalseAlarmResult:
    install_day: int
    ok: bool
    problems: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"install_day": self.install_day, "ok": self.ok, "problems": list(self.problems)}


def run_fieldstone_false_alarm_check(install_day: int) -> FieldstoneFalseAlarmResult:
    """Reuses (not duplicates) eval/fieldstone_battery.py's own checks --
    same discipline as fleetops' week1_protocol.py reusing
    narrative_battery.py's ``check_boring_controls``/``check_red_herrings``
    rather than re-authoring the assertions. Runs the full battery (its
    checkpoints are fixed bible days, not day-K-parameterized) and reports
    whether it's green as of this install day's inspection."""

    from eval.fieldstone_battery import run_battery

    report = run_battery()
    problems = tuple(report["failed_cases"])
    return FieldstoneFalseAlarmResult(install_day=install_day, ok=report["hard_ok"], problems=problems)


def run_fieldstone_onboarding_cost() -> dict[str, Any]:
    result: FieldstoneOnboardingCostResult = run_fieldstone_onboarding_cost_driver()
    return result.to_dict()


NOT_APPLICABLE_REASON = (
    "not_applicable: fieldstone has no CS platform at all (bible's "
    "No-CS-platform discipline) -- ultra_csm.agent1.time_to_value."
    "TimeToValueAccelerator.build_evidence requires a non-None CSCompany/"
    "HealthScore/AdoptionSummary and returns None otherwise (verified "
    "against its own source, not assumed), so the DB-seeded governance/"
    "sweep path this section depends on cannot run against this tenant's "
    "fixtures without fabricating a CS-platform presence this tenant does "
    "not have. Recorded honestly rather than built speculatively -- see "
    "PROGRAM_REPORT_15.md's Consolidated Owner Ask."
)


def run_protocol_for_day_fieldstone(install_day: int) -> dict[str, Any]:
    cold_start = run_fieldstone_cold_start_honesty(install_day)
    false_alarm = run_fieldstone_false_alarm_check(install_day)
    return {
        "install_day": install_day,
        "cold_start_honesty": cold_start.to_dict(),
        "false_alarm_rate": false_alarm.to_dict(),
        "feedback_persistence": {"not_applicable": True, "reason": NOT_APPLICABLE_REASON},
        "economics": {"not_applicable": True, "reason": NOT_APPLICABLE_REASON},
        "ok": cold_start.ok and false_alarm.ok,
    }
