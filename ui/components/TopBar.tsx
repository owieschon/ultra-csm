"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { toggleTheme as toggleThemeUtil } from "@/lib/theme";

type View = "book" | "queue";

export function TopBar({
  view,
  onViewChange,
  accountCount,
  queueCount,
  day,
  liveMode,
  readOnlyDemo,
  onDayChange,
  health,
  onOpenPalette,
  onOpenHelp,
}: {
  view: View;
  onViewChange: (v: View) => void;
  accountCount: number | null;
  queueCount: number;
  day: number;
  liveMode: boolean;
  readOnlyDemo?: boolean;
  onDayChange: (day: number) => void;
  health: "ok" | "degraded" | "checking";
  onOpenPalette: () => void;
  onOpenHelp: () => void;
}) {
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    if (typeof window === "undefined") return "dark";
    const stored = window.localStorage.getItem("ucsm-theme");
    return stored === "light" ? "light" : "dark";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  function handleToggleTheme() {
    setTheme(toggleThemeUtil());
  }

  return (
    <header className="topbar">
      <div className="brand">
        <svg className="mark" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />
          <circle cx="12" cy="12" r="3.4" fill="currentColor" />
          <path
            d="M12 3v3M12 18v3M3 12h3M18 12h3"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
        <b title="Customer Action Control Plane">action·control</b>
        <span className="envchip">
          <b>fleetops</b>
          <span className="num" style={{ color: "var(--fg-2)" }}>
            {accountCount != null ? `${accountCount} accounts` : "…"}
          </span>
          <span className="pb">{readOnlyDemo ? "READ-ONLY DEMO" : "LIVE BOOK"}</span>
        </span>
      </div>

      <div
        className="seg"
        role="tablist"
        aria-label="Workspace view"
        onKeyDown={(event) => {
          if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
          event.preventDefault();
          const nextView = view === "book" ? "queue" : "book";
          onViewChange(nextView);
          window.requestAnimationFrame(() => {
            document.getElementById(`${nextView}-tab`)?.focus();
          });
        }}
      >
        <button
          type="button"
          role="tab"
          id="book-tab"
          aria-selected={view === "book"}
          aria-controls="book-panel"
          className={view === "book" ? "on" : ""}
          onClick={() => onViewChange("book")}
        >
          Book
        </button>
        <button
          type="button"
          role="tab"
          id="queue-tab"
          aria-selected={view === "queue"}
          aria-controls="queue-panel"
          className={view === "queue" ? "on" : ""}
          onClick={() => onViewChange("queue")}
        >
          Queue{queueCount > 0 && <span className="cnt num">{queueCount}</span>}
        </button>
      </div>

      <Link className="navlink" href="/comms-review" aria-label="Review evidence mappings">
        Evidence
      </Link>

      <button
        type="button"
        className="search"
        onClick={onOpenPalette}
        aria-label="Search accounts and commands"
      >
        <span className="ph">Search accounts…</span>
        <span className="k">⌘K</span>
      </button>

      <div className="scrub">
        <label className="lbl" htmlFor="scenario-day">
          {liveMode ? (
            <b>live</b>
          ) : (
            <>
              day <b className="num">{day}</b>
            </>
          )}
        </label>
        <input
          id="scenario-day"
          type="range"
          min={1}
          max={365}
          value={day}
          disabled={liveMode}
          onChange={(e) => onDayChange(Number(e.target.value))}
        />
      </div>

      <div className="topright">
        <button
          type="button"
          className="iconbtn"
          onClick={onOpenHelp}
          title="Shortcuts (?)"
          aria-label="Show keyboard shortcuts"
        >
          ?
        </button>
        <button
          type="button"
          className="iconbtn"
          onClick={handleToggleTheme}
          title="Theme (t)"
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
        >
          {theme === "dark" ? "☾" : "☀"}
        </button>
        <div className="live" role="status" aria-live="polite">
          <span
            className="d"
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              display: "inline-block",
              background:
                health === "ok"
                  ? "var(--ok)"
                  : health === "checking"
                    ? "var(--fg-3)"
                    : "var(--danger)",
            }}
          />
          {readOnlyDemo ? "STATIC" : health === "ok" ? "LIVE" : health === "checking" ? "…" : "DEGRADED"}
        </div>
      </div>
    </header>
  );
}
