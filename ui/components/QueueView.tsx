"use client";

import { useEffect, useMemo, useState } from "react";
import { api, AccountSummary, WorkItem } from "@/lib/api";
import { QueueLanes, LaneItem } from "@/components/QueueLanes";
import { QueueDetail } from "@/components/QueueDetail";

export function QueueView({
  day,
  accounts,
  selectedProposalId,
  onSelect,
  onSelectedItemChange,
  refreshToken,
}: {
  day: number;
  accounts: AccountSummary[] | null;
  selectedProposalId: string | null;
  onSelect: (proposalId: string) => void;
  onSelectedItemChange: (item: WorkItem | null) => void;
  refreshToken: number;
}) {
  const [sweep, setSweep] = useState<{
    work_items: WorkItem[];
    escalations: Record<string, unknown>[];
    swept_accounts: string[];
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    api
      .sweep(day)
      .then((r) =>
        setSweep({
          work_items: r.work_items,
          escalations: r.escalations,
          swept_accounts: r.swept_accounts,
        })
      )
      .catch((e) => setError(String(e)));
  }, [day, refreshToken]);

  const tierByAccount = useMemo(() => {
    const map = new Map<string, string | null>();
    (accounts ?? []).forEach((a) => map.set(a.account_id, a.tier));
    return map;
  }, [accounts]);

  const withProposal = (sweep?.work_items ?? []).filter((i) => i.proposal);
  const needsDecision: LaneItem[] = withProposal
    .filter((i) => i.proposal!.status === "pending")
    .map((item) => ({ item, tier: item.account_id ? tierByAccount.get(item.account_id) ?? null : null }));
  const resolved: LaneItem[] = withProposal
    .filter((i) => i.proposal!.status !== "pending")
    .map((item) => ({ item, tier: item.account_id ? tierByAccount.get(item.account_id) ?? null : null }));

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

  if (error) {
    return <div className="placeholder-view">Error: {error}</div>;
  }

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
          <QueueDetail item={selectedItem} day={day} />
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
