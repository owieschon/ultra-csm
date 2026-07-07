"use client";

import { useEffect, useMemo } from "react";
import { AccountSummary, CSMWorkPacket, WorkItem } from "@/lib/api";
import { SweepData } from "@/lib/useSweep";
import { QueueLanes, LaneItem } from "@/components/QueueLanes";
import { QueueDetail } from "@/components/QueueDetail";

export interface QueueSelection {
  item: WorkItem | null;
  packet: CSMWorkPacket;
}

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
  onSelect: (packetId: string) => void;
  onSelectedItemChange: (selection: QueueSelection | null) => void;
}) {
  const tierByAccount = useMemo(() => {
    const map = new Map<string, string | null>();
    (accounts ?? []).forEach((a) => map.set(a.account_id, a.tier));
    return map;
  }, [accounts]);

  const workEntries: LaneItem[] = useMemo(
    () =>
      (sweep?.work_items ?? [])
        .filter((item) => item.work_packet)
        .map((item) => ({
          item,
          packet: item.work_packet!,
          tier: item.account_id ? tierByAccount.get(item.account_id) ?? null : null,
        })),
    [sweep?.work_items, tierByAccount]
  );
  const coverageEntries: LaneItem[] = useMemo(
    () =>
      (sweep?.coverage_packets ?? []).map((packet) => ({
        item: null,
        packet,
        tier: packet.account_id ? tierByAccount.get(packet.account_id) ?? null : null,
      })),
    [sweep?.coverage_packets, tierByAccount]
  );
  const needsJudgment = useMemo(
    () => workEntries.filter(({ packet }) => packet.lane === "needs_judgment" || packet.lane === "blocked"),
    [workEntries]
  );
  const prepared = useMemo(
    () => workEntries.filter(({ packet }) => packet.lane !== "needs_judgment" && packet.lane !== "blocked"),
    [workEntries]
  );
  const wholeBook = coverageEntries;

  const selectedEntry = useMemo(
    () =>
      [...workEntries, ...coverageEntries].find(
        ({ packet }) => packet.packet_id === selectedProposalId
      ) ?? null,
    [workEntries, coverageEntries, selectedProposalId]
  );

  useEffect(() => {
    onSelectedItemChange(selectedEntry ? { item: selectedEntry.item, packet: selectedEntry.packet } : null);
    // onSelectedItemChange is a setState setter passed from the parent
    // (stable identity); only the derived item itself should retrigger this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedEntry]);

  if (sweepError) {
    return <div className="placeholder-view">Error: {sweepError}</div>;
  }

  return (
    <div className="queue">
      <QueueLanes
        needsJudgment={needsJudgment}
        prepared={prepared}
        wholeBook={wholeBook}
        selectedId={selectedProposalId}
        onSelect={onSelect}
      />
      <main className="col detail">
        {selectedEntry ? (
          <QueueDetail item={selectedEntry.item} packet={selectedEntry.packet} day={day} />
        ) : (
          <div className="empty">
            <h2>
              {sweep ? "Select an item from the queue" : "Loading sweep…"}
            </h2>
            {sweep && (
              <div className="sub">
                {needsJudgment.length} need judgment · {wholeBook.length} whole-book packets
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
