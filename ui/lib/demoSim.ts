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

// This demo runs no ActionGate call, verifies no payload hash, and obtains
// no committer receipt — every line below states only what happened in the
// browser: a button click updated local state. Nothing left the tab.
export function simulateApproval(proposalId: string): DemoLedgerEvent[] {
  return [
    {
      ts: ts(0),
      event: "gate.approve",
      label: "Approved",
      proposal_id: proposalId,
      detail: "Approved in this demo — no gate call made",
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
