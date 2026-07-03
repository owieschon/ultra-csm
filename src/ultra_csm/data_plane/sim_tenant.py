"""File-backed simulated tenant for the demo loop.

The sim tenant is intentionally a thin overlay over the deterministic fixture
data. It stores only demo-run mutations under ``demo_state/``: committed CRM
activities, outcome completions, and audit events. The read side still uses the
same CustomerDataPlane protocols as every other connector path.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from ultra_csm.data_plane.contracts import (
    AccountResolution,
    AdoptionSummary,
    CRMAccount,
    CRMActivity,
    CRMCase,
    CRMContact,
    CRMOpportunity,
    CSCompany,
    CTA,
    CTAStatus,
    CustomerDataPlane,
    Entitlement,
    HealthScore,
    SuccessPlan,
    TimeToValueMilestone,
    UsageSignal,
    resolve_candidates,
)
from ultra_csm.data_plane.fixtures import DEFAULT_TENANT, det_id, sweep_fixture_data

STATE_VERSION = 1
DEFAULT_DEMO_STATE_DIR = Path("demo_state")


@dataclass(frozen=True)
class SimTenantState:
    state_version: int
    tenant_id: str
    completions: dict[str, str]
    activities: tuple[CRMActivity, ...]
    audit_events: tuple[dict[str, Any], ...]


class SimTenantStore:
    """Mutable demo-run state, persisted as compact JSON."""

    def __init__(self, state_dir: Path | str = DEFAULT_DEMO_STATE_DIR, *, tenant_id: str = DEFAULT_TENANT) -> None:
        self.state_dir = Path(state_dir)
        self.tenant_id = tenant_id
        self.path = self.state_dir / "tenant_state.json"

    @classmethod
    def seed(
        cls,
        state_dir: Path | str = DEFAULT_DEMO_STATE_DIR,
        *,
        tenant_id: str = DEFAULT_TENANT,
        reset: bool = False,
    ) -> "SimTenantStore":
        store = cls(state_dir, tenant_id=tenant_id)
        store.state_dir.mkdir(parents=True, exist_ok=True)
        if reset or not store.path.exists():
            store._write(SimTenantState(
                state_version=STATE_VERSION,
                tenant_id=tenant_id,
                completions={},
                activities=(),
                audit_events=(),
            ))
        return store

    def data_plane(self) -> CustomerDataPlane:
        return CustomerDataPlane(
            crm=SimCRMDataConnector(self),
            cs=SimCSPlatformConnector(self),
            telemetry=SimProductTelemetryConnector(self),
        )

    def state(self) -> SimTenantState:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return SimTenantState(
            state_version=int(raw["state_version"]),
            tenant_id=str(raw["tenant_id"]),
            completions={str(k): str(v) for k, v in raw.get("completions", {}).items()},
            activities=tuple(CRMActivity(**item) for item in raw.get("activities", ())),
            audit_events=tuple(dict(item) for item in raw.get("audit_events", ())),
        )

    def data(self):
        base = sweep_fixture_data(tenant_id=self.tenant_id)
        completions = self.state().completions
        milestones = tuple(
            replace(milestone, achieved_at=completions[milestone.account_id])
            if milestone.account_id in completions and milestone.achieved_at is None
            else milestone
            for milestone in base.milestones
        )
        success_plans = tuple(
            replace(plan, status="realized")
            if plan.account_id in completions and plan.status != "realized"
            else plan
            for plan in base.success_plans
        )
        return replace(base, milestones=milestones, success_plans=success_plans)

    def record_activity(
        self,
        account_id: str,
        *,
        channel: str,
        direction: str,
        summary: str,
        idempotency_key: str,
        occurred_at: str,
    ) -> str:
        state = self.state()
        for activity in state.activities:
            if activity.idempotency_key == idempotency_key:
                return activity.activity_id
        activity = CRMActivity(
            activity_id=det_id("sim-activity", self.tenant_id, account_id, idempotency_key),
            account_id=account_id,
            channel=channel,
            direction=direction,
            summary=summary,
            occurred_at=occurred_at,
            idempotency_key=idempotency_key,
        )
        self._write(replace(state, activities=(*state.activities, activity)))
        self.append_audit("crm_activity_logged", {
            "account_id": account_id,
            "activity_id": activity.activity_id,
            "idempotency_key": idempotency_key,
        })
        return activity.activity_id

    def advance_after_commits(self, *, as_of: str) -> dict[str, Any]:
        state = self.state()
        account_ids = {
            activity.account_id for activity in state.activities
            if activity.direction == "outbound"
        }
        for item in _read_jsonl(self.state_dir / "outbox.jsonl"):
            account_id = item.get("account_id")
            if isinstance(account_id, str):
                account_ids.add(account_id)

        completed_at = f"{as_of}T00:00:00Z"
        newly_completed = tuple(
            sorted(account_id for account_id in account_ids if account_id not in state.completions)
        )
        if newly_completed:
            completions = dict(state.completions)
            for account_id in newly_completed:
                completions[account_id] = completed_at
            self._write(replace(state, completions=completions))
            self.append_audit("sim_clock_advanced", {
                "as_of": as_of,
                "completed_accounts": newly_completed,
            })
        return {
            "as_of": as_of,
            "completed_accounts": newly_completed,
            "source": "sim",
        }

    def append_audit(self, event_type: str, payload: dict[str, Any]) -> None:
        state = self.state()
        event = {
            "event_type": event_type,
            "payload": payload,
            "source": "sim",
        }
        self._write(replace(state, audit_events=(*state.audit_events, event)))

    def _write(self, state: SimTenantState) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "state_version": state.state_version,
            "tenant_id": state.tenant_id,
            "completions": state.completions,
            "activities": [asdict(item) for item in state.activities],
            "audit_events": list(state.audit_events),
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)


class SimCRMDataConnector:
    def __init__(self, store: SimTenantStore) -> None:
        self._store = store

    def list_accounts(self, *, tenant_id: str | None = None) -> list[CRMAccount]:
        data = self._store.data()
        account_ids = None
        if tenant_id is not None and data.tenant_accounts is not None:
            account_ids = set(data.tenant_accounts.get(tenant_id, ()))
        return [
            account for account in data.accounts
            if account_ids is None or account.account_id in account_ids
        ]

    def resolve_account_by_email(self, email: str) -> AccountResolution:
        if not email:
            return resolve_candidates([])
        account_ids = [
            contact.account_id for contact in self._store.data().contacts
            if contact.email.lower() == email.lower()
        ]
        return resolve_candidates(account_ids)

    def get_account(self, account_id: str) -> CRMAccount | None:
        return next((item for item in self._store.data().accounts if item.account_id == account_id), None)

    def list_contacts(self, account_id: str) -> list[CRMContact]:
        return [item for item in self._store.data().contacts if item.account_id == account_id]

    def list_cases(self, account_id: str) -> list[CRMCase]:
        return [item for item in self._store.data().cases if item.account_id == account_id]

    def list_opportunities(self, account_id: str) -> list[CRMOpportunity]:
        return [item for item in self._store.data().opportunities if item.account_id == account_id]

    def log_activity(
        self,
        account_id: str,
        *,
        channel: str,
        direction: str,
        summary: str,
        idempotency_key: str,
    ) -> str:
        return self._store.record_activity(
            account_id,
            channel=channel,
            direction=direction,
            summary=summary,
            idempotency_key=idempotency_key,
            occurred_at="2026-06-28T12:00:00Z",
        )


class SimCSPlatformConnector:
    def __init__(self, store: SimTenantStore) -> None:
        self._store = store

    def get_company(self, account_id: str) -> CSCompany | None:
        return next((item for item in self._store.data().companies if item.company_id == account_id), None)

    def get_health_score(self, account_id: str) -> HealthScore | None:
        return next((item for item in self._store.data().health_scores if item.account_id == account_id), None)

    def list_ctas(self, account_id: str, *, status: CTAStatus | None = None) -> list[CTA]:
        items = [item for item in self._store.data().ctas if item.account_id == account_id]
        if status is not None:
            items = [item for item in items if item.status == status]
        return items

    def list_success_plans(self, account_id: str) -> list[SuccessPlan]:
        return [item for item in self._store.data().success_plans if item.account_id == account_id]

    def get_adoption_summary(self, account_id: str) -> AdoptionSummary | None:
        return next(
            (item for item in self._store.data().adoption_summaries if item.account_id == account_id),
            None,
        )


class SimProductTelemetryConnector:
    def __init__(self, store: SimTenantStore) -> None:
        self._store = store

    def list_entitlements(self, account_id: str) -> list[Entitlement]:
        return [item for item in self._store.data().entitlements if item.account_id == account_id]

    def list_usage_signals(
        self,
        account_id: str,
        *,
        metric_name: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> list[UsageSignal]:
        signals = [
            item for item in self._store.data().usage_signals
            if item.account_id == account_id
        ]
        if metric_name is not None:
            signals = [item for item in signals if item.metric_name == metric_name]
        if since is not None:
            signals = [item for item in signals if item.observed_at >= since]
        if until is not None:
            signals = [item for item in signals if item.observed_at <= until]
        return signals

    def list_ttv_milestones(self, account_id: str) -> list[TimeToValueMilestone]:
        return [item for item in self._store.data().milestones if item.account_id == account_id]


def _read_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    if not path.exists():
        return ()
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return tuple(rows)
