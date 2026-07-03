"""R1: Rocketlane onboarding contracts, fixture connector, source-map coverage,
and recorded-payload parse tests (Program 4).

Recorded R0 payloads live outside the repo at
~/ultra-csm-corpus-runs/rocketlane-baseline-20260703/ (captured live via the
Rocketlane MCP connector). Tests that parse them skip gracefully if that path
is absent (e.g. CI without the local corpus-runs directory) rather than
failing the suite -- the payloads are a local verification aid, not a
repo-committed fixture (they contain the trial org's sample customer contact
names).
"""

from __future__ import annotations

from dataclasses import fields
import json
from pathlib import Path
import socket

import pytest

from ultra_csm.data_plane import (
    ALL_SOURCE_MAPS,
    RL_AT_RISK_TASKS,
    RL_EMPTY_PROJECT,
    RL_HEALTHY,
    RL_MISSING_DATES,
    RL_PRIVATE_PHASE,
    RL_RUNNING_LATE,
    ROCKETLANE_SOURCE_MAPS,
    FixtureOnboardingConnector,
    OnboardingPhase,
    OnboardingProject,
    OnboardingTask,
    default_onboarding_fixture_data,
    derive_ttv_milestones,
    has_activation_gap,
)
from ultra_csm.data_plane import contracts
from ultra_csm.data_plane.adapters.rocketlane import parse_phase, parse_project, parse_task

CORPUS_RUN_DIR = Path.home() / "ultra-csm-corpus-runs" / "rocketlane-baseline-20260703"


# ---------------------------------------------------------------------------
# Source-map coverage: every Onboarding* contract field is vendor-backed or
# explicitly derived. Mirrors the "every field has an entry" gate the spec
# calls for; no such generic test existed before this program, so this one
# is intentionally structured to cover the other three ALL_SOURCE_MAPS
# families too rather than being Rocketlane-only.
# ---------------------------------------------------------------------------

_CONTRACT_CLASSES = {
    "OnboardingProject": OnboardingProject,
    "OnboardingPhase": OnboardingPhase,
    "OnboardingTask": OnboardingTask,
}


@pytest.mark.parametrize("contract_name", sorted(_CONTRACT_CLASSES))
def test_rocketlane_source_map_covers_every_contract_field(contract_name):
    dataclass_type = _CONTRACT_CLASSES[contract_name]
    declared = {f.name for f in fields(dataclass_type)}
    source_map = ROCKETLANE_SOURCE_MAPS[contract_name]
    mapped = set(source_map.fields.keys())
    assert declared == mapped, (
        f"{contract_name}: dataclass fields {declared - mapped} have no source-map "
        f"entry, or source-map has stale entries {mapped - declared}"
    )


def test_rocketlane_source_maps_registered_in_all_source_maps():
    for name in ("OnboardingProject", "OnboardingPhase", "OnboardingTask"):
        assert name in ALL_SOURCE_MAPS
        assert ALL_SOURCE_MAPS[name].vendor == "Rocketlane"


def test_rocketlane_source_map_docs_are_https():
    for obj_map in ROCKETLANE_SOURCE_MAPS.values():
        assert obj_map.docs_url.startswith("https://developer.rocketlane.com/")


# ---------------------------------------------------------------------------
# Fixture connector: socket-free, deterministic, mirrors FixtureCRMDataConnector.
# ---------------------------------------------------------------------------


def test_onboarding_fixture_connector_does_not_open_sockets(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("onboarding fixture attempted network access")

    monkeypatch.setattr(socket, "create_connection", boom)

    conn = FixtureOnboardingConnector()
    assert conn.list_projects_for_account(RL_HEALTHY)
    assert conn.derive_ttv_milestones(RL_HEALTHY)


def test_onboarding_fixture_connector_matches_protocol_shape():
    # OnboardingConnector is a structural Protocol; assert the fixture
    # implements every method the Protocol declares.
    protocol_methods = {
        name
        for name in dir(contracts.OnboardingConnector)
        if not name.startswith("_")
    }
    conn = FixtureOnboardingConnector()
    for method in protocol_methods:
        assert hasattr(conn, method), f"fixture connector missing {method}"


def test_healthy_project_yields_achieved_milestone():
    conn = FixtureOnboardingConnector()
    milestones = conn.derive_ttv_milestones(RL_HEALTHY)
    assert len(milestones) == 1
    m = milestones[0]
    assert m.account_id == RL_HEALTHY
    assert m.achieved_at is not None
    assert m.expected_by is not None
    assert m.evidence_signal_ids  # phase id + at least the one task id


def test_missing_dates_phase_is_skipped_not_fabricated():
    """Adversarial: a phase with no due_date must never produce a milestone
    with a guessed expected_by -- it is skipped entirely (fail-closed)."""
    conn = FixtureOnboardingConnector()
    assert conn.derive_ttv_milestones(RL_MISSING_DATES) == []


def test_running_late_project_flags_activation_gap_via_progress():
    data = default_onboarding_fixture_data()
    conn = FixtureOnboardingConnector()
    milestones = conn.derive_ttv_milestones(RL_RUNNING_LATE)
    assert len(milestones) == 1
    project = next(p for p in data.projects if p.account_id == RL_RUNNING_LATE)
    phase = next(ph for ph in data.phases if ph.project_id == project.project_id)
    tasks = tuple(t for t in data.tasks if t.project_id == project.project_id)
    assert project.progress == "running_late"
    assert has_activation_gap(phase, project, tasks, as_of="2026-06-01") is True


def test_at_risk_task_flags_activation_gap_even_before_due_date():
    """Adversarial: atRisk=true on a task must flag the gap even when the
    phase due date is far in the future (not yet overdue)."""
    data = default_onboarding_fixture_data()
    project = next(p for p in data.projects if p.account_id == RL_AT_RISK_TASKS)
    phase = next(ph for ph in data.phases if ph.project_id == project.project_id)
    tasks = tuple(t for t in data.tasks if t.project_id == project.project_id)
    assert any(t.at_risk for t in tasks)
    # as_of is far before the phase due date -- not overdue by date alone.
    assert has_activation_gap(phase, project, tasks, as_of="2026-06-01") is True


def test_private_phase_still_contributes_evidence():
    """Private is a visibility flag, not an evidence-eligibility flag."""
    conn = FixtureOnboardingConnector()
    milestones = conn.derive_ttv_milestones(RL_PRIVATE_PHASE)
    assert len(milestones) == 1
    data = default_onboarding_fixture_data()
    project_id = next(p.project_id for p in data.projects if p.account_id == RL_PRIVATE_PHASE)
    private_phase = next(ph for ph in data.phases if ph.project_id == project_id)
    assert private_phase.private is True
    assert private_phase.phase_id in milestones[0].evidence_signal_ids


def test_empty_project_yields_no_milestones_not_an_error():
    conn = FixtureOnboardingConnector()
    assert conn.derive_ttv_milestones(RL_EMPTY_PROJECT) == []
    assert conn.list_projects_for_account(RL_EMPTY_PROJECT)
    assert conn.list_phases(
        conn.list_projects_for_account(RL_EMPTY_PROJECT)[0].project_id
    ) == []


def test_list_tasks_at_risk_only_filters_correctly():
    conn = FixtureOnboardingConnector()
    project = conn.list_projects_for_account(RL_AT_RISK_TASKS)[0]
    all_tasks = conn.list_tasks(project.project_id)
    at_risk = conn.list_tasks(project.project_id, at_risk_only=True)
    assert len(all_tasks) == 2
    assert len(at_risk) == 1
    assert at_risk[0].at_risk is True


def test_derive_ttv_milestones_pure_function_matches_connector_output():
    data = default_onboarding_fixture_data()
    direct = derive_ttv_milestones(
        RL_HEALTHY, projects=data.projects, phases=data.phases, tasks=data.tasks
    )
    via_connector = FixtureOnboardingConnector(data=data).derive_ttv_milestones(RL_HEALTHY)
    assert direct == via_connector


# ---------------------------------------------------------------------------
# Recorded-payload parse: R0's live sample payloads must parse through the
# new contracts with zero unknown-field surprises.
# ---------------------------------------------------------------------------


def _skip_if_no_corpus_run():
    if not CORPUS_RUN_DIR.exists():
        pytest.skip(f"local corpus-run dir not present: {CORPUS_RUN_DIR}")


def test_r0_recorded_projects_parse_cleanly():
    _skip_if_no_corpus_run()
    payload = json.loads((CORPUS_RUN_DIR / "projects_sample.json").read_text())
    detail_records = payload["detail"]
    assert len(detail_records) == 2
    for record in detail_records:
        project = parse_project(record)
        assert project.project_id
        assert project.account_id
        assert project.name
        # Verified live delta: inferredProgress is absent from these live
        # payloads even with includeAllFields=true (re-verified live during
        # this program, not just from the captured sample) -- fail-safe
        # default to "none" rather than raising.
        assert project.progress == "none"


def test_r0_recorded_task_sample_parses_cleanly():
    _skip_if_no_corpus_run()
    payload = json.loads((CORPUS_RUN_DIR / "tasks_sample.json").read_text())
    record = payload["detail_sample"]
    task = parse_task(record)
    assert task.task_id
    assert task.project_id
    assert task.phase_id
    assert task.status_label == "Completed"
    assert task.due_date_actual is not None
    assert task.at_risk is False
    assert task.assignee_ids


def test_r0_recorded_phase_detail_parses_cleanly_live_delta_from_search_shape():
    """The R0 phases_sample.json captured the *search* shape
    ({phaseId, phaseName} only, no project/date fields) -- get_phases search
    requires a projectId filter and returns a thin row. This program's own
    live get_phases(phaseId=...) detail call (issued while writing R1)
    confirmed the *detail* shape does carry project.projectId, dates, and
    status -- parse_phase requires the detail shape, matching the connector's
    intended list_phases implementation (id search, then per-id detail
    fetch, or a bridge that supplies project_id from the calling context).
    This test locks in that same detail shape from a hand-transcribed
    live-verified record (values match the phase actually fetched live
    2026-07-03: phase 'Pre-Kickoff' under the '[Sample] Acme 2 week
    onboarding' project) rather than depending on a REST detail dump this
    program never captured to a fixture file.
    """
    live_verified_detail_shape = {
        "phaseId": 5000000385224,
        "phaseName": "Pre-Kickoff",
        "project": {"projectId": 5000000116921, "projectName": "[Sample] Acme 2 week onboarding"},
        "startDate": "2026-06-27",
        "dueDate": "2026-06-29",
        "status": {"value": 2, "label": "In Progress"},
        "private": True,
    }
    phase = parse_phase(live_verified_detail_shape)
    assert phase.phase_id == "5000000385224"
    assert phase.project_id == "5000000116921"
    assert phase.name == "Pre-Kickoff"
    assert phase.due_date == "2026-06-29"
    assert phase.due_date_actual is None
    assert phase.private is True


def test_r0_phase_search_shape_is_too_thin_for_parse_phase():
    """Documents the delta: the search/list shape genuinely lacks
    project.projectId, so parse_phase correctly raises rather than
    fabricating a project_id."""
    _skip_if_no_corpus_run()
    from ultra_csm.data_plane.transforms import TransformError

    payload = json.loads((CORPUS_RUN_DIR / "phases_sample.json").read_text())
    project_block = next(v for k, v in payload.items() if k != "_note")
    thin_record = project_block["data"][0]
    assert "project" not in thin_record  # confirms the thin shape
    with pytest.raises(TransformError):
        parse_phase(thin_record)
