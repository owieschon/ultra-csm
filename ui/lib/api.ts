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
  if (rawPath === "/comms/pending-mappings/slack") return "comms-slack.json";
  if (rawPath === "/comms/pending-mappings/notion") return "comms-notion.json";
  if (accountMatch) {
    const accountId = accountMatch[1];
    const leaf = accountMatch[2];
    if (leaf === "brief") return `account-${accountId}-brief-day-${day}.json`;
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
}

export interface SweepResponse {
  tenant_id: string;
  work_items: WorkItem[];
  escalations: Record<string, unknown>[];
  swept_accounts: string[];
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
