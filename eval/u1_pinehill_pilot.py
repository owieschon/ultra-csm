"""Phase U1 pilot: Pinehill Transport's onboarding-stall arc, end to end.

Runs the existing sweep/briefing (``run_time_to_value_sweep``) against the
35-account synthetic book at three day_offsets bracketing the stall
(before / during / after — see docs/SYNTHETIC_UNIVERSE_BIBLE.md, arc 1),
alongside the new deterministic signal extractor's output. Prints a
checkpoint report for owner review; this is the mandatory Phase U1
stop-and-show, not a battery (Phase U3 turns this into assertions).

Not wired into any Makefile target -- this is a one-shot pilot script, run
directly: ``PYTHONPATH=src:. .venv/bin/python -m eval.u1_pinehill_pilot``.
"""

from __future__ import annotations

import json
from pathlib import Path

import psycopg

from ultra_csm.agent1 import SweepResult, run_time_to_value_sweep
from ultra_csm.data_plane import (
    CustomerDataPlane,
    FixtureCRMDataConnector,
    FixtureCSPlatformConnector,
    FixtureProductTelemetryConnector,
)
from ultra_csm.data_plane.book_simulator import simulate_book
from ultra_csm.data_plane.comms_fixtures import (
    pinehill_cases_as_of,
    pinehill_calendar_events,
    pinehill_communication_signals,
    pinehill_email_thread,
    pinehill_stakeholder_relationships,
    PINEHILL_ACCOUNT_ID,
)
from ultra_csm.data_plane.fixtures import FixtureCustomerData
from ultra_csm.data_plane.rocketlane_fixtures import (
    FixtureOnboardingConnector,
    has_activation_gap,
    pinehill_onboarding_fixture_data,
)
from ultra_csm.data_plane.signal_extractor import (
    meeting_cadence_shift,
    reply_latency_trend,
    thread_participation_width,
    ticket_frequency_window,
)
from ultra_csm.data_plane.synthetic_book import SEED_DATE, build_synthetic_book
from ultra_csm.governance import ActionGate, FixtureVerdictSource, ROLE_CS_ORCHESTRATOR, make_principal, seed_roster
from ultra_csm.platform import EphemeralCluster
from ultra_csm.platform.db import apply_migrations, session
from ultra_csm.platform.seed import SEED_CLOCK, det_uuid

REPO = Path(__file__).resolve().parents[1]
MIGRATIONS = REPO / "migrations"
OUTPUT_PATH = REPO / "eval" / "u1_pinehill_pilot.json"
TENANT_ID = det_uuid("tenant", "ultra-csm-u1-pilot")
SEED_ACTOR_ID = det_uuid("principal", "ultra-csm-u1-pilot", "system-seed")

# Checkpoints: before the stall's third case, during it, well after the
# day-300 graduation to steady_state.
CHECKPOINTS = ((20, "before"), (50, "during"), (310, "after"))


def _as_of_iso(day_offset: int) -> str:
    from datetime import date, timedelta

    return (date.fromisoformat(SEED_DATE) + timedelta(days=day_offset)).isoformat()


def _restrict_to_pinehill(data: FixtureCustomerData, *, day_offset: int) -> FixtureCustomerData:
    def keep(items):
        return tuple(i for i in items if getattr(i, "account_id", None) == PINEHILL_ACCOUNT_ID)

    return FixtureCustomerData(
        accounts=tuple(a for a in data.accounts if a.account_id == PINEHILL_ACCOUNT_ID),
        companies=tuple(c for c in data.companies if c.company_id == PINEHILL_ACCOUNT_ID),
        contacts=keep(data.contacts),
        cases=tuple(pinehill_cases_as_of(day_offset)),
        opportunities=keep(data.opportunities),
        health_scores=keep(data.health_scores),
        ctas=keep(data.ctas),
        success_plans=keep(data.success_plans),
        adoption_summaries=keep(data.adoption_summaries),
        entitlements=keep(data.entitlements),
        usage_signals=keep(data.usage_signals),
        milestones=keep(data.milestones),
        tenant_accounts={TENANT_ID: (PINEHILL_ACCOUNT_ID,)},
    )


def _data_plane_for_day(base, day_offset: int) -> CustomerDataPlane:
    book = simulate_book(base, day_offset)
    data = _restrict_to_pinehill(book, day_offset=day_offset)
    return CustomerDataPlane(
        crm=FixtureCRMDataConnector(data=data),
        cs=FixtureCSPlatformConnector(data=data),
        telemetry=FixtureProductTelemetryConnector(data=data),
        onboarding=FixtureOnboardingConnector(data=pinehill_onboarding_fixture_data(day_offset)),
    )


def _work_item_for_pinehill(sweep: SweepResult):
    for item in sweep.work_items:
        if item.account_id == PINEHILL_ACCOUNT_ID:
            return item
    return None


def _extractor_summary(day_offset: int, as_of: str) -> dict:
    signals = pinehill_communication_signals(day_offset)
    relationships = pinehill_stakeholder_relationships(day_offset)
    calendar = pinehill_calendar_events(day_offset)
    cases = pinehill_cases_as_of(day_offset)

    latency = reply_latency_trend(PINEHILL_ACCOUNT_ID, signals, as_of=as_of)
    width = thread_participation_width(PINEHILL_ACCOUNT_ID, relationships, as_of=as_of)
    cadence = meeting_cadence_shift(PINEHILL_ACCOUNT_ID, calendar, as_of=as_of)
    tickets = ticket_frequency_window(PINEHILL_ACCOUNT_ID, cases, as_of=as_of)

    onboarding = pinehill_onboarding_fixture_data(day_offset)
    gaps = []
    for phase in onboarding.phases:
        project = onboarding.projects[0]
        gap = has_activation_gap(phase, project, onboarding.tasks, as_of=as_of)
        gaps.append({"phase": phase.name, "activation_gap": gap, "due_date_actual": phase.due_date_actual})

    return {
        "reply_latency_trend_hours": {"value": latency.value, "detail": latency.detail},
        "thread_participation_width": {"value": width.value, "detail": width.detail},
        "meeting_cadence_shift_days": {"value": cadence.value, "detail": cadence.detail},
        "ticket_frequency_window": {"value": tickets.value, "detail": tickets.detail},
        "rocketlane_activation_gaps": gaps,
        "email_message_count": len(pinehill_email_thread(day_offset)["messages"]),
        "calendar_event_count": len(calendar["items"]),
        "case_count": len(cases),
    }


def run_pilot() -> dict:
    with EphemeralCluster() as cluster:
        with psycopg.connect(**cluster.dsn(user=cluster.BOOTSTRAP_USER)) as boot:
            apply_migrations(boot, MIGRATIONS)
        with psycopg.connect(**cluster.dsn(user="app_runtime")) as conn:
            with session(conn, tenant_id=TENANT_ID, actor_id=SEED_ACTOR_ID, now=SEED_CLOCK) as cur:
                cur.execute(
                    "INSERT INTO tenant (tenant_id, name) VALUES (%s, %s) "
                    "ON CONFLICT (tenant_id) DO NOTHING",
                    (TENANT_ID, "Ultra CSM U1 Pilot"),
                )
                cur.execute(
                    "INSERT INTO principal (principal_id, tenant_id, kind, display_name) "
                    "VALUES (%s, %s, 'agent', %s) ON CONFLICT (principal_id) DO NOTHING",
                    (SEED_ACTOR_ID, TENANT_ID, "system-seed"),
                )
            seed_roster(conn, tenant_id=TENANT_ID, actor_id=SEED_ACTOR_ID, now=SEED_CLOCK)
            actor_id = make_principal(
                conn,
                tenant_id=TENANT_ID,
                actor_id=SEED_ACTOR_ID,
                display_name="u1-pilot",
                role=ROLE_CS_ORCHESTRATOR,
                now=SEED_CLOCK,
            )
            gate = ActionGate(
                conn,
                tenant_id=TENANT_ID,
                actor_principal_id=actor_id,
                verdict_source=FixtureVerdictSource(),
                now=SEED_CLOCK,
            )

            base = build_synthetic_book()
            checkpoints = []
            for day_offset, label in CHECKPOINTS:
                as_of = _as_of_iso(day_offset)
                data_plane = _data_plane_for_day(base, day_offset)
                sweep = run_time_to_value_sweep(
                    data_plane,
                    TENANT_ID,
                    gate,
                    sweep_principal_id=actor_id,
                    as_of=as_of,
                )
                work_item = _work_item_for_pinehill(sweep)
                checkpoints.append(
                    {
                        "label": label,
                        "day_offset": day_offset,
                        "as_of": as_of,
                        "briefing": {
                            "disposition": work_item.disposition if work_item else None,
                            "recommended_action": (
                                work_item.recommended_action if work_item else None
                            ),
                            "reason": work_item.reason if work_item else None,
                            "priority": work_item.priority if work_item else None,
                            "evidence_count": len(work_item.evidence) if work_item else 0,
                        }
                        if work_item is not None
                        else None,
                        "extractor": _extractor_summary(day_offset, as_of),
                    }
                )

    artifact = {
        "artifact": "u1_pinehill_pilot",
        "account_id": PINEHILL_ACCOUNT_ID,
        "checkpoints": checkpoints,
    }
    OUTPUT_PATH.write_text(json.dumps(artifact, indent=2, sort_keys=True, default=str) + "\n")
    return artifact


def main() -> int:
    artifact = run_pilot()
    print(json.dumps(artifact, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
