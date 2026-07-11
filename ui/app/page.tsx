"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { TopBar } from "@/components/TopBar";
import { BookView } from "@/components/BookView";
import { QueueView } from "@/components/QueueView";
import { ActionRail, ActionRailHandle } from "@/components/ActionRail";
import { CommandPalette } from "@/components/CommandPalette";
import { ShortcutsOverlay } from "@/components/ShortcutsOverlay";
import {
  api,
  AccountSummary,
  ApiError,
  demoManifest,
  isReadOnlyDemo,
  WorkItem,
} from "@/lib/api";
import { useSweep } from "@/lib/useSweep";
import { DemoLedgerEvent, DemoVerdict } from "@/lib/demoSim";
import { toggleTheme } from "@/lib/theme";

const INTRO_DISMISSED_KEY = "ucsm-demo-intro-dismissed";

// Plain-English rendering of a load failure (two-register rule: the raw
// error stays in the console, never as the primary label).
function describeError(e: unknown): string {
  if (e instanceof ApiError && e.status === 404) {
    return "Nothing exported for this day — pick a day inside the snapshot window.";
  }
  return "Couldn't reach the data source. The view below may be stale.";
}

export default function Home() {
  const [view, setView] = useState<"book" | "queue">("book");
  const [day, setDay] = useState(140);
  const [dayWindow, setDayWindow] = useState<[number, number] | null>(null);
  const [health, setHealth] = useState<"ok" | "degraded" | "checking">(
    "checking"
  );
  const [liveMode, setLiveMode] = useState(false);
  const [healthKnown, setHealthKnown] = useState(false);
  const [accounts, setAccounts] = useState<AccountSummary[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(
    null
  );
  const [selectedItem, setSelectedItem] = useState<WorkItem | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [highlightAccountId, setHighlightAccountId] = useState<string | null>(
    null
  );
  // Hosted-demo simulation: verdicts + receipt events live client-side only
  // (see lib/demoSim.ts). A reload clears them — that is the honest scope.
  const [demoVerdicts, setDemoVerdicts] = useState<Record<string, DemoVerdict>>(
    {}
  );
  const [demoLedger, setDemoLedger] = useState<DemoLedgerEvent[]>([]);
  const [introDismissed, setIntroDismissed] = useState(true);
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
    if (!isReadOnlyDemo) return;
    // Hydration-safe localStorage read: the static export prerenders with the
    // strip hidden; the client decides after mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIntroDismissed(window.localStorage.getItem(INTRO_DISMISSED_KEY) === "1");
    demoManifest().then((m) => {
      if (!m) return;
      const days = m.days?.length ? m.days : [m.day];
      setDayWindow([Math.min(...days), Math.max(...days)]);
      setDay(m.day);
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
      .catch((e) => setError(e));
  }, [servedDay, healthKnown]);

  // Demo verdicts overlaid on the served sweep so every consumer (book
  // tiles, queue lanes, tab count, rail) sees one consistent state.
  const effectiveSweep = useMemo(() => {
    if (!sweep || Object.keys(demoVerdicts).length === 0) return sweep;
    return {
      ...sweep,
      work_items: sweep.work_items.map((item) => {
        const verdict = item.proposal
          ? demoVerdicts[item.proposal.proposal_id]
          : undefined;
        if (!verdict) return item;
        return {
          ...item,
          proposal: { ...item.proposal!, status: verdict },
        };
      }),
    };
  }, [sweep, demoVerdicts]);

  const pendingProposalIds = (effectiveSweep?.work_items ?? [])
    .filter((i) => i.proposal?.status === "pending")
    .map((i) => i.proposal!.proposal_id);
  const needsCount = pendingProposalIds.length;

  // Entering the queue with nothing selected drops the reader into an empty
  // center pane — land on the top pending item instead.
  useEffect(() => {
    if (view !== "queue") return;
    if (selectedProposalId) return;
    if (pendingProposalIds.length > 0) {
      // Deliberate state write: landing selection, not derived state.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelectedProposalId(pendingProposalIds[0]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, effectiveSweep]);

  function jumpToAccount(accountId: string) {
    const item = (effectiveSweep?.work_items ?? []).find(
      (i) => i.account_id === accountId
    );
    if (item?.proposal) {
      setSelectedProposalId(item.proposal.proposal_id);
      setView("queue");
      return;
    }
    // Quiet account: nothing in the queue for it — land on its tile in the
    // book instead of an unrelated queue selection.
    setView("book");
    setHighlightAccountId(accountId);
  }

  function handleDemoVerdict(
    proposalId: string,
    verdict: DemoVerdict | null,
    events: DemoLedgerEvent[]
  ) {
    if (!verdict) {
      // Revision: draft stays pending, receipt lines land at once.
      setDemoLedger((prev) => [...prev, ...events]);
      return;
    }
    const idx = pendingProposalIds.indexOf(proposalId);
    const remaining = pendingProposalIds.filter((id) => id !== proposalId);
    setDemoVerdicts((prev) => ({ ...prev, [proposalId]: verdict }));
    // The receipt IS the story: hold the resolved item while its ledger
    // lines stream into the rail, then auto-advance (last one clears the
    // selection so the queue composes its payoff state).
    events.forEach((event, i) => {
      window.setTimeout(
        () => setDemoLedger((prev) => [...prev, event]),
        i * 280
      );
    });
    window.setTimeout(() => {
      setSelectedProposalId((current) =>
        current === proposalId
          ? remaining.length === 0
            ? null
            : remaining[Math.min(Math.max(idx, 0), remaining.length - 1)]
          : current
      );
    }, events.length * 280 + 600);
  }

  function dismissIntro() {
    setIntroDismissed(true);
    window.localStorage.setItem(INTRO_DISMISSED_KEY, "1");
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
      const target = e.target;
      if (
        target instanceof HTMLElement &&
        (target.matches("input, textarea, select") || target.isContentEditable)
      ) {
        return;
      }
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

  const pendingAccountIds = useMemo(
    () =>
      new Set(
        (effectiveSweep?.work_items ?? [])
          .filter((i) => i.proposal?.status === "pending" && i.account_id)
          .map((i) => i.account_id as string)
      ),
    [effectiveSweep]
  );

  return (
    <div className="app">
      <TopBar
        view={view}
        onViewChange={setView}
        accountCount={accounts?.length ?? null}
        queueCount={needsCount}
        day={day}
        dayWindow={dayWindow}
        liveMode={liveMode}
        readOnlyDemo={isReadOnlyDemo}
        onDayChange={setDay}
        health={health}
        onOpenPalette={() => setPaletteOpen(true)}
        onOpenHelp={() => setHelpOpen(true)}
      />
      {isReadOnlyDemo && !introDismissed && (
        <div className="intro-strip" role="note">
          <span className="intro-text">
            An agent works this 181-account book continuously. Anything it
            wants to send a customer stops in the queue for your approval —
            decisions here are simulated, nothing is sent.
          </span>
          <button
            type="button"
            className="intro-cta"
            onClick={() => {
              dismissIntro();
              setView("queue");
            }}
          >
            Work the queue
          </button>
          <button
            type="button"
            className="intro-dismiss"
            aria-label="Dismiss intro"
            onClick={dismissIntro}
          >
            ✕
          </button>
        </div>
      )}
      <div className={`main main-${view}`}>
        <div className="stage">
          {error != null && (
            <div className="notice-error" role="alert">
              {describeError(error)}
            </div>
          )}
          {view === "book" && (
            <section
              id="book-panel"
              className="view-panel"
              role="tabpanel"
              aria-labelledby="book-tab"
            >
              <BookView
                accounts={accounts}
                sweep={effectiveSweep}
                day={servedDay}
                highlightAccountId={highlightAccountId}
                onHighlightDone={() => setHighlightAccountId(null)}
                onWorkQueue={() => setView("queue")}
                onSelectAccount={jumpToAccount}
              />
            </section>
          )}
          {view === "queue" && (
            <section
              id="queue-panel"
              className="view-panel"
              role="tabpanel"
              aria-labelledby="queue-tab"
            >
              <QueueView
                day={servedDay}
                accounts={accounts}
                sweep={effectiveSweep}
                sweepError={sweepError ? describeError(sweepError) : null}
                selectedProposalId={selectedProposalId}
                onSelect={setSelectedProposalId}
                onSelectedItemChange={setSelectedItem}
                onBackToBook={() => setView("book")}
              />
            </section>
          )}
        </div>
        <aside className="rail" aria-label="Decision controls and receipt">
          {view === "queue" && (
            <ActionRail
              ref={railRef}
              item={selectedItem}
              onVerdict={() => setRefreshToken((t) => t + 1)}
              readOnly={isReadOnlyDemo}
              demoLedger={demoLedger}
              onDemoVerdict={handleDemoVerdict}
            />
          )}
        </aside>
      </div>
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        accounts={accounts}
        pendingAccountIds={pendingAccountIds}
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
