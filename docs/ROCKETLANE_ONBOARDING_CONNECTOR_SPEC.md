# Rocketlane Onboarding Connector — Spec

Status: integration spec, grounded in Rocketlane public developer documentation.
Date: 2026-06-27.

## Ground Rules

`Verified` = traceable to a cited Rocketlane doc page fetched while writing this
spec. `Planned` = proposed contract/field that must be confirmed against a live
payload or a not-yet-fetched reference page before it is treated as vendor-backed.
Vendor-backed fields map to a documented object; derived/internal fields are marked
non-standard. Fixtures are synthetic substrate, not customer data. Writes stay behind
the action gate.

## Why this connector exists (positioning)

Rocketlane is a customer-onboarding / professional-services-automation (PSA) system
of record: projects, phases, tasks, time. **Rocketlane does not ship its own agents**
— its AI connects an LLM to Rocketlane data; the orchestration/judgment/guardrail
layer is the customer's to build. So a Rocketlane-backed agent is *not* redundant with
the vendor, **provided** Rocketlane is consumed as a **source feeding the existing
cross-system Agent 1**, never as a standalone single-source "Rocketlane agent" (that
*would* duplicate what the platform already does).

Strategic fit: Rocketlane's domain is onboarding and time-to-value: planned versus
actual dates, phase progress, and at-risk tasks. That makes it a useful optional
onboarding source for the **Time-to-Value Accelerator (Agent 1)**. It does not
replace the Salesforce-shaped CRM seam, the Gainsight-shaped CS seam, or product
telemetry; it proves the data plane can accept another source behind the same
governed internal agent loop.

## Approach (conform, do not re-solve)

- Add **one** new seam, `OnboardingConnector`, in `src/ultra_csm/data_plane/`,
  mirroring the existing `CRMDataConnector` / `CSPlatformConnector` /
  `ProductTelemetryConnector` Protocol+frozen-dataclass+source-map+fixture pattern.
- It is **read-mostly**. The only write candidates (create follow-up task, post a
  project update) are deferred and, when added, emit an action-gate proposal — never a
  direct mutation through the connector.
- The scored/offline eval path uses a **fixture** `OnboardingConnector` (socket-free,
  cred-free). The live adapter is `[onboarding]`-extra + credentials only.
- Deliberately **not** replacing `ProductTelemetryConnector`. They are complementary:
  Rocketlane = *delivery/onboarding execution* signal (phase slippage, at-risk tasks);
  product telemetry = *product usage* signal. They meet at the TTV-milestone bridge.
- Deliberately **not** adding a new agent or new scorecard pillar. This connector feeds
  Agent 1's existing `TimeToValueMilestone` evidence.

## Verified API surface

- REST base URL: `https://api.rocketlane.com/api/1.0`. [overview, authentication]
- Auth (REST): `api-key` header (`api-key: <key>`), `accept`/`content-type:
  application/json`; missing/invalid key → 401/403. Treat as a secret env var.
  [authentication]
- Methods: GET/POST/PUT/DELETE; JSON responses, UTF-8. [overview]
- Resources (from the `llms.txt` index): **Projects, Tasks, Phases, Time Entries,
  Custom Fields, Users/Team-Members** (+ Time-Off, Invoices, Spaces & Space Documents,
  Resource Allocations). [llms.txt]
- **MCP server:** OAuth-authenticated Rocketlane MCP server exposing project/company
  management, task create/update/delete, and time-entry tracking to an MCP host
  (Claude, Cursor, etc.). [MCP help article] Note: MCP auth is **OAuth**, distinct from
  REST's **api-key** — the live adapter must pick one mode per the existing
  "MCP-client OR REST-adapter" shape in `crm/live.py`.

### Verified Project fields (get-project response schema)
`projectName`, `status`, `startDate`, `startDateActual`, `dueDate`, `dueDateActual`,
`inferredProgress` (enum: `ON_TRACK` | `AHEAD_OF_TIME` | `RUNNING_LATE` | `NONE`),
`annualizedRecurringRevenue`, `projectFee`, `financials.contractType`,
`customer.companyId`, and `owner.userId`. The list/filter endpoint also exposes
filter keys such as `customerId`/`companyId` and `teamMemberId`. [get-all-projects,
get-project]

The full `get-project` 200 response schema is now verified from
`ProjectPublicAPIResponseEntity` in `get-project.md`. Fields include:
`projectId`, `projectName`, `startDate`, `dueDate`, `createdAt`, `updatedAt`, `owner`,
`teamMembers`, `status`, `fields`, `customer`, `partnerCompanies`, `archived`,
`visibility`, `createdBy`, `updatedBy`, `currency`, `financials`, `startDateActual`,
`dueDateActual`, `annualizedRecurringRevenue`, `projectFee`, `budgetedHours`,
`percentageBudgetedHoursConsumed`, `percentageBudgetConsumed`, `trackedHours`,
`trackedMinutes`, `allocatedHours`, `allocatedMinutes`, `billableHours`,
`billableMinutes`, `nonBillableHours`, `nonBillableMinutes`, `remainingHours`,
`remainingMinutes`, `progressPercentage`, `currentPhases`, `autoAllocation`, `sources`,
`plannedDurationInDays`, `inferredProgress`, `projectAgeInDays`, `customersInvited`,
`customersJoined`, and `externalReferenceId`. Nested verified shapes include:
`owner` (`emailId`, `userId`, `firstName`, `lastName`), `status` (`value`, `label`),
`customer` (`companyId`, `companyName`, `companyUrl`), `currentPhases` (`phaseId`,
`phaseName`), and `financials` (`contractType`, `revenueRecognitionType`,
`fixedFeeContract`, `timeAndMaterialContract`, `subscriptionContract`, `metrics`).

### Verified Task fields (reference)
`status` (object: value + label), `startDate`, `dueDate`, `dueDateActual` ("date the
task status changed to completed"), `assignees` (array), `phase` (object), `project`
(object), **`atRisk`** (Boolean). [reference/tasks]

### Verified Phase fields (get-phase response schema)
Endpoint set exists (`get-all-phases`, `get-phase`, create/update/delete). The
`get-phase` 200 response schema is now verified from `PhasePublicAPIResponseEntity` in
`get-phase.md`: `phaseId`, `phaseName`, `project`, `startDate`, `dueDate`,
`startDateActual`, `dueDateActual`, `createdAt`, `updatedAt`, `createdBy`, `updatedBy`,
`status`, and `private`. Nested verified shapes include `project` (`projectId`,
`projectName`), `status` (`value`, `label`), and created/updated user objects
(`emailId`, `userId`, `firstName`, `lastName`). [get-phase]

## Proposed contracts (implementation sketch)

```python
ProjectProgress = Literal["on_track", "ahead", "running_late", "none"]  # maps inferredProgress

@dataclass(frozen=True)
class OnboardingProject:
    project_id: str
    account_id: str            # JOIN KEY — see "Account join" gap below
    name: str
    status_value: int | None   # status.value
    status_label: str | None   # status.label
    owner_id: str | None       # owner.userId
    progress: ProjectProgress  # from inferredProgress
    start_date: str | None
    start_date_actual: str | None
    due_date: str | None
    due_date_actual: str | None
    arr_cents: int | None      # annualizedRecurringRevenue, stored as cents

@dataclass(frozen=True)
class OnboardingPhase:
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
    task_id: str
    project_id: str
    phase_id: str | None
    name: str
    status_label: str          # status.label
    start_date: str | None
    due_date: str | None
    due_date_actual: str | None  # populated == completed
    at_risk: bool              # atRisk
    assignee_ids: tuple[str, ...]


class OnboardingConnector(Protocol):
    """Rocketlane-backed onboarding/PSA seam. Tenant-bound, fail-closed, read-mostly."""
    def list_projects_for_account(self, account_id: str) -> list[OnboardingProject]: ...
    def get_project(self, project_id: str) -> OnboardingProject | None: ...
    def list_phases(self, project_id: str) -> list[OnboardingPhase]: ...
    def list_tasks(
        self, project_id: str, *, at_risk_only: bool = False, phase_id: str | None = None
    ) -> list[OnboardingTask]: ...
    # The bridge into Agent 1's existing evidence shape (see below).
    def derive_ttv_milestones(self, account_id: str) -> list[TimeToValueMilestone]: ...
```

## The TTV bridge (how it feeds Agent 1 without a new agent)

`derive_ttv_milestones` adapts Rocketlane structure into the **existing**
`TimeToValueMilestone` shape Agent 1 already consumes, so no agent or scorecard
category changes:

- A **phase** (or a milestone-tagged task) → one `TimeToValueMilestone`.
- `expected_by` ← phase/task `dueDate`; `achieved_at` ← `dueDateActual` (null = not yet
  achieved).
- **Activation-gap signal** = `dueDate` passed AND `dueDateActual` is null, or
  `inferredProgress == RUNNING_LATE`, or task `atRisk == true`.
- `evidence_signal_ids` ← the Rocketlane task/phase ids, so every recommendation cites a
  concrete grounded fact (satisfies the `grounding_stress` / evidence-citation gates).

This is the constrained integration: Rocketlane supplies *real onboarding-execution
evidence*; Agent 1's governance, eval, and recommendation logic are unchanged.

## Source map (conforms to source_maps.py)

```python
ROCKETLANE_SOURCE_MAPS: dict[str, SourceObjectMap] = {
    "OnboardingProject": SourceObjectMap(
        vendor="Rocketlane", object_name="Project",
        docs_url="https://developer.rocketlane.com/reference/get-project",
        fields={
            "project_id": SourceField("projectId", True),
            "account_id": SourceField("customer.companyId", True, "JOIN to CRM/CS account; see gap"),
            "name": SourceField("projectName", True),
            "status_value": SourceField("status.value", True),
            "status_label": SourceField("status.label", True),
            "owner_id": SourceField("owner.userId", True, "project owner / CSM"),
            "progress": SourceField("inferredProgress", True, "ON_TRACK|AHEAD_OF_TIME|RUNNING_LATE|NONE"),
            "start_date": SourceField("startDate", True),
            "start_date_actual": SourceField("startDateActual", True),
            "due_date": SourceField("dueDate", True),
            "due_date_actual": SourceField("dueDateActual", True),
            "arr_cents": SourceField("annualizedRecurringRevenue", True, "stored internally as cents"),
        },
    ),
    "OnboardingTask": SourceObjectMap(
        vendor="Rocketlane", object_name="Task",
        docs_url="https://developer.rocketlane.com/reference/tasks",
        fields={
            "task_id": SourceField("taskId", True),
            "project_id": SourceField("project", True, "task.project object"),
            "phase_id": SourceField("phase", True, "task.phase object"),
            "name": SourceField("taskName", True),
            "status_label": SourceField("status.label", True),
            "start_date": SourceField("startDate", True),
            "due_date": SourceField("dueDate", True),
            "due_date_actual": SourceField("dueDateActual", True, "set when completed"),
            "at_risk": SourceField("atRisk", True),
            "assignee_ids": SourceField("assignees", True),
        },
    ),
    "OnboardingPhase": SourceObjectMap(
        vendor="Rocketlane", object_name="Phase",
        docs_url="https://developer.rocketlane.com/reference/get-phase",
        fields={
            "phase_id": SourceField("phaseId", True),
            "project_id": SourceField("project.projectId", True),
            "name": SourceField("phaseName", True),
            "start_date": SourceField("startDate", True),
            "start_date_actual": SourceField("startDateActual", True),
            "due_date": SourceField("dueDate", True),
            "due_date_actual": SourceField("dueDateActual", True),
            "status_label": SourceField("status.label", True),
            "private": SourceField("private", True),
        },
    ),
}
```
Add `**ROCKETLANE_SOURCE_MAPS` to `ALL_SOURCE_MAPS`, and extend the source-map coverage
test so every `Onboarding*` contract field has an entry (same gate as the existing
connectors).

## Live adapter shape

- Two modes behind one credential set, conforming to `crm/live.py`:
  - **MCP client** against the Rocketlane OAuth MCP server (our app is the host), or
  - **REST adapter** (httpx) against `https://api.rocketlane.com/api/1.0` with the
    `api-key` header.
- Lazy-import the client so importing the module is socket-free/key-free.
- **Fail-closed:** a Rocketlane outage/timeout/auth error surfaces as no-project /
  escalate, never a fabricated milestone.
- Pagination + rate limits: confirm against the reference before the live adapter ships
  (not yet fetched).

## Scope discipline

- One connector, feeding the existing Agent 1. **No new agent, no new scorecard
  pillar.** Keeps the Agent-1 MVP cut intact.
- Scored eval path stays on the **fixture** connector. Live Rocketlane is live-lane only.
- Build order: fixtures + contracts + source-map + coverage test **first**; the
  `derive_ttv_milestones` bridge into Agent 1 evidence **second**; the live MCP/REST
  adapter **last** (and credential-gated).

## Open gaps & decisions

1. **Account join.** Rocketlane has **no standalone companies/customers REST resource**
   in the index; account identity is the `customerId`/`companyId` reference on projects.
   Joining a Rocketlane project to the CRM/CS account requires a shared external id or a
   configured mapping. Fixtures key directly on `account_id`; the live adapter needs an
   explicit join strategy — **decision needed** (shared external id vs mapping table vs
   MCP company lookup).
2. **Write-back deferred.** If/when Agent surfaces a "create follow-up task" or "post
   update" action, it goes through the action gate as a proposal; not in the read MVP.
3. **MCP vs REST for the live lane** — pick one for the first live adapter (OAuth MCP is
   lower-code but host-bound; REST api-key is simpler to credential-gate in CI). Default
   recommendation: REST for the live-smoke lane, MCP as a documented alternative.

## Source Documentation Inputs

- Rocketlane API overview: `https://developer.rocketlane.com/docs/overview`
- Authentication (api-key): `https://developer.rocketlane.com/docs/authentication`
- Markdown/OpenAPI index for agents: `https://developer.rocketlane.com/llms.txt`
- Get all projects (project filter fields): `https://developer.rocketlane.com/reference/get-all-projects`
- Get project by Id (full project response schema): `https://developer.rocketlane.com/reference/get-project`
- Tasks reference (task fields): `https://developer.rocketlane.com/reference/tasks`
- Get phase by Id (full phase response schema): `https://developer.rocketlane.com/reference/get-phase`
- Time entries: `https://developer.rocketlane.com/reference/get-all-time-entries`
- Rocketlane MCP (OAuth, Claude/Cursor): `https://help.rocketlane.com/support/solutions/articles/67000754219-connect-rocketlane-mcp-to-claude-code`
