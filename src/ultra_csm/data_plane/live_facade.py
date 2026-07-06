"""Live-backed data-plane facade assembly for API/MCP serving.

This module intentionally sits above the proven source connectors. It selects
fixture vs. live mode, adapts read-only Salesforce/Rocketlane/Gmail evidence
into the existing ``CustomerDataPlane`` protocols, and derives health from raw
signals instead of importing a CS-platform score.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
import os
from typing import Any, Mapping
from urllib import parse
from uuid import UUID

from ultra_csm.data_plane.adapters.rocketlane import parse_phase, parse_project, parse_task
from ultra_csm.data_plane.connector_catalog import load_live_creds_file
from ultra_csm.data_plane.contracts import (
    AdoptionSummary,
    CommunicationSignal,
    CRMCase,
    CRMContact,
    CRMDataConnector,
    CSCompany,
    CTA,
    CTAStatus,
    CustomerDataPlane,
    Entitlement,
    HealthScore,
    InternalCommsNote,
    OnboardingPhase,
    OnboardingProject,
    OnboardingTask,
    SuccessPlan,
    TimeToValueMilestone,
    UsageSignal,
)
from ultra_csm.data_plane.fixtures import (
    DEFAULT_TENANT,
    FixtureCRMDataConnector,
    FixtureCommsConnector,
    FixtureCustomerData,
    build_sweep_fixture_data_plane,
    det_id,
)
from ultra_csm.data_plane.live_gmail_reader import live_email_thread
from ultra_csm.data_plane.live_smoke import HttpClient, HttpRequest, UrllibHttpClient
from ultra_csm.data_plane.rocketlane_fixtures import FixtureOnboardingData, derive_ttv_milestones
from ultra_csm.data_plane.explorer import run_explorer
from ultra_csm.data_plane.salesforce_live import DEFAULT_ROW_CAP, fetch_salesforce_book
from ultra_csm.data_plane.source_mapping import freeze_confirmed_source_map, load_mapping_confirmations
from ultra_csm.data_plane.transforms import TransformError

log = logging.getLogger(__name__)

_LIVE_MODE_ENV = "ULTRA_CSM_DATA_PLANE_MODE"
_LIVE_ROW_CAP_ENV = "ULTRA_CSM_LIVE_ROW_CAP"
_GMAIL_THREAD_TAG_ENV = "ULTRA_CSM_GMAIL_THREAD_TAG"
_DEFAULT_AS_OF = "2026-06-27"


class LiveDataPlaneError(RuntimeError):
    """Live mode was explicitly requested but could not be assembled."""


@dataclass(frozen=True)
class DataPlaneAssembly:
    data_plane: CustomerDataPlane
    mode: str
    source_status: dict[str, str]
    health_source: str
    fallback_reason: str | None = None

    @property
    def live(self) -> bool:
        return self.mode == "live"


@dataclass(frozen=True)
class LiveOnboardingData:
    projects: tuple[OnboardingProject, ...] = ()
    phases: tuple[OnboardingPhase, ...] = ()
    tasks: tuple[OnboardingTask, ...] = ()
    status: str = "not_instrumented"


def data_plane_mode(env: Mapping[str, str] | None = None) -> str:
    source = env or os.environ
    return source.get(_LIVE_MODE_ENV, "fixture").strip().lower() or "fixture"


def build_served_data_plane(
    *,
    conn=None,
    comms_tenant_id: str | None = None,
    tenant_id: str = DEFAULT_TENANT,
    as_of: str = _DEFAULT_AS_OF,
    env: Mapping[str, str] | None = None,
    http_client: HttpClient | None = None,
) -> DataPlaneAssembly:
    """Build the data plane served by API/MCP.

    Fixture mode is the default and is used whenever live mode is not explicitly
    requested. Explicit live mode fails closed if Salesforce cannot be read; the
    optional Rocketlane/Gmail sources degrade to honest ``not_instrumented``.
    """

    merged_env = _merged_env(env)
    mode = data_plane_mode(merged_env)
    if mode not in {"fixture", "live"}:
        raise LiveDataPlaneError(f"{_LIVE_MODE_ENV} must be 'fixture' or 'live', got {mode!r}")
    if mode == "fixture":
        return DataPlaneAssembly(
            data_plane=build_sweep_fixture_data_plane(
                tenant_id=tenant_id,
                comms_conn=conn,
                comms_tenant_id=comms_tenant_id,
            ),
            mode="fixture",
            source_status={
                "salesforce": "fixture",
                "rocketlane": "fixture",
                "gmail": "fixture_or_persisted",
            },
            health_source="fixture_cs_platform",
            fallback_reason="live mode not requested",
        )

    _require_salesforce_env(merged_env)
    row_cap = _row_cap(merged_env)
    client = http_client or UrllibHttpClient()
    confirmations = load_mapping_confirmations("eval/salesforce_simulated_confirmations.json")
    discovery = run_explorer(
        "salesforce_crm",
        env=merged_env,
        client=client,
    )
    if not discovery.ok or discovery.mapping_proposal is None:
        raise LiveDataPlaneError(f"Salesforce discovery failed: {discovery.errors}")
    standard_proposal = discovery.mapping_proposal.__class__(
        connector_id=discovery.mapping_proposal.connector_id,
        schema_hash=discovery.mapping_proposal.schema_hash,
        proposal_hash=discovery.mapping_proposal.proposal_hash,
        entries=tuple(
            entry
            for entry in discovery.mapping_proposal.entries
            if entry.contract != "__tenant_custom__"
        ),
        coverage=discovery.mapping_proposal.coverage,
        required_operator_actions=tuple(
            action
            for action in discovery.mapping_proposal.required_operator_actions
            if not action.startswith("__tenant_custom__.")
        ),
    )
    frozen = freeze_confirmed_source_map(
        standard_proposal,
        confirmations=confirmations,
    )
    salesforce = fetch_salesforce_book(
        frozen,
        env=merged_env,
        client=client,
        row_cap=row_cap,
    )
    onboarding_data = _fetch_rocketlane_data(merged_env, client=client, row_cap=row_cap)
    comms_conn = conn if _uuid_account_book(salesforce.data) else None
    return build_live_facade_from_data(
        salesforce_data=salesforce.data,
        onboarding_data=onboarding_data,
        conn=conn,
        comms_tenant_id=comms_tenant_id,
        tenant_id=tenant_id,
        as_of=as_of,
        env=merged_env,
        source_status={
            "salesforce": "live",
            "rocketlane": onboarding_data.status,
            "gmail": _gmail_status(merged_env, conn=comms_conn),
        },
    )


def build_live_facade_from_data(
    *,
    salesforce_data: FixtureCustomerData,
    onboarding_data: LiveOnboardingData | FixtureOnboardingData | None = None,
    conn=None,
    comms_tenant_id: str | None = None,
    tenant_id: str = DEFAULT_TENANT,
    as_of: str = _DEFAULT_AS_OF,
    env: Mapping[str, str] | None = None,
    source_status: dict[str, str] | None = None,
) -> DataPlaneAssembly:
    crm = FixtureCRMDataConnector(tenant=tenant_id, data=salesforce_data)
    onboarding = LiveOnboardingConnector(onboarding_data or LiveOnboardingData())
    comms_conn = conn if _uuid_account_book(salesforce_data) else None
    base_comms = FixtureCommsConnector(data=salesforce_data, conn=comms_conn, tenant_id=comms_tenant_id)
    comms = GmailOverlayCommsConnector(base=base_comms, crm=crm, env=env or {})
    cs = DerivedCSPlatformConnector(crm=crm, onboarding=onboarding, comms=comms, as_of=as_of)
    telemetry = DerivedProductTelemetryConnector(crm=crm, onboarding=onboarding, comms=comms, as_of=as_of)
    return DataPlaneAssembly(
        data_plane=CustomerDataPlane(
            crm=crm,
            cs=cs,
            telemetry=telemetry,
            onboarding=onboarding,
            comms=comms,
        ),
        mode="live",
        source_status=source_status or {
            "salesforce": "live",
            "rocketlane": getattr(onboarding_data, "status", "not_instrumented"),
            "gmail": _gmail_status(env or {}, conn=comms_conn),
        },
        health_source="derived_raw_signals",
    )


class LiveOnboardingConnector:
    def __init__(self, data: LiveOnboardingData | FixtureOnboardingData) -> None:
        self._projects = tuple(data.projects)
        self._phases = tuple(data.phases)
        self._tasks = tuple(data.tasks)

    def list_projects_for_account(self, account_id: str) -> list[OnboardingProject]:
        return [p for p in self._projects if p.account_id == account_id]

    def get_project(self, project_id: str) -> OnboardingProject | None:
        return next((p for p in self._projects if p.project_id == project_id), None)

    def list_phases(self, project_id: str) -> list[OnboardingPhase]:
        return [p for p in self._phases if p.project_id == project_id]

    def list_tasks(
        self,
        project_id: str,
        *,
        at_risk_only: bool = False,
        phase_id: str | None = None,
    ) -> list[OnboardingTask]:
        tasks = [t for t in self._tasks if t.project_id == project_id]
        if phase_id is not None:
            tasks = [t for t in tasks if t.phase_id == phase_id]
        if at_risk_only:
            tasks = [t for t in tasks if t.at_risk]
        return tasks

    def derive_ttv_milestones(self, account_id: str) -> list[TimeToValueMilestone]:
        return derive_ttv_milestones(
            account_id,
            projects=self._projects,
            phases=self._phases,
            tasks=self._tasks,
        )


class DerivedCSPlatformConnector:
    def __init__(
        self,
        *,
        crm: CRMDataConnector,
        onboarding: LiveOnboardingConnector,
        comms: "GmailOverlayCommsConnector",
        as_of: str,
    ) -> None:
        self._crm = crm
        self._onboarding = onboarding
        self._comms = comms
        self._as_of = as_of

    def get_company(self, account_id: str) -> CSCompany | None:
        account = self._crm.get_account(account_id)
        if account is None:
            return None
        projects = self._onboarding.list_projects_for_account(account_id)
        opportunities = self._crm.list_opportunities(account_id)
        arr_cents = max(
            [0]
            + [o.amount_cents for o in opportunities]
            + [p.arr_cents or 0 for p in projects]
        )
        return CSCompany(
            company_id=account.account_id,
            name=account.name,
            industry=account.industry,
            arr_cents=arr_cents,
            lifecycle_stage=_lifecycle_stage(self._crm.list_cases(account_id), opportunities, projects),
            status="derived_from_raw_signals",
            original_contract_date=_earliest_date(
                [p.start_date or p.start_date_actual for p in projects] + [o.close_date for o in opportunities],
                default=self._as_of,
            ),
            renewal_date=_latest_date([o.close_date for o in opportunities], default=self._as_of),
            csm_owner_id=account.owner_id,
            current_score=None,
        )

    def get_health_score(self, account_id: str) -> HealthScore | None:
        if self._crm.get_account(account_id) is None:
            return None
        score = 88.0
        drivers: list[str] = ["crm_state"]
        open_cases = [c for c in self._crm.list_cases(account_id) if _case_is_open(c)]
        for case in open_cases:
            priority = case.priority.lower()
            if priority in {"critical", "urgent", "high"}:
                score -= 20
                drivers.append("crm_high_priority_open_case")
            else:
                score -= 8
                drivers.append("crm_open_case")

        projects = self._onboarding.list_projects_for_account(account_id)
        if not projects:
            drivers.append("rocketlane_not_instrumented")
        for project in projects:
            tasks = self._onboarding.list_tasks(project.project_id)
            if project.progress == "running_late":
                score -= 18
                drivers.append("rocketlane_project_running_late")
            if any(t.at_risk for t in tasks):
                score -= 10
                drivers.append("rocketlane_at_risk_task")
            if any(_task_overdue(t, self._as_of) for t in tasks):
                score -= 8
                drivers.append("rocketlane_overdue_task")

        comms_count = len(self._comms.list_gmail_signals(account_id)) + len(
            self._comms.list_call_transcript_signals(account_id)
        )
        if comms_count == 0:
            drivers.append("comms_not_instrumented")
        score = max(0.0, min(100.0, score))
        return HealthScore(
            account_id=account_id,
            score=score,
            band=_health_band(score),
            drivers=tuple(dict.fromkeys(drivers)),
            measured_at=self._as_of,
        )

    def list_ctas(self, account_id: str, *, status: CTAStatus | None = None) -> list[CTA]:
        ctas: list[CTA] = []
        account = self._crm.get_account(account_id)
        if account is None:
            return ctas
        for case in self._crm.list_cases(account_id):
            if _case_is_open(case) and case.priority.lower() in {"critical", "urgent", "high"}:
                ctas.append(
                    CTA(
                        cta_id=det_id("live-derived-cta", case.case_id),
                        account_id=account_id,
                        reason=f"Open {case.priority} support case: {case.subject}",
                        priority=case.priority,
                        status="open",
                        due_date=self._as_of,
                        owner_id=account.owner_id,
                    )
                )
        for project in self._onboarding.list_projects_for_account(account_id):
            if project.progress == "running_late" or self._onboarding.list_tasks(project.project_id, at_risk_only=True):
                ctas.append(
                    CTA(
                        cta_id=det_id("live-derived-cta", project.project_id),
                        account_id=account_id,
                        reason=f"Rocketlane onboarding risk: {project.name}",
                        priority="High",
                        status="open",
                        due_date=project.due_date or self._as_of,
                        owner_id=project.owner_id or account.owner_id,
                    )
                )
        if status is not None:
            ctas = [c for c in ctas if c.status == status]
        return ctas

    def list_success_plans(self, account_id: str) -> list[SuccessPlan]:
        return [
            SuccessPlan(
                plan_id=det_id("live-derived-plan", project.project_id),
                account_id=account_id,
                status=project.status_label or "rocketlane_project",
                objectives=tuple(
                    phase.name
                    for phase in self._onboarding.list_phases(project.project_id)
                    if not phase.private
                ),
                target_date=project.due_date or self._as_of,
            )
            for project in self._onboarding.list_projects_for_account(account_id)
        ]

    def get_adoption_summary(self, account_id: str) -> AdoptionSummary | None:
        if self._crm.get_account(account_id) is None:
            return None
        tasks = [
            task
            for project in self._onboarding.list_projects_for_account(account_id)
            for task in self._onboarding.list_tasks(project.project_id)
        ]
        completed = sum(1 for task in tasks if task.due_date_actual is not None)
        total = len(tasks)
        underused = []
        if total == 0:
            underused.append("rocketlane_not_instrumented")
        if any(task.at_risk or _task_overdue(task, self._as_of) for task in tasks):
            underused.append("onboarding_activation")
        contacts = self._crm.list_contacts(account_id)
        return AdoptionSummary(
            account_id=account_id,
            active_users=len(contacts),
            licensed_users=max(len(contacts), 1),
            active_assets=completed,
            entitled_assets=max(total, completed),
            adoption_rate=round(completed / total, 4) if total else 0.0,
            underused_capabilities=tuple(dict.fromkeys(underused)),
            measured_at=self._as_of,
        )


class DerivedProductTelemetryConnector:
    def __init__(
        self,
        *,
        crm: CRMDataConnector,
        onboarding: LiveOnboardingConnector,
        comms: "GmailOverlayCommsConnector",
        as_of: str,
    ) -> None:
        self._crm = crm
        self._onboarding = onboarding
        self._comms = comms
        self._as_of = as_of

    def list_entitlements(self, account_id: str) -> list[Entitlement]:
        entitlements: list[Entitlement] = []
        for opportunity in self._crm.list_opportunities(account_id):
            entitlements.append(
                Entitlement(
                    account_id=account_id,
                    capability=_capability_name(opportunity.opportunity_type),
                    entitled_quantity=1,
                    unit="contract",
                    starts_at=opportunity.close_date,
                )
            )
        for project in self._onboarding.list_projects_for_account(account_id):
            entitlements.append(
                Entitlement(
                    account_id=account_id,
                    capability="onboarding_success",
                    entitled_quantity=1,
                    unit="project",
                    starts_at=project.start_date or project.start_date_actual or self._as_of,
                    ends_at=project.due_date_actual,
                )
            )
        return entitlements

    def list_usage_signals(
        self,
        account_id: str,
        *,
        metric_name: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> list[UsageSignal]:
        projects = self._onboarding.list_projects_for_account(account_id)
        tasks = [task for project in projects for task in self._onboarding.list_tasks(project.project_id)]
        completed = sum(1 for task in tasks if task.due_date_actual is not None)
        total = len(tasks)
        signals = [
            UsageSignal(
                signal_id=det_id("live-usage", account_id, "open_cases", self._as_of),
                account_id=account_id,
                grain="company",
                subject_id=None,
                metric_name="open_case_count",
                value=float(sum(1 for case in self._crm.list_cases(account_id) if _case_is_open(case))),
                unit="cases",
                observed_at=self._as_of,
                source_ref="crm",
            ),
            UsageSignal(
                signal_id=det_id("live-usage", account_id, "rocketlane_completion", self._as_of),
                account_id=account_id,
                grain="company",
                subject_id=None,
                metric_name="rocketlane_task_completion_rate",
                value=round(completed / total, 4) if total else 0.0,
                unit="ratio",
                observed_at=self._as_of,
                source_ref="rocketlane" if total else "rocketlane_not_instrumented",
            ),
            UsageSignal(
                signal_id=det_id("live-usage", account_id, "comms_count", self._as_of),
                account_id=account_id,
                grain="company",
                subject_id=None,
                metric_name="customer_comms_count",
                value=float(
                    len(self._comms.list_gmail_signals(account_id))
                    + len(self._comms.list_call_transcript_signals(account_id))
                ),
                unit="signals",
                observed_at=self._as_of,
                source_ref="comms",
            ),
        ]
        if metric_name is not None:
            signals = [s for s in signals if s.metric_name == metric_name]
        if since is not None:
            signals = [s for s in signals if s.observed_at >= since]
        if until is not None:
            signals = [s for s in signals if s.observed_at <= until]
        return signals

    def list_ttv_milestones(self, account_id: str) -> list[TimeToValueMilestone]:
        return self._onboarding.derive_ttv_milestones(account_id)


class GmailOverlayCommsConnector:
    def __init__(
        self,
        *,
        base: FixtureCommsConnector,
        crm: CRMDataConnector,
        env: Mapping[str, str],
    ) -> None:
        self._base = base
        self._crm = crm
        self._tag = env.get(_GMAIL_THREAD_TAG_ENV)

    def list_gmail_signals(self, account_id: str) -> list[CommunicationSignal]:
        signals = list(self._base.list_gmail_signals(account_id))
        if not self._tag:
            return signals
        contact = next((c for c in self._crm.list_contacts(account_id) if "@" in c.email), None)
        if contact is None:
            return signals
        domain = contact.email.split("@", 1)[1].lower()
        try:
            thread = live_email_thread(tag=self._tag, participant_domain=domain)
        except Exception as exc:  # pragma: no cover - live mailbox failure path.
            log.info("Gmail live overlay unavailable", extra={"account_id": account_id, "reason": type(exc).__name__})
            return signals
        return signals + _signals_from_gmail_thread(thread, account_id=account_id, contact=contact)

    def list_call_transcript_signals(self, account_id: str) -> list[CommunicationSignal]:
        return self._base.list_call_transcript_signals(account_id)

    def list_internal_notes(self, account_id: str) -> list[InternalCommsNote]:
        return self._base.list_internal_notes(account_id)


def _fetch_rocketlane_data(
    env: Mapping[str, str],
    *,
    client: HttpClient,
    row_cap: int,
) -> LiveOnboardingData:
    if not env.get("ULTRA_CSM_ROCKETLANE_API_KEY"):
        return LiveOnboardingData(status="not_instrumented")
    base = env.get("ULTRA_CSM_ROCKETLANE_BASE_URL", "https://api.rocketlane.com/api/1.0").rstrip("/")
    headers = {"accept": "application/json", "api-key": env["ULTRA_CSM_ROCKETLANE_API_KEY"]}
    requests = {
        "projects": HttpRequest("GET", f"{base}/projects?pageSize={row_cap}&includeAllFields=true", headers),
        "phases": HttpRequest("GET", f"{base}/phases?pageSize={row_cap}", headers),
        "tasks": HttpRequest("GET", f"{base}/tasks?pageSize={row_cap}&includeAllFields=true", headers),
    }
    errors = 0
    try:
        project_rows = _records_from_response(client.send(requests["projects"]))
    except Exception as exc:
        log.info("Rocketlane projects read unavailable", extra={"reason": type(exc).__name__})
        project_rows = ()
        errors += 1
    try:
        phase_rows = _records_from_response(client.send(requests["phases"]))
    except Exception as exc:
        log.info("Rocketlane phases read unavailable", extra={"reason": type(exc).__name__})
        phase_rows = ()
        errors += 1
    try:
        task_rows = _records_from_response(client.send(requests["tasks"]))
    except Exception as exc:
        log.info("Rocketlane tasks read unavailable", extra={"reason": type(exc).__name__})
        task_rows = ()
        errors += 1
    status = "live" if errors == 0 else "live_partial" if errors < 3 else "error"
    return LiveOnboardingData(
        projects=tuple(_parse_many(project_rows, parse_project)),
        phases=tuple(_parse_many(phase_rows, parse_phase)),
        tasks=tuple(_parse_many(task_rows, parse_task)),
        status=status,
    )


def _merged_env(env: Mapping[str, str] | None) -> dict[str, str]:
    merged = load_live_creds_file()
    merged.update(os.environ)
    if env is not None:
        merged.update(env)
    return {k: v for k, v in merged.items() if isinstance(v, str)}


def _require_salesforce_env(env: Mapping[str, str]) -> None:
    missing = []
    if not env.get("ULTRA_CSM_SALESFORCE_INSTANCE_URL"):
        missing.append("ULTRA_CSM_SALESFORCE_INSTANCE_URL")
    if not env.get("ULTRA_CSM_SALESFORCE_ACCESS_TOKEN"):
        for key in (
            "ULTRA_CSM_SALESFORCE_CLIENT_ID",
            "ULTRA_CSM_SALESFORCE_CLIENT_SECRET",
            "ULTRA_CSM_SALESFORCE_REFRESH_TOKEN",
        ):
            if not env.get(key):
                missing.append(key)
    if missing:
        raise LiveDataPlaneError("missing Salesforce live env names: " + ", ".join(missing))


def _row_cap(env: Mapping[str, str]) -> int:
    raw = env.get(_LIVE_ROW_CAP_ENV)
    if raw is None:
        return DEFAULT_ROW_CAP
    try:
        return max(1, min(int(raw), DEFAULT_ROW_CAP))
    except ValueError:
        return DEFAULT_ROW_CAP


def _records_from_response(response: Any) -> tuple[dict[str, Any], ...]:
    if response.status != 200:
        raise LiveDataPlaneError(f"Rocketlane read returned HTTP {response.status}")
    raw = response.json()
    if isinstance(raw, list):
        records = raw
    elif isinstance(raw, dict):
        records = raw.get("data") or raw.get("results") or raw.get("items") or []
    else:
        records = []
    return tuple(record for record in records if isinstance(record, dict))


def _parse_many(records: tuple[dict[str, Any], ...], parser) -> list[Any]:
    parsed: list[Any] = []
    for record in records:
        try:
            parsed.append(parser(record))
        except TransformError:
            continue
    return parsed


def _gmail_status(env: Mapping[str, str], *, conn=None) -> str:
    if env.get(_GMAIL_THREAD_TAG_ENV):
        return "live_overlay"
    if conn is not None:
        return "persisted_or_not_instrumented"
    if env.get("ULTRA_CSM_GMAIL_SENDER") or env.get("ULTRA_CSM_GMAIL_APP_PASSWORD"):
        return "configured_not_instrumented"
    return "not_instrumented"


def _uuid_account_book(data: FixtureCustomerData) -> bool:
    for account in data.accounts:
        try:
            UUID(account.account_id)
        except ValueError:
            return False
    return True


def _signals_from_gmail_thread(
    thread: Mapping[str, Any],
    *,
    account_id: str,
    contact: CRMContact,
) -> list[CommunicationSignal]:
    messages = thread.get("messages", [])
    if not isinstance(messages, list):
        return []
    signals: list[CommunicationSignal] = []
    previous_outbound_at: datetime | None = None
    contact_domain = contact.email.split("@", 1)[1].lower()
    for message in messages:
        if not isinstance(message, dict):
            continue
        headers = {
            h.get("name"): h.get("value")
            for h in message.get("payload", {}).get("headers", [])
            if isinstance(h, dict)
        }
        timestamp = str(headers.get("Date") or "")
        sender = str(headers.get("From") or "").lower()
        direction = "inbound" if contact_domain in sender else "outbound"
        response_time_hours = None
        observed_at = _parse_iso_datetime(timestamp)
        if direction == "outbound":
            previous_outbound_at = observed_at
        elif previous_outbound_at is not None and observed_at is not None:
            response_time_hours = round((observed_at - previous_outbound_at).total_seconds() / 3600.0, 1)
        signals.append(
            CommunicationSignal(
                signal_id=det_id("live-gmail", account_id, message.get("id", len(signals))),
                account_id=account_id,
                contact_id=contact.contact_id,
                channel="email",
                direction=direction,
                timestamp=timestamp,
                response_time_hours=response_time_hours,
            )
        )
    return signals


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _case_is_open(case: CRMCase) -> bool:
    status = case.status.lower()
    return case.closed_at is None and status not in {"closed", "resolved", "done"}


def _task_overdue(task: OnboardingTask, as_of: str) -> bool:
    return task.due_date is not None and task.due_date_actual is None and task.due_date <= as_of


def _health_band(score: float) -> str:
    if score >= 75:
        return "green"
    if score >= 50:
        return "yellow"
    return "red"


def _lifecycle_stage(
    cases: list[CRMCase],
    opportunities: list[Any],
    projects: list[OnboardingProject],
) -> str:
    if any(_case_is_open(case) and case.priority.lower() in {"critical", "urgent", "high"} for case in cases):
        return "at_risk"
    if projects:
        return "onboarding"
    if any("renew" in (opp.opportunity_type + " " + opp.stage_name).lower() for opp in opportunities):
        return "renewal"
    return "steady_state"


def _earliest_date(values: list[str | None], *, default: str) -> str:
    dates = sorted(v[:10] for v in values if v)
    return dates[0] if dates else default


def _latest_date(values: list[str | None], *, default: str) -> str:
    dates = sorted(v[:10] for v in values if v)
    return dates[-1] if dates else default


def _capability_name(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    return parse.quote(normalized or "contracted_product", safe="_")
