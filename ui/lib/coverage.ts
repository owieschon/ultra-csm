import { AccountSummary, CoverageReceiptResponse, WorkItem } from "@/lib/api";
import { label, MOTION_LABELS, TRIGGER_LABELS } from "@/lib/labels";
import { describeWork } from "@/lib/work";

export type CoverageState =
  | "needs_human"
  | "prepared_work"
  | "reviewed"
  | "covered"
  | "insufficient_evidence"
  | "source_degraded"
  | "not_scanned";

export interface CoverageReceipt {
  account: AccountSummary;
  state: CoverageState;
  label: string;
  actionLabel: string;
  reason: string;
  scoreLabel: string;
  scanned: boolean;
  workItem: WorkItem | null;
  evidenceLines: string[];
  missingLines: string[];
  receiptLines: string[];
}

export const COVERAGE_FILTERS: { key: CoverageState | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "needs_human", label: "Needs human" },
  { key: "prepared_work", label: "Prepared" },
  { key: "covered", label: "Covered" },
  { key: "reviewed", label: "Reviewed" },
  { key: "insufficient_evidence", label: "Insufficient" },
  { key: "source_degraded", label: "Source degraded" },
  { key: "not_scanned", label: "Not scanned" },
];

export function buildCoverageReceipts({
  accounts,
  workItems,
  sweptAccounts,
  backendReceipts,
}: {
  accounts: AccountSummary[];
  workItems: WorkItem[];
  sweptAccounts: string[];
  backendReceipts?: CoverageReceiptResponse[];
}): CoverageReceipt[] {
  if (backendReceipts?.length) {
    return fromBackendReceipts(accounts, workItems, backendReceipts);
  }
  const workByAccount = new Map<string, WorkItem>();
  workItems.forEach((item) => {
    if (item.account_id) workByAccount.set(item.account_id, item);
  });
  const swept = new Set(sweptAccounts);
  return accounts.map((account) => {
    const item = workByAccount.get(account.account_id) ?? null;
    return receiptForAccount(account, item, swept.has(account.account_id));
  });
}

function fromBackendReceipts(
  accounts: AccountSummary[],
  workItems: WorkItem[],
  backendReceipts: CoverageReceiptResponse[]
): CoverageReceipt[] {
  const accountsById = new Map(accounts.map((account) => [account.account_id, account]));
  const workByAccount = new Map<string, WorkItem>();
  workItems.forEach((item) => {
    if (item.account_id) workByAccount.set(item.account_id, item);
  });
  return backendReceipts.flatMap((receipt) => {
    const account = accountsById.get(receipt.account_id);
    if (!account) return [];
    return [{
      account,
      state: receipt.state,
      label: receipt.label,
      actionLabel: receipt.action_label,
      reason: operatorReason(receipt.state, workByAccount.get(receipt.account_id) ?? null, receipt.reason),
      scoreLabel: receipt.score_label,
      scanned: receipt.scanned,
      workItem: workByAccount.get(receipt.account_id) ?? null,
      evidenceLines: humanizeReceiptLines(receipt.evidence_lines),
      missingLines: humanizeReceiptLines(receipt.missing_lines),
      receiptLines: [...receipt.evidence_lines, ...receipt.missing_lines],
    }];
  });
}

function receiptForAccount(
  account: AccountSummary,
  item: WorkItem | null,
  scanned: boolean
): CoverageReceipt {
  if (!scanned) {
    return baseReceipt(account, item, "not_scanned", scanned, {
      reason: "This account is in the book but is absent from the latest sweep receipt.",
      actionLabel: "Review source coverage",
      missingLines: ["No swept_accounts receipt for this account."],
    });
  }
  if (account.priority_score_error) {
    return baseReceipt(account, item, "source_degraded", scanned, {
      reason: `Priority scoring failed with ${account.priority_score_error}.`,
      actionLabel: "Review degraded source",
      missingLines: [`priority_score_error: ${account.priority_score_error}`],
    });
  }
  if (account.priority_score == null) {
    return baseReceipt(account, item, "insufficient_evidence", scanned, {
      reason: "The account was swept, but no priority score is available.",
      actionLabel: "Inspect missing evidence",
      missingLines: ["priority_score is null."],
    });
  }
  if (item?.proposal?.status === "pending") {
    const descriptor = describeWork(item);
    return baseReceipt(account, item, "needs_human", scanned, {
      reason: `${descriptor.packetLabel} is waiting for human approval.`,
      actionLabel: "Open packet",
    });
  }
  if (item && !item.proposal) {
    const descriptor = describeWork(item);
    return baseReceipt(account, item, "prepared_work", scanned, {
      reason: `${descriptor.packetLabel} was prepared without a customer-facing release.`,
      actionLabel: "Inspect packet",
    });
  }
  if (item?.proposal) {
    return baseReceipt(account, item, "reviewed", scanned, {
      reason: `The proposal was ${item.proposal.status}.`,
      actionLabel: "Review audit receipt",
    });
  }
  return baseReceipt(account, item, "covered", scanned, {
    reason: "Swept this run; no work item was emitted for the account.",
    actionLabel: "Review receipt",
    missingLines: [
      "Per-factor non-promotion thresholds are not exposed by the current API.",
    ],
  });
}

function baseReceipt(
  account: AccountSummary,
  item: WorkItem | null,
  state: CoverageState,
  scanned: boolean,
  overrides: {
    reason: string;
    actionLabel: string;
    missingLines?: string[];
  }
): CoverageReceipt {
  const factors = item?.priority?.factors ?? [];
  const factorLines = factors.slice(0, 3).map((factor) => {
    const threshold =
      factor.threshold_name && factor.threshold_value != null
        ? ` · threshold ${factor.threshold_name}=${factor.threshold_value}`
        : "";
    return `${factor.name}: value ${factor.value}, contribution ${factor.contribution}${threshold}`;
  });
  const motion = item?.motion ? label(MOTION_LABELS, item.motion) : null;
  return {
    account,
    state,
    label: stateLabel(state),
    actionLabel: overrides.actionLabel,
    reason: overrides.reason,
    scoreLabel:
      account.priority_score == null
        ? "score unavailable"
        : `priority score ${account.priority_score}`,
    scanned,
    workItem: item,
    evidenceLines: [
      scanned ? "Included in latest swept_accounts receipt." : "Not included in latest sweep.",
      motion ? `Motion: ${motion}.` : "No motion emitted.",
      ...factorLines,
    ].map(humanizeReceiptLine),
    missingLines: (overrides.missingLines ?? []).map(humanizeReceiptLine),
    receiptLines: [
      scanned ? "Included in latest swept_accounts receipt." : "Not included in latest sweep.",
      motion ? `Motion: ${item?.motion}.` : "No motion emitted.",
      ...factorLines,
      ...(overrides.missingLines ?? []),
    ],
  };
}

export function stateLabel(state: CoverageState): string {
  switch (state) {
    case "needs_human":
      return "Needs human";
    case "prepared_work":
      return "Prepared work";
    case "reviewed":
      return "Reviewed";
    case "covered":
      return "Covered";
    case "insufficient_evidence":
      return "Insufficient evidence";
    case "source_degraded":
      return "Source degraded";
    case "not_scanned":
      return "Not scanned";
  }
}

function operatorReason(
  state: CoverageState,
  item: WorkItem | null,
  fallback: string
): string {
  const descriptor = item ? describeWork(item) : null;
  switch (state) {
    case "needs_human":
      return descriptor
        ? `Review the agent-prepared ${descriptor.packetLabel.toLowerCase()} before anything reaches the customer.`
        : "Review the agent-prepared work before anything reaches the customer.";
    case "prepared_work":
      return descriptor
        ? `${descriptor.packetLabel} is ready for internal review; no customer-facing action can send from here.`
        : "Internal work is ready for review; no customer-facing action can send from here.";
    case "reviewed":
      return "This account already has a human decision recorded for the prepared work.";
    case "covered":
      return "The agent checked this account and found no work that needs attention right now.";
    case "insufficient_evidence":
      return "The agent could not score this account because required source evidence is missing.";
    case "source_degraded":
      return "A source problem blocked reliable prioritization for this account.";
    case "not_scanned":
      return "This account is in the book but did not appear in the latest sweep coverage receipt.";
    default:
      return fallback;
  }
}

function humanizeReceiptLines(lines: string[]): string[] {
  return lines.map(humanizeReceiptLine);
}

function humanizeReceiptLine(line: string): string {
  if (line === "Included in latest swept_accounts receipt.") {
    return "Included in the latest book sweep.";
  }
  if (line === "Not included in latest sweep." || line === "No swept_accounts receipt for this account.") {
    return "Missing from the latest book sweep.";
  }
  if (line === "No motion emitted.") {
    return "No agent action was prepared.";
  }
  if (line === "priority_score is null.") {
    return "No reliable priority score is available.";
  }
  if (line.startsWith("priority_score_error:")) {
    return "Priority scoring source returned an error.";
  }
  if (line === "Per-factor non-promotion thresholds are not exposed by the current API.") {
    return "No detailed near-miss explanation is exposed yet.";
  }

  const motion = line.match(/^Motion: (.+)\.$/);
  if (motion) {
    return `Recommended next step: ${label(MOTION_LABELS, motion[1])}.`;
  }

  const factor = line.match(/^([^:]+): value ([^,]+), contribution ([^·]+)(?: · threshold .+)?$/);
  if (factor) {
    const factorLabel = label(TRIGGER_LABELS, factor[1]);
    const contribution = String(factor[3]).trim();
    return `${factorLabel}: adds ${contribution} priority points.`;
  }

  return line;
}
