"""Ultra CSM integration contracts.

This module defines the customer-success data plane before any agent logic is
written. The boundary is intentionally integration-first:

* Salesforce-backed CRM context: account, contact, case, opportunity, activity.
* Gainsight-backed CS context: company, health score, CTA, success plan,
  adoption summary.
* Product telemetry: entitlements and usage signals from the product/telemetry
  system, which a CS platform may also ingest or summarize.

The contracts are read-mostly and tenant-scoped at construction. Writes are kept
explicit and idempotent so a future agent can place them behind the existing action
gate instead of smuggling authority through a connector.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


ResolutionState = Literal["exactly_one", "ambiguous", "none"]
LifecycleStage = Literal["onboarding", "adopting", "steady_state", "renewal", "at_risk"]
CTAStatus = Literal["open", "in_progress", "closed"]
HealthBand = Literal["green", "yellow", "red", "unknown"]
SignalGrain = Literal["company", "person", "asset"]
EvidenceSource = Literal["rocketlane", "telemetry", "cs_platform", "crm"]
ProjectProgress = Literal["on_track", "ahead", "running_late", "none"]


@dataclass(frozen=True)
class EvidenceRef:
    """Pointer to one grounded fact in a source fixture or connector payload."""

    source: EvidenceSource
    source_id: str
    field: str
    observed_at: str


@dataclass(frozen=True)
class AccountResolution:
    """0/1/many identity resolution. Ambiguous results never auto-pick."""

    state: ResolutionState
    account_id: str | None
    candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class CRMAccount:
    """Salesforce Account customer context."""

    account_id: str
    name: str
    owner_id: str
    industry: str | None


@dataclass(frozen=True)
class CRMContact:
    """Salesforce Contact person context."""

    contact_id: str
    account_id: str
    email: str
    name: str
    role: str | None
    title: str | None
    consent_to_contact: bool
    # Optional org-chart hierarchy position
    # (1=C-suite, 2=VP, 3=Director, 4=Manager, 5=IC).
    org_level: int | None = None


@dataclass(frozen=True)
class CRMCase:
    """Salesforce Case support context."""

    case_id: str
    account_id: str
    status: str
    priority: str
    origin: str
    subject: str
    created_at: str
    closed_at: str | None = None


@dataclass(frozen=True)
class CRMOpportunity:
    """Salesforce Opportunity revenue context."""

    opportunity_id: str
    account_id: str
    stage_name: str
    amount_cents: int
    close_date: str
    opportunity_type: str


@dataclass(frozen=True)
class CRMActivity:
    """CRM activity/timeline write-back shape."""

    activity_id: str
    account_id: str
    channel: str
    direction: str
    summary: str
    occurred_at: str
    idempotency_key: str


@dataclass(frozen=True)
class CSCompany:
    """Gainsight Company customer-success account context."""

    company_id: str
    name: str
    industry: str | None
    arr_cents: int
    lifecycle_stage: LifecycleStage
    status: str
    original_contract_date: str
    renewal_date: str
    csm_owner_id: str
    current_score: float | None


@dataclass(frozen=True)
class HealthScore:
    """Gainsight scorecard output."""

    account_id: str
    score: float
    band: HealthBand
    drivers: tuple[str, ...]
    measured_at: str


@dataclass(frozen=True)
class CTA:
    """Gainsight CTA work item."""

    cta_id: str
    account_id: str
    reason: str
    priority: str
    status: CTAStatus
    due_date: str
    owner_id: str


@dataclass(frozen=True)
class SuccessPlan:
    """Gainsight success-plan outcome plan."""

    plan_id: str
    account_id: str
    status: str
    objectives: tuple[str, ...]
    target_date: str


@dataclass(frozen=True)
class AdoptionSummary:
    """CS-platform adoption rollup, often derived from product usage data."""

    account_id: str
    active_users: int
    licensed_users: int
    active_assets: int
    entitled_assets: int
    adoption_rate: float
    underused_capabilities: tuple[str, ...]
    measured_at: str


@dataclass(frozen=True)
class Entitlement:
    """What the account is entitled to use."""

    account_id: str
    capability: str
    entitled_quantity: int
    unit: str
    starts_at: str
    ends_at: str | None = None


@dataclass(frozen=True)
class UsageSignal:
    """A product-telemetry observation at company/person/asset grain."""

    signal_id: str
    account_id: str
    grain: SignalGrain
    subject_id: str | None
    metric_name: str
    value: float
    unit: str
    observed_at: str
    source_ref: str


@dataclass(frozen=True)
class TimeToValueMilestone:
    """Activation milestone expected during onboarding/adoption."""

    account_id: str
    milestone: str
    expected_by: str
    achieved_at: str | None
    evidence_signal_ids: tuple[str, ...]


# ---------------------------------------------------------------------------
# Extended contract types — reserved for live connector integration.
# Simulation deferred; these types define the schema for future data sources
# that the value model and agent lenses will consume.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommunicationSignal:
    """A single communication event between CSM and customer contact.

    Reserved for live connector integration — simulation deferred.

    ``channel`` additively widened to include ``"chat"`` (Universe v2,
    WS-Tenant-Loopway, Wave 3) for Loopway's Intercom-ish in-app support
    chat class — sanctioned by ``docs/UNIVERSE_V2_CONVENTIONS.md`` §7
    ("frozen contracts stay frozen unless explicitly sanctioned here");
    no existing consumer (``signal_extractor.py``, any tenant's
    ``*_comms.py`` module) exhaustively switches over this field's value,
    so the widening is purely additive. See
    ``docs/TENANT_LOOPWAY_BIBLE.md``'s "Chat class" section.
    """

    signal_id: str
    account_id: str
    contact_id: str
    channel: Literal["email", "call", "meeting", "chat"]
    direction: Literal["inbound", "outbound"]
    timestamp: str
    response_time_hours: float | None = None  # for email
    attendees: tuple[str, ...] = ()  # for meetings


@dataclass(frozen=True)
class AccountAttributionCandidate:
    """A proposed (not yet confirmed) account attribution for one piece of
    identity-ambiguous external evidence -- shared shape for connectors that
    must propose rather than assume which account a record belongs to
    (Notion call transcripts by meeting title/transcript text, Slack
    channels by channel name). Mirrors source_mapping.py's propose-then-
    confirm discipline without reusing its field-mapping-specific
    dataclasses -- this is record-level identity attribution, a different
    problem from source_mapping's field-level schema mapping."""

    account_id: str
    confidence: float
    reason: str
    signal: Literal["title_match", "transcript_text_match", "channel_name_match"]


@dataclass(frozen=True)
class InternalCommsNote:
    """Internal commentary on an account -- never customer-facing.

    Distinct from ``CommunicationSignal`` rather than a widened variant of
    it: an internal note has no customer ``contact_id`` (it's CSM-to-CSM
    commentary, not a conversation with the customer), so forcing it into
    the customer-conversation shape would require a fake contact reference.
    ``source`` distinguishes a CSM-authored note (native, Postgres-backed)
    from one pulled from a connected Slack channel.
    """

    note_id: str
    account_id: str
    author: str
    timestamp: str
    content: str
    source: Literal["csm_note", "slack"]


@dataclass(frozen=True)
class StakeholderRelationship:
    """Relationship graph node between account and a contact.

    Reserved for live connector integration — simulation deferred.
    """

    account_id: str
    contact_id: str
    relationship_type: Literal[
        "champion", "executive_sponsor", "technical_lead", "end_user", "admin"
    ]
    strength: Literal["strong", "moderate", "weak"]
    last_interaction: str
    multi_thread_depth: int
    # Optional relationship graph edge: who knows whom, or who introduced whom.
    related_contact_id: str | None = None


JobChangeType = Literal["departure", "promotion", "lateral_move"]


@dataclass(frozen=True)
class JobChangeSignal:
    """An enrichment-feed event reporting a contact's job change.

    Moved here from ``data_plane/relationship_signals.py`` (architecture
    cleanup, report 42): ``value_model.py`` (the deterministic core) consumes
    this type directly (``_champion_departed_factor``, wired via Harvest 16's
    person layer), so it belongs in the dependency-free contracts module
    alongside its sibling person-record type ``StakeholderRelationship``,
    not in a module that also pulls in fixture/bible content
    (``data_plane.fixtures``, tenant ``*_comms`` modules). This dataclass
    itself carries no fixture dependency; ``relationship_signals.py`` still
    owns the actual fixture rows (``DEREK_VAUGHN_DEPARTURE`` etc.) and
    imports this type back from here.
    """

    signal_id: str
    account_id: str
    contact_id: str
    contact_name: str
    change_type: JobChangeType
    day_offset: int
    observed_at: str
    old_title: str
    new_title: str | None  # None for a departure (no successor title to report)
    same_company: bool
    detail: str


@dataclass(frozen=True)
class SurveyResponse:
    """A survey response (NPS, CSAT, or custom) from a contact.

    Reserved for live connector integration — simulation deferred.
    """

    survey_id: str
    account_id: str
    contact_id: str
    survey_type: Literal["NPS", "CSAT", "custom"]
    score: float
    comment: str | None
    timestamp: str


@dataclass(frozen=True)
class BillingEvent:
    """A billing-related event for an account.

    Reserved for live connector integration — simulation deferred.
    """

    event_id: str
    account_id: str
    event_type: Literal["invoice", "payment", "failure", "consumption_alert"]
    amount_cents: int
    timestamp: str
    details: str | None = None


@dataclass(frozen=True)
class OnboardingProject:
    """Rocketlane Project — onboarding/PSA engagement for one account.

    ``account_id`` is the join key back to the CRM/CS account (Rocketlane
    ``customer.companyId``); see the open "Account join" gap in
    docs/ROCKETLANE_ONBOARDING_CONNECTOR_SPEC.md.
    """

    project_id: str
    account_id: str
    name: str
    status_value: int | None
    status_label: str | None
    owner_id: str | None
    progress: ProjectProgress
    start_date: str | None
    start_date_actual: str | None
    due_date: str | None
    due_date_actual: str | None
    arr_cents: int | None


@dataclass(frozen=True)
class OnboardingPhase:
    """Rocketlane Phase — a milestone stage within an onboarding project."""

    phase_id: str
    project_id: str
    name: str
    start_date: str | None
    start_date_actual: str | None
    due_date: str | None
    due_date_actual: str | None
    status_label: str | None
    private: bool


@dataclass(frozen=True)
class OnboardingTask:
    """Rocketlane Task — a unit of work within an onboarding project/phase."""

    task_id: str
    project_id: str
    phase_id: str | None
    name: str
    status_label: str
    start_date: str | None
    due_date: str | None
    due_date_actual: str | None  # populated == completed
    at_risk: bool
    assignee_ids: tuple[str, ...]


def resolve_candidates(account_ids: list[str]) -> AccountResolution:
    ids = tuple(sorted(set(account_ids)))
    if len(ids) == 1:
        return AccountResolution("exactly_one", ids[0], ())
    if len(ids) > 1:
        return AccountResolution("ambiguous", None, ids)
    return AccountResolution("none", None, ())


class CRMDataConnector(Protocol):
    """Salesforce-backed CRM seam. Tenant-bound and fail-closed by implementation."""

    def list_accounts(self, *, tenant_id: str | None = None) -> list[CRMAccount]: ...

    def resolve_account_by_email(self, email: str) -> AccountResolution: ...

    def get_account(self, account_id: str) -> CRMAccount | None: ...

    def list_contacts(self, account_id: str) -> list[CRMContact]: ...

    def list_cases(self, account_id: str) -> list[CRMCase]: ...

    def list_opportunities(self, account_id: str) -> list[CRMOpportunity]: ...

    def log_activity(
        self,
        account_id: str,
        *,
        channel: str,
        direction: str,
        summary: str,
        idempotency_key: str,
    ) -> str: ...


class CSPlatformConnector(Protocol):
    """Gainsight-backed customer-success seam."""

    def get_company(self, account_id: str) -> CSCompany | None: ...

    def get_health_score(self, account_id: str) -> HealthScore | None: ...

    def list_ctas(self, account_id: str, *, status: CTAStatus | None = None) -> list[CTA]: ...

    def list_success_plans(self, account_id: str) -> list[SuccessPlan]: ...

    def get_adoption_summary(self, account_id: str) -> AdoptionSummary | None: ...


class ProductTelemetryConnector(Protocol):
    """Product telemetry seam; independent from CRM and CS-platform summaries."""

    def list_entitlements(self, account_id: str) -> list[Entitlement]: ...

    def list_usage_signals(
        self,
        account_id: str,
        *,
        metric_name: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> list[UsageSignal]: ...

    def list_ttv_milestones(self, account_id: str) -> list[TimeToValueMilestone]: ...


class OnboardingConnector(Protocol):
    """Rocketlane-backed onboarding/PSA seam. Tenant-bound, fail-closed, read-mostly.

    Optional: a tenant with no onboarding source configured has no
    ``OnboardingConnector`` at all (``CustomerDataPlane.onboarding is None``),
    and the outcome/TTV rail degrades honestly rather than fabricating
    milestones. See docs/ROCKETLANE_ONBOARDING_CONNECTOR_SPEC.md.
    """

    def list_projects_for_account(self, account_id: str) -> list[OnboardingProject]: ...

    def get_project(self, project_id: str) -> OnboardingProject | None: ...

    def list_phases(self, project_id: str) -> list[OnboardingPhase]: ...

    def list_tasks(
        self, project_id: str, *, at_risk_only: bool = False, phase_id: str | None = None
    ) -> list[OnboardingTask]: ...

    def derive_ttv_milestones(self, account_id: str) -> list[TimeToValueMilestone]: ...


class CommsConnector(Protocol):
    """Comms evidence seam: customer-facing (Gmail, Notion call transcripts)
    and internal account commentary. Optional, same discipline as
    OnboardingConnector: an account with no comms source configured has no
    CommsConnector at all (``CustomerDataPlane.comms is None``), and the
    Comms UI degrades honestly to empty lists rather than fabricating rows
    (matches the drawer's existing dormant-until-real-data precedent in
    ``ui/components/QueueDetail.tsx``)."""

    def list_gmail_signals(self, account_id: str) -> list[CommunicationSignal]: ...

    def list_call_transcript_signals(self, account_id: str) -> list[CommunicationSignal]: ...

    def list_internal_notes(self, account_id: str) -> list[InternalCommsNote]: ...


@dataclass(frozen=True)
class CustomerDataPlane:
    """The integration seams an Ultra CSM agent consumes."""

    crm: CRMDataConnector
    cs: CSPlatformConnector
    telemetry: ProductTelemetryConnector
    onboarding: OnboardingConnector | None = None
    comms: CommsConnector | None = None
