import { ProposalSummary, WorkItem } from "./api";

// The proposal list is authoritative even when a sweep still returns the old draft.
export function replacementItem(item: WorkItem, id: string, proposals: ProposalSummary[]): WorkItem {
  const original = proposals.find((p) => p.proposal_id === item.proposal?.proposal_id);
  const next = proposals.find((p) => p.proposal_id === id);
  if (!original || !next || original.status !== "denied" || next.status !== "pending") {
    throw new Error("Replacement is unavailable or no longer pending.");
  }
  const before = original.payload;
  const after = next.payload;
  const chain = after.revise_chain as { parent_proposal_id?: string } | undefined;
  const ids = (value: unknown): string | null => Array.isArray(value) && value.every((v) => typeof v === "string")
    ? JSON.stringify([...new Set(value)].sort()) : null;
  if (before.account_id !== item.account_id ||
      ["account_id", "contact_id", "contact_email"].some((key) => typeof before[key] !== "string" || before[key] !== after[key]) ||
      original.intent !== next.intent || original.action !== next.action ||
      original.autonomy_tier !== next.autonomy_tier || original.required_permission !== next.required_permission ||
      ids(before.evidence_ids) === null || ids(before.evidence_ids) !== ids(after.evidence_ids) ||
      chain?.parent_proposal_id !== original.proposal_id ||
      typeof after.body !== "string" || !after.body.trim()) {
    throw new Error("Replacement does not preserve the proposal's recipient, evidence, or authority.");
  }
  return {
    ...item,
    replacement_proposal_id: undefined,
    redrafted_from: original.proposal_id,
    proposal: { ...item.proposal!, proposal_id: next.proposal_id, status: "pending" },
    customer_draft: after.body,
    work_packet: item.work_packet ? {
      ...item.work_packet,
      prepared_artifact: { ...item.work_packet.prepared_artifact, body: after.body },
    } : item.work_packet,
  };
}
