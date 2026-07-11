"use client";

import { useEffect, useMemo, useState } from "react";
import { AccountSummary, WorkItem } from "@/lib/api";
import { SweepData } from "@/lib/useSweep";
import { label, MOTION_LABELS, TIER_LABELS } from "@/lib/labels";

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
  highlightAccountId = null,
  onHighlightDone,
  onWorkQueue,
  onSelectAccount,
}: {
  accounts: AccountSummary[] | null;
  sweep: SweepData | null;
  day: number | undefined;
  highlightAccountId?: string | null;
  onHighlightDone?: () => void;
  onWorkQueue: () => void;
  onSelectAccount: (accountId: string) => void;
}) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  // Palette jump to a quiet account: expand its band if the tile is folded
  // behind "+N quiet", scroll it into view, flash it, then clear.
  useEffect(() => {
    if (!highlightAccountId || !accounts) return;
    const tier = accounts.find((a) => a.account_id === highlightAccountId)?.tier;
    // Deliberate: unfold the band so the target tile exists before scrolling.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (tier) setExpanded((e) => ({ ...e, [tier]: true }));
    const raf = requestAnimationFrame(() => {
      document
        .querySelector(`[data-account-id="${highlightAccountId}"]`)
        ?.scrollIntoView({ block: "center", behavior: "smooth" });
    });
    const timer = window.setTimeout(() => onHighlightDone?.(), 2200);
    return () => {
      cancelAnimationFrame(raf);
      window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlightAccountId, accounts]);

  const workItemByAccount = useMemo(() => {
    const map = new Map<string, WorkItem>();
    (sweep?.work_items ?? []).forEach((item) => {
      if (item.account_id) map.set(item.account_id, item);
    });
    return map;
  }, [sweep]);

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
              ? "Book quiet."
              : `Book steady — ${needsCount} need you.`}
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
        <button className="cta" onClick={onWorkQueue} disabled={needsCount === 0}>
          Work the queue{needsCount ? ` (${needsCount})` : ""}
        </button>
      </div>

      <div className="sec">
        <div className="sec-h">
          <span className="t">Lenses</span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {["Adoption", "Risk", "Expansion", "Program"].map((l) => (
            <span
              className="lens"
              key={l}
              title={`lens: ${l.toLowerCase()}`}
            >
              {l}
            </span>
          ))}
          <span className="lens-cap">
            four ways the agent reads the book — each queue item carries the
            lens that surfaced it
          </span>
        </div>
      </div>

      {bands.map((band) => (
        <BandView
          key={band.tier}
          band={band}
          workItemByAccount={workItemByAccount}
          expanded={expanded[band.tier] ?? false}
          highlightAccountId={highlightAccountId}
          onToggleExpand={() =>
            setExpanded((e) => ({ ...e, [band.tier]: !e[band.tier] }))
          }
          onSelectAccount={onSelectAccount}
        />
      ))}
    </div>
  );
}

function BandView({
  band,
  workItemByAccount,
  expanded,
  highlightAccountId,
  onToggleExpand,
  onSelectAccount,
}: {
  band: Band;
  workItemByAccount: Map<string, WorkItem>;
  expanded: boolean;
  highlightAccountId?: string | null;
  onToggleExpand: () => void;
  onSelectAccount: (accountId: string) => void;
}) {
  const hot = band.accounts.filter(
    (a) => workItemByAccount.get(a.account_id)?.proposal?.status === "pending"
  );
  const handled = band.accounts.filter((a) => {
    const status = workItemByAccount.get(a.account_id)?.proposal?.status;
    return status === "approved" || status === "denied";
  });
  // internal_review work items have no gate proposal at all (nothing for a
  // human to approve/deny) -- distinct from "quiet" (no work item fired at
  // all): rendering these as quiet would silently drop a real finding from
  // the wall entirely.
  const internal = band.accounts.filter((a) => {
    const item = workItemByAccount.get(a.account_id);
    return item && !item.proposal;
  });
  const quiet = band.accounts.filter((a) => !workItemByAccount.has(a.account_id));
  const shownQuiet = expanded ? quiet : quiet.slice(0, QUIET_VISIBLE);

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
            data-account-id={a.account_id}
            className={`tile hot${highlightAccountId === a.account_id ? " flash" : ""}`}
            onClick={() => onSelectAccount(a.account_id)}
          >
            <span className="tname">{a.account_name}</span>
            <span className="tsub">
              {label(MOTION_LABELS, workItemByAccount.get(a.account_id)?.motion)}
            </span>
          </button>
        ))}
        {handled.map((a) => (
          <div
            key={a.account_id}
            data-account-id={a.account_id}
            className={`tile handled${highlightAccountId === a.account_id ? " flash" : ""}`}
          >
            <span className="tname">{a.account_name}</span>
            <span className="tdone">
              {workItemByAccount.get(a.account_id)?.proposal?.status === "denied"
                ? "denied"
                : "approved"}
            </span>
          </div>
        ))}
        {internal.map((a) => (
          <div
            key={a.account_id}
            data-account-id={a.account_id}
            className={`tile handled${highlightAccountId === a.account_id ? " flash" : ""}`}
            title={workItemByAccount.get(a.account_id)?.reason}
          >
            <span className="tname">{a.account_name}</span>
            <span className="tsub">internal review · no customer action</span>
          </div>
        ))}
        {shownQuiet.map((a) => (
          <div
            key={a.account_id}
            data-account-id={a.account_id}
            className={`tile quiet${highlightAccountId === a.account_id ? " flash" : ""}`}
            title="Swept today — no trigger fired"
          >
            <span className="tname">{a.account_name}</span>
            <span className="tsub">quiet</span>
          </div>
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
