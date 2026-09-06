"use client";

import { useEffect, useMemo } from "react";
import { AccountSummary, WorkItem } from "@/lib/api";
import { SweepData } from "@/lib/useSweep";
import { QueueLanes, LaneItem } from "@/components/QueueLanes";
import { QueueDetail } from "@/components/QueueDetail";
import { draftFallbackReasonLabel } from "@/lib/labels";
import { ActionRail, ActionRailHandle } from "@/components/ActionRail";
import { DemoApprovalSnapshot, DemoLedgerEvent, DemoVerdict } from "@/lib/demoSim";
import { Ref } from "react";

export function QueueView({
  day,
  accounts,
  sweep,
  sweepError,
  selectedProposalId,
  onSelect,
  onClearSelection,
  onSelectedItemChange,
  onBackToBook,
  railRef,
  onVerdict,
  readOnly,
  demoLedger,
  onDemoVerdict,
  onDemoEdit,
  demoApprovals,
}: {
  day: number | undefined;
  accounts: AccountSummary[] | null;
  sweep: SweepData | null;
  sweepError: string | null;
  selectedProposalId: string | null;
  onSelect: (proposalId: string) => void;
  onClearSelection: () => void;
  onSelectedItemChange: (item: WorkItem | null) => void;
  onBackToBook: () => void;
  railRef: Ref<ActionRailHandle>;
  onVerdict: (item: WorkItem, replacement?: WorkItem) => void;
  readOnly?: boolean;
  demoLedger?: DemoLedgerEvent[];
  onDemoVerdict?: (
    proposalId: string,
    verdict: DemoVerdict | null,
    events: DemoLedgerEvent[],
    snapshot?: { revisionId: string; body: string }
  ) => void;
  onDemoEdit?: (proposalId: string, newBody: string, expectedRevision: string) => void;
  demoApprovals?: Record<string, DemoApprovalSnapshot>;
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
  const fallbacks = (sweep?.work_items ?? [])
    .filter((item) => !item.proposal && item.draft_mode === "template_fallback" && draftFallbackReasonLabel(item.draft_fallback_reason))
    .map((item, index) => ({
      id: `fallback:${JSON.stringify([item.tenant_id, item.account_id ?? index, item.motion, item.recommended_action])}`,
      item,
      accountName: item.account_id ? nameByAccount.get(item.account_id) ?? item.account_id : "Portfolio-wide action",
    }));

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
    ) ?? fallbacks.find((entry) => entry.id === selectedProposalId)?.item ?? null;

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
  const queueClear = sweep != null && needsDecision.length === 0 && fallbacks.length === 0;

  return (
    <div className="queue" data-has-selection={selectedItem || queueClear ? "true" : "false"}>
      <QueueLanes
        needsDecision={needsDecision}
        resolved={resolved}
        fallbacks={fallbacks}
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
            onBack={onClearSelection}
            controls={
              <ActionRail
                key={selectedItem.proposal?.proposal_id ?? selectedProposalId}
                ref={railRef}
                item={selectedItem}
                onVerdict={onVerdict}
                readOnly={readOnly}
                demoLedger={demoLedger}
                onDemoVerdict={onDemoVerdict}
                onDemoEdit={onDemoEdit}
                demoApprovals={demoApprovals}
              />
            }
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
                {needsDecision.length} decisions pending · {fallbacks.length} draft statuses to inspect
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
