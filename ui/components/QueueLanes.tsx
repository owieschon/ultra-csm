"use client";

import { WorkItem } from "@/lib/api";
import { label, MOTION_LABELS, TIER_LABELS, TRIGGER_LABELS } from "@/lib/labels";

export interface LaneItem {
  item: WorkItem;
  tier: string | null;
  accountName: string | null;
}

export function QueueLanes({
  needsDecision,
  resolved,
  escalations,
  coveredCount,
  selectedId,
  onSelect,
}: {
  needsDecision: LaneItem[];
  resolved: LaneItem[];
  escalations: Record<string, unknown>[];
  coveredCount: number;
  selectedId: string | null;
  onSelect: (proposalId: string) => void;
}) {
  return (
    <aside className="lanes" aria-label="Decision queue">
      <div className="lane-h">
        <span className="t">Needs your decision</span>
        <span className="c num">{needsDecision.length}</span>
        <span className="badge">needs your approval</span>
      </div>
      {needsDecision.map(({ item, tier, accountName }) => (
        <Row
          key={item.proposal!.proposal_id as unknown as string}
          item={item}
          tier={tier}
          accountName={accountName}
          selected={selectedId === item.proposal!.proposal_id}
          onSelect={onSelect}
        />
      ))}

      <div className="lane-h">
        <span className="t">Resolved this session</span>
        <span className="c num">{resolved.length}</span>
        <span className="badge">verdict recorded · logged</span>
      </div>
      {resolved.map(({ item, tier, accountName }) => (
        <Row
          key={item.proposal!.proposal_id as unknown as string}
          item={item}
          tier={tier}
          accountName={accountName}
          selected={selectedId === item.proposal!.proposal_id}
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
  tier,
  accountName,
  selected,
  onSelect,
  resolved,
}: {
  item: WorkItem;
  tier: string | null;
  accountName: string | null;
  selected: boolean;
  onSelect: (proposalId: string) => void;
  resolved?: boolean;
}) {
  const proposalId = item.proposal?.proposal_id;
  if (!proposalId) return null;
  const trigger = item.priority?.factors?.[0]?.name ?? null;
  const status = item.proposal?.status;
  const packet = item.work_packet ?? null;
  return (
    <button
      type="button"
      className={`row${selected ? " sel" : ""}${resolved ? " resolved" : ""}`}
      aria-pressed={selected}
      onClick={() => onSelect(proposalId)}
    >
      <div className="l1">
        <span className="acct" title={item.account_id ?? undefined}>
          {packet?.account_name ??
            accountName ??
            item.account_id?.slice(0, 8) ??
            "Portfolio-wide action"}
        </span>
        {tier && (
          <span className="tier" title={tier}>
            {label(TIER_LABELS, tier)}
          </span>
        )}
        <span className="score num">{item.priority?.score ?? "—"}</span>
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
        {packet && (
          <span className="motion" title={`${packet.job_type} · ${packet.lane}`}>
            {packet.lane}
          </span>
        )}
        {resolved && status && (
          <span className={`res-chip ${status === "denied" ? "dn" : "ap"}`}>
            {status === "denied" ? "denied" : "approved"}
          </span>
        )}
      </div>
    </button>
  );
}
