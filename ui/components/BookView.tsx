"use client";

import { useMemo, useState } from "react";
import { AccountSummary, WorkItem } from "@/lib/api";
import { SweepData } from "@/lib/useSweep";
import { label, MOTION_LABELS, TIER_LABELS } from "@/lib/labels";
import {
  buildCoverageReceipts,
  COVERAGE_FILTERS,
  CoverageReceipt,
  CoverageState,
} from "@/lib/coverage";

const TIER_ORDER = ["high_touch", "mid_touch", "tech_touch"];
const QUIET_VISIBLE = 6;

interface Band {
  tier: string;
  accounts: AccountSummary[];
  arrCentsSum: number;
}

export function BookView({
  accounts,
  sweep,
  day,
  onWorkQueue,
  onSelectAccount,
}: {
  accounts: AccountSummary[] | null;
  sweep: SweepData | null;
  day: number | undefined;
  onWorkQueue: () => void;
  onSelectAccount: (accountId: string) => void;
}) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [coverageFilter, setCoverageFilter] = useState<CoverageState | "all">("all");
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null);

  const workItemByAccount = useMemo(() => {
    const map = new Map<string, WorkItem>();
    (sweep?.work_items ?? []).forEach((item) => {
      if (item.account_id) map.set(item.account_id, item);
    });
    return map;
  }, [sweep]);
  const coverageReceipts = useMemo(
    () =>
      buildCoverageReceipts({
        accounts: accounts ?? [],
        workItems: sweep?.work_items ?? [],
        sweptAccounts: sweep?.swept_accounts ?? [],
      }),
    [accounts, sweep]
  );
  const coverageByAccount = useMemo(() => {
    const map = new Map<string, CoverageReceipt>();
    coverageReceipts.forEach((receipt) => map.set(receipt.account.account_id, receipt));
    return map;
  }, [coverageReceipts]);
  const coverageCounts = useMemo(() => {
    const counts = new Map<CoverageState | "all", number>([["all", coverageReceipts.length]]);
    coverageReceipts.forEach((receipt) => {
      counts.set(receipt.state, (counts.get(receipt.state) ?? 0) + 1);
    });
    return counts;
  }, [coverageReceipts]);
  const selectedReceipt = selectedAccountId
    ? coverageByAccount.get(selectedAccountId) ?? null
    : coverageReceipts.find((receipt) => receipt.state === "needs_human") ??
      coverageReceipts[0] ??
      null;

  const bands: Band[] = useMemo(() => {
    if (!accounts) return [];
    const byTier = new Map<string, AccountSummary[]>();
    accounts.forEach((a) => {
      const t = a.tier ?? "unknown";
      if (!byTier.has(t)) byTier.set(t, []);
      byTier.get(t)!.push(a);
    });
    const order = [...TIER_ORDER, ...[...byTier.keys()].filter((t) => !TIER_ORDER.includes(t))];
    return order
      .filter((t) => byTier.has(t))
      .map((t) => ({
        tier: t,
        accounts: byTier.get(t)!,
        arrCentsSum: byTier.get(t)!.reduce((sum, a) => sum + (a.arr_cents ?? 0), 0),
      }));
  }, [accounts]);

  const needsCount = [...workItemByAccount.values()].filter(
    (i) => i.proposal?.status === "pending"
  ).length;
  const escalationCount = sweep?.escalations.length ?? 0;

  if (!accounts) {
    return <div className="placeholder-view">Loading book…</div>;
  }

  return (
    <div className="book">
      <div className="bb">
        <div className="txt">
          <h2>
            {needsCount === 0
              ? "Book covered."
              : `Today: ${needsCount} agent-prepared items need you.`}
          </h2>
          <div className="sub">
            <b className="num">{accounts.length}</b> accounts ·{" "}
            {day == null ? (
              <b>live</b>
            ) : (
              <>
                day <b className="num">{day}</b>
              </>
            )}{" "}
            ·{" "}
            <b className="num">{escalationCount}</b> escalations{" "}
            <span className="chip-det" title="Composed from sweep + accounts data by template — no LLM">
              deterministic brief
            </span>
          </div>
        </div>
        <button className="cta" onClick={onWorkQueue} disabled={(sweep?.work_items.length ?? 0) === 0}>
          Work today{needsCount ? ` (${needsCount})` : ""}
        </button>
      </div>

      <div className="coverage-panel">
        <div className="coverage-head">
          <div>
            <div className="eyebrow">Book coverage</div>
            <div className="intro-title">
              {coverageCounts.get("all") ?? 0} accounted for · {coverageCounts.get("covered") ?? 0} covered ·{" "}
              {(coverageCounts.get("source_degraded") ?? 0) + (coverageCounts.get("not_scanned") ?? 0)} need source review
            </div>
          </div>
          <span className="chip-det">prioritization is filterable, not hidden</span>
          {(sweep?.degraded_items ?? 0) > 0 && (
            <span className="chip-llm">{sweep?.degraded_items} degraded</span>
          )}
        </div>
        <div className="coverage-filters">
          {COVERAGE_FILTERS.map((filter) => (
            <button
              key={filter.key}
              className={`coverage-filter${coverageFilter === filter.key ? " on" : ""}`}
              onClick={() => setCoverageFilter(filter.key)}
            >
              <span>{filter.label}</span>
              <span className="num">{coverageCounts.get(filter.key) ?? 0}</span>
            </button>
          ))}
        </div>
        {selectedReceipt && (
          <CoverageReceiptCard
            receipt={selectedReceipt}
            onOpenPacket={() => {
              if (selectedReceipt.workItem?.account_id) {
                onSelectAccount(selectedReceipt.workItem.account_id);
                onWorkQueue();
              }
            }}
          />
        )}
      </div>

      <div className="sec">
        <div className="sec-h">
          <span className="t">Lenses</span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <span className="lens" title="lens: adoption">
            Adoption
          </span>
          {["Risk", "Expansion", "Program"].map((l) => (
            <span
              className="lens"
              key={l}
              title={`lens: ${l.toLowerCase()}`}
            >
              {l}
            </span>
          ))}
        </div>
      </div>

      {bands.map((band) => (
        <BandView
          key={band.tier}
          band={band}
          workItemByAccount={workItemByAccount}
          coverageByAccount={coverageByAccount}
          coverageFilter={coverageFilter}
          expanded={expanded[band.tier] ?? false}
          onToggleExpand={() =>
            setExpanded((e) => ({ ...e, [band.tier]: !e[band.tier] }))
          }
          onSelectAccount={setSelectedAccountId}
          onOpenPacket={(accountId) => {
            onSelectAccount(accountId);
            onWorkQueue();
          }}
        />
      ))}
    </div>
  );
}

function BandView({
  band,
  workItemByAccount,
  coverageByAccount,
  coverageFilter,
  expanded,
  onToggleExpand,
  onSelectAccount,
  onOpenPacket,
}: {
  band: Band;
  workItemByAccount: Map<string, WorkItem>;
  coverageByAccount: Map<string, CoverageReceipt>;
  coverageFilter: CoverageState | "all";
  expanded: boolean;
  onToggleExpand: () => void;
  onSelectAccount: (accountId: string) => void;
  onOpenPacket: (accountId: string) => void;
}) {
  const accounts =
    coverageFilter === "all"
      ? band.accounts
      : band.accounts.filter((a) => coverageByAccount.get(a.account_id)?.state === coverageFilter);
  const hot = accounts.filter(
    (a) => workItemByAccount.get(a.account_id)?.proposal?.status === "pending"
  );
  const handled = accounts.filter((a) => {
    const status = workItemByAccount.get(a.account_id)?.proposal?.status;
    return status === "approved" || status === "denied";
  });
  // internal_review work items have no gate proposal at all (nothing for a
  // human to approve/deny) -- distinct from "quiet" (no work item fired at
  // all): rendering these as quiet would silently drop a real finding from
  // the wall entirely.
  const internal = accounts.filter((a) => {
    const item = workItemByAccount.get(a.account_id);
    return item && !item.proposal;
  });
  const quiet = accounts.filter((a) => !workItemByAccount.has(a.account_id));
  const shownQuiet = expanded ? quiet : quiet.slice(0, QUIET_VISIBLE);

  if (accounts.length === 0) return null;

  return (
    <div className="band" style={{ marginBottom: 22 }}>
      <div className="band-h">
        <span className="bt">{label(TIER_LABELS, band.tier)}</span>
        <span className="bstats">
          <b className="num">{band.accounts.length}</b> accounts ·{" "}
          <b>${(band.arrCentsSum / 100).toLocaleString()}</b> ARR
        </span>
        <span className={`bneeds${hot.length === 0 ? " zero" : ""}`}>
          {hot.length === 0 ? "✓ nothing needs you" : `${hot.length} need you`}
        </span>
      </div>
      <div className="grid">
        {hot.map((a) => (
          <button
            key={a.account_id}
            className="tile hot"
            onClick={() => onSelectAccount(a.account_id)}
          >
            <span className="tname">{a.account_name}</span>
            <span className="tsub">
              {coverageByAccount.get(a.account_id)?.label ?? label(MOTION_LABELS, workItemByAccount.get(a.account_id)?.motion)}
            </span>
          </button>
        ))}
        {handled.map((a) => (
          <button
            key={a.account_id}
            className="tile handled"
            onClick={() => onSelectAccount(a.account_id)}
          >
            <span className="tname">{a.account_name}</span>
            <span className="tdone">
              {workItemByAccount.get(a.account_id)?.proposal?.status === "denied"
                ? "denied"
                : "sent"}
            </span>
          </button>
        ))}
        {internal.map((a) => (
          <button
            key={a.account_id}
            className="tile handled"
            title={workItemByAccount.get(a.account_id)?.reason}
            onClick={() => onOpenPacket(a.account_id)}
          >
            <span className="tname">{a.account_name}</span>
            <span className="tsub">{coverageByAccount.get(a.account_id)?.label ?? "prepared work"}</span>
          </button>
        ))}
        {shownQuiet.map((a) => (
          <button
            key={a.account_id}
            className={`tile quiet coverage-${coverageByAccount.get(a.account_id)?.state ?? "covered"}`}
            title={coverageByAccount.get(a.account_id)?.reason ?? "Swept today — no trigger fired"}
            onClick={() => onSelectAccount(a.account_id)}
          >
            <span className="tname">{a.account_name}</span>
            <span className="tsub">{coverageByAccount.get(a.account_id)?.label ?? "covered"}</span>
          </button>
        ))}
        {quiet.length > QUIET_VISIBLE && (
          <button className="tile more" onClick={onToggleExpand}>
            {expanded ? "show less" : `+${quiet.length - QUIET_VISIBLE} quiet`}
          </button>
        )}
      </div>
    </div>
  );
}

function CoverageReceiptCard({
  receipt,
  onOpenPacket,
}: {
  receipt: CoverageReceipt;
  onOpenPacket: () => void;
}) {
  return (
    <div className={`coverage-receipt coverage-${receipt.state}`}>
      <div className="receipt-main">
        <div>
          <div className="receipt-state">{receipt.label}</div>
          <div className="receipt-name">{receipt.account.account_name}</div>
          <div className="receipt-reason">{receipt.reason}</div>
        </div>
        <div className="receipt-score num">{receipt.scoreLabel}</div>
      </div>
      <div className="receipt-lines">
        {receipt.evidenceLines.map((line) => (
          <span key={line}>{line}</span>
        ))}
        {receipt.missingLines.map((line) => (
          <span key={line} className="warn-line">
            {line}
          </span>
        ))}
      </div>
      <div className="receipt-actions">
        <span className="chip-det">coverage receipt</span>
        {receipt.workItem && (
          <button className="mini-cta" onClick={onOpenPacket}>
            {receipt.actionLabel}
          </button>
        )}
      </div>
    </div>
  );
}
