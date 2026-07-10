"use client";

import { useEffect, useRef, useState } from "react";
import { AccountSummary } from "@/lib/api";

interface Command {
  label: string;
  action: () => void;
}

export function CommandPalette({
  open,
  onClose,
  accounts,
  onJumpToAccount,
  commands,
}: {
  open: boolean;
  onClose: () => void;
  accounts: AccountSummary[] | null;
  onJumpToAccount: (accountId: string) => void;
  commands: Command[];
}) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    const timer = window.setTimeout(() => {
      setQuery("");
      setActive(0);
      inputRef.current?.focus();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [open]);

  if (!open) return null;

  const q = query.toLowerCase();
  const matchedAccounts = (accounts ?? []).filter((a) =>
    a.account_name.toLowerCase().includes(q)
  );
  const matchedCommands = commands.filter((c) =>
    c.label.toLowerCase().includes(q)
  );

  const items: { render: React.ReactNode; act: () => void }[] = [
    ...matchedAccounts.map((a) => ({
      render: (
        <>
          <b>{a.account_name}</b>
          <span className="meta">{a.tier ?? "—"}</span>
        </>
      ),
      act: () => onJumpToAccount(a.account_id),
    })),
    ...matchedCommands.map((c) => ({
      render: <b>{c.label}</b>,
      act: c.action,
    })),
  ];

  function runActive() {
    const item = items[active];
    if (item) {
      item.act();
      onClose();
    }
  }

  return (
    <div className="scrim open" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="palette">
        <div className="pal-in">
          <input
            ref={inputRef}
            placeholder="Jump to an account, or run a command…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "Escape") onClose();
              else if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((i) => Math.min(i + 1, items.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((i) => Math.max(i - 1, 0));
              } else if (e.key === "Enter") runActive();
            }}
          />
          <span className="esc">esc</span>
        </div>
        <div className="pal-list">
          {matchedAccounts.length > 0 && <div className="pal-grp">Accounts</div>}
          {matchedAccounts.map((a, i) => (
            <div
              key={a.account_id}
              className={`pal-item${active === i ? " active" : ""}`}
              onClick={() => {
                onJumpToAccount(a.account_id);
                onClose();
              }}
            >
              <b>{a.account_name}</b>
              <span className="meta">{a.tier ?? "—"}</span>
            </div>
          ))}
          {matchedCommands.length > 0 && <div className="pal-grp">Commands</div>}
          {matchedCommands.map((c, i) => (
            <div
              key={c.label}
              className={`pal-item${active === matchedAccounts.length + i ? " active" : ""}`}
              onClick={() => {
                c.action();
                onClose();
              }}
            >
              <b>{c.label}</b>
            </div>
          ))}
          {items.length === 0 && <div className="pal-empty">No matches</div>}
        </div>
      </div>
    </div>
  );
}
