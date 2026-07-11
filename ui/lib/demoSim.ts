// Hosted read-only demo: the backend accepts no writes, so decisions are
// simulated CLIENT-SIDE ONLY — nothing is sent, nothing persists past a
// reload. Every simulated receipt line carries simulated: true and renders
// with an explicit "sim" mark (honesty register: the demo performs the
// product story without claiming backend state it never created).
import { LedgerEvent } from "@/lib/api";

export type DemoVerdict = "approved" | "denied";

export interface DemoLedgerEvent extends LedgerEvent {
  simulated: true;
}

function ts(offsetSeconds: number): string {
  const d = new Date(Date.now() + offsetSeconds * 1000);
  return d.toISOString();
}

function simId(): string {
  return Math.random().toString(16).slice(2, 10);
}

export function simulateApproval(proposalId: string): DemoLedgerEvent[] {
  const messageId = `sim-${simId()}`;
  return [
    {
      ts: ts(0),
      event: "gate.approve",
      label: "Approved",
      proposal_id: proposalId,
      detail: "human verdict recorded — exact payload authorized",
      simulated: true,
    },
    {
      ts: ts(1),
      event: "committer.commit",
      label: "Committed",
      proposal_id: proposalId,
      detail: "payload-bound release through the gate",
      simulated: true,
    },
    {
      ts: ts(2),
      event: "send.receipt",
      label: "Email sent",
      proposal_id: proposalId,
      detail: `message-id ${messageId}`,
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

// No live model runs in this snapshot, so the draft text cannot actually
// change — the receipt records the instruction without claiming a redraft
// that never happened.
export function simulateRevision(
  proposalId: string,
  instruction: string
): DemoLedgerEvent[] {
  return [
    {
      ts: ts(0),
      event: "slot_b.revise",
      label: "Edit recorded",
      proposal_id: proposalId,
      detail: `"${instruction.slice(0, 60)}" — the live system redrafts under it; snapshot draft unchanged`,
      simulated: true,
    },
  ];
}
