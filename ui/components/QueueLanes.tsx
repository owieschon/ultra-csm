"use client";

import { CSMWorkPacket, WorkItem } from "@/lib/api";

export interface LaneItem {
  item: WorkItem | null;
  packet: CSMWorkPacket;
  tier: string | null;
}

export function QueueLanes({
  needsJudgment,
  prepared,
  wholeBook,
  selectedId,
  onSelect,
}: {
  needsJudgment: LaneItem[];
  prepared: LaneItem[];
  wholeBook: LaneItem[];
  selectedId: string | null;
  onSelect: (packetId: string) => void;
}) {
  return (
    <aside className="lanes">
      <LaneSection
        title="Needs judgment"
        badge="human decision"
        items={needsJudgment}
        selectedId={selectedId}
        onSelect={onSelect}
      />
      <LaneSection
        title="Prepared work"
        badge="ready to inspect"
        items={prepared}
        selectedId={selectedId}
        onSelect={onSelect}
      />
      <LaneSection
        title="Whole book"
        badge="covered / blocked"
        items={wholeBook}
        selectedId={selectedId}
        onSelect={onSelect}
        limit={40}
      />
    </aside>
  );
}

function LaneSection({
  title,
  badge,
  items,
  selectedId,
  onSelect,
  limit,
}: {
  title: string;
  badge: string;
  items: LaneItem[];
  selectedId: string | null;
  onSelect: (packetId: string) => void;
  limit?: number;
}) {
  const shown = typeof limit === "number" ? items.slice(0, limit) : items;
  return (
    <>
      <div className="lane-h">
        <span className="t">{title}</span>
        <span className="c num">{items.length}</span>
        <span className="badge">{badge}</span>
      </div>
      {shown.length === 0 && (
        <div className="row muted-row">none in this lane</div>
      )}
      {shown.map(({ item, packet, tier }) => (
        <Row
          key={packet.packet_id}
          item={item}
          packet={packet}
          tier={tier}
          selected={selectedId === packet.packet_id}
          onSelect={onSelect}
        />
      ))}
      {limit && items.length > shown.length && (
        <div className="row muted-row">{items.length - shown.length} more covered accounts</div>
      )}
    </>
  );
}

function Row({
  item,
  packet,
  tier,
  selected,
  onSelect,
}: {
  item: WorkItem | null;
  packet: CSMWorkPacket;
  tier: string | null;
  selected: boolean;
  onSelect: (packetId: string) => void;
}) {
  const score = item?.priority?.score;
  return (
    <button
      className={`row${selected ? " sel" : ""} packet-${packet.lane}`}
      onClick={() => onSelect(packet.packet_id)}
      title={packet.bucket_trace.rule_label}
    >
      <div className="l1">
        <span className="acct">{packet.account_name}</span>
        {tier && <span className="tier">{tier.replace(/_/g, " ")}</span>}
        {typeof score === "number" && <span className="score num">{score}</span>}
      </div>
      <div className="l2">
        <span className="trig">{packet.primary_next_step}</span>
      </div>
      <div className="packet-row-meta">
        <span>{packet.job_type.replace(/_/g, " ")}</span>
        <span>{packet.cadence.replace(/_/g, " ")}</span>
        <span>{Math.round(packet.confidence * 100)}%</span>
      </div>
    </button>
  );
}
