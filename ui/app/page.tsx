"use client";

import { useEffect, useState } from "react";
import { TopBar } from "@/components/TopBar";
import { BookView } from "@/components/BookView";
import { QueueView } from "@/components/QueueView";
import { ActionRail } from "@/components/ActionRail";
import { api, AccountSummary, WorkItem } from "@/lib/api";
import { useSweep } from "@/lib/useSweep";

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
  const { sweep, error: sweepError } = useSweep(day, refreshToken);

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

  const needsCount = (sweep?.work_items ?? []).filter(
    (i) => i.proposal?.status === "pending"
  ).length;

  return (
    <div className="app">
      <TopBar
        view={view}
        onViewChange={setView}
        accountCount={accounts?.length ?? null}
        queueCount={needsCount}
        day={day}
        onDayChange={setDay}
        health={health}
      />
      <div className="main">
        <div className="stage">
          {error && <div className="placeholder-view">Error: {error}</div>}
          {view === "book" && (
            <BookView
              accounts={accounts}
              sweep={sweep}
              day={day}
              onWorkQueue={() => setView("queue")}
              onSelectAccount={(accountId) => {
                const item = (sweep?.work_items ?? []).find(
                  (i) => i.account_id === accountId
                );
                if (item?.proposal) setSelectedProposalId(item.proposal.proposal_id);
              }}
            />
          )}
          {view === "queue" && (
            <QueueView
              day={day}
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
              item={selectedItem}
              onVerdict={() => setRefreshToken((t) => t + 1)}
            />
          )}
        </aside>
      </div>
    </div>
  );
}
