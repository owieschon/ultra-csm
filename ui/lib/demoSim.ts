// Demo decisions and edits exist only in tab memory and reset on reload.
import { LedgerEvent } from "@/lib/api";

export type DemoVerdict = "approved" | "denied";

export interface DemoLedgerEvent extends LedgerEvent {
  simulated: true;
}

export interface DemoEditRecord {
  revisionId: string;
  body: string;
  editedAt: string;
}

export interface DemoApprovalSnapshot {
  revisionId: string;
  body: string;
  approvedAt: string;
}

function ts(offsetSeconds: number): string {
  const d = new Date(Date.now() + offsetSeconds * 1000);
  return d.toISOString();
}

let revisionSeq = 0;

// Monotonic within the tab (never persisted, reset on reload along with
// everything else in this file) — just needs to be unique enough to tell
// two saved edits apart in the receipt.
export function nextRevisionId(proposalId: string): string {
  revisionSeq += 1;
  return `sim-rev-${proposalId.slice(0, 8)}-${revisionSeq}`;
}

// This demo runs no ActionGate call, verifies no payload hash, and obtains
// no committer receipt — every line below states only what happened in the
// browser: a button click updated local state. Nothing left the tab.
export function simulateApproval(
  proposalId: string,
  revisionId: string
): DemoLedgerEvent[] {
  return [
    {
      ts: ts(0),
      event: "gate.approve",
      label: "Approved",
      proposal_id: proposalId,
      detail: `Approved in this demo — no gate call made — exact revision ${revisionId}`,
      simulated: true,
    },
    {
      ts: ts(1),
      event: "committer.commit",
      label: "Commit simulated",
      proposal_id: proposalId,
      detail: "no committer ran — nothing released",
      simulated: true,
    },
    {
      ts: ts(2),
      event: "send.receipt",
      label: "Send simulated",
      proposal_id: proposalId,
      detail: "no message sent — demo only",
      simulated: true,
    },
    {
      ts: ts(3),
      event: "tick.reobserve",
      label: "Re-check queued",
      proposal_id: proposalId,
      detail: "agent re-observes this account next sweep",
      simulated: true,
    },
  ];
}

export function simulateDenial(proposalId: string): DemoLedgerEvent[] {
  return [
    {
      ts: ts(0),
      event: "gate.deny",
      label: "Denied",
      proposal_id: proposalId,
      detail: "human verdict recorded — this draft won't recur verbatim",
      simulated: true,
    },
    {
      ts: ts(1),
      event: "feedback.persist",
      label: "Feedback saved",
      proposal_id: proposalId,
      detail: "denial feeds the agent's persistence rules",
      simulated: true,
    },
  ];
}

// The operator typed real replacement text into the textarea and saved it —
// this DOES change the locally displayed draft (unlike the rest of this
// file). The receipt says exactly that: a browser-local edit, not a
// re-generated draft from a model or the live redraft loop (that bounded,
// server-authoritative path is exercised against the real local API, not
// this static demo — see ActionRail.tsx's actRedraft()).
export function simulateEdit(
  proposalId: string,
  revisionId: string
): DemoLedgerEvent[] {
  return [
    {
      ts: ts(0),
      event: "draft.edit",
      label: "Draft edited",
      proposal_id: proposalId,
      detail: `Edited by operator (simulated, local only) — new revision ${revisionId}`,
      simulated: true,
    },
  ];
}
