"""Rocketlane onboarding fixture connector and the TTV bridge.

The fixture connector is socket-free/cred-free, mirroring the existing
``FixtureCRMDataConnector`` / ``FixtureCSPlatformConnector`` pattern in
:mod:`ultra_csm.data_plane.fixtures`. ``derive_ttv_milestones`` is the bridge
described in docs/ROCKETLANE_ONBOARDING_CONNECTOR_SPEC.md: it adapts
Rocketlane phase/task structure into the *existing*
:class:`~ultra_csm.data_plane.contracts.TimeToValueMilestone` shape Agent 1
already consumes — no new agent, no new scorecard pillar.
"""

from __future__ import annotations

from dataclasses import dataclass

from ultra_csm._util import iso_date
from ultra_csm.data_plane.contracts import (
    OnboardingPhase,
    OnboardingProject,
    OnboardingTask,
    TimeToValueMilestone,
)


def det_rocketlane_id(*parts: object) -> str:
    """Deterministic fixture id, local to this module to avoid a fixtures.py import cycle."""

    from uuid import NAMESPACE_URL, uuid5

    return str(uuid5(NAMESPACE_URL, "ultra-csm:rocketlane:" + ":".join(map(str, parts))))


@dataclass(frozen=True)
class FixtureOnboardingData:
    projects: tuple[OnboardingProject, ...]
    phases: tuple[OnboardingPhase, ...]
    tasks: tuple[OnboardingTask, ...]


def _resolve_achieved_at(
    phase: OnboardingPhase,
    phase_tasks: tuple[OnboardingTask, ...],
) -> str | None:
    """Prefer a task-level ``due_date_actual`` over the phase's own.

    Rocketlane's server-side auto-completion cascade sets a phase's
    ``due_date_actual`` to the write-time "now" when its last task
    completes, not to any caller-supplied or task-grounded date (see
    docs/LIVE_INTEGRATION_FINDINGS.md, "Auto-completion cascade") -- the
    phase-level actual is contaminated evidence. A task's own
    ``due_date_actual`` is not touched by that cascade, so when at least one
    task under the phase carries one, it is the more trustworthy signal.
    Falls back to the phase-level actual only when no task has one.
    """

    task_actuals = [t.due_date_actual for t in phase_tasks if t.due_date_actual is not None]
    if task_actuals:
        return max(task_actuals)
    return phase.due_date_actual


def derive_ttv_milestones(
    account_id: str,
    *,
    projects: tuple[OnboardingProject, ...],
    phases: tuple[OnboardingPhase, ...],
    tasks: tuple[OnboardingTask, ...],
) -> list[TimeToValueMilestone]:
    """Adapt Rocketlane phases (+ their tasks) into TimeToValueMilestone evidence.

    One phase -> one milestone. ``expected_by`` <- phase.due_date;
    ``achieved_at`` <- the task-level actual when one exists, else the
    phase's own (see ``_resolve_achieved_at``; None = not yet achieved).
    ``evidence_signal_ids`` always includes the phase id, plus every task id
    under that phase so a proposal can cite concrete task-level evidence.
    Activation-gap tasks (overdue-with-null-actual, or atRisk) do not change
    which milestones are emitted -- their ids simply widen the evidence set,
    per the spec's "evidence_signal_ids carry Rocketlane phase/task ids" rule.
    Fail-closed: a project with no due_date on a phase is skipped (no
    fabricated expected_by), never defaulted to a guessed date.
    """

    project_ids = {p.project_id for p in projects if p.account_id == account_id}
    milestones: list[TimeToValueMilestone] = []
    for phase in phases:
        if phase.project_id not in project_ids:
            continue
        if phase.due_date is None:
            continue
        phase_tasks = tuple(t for t in tasks if t.phase_id == phase.phase_id)
        evidence_ids = (phase.phase_id, *(t.task_id for t in phase_tasks))
        milestones.append(
            TimeToValueMilestone(
                account_id=account_id,
                milestone=phase.name,
                expected_by=phase.due_date,
                achieved_at=_resolve_achieved_at(phase, phase_tasks),
                evidence_signal_ids=evidence_ids,
            )
        )
    return milestones


def onboarding_activation_gap_ids(
    *,
    projects: tuple[OnboardingProject, ...],
    phases: tuple[OnboardingPhase, ...],
    tasks: tuple[OnboardingTask, ...],
    as_of: str,
    covered_milestone_names: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """Phase/task ids carrying activation-gap evidence not already covered
    by a date-based open milestone gap.

    ``has_activation_gap`` (RUNNING_LATE progress, an at-risk task, or an
    overdue phase with no actual) can be true for a phase that the
    date-based ``expected_by <= as_of`` filter does not catch on its own --
    an at-risk task before its own due date is the exact blind spot: no
    signal reaches Agent 1's sweep for an onboarding-stage account whose
    only evidence is delivery slippage. ``covered_milestone_names`` (phase
    names already surfaced as an open gap) excludes double-counting the
    same phase under both paths.
    """

    project_by_id = {p.project_id: p for p in projects}
    ids: list[str] = []
    for phase in phases:
        if phase.name in covered_milestone_names:
            continue
        phase_tasks = tuple(t for t in tasks if t.phase_id == phase.phase_id)
        project = project_by_id.get(phase.project_id)
        if not has_activation_gap(phase, project, phase_tasks, as_of=as_of):
            continue
        ids.append(phase.phase_id)
        ids.extend(t.task_id for t in phase_tasks if t.at_risk)
    return tuple(ids)


def has_activation_gap(
    phase: OnboardingPhase,
    project: OnboardingProject | None,
    tasks: tuple[OnboardingTask, ...],
    *,
    as_of: str,
) -> bool:
    """Activation-gap signal per the spec: RUNNING_LATE progress, an at-risk
    task under the phase, or the phase itself overdue with no actual date.
    """

    if project is not None and project.progress == "running_late":
        return True
    if any(t.at_risk for t in tasks if t.phase_id == phase.phase_id):
        return True
    if phase.due_date is not None and phase.due_date_actual is None:
        if iso_date(phase.due_date) <= iso_date(as_of):
            return True
    return False


class FixtureOnboardingConnector:
    """Pure Rocketlane-backed onboarding fixture. Socket-free, cred-free."""

    def __init__(self, *, data: FixtureOnboardingData | None = None) -> None:
        self._data = data or default_onboarding_fixture_data()

    def list_projects_for_account(self, account_id: str) -> list[OnboardingProject]:
        return [p for p in self._data.projects if p.account_id == account_id]

    def get_project(self, project_id: str) -> OnboardingProject | None:
        return next(
            (p for p in self._data.projects if p.project_id == project_id),
            None,
        )

    def list_phases(self, project_id: str) -> list[OnboardingPhase]:
        return [ph for ph in self._data.phases if ph.project_id == project_id]

    def list_tasks(
        self,
        project_id: str,
        *,
        at_risk_only: bool = False,
        phase_id: str | None = None,
    ) -> list[OnboardingTask]:
        items = [t for t in self._data.tasks if t.project_id == project_id]
        if phase_id is not None:
            items = [t for t in items if t.phase_id == phase_id]
        if at_risk_only:
            items = [t for t in items if t.at_risk]
        return items

    def derive_ttv_milestones(self, account_id: str) -> list[TimeToValueMilestone]:
        return derive_ttv_milestones(
            account_id,
            projects=self._data.projects,
            phases=self._data.phases,
            tasks=self._data.tasks,
        )


# ---------------------------------------------------------------------------
# Adversarial fixture data
# ---------------------------------------------------------------------------
#
# Account ids below are deliberately independent of fixtures.py's CRM/CS
# account ids -- callers wire a Rocketlane account_id to a CRM account_id by
# construction (the "account join" gap the spec flags as an open decision),
# not by a shared fixture constant.

RL_HEALTHY = det_rocketlane_id("account", "rocketlane-healthy")
RL_MISSING_DATES = det_rocketlane_id("account", "rocketlane-missing-dates")
RL_RUNNING_LATE = det_rocketlane_id("account", "rocketlane-running-late")
RL_AT_RISK_TASKS = det_rocketlane_id("account", "rocketlane-at-risk-tasks")
RL_PRIVATE_PHASE = det_rocketlane_id("account", "rocketlane-private-phase")
RL_EMPTY_PROJECT = det_rocketlane_id("account", "rocketlane-empty-project")


def default_onboarding_fixture_data() -> FixtureOnboardingData:
    projects: list[OnboardingProject] = []
    phases: list[OnboardingPhase] = []
    tasks: list[OnboardingTask] = []

    def add_project(
        account_id: str,
        slug: str,
        *,
        progress: str = "on_track",
        due_date: str | None = "2026-07-10",
        due_date_actual: str | None = None,
    ) -> str:
        project_id = det_rocketlane_id("project", slug)
        projects.append(
            OnboardingProject(
                project_id=project_id,
                account_id=account_id,
                name=f"[Fixture] {slug} onboarding",
                status_value=2,
                status_label="In progress",
                owner_id=det_rocketlane_id("user", "csm-owner"),
                progress=progress,  # type: ignore[arg-type]
                start_date="2026-06-01",
                start_date_actual="2026-06-01",
                due_date=due_date,
                due_date_actual=due_date_actual,
                arr_cents=1_000_000,
            )
        )
        return project_id

    def add_phase(
        project_id: str,
        slug: str,
        name: str,
        *,
        due_date: str | None,
        due_date_actual: str | None = None,
        private: bool = False,
    ) -> str:
        phase_id = det_rocketlane_id("phase", slug)
        phases.append(
            OnboardingPhase(
                phase_id=phase_id,
                project_id=project_id,
                name=name,
                start_date="2026-06-01",
                start_date_actual="2026-06-01",
                due_date=due_date,
                due_date_actual=due_date_actual,
                status_label="Completed" if due_date_actual else "In Progress",
                private=private,
            )
        )
        return phase_id

    def add_task(
        project_id: str,
        phase_id: str | None,
        slug: str,
        name: str,
        *,
        due_date: str | None = "2026-06-20",
        due_date_actual: str | None = None,
        at_risk: bool = False,
    ) -> str:
        task_id = det_rocketlane_id("task", slug)
        tasks.append(
            OnboardingTask(
                task_id=task_id,
                project_id=project_id,
                phase_id=phase_id,
                name=name,
                status_label="Completed" if due_date_actual else "In progress",
                start_date="2026-06-01",
                due_date=due_date,
                due_date_actual=due_date_actual,
                at_risk=at_risk,
                assignee_ids=(det_rocketlane_id("user", "csm-owner"),),
            )
        )
        return task_id

    # RL_HEALTHY: on-track project, one completed phase (milestone achieved).
    pid = add_project(RL_HEALTHY, "healthy")
    phid = add_phase(
        pid, "healthy-kickoff", "Kickoff",
        due_date="2026-06-15", due_date_actual="2026-06-14",
    )
    add_task(pid, phid, "healthy-task-1", "Kickoff call", due_date_actual="2026-06-14")

    # RL_MISSING_DATES: adversarial -- a phase with no due_date at all (must
    # be skipped by derive_ttv_milestones, never fabricated).
    pid = add_project(RL_MISSING_DATES, "missing-dates", due_date=None)
    add_phase(pid, "missing-dates-phase", "Undated Phase", due_date=None)

    # RL_RUNNING_LATE: project-level RUNNING_LATE progress signal, phase
    # overdue with no actual -- activation gap via progress AND overdue.
    pid = add_project(RL_RUNNING_LATE, "running-late", progress="running_late")
    phid = add_phase(pid, "running-late-phase", "Implementation", due_date="2026-06-10")
    add_task(pid, phid, "running-late-task", "Data migration", due_date="2026-06-08")

    # RL_AT_RISK_TASKS: phase not yet overdue, but a task under it is
    # explicitly atRisk=true -- activation gap via task risk, not overdue-ness.
    pid = add_project(RL_AT_RISK_TASKS, "at-risk", due_date="2026-12-01")
    phid = add_phase(pid, "at-risk-phase", "Setup", due_date="2026-12-01")
    add_task(pid, phid, "at-risk-task", "Integration setup", due_date="2026-11-01", at_risk=True)
    add_task(pid, phid, "at-risk-task-2", "Non-risk task", due_date="2026-11-01")

    # RL_PRIVATE_PHASE: private phase still contributes a milestone (private
    # is a visibility flag, not an evidence-eligibility flag).
    pid = add_project(RL_PRIVATE_PHASE, "private-phase")
    add_phase(
        pid, "private-internal-review", "Internal Review",
        due_date="2026-07-01", private=True,
    )

    # RL_EMPTY_PROJECT: project exists, zero phases, zero tasks -- must
    # derive zero milestones, not error.
    add_project(RL_EMPTY_PROJECT, "empty-project")

    return FixtureOnboardingData(
        projects=tuple(projects),
        phases=tuple(phases),
        tasks=tuple(tasks),
    )
