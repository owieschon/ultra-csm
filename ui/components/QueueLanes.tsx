"use client";

import { WorkItem } from "@/lib/api";
import { label, MOTION_LABELS, TIER_LABELS, TRIGGER_LABELS } from "@/lib/labels";
import { describeWork, workItemKey } from "@/lib/work";

export interface LaneItem {
  item: WorkItem;
  accountName: string | null;
  tier: string | null;
}

export function QueueLanes({
  needsDecision,
  prepared,
  resolved,
  escalations,
  coveredCount,
  selectedId,
  onSelect,
}: {
  needsDecision: LaneItem[];
  prepared: LaneItem[];
  resolved: LaneItem[];
  escalations: Record<string, unknown>[];
  coveredCount: number;
  selectedId: string | null;
  onSelect: (proposalId: string) => void;
}) {
  return (
    <aside className="lanes">
      <div className="lane-intro">
        <div className="eyebrow">CSM operating cadence</div>
        <div className="intro-title">Today&apos;s agent work</div>
        <div className="intro-sub">
          Daily, weekly, and event-driven packets prepared from the book sweep.
        </div>
      </div>
      <div className="lane-h">
        <span className="t">Needs judgment</span>
        <span className="c num">{needsDecision.length}</span>
        <span className="badge">approval gate</span>
      </div>
      {needsDecision.map(({ item, tier, accountName }) => (
        <Row
          key={workItemKey(item)}
          item={item}
          accountName={accountName}
          tier={tier}
          selected={selectedId === workItemKey(item)}
          onSelect={onSelect}
        />
      ))}

      <div className="lane-h">
        <span className="t">Prepared work</span>
        <span className="c num">{prepared.length}</span>
        <span className="badge">no customer send</span>
      </div>
      {prepared.map(({ item, tier, accountName }) => (
        <Row
          key={workItemKey(item)}
          item={item}
          accountName={accountName}
          tier={tier}
          selected={selectedId === workItemKey(item)}
          onSelect={onSelect}
        />
      ))}
      {prepared.length === 0 && (
        <div className="row note">
          no internal-only work this sweep
        </div>
      )}

      <div className="lane-h">
        <span className="t">Completed this run</span>
        <span className="c num">{resolved.length}</span>
        <span className="badge">approved/denied · logged</span>
      </div>
      {resolved.map(({ item, tier, accountName }) => (
        <Row
          key={workItemKey(item)}
          item={item}
          accountName={accountName}
          tier={tier}
          selected={selectedId === workItemKey(item)}
          onSelect={onSelect}
          resolved
        />
      ))}

      <div className="lane-h">
        <span className="t">Escalations</span>
        <span className="c num">{escalations.length}</span>
        <span className="badge">need judgment</span>
      </div>
      {escalations.length === 0 && (
        <div className="row" style={{ color: "var(--fg-2)", fontSize: 12 }}>
          none this sweep
        </div>
      )}

      <div className="lane-h">
        <span className="t">Covered — no action</span>
        <span className="c num">{coveredCount}</span>
        <span className="badge">receipts</span>
      </div>
    </aside>
  );
}

function Row({
  item,
  accountName,
  tier,
  selected,
  onSelect,
  resolved,
}: {
  item: WorkItem;
  accountName: string | null;
  tier: string | null;
  selected: boolean;
  onSelect: (proposalId: string) => void;
  resolved?: boolean;
}) {
  const trigger = item.priority?.factors?.[0]?.name ?? null;
  const status = item.proposal?.status;
  const descriptor = describeWork(item);
  const key = workItemKey(item);
  return (
    <button
      className={`row${selected ? " sel" : ""}${resolved ? " resolved" : ""}`}
      onClick={() => onSelect(key)}
    >
      <div className="l1">
        <span className="acct">{accountName ?? item.account_id?.slice(0, 8) ?? "program"}</span>
        {tier && (
          <span className="tier" title={tier}>
            {label(TIER_LABELS, tier)}
          </span>
        )}
        <span className="score num">{item.priority?.score ?? "—"}</span>
      </div>
      <div className="l2">
        <span className={`cadence ${descriptor.cadence}`}>{descriptor.cadenceLabel}</span>
        <span className="motion">{descriptor.kindLabel}</span>
      </div>
      <div className="l2">
        {trigger && (
          <span className="trig" title={trigger}>
            {label(TRIGGER_LABELS, trigger)}
          </span>
        )}
        {item.motion && (
          <span className="motion" title={item.motion}>
            {label(MOTION_LABELS, item.motion)}
          </span>
        )}
        {!item.proposal && (
          <span className="res-chip ap">prepared</span>
        )}
        {resolved && status && (
          <span className={`res-chip ${status === "denied" ? "dn" : "ap"}`}>
            {status === "denied" ? "denied" : "sent"}
          </span>
        )}
      </div>
    </button>
  );
}
