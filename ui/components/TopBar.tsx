"use client";

import { useEffect, useState } from "react";

type View = "book" | "queue";

export function TopBar({
  view,
  onViewChange,
  accountCount,
  queueCount,
  day,
  onDayChange,
  health,
}: {
  view: View;
  onViewChange: (v: View) => void;
  accountCount: number | null;
  queueCount: number;
  day: number;
  onDayChange: (day: number) => void;
  health: "ok" | "degraded" | "checking";
}) {
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const stored = window.localStorage.getItem("ucsm-theme");
    if (stored === "dark" || stored === "light") {
      setTheme(stored);
      document.documentElement.setAttribute("data-theme", stored);
    }
  }, []);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    window.localStorage.setItem("ucsm-theme", next);
  }

  return (
    <header className="topbar">
      <div className="brand">
        <svg className="mark" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />
          <circle cx="12" cy="12" r="3.4" fill="currentColor" />
          <path
            d="M12 3v3M12 18v3M3 12h3M18 12h3"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
        <b>ultra·csm</b>
        <span className="envchip">
          <b>fleetops</b>
          <span className="num" style={{ color: "var(--fg-2)" }}>
            {accountCount != null ? `${accountCount} accounts` : "…"}
          </span>
          <span className="pb">LIVE BOOK</span>
        </span>
      </div>

      <div className="seg" role="tablist">
        <button
          className={view === "book" ? "on" : ""}
          onClick={() => onViewChange("book")}
        >
          Book
        </button>
        <button
          className={view === "queue" ? "on" : ""}
          onClick={() => onViewChange("queue")}
        >
          Queue{queueCount > 0 && <span className="cnt num">{queueCount}</span>}
        </button>
      </div>

      <div className="scrub">
        <span className="lbl">
          day <b className="num">{day}</b>
        </span>
        <input
          type="range"
          min={1}
          max={365}
          value={day}
          onChange={(e) => onDayChange(Number(e.target.value))}
        />
      </div>

      <div className="topright">
        <button className="iconbtn" onClick={toggleTheme} title="Theme (t)">
          {theme === "dark" ? "☾" : "☀"}
        </button>
        <div className="live">
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
          {health === "ok" ? "LIVE" : health === "checking" ? "…" : "DEGRADED"}
        </div>
      </div>
    </header>
  );
}
