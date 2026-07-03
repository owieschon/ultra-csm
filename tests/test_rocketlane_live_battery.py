"""R4: live battery over Program 4's seeded Rocketlane datasets.

Payloads below are recorded from live get_phases/get_tasks calls
(2026-07-03, via the mcp__rocketlane__* MCP lane) against phases/tasks
created this program in the two existing factory projects (see
docs/PROGRAM_REPORT_4.md and
~/ultra-csm-corpus-runs/rocketlane-seed-20260703/ for the full ledger and
ground truth). Assertions are exact numbers against
ground_truth.json -- not tolerances.

Two live findings, folded into these payloads (never faked before
observation -- ground_truth.json was authored first, then corrected after
seeding to match what the API actually returned):

  1. Completing a phase's only/last open task auto-completes the phase and
     sets startDateActual/dueDateActual to the write date (server "now"),
     not any caller-supplied value (D1, D4).
  2. Creating a task under a phase recalculates the phase's dueDate to the
     task's dueDate, overriding whatever dueDate was passed to create_phase
     (D2, D3).

Neither finding required a product code change -- derive_ttv_milestones
correctly reads whatever the API returns, whatever its provenance.
"""

from __future__ import annotations

import pytest

from ultra_csm.data_plane.adapters.rocketlane import parse_phase, parse_task
from ultra_csm.data_plane.contracts import OnboardingProject
from ultra_csm.data_plane.rocketlane_fixtures import derive_ttv_milestones, has_activation_gap

AS_OF = "2026-07-03"

_PAYLOADS = {
    "phases": {
        "D1_healthy": {
            "phaseId": 5000000385259, "phaseName": "UCSM-P4C-D1 Healthy Onboarding Review",
            "project": {"projectId": 5000000116921, "projectName": "[Sample] Acme 2 week onboarding"},
            "startDate": "2026-07-01", "dueDate": "2026-07-03",
            "startDateActual": "2026-07-03", "dueDateActual": "2026-07-03",
            "status": {"value": 3, "label": "Completed"}, "private": False,
        },
        "D2_slipping": {
            "phaseId": 5000000385260, "phaseName": "UCSM-P4C-D2 Slipping Data Migration",
            "project": {"projectId": 5000000116922, "projectName": "[Sample] Modert 5 week onboarding"},
            "startDate": "2026-06-01", "dueDate": "2026-06-20",
            "status": {"value": 1, "label": "To do"}, "private": False,
        },
        "D3_at_risk_cluster": {
            "phaseId": 5000000385261, "phaseName": "UCSM-P4C-D3 At-Risk Integration Cluster",
            "project": {"projectId": 5000000116921, "projectName": "[Sample] Acme 2 week onboarding"},
            "startDate": "2026-07-01", "dueDate": "2026-08-01",
            "status": {"value": 1, "label": "To do"}, "private": False,
        },
        "D4_completed": {
            "phaseId": 5000000385262, "phaseName": "UCSM-P4C-D4 Completed Requirements Signoff",
            "project": {"projectId": 5000000116922, "projectName": "[Sample] Modert 5 week onboarding"},
            "startDate": "2026-06-01", "dueDate": "2026-06-14",
            "startDateActual": "2026-07-03", "dueDateActual": "2026-07-03",
            "status": {"value": 3, "label": "Completed"}, "private": False,
        },
        "D5_sparse": {
            "phaseId": 5000000385269, "phaseName": "UCSM-P4C-D5 Sparse Minimal Phase",
            "project": {"projectId": 5000000116921, "projectName": "[Sample] Acme 2 week onboarding"},
            "startDate": "2026-07-10", "dueDate": "2026-07-11",
            "status": {"value": 1, "label": "To do"}, "private": False,
        },
    },
    "tasks": {
        "D1_healthy": [{
            "taskId": 5000002982468, "taskName": "UCSM-P4C-D1-T1 Kickoff readiness check",
            "startDate": "2026-07-01", "dueDate": "2026-07-03",
            "project": {"projectId": 5000000116921, "projectName": "[Sample] Acme 2 week onboarding"},
            "status": {"value": 3, "label": "Completed"},
            "startDateActual": "2026-07-03", "dueDateActual": "2026-07-03",
            "phase": {"phaseId": 5000000385259, "phaseName": "UCSM-P4C-D1 Healthy Onboarding Review"},
            "assignees": {},
        }],
        "D2_slipping": [{
            "taskId": 5000002982469, "taskName": "UCSM-P4C-D2-T1 Legacy export overdue",
            "startDate": "2026-06-01", "dueDate": "2026-06-20",
            "project": {"projectId": 5000000116922, "projectName": "[Sample] Modert 5 week onboarding"},
            "status": {"value": 1, "label": "To do"},
            "phase": {"phaseId": 5000000385260, "phaseName": "UCSM-P4C-D2 Slipping Data Migration"},
            "assignees": {},
        }],
        "D3_at_risk_cluster": [
            {
                "taskId": 5000002982470, "taskName": "UCSM-P4C-D3-T1 API credential exchange",
                "startDate": "2026-07-01", "dueDate": "2026-07-15", "atRisk": True,
                "project": {"projectId": 5000000116921, "projectName": "[Sample] Acme 2 week onboarding"},
                "status": {"value": 1, "label": "To do"},
                "phase": {"phaseId": 5000000385261, "phaseName": "UCSM-P4C-D3 At-Risk Integration Cluster"},
                "assignees": {},
            },
            {
                "taskId": 5000002982471, "taskName": "UCSM-P4C-D3-T2 Data mapping validation",
                "startDate": "2026-07-05", "dueDate": "2026-07-20", "atRisk": True,
                "project": {"projectId": 5000000116921, "projectName": "[Sample] Acme 2 week onboarding"},
                "status": {"value": 1, "label": "To do"},
                "phase": {"phaseId": 5000000385261, "phaseName": "UCSM-P4C-D3 At-Risk Integration Cluster"},
                "assignees": {},
            },
            {
                "taskId": 5000002982472, "taskName": "UCSM-P4C-D3-T3 Non-risk documentation task",
                "startDate": "2026-07-01", "dueDate": "2026-08-01",
                "project": {"projectId": 5000000116921, "projectName": "[Sample] Acme 2 week onboarding"},
                "status": {"value": 1, "label": "To do"},
                "phase": {"phaseId": 5000000385261, "phaseName": "UCSM-P4C-D3 At-Risk Integration Cluster"},
                "assignees": {},
            },
        ],
        "D4_completed": [{
            "taskId": 5000002982473, "taskName": "UCSM-P4C-D4-T1 Requirements signoff call",
            "startDate": "2026-06-01", "dueDate": "2026-06-14",
            "project": {"projectId": 5000000116922, "projectName": "[Sample] Modert 5 week onboarding"},
            "status": {"value": 3, "label": "Completed"},
            "startDateActual": "2026-07-03", "dueDateActual": "2026-07-03",
            "phase": {"phaseId": 5000000385262, "phaseName": "UCSM-P4C-D4 Completed Requirements Signoff"},
            "assignees": {},
        }],
        "D5_sparse": [{
            "taskId": 5000002982525, "taskName": "UCSM-P4C-D5-T1 Minimal task",
            "project": {"projectId": 5000000116921, "projectName": "[Sample] Acme 2 week onboarding"},
            "status": {"value": 1, "label": "To do"},
            "phase": {"phaseId": 5000000385269, "phaseName": "UCSM-P4C-D5 Sparse Minimal Phase"},
            "assignees": {},
        }],
    },
}

_EXPECTED = {
    "D1_healthy": {
        "milestone_count": 1, "achieved_count": 1, "open_gap_count": 0,
        "at_risk_task_count": 0, "activation_gap_flag": False,
    },
    "D2_slipping": {
        "milestone_count": 1, "achieved_count": 0, "open_gap_count": 1,
        "at_risk_task_count": 0, "activation_gap_flag": True,
    },
    "D3_at_risk_cluster": {
        "milestone_count": 1, "achieved_count": 0, "open_gap_count": 0,
        "at_risk_task_count": 2, "activation_gap_flag": True,
    },
    "D4_completed": {
        "milestone_count": 1, "achieved_count": 1, "open_gap_count": 0,
        "at_risk_task_count": 0, "activation_gap_flag": False,
    },
    "D5_sparse": {
        "milestone_count": 1, "achieved_count": 0, "open_gap_count": 0,
        "at_risk_task_count": 0, "activation_gap_flag": False,
    },
}


def _derive(dataset: str):
    phase = parse_phase(_PAYLOADS["phases"][dataset])
    tasks = tuple(parse_task(t) for t in _PAYLOADS["tasks"][dataset])
    account_id = f"acct-{dataset}"
    project = OnboardingProject(
        project_id=phase.project_id,
        account_id=account_id,
        name="n/a",
        status_value=None,
        status_label=None,
        owner_id=None,
        progress="none",
        start_date=None,
        start_date_actual=None,
        due_date=None,
        due_date_actual=None,
        arr_cents=None,
    )
    milestones = derive_ttv_milestones(
        account_id, projects=(project,), phases=(phase,), tasks=tasks
    )
    return phase, project, tasks, milestones


@pytest.mark.parametrize("dataset", sorted(_EXPECTED))
def test_live_dataset_matches_exact_ground_truth(dataset):
    phase, project, tasks, milestones = _derive(dataset)
    exp = _EXPECTED[dataset]

    achieved = [m for m in milestones if m.achieved_at is not None]
    open_gaps = [m for m in milestones if m.achieved_at is None and m.expected_by <= AS_OF]
    at_risk_tasks = [t for t in tasks if t.at_risk]
    gap_flag = has_activation_gap(phase, project, tasks, as_of=AS_OF)

    assert len(milestones) == exp["milestone_count"]
    assert len(achieved) == exp["achieved_count"]
    assert len(open_gaps) == exp["open_gap_count"]
    assert len(at_risk_tasks) == exp["at_risk_task_count"]
    assert gap_flag == exp["activation_gap_flag"]

    if milestones:
        # Evidence ids must cite the real phase id (and, when tasks exist
        # under the phase, real task ids too) -- never a fabricated id.
        assert phase.phase_id in milestones[0].evidence_signal_ids
        real_task_ids = {t.task_id for t in tasks}
        cited_task_ids = set(milestones[0].evidence_signal_ids) - {phase.phase_id}
        assert cited_task_ids <= real_task_ids


def test_d1_and_d4_auto_completion_live_finding_is_captured_honestly():
    """Both D1 and D4 were authored as create_phase(dueDate=<planned future
    date>) + a task marked Completed -- but Rocketlane auto-completed the
    phase and overwrote dueDateActual to the write date, not any date this
    program specified. This locks in that real behavior rather than a
    fabricated one."""
    d1_phase = parse_phase(_PAYLOADS["phases"]["D1_healthy"])
    d4_phase = parse_phase(_PAYLOADS["phases"]["D4_completed"])
    assert d1_phase.due_date_actual == "2026-07-03"
    assert d4_phase.due_date_actual == "2026-07-03"
    # D1's authored plan was a 2026-07-20 due date; D4's was 2026-06-15.
    # Both were overwritten to the task's dueDate by the recalculation
    # finding below, then further overwritten to the completion date once
    # the sole task completed.
    assert d1_phase.due_date == "2026-07-03"
    assert d4_phase.due_date == "2026-06-14"


def test_d2_and_d3_phase_due_date_recalculation_live_finding_is_captured_honestly():
    """D2 was authored with create_phase(dueDate="2026-06-25") but the live
    phase came back with dueDate="2026-06-20" (the task's dueDate). D3 was
    authored with dueDate="2026-09-01" but came back "2026-08-01" (the
    latest task's dueDate). Creating a task under a phase recalculates the
    phase's dueDate; this test locks in the observed values, not the
    originally-planned ones."""
    d2_phase = parse_phase(_PAYLOADS["phases"]["D2_slipping"])
    d3_phase = parse_phase(_PAYLOADS["phases"]["D3_at_risk_cluster"])
    assert d2_phase.due_date == "2026-06-20"
    assert d3_phase.due_date == "2026-08-01"
