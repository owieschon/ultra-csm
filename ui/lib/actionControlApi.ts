import { isReadOnlyDemo } from "./api";

const GENERAL_API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";
const SANDBOX_API_BASE = process.env.NEXT_PUBLIC_ACTION_CONTROL_SANDBOX_API;

export type SandboxState =
  | "pending_human_decision"
  | "approved_payload_bound"
  | "denied_terminal"
  | "simulated_committed"
  | "refused_payload_mismatch";

export type SandboxCommand =
  | { command_id: string; type: "approve_exact" }
  | { command_id: string; type: "revise_and_approve"; draft: string }
  | { command_id: string; type: "deny" }
  | { command_id: string; type: "commit_simulated" }
  | { command_id: string; type: "retry_same_commit" }
  | { command_id: string; type: "probe_tamper"; draft: string };

export interface SandboxSession {
  schema_version: "action-control.sandbox-session.v1";
  run_id: string;
  revision: number;
  state: SandboxState;
  state_sha256: string;
  allowed_commands: SandboxCommand["type"][];
  mode: "rollback_isolated_synthetic";
  outbound_effects_enabled: false;
  scenario: {
    scenario_id: string;
    account_id: string;
    account_name: "Trailhead Logistics";
    contact_name: "Vanessa Torres";
    recipient: string;
    original_draft: string;
    evidence: { evidence_id: string; label: string; provenance: "synthetic_fixture" }[];
  };
  proposal: {
    proposal_id: string;
    action: "draft_customer_outreach";
    status: "pending" | "approved" | "denied";
    draft: string;
    payload_sha256: string;
  };
  decision: null | {
    verdict: "approve" | "revise" | "deny";
    human_principal_id: string;
    approved_payload_sha256: string | null;
  };
  committed_receipt: null | {
    state: "simulated_committed";
    receipt_id: string;
    proposal_id: string;
    idempotency_key: string;
    target: "simulated_outbox";
    committed: true;
    dry_run: false;
    external_effect: false;
    payload_sha256: string;
  };
  idempotency_probe: null | {
    state: "duplicate_suppressed";
    receipt_id: string;
    idempotency_key: string;
    committed: false;
    outbox_rows: 1;
  };
  tamper_refusal: null | {
    state: "refused_payload_mismatch";
    code: "PAYLOAD_HASH_MISMATCH";
    reason: string;
    committed: false;
    approved_payload_sha256: string;
    attempted_payload_sha256: string;
    outbox_rows: 1;
  };
  events: {
    sequence: number;
    state: SandboxState;
    label: string;
    technical_event: string;
    detail: string;
    payload_sha256: string | null;
  }[];
  isolation: {
    database_transaction: "rolled_back";
    filesystem: "temporary_directory_removed";
    external_effect: false;
  };
}

export interface SandboxRequest {
  schema_version: "action-control.sandbox-command-log.v1";
  run_id: string;
  expected_state_sha256: string | null;
  commands: SandboxCommand[];
}

export class SandboxApiError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly status = 0
  ) {
    super(message);
  }
}

export const sandboxApiAvailable = Boolean(SANDBOX_API_BASE) || !isReadOnlyDemo;

export async function evaluateSandbox(
  request: SandboxRequest,
  signal?: AbortSignal
): Promise<SandboxSession> {
  if (!sandboxApiAvailable) {
    throw new SandboxApiError(
      "Interactive sandbox backend is not deployed. The frozen proof remains available below.",
      "SANDBOX_BACKEND_UNAVAILABLE"
    );
  }
  const base = SANDBOX_API_BASE ?? GENERAL_API_BASE;
  const response = await fetch(`${base}/demo/action-control/sandbox/evaluate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
    cache: "no-store",
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail ?? body;
    throw new SandboxApiError(
      detail?.error ?? `Sandbox request failed (${response.status})`,
      detail?.code ?? "SANDBOX_REQUEST_FAILED",
      response.status
    );
  }
  return body as SandboxSession;
}
