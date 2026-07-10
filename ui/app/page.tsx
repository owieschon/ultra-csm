"use client";

import { useEffect, useRef, useState } from "react";
import { TopBar } from "@/components/TopBar";
import { BookView } from "@/components/BookView";
import { QueueView } from "@/components/QueueView";
import { ActionRail, ActionRailHandle } from "@/components/ActionRail";
import { CommandPalette } from "@/components/CommandPalette";
import { ShortcutsOverlay } from "@/components/ShortcutsOverlay";
import { api, AccountSummary, isReadOnlyDemo, WorkItem } from "@/lib/api";
import { useSweep } from "@/lib/useSweep";
import { toggleTheme } from "@/lib/theme";

export default function Home() {
  const [view, setView] = useState<"book" | "queue">("book");
  const [day, setDay] = useState(140);
  const [health, setHealth] = useState<"ok" | "degraded" | "checking">(
    "checking"
  );
  const [liveMode, setLiveMode] = useState(false);
  const [healthKnown, setHealthKnown] = useState(false);
  const [accounts, setAccounts] = useState<AccountSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(
    null
  );
  const [selectedItem, setSelectedItem] = useState<WorkItem | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const servedDay = liveMode ? undefined : day;
  const { sweep, error: sweepError } = useSweep(servedDay, refreshToken, healthKnown);
  const railRef = useRef<ActionRailHandle>(null);

  useEffect(() => {
    api
      .health()
      .then((h) => {
        setHealth(h.status === "ok" ? "ok" : "degraded");
        setLiveMode(h.data_plane_mode === "live");
        setHealthKnown(true);
      })
      .catch(() => {
        setHealth("degraded");
        setLiveMode(false);
        setHealthKnown(true);
      });
  }, []);

  useEffect(() => {
    if (!healthKnown) return;
    api
      .accounts(servedDay)
      .then((r) => {
        setAccounts(r.accounts);
        setError(null);
      })
      .catch((e) => setError(String(e)));
  }, [servedDay, healthKnown]);

  const pendingProposalIds = (sweep?.work_items ?? [])
    .filter((i) => i.proposal?.status === "pending")
    .map((i) => i.proposal!.proposal_id);
  const needsCount = pendingProposalIds.length;

  function jumpToAccount(accountId: string) {
    const item = (sweep?.work_items ?? []).find((i) => i.account_id === accountId);
    if (item?.proposal) setSelectedProposalId(item.proposal.proposal_id);
    setView("queue");
  }

  // Keyboard map (Decisions: "ported as-is from the mockup").
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const meta = e.metaKey || e.ctrlKey;
      if (meta && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
        return;
      }
      if (helpOpen) {
        if (e.key === "Escape") setHelpOpen(false);
        return;
      }
      if (paletteOpen) return; // CommandPalette's own input owns Escape/arrows/Enter
      if (e.key === "v") {
        setView((v) => (v === "book" ? "queue" : "book"));
      } else if (e.key === "?") {
        setHelpOpen(true);
      } else if (e.key === "t") {
        toggleTheme();
      } else if (view === "queue") {
        if (e.key === "j" || e.key === "k") {
          e.preventDefault();
          const idx = pendingProposalIds.indexOf(selectedProposalId ?? "");
          const delta = e.key === "j" ? 1 : -1;
          const nextIdx = Math.min(
            Math.max(idx + delta, 0),
            pendingProposalIds.length - 1
          );
          if (pendingProposalIds[nextIdx]) setSelectedProposalId(pendingProposalIds[nextIdx]);
        } else if (e.key === "a") {
          railRef.current?.approve();
        } else if (e.key === "e") {
          railRef.current?.edit();
        } else if (e.key === "d") {
          railRef.current?.deny();
        }
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [view, paletteOpen, helpOpen, pendingProposalIds, selectedProposalId]);

  return (
    <div className="app">
      <TopBar
        view={view}
        onViewChange={setView}
        accountCount={accounts?.length ?? null}
        queueCount={needsCount}
        day={day}
        liveMode={liveMode}
        readOnlyDemo={isReadOnlyDemo}
        onDayChange={setDay}
        health={health}
        onOpenPalette={() => setPaletteOpen(true)}
        onOpenHelp={() => setHelpOpen(true)}
      />
      <div className="main">
        <div className="stage">
          {error && <div className="placeholder-view">Error: {error}</div>}
          {view === "book" && (
            <BookView
              accounts={accounts}
              sweep={sweep}
              day={servedDay}
              onWorkQueue={() => setView("queue")}
              onSelectAccount={jumpToAccount}
            />
          )}
          {view === "queue" && (
            <QueueView
              day={servedDay}
              accounts={accounts}
              sweep={sweep}
              sweepError={sweepError}
              selectedProposalId={selectedProposalId}
              onSelect={setSelectedProposalId}
              onSelectedItemChange={setSelectedItem}
            />
          )}
        </div>
        <aside className="rail">
          {view === "queue" && (
            <ActionRail
              ref={railRef}
              item={selectedItem}
              onVerdict={() => setRefreshToken((t) => t + 1)}
              readOnly={isReadOnlyDemo}
            />
          )}
        </aside>
      </div>
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        accounts={accounts}
        onJumpToAccount={jumpToAccount}
        commands={[
          { label: "Switch to Book view", action: () => setView("book") },
          { label: "Switch to Queue view", action: () => setView("queue") },
          { label: "Toggle theme", action: () => toggleTheme() },
          { label: "Show shortcuts", action: () => setHelpOpen(true) },
        ]}
      />
      <ShortcutsOverlay open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
}
