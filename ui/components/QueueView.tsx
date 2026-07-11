"use client";

import { useEffect, useMemo } from "react";
import { AccountSummary, WorkItem } from "@/lib/api";
import { SweepData } from "@/lib/useSweep";
import { QueueLanes, LaneItem } from "@/components/QueueLanes";
import { QueueDetail } from "@/components/QueueDetail";

export function QueueView({
  day,
  accounts,
  sweep,
  sweepError,
  selectedProposalId,
  onSelect,
  onSelectedItemChange,
  onBackToBook,
}: {
  day: number | undefined;
  accounts: AccountSummary[] | null;
  sweep: SweepData | null;
  sweepError: string | null;
  selectedProposalId: string | null;
  onSelect: (proposalId: string) => void;
  onSelectedItemChange: (item: WorkItem | null) => void;
  onBackToBook: () => void;
}) {
  const tierByAccount = useMemo(() => {
    const map = new Map<string, string | null>();
    (accounts ?? []).forEach((a) => map.set(a.account_id, a.tier));
    return map;
  }, [accounts]);

  const nameByAccount = useMemo(() => {
    const map = new Map<string, string>();
    (accounts ?? []).forEach((a) => map.set(a.account_id, a.account_name));
    return map;
  }, [accounts]);

  const withProposal = (sweep?.work_items ?? []).filter((i) => i.proposal);
  const needsDecision: LaneItem[] = withProposal
    .filter((i) => i.proposal!.status === "pending")
    .map((item) => ({
      item,
      tier: item.account_id ? tierByAccount.get(item.account_id) ?? null : null,
      accountName: item.account_id ? nameByAccount.get(item.account_id) ?? null : null,
    }));
  const resolved: LaneItem[] = withProposal
    .filter((i) => i.proposal!.status !== "pending")
    .map((item) => ({
      item,
      tier: item.account_id ? tierByAccount.get(item.account_id) ?? null : null,
      accountName: item.account_id ? nameByAccount.get(item.account_id) ?? null : null,
    }));

  const coveredCount = Math.max(
    0,
    (sweep?.swept_accounts.length ?? 0) -
      new Set((sweep?.work_items ?? []).map((i) => i.account_id).filter(Boolean)).size
  );

  const selectedItem =
    (sweep?.work_items ?? []).find(
      (i) => i.proposal?.proposal_id === selectedProposalId
    ) ?? null;

  useEffect(() => {
    onSelectedItemChange(selectedItem);
    // onSelectedItemChange is a setState setter passed from the parent
    // (stable identity); only the derived item itself should retrigger this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedItem]);

  if (sweepError) {
    return (
      <div className="notice-error" role="alert">
        {sweepError}
      </div>
    );
  }

  // The goal state of this screen is emptiness — when the last decision
  // resolves, that moment is composed deliberately (UI_DESIGN_BRIEF's
  // designed empty state), not left as a generic "select an item".
  const queueClear = sweep != null && needsDecision.length === 0;

  return (
    <div className="queue">
      <QueueLanes
        needsDecision={needsDecision}
        resolved={resolved}
        escalations={sweep?.escalations ?? []}
        coveredCount={coveredCount}
        selectedId={selectedProposalId}
        onSelect={onSelect}
      />
      <main className="col detail">
        {selectedItem ? (
          <QueueDetail
            key={`${selectedItem.account_id ?? "program"}:${day ?? "live"}`}
            item={selectedItem}
            day={day}
          />
        ) : queueClear ? (
          <div className="empty payoff">
            <div className="payoff-check" aria-hidden="true">
              ✓
            </div>
            <h2>Queue clear.</h2>
            <div className="sub">
              <span className="mono">
                0 decisions pending · agent operating
              </span>
              <br />
              {resolved.length > 0
                ? `${resolved.length} resolved this session · ${coveredCount} accounts covered with no action needed.`
                : `${coveredCount} accounts covered with no action needed.`}
            </div>
            <button type="button" className="cta" onClick={onBackToBook}>
              Back to a quiet book
            </button>
          </div>
        ) : (
          <div className="empty">
            <h2>
              {sweep ? "Select an item from the queue" : "Loading sweep…"}
            </h2>
            {sweep && (
              <div className="sub">
                {needsDecision.length} need you · {coveredCount} covered, no
                action needed
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
