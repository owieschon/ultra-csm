"use client";

import { useEffect, useState } from "react";
import { TopBar } from "@/components/TopBar";
import { QueueView } from "@/components/QueueView";
import { ActionRail } from "@/components/ActionRail";
import { api, AccountSummary, WorkItem } from "@/lib/api";

export default function Home() {
  const [view, setView] = useState<"book" | "queue">("book");
  const [day, setDay] = useState(140);
  const [health, setHealth] = useState<"ok" | "degraded" | "checking">(
    "checking"
  );
  const [accounts, setAccounts] = useState<AccountSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(
    null
  );
  const [selectedItem, setSelectedItem] = useState<WorkItem | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    api
      .health()
      .then((h) => setHealth(h.status === "ok" ? "ok" : "degraded"))
      .catch(() => setHealth("degraded"));
  }, []);

  useEffect(() => {
    setError(null);
    api
      .accounts(day)
      .then((r) => setAccounts(r.accounts))
      .catch((e) => setError(String(e)));
  }, [day]);

  return (
    <div className="app">
      <TopBar
        view={view}
        onViewChange={setView}
        accountCount={accounts?.length ?? null}
        queueCount={0}
        day={day}
        onDayChange={setDay}
        health={health}
      />
      <div className="main">
        <div className="stage">
          {error && <div className="placeholder-view">Error: {error}</div>}
          {view === "book" && (
            <div className="placeholder-view" data-testid="book-view">
              Book view — {accounts?.length ?? "…"} accounts loaded from{" "}
              <code className="mono">GET /accounts?day={day}</code>. Tier
              bands land in Phase 4.
            </div>
          )}
          {view === "queue" && (
            <QueueView
              day={day}
              accounts={accounts}
              selectedProposalId={selectedProposalId}
              onSelect={setSelectedProposalId}
              onSelectedItemChange={setSelectedItem}
              refreshToken={refreshToken}
            />
          )}
        </div>
        <aside className="rail">
          {view === "queue" && (
            <ActionRail
              item={selectedItem}
              onVerdict={() => setRefreshToken((t) => t + 1)}
            />
          )}
        </aside>
      </div>
    </div>
  );
}
