"""Rocketlane raw-shape transforms.

These functions are pure: no sockets, no credentials, no live Rocketlane client. A
live client (MCP or REST) should fetch records and hand raw JSON to these
transforms. Field paths conform to
docs/ROCKETLANE_ONBOARDING_CONNECTOR_SPEC.md's verified API surface and to the
recorded R0 payloads in ~/ultra-csm-corpus-runs/rocketlane-baseline-20260703/.

One verified delta from the spec doc, folded in here: ``OnboardingTask.project_id``
and ``phase_id`` come from nested ``project``/``phase`` objects
(``{"projectId": ..., "projectName": ...}`` / ``{"phaseId": ..., "phaseName": ...}``),
not bare scalar fields — the live payload wins over the spec's field-path shorthand.
"""

from __future__ import annotations

from typing import Any

from ultra_csm.data_plane.contracts import (
    OnboardingPhase,
    OnboardingProject,
    OnboardingTask,
    ProjectProgress,
)
from ultra_csm.data_plane.transforms import (
    TransformError,
    get_path,
    optional_bool,
    optional_int,
    optional_str,
    require_str,
)

_PROGRESS_MAP: dict[str, ProjectProgress] = {
    "ON_TRACK": "on_track",
    "AHEAD_OF_TIME": "ahead",
    "RUNNING_LATE": "running_late",
    "NONE": "none",
}


def parse_progress(value: Any) -> ProjectProgress:
    if value is None:
        return "none"
    if not isinstance(value, str) or value not in _PROGRESS_MAP:
        raise TransformError(f"unrecognized inferredProgress value: {value!r}")
    return _PROGRESS_MAP[value]


def parse_project(record: dict[str, Any]) -> OnboardingProject:
    return OnboardingProject(
        project_id=str(require_str_or_int(record, "projectId")),
        account_id=str(require_str_or_int(record, "customer.companyId")),
        name=require_str(record, "projectName"),
        status_value=optional_int(record, "status.value"),
        status_label=optional_str(record, "status.label"),
        owner_id=_optional_str_or_int(record, "owner.userId"),
        progress=parse_progress(get_path(record, "inferredProgress", default=None)),
        start_date=optional_str(record, "startDate"),
        start_date_actual=optional_str(record, "startDateActual"),
        due_date=optional_str(record, "dueDate"),
        due_date_actual=optional_str(record, "dueDateActual"),
        arr_cents=_optional_arr_cents(record, "annualizedRecurringRevenue"),
    )


def parse_phase(record: dict[str, Any]) -> OnboardingPhase:
    project_id = _optional_str_or_int(record, "project.projectId")
    if project_id is None:
        raise TransformError("missing required field: project.projectId")
    return OnboardingPhase(
        phase_id=str(require_str_or_int(record, "phaseId")),
        project_id=project_id,
        name=require_str(record, "phaseName"),
        start_date=optional_str(record, "startDate"),
        start_date_actual=optional_str(record, "startDateActual"),
        due_date=optional_str(record, "dueDate"),
        due_date_actual=optional_str(record, "dueDateActual"),
        status_label=optional_str(record, "status.label"),
        private=optional_bool(record, "private", default=False),
    )


def parse_task(record: dict[str, Any]) -> OnboardingTask:
    project_id = _optional_str_or_int(record, "project.projectId")
    if project_id is None:
        raise TransformError("missing required field: project.projectId")
    phase_id = _optional_str_or_int(record, "phase.phaseId")
    assignee_ids = tuple(
        str(member["userId"])
        for member in get_path(record, "assignees.members", default=[]) or []
        if isinstance(member, dict) and member.get("userId") is not None
    )
    return OnboardingTask(
        task_id=str(require_str_or_int(record, "taskId")),
        project_id=project_id,
        phase_id=phase_id,
        name=require_str(record, "taskName"),
        status_label=require_str(record, "status.label"),
        start_date=optional_str(record, "startDate"),
        due_date=optional_str(record, "dueDate"),
        due_date_actual=optional_str(record, "dueDateActual"),
        at_risk=optional_bool(record, "atRisk", default=False),
        assignee_ids=assignee_ids,
    )


def require_str_or_int(payload: dict[str, Any], path: str) -> str | int:
    """Rocketlane ids are numeric on the wire; accept int or non-empty string."""

    value = get_path(payload, path)
    if isinstance(value, bool):
        raise TransformError(f"expected id at {path}, got bool")
    if isinstance(value, (str, int)) and value != "":
        return value
    raise TransformError(f"expected id (str or int) at {path}, got {type(value).__name__}")


def _optional_str_or_int(payload: dict[str, Any], path: str) -> str | None:
    value = get_path(payload, path, default=None)
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise TransformError(f"expected id at {path}, got bool")
    if isinstance(value, (str, int)):
        return str(value)
    raise TransformError(f"expected optional id at {path}, got {type(value).__name__}")


def _optional_arr_cents(payload: dict[str, Any], path: str) -> int | None:
    value = get_path(payload, path, default=None)
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise TransformError(f"expected numeric ARR at {path}, got bool")
    if isinstance(value, (int, float)):
        return int(round(value * 100))
    raise TransformError(f"expected optional numeric ARR at {path}, got {type(value).__name__}")
