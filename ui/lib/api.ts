// Thin fetch wrapper over the FastAPI surface (src/ultra_csm/api.py).
// Dev (`next dev` on :3000): NEXT_PUBLIC_API_BASE=http://localhost:8000
// (set by `npm run dev`), CORS added in api.py's Phase 1 commit.
// Demo/prod (`make serve` mounting ui/out at /ui via StaticFiles): base is
// "" (relative), same-origin, no CORS needed.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";
export const isReadOnlyDemo = process.env.NEXT_PUBLIC_UCSM_READONLY_DEMO === "1";
const DEMO_API_BASE =
  process.env.NEXT_PUBLIC_UCSM_DEMO_API_BASE ?? "/ui/demo-api";

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    super(`API error ${status}`);
    this.status = status;
    this.body = body;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  if (isReadOnlyDemo) {
    return demoRequest<T>(path, init);
  }
  const resp = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  const body = await resp.json().catch(() => null);
  if (!resp.ok) {
    throw new ApiError(resp.status, body);
  }
  return body as T;
}

function demoPath(path: string): string {
  const [rawPath, rawQuery = ""] = path.split("?");
  const query = new URLSearchParams(rawQuery);
  const day = query.get("day") ?? "140";
  const accountMatch = rawPath.match(/^\/accounts\/([^/]+)\/([^/]+)$/);
  if (rawPath === "/health") return "health.json";
  if (rawPath === "/accounts") return `accounts-day-${day}.json`;
  if (rawPath === "/sweep") return `sweep-day-${day}.json`;
  if (rawPath === "/proposals") return "proposals.json";
  if (rawPath === "/ledger") return "ledger.json";
  if (rawPath === "/workflow-authoring/readiness") return "workflow-authoring-readiness.json";
  if (rawPath === "/comms/pending-mappings/slack") return "comms-slack.json";
  if (rawPath === "/comms/pending-mappings/notion") return "comms-notion.json";
  if (accountMatch) {
    const accountId = accountMatch[1];
    const leaf = accountMatch[2];
    if (leaf === "brief") return `account-${accountId}-brief-day-${day}.json`;
    if (leaf === "centralize-telemetry") return `account-${accountId}-centralize-telemetry-day-${day}.json`;
    if (leaf === "trajectory") return `account-${accountId}-trajectory.json`;
    if (leaf === "reconciliation") return `account-${accountId}-reconciliation-day-${day}.json`;
  }
  throw new ApiError(404, {
    error: "Read-only demo fixture not found",
    code: "READONLY_DEMO_NOT_FOUND",
    path,
  });
}

async function demoRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const method = init?.method ?? "GET";
  const [rawPath] = path.split("?");
  if (method !== "GET" && rawPath !== "/sweep") {
    throw new ApiError(405, {
      error: "The hosted demo is read-only.",
      code: "READONLY_DEMO",
      path,
    });
  }
  const fixture = demoPath(path);
  const resp = await fetch(`${DEMO_API_BASE}/${fixture}`, {
    headers: { Accept: "application/json" },
  });
  const body = await resp.json().catch(() => null);
  if (!resp.ok) {
    throw new ApiError(resp.status, body);
  }
  return body as T;
}

export interface PendingMappingCandidate {
  account_id: string;
  confidence: number;
  reason: string;
  signal: string;
}

export interface PendingMapping {
  source_type: "notion_meeting" | "slack_channel";
  external_id: string;
  title: string;
  candidates: PendingMappingCandidate[];
}

export interface PendingMappingsResponse {
  pending: PendingMapping[];
  auth: string | null;
}

export interface ConfirmMappingResponse {
  mapping_id: string;
  auth: string | null;
}

export interface AccountSummary {
  account_id: string;
  account_name: string;
  industry: string | null;
  health_band: string | null;
  health_score: number | null;
  lifecycle_stage: string | null;
  arr_cents: number | null;
  priority_score: number | null;
  priority_score_error: string | null;
  tier: string | null;
}

export interface AccountListResponse {
  tenant_id: string;
  account_count: number;
  accounts: AccountSummary[];
}

export interface ValueFactor {
  name: string;
  value: number;
  contribution: number;
  evidence: Record<string, unknown>[];
  config_version: string;
  rule_name: string;
  threshold_name: string | null;
  threshold_value: number | string | null;
}

export interface WorkItemProposalRef {
  proposal_id: string;
  status: "pending" | "approved" | "denied";
  action_type: string;
  channel: string;
  created_by_principal: string;
}

export interface InternalBridgeEvidence {
  source: string;
  source_id: string;
  field: string;
  observed_at: string;
}

export interface InternalBridgeDecision {
  target: "engineering" | "product" | null;
  motion: string | null;
  signal: string | null;
  evidence: InternalBridgeEvidence[];
  abstained: boolean;
  reason: string;
}

export interface DiagnosticHypothesis {
  summary: string;
  signals: string[];
  counter_signals: string[];
  unknowns: string[];
  confidence: number;
  source_ids: string[];
}

export interface RecommendedAction {
  action_id: string;
  action_type: string;
  label: string;
  objective: string;
  recipient_role: string | null;
  recipient_contact_id: string | null;
  message_strategy: string;
  success_criteria: string[];
  blocked_by: string[];
  source_ids: string[];
}

export interface ContactPlan {
  primary_contact: Record<string, unknown> | null;
  backup_contact: Record<string, unknown> | null;
  internal_owner: string | null;
  tone: string;
  channel: string;
  reason_for_contact_choice: string;
  source_ids: string[];
}

export interface PreparedArtifact {
  artifact_id: string;
  artifact_type: string;
  title: string;
  body_or_outline: string;
  intended_audience: string;
  requires_approval: boolean;
  source_ids: string[];
}

export interface AllowedCTA {
  cta_id: string;
  label: string;
  kind: "inspect" | "preview" | "copy" | "edit" | "approve" | "reject" | "assign" | "simulate" | "deep_link" | "mark_reviewed" | "leave_feedback";
  enabled: boolean;
  disabled_reason: string | null;
  governance_requirement: string | null;
  readonly_behavior: string;
  source_ids: string[];
}

export interface GovernanceBoundary {
  mode: string;
  requires_human_principal: boolean;
  requires_action_gate: boolean;
  can_execute_from_ui: boolean;
  audit_requirements: string[];
}

export interface EvidenceChainStep {
  step_id: string;
  claim: string;
  source_type: string;
  source_id: string;
  field: string;
  observed_value: string;
  interpretation: string;
  supports: string;
  strength: "weak" | "medium" | "strong";
}

export interface BucketTrace {
  lane: string;
  rule_id: string;
  rule_label: string;
  inputs: Record<string, unknown>;
  thresholds: Record<string, unknown>;
  matched: string[];
  near_misses: string[];
  source_ids: string[];
}

export interface CoverageTrace {
  book_size: number;
  accounts_scanned: number;
  included_reason: string;
  excluded_or_suppressed_reason: string | null;
  last_reviewed_at: string | null;
  freshness: string;
}

export interface FeedbackHook {
  category: string;
  label: string;
  local_only: boolean;
  readonly_behavior: string;
}

export interface CSMWorkPacket {
  packet_id: string;
  account_id: string | null;
  account_name: string;
  generated_at: string;
  as_of_day: string;
  cadence: string;
  job_type: string;
  lane: string;
  primary_next_step: string;
  why_now: string;
  diagnostic_hypothesis: DiagnosticHypothesis;
  implied_customer_state: string;
  recommended_action: RecommendedAction;
  contact_plan: ContactPlan;
  prepared_artifacts: PreparedArtifact[];
  allowed_ctas: AllowedCTA[];
  governance: GovernanceBoundary;
  evidence_chain: EvidenceChainStep[];
  bucket_trace: BucketTrace;
  coverage_trace: CoverageTrace;
  open_questions: string[];
  confidence: number;
  feedback_hooks: FeedbackHook[];
}

export interface WorkItem {
  tenant_id: string;
  account_resolution: string;
  account_id: string | null;
  candidate_account_ids: string[];
  disposition: string;
  recommended_action: string | null;
  reason: string;
  priority: { score: number; factors: ValueFactor[] } | null;
  evidence: Record<string, unknown>[];
  customer_contact_allowed: boolean;
  proposal: WorkItemProposalRef | null;
  swept_at: string;
  draft_mode: string;
  customer_draft: string | null;
  motion: string | null;
  internal_bridge_decision?: InternalBridgeDecision | null;
  recipient_resolution: string | null;
  recipient_name: string | null;
  recipient_role: string | null;
  work_packet: CSMWorkPacket | null;
}

export interface SweepResponse {
  tenant_id: string;
  work_items: WorkItem[];
  escalations: Record<string, unknown>[];
  swept_accounts: string[];
  coverage_packets: CSMWorkPacket[];
  degraded_items: number;
  auth: string | null;
}

export interface ProposalSummary {
  proposal_id: string;
  intent: string;
  action: string;
  payload: Record<string, unknown>;
  autonomy_tier: number;
  required_permission: string;
  status: string;
}

export interface ProposalListResponse {
  tenant_id: string;
  pending_count: number;
  proposals: ProposalSummary[];
}

export interface VerdictResponse {
  proposal_id: string;
  status: string;
  authorized: boolean;
  verdict: string;
  payload_sha256: string;
  superseding_proposal_id: string | null;
  auth: string | null;
}

export interface LedgerEvent {
  ts: string;
  event: string;
  label: string;
  proposal_id: string | null;
  detail: string;
}

export interface LedgerResponse {
  tenant_id: string;
  events: LedgerEvent[];
  ledger_gap: string[];
}

export interface WorkflowPlaybookResponse {
  tenant_id: string;
  workflows: Record<string, unknown>;
}

export interface WorkflowAuthoringIssue {
  workflow_id: string;
  check_name: string;
  severity: "error" | "warning";
  detail: string;
}

export interface WorkflowReadiness {
  workflow_id: string;
  ready: boolean;
  issues: WorkflowAuthoringIssue[];
  declared_test_obligations: string[];
}

export interface WorkflowAuthoringReadinessReport {
  ready: boolean;
  workflows: Record<string, WorkflowReadiness>;
  registry_issues: WorkflowAuthoringIssue[];
}

export interface WorkflowAuthoringReadinessResponse {
  tenant_id: string;
  report: WorkflowAuthoringReadinessReport;
}

export interface EnterpriseOnboardingPacket {
  packet_id: string;
  account_id: string;
  opportunity_id: string;
  status: string;
  packet: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface EnterpriseOnboardingPacketListResponse {
  tenant_id: string;
  packets: EnterpriseOnboardingPacket[];
}

export interface SelfServeActivationPacket {
  packet_id: string;
  account_id: string;
  workspace_id: string;
  signup_email: string;
  status: string;
  packet: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SelfServeActivationPacketListResponse {
  tenant_id: string;
  packets: SelfServeActivationPacket[];
}

export interface AdoptionRegressionPacket {
  packet_id: string;
  account_id: string;
  metric_name: string;
  status: string;
  packet: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AdoptionRegressionPacketListResponse {
  tenant_id: string;
  packets: AdoptionRegressionPacket[];
}

// Reconciliation agent (Harvest 31/32, report 52/53): reported-vs-
// experienced reconciliation for one account. EvidenceRefRow mirrors
// EvidenceRef (contracts.py) -- source/source_id/field/observed_at.
export interface EvidenceRefRow {
  source: string;
  source_id: string;
  field: string;
  observed_at: string;
}

export interface DeterministicSignalRow {
  origin: "deterministic";
  name: string;
  value: number;
  contribution: number;
  surfaced_by_lenses: string[];
  evidence: EvidenceRefRow[];
}

export interface CandidateDivergenceRow {
  origin: "llm_hypothesis";
  claim: string;
  confidence: "low" | "medium";
  disclaimer: string;
  evidence: EvidenceRefRow[];
}

export interface ReconciliationResponse {
  account_id: string;
  deterministic_signals: DeterministicSignalRow[];
  explanation: {
    text: string;
    disclaimer: string;
    evidence: EvidenceRefRow[];
  };
  candidate_divergences: CandidateDivergenceRow[];
}

export interface CentralizeTelemetryResponse {
  account_id: string;
  account_slug: string;
  account_name: string;
  day_offset: number;
  as_of: string;
  app_events: Record<string, unknown>[];
  posthog_events: Record<string, unknown>[];
  derived_usage_signals: Record<string, unknown>[];
}

export interface HealthResponse {
  status: string;
  db_connected: boolean;
  config_loaded: boolean;
  tenant_id: string;
  accounts_loaded: number;
  auth: string;
  data_plane_mode: string;
  data_plane_sources: Record<string, string>;
  health_source: string;
}

export const api = {
  health: () => request<HealthResponse>("/health"),
  accounts: (day?: number) =>
    request<AccountListResponse>(`/accounts${day != null ? `?day=${day}` : ""}`),
  accountBrief: (accountId: string, day?: number) =>
    request<Record<string, unknown>>(
      `/accounts/${accountId}/brief${day != null ? `?day=${day}` : ""}`
    ),
  accountCentralizeTelemetry: (accountId: string, day?: number) =>
    request<CentralizeTelemetryResponse>(
      `/accounts/${accountId}/centralize-telemetry${day != null ? `?day=${day}` : ""}`
    ),
  accountTrajectory: (accountId: string, window = 30) =>
    request<Record<string, unknown>>(
      `/accounts/${accountId}/trajectory?window=${window}`
    ),
  accountReconciliation: (accountId: string, day?: number) =>
    request<ReconciliationResponse>(
      `/accounts/${accountId}/reconciliation${day != null ? `?day=${day}` : ""}`
    ),
  // No Authorization header is sent: `_require_write_auth` accepts either a
  // mapped ULTRA_CSM_API_TOKENS bearer or ULTRA_CSM_DEMO_NOAUTH=1 (the
  // existing local-demo convention, e.g. eval/mcp_operator_demo.py's
  // ULTRA_CSM_DEMO_OPERATOR=1) -- the UI does not invent a credential; the
  // operator sets ULTRA_CSM_DEMO_NOAUTH=1 when running `make ui-serve-demo`.
  sweep: (day?: number) =>
    request<SweepResponse>(`/sweep${day != null ? `?day=${day}` : ""}`, {
      method: "POST",
    }),
  proposals: () => request<ProposalListResponse>("/proposals"),
  submitVerdict: (
    proposalId: string,
    verdict: "approve" | "deny" | "revise",
    reason: string,
    editInstruction?: string
  ) =>
    request<VerdictResponse>(`/proposals/${proposalId}/verdict`, {
      method: "POST",
      body: JSON.stringify({
        verdict,
        reason,
        edit_instruction: editInstruction,
      }),
    }),
  ledger: (limit = 50) => request<LedgerResponse>(`/ledger?limit=${limit}`),
  workflowPlaybooks: () => request<WorkflowPlaybookResponse>("/workflow-playbooks"),
  workflowAuthoringReadiness: () =>
    request<WorkflowAuthoringReadinessResponse>("/workflow-authoring/readiness"),
  enterpriseOnboardingPackets: (accountId?: string, opportunityId?: string) => {
    const params = new URLSearchParams();
    if (accountId) params.set("account_id", accountId);
    if (opportunityId) params.set("opportunity_id", opportunityId);
    const query = params.toString();
    return request<EnterpriseOnboardingPacketListResponse>(
      `/enterprise-onboarding/packets${query ? `?${query}` : ""}`
    );
  },
  enterpriseOnboardingPacket: (packetId: string) =>
    request<EnterpriseOnboardingPacket>(
      `/enterprise-onboarding/packets/${encodeURIComponent(packetId)}`
    ),
  selfServeActivationPackets: (accountId?: string, workspaceId?: string) => {
    const params = new URLSearchParams();
    if (accountId) params.set("account_id", accountId);
    if (workspaceId) params.set("workspace_id", workspaceId);
    const query = params.toString();
    return request<SelfServeActivationPacketListResponse>(
      `/self-serve/activation/packets${query ? `?${query}` : ""}`
    );
  },
  selfServeActivationPacket: (packetId: string) =>
    request<SelfServeActivationPacket>(
      `/self-serve/activation/packets/${encodeURIComponent(packetId)}`
    ),
  adoptionRegressionPackets: (accountId?: string, metricName?: string) => {
    const params = new URLSearchParams();
    if (accountId) params.set("account_id", accountId);
    if (metricName) params.set("metric_name", metricName);
    const query = params.toString();
    return request<AdoptionRegressionPacketListResponse>(
      `/adoption-regression/packets${query ? `?${query}` : ""}`
    );
  },
  adoptionRegressionPacket: (packetId: string) =>
    request<AdoptionRegressionPacket>(
      `/adoption-regression/packets/${encodeURIComponent(packetId)}`
    ),
  pendingSlackMappings: () =>
    request<PendingMappingsResponse>("/comms/pending-mappings/slack"),
  pendingNotionMappings: () =>
    request<PendingMappingsResponse>("/comms/pending-mappings/notion"),
  confirmCommsMapping: (
    sourceType: "notion_meeting" | "slack_channel",
    externalId: string,
    accountId: string,
    contactId?: string
  ) =>
    request<ConfirmMappingResponse>("/comms/mappings/confirm", {
      method: "POST",
      body: JSON.stringify({
        source_type: sourceType,
        external_id: externalId,
        account_id: accountId,
        contact_id: contactId ?? null,
      }),
    }),
};
