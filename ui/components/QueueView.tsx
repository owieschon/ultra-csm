"use client";

import { useEffect, useMemo } from "react";
import { AccountSummary, WorkItem } from "@/lib/api";
import { SweepData } from "@/lib/useSweep";
import { QueueLanes, LaneItem } from "@/components/QueueLanes";
import { QueueDetail } from "@/components/QueueDetail";
import { workItemKey } from "@/lib/work";

export function QueueView({
  day,
  accounts,
  sweep,
  sweepError,
  selectedProposalId,
  onSelect,
  onSelectedItemChange,
}: {
  day: number | undefined;
  accounts: AccountSummary[] | null;
  sweep: SweepData | null;
  sweepError: string | null;
  selectedProposalId: string | null;
  onSelect: (proposalId: string) => void;
  onSelectedItemChange: (item: WorkItem | null) => void;
}) {
  const tierByAccount = useMemo(() => {
    const map = new Map<string, string | null>();
    (accounts ?? []).forEach((a) => map.set(a.account_id, a.tier));
    return map;
  }, [accounts]);
  const accountNameById = useMemo(() => {
    const map = new Map<string, string>();
    (accounts ?? []).forEach((a) => map.set(a.account_id, a.account_name));
    return map;
  }, [accounts]);

  const laneItem = (item: WorkItem): LaneItem => ({
    item,
    accountName: item.account_id ? accountNameById.get(item.account_id) ?? null : null,
    tier: item.account_id ? tierByAccount.get(item.account_id) ?? null : null,
  });
  const workItems = sweep?.work_items ?? [];
  const withProposal = workItems.filter((i) => i.proposal);
  const needsDecision: LaneItem[] = withProposal
    .filter((i) => i.proposal!.status === "pending")
    .map(laneItem);
  const prepared: LaneItem[] = workItems
    .filter((i) => !i.proposal)
    .map(laneItem);
  const resolved: LaneItem[] = withProposal
    .filter((i) => i.proposal!.status !== "pending")
    .map(laneItem);
  const defaultItem =
    needsDecision[0]?.item ?? prepared[0]?.item ?? resolved[0]?.item ?? null;
  const defaultSelectedId = defaultItem ? workItemKey(defaultItem) : null;
  const effectiveSelectedId = selectedProposalId ?? defaultSelectedId;

  const coveredCount = Math.max(
    0,
    (sweep?.swept_accounts.length ?? 0) -
      new Set(workItems.map((i) => i.account_id).filter(Boolean)).size
  );

  const selectedItem =
    workItems.find((i) => workItemKey(i) === effectiveSelectedId) ??
    workItems.find((i) => i.proposal?.proposal_id === effectiveSelectedId) ??
    defaultItem ??
    null;

  useEffect(() => {
    onSelectedItemChange(selectedItem);
    // onSelectedItemChange is a setState setter passed from the parent
    // (stable identity); only the derived item itself should retrigger this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedItem]);

  if (sweepError) {
    return <div className="placeholder-view">Error: {sweepError}</div>;
  }

  return (
    <div className="queue">
      <QueueLanes
        needsDecision={needsDecision}
        prepared={prepared}
        resolved={resolved}
        escalations={sweep?.escalations ?? []}
        coveredCount={coveredCount}
        selectedId={effectiveSelectedId}
        onSelect={onSelect}
      />
      <main className="col detail">
        {selectedItem ? (
          <QueueDetail item={selectedItem} day={day} />
        ) : (
          <div className="empty">
            <h2>
              {sweep ? "Select an item from the queue" : "Loading sweep…"}
            </h2>
            {sweep && (
              <div className="sub">
                {needsDecision.length} need approval · {prepared.length} prepared without a send · {coveredCount} covered
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
